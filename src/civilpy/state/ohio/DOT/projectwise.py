# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT ProjectWise plan discovery.

Find as-built / repair / maintenance plan sets for a bridge, using the two
ODOT ProjectWise datasources mapped in 2026:

- **PlanVault archive** (``pw-03``): 21k compiled plan-set PDFs keyed by PID
  in the filename grammar and by a short ``{CTY}-{PID}`` description key.
  Queried offline through an inventory CSV cache (see
  :func:`load_planvault_inventory`) — refresh the cache weekly with the
  snbi_ui *Bridge Plan Puller* notebook.
- **Active projects** (``pw-02``): live design files under
  ``01 Active Projects/District NN/County/{PID}/400-Engineering/Structures/
  SFN_{sfn}``, queried through the native API (Windows +
  logged-in ProjectWise Explorer required — everything else in this module
  runs anywhere).

Typical use::

    from civilpy import projectwise as pw

    inv = pw.load_planvault_inventory("pw_archive_inventory.csv")
    result = pw.find_plans_by_sfn("2510774", inv)      # TIMS lookup for PIDs
    hits = pw.find_plans_by_pid("116581", inv)         # direct PID lookup

    # on an ODOT Windows box with PW Explorer running:
    sheets = pw.get_structures_sheets("112665", district="06",
                                      county="Franklin", sfn="2510774")
