#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Build and analyze an ODOT standard bridge in Midas Civil NX.

The whole workflow as a handful of calls, meant to read like a checklist in
a notebook (and to be callable from Rhino/Grasshopper, which is why nothing
here needs a UI or an interactive prompt)::

    from civilpy.state.ohio.dot import (
        connect, new_model, add_girder, midas_ohio_legal_loads,
        generate_lane_load, add_moving_load_case, set_moving_load_control,
        analyze, moving_load_envelopes,
    )

    midas = connect()
    new_model(midas)
    girder = add_girder(midas, "CB27-48", span_ft=70, n_beams=9)
    midas_ohio_legal_loads(midas)
    lanes = generate_lane_load(midas, girder)
    add_moving_load_case(midas, lanes)
    set_moving_load_control(midas)
    analyze(midas)
    env = moving_load_envelopes(midas)

Why this module exists
----------------------

Every ``/db/*`` body below is transcribed from an authoritative source --
the Civil NX API manual, or a record read back off a live model -- and the
source is named in the code. That is deliberate. Composing these bodies
from memory produces ``{"error": {"message": "Wrong Field"}}``, which names
neither the offending field nor the reason, and which is easy to
misdiagnose as an API restriction. Some real examples that cost hours:

* ``MVLD.DEFAULT.COMB_OPTION`` is the **string** ``"INDEPENDENT"``, not
  an integer code; the lane counts are ``MIN_LOADED_LANE`` /
  ``MAX_LOADED_LANE``, not ``MIN_NUM`` / ``MAX_NUM``.
* ``LLAN`` carries the lane name at ``COMMON.LL_NAME`` -- not a top-level
  ``LANE_NAME`` -- its ``LOAD_DIST`` is ``"LANE"``, and its items are
  ``ELEM/ECC/FACT/SPAN_START/ECCEN_VERT_LOAD/CENT_F``.
* A standard-DB vehicle name that does not resolve stores **cleanly** and
  then applies **zero load**, silently. :func:`midas_ohio_legal_loads`
  therefore defaults to explicit axle trains, and
  :func:`check_nonzero_envelopes` exists to catch the failure if you opt
  into the DB entries.

If you need a table this module does not cover, read the manual page
first: search ``support.midasuser.com/api/v2/help_center/articles/
search.json?query=<title>``, then fetch
``/api/v2/help_center/ko/articles/<id>.json``. Known ids are listed in
:data:`API_MANUAL_ARTICLES`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "API_MANUAL_ARTICLES",
    "GirderModel",
    "add_girder",
    "add_moving_load_case",
    "analyze",
    "check_nonzero_envelopes",
    "connect",
    "ensure_base_stage",
    "generate_lane_load",
    "midas_ohio_legal_loads",
    "moving_load_envelopes",
    "new_model",
    "set_moving_load_control",
]

#: Civil NX API manual article ids on the MIDAS support site, for the
#: endpoints this module writes.  Fetch with
#: ``/api/v2/help_center/ko/articles/<id>.json``.
API_MANUAL_ARTICLES = {
    "MVLD": 35959068573209,   # moving load cases
    "MVCT": 35989483364633,   # moving load analysis control
    "STCT": 35990281053465,   # construction stage analysis control
    "MVHL": 35957229130521,   # vehicles (AASHTO LRFD / legal / state DB)
}

#: AASHTO LRFD multiple-presence factors, 1..6 loaded lanes
#: (LRFD Table 3.6.1.1.2-1).  Midas expects the whole set on every
#: moving load case.
MULTIPLE_PRESENCE = [1.2, 1.0, 0.85, 0.65, 0.65, 0.65]


@dataclass
class GirderModel:
    """What :func:`add_girder` built, and what the later calls need.

    ``elements_by_line`` maps girder line index (0-based, left to right) to
    the element ids forming that line -- :func:`generate_lane_load` puts one
    traffic lane on each.
    """

    designation: str
    family: str                       # "box" | "ps-i" | "steel"
    span_ft: float
    n_beams: int
    hub: Any = None                   # the StructuralModel
    elements_by_line: dict[int, list[int]] = field(default_factory=dict)
    report: dict = field(default_factory=dict)

    @property
    def all_elements(self) -> list[int]:
        return [e for line in self.elements_by_line.values() for e in line]


# ── session ──────────────────────────────────────────────────────────────
def connect(**client_kwargs):
    """A :class:`~civilpy.structural.midas.MidasCivil` from ``~/secrets.json``.

    ``timeout`` defaults high: the app serializes API calls behind whatever
    the UI is doing, and a solve can block even a ping.
    """
    from civilpy.structural.midas import MidasCivil

    client_kwargs.setdefault("timeout", 300)
    client_kwargs.setdefault("reconnect_retries", 0)
    return MidasCivil(**client_kwargs)


def ensure_base_stage(client) -> bool:
    """Put the app where ``/db/*`` writes are legal, and say whether it moved.

    Civil NX refuses section, element and control writes while the UI is
    displaying a construction stage or post-processing results -- the error
    reads "... can be added/modified/deleted in Base Stage only", which is
    easy to mistake for a malformed body.  ``POST /view/CAPTURE`` with
    ``SET_MODE "pre"`` flips it back to preprocessing/base stage.

    .. warning::
       Flipping to preprocessing **drops analysis results**, exactly as any
       ``/db`` write does.  Re-analyze afterwards.
    """
    try:
        client.request("POST", "view/CAPTURE", {"Argument": {
            "SET_MODE": "pre", "HEIGHT": 100, "WIDTH": 100,
            "ANGLE": {"HORIZONTAL": 0, "VERTICAL": 0}}}, timeout=300)
        return True
    except Exception:
        return False


def new_model(client) -> None:
    """``POST /doc/new``.  The empty-``Argument`` body is required -- a null
    body returns HTTP 500."""
    client.request("POST", "/doc/new", {"Argument": {}})


# ── geometry ─────────────────────────────────────────────────────────────
def add_girder(client, designation: str, *, span_ft: float, n_beams: int,
               spacing_ft: float | None = None, push: bool = True,
               **kwargs) -> GirderModel:
    """Build an ODOT standard superstructure and send it to Midas.

    ``designation`` selects the family:

    ==========================  ==========================================
    ``"CB27-48"``, ``"B21-48"`` PSBD-1-25 adjacent box beam
    ``"WF36-49"``, ``"AASHTO
    Type 4"``                   PSID-1-13 prestressed I-beam
    ``"W36X150"``               steel plate/rolled girder (BridgeInput)
    ==========================  ==========================================

    Extra keyword arguments pass through to the underlying hub builder
    (``barrier_klf``, ``fws_klf``, ``deck_t_in``, ``grade``, ``skew_deg``,
    ...).  With ``push=False`` the hub is built but nothing is sent, which
    is how the notebook shows the model before committing to it.
    """
    from civilpy.structural.midas_models import push_midas

    fam = _family(designation)
    if fam == "box":
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)
        hub = structural_model_from_box(designation, span_ft, n_beams,
                                        **kwargs)
    elif fam == "ps-i":
        from civilpy.structural.ps_i_beam_pipeline import (
            structural_model_from_ps_i)
        if spacing_ft is None:
            raise ValueError("spacing_ft is required for a PS I-beam bridge")
        hub = structural_model_from_ps_i(designation, span_ft, n_beams,
                                         spacing_ft=spacing_ft, **kwargs)
    else:
        from civilpy.structural.bridge_layout import (
            BridgeInput, layout_bridge, structural_model_from_layout)
        if spacing_ft is None:
            raise ValueError("spacing_ft is required for a steel girder bridge")
        inp = BridgeInput(spans_ft=(float(span_ft),), girder_count=n_beams,
                          girder_spacing_ft=spacing_ft,
                          girder_label=designation,
                          overhang_ft=kwargs.pop("overhang_ft", 3.0),
                          **kwargs)
        hub = structural_model_from_layout(layout_bridge(inp))

    model = GirderModel(designation=designation, family=fam,
                        span_ft=float(span_ft), n_beams=int(n_beams), hub=hub,
                        elements_by_line=_element_lines(hub, n_beams))
    if push:
        model.report = push_midas(hub, client)
    return model


def _family(designation: str) -> str:
    import re

    if re.match(r"^C?B\d+-\d+$", designation):
        return "box"
    if re.match(r"^W\d+X\d+$", designation, re.I):
        return "steel"
    return "ps-i"


def _element_lines(hub, n_beams: int) -> dict[int, list[int]]:
    """Girder-line index -> 1-based Midas element ids.

    ``midas_payloads`` numbers elements by insertion order, so the hub's own
    ordering is the mapping.  Girder elements carry ``gdr.line`` metadata
    where the builder sets it; otherwise the elements are split evenly.
    """
    girders = [e for e in getattr(hub, "elements", {}).values()
               if getattr(e, "role", None) == "girder"]
    order = {id(e): i + 1 for i, e in
             enumerate(getattr(hub, "elements", {}).values())}
    lines: dict[int, list[int]] = {}
    for e in girders:
        line = e.metadata.get("gdr.line") if hasattr(e, "metadata") else None
        idx = int(line) - 1 if line is not None else None
        lines.setdefault(idx if idx is not None else 0, []).append(order[id(e)])
    if len(lines) == 1 and n_beams > 1 and lines.get(0):
        # no per-line metadata -- split the chain evenly
        chain = lines.pop(0)
        per = max(1, len(chain) // n_beams)
        lines = {i: chain[i * per:(i + 1) * per] for i in range(n_beams)}
    return {k: sorted(v) for k, v in sorted(lines.items()) if v}


# ── rating vehicles ──────────────────────────────────────────────────────
def midas_ohio_legal_loads(client, *, im_percent: float = 33.0,
                           include_design: bool = True,
                           use_standard_db: bool = False,
                           replace: bool = True) -> dict:
    """Load every vehicle ODOT BDM Section 908 specifies, and nothing else.

    Ten commercial legal vehicles and two emergency vehicles (908.3), the
    two state permit loads (908.3.3), and -- with ``include_design`` -- the
    HL-93 / HS20 inventory-and-operating loads of 908.2.  The AASHTO
    National Rating Load, the H15/H20/HS15/HS25/AML set and Ohio 4F1 are
    excluded: Midas offers them, the BDM does not ask for them.

    BDM 924.4 rules that can live on a vehicle record are applied for you --
    lane loads and the permit loads get IM = 0 (924.4.C and .E), everything
    else ``im_percent`` (924.4.A). The rest of 924.4 is bridge-specific:
    15% for fatigue (B), no IM on wood (D), and the buried reduction (F).

    ``use_standard_db=False`` (the default) writes explicit axle trains
    checked against BDM Figures 908.3-1..-5. The DB entries have been
    verified to reproduce those axle trains exactly (0.00% on midspan
    moment), so ``use_standard_db=True`` is safe and has one advantage:
    Midas discards ``DYN_LOAD_ALLOWANCE`` on user-defined records, so only
    the DB route carries IM on the vehicle itself.
    """
    from civilpy.structural.midas_models import load_oh_vehicles

    return load_oh_vehicles(client, im_percent=im_percent,
                            include_design=include_design,
                            use_standard_db=use_standard_db,
                            replace=replace)


# ── traffic lanes ────────────────────────────────────────────────────────
def generate_lane_load(client, girder: GirderModel | None = None, *,
                       elements: dict[int, list[int]] | None = None,
                       width_ft: float = 10.0,
                       wheel_spacing_ft: float = 6.0,
                       moving: str = "BOTH",
                       replace: bool = True) -> list[str]:
    """One traffic line lane per girder line.  Returns the lane names.

    Schema from a UI-created record: the name is ``COMMON.LL_NAME``,
    ``LOAD_DIST`` is ``"LANE"``, and each item is
    ``ELEM/ECC/FACT/SPAN_START/ECCEN_VERT_LOAD/CENT_F``.  ``CENT_F`` must be
    strictly inside (0, 1) -- 0.0 is rejected.

    Lanes ride the girder lines, which is the line-girder idealization: it
    exercises each girder directly but never places a wheel *between*
    girders, so transverse distribution is not tested. Use the grillage
    model and a transverse lane layout when that matters.
    """
    lines = elements or (girder.elements_by_line if girder else None)
    if not lines:
        raise ValueError("no girder elements -- pass a GirderModel or elements")

    if replace:
        for lid in sorted(client.request("GET", "db/llan").get("LLAN", {}),
                          key=int, reverse=True):
            client.request("DELETE", f"db/llan/{lid}")

    assign, names = {}, []
    for i, (_, elems) in enumerate(sorted(lines.items()), start=1):
        name = f"Lane{i}"
        names.append(name)
        assign[str(i)] = {
            "COMMON": {
                "LL_NAME": name,
                "LOAD_DIST": "LANE",
                "GROUP_NAME": "",
                "SKEW_START": 0, "SKEW_END": 0,
                "MOVING": moving,
                "WHEEL_SPACE": wheel_spacing_ft * 12.0,
                "WIDTH": width_ft * 12.0,
                "OPT_AUTO_LANE": False,
                "ALLOW_WIDTH": width_ft * 12.0,
            },
            "LANE_ITEMS": [
                {"ELEM": int(e), "ECC": 0, "FACT": 0, "SPAN_START": False,
                 "ECCEN_VERT_LOAD": 0, "CENT_F": 0.5}
                for e in elems
            ],
        }
    client.request("PUT", "db/llan", {"Assign": assign})
    return names


# ── moving load cases ────────────────────────────────────────────────────
def add_moving_load_case(client, lanes: list[str] | str, *,
                         vehicles: list[str] | None = None,
                         scale_factors: list[float] | None = None,
                         comb_option: str = "INDEPENDENT",
                         max_loaded_lanes: int | None = None,
                         replace: bool = True) -> dict[str, str]:
    """One moving load case per vehicle.  Returns ``{case name: vehicle}``.

    ``vehicles`` defaults to every vehicle currently in the model, so the
    usual sequence is :func:`midas_ohio_legal_loads` then this.

    Body per the db/MVLD manual (:data:`API_MANUAL_ARTICLES`):
    ``COMB_OPTION`` is the STRING ``"INDEPENDENT"`` (or ``"COMBINED"``),
    and the lane counts are ``MIN_LOADED_LANE`` / ``MAX_LOADED_LANE``.
    ``SCALE_FACTORS`` carries the multiple-presence set, which Midas wants
    in full on every case.
    """
    if isinstance(lanes, str):
        lanes = [lanes]
    if vehicles is None:
        stored = client.request("GET", "db/mvhl").get("MVHL", {})
        vehicles = [v.get("VEHICLE_LOAD_NAME")
                    for _, v in sorted(stored.items(), key=lambda kv: int(kv[0]))]
    if not vehicles:
        raise ValueError("no vehicles in the model -- run "
                         "midas_ohio_legal_loads() first")

    if replace:
        for cid in sorted(client.request("GET", "db/mvld").get("MVLD", {}),
                          key=int, reverse=True):
            client.request("DELETE", f"db/mvld/{cid}")

    assign, cases = {}, {}
    for i, veh in enumerate(vehicles, start=1):
        assign[str(i)] = {
            "LCNAME": veh, "DESC": "", "TYPE": 0,
            "DEFAULT": {
                "SCALE_FACTORS": list(scale_factors or MULTIPLE_PRESENCE),
                "COMB_OPTION": comb_option,
                "LANE_FACTOR_TYPE": 1,
                "SUB_LOAD_DATAS": [{
                    "VEHICLE_TYPE": "VL",
                    "VEHICLE_NAME": veh,
                    "SCALE_FACTOR": 1,
                    "MIN_LOADED_LANE": 1,
                    "MAX_LOADED_LANE": int(max_loaded_lanes or len(lanes)),
                    "LANE_NAMES": list(lanes),
                }],
            },
        }
        cases[veh] = veh
    client.request("PUT", "db/mvld", {"Assign": assign})
    return cases


def set_moving_load_control(client, *, concurrent_forces: bool = True,
                            group_name: str | None = None) -> None:
    """The Moving Load Analysis Control record (``db/MVCT``).

    Without it the influence-line solve returns all-zero envelopes. Schema
    per the manual and a UI-created record: ``METHOD`` ``"EXACT"``,
    ``POINT`` ``"INF"``, ``FRAME`` ``"AXIAL"``, ``PLATE`` ``"NODAL"``.
    """
    body = {
        "METHOD": "EXACT", "POINT": "INF", "iIGP": 0, "iIGPN": 3,
        "PLATE": "NODAL", "FRAME": "AXIAL",
        "bSTRCALC": True, "bCSTRCALC": True,
        "bCONCURRENT": bool(concurrent_forces),
        "bCONCLINK": bool(concurrent_forces),
        "bREAC": True, "bRG": False, "RGN": group_name or "",
        "bDISP": True, "bDG": False, "DGN": "",
        "bFM": True, "bFG": False, "FGN": "",
        "bL": True, "bLG": False, "LGN": "",
    }
    client.request("PUT", "db/MVCT", {"Assign": {"1": body}})


# ── run and read ─────────────────────────────────────────────────────────
def analyze(client) -> dict:
    """``POST /doc/ANAL``.  Long timeout: the app queues behind the UI and
    even a small model can exceed 60 s."""
    return client.request("POST", "/doc/ANAL", {"Argument": {}},
                          timeout=getattr(client, "ANALYSIS_TIMEOUT", 600))


def moving_load_envelopes(client, *, elements: list[int] | None = None,
                          component: str = "Moment-y") -> dict[str, float]:
    """``{load case: max |component|}`` from the beam-force table.

    Pulled in one request with no load-case filter and grouped by the
    table's own Load column -- Midas decorates moving-load case names
    (``"SU5(MV:all)"``), so matching a guessed suffix is fragile.
    """
    from civilpy.structural.midas import parse_result_table

    kw: dict[str, Any] = {"components": ["Elem", "Load", component]}
    if elements:
        kw["node_elems"] = {"KEYS": list(elements)}
    resp = client.result_table("BeamForce", table_type="BEAMFORCE", **kw)

    out: dict[str, float] = {}
    for row in parse_result_table(resp):
        load = next((str(v) for k, v in row.items()
                     if str(k).strip().lower() == "load"), None)
        if not load:
            continue
        case = load.split("(")[0].strip()
        for k, v in row.items():
            if component in str(k):
                try:
                    m = abs(float(v))
                except (TypeError, ValueError):
                    continue
                out[case] = max(out.get(case, 0.0), m)
    return out


def check_nonzero_envelopes(envelopes: dict[str, float],
                            expected: list[str] | None = None) -> list[str]:
    """Names that produced no load effect -- the silent-failure check.

    A standard-DB vehicle whose name does not resolve stores cleanly and
    applies **zero load** with no error anywhere. Run this after the first
    analysis; anything returned here contributed nothing.
    """
    names = expected if expected is not None else list(envelopes)
    return [n for n in names if not envelopes.get(n)]
