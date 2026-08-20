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
    "DEFAULT_MODEL_PATH",
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
    "save_model",
    "set_moving_load_code",
    "set_moving_load_control",
]

#: Civil NX API manual article ids on the MIDAS support site, for the
#: endpoints this module writes.  Fetch with
#: ``/api/v2/help_center/ko/articles/<id>.json``.
API_MANUAL_ARTICLES = {
    "MVLD": 35959068573209,   # moving load cases
    "MVCT": 35989483364633,   # moving load analysis control
    "MVCD": 35955076795929,   # moving load code (prerequisite for MVHL)
    "STCT": 35990281053465,   # construction stage analysis control
    "MVHL": 35957229130521,   # vehicles (AASHTO LRFD / legal / state DB)
    "SECT_PSC_VALUE": 39233604772633,     # PSC value (polygon) sections
    "SECT_COMPOSITE_PSC": 35938998724377,  # composite PSC (CI/CT only)
}

#: AASHTO LRFD multiple-presence factors, 1..6 loaded lanes
#: (LRFD Table 3.6.1.1.2-1).  Midas expects the whole set on every
#: moving load case.
MULTIPLE_PRESENCE = [1.2, 1.0, 0.85, 0.65, 0.65, 0.65]

#: Where :func:`new_model` parks a scratch model so the solver never has to
#: ask.  Any writable path on the Civil NX machine will do.
DEFAULT_MODEL_PATH = r"C:\Temp\civilpy_model.mcb"


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
    deck_width_ft: float = 0.0        # out-to-out, for the design lane count
    #: dummy lane-line elements by lane index, the traffic lanes ride these
    lane_elements: dict[int, list[int]] = field(default_factory=dict)
    lane_offsets_ft: list[float] = field(default_factory=list)

    @property
    def all_elements(self) -> list[int]:
        return [e for line in self.elements_by_line.values() for e in line]

    @property
    def design_lanes(self) -> int:
        """Number of design lanes, LRFD 3.6.1.1.1: ``INT(clear / 12 ft)``.

        Taken from the lane lines the builder laid down when it has them,
        so it is the same number in the model and in the load case.
        """
        if self.lane_elements:
            return len(self.lane_elements)
        return max(1, int(self.deck_width_ft // 12.0)) if self.deck_width_ft \
            else 0


# ── session ──────────────────────────────────────────────────────────────
def connect(**client_kwargs):
    """A :class:`~civilpy.structural.midas.MidasCivil` from ``~/secrets.json``.

    ``timeout`` defaults high: the app serializes API calls behind whatever
    the UI is doing, and a solve can block even a ping.
    ``analysis_timeout`` is a **separate** budget that only ``/doc/ANAL``
    uses -- raising ``timeout`` alone leaves it at the 600 s class default,
    which a grillage of any size will blow straight through.
    """
    from civilpy.structural.midas import MidasCivil

    client_kwargs.setdefault("timeout", 300)
    client_kwargs.setdefault("analysis_timeout", 1800)
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


def new_model(client, *, path: str | None = DEFAULT_MODEL_PATH) -> None:
    """Save whatever is open, start a new model, and name it.

    The empty-``Argument`` body on ``/doc/new`` is required -- a null body
    returns HTTP 500.  The two saves are not decoration; **both** of the
    surrounding commands raise a modal dialog otherwise, and because the
    API is serialized behind the UI, either one silently blocks every
    later request until somebody clicks it:

    * ``/doc/new`` on a model with unsaved changes asks *"save changes?"*
    * ``/doc/ANAL`` on a model that has never been written to disk asks
      *Save As* (see :func:`analyze`)

    Neither is visible from the API. The request simply never returns, and
    a bare ``GET /db/UNIT`` hangs alongside it, so it reads as an
    impossibly slow solve rather than a prompt.

    ``path`` is a location on the **Civil NX machine**.  Saving to it first
    only clears the dirty flag -- the file is immediately overwritten by
    the new model -- so point it at scratch, not at work you care about.
    ``path=None`` skips both saves and takes the dialogs on yourself.
    """
    if path:
        # clear the dirty flag so /doc/new has nothing to ask about
        try:
            save_model(client, path=path)
        except Exception:
            pass                     # nothing open yet, or already clean
    client.request("POST", "/doc/new", {"Argument": {}})
    if path:
        save_model(client, path=path)


# ── geometry ─────────────────────────────────────────────────────────────
def add_girder(client, designation: str, *, span_ft: float,
               n_lanes: int | None = None, n_beams: int | None = None,
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

    **Say how much traffic, not how many beams.**  ``n_lanes`` sizes the
    deck -- lanes at ``lane_width_ft`` (12 ft, LRFD 3.6.1.1.1), plus
    ``shoulder_ft`` each side, plus the cataloged base width of the
    railing, rounded up to whole boxes -- and then works out where those
    lanes have to sit to produce the governing case.  ``n_beams`` is still
    accepted for a deck whose width is already fixed; give one or the
    other, not both.

    Extra keyword arguments pass through to the underlying hub builder.
    For a box-beam bridge that is
    :func:`~civilpy.structural.box_beam_pipeline.structural_model_from_box`,
    whose defaults already give you the whole ODOT superstructure:

    ``shear_keys=True``
        the grouted key between each pair of boxes, as its real
        cross-section, so it is visible in a non-hidden view;
    ``deck=None``
        the 5 in structural deck as composite plate elements, on
        automatically for a ``CB`` (composite) design and refused for a
        ``B`` (non-composite) one, which BDM 309.1.B surfaces with asphalt
        instead;
    ``barrier_klf``, ``fws_ksf``, ``asphalt_in``, ``deck_in``
        the dead loads -- see
        :func:`~civilpy.structural.box_beam_pipeline.box_beam_dead_loads`
        for which BDM article sets each default.

    With ``push=False`` the hub is built but nothing is sent, which is how
    the notebook shows the model before committing to it.
    """
    from civilpy.structural.midas_models import push_midas

    fam = _family(designation)
    if fam == "box":
        from civilpy.structural.box_beam_pipeline import (
            structural_model_from_box)
        hub = structural_model_from_box(designation, span_ft, n_beams,
                                        n_lanes=n_lanes, **kwargs)
        n_beams = len({e.metadata["gdr.line"] for e in hub.elements.values()
                       if getattr(e, "role", None) == "girder"})
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
                        elements_by_line=_element_lines(hub, n_beams),
                        deck_width_ft=_deck_width_ft(hub),
                        lane_elements=_lane_lines(hub),
                        lane_offsets_ft=list(
                            getattr(hub, "metadata", {}).get(
                                "lane.offsets_ft", [])))
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


def _lane_lines(hub) -> dict[int, list[int]]:
    """Lane index -> 1-based Midas element ids of that lane's dummy line."""
    order = {id(e): i + 1 for i, e in
             enumerate(getattr(hub, "elements", {}).values())}
    lines: dict[int, list[int]] = {}
    for e in getattr(hub, "elements", {}).values():
        if getattr(e, "role", None) != "lane-line":
            continue
        lines.setdefault(int(e.metadata["lane.index"]), []).append(order[id(e)])
    return {k: sorted(v) for k, v in sorted(lines.items())}


def _deck_width_ft(hub) -> float:
    """Out-to-out width of the hub, from its own node coordinates."""
    ys = [n.coords[1] for n in getattr(hub, "nodes", {}).values()]
    return (max(ys) - min(ys)) if ys else 0.0


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

    set_moving_load_code(client)
    return load_oh_vehicles(client, im_percent=im_percent,
                            include_design=include_design,
                            use_standard_db=use_standard_db,
                            replace=replace)


def set_moving_load_code(client, code: str = "AASHTO LRFD") -> None:
    """Select the moving load code (``db/MVCD``).

    **A new model has none**, and until one is set every write to
    ``db/mvhl`` is rejected with ``{"message": "Unknown Error"}`` -- which
    names neither the table at fault nor the missing prerequisite, and
    looks exactly like a malformed vehicle body.  Verified live
    2026-07-29: the identical payload that fails on a fresh ``/doc/new``
    model stores immediately once this record exists.

    Valid values come from the ``db/MVCD`` manual page and are literal UI
    strings -- ``"AASHTO LRFD"``, ``"AASHTO STANDARD"``,
    ``"AASHTO LRFD(PENDOT)"`` (sic), ``"CANADA"``, ``"EUROCODE"``, ...
    """
    client.request("PUT", "db/MVCD", {"Assign": {"1": {"CODE": code}}})


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

    Lanes ride the **dummy lane lines** :func:`add_girder` lays down on the
    design-lane centrelines (LRFD 3.6.1.1.1) -- weightless stringers at deck
    level, rigid-linked to the slab.  Falling back to the girder lines, as
    this did before, is wrong twice over: it puts every wheel directly over
    a beam, which no real lane does, and it offers as many "lanes" as there
    are beams -- six on a 24 ft deck that holds two.

    ``WIDTH`` and ``WHEEL_SPACE`` go out in the model's own length unit,
    read off ``/db/UNIT`` -- a lane 12x too wide stores without complaint.
    """
    from civilpy.structural.midas_models import model_length_unit

    lines = elements
    if lines is None and girder is not None:
        lines = girder.lane_elements or girder.elements_by_line
    if not lines:
        raise ValueError("no girder elements -- pass a GirderModel or elements")
    per_model_unit = {"in": 12.0, "ft": 1.0, "m": 0.3048,
                      "mm": 304.8, "cm": 30.48}.get(
        model_length_unit(client), 12.0)

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
                "WHEEL_SPACE": wheel_spacing_ft * per_model_unit,
                "WIDTH": width_ft * per_model_unit,
                "OPT_AUTO_LANE": False,
                "ALLOW_WIDTH": width_ft * per_model_unit,
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
                         girder: GirderModel | None = None,
                         vehicles: list[str] | None = None,
                         scale_factors: list[float] | None = None,
                         comb_option: str = "INDEPENDENT",
                         max_loaded_lanes: int | None = None,
                         replace: bool = True) -> dict[str, str]:
    """One moving load case per vehicle.  Returns ``{case name: vehicle}``.

    ``vehicles`` defaults to every vehicle currently in the model, so the
    usual sequence is :func:`midas_ohio_legal_loads` then this.

    ``max_loaded_lanes`` is how many of the lane *positions* may carry
    traffic at once.  Pass ``girder`` and it comes from LRFD 3.6.1.1.1 --
    ``INT(roadway width / 12 ft)``, so 2 on a six-beam adjacent box
    bridge, not 6.  Getting this wrong is expensive twice over: MIDAS
    enumerates every combination up to the limit (63 per vehicle at 6,
    21 at 2), and the extra ones put more trucks abreast than the deck
    can hold.  Without a girder it falls back to the number of lanes,
    which is only right when each lane really is a design lane.

    Body per the db/MVLD manual (:data:`API_MANUAL_ARTICLES`):
    ``COMB_OPTION`` is the STRING ``"INDEPENDENT"`` (or ``"COMBINED"``),
    and the lane counts are ``MIN_LOADED_LANE`` / ``MAX_LOADED_LANE``.
    ``SCALE_FACTORS`` carries the multiple-presence set, which Midas wants
    in full on every case.
    """
    if isinstance(lanes, str):
        lanes = [lanes]
    if max_loaded_lanes is None and girder is not None and girder.design_lanes:
        max_loaded_lanes = min(girder.design_lanes, len(lanes))
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
def analyze(client, *, save_as: str | None = None) -> dict:
    """Save the model, then ``POST /doc/ANAL``.

    **The save is not optional.** Analysing a model that has never been
    written to disk makes Civil NX raise a *Save As* dialog, and because
    the API is serialized behind the UI that dialog blocks every
    subsequent request -- the analysis appears to run for as long as
    anyone is willing to wait, and a plain ``GET /db/UNIT`` times out
    alongside it. Nothing in any response says a dialog is up.
    :func:`new_model` therefore names the file up front, and this saves
    again before every solve.

    .. note::
       **A read timeout here is not a failure.** Civil NX keeps solving
       after the HTTP request gives up -- an 11-girder grillage has come
       back complete, with results identical to a run that returned
       normally, after blowing a 600 s budget. Catch
       :class:`~civilpy.structural.midas.MidasTimeoutError`, reconnect and
       read the result table before deciding anything went wrong; retrying
       ``/doc/ANAL`` blind is what pops the modal *error* dialog that then
       blocks every later solve.

       What *is* a failure, and looks like success: a returned
       ``"command complete"`` with no results behind it. That means the
       solve aborted -- a rigid-link master/slave chain will do it -- and
       the next ``/doc/ANAL`` answers ``"Analysis is not allowed."``
    """
    save_model(client, path=save_as)
    return client.request("POST", "/doc/ANAL", {"Argument": {}},
                          timeout=getattr(client, "ANALYSIS_TIMEOUT", 600))


def save_model(client, path: str | None = None) -> dict:
    """``POST /doc/SAVE``, or ``/doc/SAVEAS`` when ``path`` is given.

    Call this before analysing anything -- see :func:`analyze` for what an
    unsaved model costs you.
    """
    if path:
        return client.request("POST", "/doc/SAVEAS", {"Argument": str(path)})
    return client.request("POST", "/doc/SAVE", {})


def moving_load_envelopes(client, *, elements: list[int] | None = None,
                          component: str = "Moment-y") -> dict[str, float]:
    """``{load case: max |component|}`` from the beam-force table.

    Pulled in one request with no load-case filter and grouped by the
    table's own Load column -- Midas decorates moving-load case names
    (``"SU5(MV:all)"``), so matching a guessed suffix is fragile.

    .. warning::
       These are **girder element** forces, not composite section forces.
       When :func:`add_girder` builds the deck as rigid-linked plates, the
       girder and the slab form a composite section whose total moment is
       the girder's own ``My`` **plus** the couple ``N * d`` from the axial
       force the composite action puts in each part, ``d`` being the
       distance between the girder centroid and the deck mid-surface.
       Reading ``Moment-y`` alone understates the section moment badly --
       by 40% on the CB27-48 example.  Measured live 2026-07-29, DC1 at
       midspan of a 70 ft span:

       =============================  ==============  =============
       model                          girder ``My``   girder ``N``
       =============================  ==============  =============
       deck on (plates + rigid links) 372.9 kip-ft    180.5 kip
       deck off (bare girders)        610.4 kip-ft    6.9 kip
       =============================  ==============  =============

       with ``w L^2 / 8 = 623.5`` kip-ft by hand.  The deck-on case
       reconciles as ``372.9 + 180.5 * (16.12/12) = 615`` kip-ft; the
       moment is not missing, it is in the couple.  Build with
       ``deck=False`` when you want the girder to carry all of it, or add
       the couple before comparing against
       :func:`~civilpy.structural.box_beam_pipeline.box_beam_line_checks`.
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