"""
from __future__ import annotations

import csv
import re

import requests

# --- Datasources & known anchors (verified on-box 2026-07-21) ---------------
DATASOURCE_ACTIVE = "ohiodot-pw.bentley.com:ohiodot-pw-02"
DATASOURCE_ARCHIVE = "ohiodot-pw.bentley.com:ohiodot-pw-03"

PLANVAULT_GUID = "1bdc7305-e848-47f2-8ef3-d5b0c4bfe46f"
PLANVAULT_FOLDER_ID = 8152
PLANVAULT_DISTRICT_FOLDERS = {
    "01": 8198, "02": 8199, "03": 8200, "04": 8201, "05": 8202, "06": 8203,
    "07": 8204, "08": 8205, "09": 8206, "10": 8207, "11": 8208, "12": 8209,
}

# Paths under 01 Active Projects.  The root segment ("Documents") may need
# adjustment after the first resolve-by-name-path test on the ODOT box.
ACTIVE_PROJECT_PATH = (
    "Documents\\01 Active Projects\\District {district}\\{county}\\{pid}"
)
ACTIVE_STRUCTURES_PATH = ACTIVE_PROJECT_PATH + "\\400-Engineering\\Structures"

# --- Grammars ----------------------------------------------------------------
#: PlanVault filename: D{dd}-{PID}-{CTY}-{ROUTE}-{SLM}-{YEAR}-{NN}.pdf
PLAN_SET_GRAMMAR = re.compile(
    r"D(?P<district>\d{2})-(?P<pid>\d+)-(?P<county>[A-Z]{3})-(?P<route>\w+)"
    r"-(?P<slm>[\d.]+)-(?P<year>\d{4})-(?P<sheet>\d{2})", re.IGNORECASE)

#: PlanVault description key: {CTY}-{PID}.pdf
SHORT_DESC_GRAMMAR = re.compile(
    r"(?P<county>[A-Z]{3})-(?P<pid>\d+)\.pdf$", re.IGNORECASE)

#: Active-project sheet: {PID}_SFN_{SFN}_{sheet}.dgn / {PID}_{SFN}_{sheet}.pdf
ACTIVE_SHEET_GRAMMAR = re.compile(
    r"(?P<pid>\d+)_(?:SFN_)?(?P<sfn>\d{7})_(?P<sheet>\w+)\.(?P<ext>\w+)$",
    re.IGNORECASE)

#: Bridge display name: {CTY}-{ROUTE}-{SLM}[L|R|C]
BRIDGE_NAME_GRAMMAR = re.compile(
    r"^(?P<county>[A-Z]{3})-(?P<route>[A-Z0-9]+)"
    r"-(?P<slm>[\d.]+)(?P<suffix>[LRC]?)", re.IGNORECASE)

_TIMS_PROJECTS_URL = ("https://tims.dot.state.oh.us/ags/rest/services/Projects/"
                      "All_Project_Points/MapServer/0/query")


def sfn_to_pids(sfn, timeout=60):
    """Construction/project PIDs for an SFN via the public TIMS Projects layer.

    Works from any network (no ODOT VPN needed).  Returns a sorted list of
    PID strings; empty when TIMS has no project link for the bridge.
    """
    r = requests.post(_TIMS_PROJECTS_URL, data={
        "where": f"STRUCTURE_FILE_NBR='{sfn}'",
        "outFields": "PID_NBR", "returnGeometry": False, "f": "json",
    }, timeout=timeout)
    r.raise_for_status()
    return sorted({str(f["attributes"]["PID_NBR"])
                   for f in r.json().get("features", [])
                   if f["attributes"].get("PID_NBR")})


#: Key in ``~/secrets.json`` whose value is the path of a *definitions* JSON
#: describing the agency's internal SFN->project database.  The definitions
#: file (kept outside this package — schemas are institution-private) has
#: three generic keys::
#:
#:     {
#:       "odbc":      "<pyodbc connection string>",
#:       "sfn_query": "<SQL with exactly one ? parameter (the SFN)>",
#:       "columns":   ["sfn", "pid", "label", "work_category", "status", ...]
#:     }
#:
#: ``columns`` names the generic key for each column of the result set, in
#: order; ``pid`` is required, anything else is optional and rides along.
PROJECT_DB_SECRETS_KEY = "PROJECT_DB_DEFINITIONS"


def load_project_db_definitions(path=None):
    """The project-DB definitions dict, or ``None`` when not configured.

    Resolution: explicit ``path`` argument, else ``~/secrets.json``'s
    :data:`PROJECT_DB_SECRETS_KEY` entry.  Never raises for the ordinary
    "not set up on this machine" cases.
    """
    import json
    from pathlib import Path
    if path is None:
        try:
            with open(Path.home() / "secrets.json") as fh:
                path = json.load(fh).get(PROJECT_DB_SECRETS_KEY)
        except (OSError, ValueError):
            return None
        if not path:
            return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def query_projects_by_sfn(sfn, definitions=None, _connect=None):
    """Query the agency's internal project database for a bridge's projects.

    Schema-free by design: the connection string, query text, and column
    mapping all come from the definitions file (see
    :data:`PROJECT_DB_SECRETS_KEY`), so this works identically for anyone —
    with the definitions file and network access it returns live rows; without
    them it returns ``None`` and callers fall back to public sources.

    Returns a list of generic project dicts (``pid`` plus whatever the
    definitions map), ``[]`` for a connected-but-no-rows bridge, or ``None``
    when unconfigured/unreachable.
    """
    definitions = definitions or load_project_db_definitions()
    if not definitions:
        return None
    try:
        if _connect is None:
            import pyodbc
            _connect = pyodbc.connect
        with _connect(definitions["odbc"], timeout=8) as cn:
            cur = cn.cursor()
            cur.execute(definitions["sfn_query"], str(sfn).strip())
            raw = cur.fetchall()
    except Exception:
        return None
    keys = definitions.get("columns", ["sfn", "pid"])
    rows = []
    for record in raw:
        row = {k: ("" if v is None else str(v).strip())
               for k, v in zip(keys, record)}
        pid = row.get("pid", "")
        pid = pid.split(".")[0] if pid else ""     # numeric PIDs arrive as floats
        if pid:
            row["pid"] = pid
            rows.append(row)
    return rows


def parse_slm(text):
    """SLM string -> float miles. No decimal point means implied hundredths
    (``'2292'`` -> 22.92, matching ODOT bridge display names)."""
    s = str(text).strip()
    return float(s) if "." in s else int(s) / 100.0


def load_planvault_inventory(path):
    """Load the PlanVault inventory CSV (from the Puller's Probe C) and attach
    parsed keys to each row: ``pid``, ``county``, ``route``, ``slm``,
    ``year`` (None where the grammar doesn't parse)."""
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m = PLAN_SET_GRAMMAR.search(r.get("filename") or r.get("name") or "")
            d = SHORT_DESC_GRAMMAR.search(r.get("desc") or "")
            r["pid"] = (m and m["pid"]) or (d and d["pid"]) or None
            r["county"] = ((m and m["county"]) or (d and d["county"]) or None)
            if r["county"]:
                r["county"] = r["county"].upper()
            r["route"] = m and m["route"].lstrip("0").upper() or None
            try:
                r["slm"] = parse_slm(m["slm"]) if m else None
            except ValueError:
                r["slm"] = None
            r["year"] = int(m["year"]) if m else None
            rows.append(r)
    return rows


def find_plans_by_pid(pid, inventory):
    """PlanVault rows whose filename or description key carries this PID."""
    pid = str(pid).lstrip("0")
    return [r for r in inventory
            if r.get("pid") and r["pid"].lstrip("0") == pid]


def find_plans_by_bridge_key(county, route, slm, inventory, tol=0.20):
    """PlanVault rows matching county + route with SLM within ``tol`` miles.

    Weaker than a PID match (a project's SLM need not equal the bridge's) —
    treat results as candidates for review.
    """
    county = county.upper()
    route = str(route).lstrip("0").upper() or "0"
    slm = float(slm)
    out = []
    for r in inventory:
        if r.get("county") == county and r.get("route") == route \
                and r.get("slm") is not None and abs(r["slm"] - slm) <= tol:
            out.append(dict(r, slm_delta=round(abs(r["slm"] - slm), 3)))
    return sorted(out, key=lambda r: r["slm_delta"])


def find_plans_by_sfn(sfn, inventory, pids=None, project_rows=None,
                      bridge_name=None, tol=0.20):
    """Every PlanVault plan set discoverable for an SFN.

    PID sources, in priority order:

    - ``pids`` — an explicit iterable of PID strings;
    - ``project_rows`` — dicts with at least a ``pid`` key (extras like a
      work-type label or status ride along into the result).  Agencies with a
      richer internal SFN→project crosswalk than public TIMS should inject it
      here — TIMS only reaches back a handful of years;
    - the internal project database, when configured
      (:func:`query_projects_by_sfn` via the secrets-referenced definitions
      file);
    - finally a live TIMS lookup (:func:`sfn_to_pids`).

    ``bridge_name`` (``'FRA-00270-22.66'``) enables the county-route-SLM
    fallback tier.

    Returns ``{"sfn", "pids", "pid_source", "projects", "pid_hits",
    "name_hits"}`` — ``pid_hits`` are high-confidence, ``name_hits`` are
    candidates (each row carries ``slm_delta``).
    """
    sfn = str(sfn).strip()
    project_rows = list(project_rows or [])
    pid_source = "injected"
    if pids is None:
        if not project_rows:
            db_rows = query_projects_by_sfn(sfn)
            if db_rows is not None:
                project_rows, pid_source = db_rows, "project_db"
        if project_rows:
            pids = [r["pid"] for r in project_rows]
        else:
            pids, pid_source = sfn_to_pids(sfn), "tims"
    pids = list(dict.fromkeys(str(p) for p in pids))
    pid_hits = []
    for pid in pids:
        pid_hits.extend(find_plans_by_pid(pid, inventory))
    name_hits = []
    if bridge_name:
        m = BRIDGE_NAME_GRAMMAR.match(bridge_name.strip())
        if m:
            seen = {id(r) for r in pid_hits}
            name_hits = [r for r in find_plans_by_bridge_key(
                m["county"], m["route"], parse_slm(m["slm"]), inventory, tol)
                if id(r) not in seen]
    return {"sfn": sfn, "pids": pids, "pid_source": pid_source,
            "projects": project_rows,
            "pid_hits": pid_hits, "name_hits": name_hits}


# --- Live ProjectWise (Windows + logged-in PW Explorer) ----------------------

def _pw():
    from civilpy.general.bentley import projectwise
    return projectwise


def get_structures_sheets(pid, district, county, sfn=None,
                          datasource=DATASOURCE_ACTIVE):
    """Sheets in an active project's Structures folder (live pw-02 query).

    Resolves ``01 Active Projects/District {dd}/{county}/{pid}/
    400-Engineering/Structures`` by name path, then lists documents in it and
    its ``SFN_*`` subfolders (filtered to one bridge when ``sfn`` is given).
    Each returned dict carries ``folder``, calibrated document properties,
    and parsed ``pid``/``sfn``/``sheet`` where the filename grammar applies.
    """
    pw = _pw()
    path = ACTIVE_STRUCTURES_PATH.format(
        district=str(district).zfill(2), county=county, pid=pid)
    out = []
    with pw.PW_SESSION(datasource):
        pw.extend_prototypes()
        root = pw.resolve_path(path)
        if not root:
            raise LookupError(f"could not resolve {path!r} on {datasource}")
        targets = [(root, "Structures")]
        for name, fid in pw.list_children(root):
            if sfn and name and name.upper() != f"SFN_{sfn}".upper():
                continue
            targets.append((fid, name))
        for fid, label in targets:
            for doc in pw.list_documents(fid):
                m = ACTIVE_SHEET_GRAMMAR.search(doc.get("filename") or "")
                doc.update(folder=label,
                           pid=m and m["pid"], sfn=m and m["sfn"],
                           sheet=m and m["sheet"])
                out.append(doc)
    return out


def pull_plan(folder_id, doc_id, dest_dir, datasource=DATASOURCE_ARCHIVE):
    """Copy one plan document out of ProjectWise to ``dest_dir``.

    Works for PlanVault rows (default) and active-project sheets
    (``datasource=DATASOURCE_ACTIVE``).  Returns the written filename.
    """
    pw = _pw()
    with pw.PW_SESSION(datasource):
        pw.extend_prototypes()
        return pw.copy_out(int(folder_id), int(doc_id), dest_dir)
