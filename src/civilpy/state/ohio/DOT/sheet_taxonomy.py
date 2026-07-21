# -*- coding: utf-8 -*-
#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT CADD plan-sheet taxonomy — L&D Manual Vol. 3 §1204.3.4 (Jan 2026).

The complete File Name Type Codes tables and file-naming formats, transcribed
from the public manual, plus :func:`classify_filename` to parse any
convention-following design file name into its parts.  This is what powers
the sheet accessors on :class:`~civilpy.state.ohio.DOT.pw_project
.ProjectWiseProject` (``project.alignments``, ``sfn.site_plans``, ...).

Naming formats::

    123456_GP005.dgn                standard    PID_code+number
    123456_SFN1234567_SD002.dgn     structure   PID_SFN/CFN+7digit_code+number
    123456_WALL001_WP005.dgn        wall        PID_WALLnnn_code+number

Observed on-box deviation (2026-07-21): structure files may separate the SFN
with an underscore (``116581_SFN_2510774_SI001.dgn``) — the structure regex
tolerates both forms.  Note ``SI`` is **Piers** in the Bridge Sheets table;
Site Plan is ``SP``.
"""
from __future__ import annotations

import re

#: filename formats, tried in order (most specific first)
FILENAME_FORMATS = {
    "structure": re.compile(
        r"^(?P<pid>\d{5,6})_(?P<kind>SFN|CFN)_?(?P<sfn>\d{7})"
        r"_(?P<code>[A-Z]{2})(?P<num>\d{3})\.(?P<ext>\w+)$", re.IGNORECASE),
    "wall": re.compile(
        r"^(?P<pid>\d{5,6})_WALL(?P<wall>\d{3})"
        r"_(?P<code>[A-Z]{2})(?P<num>\d{3})\.(?P<ext>\w+)$", re.IGNORECASE),
    "standard": re.compile(
        r"^(?P<pid>\d{5,6})_(?P<code>[A-Z]{2})(?P<num>\d{3})"
        r"\.(?P<ext>\w+)$", re.IGNORECASE),
}

#: File Name Type Codes tables (L&D Vol. 3 §1204.3.4.3), keyed by table.
#: ``scope`` says what a file of this code describes: the whole *project*,
#: one *structure* (SFN/CFN filename format), or one *wall*.
CODE_TABLES = {
    "basemap_design_files": {"scope": "project", "codes": {
        "KL": "3D Line Strings (Combined Final)", "KB": "3D Model",
        "KM": "3D Modeling", "BC": "Aerial and Ground Combined",
        "BA": "Aerial Mapping", "BS": "Bridge", "KD": "Digital Terrain Model",
        "BD": "Drainage", "FD": "Field Digital Terrain Model", "BK": "Geometry",
        "VK": "Geometry (Survey)", "BI": "Geotechnical", "BL": "Landscaping",
        "BH": "Lighting", "BM": "MOT", "PC": "Point Cloud",
        "BR": "Right-of-Way", "BP": "Roadway", "BG": "Signals",
        "KS": "Superelevation", "FB": "Survey Field Book",
        "BT": "Traffic Control", "BU": "Utilities", "BW": "Wall"}},
    "bridge_sheets": {"scope": "structure", "codes": {
        "SB": "Bearing", "SD": "Deck Plan", "SQ": "Estimated Quantities",
        "SX": "Expansion Device Details", "SF": "Forward Abutment",
        "SO": "Foundation Plan", "SN": "General Notes", "SG": "General Plan",
        "SM": "Miscellaneous Details", "SI": "Piers", "SA": "Railing",
        "SR": "Rear Abutment", "SL": "Reinforcing Steel List", "SV": "Removal",
        "SH": "Sheeting", "SP": "Site Plan",
        "SC": "Staged Construction Details", "SS": "Superstructure Details",
        "ST": "Transverse Section"}},
    "drainage_sheets": {"scope": "project", "codes": {
        "XD": "Channel Cross Sections", "DC": "Culvert Details",
        "DD": "Details", "DE": "Erosion Control", "DM": "Miscellaneous Details",
        "DN": "Notes", "DP": "Plan and Profile or Plan", "DF": "Profile",
        "DQ": "Quantity Table", "DB": "Schematic Plan", "DS": "Sub-Summary"}},
    "geotechnical_sheets": {"scope": "project", "codes": {
        "YL": "Geohazard Boring Logs", "YC": "Geohazard Cover",
        "YX": "Geohazard Cross Sections", "YD": "Geohazard Lab Data",
        "YP": "Geohazard Plan and Profile", "YF": "Geohazard Profile",
        "IC": "Geotechnical Profile Cover",
        "IX": "Geotechnical Profile Cross Sections",
        "ID": "Geotechnical Profile Lab Data",
        "IP": "Geotechnical Profile, Plan and Profile or Plan",
        "IF": "Geotechnical Profile, Profile Only",
        "ZL": "Structure Foundation Exploration Boring Logs",
        "ZC": "Structure Foundation Exploration Cover",
        "ZD": "Structure Foundation Exploration Lab Data",
        "ZP": "Structure Foundation Exploration Plan and Profile",
        "ZF": "Structure Foundation Exploration Profile"}},
    "landscaping_sheets": {"scope": "project", "codes": {
        "PD": "Details", "PM": "Miscellaneous Details", "PN": "Notes",
        "PP": "Plan", "PB": "Schematic Plan", "PS": "Sub-Summary"}},
    "lighting_sheets": {"scope": "project", "codes": {
        "LC": "Circuit Diagrams", "LD": "Details", "LE": "Elevation Views",
        "LG": "General Summary", "LM": "Miscellaneous", "LN": "Notes",
        "LP": "Plan", "LQ": "Quantity Table", "LB": "Schematic Plan",
        "LS": "Sub-Summary"}},
    "mot_sheets": {"scope": "project", "codes": {
        "XM": "Cross Sections", "MD": "Detour Plan", "MM": "Miscellaneous",
        "MN": "Notes", "MP": "Phase Plan and Profile or Plan",
        "MH": "Phase Details", "MF": "Profile", "MQ": "Quantity Table",
        "MB": "Schematic Plan", "MS": "Sub-Summary", "MY": "Typical Sections"}},
    "right_of_way_sheets": {"scope": "project", "codes": {
        "RC": "Centerline Plat", "RL": "Legend", "RM": "Property Map",
        "RR": "Railroad Plat", "RB": "RW Boundary", "RD": "RW Detail",
        "RT": "RW Topo", "RS": "Summary of Additional RW"}},
    "roadway_sheets": {"scope": "project", "codes": {
        "GC": "Calculations/Computations", "XS": "Cross Sections",
        "GD": "Drive Details", "GX": "Fencing Plan", "GN": "General Notes",
        "GG": "General Summary", "XG": "Grading Plan",
        "GR": "Guardrail/Barrier Details",
        "GI": "Intersection/Interchange Details", "GJ": "Maintenance Data",
        "GM": "Miscellaneous", "GA": "Pavement Details",
        "GP": "Plan and Profile or Plan", "GF": "Profile",
        "GQ": "Quantity Table", "GB": "Schematic Plan", "GS": "Sub-Summary",
        "GE": "Superelevation Table", "GT": "Title Sheet",
        "GU": "Signature Sheet", "GY": "Typical Sections"}},
    "signal_sheets": {"scope": "project", "codes": {
        "CD": "Details", "CG": "General Summary", "CM": "Miscellaneous",
        "CN": "Notes", "CP": "Plan", "CQ": "Quantity Table",
        "CS": "Sub-Summary"}},
    "traffic_control_sheets": {"scope": "project", "codes": {
        "TC": "Calculations/Computations", "TD": "Details",
        "TE": "Elevation Views", "TN": "General Notes", "TG": "General Summary",
        "TM": "Miscellaneous", "TP": "Plan", "TQ": "Quantity Table",
        "TB": "Schematic Plan", "TS": "Sub-Summary"}},
    "utility_sheets": {"scope": "project", "codes": {
        "UC": "Calculations/Computations", "UD": "Details",
        "UE": "Elevation Views", "UG": "General Summary", "UM": "Miscellaneous",
        "UN": "Notes", "UP": "Plan and Profile or Plan", "UF": "Profile",
        "UQ": "Quantity Table", "UB": "Schematic Plan", "US": "Sub-Summary"}},
    "wall_sheets": {"scope": "wall", "codes": {
        "WC": "Calculations/Computations", "WX": "Cross Sections",
        "WD": "Details", "WE": "Elevation", "WQ": "Estimated Quantities",
        "WT": "Foundation", "WM": "Miscellaneous", "WN": "Notes",
        "WP": "Plan and Profile or Plan", "WF": "Profile",
        "WB": "Schematic Plan", "WH": "Sheeting", "WL": "Steel List",
        "WS": "Sub-Summary", "WY": "Typical Section"}},
}

#: Friendly accessor names -> {"scope", "codes"}.  These become attributes on
#: ProjectWiseProject (project/wall scope) and ProjectWiseSFN (structure
#: scope): ``project.alignments``, ``project.terrain_models``,
#: ``sfn.site_plans``, ``sfn.details``, ...
SHEET_ACCESSORS = {
    # project scope — basemaps & roadway
    "alignments": {"scope": "project", "codes": ["BK", "VK"]},
    "terrain_models": {"scope": "project", "codes": ["KD", "FD"]},
    "corridor_models": {"scope": "project", "codes": ["KM", "KB", "KL"]},
    "survey": {"scope": "project", "codes": ["FB", "VK", "PC"]},
    "aerial_mapping": {"scope": "project", "codes": ["BA", "BC"]},
    "bridge_basemaps": {"scope": "project", "codes": ["BS"]},
    "roadway_basemaps": {"scope": "project", "codes": ["BP"]},
    "drainage_basemaps": {"scope": "project", "codes": ["BD"]},
    "geotech_basemaps": {"scope": "project", "codes": ["BI"]},
    "row_basemaps": {"scope": "project", "codes": ["BR"]},
    "superelevation": {"scope": "project", "codes": ["KS", "GE"]},
    "title_sheet": {"scope": "project", "codes": ["GT"]},
    "signature_sheet": {"scope": "project", "codes": ["GU"]},
    "typical_sections": {"scope": "project", "codes": ["GY"]},
    "cross_sections": {"scope": "project", "codes": ["XS"]},
    "grading_plans": {"scope": "project", "codes": ["XG"]},
    "plan_profiles": {"scope": "project", "codes": ["GP", "GF"]},
    "guardrail_details": {"scope": "project", "codes": ["GR"]},
    "mot": {"scope": "project", "codes": ["MB", "MD", "MP", "MH", "MF", "MN",
                                          "MM", "MQ", "MS", "MY", "XM"]},
    "foundation_exploration": {"scope": "project",
                               "codes": ["ZL", "ZC", "ZD", "ZP", "ZF"]},
    "geohazard": {"scope": "project",
                  "codes": ["YL", "YC", "YX", "YD", "YP", "YF"]},
    "geotech_profiles": {"scope": "project",
                         "codes": ["IC", "IX", "ID", "IP", "IF"]},
    "culvert_details": {"scope": "project", "codes": ["DC"]},
    "erosion_control": {"scope": "project", "codes": ["DE"]},
    # structure scope — the bridge sheet set
    "site_plans": {"scope": "structure", "codes": ["SP"]},
    "general_plan": {"scope": "structure", "codes": ["SG"]},
    "general_notes": {"scope": "structure", "codes": ["SN"]},
    "foundation_plan": {"scope": "structure", "codes": ["SO"]},
    "piers": {"scope": "structure", "codes": ["SI"]},
    "forward_abutment": {"scope": "structure", "codes": ["SF"]},
    "rear_abutment": {"scope": "structure", "codes": ["SR"]},
    "abutments": {"scope": "structure", "codes": ["SF", "SR"]},
    "deck_plan": {"scope": "structure", "codes": ["SD"]},
    "superstructure_details": {"scope": "structure", "codes": ["SS"]},
    "transverse_sections": {"scope": "structure", "codes": ["ST"]},
    "bearings": {"scope": "structure", "codes": ["SB"]},
    "expansion_devices": {"scope": "structure", "codes": ["SX"]},
    "railing": {"scope": "structure", "codes": ["SA"]},
    "reinforcing_steel": {"scope": "structure", "codes": ["SL"]},
    "estimated_quantities": {"scope": "structure", "codes": ["SQ"]},
    "staged_construction": {"scope": "structure", "codes": ["SC"]},
    "removal": {"scope": "structure", "codes": ["SV"]},
    "temporary_sheeting": {"scope": "structure", "codes": ["SH"]},
    "details": {"scope": "structure", "codes": ["SM", "SS", "SX", "SC"]},
    # wall scope
    "wall_plans": {"scope": "wall", "codes": ["WP", "WB", "WF"]},
    "wall_details": {"scope": "wall", "codes": ["WD", "WM", "WE", "WX"]},
    "wall_foundation": {"scope": "wall", "codes": ["WT"]},
    "wall_quantities": {"scope": "wall", "codes": ["WQ"]},
}

#: code -> (table name, description), for lookups and labeling
CODE_INDEX = {code: (table, desc)
              for table, spec in CODE_TABLES.items()
              for code, desc in spec["codes"].items()}


def classify_filename(filename):
    """Parse a design-file name against the L&D naming formats.

    Returns ``None`` for non-conforming names, else a dict with ``format``
    (structure/wall/standard), ``pid``, ``code``, ``num``, ``ext``,
    ``description`` (from the code tables, when the code is known), plus
    ``sfn``/``kind`` for structure files and ``wall`` for wall files.
    """
    name = (filename or "").strip()
    for fmt, pattern in FILENAME_FORMATS.items():
        m = pattern.match(name)
        if m:
            info = {"format": fmt, **m.groupdict()}
            info["code"] = info["code"].upper()
            table_desc = CODE_INDEX.get(info["code"])
            info["table"], info["description"] = table_desc or (None, None)
            return info
    return None
