#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Dump a bridge's AssetWise inspection files to a local folder.

The API-side counterpart of the old Selenium downloader
(:mod:`ODOT_Inspection_Photo_DL`): no browser, no database — just the
pooled :class:`~civilpy.state.ohio.DOT.assetwise_client.AssetWiseClient`
and a folder. Files are organized per inspection so a folder reads like
a record::

    <folder>/Inspection - 2023/2023-01-18 DJI_0160.jpg
    <folder>/Inspection - 2023/2023-11-13 CUY-10-1613 2023 Inspection Report.pdf
    <folder>/Inspection - 2021/2021-01-06 North elevation.jpg

AssetWise keeps files in two attachment scopes and neither is a superset
of the other: per approved report (``AssetFilesReportMap`` — filename,
caption, date) and per asset (``AssetFile/GetByAssetId`` — content type
only, the name arrives on the download's Content-Disposition). The dump
takes the union, routes by content type, and names files
``YYYY-MM-DD <caption or filename>.<ext>``, Windows-safe.

Usage::

    from civilpy.state.ohio.DOT.assetwise_files import dump_inspection_files
    dump_inspection_files("1801503", "C:/TEMP/1801503")            # photos
    dump_inspection_files("1801503", "C:/TEMP/1801503", photos_only=False)

or ``civilpy odot photos 1801503 --folder C:/TEMP/1801503``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import mimetypes
import re
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

IMAGE_PREFIX = "image/"
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WS = re.compile(r"\s+")
_EXT_OVERRIDES = {
    "image/jpeg": ".jpg", "image/bitmap": ".bmp", "image/bmp": ".bmp",
    "image/tiff": ".tif", "application/octet-stream": "",
}


def safe_name(text: str, max_len: int = 120) -> str:
    """A Windows-safe filename stem: reserved characters become ``_``,
    whitespace collapses, trailing dots/spaces are stripped."""
    out = _WS.sub(" ", _UNSAFE.sub("_", text or "")).strip().strip(". ")
    return out[:max_len].rstrip(". ") or "untitled"


def extension_for(content_type: str, hint: str = "") -> str:
    """Extension from the original filename when there is one, else from
    the content type."""
    hint_ext = PurePosixPath(hint or "").suffix.lower()
    if hint_ext and len(hint_ext) <= 6:
        return hint_ext
    ct = (content_type or "").split(";")[0].strip().lower()
    if not ct:
        return ""
    if ct in _EXT_OVERRIDES:
        return _EXT_OVERRIDES[ct]
    return mimetypes.guess_extension(ct) or ""


def _content_type(row: dict, fallback: str = "") -> str:
    ct = (row.get("af_content_type") or "").split(";")[0].strip().lower()
    if not ct:
        guessed, _ = mimetypes.guess_type(row.get("af_filename") or "")
        ct = (guessed or "").lower()
    return ct or (fallback.split(";")[0].strip().lower() if fallback else "")


def _date(value) -> Optional[_dt.date]:
    from civilpy.state.ohio.DOT.assetwise_client import parse_api_datetime
    dt = parse_api_datetime(value)
    return dt.date() if dt else None


def list_inspection_files(client, as_id: int) -> List[Dict]:
    """Every file attached to the asset — report-mapped rows (with the
    report they belong to) plus asset-level rows reachable through no
    report — deduplicated by ``af_id`` (a file mapped on several reports
    is listed once, against the earliest report)."""
    reports = client.get_inspections(as_id) or []
    seen: Dict[int, Dict] = {}
    for report in sorted(reports, key=lambda r: str(r.get("ast_inspection_date") or "")):
        ast_id = report.get("ast_id")
        if not ast_id:
            continue
        report_date = _date(report.get("ast_inspection_date"))
        for row in client.get_report_files(ast_id) or []:
            af_id = row.get("af_id")
            if not af_id or af_id in seen:
                continue
            seen[af_id] = {
                "af_id": af_id, "ast_id": ast_id, "report_date": report_date,
                "filename": (row.get("af_filename") or "").strip(),
                "caption": (row.get("af_description") or "").strip(),
                "content_type": _content_type(row),
                "file_date": _date(row.get("af_date") or row.get("af_date_inserted")),
                "scope": "report", "cover": bool(row.get("af_cover")),
                "in_report": bool(row.get("af_print")),
            }
    get_asset_files = getattr(client, "get_asset_files", None)
    for row in (get_asset_files(as_id) if get_asset_files else []) or []:
        af_id = row.get("af_id")
        if not af_id or af_id in seen:
            continue
        seen[af_id] = {
            "af_id": af_id, "ast_id": None, "report_date": None,
            "filename": (row.get("af_filename") or "").strip(),
            "caption": "", "content_type": _content_type(row),
            "file_date": _date(row.get("af_date_inserted") or row.get("af_date")),
            "scope": "asset", "cover": False, "in_report": False,
        }
    return list(seen.values())


def target_path(folder: Path, item: Dict, *, flat: bool = False,
                served_name: str = "", content_type: str = "") -> Path:
    """``<folder>/Inspection - YYYY/YYYY-MM-DD <name>.<ext>`` for one
    listed file (``flat`` drops the year folder)."""
    ct = item["content_type"] or content_type
    name_hint = item["filename"] or served_name
    ext = extension_for(ct, name_hint)
    title = item["caption"] or name_hint or f"assetwise_{item['af_id']}"
    if ext and title.lower().endswith(ext):
        title = title[: -len(ext)]
    stamp = item.get("file_date") or item.get("report_date")
    year = (item.get("report_date") or item.get("file_date"))
    stem = safe_name(f"{stamp.isoformat()} {title}" if stamp else title)
    sub = folder if flat or year is None else folder / f"Inspection - {year.year}"
    return sub / f"{stem}{ext}"


def _dedupe(path: Path, taken: set) -> Path:
    candidate, n = path, 1
    while candidate in taken or candidate.exists():
        n += 1
        candidate = path.with_name(f"{path.stem} [{n}]{path.suffix}")
    taken.add(candidate)
    return candidate


def dump_inspection_files(sfn_or_as_id, folder, *, photos_only: bool = True,
                          flat: bool = False, client=None, max_workers: int = 8,
                          progress: Optional[Callable[[str], None]] = None) -> Dict:
    """Download a bridge's AssetWise inspection files into ``folder``.

    ``sfn_or_as_id`` is the SFN (resolved through ``GetAssetByAsCode``) or
    an integer AssetWise asset id. ``photos_only`` keeps images and skips
    the report-attached PDFs. Returns a summary::

        {'as_id', 'listed', 'written', 'skipped', 'failed', 'files': [...]}

    A 404 on download is a vendor-side orphan (dangling file row) and
    counts as ``failed`` rather than raising.
    """
    if client is None:
        from civilpy.state.ohio.DOT.assetwise_client import AssetWiseClient
        client = AssetWiseClient()
    folder = Path(folder).expanduser()
    if isinstance(sfn_or_as_id, int) or str(sfn_or_as_id).isdigit() and len(str(sfn_or_as_id)) < 7:
        as_id = int(sfn_or_as_id)
    else:
        as_id = client.get_as_id(str(sfn_or_as_id))
    if not as_id:
        raise LookupError(f"{sfn_or_as_id!r} could not be resolved to an AssetWise asset")

    items = list_inspection_files(client, as_id)
    summary = {"as_id": as_id, "listed": len(items), "written": 0,
               "skipped": 0, "failed": 0, "files": []}
    jobs = []
    for item in items:
        ct = item["content_type"]
        if photos_only and ct and not ct.startswith(IMAGE_PREFIX):
            summary["skipped"] += 1
            continue
        jobs.append(item)
    folder.mkdir(parents=True, exist_ok=True)
    taken: set = set()

    def _download(item):
        fn = getattr(client, "download_file_named", None)
        if fn:
            return fn(item["af_id"])
        content, ctype = client.download_file(item["af_id"])
        return content, ctype, ""

    for item, result in client.map_assets(_download, jobs, max_workers=max_workers):
        content, ctype, served = ((None, "", "") if isinstance(result, Exception)
                                  else result)
        if not content:
            summary["failed"] += 1
            continue
        ct = item["content_type"] or (ctype or "").split(";")[0].strip().lower()
        if photos_only and not ct.startswith(IMAGE_PREFIX):
            summary["skipped"] += 1
            continue
        dest = _dedupe(target_path(folder, item, flat=flat, served_name=served,
                                   content_type=ct), taken)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        summary["written"] += 1
        summary["files"].append(str(dest))
        if progress:
            progress(dest.name)
    logger.info("assetwise dump %s → %s: %s", sfn_or_as_id, folder,
                {k: v for k, v in summary.items() if k != "files"})
    return summary
