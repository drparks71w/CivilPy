#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""Connection-pooled client for the Bentley AssetWise REST API (ODOT).

This is the canonical client for the ODOT AssetWise integration. It supersedes
the scattered per-call ``requests.get(..., auth=HTTPBasicAuth(...))`` helpers in
``AssetWise.py``: a single :class:`AssetWiseClient` instance reuses one
``requests.Session`` (TCP + TLS connection pooling), retries transient failures
with exponential backoff, and exposes both per-asset and batch endpoints plus a
thread-pooled fan-out helper for the inherently per-asset endpoints (elements,
inspections, cover images).

Importing this module has no side effects and needs no credentials; auth is
loaded lazily when a client is instantiated.
"""
import datetime
import logging
import random
import re
from urllib.parse import unquote
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.auth import HTTPBasicAuth

from .credentials import get_assetwise_secrets

logger = logging.getLogger(__name__)

BASE_URL = "https://ohiodot-it-api.bentley.com"

# Matches the legacy Microsoft JSON date format: /Date(1700000000000)/
# optionally with a trailing timezone offset like /Date(1700000000000-0500)/
_MS_DATE_RE = re.compile(r"/Date\((-?\d+)([+-]\d{4})?\)/")


def parse_api_datetime(value):
    """Best-effort parse of a date string returned by the AssetWise API.

    Handles ISO 8601 (with or without a 'Z'/offset) and the legacy
    Microsoft ``/Date(ms)/`` format. Returns a timezone-aware UTC
    ``datetime`` or ``None`` if the value can't be parsed.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        dt = value
    else:
        s = str(value).strip()
        if not s:
            return None
        m = _MS_DATE_RE.search(s)
        if m:
            millis = int(m.group(1))
            dt = datetime.datetime.fromtimestamp(millis / 1000.0, tz=datetime.timezone.utc)
        else:
            iso = s.replace("Z", "+00:00")
            try:
                dt = datetime.datetime.fromisoformat(iso)
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class AssetWiseClient:
    """Reusable, connection-pooled HTTP client for the AssetWise API.

    Uses ``requests.Session`` for connection pooling (TCP + TLS reuse), which
    significantly reduces latency when making hundreds of calls. Subclasses may
    override :meth:`_load_auth` to source credentials differently.
    """

    def __init__(self, base_url=BASE_URL):
        self.session = requests.Session()
        self.session.auth = self._load_auth()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        self.base_url = base_url

    @staticmethod
    def _load_auth():
        """Build the HTTP Basic auth from the cached AssetWise secrets."""
        key_name, api_key = get_assetwise_secrets()
        return HTTPBasicAuth(key_name, api_key)

    # ------------------------------------------------------------------
    # Low-level request helper
    # ------------------------------------------------------------------
    def _get_with_retry(self, url, params=None, max_retries=3, backoff_factor=1):
        """Execute a GET with exponential backoff on transient failures.

        4xx responses (except 429) are deterministic — the server will give
        the same answer every time — so they raise immediately instead of
        burning retries. Callers that expect 404s (missing asset, no report
        container) catch HTTPError and translate it.
        """
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, 'status_code', None)
                if status is not None and 400 <= status < 500 and status != 429:
                    logger.debug("HTTP %s for %s — permanent client error, "
                                 "not retrying", status, url)
                    raise
                logger.warning("Request failed (attempt %d/%d) for %s: %s",
                               attempt + 1, max_retries, url, e)
                if attempt == max_retries - 1:
                    logger.error("Max retries exceeded for %s.", url)
                    raise
                jitter = random.uniform(0, backoff_factor)
                time.sleep(backoff_factor * (2 ** attempt) + jitter)
            except requests.exceptions.RequestException as e:
                logger.warning("Request failed (attempt %d/%d) for %s: %s",
                               attempt + 1, max_retries, url, e)
                if attempt == max_retries - 1:
                    logger.error("Max retries exceeded for %s.", url)
                    raise
                jitter = random.uniform(0, backoff_factor)
                time.sleep(backoff_factor * (2 ** attempt) + jitter)
        return None  # pragma: no cover

    @staticmethod
    def _http_status(exc):
        """Status code from a requests exception, or None."""
        return getattr(getattr(exc, 'response', None), 'status_code', None)

    # ------------------------------------------------------------------
    # Asset identity
    # ------------------------------------------------------------------
    def get_as_id(self, sfn):
        """Resolve a bridge SFN to its internal as_id (one API call).

        Returns None when the SFN can't be resolved; a 404 means the asset
        no longer exists in AssetWise (removed or renumbered) — a stale
        local inventory row, not a network problem.
        """
        url = f"{self.base_url}/api/Asset/GetAssetByAsCode/{sfn}"
        try:
            resp = self._get_with_retry(
                url, params={"IncludeCoordinates": False, "IncludeParent": False})
            if resp:
                data = resp.json()
                if data.get('success') and data.get('data'):
                    return data['data'].get('as_id')
        except Exception as e:
            if self._http_status(e) == 404:
                logger.warning(
                    "SFN %s: not found in AssetWise (GetAssetByAsCode 404) — "
                    "asset was removed or renumbered; local inventory row is "
                    "stale", sfn)
            else:
                logger.error("Failed to fetch as_id for SFN %s: %s", sfn, e)
        return None

    def iter_all_assets(self, page_size=500, max_records=200000):
        """Yield every asset (ApiAsset dicts) via paged POST /Asset/GetAssets.

        Each dict carries at least ``as_id`` and ``as_code`` (the SFN). Used by
        the bulk full-inventory sync to obtain (as_id, as_code) pairs without a
        per-bridge GetAssetByAsCode round-trip.
        """
        url = f"{self.base_url}/api/Asset/GetAssets"
        starting = 0
        while True:
            payload = {"starting": starting, "count": page_size}
            try:
                resp = self.session.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                logger.error("GetAssets failed at starting=%d: %s", starting, e)
                return
            items = data.get('data', []) if isinstance(data, dict) else []
            if not items:
                return
            for item in items:
                yield item
            if len(items) < page_size:
                return
            starting += page_size
            if starting >= max_records:
                logger.warning("iter_all_assets hit safety limit of %d", max_records)
                return

    # ------------------------------------------------------------------
    # Current values
    # ------------------------------------------------------------------
    def get_current_values(self, as_id):
        """Fetch all current field values for one asset as ``{fe_id: value}``."""
        url = f"{self.base_url}/api/CurrentValue/GetCurrentValuesByAssetId/{as_id}"
        try:
            resp = self.session.get(url)
            if resp.status_code != 200:
                logger.warning("CurrentValues returned %d for as_id=%s", resp.status_code, as_id)
                return {}
            data = resp.json()
            if not data.get('success'):
                return {}
            lookup = {}
            for item in data.get('data', []):
                fid = item.get('fe_id')
                val = item.get('cv_value') or item.get('value') or item.get('va_value')
                if fid is not None:
                    lookup[fid] = val
            return lookup
        except Exception as e:
            logger.error("Failed to fetch CurrentValues for as_id=%s: %s", as_id, e)
            return {}

    def get_current_values_for_assets(self, as_ids, fe_ids=None):
        """Batch-fetch CurrentValues for many assets in one POST.

        Calls ``POST /CurrentValue/GetCurrentValuesByAssetIds``. Returns the raw
        list of value rows (each a dict with ``as_id``, ``fe_id``, ``cv_value``).
        Optionally restrict to ``fe_ids`` to keep the payload small.
        """
        url = f"{self.base_url}/api/CurrentValue/GetCurrentValuesByAssetIds"
        payload = {"as_ids": list(as_ids)}
        if fe_ids:
            payload["fe_ids"] = list(fe_ids)
        try:
            resp = self.session.post(url, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            if not data.get('success'):
                logger.warning("GetCurrentValuesByAssetIds returned success=false "
                               "for %d assets", len(payload['as_ids']))
                return []
            return data.get('data', [])
        except requests.exceptions.RequestException as e:
            logger.error("GetCurrentValuesByAssetIds failed for %d assets: %s",
                         len(payload['as_ids']), e)
            return []

    @staticmethod
    def group_values_by_asset(rows):
        """Collapse a flat list of CurrentValue rows into ``{as_id: {fe_id: value}}``."""
        grouped = {}
        for row in rows:
            as_id = row.get('as_id')
            fe_id = row.get('fe_id')
            if as_id is None or fe_id is None:
                continue
            val = row.get('cv_value')
            if val is None:
                val = row.get('value') or row.get('va_value')
            grouped.setdefault(as_id, {})[fe_id] = val
        return grouped

    # ------------------------------------------------------------------
    # Elements / inspections
    # ------------------------------------------------------------------
    def get_current_elements(self, asset_id):
        """Fetch current bridge elements via asset_id (ObjectType 0)."""
        url = f"{self.base_url}/api/StructureElement/GetElements/0/{asset_id}/{asset_id}/0/0"
        try:
            resp = self._get_with_retry(url)
            if resp:
                data = resp.json()
                if isinstance(data, dict):
                    return data.get('value') or data.get('data') or []
                elif isinstance(data, list):
                    return data
        except Exception as e:
            logger.error("Failed to fetch current elements for asset=%s: %s", asset_id, e)
        return []

    def get_structure_elements(self, report_id, asset_id):
        """Fetch bridge elements for a specific inspection report."""
        url = f"{self.base_url}/api/StructureElement/GetElements/1/{report_id}/{asset_id}"
        try:
            resp = self.session.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    return data.get('value') or data.get('data') or []
                elif isinstance(data, list):
                    return data
            else:
                logger.warning("GetElements returned %d for report=%s asset=%s",
                               resp.status_code, report_id, asset_id)
        except Exception as e:
            logger.error("Failed to fetch elements for report=%s asset=%s: %s",
                         report_id, asset_id, e)
        return []

    def get_inspections(self, asset_id):
        """Fetch all approved inspections for an asset.

        Returns [] when the asset has reports but none approved, and None
        when GetAllApproved 404s — the asset has no inspection-report
        container at all (brand-new or skeletal asset). Both are falsy, so
        ``if not inspections`` keeps working for callers that don't care.
        """
        url = f"{self.base_url}/api/InspectionReport/GetAllApproved/{asset_id}"
        try:
            resp = self._get_with_retry(url)
            if resp:
                data = resp.json()
                if data.get('success'):
                    return data.get('data', [])
        except Exception as e:
            if self._http_status(e) == 404:
                logger.warning(
                    "asset=%s: no inspection-report container "
                    "(GetAllApproved 404) — new or skeletal asset, nothing "
                    "to sync", asset_id)
                return None
            logger.error("Failed to fetch inspections for asset=%s: %s", asset_id, e)
        return []

    def get_report_inspection_types(self, ast_id):
        """it_ids covered by one report (InspectionReportInspTypeMap).

        A report's rt_id is always 1 in ODOT's data — the inspection type(s)
        a report actually performed live in this map (1/6=Routine,
        3/7=Underwater, 2/8=FC/NSTM, 4/11=Special, 5=Initial, 9=Damage,
        10=In-Depth, 12=Service; legacy/SNBI pairs).
        """
        url = (f"{self.base_url}/api/InspectionReportInspTypeMap/"
               f"GetAllReportInspectionTypeMap/{ast_id}")
        try:
            resp = self._get_with_retry(url)
            if resp:
                data = resp.json().get('data', []) or []
                return [m.get('it_id') for m in data if m.get('it_id')]
        except Exception as e:
            logger.error("Failed to fetch inspection-type map for report=%s: %s",
                         ast_id, e)
        return []

    def get_full_inspection_report(self, ast_id):
        """Fetch the full inspection report values via ast_id."""
        url = f"{self.base_url}/api/Value/GetValuesForReport/{ast_id}"
        try:
            resp = self._get_with_retry(url)
            if resp:
                data = resp.json()
                if data.get('success'):
                    return data.get('data', [])
        except Exception as e:
            logger.error("Failed to fetch full report for ast_id=%s: %s", ast_id, e)
        return []

    # ------------------------------------------------------------------
    # Field metadata / media
    # ------------------------------------------------------------------
    def get_field_name(self, fe_id):
        """Fetch a field's display name. Used for debugging/discovery."""
        url = f"{self.base_url}/api/Field/{fe_id}"
        try:
            resp = self.session.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    return data['data'].get('fe_name', 'Unknown')
        except Exception:
            pass
        return "Unknown"

    def get_cover_image(self, as_id, timeout=15):
        """Return the raw cover-image bytes for an asset, or ``None``.

        A 404 (no photo on file) returns ``None`` rather than raising.
        """
        url = f"{self.base_url}/api/AssetFile/GetAssetCoverImage/{as_id}"
        try:
            resp = self.session.get(
                url, headers={"Accept": "application/octet-stream"}, timeout=timeout)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
        except requests.exceptions.RequestException as e:
            logger.error("Failed to fetch cover image for as_id=%s: %s", as_id, e)
            return None

    def get_report_files(self, ast_id):
        """Files mapped to one inspection report (AssetFilesReportMap).

        Files attached to a report persist for historical reports
        (verified 2026-08-21: approved reports back to 2020 all kept their
        maps), so iterating a bridge's approved reports recovers the full
        report-attachment history. The report map and the asset-level list
        (:meth:`get_asset_files`) are DIFFERENT attachment scopes and
        neither is a superset of the other: one bridge keeps its photos
        only in report maps, another (e.g. SFN 1801503, 2026-08-28) keeps
        its photos only at asset level and its report maps hold only PDFs
        (UW reports, FCM plans). Pull the union and route by content type.
        Rows carry ``af_id`` (the download key), ``af_filename``,
        ``af_description`` (caption), ``af_date``, and
        ``af_cover``/``af_print`` flags. Returns [] when the report has no
        mapped files.
        """
        url = (f"{self.base_url}/api/AssetFilesReportMap/"
               f"GetMapsForReportByAstId/{ast_id}")
        try:
            resp = self._get_with_retry(url)
            if resp:
                data = resp.json()
                rows = data.get('data') if isinstance(data, dict) else data
                return rows or []
        except Exception as e:
            logger.error("Failed to fetch report file map for ast_id=%s: %s",
                         ast_id, e)
        return []

    def get_asset_files(self, as_id):
        """Asset-level file list (``AssetFile/GetByAssetId``).

        Rows carry ``af_id``, ``af_size``, ``af_content_type`` (e.g.
        ``image/jpeg``, ``image/bitmap``, ``application/pdf``),
        ``af_date_inserted`` and ``af_deleted``; there is NO filename or
        caption at this level. Deleted rows are dropped. Returns [] on
        error. See :meth:`get_report_files` for how this relates to the
        per-report map.
        """
        url = f"{self.base_url}/api/AssetFile/GetByAssetId/{as_id}"
        try:
            resp = self._get_with_retry(url)
            if resp:
                data = resp.json()
                rows = data.get('data') if isinstance(data, dict) else data
                return [r for r in (rows or []) if not r.get('af_deleted')]
        except Exception as e:
            logger.error("Failed to fetch asset file list for as_id=%s: %s",
                         as_id, e)
        return []

    @staticmethod
    def _disposition_filename(headers):
        """Filename from a ``Content-Disposition`` header — the RFC 5987
        ``filename*=UTF-8''...`` form first, else the quoted ``filename=``.
        AssetWise's download endpoint is the ONLY place the original
        filename of an asset-level file is exposed (the GetByAssetId rows
        carry just a GUID)."""
        cd = headers.get('Content-Disposition', '') or ''
        m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I)
        if m:
            return unquote(m.group(1).strip())
        m = re.search(r'filename="?([^";]+)"?', cd, re.I)
        return m.group(1).strip() if m else ''

    def download_file_named(self, af_id, timeout=120):
        """Download one asset file by ``af_id``.

        Returns ``(bytes, content_type, filename)``; ``(None, '', '')`` on
        failure or 404 (AssetWise keeps dangling file rows whose bytes are
        gone — a 404 here is a vendor-side orphan, not a transport error).
        Report photos are full-resolution originals (a few MB each), so
        batch callers should parallelize with :meth:`map_assets`.
        """
        url = f"{self.base_url}/api/AssetFile/Download/{af_id}"
        try:
            resp = self.session.get(
                url, headers={"Accept": "application/octet-stream"},
                timeout=timeout)
            if resp.status_code == 404:
                return None, '', ''
            resp.raise_for_status()
            return (resp.content, resp.headers.get('Content-Type', ''),
                    self._disposition_filename(resp.headers))
        except requests.exceptions.RequestException as e:
            logger.error("Failed to download af_id=%s: %s", af_id, e)
            return None, '', ''

    def download_file(self, af_id, timeout=120):
        """:meth:`download_file_named` without the filename —
        ``(bytes, content_type)`` or ``(None, '')``."""
        content, ctype, _ = self.download_file_named(af_id, timeout=timeout)
        return content, ctype

    def file_name(self, af_id, timeout=30):
        """Original filename of an asset file without downloading it:
        a streamed GET whose body is closed after the headers arrive.
        Returns '' when unknown."""
        url = f"{self.base_url}/api/AssetFile/Download/{af_id}"
        try:
            resp = self.session.get(
                url, headers={"Accept": "application/octet-stream"},
                timeout=timeout, stream=True)
            try:
                if resp.status_code != 200:
                    return ''
                return self._disposition_filename(resp.headers)
            finally:
                resp.close()
        except requests.exceptions.RequestException as e:
            logger.error("Failed to read filename for af_id=%s: %s", af_id, e)
            return ''

    # ------------------------------------------------------------------
    # Differential sync
    # ------------------------------------------------------------------
    def fetch_updated_assets(self, start_date, count=1000):
        """Return assets modified after ``start_date`` (ApiAsset dicts).

        Two safeguards against the observed bug where the endpoint returned the
        *entire* inventory regardless of ``start_date``:

        1. The timestamp is sent as a plain UTC instant ending in ``Z`` with no
           sub-second component. A naive ``datetime.isoformat()`` emits a
           ``+00:00`` offset that the .NET model binder can fail to parse,
           silently falling back to ``DateTime.MinValue`` (year 1) and matching
           every asset.
        2. Returned assets are filtered client-side against ``start_date`` using
           ``as_last_update_date``. Assets with a missing/unparseable date are
           kept (fail-open) so a schema surprise never drops a real update.
        """
        url = f"{self.base_url}/api/Asset/GetAssetsUpdatedAfter"

        if isinstance(start_date, datetime.datetime):
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            start_utc = start_date.astimezone(datetime.timezone.utc).replace(microsecond=0)
        else:
            start_utc = datetime.datetime.combine(
                start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
        time_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "root": 0,
            "assetDef": 0,
            "time": time_str,
            "starting": 0,
            "count": count,
        }
        logger.debug("GetAssetsUpdatedAfter payload: %s", payload)

        all_assets = []
        while True:
            try:
                resp = self.session.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                items = data.get('data', [])
                if items:
                    all_assets.extend(items)
                if len(items) < payload['count']:
                    break
                payload['starting'] += payload['count']
                if payload['starting'] > 100000:
                    logger.warning("Hit safety limit of 100k records")
                    break
            except requests.exceptions.RequestException as e:
                logger.error("GetAssetsUpdatedAfter failed: %s", e)
                break

        return self._filter_assets_since(all_assets, start_utc)

    @staticmethod
    def _filter_assets_since(assets, start_utc):
        """Drop assets whose ``as_last_update_date`` predates ``start_utc`` (fail-open)."""
        kept, dropped = [], 0
        for a in assets:
            updated = parse_api_datetime(a.get('as_last_update_date'))
            if updated is not None and updated < start_utc:
                dropped += 1
                continue
            kept.append(a)
        if dropped:
            logger.info(
                "fetch_updated_assets: dropped %d assets older than %s "
                "(server returned %d, kept %d)",
                dropped, start_utc.isoformat(), len(assets), len(kept))
        return kept

    # ------------------------------------------------------------------
    # Concurrency helper
    # ------------------------------------------------------------------
    def map_assets(self, fn, items, max_workers=10):
        """Run ``fn(item)`` across ``items`` concurrently over the pooled session.

        Yields ``(item, result)`` tuples as they complete. An exception raised by
        ``fn`` is yielded as the result (not raised) so one bad asset can't abort
        the batch — callers decide how to handle it. The shared ``Session`` is
        thread-safe for this read-mostly use.
        """
        items = list(items)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {executor.submit(fn, item): item for item in items}
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    yield item, future.result()
                except Exception as e:  # surfaced to caller, not raised
                    logger.error("map_assets: %r failed: %s", item, e)
                    yield item, e
