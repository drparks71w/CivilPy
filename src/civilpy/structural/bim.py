#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""BrIM attribute schema: the per-component BIM record the Rhino "source of
truth" model carries as user text, and that MIDAS / quantity estimating read
back.

Every component gets a **typed** attribute set (not the blanket ``gdr.*``):

* shared ``bim.type`` (girder / deck / parapet / bearing / load_plate / haunch /
  shear_stud / rebar / diaphragm) and a unique ``bim.id``;
* where the part is a standard detail, ``bim.scd`` + ``bim.scd_year`` -- the
  highest-value BIM keys, since the SCD implies most of the rest;
* a **pay item** (``pay.*``) so quantities roll straight into an estimate;
* a **material** block (``mat.*``): spec/grade/treatment for steel, f'c/class
  for concrete, coating/size for reinforcing.

Builders return a flat ``{key: str}`` dict ready to write to Rhino user text (or
IFC property sets).  Values are strings so they survive the .3dm round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── pay items ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PayItem:
    """An ODOT pay item.  ``level`` is the estimating detail level; ``unit`` the
    quantity unit (lb, ea, cy, ft, sf)."""

    code: str
    description: str
    unit: str
    category: str          # leading item number, e.g. "513" structural steel
    level: int = 1


#: Seed catalog. The two studs/steel items are confirmed from Dane; the concrete
#: and reinforcing items are typical ODOT numbers flagged CONFIRM until verified
#: against the current ODOT Construction & Material Specs item master.
PAY_ITEMS: dict[str, PayItem] = {
    "513E10220": PayItem("513E10220", "Structural steel members, Level 1",
                         "lb", "513", 1),
    "513E20000": PayItem("513E20000", "Shear connectors (welded studs)",
                         "ea", "513", 1),
    "509E00200": PayItem("509E00200", "Epoxy coated reinforcing steel [CONFIRM]",
                         "lb", "509", 1),
    "509E00100": PayItem("509E00100", "Reinforcing steel, black [CONFIRM]",
                         "lb", "509", 1),
    "509E00300": PayItem("509E00300", "GFRP deformed bars [CONFIRM]",
                         "lb", "509", 1),
    "511E12100": PayItem("511E12100", "Class QC2 concrete, superstructure (deck) [CONFIRM]",
                         "cy", "511", 1),
    "512E10000": PayItem("512E10000", "Concrete, parapet/railing [CONFIRM]",
                         "cy", "512", 1),
    "516E10000": PayItem("516E10000", "Elastomeric bearing [CONFIRM]",
                         "ea", "516", 1),
    "511E40000": PayItem("511E40000",
                         "Class QC1 concrete, substructure [CONFIRM]",
                         "cy", "511", 1),
    "507E10000": PayItem("507E10000",
                         "Steel piles HP, furnished and driven [CONFIRM]",
                         "ft", "507", 1),
    "515E10000": PayItem("515E10000",
                         "Prestressed concrete box beam member [CONFIRM]",
                         "ea", "515", 1),
    "515E20000": PayItem("515E20000",
                         "Prestressed concrete I-beam member [CONFIRM]",
                         "ea", "515", 1),
    "515E30000": PayItem("515E30000",
                         "Intermediate diaphragms [CONFIRM]",
                         "ea", "515", 1),
    "526E10000": PayItem("526E10000",
                         "Reinforced concrete approach slabs [CONFIRM]",
                         "sy", "526", 1),
}


def pay_item(code: str) -> PayItem:
    return PAY_ITEMS[code]


#: Planning-level unit prices ($ per pay-item unit) for the seed catalog —
#: round numbers in the range of recent ODOT bid tabulations, meant to rank
#: alternatives and sanity-check a budget, **not** to replace a district
#: estimate.  Override any entry (or add items) through the ``prices``
#: argument of :func:`cost_estimate`.
DEFAULT_UNIT_PRICES: dict[str, float] = {
    "513E10220": 2.25,       # structural steel, fabricated + erected, $/lb
    "513E20000": 10.0,       # welded shear stud, $/ea
    "509E00200": 1.60,       # epoxy coated reinforcing, $/lb
    "509E00100": 1.40,       # black reinforcing, $/lb
    "509E00300": 3.00,       # GFRP deformed bar, $/lb
    "511E12100": 950.0,      # QC2 superstructure (deck) concrete, $/cy
    "511E40000": 850.0,      # QC1 substructure concrete, $/cy
    "512E10000": 1200.0,     # parapet/railing concrete, $/cy
    "516E10000": 2000.0,     # elastomeric bearing, $/ea
    "507E10000": 75.0,       # HP pile furnished + driven, $/ft
    "515E10000": 22000.0,    # PS box beam member, $/ea
    "515E20000": 30000.0,    # PS I-beam member, $/ea
    "515E30000": 1500.0,     # PS intermediate diaphragm, $/ea
    "526E10000": 120.0,      # RC approach slab, $/sy
}


@dataclass(frozen=True)
class CostEstimate:
    """A priced pay-item rollup.  ``rows`` extends the quantity records
    (``{"desc", "unit", "qty", "objects"}``) with ``unit_price`` and
    ``cost``; items the price book doesn't know are listed in ``unpriced``
    (their ``cost`` is ``None``) and excluded from ``total``."""

    rows: dict[str, dict]
    total: float
    unpriced: tuple[str, ...] = ()

    def __str__(self) -> str:
        lines = [f"{'item':<12}{'qty':>14} {'unit':<5}{'unit $':>10}"
                 f"{'cost $':>14}  description"]
        for item, r in self.rows.items():
            up = f"{r['unit_price']:,.2f}" if r["unit_price"] is not None else "--"
            c = f"{r['cost']:,.0f}" if r["cost"] is not None else "--"
            lines.append(f"{item:<12}{r['qty']:>14,.1f} {r['unit']:<5}"
                         f"{up:>10}{c:>14}  {r['desc']}")
        lines.append(f"{'total':<12}{'':>14} {'':<5}{'':>10}"
                     f"{self.total:>14,.0f}")
        return "\n".join(lines)


def cost_estimate(quantities: dict[str, dict],
                  prices: dict[str, float] | None = None) -> CostEstimate:
    """Price a quantity rollup (the ``{item: {"desc", "unit", "qty", ...}}``
    dict that ``pay_item_quantities`` / ``read_bim_quantities`` produce).

    Unit prices come from :data:`DEFAULT_UNIT_PRICES` updated with
    ``prices``; see the caveat there — these are planning numbers."""
    book = {**DEFAULT_UNIT_PRICES, **(prices or {})}
    rows: dict[str, dict] = {}
    total = 0.0
    unpriced: list[str] = []
    for item, rec in sorted(quantities.items()):
        up = book.get(item)
        cost = None if up is None else round(rec["qty"] * up, 2)
        if cost is None:
            unpriced.append(item)
        else:
            total += cost
        rows[item] = {**rec, "unit_price": up, "cost": cost}
    return CostEstimate(rows=rows, total=round(total, 2),
                        unpriced=tuple(unpriced))


def _pay_tags(code: str | None, quantity: float | None = None) -> dict:
    if code is None:
        return {}
    p = PAY_ITEMS.get(code)
    if p is None:
        return {"pay.item": code}
    tags = {"pay.item": p.code, "pay.category": p.category,
            "pay.desc": p.description, "pay.unit": p.unit,
            "pay.level": str(p.level)}
    if quantity is not None:
        tags["pay.qty"] = f"{quantity:g}"
    return tags


# ── material blocks ─────────────────────────────────────────────────────────

def steel_mat(spec: str = "ASTM A709", grade: str = "50W",
              treatment: str = "none") -> dict:
    """Structural-steel material block.  ``grade`` is 36/50/50W/70; ``50W`` and
    ``70W`` are weathering. ``treatment`` = none / galvanized / painted."""
    weathering = grade.upper().endswith("W")
    return {"mat.spec": spec, "mat.grade": grade,
            "mat.type": "weathering steel" if weathering else "carbon steel",
            "mat.treatment": treatment}


def concrete_mat(fc_psi: float, cls: str = "QC2") -> dict:
    """Concrete material block."""
    return {"mat.spec": "concrete", "mat.class": cls,
            "mat.fc_psi": f"{fc_psi:g}"}


def rebar_mat(size: int, coating: str = "epoxy") -> dict:
    """Reinforcing material block.  ``coating`` = epoxy / GFRP / stainless /
    black; ``size`` the bar number (#), diameter in eighths of an inch.
    The tabulated weight is **steel** (C&MS 509); GFRP bars carry the spec
    reference instead (C&MS 705.28) since their weight is producer-specific."""
    dia_in = size / 8.0
    tags = {"rebar.size": f"#{size}", "rebar.dia_in": f"{dia_in:g}",
            "rebar.coating": coating}
    if coating.upper() == "GFRP":
        tags["mat.spec"] = "GFRP, C&MS 705.28"
        return tags
    tags["mat.spec"] = "reinforcing steel"
    weight_plf = {3: 0.376, 4: 0.668, 5: 1.043, 6: 1.502, 7: 2.044,
                  8: 2.670, 9: 3.400, 10: 4.303, 11: 5.313}.get(size)
    if weight_plf is not None:
        tags["rebar.weight_plf"] = f"{weight_plf:g}"
    return tags


#: Reinforcing pay item by coating (see :data:`PAY_ITEMS`).
REBAR_PAY_ITEM = {"epoxy": "509E00200", "black": "509E00100",
                  "gfrp": "509E00300"}


# ── component tag builders ──────────────────────────────────────────────────

def _base(btype: str, bid: str, scd: str | None = None,
          scd_year: str | int | None = None) -> dict:
    tags = {"bim.type": btype, "bim.id": bid}
    if scd is not None:
        tags["bim.scd"] = scd
    if scd_year is not None:
        tags["bim.scd_year"] = str(scd_year)
    return tags


def girder_tags(bid: str, shape: str, *, grade: str = "50W",
                spec: str = "ASTM A709", treatment: str = "none",
                weight_lb: float | None = None) -> dict:
    return {**_base("girder", bid), "girder.shape": shape,
            **steel_mat(spec, grade, treatment),
            **_pay_tags("513E10220", weight_lb)}


def shear_stud_tags(bid: str, *, dia_in: float = 0.875, length_in: float = 6.0,
                    count: int | None = None) -> dict:
    return {**_base("shear_stud", bid), "shear_stud.dia_in": f"{dia_in:g}",
            "shear_stud.length_in": f"{length_in:g}",
            **_pay_tags("513E20000", count)}


def deck_tags(bid: str, *, thickness_in: float, slope_pct: float,
              crown_offset_ft: float, fc_psi: float = 4500.0,
              cls: str = "QC2", volume_cy: float | None = None) -> dict:
    return {**_base("deck", bid), "deck.thickness_in": f"{thickness_in:g}",
            "deck.slope_pct": f"{slope_pct:g}",
            "deck.crown_offset_ft": f"{crown_offset_ft:g}",
            **concrete_mat(fc_psi, cls), **_pay_tags("511E12100", volume_cy)}


def parapet_tags(bid: str, scd: str, *, scd_year: str | int | None = None,
                 height_in: float | None = None, fc_psi: float = 4500.0,
                 length_ft: float | None = None,
                 volume_cy: float | None = None) -> dict:
    tags = {**_base("parapet", bid, scd=scd, scd_year=scd_year),
            **concrete_mat(fc_psi, "QC1"), **_pay_tags("512E10000", volume_cy)}
    if height_in is not None:
        tags["parapet.height_in"] = f"{height_in:g}"
    if length_ft is not None:
        tags["parapet.length_ft"] = f"{length_ft:g}"
    return tags


def approach_slab_tags(bid: str, scd: str = "AS-1-15", *,
                       scd_year: str | int | None = None,
                       length_ft: float, width_ft: float,
                       thickness_in: float, skew_deg: float = 0.0,
                       fc_psi: float = 4500.0,
                       area_sy: float | None = None) -> dict:
    """Approach slab concrete.  ITEM 526 measures the plan **area** (sy)
    and includes the slab reinforcing (anchor bars into the abutment are
    the exception — they measure under the ITEM 509 reinforcing items)."""
    return {**_base("approach_slab", bid, scd=scd, scd_year=scd_year),
            "approach_slab.length_ft": f"{length_ft:g}",
            "approach_slab.width_ft": f"{width_ft:g}",
            "approach_slab.thickness_in": f"{thickness_in:g}",
            "approach_slab.skew_deg": f"{skew_deg:g}",
            **concrete_mat(fc_psi, "QC1"), **_pay_tags("526E10000", area_sy)}


def bearing_tags(bid: str, *, fixity: str, kind: str = "elastomeric",
                 plies: int | None = None, ply_thickness_in: float | None = None,
                 total_thickness_in: float | None = None) -> dict:
    tags = {**_base("bearing", bid), "bearing.kind": kind,
            "bearing.fixity": fixity, **_pay_tags("516E10000", 1)}
    if plies is not None:
        tags["bearing.plies"] = str(plies)
    if ply_thickness_in is not None:
        tags["bearing.ply_thickness_in"] = f"{ply_thickness_in:g}"
    if total_thickness_in is not None:
        tags["bearing.total_thickness_in"] = f"{total_thickness_in:g}"
    return tags


def load_plate_tags(bid: str, *, thickness_in: float, grade: str = "50",
                    spec: str = "ASTM A709", weight_lb: float | None = None) -> dict:
    return {**_base("load_plate", bid), "load_plate.thickness_in": f"{thickness_in:g}",
            **steel_mat(spec, grade), **_pay_tags("513E10220", weight_lb)}


def haunch_tags(bid: str, *, depth_in: float, width_in: float,
                fc_psi: float = 4500.0,
                volume_cy: float | None = None) -> dict:
    """Haunch concrete is conventionally measured with the superstructure
    (deck) concrete item, so a ``volume_cy`` rolls into ``511E12100``."""
    tags = {**_base("haunch", bid), "haunch.depth_in": f"{depth_in:g}",
            "haunch.width_in": f"{width_in:g}", **concrete_mat(fc_psi, "QC2")}
    if volume_cy is not None:
        tags.update(_pay_tags("511E12100", volume_cy))
    return tags


#: Substructure concrete component types (one Rhino layer each).
SUBSTRUCTURE_CONCRETE_TYPES = (
    "pier_cap", "abutment_cap", "beam_seat", "column", "footing",
    "backwall", "wingwall", "foreslope_wall", "cutoff_wall")


def substructure_concrete_tags(btype: str, bid: str, *,
                               fc_psi: float = 4000.0, cls: str = "QC1",
                               volume_cy: float | None = None,
                               **dims: float) -> dict:
    """Tag block for a cast-in-place substructure concrete component.

    ``btype`` is one of :data:`SUBSTRUCTURE_CONCRETE_TYPES`; extra ``dims``
    keywords flatten to ``"<btype>.<key>"`` string tags (e.g.
    ``depth_ft=5.0`` on a ``pier_cap`` becomes ``pier_cap.depth_ft``).
    All substructure concrete measures into the one Class QC1 substructure
    item, the way haunches roll into the deck item."""
    if btype not in SUBSTRUCTURE_CONCRETE_TYPES:
        raise ValueError(f"unknown substructure component type {btype!r}")
    tags = {**_base(btype, bid), **concrete_mat(fc_psi, cls),
            **_pay_tags("511E40000", volume_cy)}
    for k, v in dims.items():
        tags[f"{btype}.{k}"] = f"{v:g}"
    return tags


def box_beam_tags(bid: str, *, box: str, depth_in: float, beam_type: str,
                  part: str, span_ft: float, scd: str | None = "PSBD-1-25",
                  scd_year: str | int | None = 2025,
                  fc_psi: float = 6000.0, n_strands: int | None = None,
                  concrete_cy: float | None = None,
                  count: int | None = None) -> dict:
    """Prestressed box-beam member.  The member is drawn as several
    ``part`` prisms (top/bottom flange, webs) sharing a beam id prefix;
    exactly one part per beam carries ``count`` so the 515 member item
    counts each beam once (strands, tie rods, and precast diaphragms are
    included in the member)."""
    tags = {**_base("box_beam", bid, scd=scd, scd_year=scd_year),
            "box_beam.box": box, "box_beam.depth_in": f"{depth_in:g}",
            "box_beam.beam_type": beam_type, "box_beam.part": part,
            "box_beam.span_ft": f"{span_ft:g}",
            **concrete_mat(fc_psi, "prestressed")}
    if n_strands is not None:
        tags["box_beam.n_strands"] = str(n_strands)
    if concrete_cy is not None:
        tags["box_beam.concrete_cy"] = f"{concrete_cy:g}"
    if count is not None:
        tags.update(_pay_tags("515E10000", count))
    return tags


def ps_i_beam_tags(bid: str, *, section: str, depth_in: float,
                   span_ft: float, scd: str | None = "PSID-1-13",
                   scd_year: str | int | None = 2025,
                   fc_psi: float = 5500.0, n_strands: int | None = None,
                   n_debonded: int | None = None,
                   concrete_cy: float | None = None,
                   count: int | None = None) -> dict:
    """Prestressed I-beam member (PSID-1-13).  One prism per beam; the
    member carries the 515 I-beam item (strands, embedded sole plates,
    and anchorage-zone steel are included in the member per sheet 10)."""
    tags = {**_base("ps_i_beam", bid, scd=scd, scd_year=scd_year),
            "ps_i_beam.section": section,
            "ps_i_beam.depth_in": f"{depth_in:g}",
            "ps_i_beam.span_ft": f"{span_ft:g}",
            **concrete_mat(fc_psi, "prestressed")}
    if n_strands is not None:
        tags["ps_i_beam.n_strands"] = str(n_strands)
    if n_debonded is not None:
        tags["ps_i_beam.n_debonded"] = str(n_debonded)
    if concrete_cy is not None:
        tags["ps_i_beam.concrete_cy"] = f"{concrete_cy:g}"
    if count is not None:
        tags.update(_pay_tags("515E20000", count))
    return tags


def tendon_tags(bid: str, *, strands: int, row_in: float,
                debonded: int | None = None) -> dict:
    """One schematic prestressing-strand row (paid with the member).
    ``debonded`` counts the row's strands debonded at each beam end."""
    tags = {**_base("tendon", bid), "tendon.strands": str(strands),
            "tendon.row_in": f"{row_in:g}",
            "mat.spec": "prestressing strand, AASHTO M203 Gr 270"}
    if debonded:
        tags["tendon.debonded"] = str(debonded)
    return tags


def tie_rod_tags(bid: str, *, diameter_in: float,
                 station_ft: float) -> dict:
    """Transverse tie rod (paid with the members)."""
    return {**_base("tie_rod", bid), "tie_rod.diameter_in": f"{diameter_in:g}",
            "tie_rod.station_ft": f"{station_ft:g}",
            **steel_mat("ASTM A307", "307A")}


def diaphragm_tags(bid: str, *, thickness_in: float, fc_psi: float = 4500.0,
                   volume_cy: float | None = None, pay: bool = True,
                   item: str = "511E12100",
                   count: float | None = None) -> dict:
    """Concrete end/intermediate diaphragm.  Integral and semi-integral
    end diaphragms are cast with (and move with) the superstructure, so
    their concrete measures into the superstructure item like the
    haunches; a box beam's precast diaphragms are included in the member
    (``pay=False``).  A PS I-beam bridge's intermediate diaphragms have
    their own 515 each-measured item (PSID-1-13 sheet 10) — pass
    ``item="515E30000"`` with ``count`` instead of ``volume_cy``."""
    tags = {**_base("diaphragm", bid),
            "diaphragm.thickness_in": f"{thickness_in:g}",
            **concrete_mat(fc_psi, "QC2")}
    if pay:
        tags.update(_pay_tags(item, count if count is not None
                              else volume_cy))
    return tags


def cross_frame_tags(bid: str, *, frame_type: str, member_shape: str,
                     grade: str = "50", weight_lb: float | None = None) -> dict:
    """Intermediate cross-frame / steel diaphragm bay (build plan §3a).  Its
    members are fabricated structural steel measured by weight into the 513
    item like the girders."""
    return {**_base("cross_frame", bid), "cross_frame.type": frame_type,
            "cross_frame.member": member_shape, **steel_mat(grade=grade),
            **_pay_tags("513E10220", weight_lb)}


def stiffener_tags(bid: str, *, kind: str, thickness_in: float,
                   grade: str = "50", weight_lb: float | None = None) -> dict:
    """Web/bearing/longitudinal stiffener plate (§3a).  ``kind`` is
    ``transverse`` / ``bearing`` / ``longitudinal``; measured by weight into
    the 513 structural-steel item."""
    return {**_base("stiffener", bid), "stiffener.kind": kind,
            "stiffener.thickness_in": f"{thickness_in:g}",
            **steel_mat(grade=grade), **_pay_tags("513E10220", weight_lb)}


def field_splice_tags(bid: str, *, bolt_count: int, grade: str = "50",
                      weight_lb: float | None = None) -> dict:
    """Bolted field splice (§3a): the splice plates are structural steel by
    weight (513); the high-strength bolts are incidental, carried as a count."""
    return {**_base("field_splice", bid), "field_splice.bolts": str(bolt_count),
            **steel_mat(grade=grade), **_pay_tags("513E10220", weight_lb)}


def pile_tags(bid: str, *, shape: str, length_ft: float, grade: str = "50",
              spec: str = "ASTM A572") -> dict:
    """Driven steel HP pile: pay quantity is the furnished+driven length
    (ft) below cutoff."""
    return {**_base("pile", bid), "pile.shape": shape,
            "pile.length_ft": f"{length_ft:g}", **steel_mat(spec, grade),
            **_pay_tags("507E10000", length_ft)}


def rebar_tags(bid: str, *, size: int, coating: str = "epoxy", mat: str = "top",
               bend: str = "straight", length_ft: float | None = None,
               scd: str | None = None) -> dict:
    tags = {**_base("rebar", bid, scd=scd), "rebar.mat": mat,
            "rebar.bend": bend, **rebar_mat(size, coating)}
    if length_ft is not None:
        tags["rebar.length_ft"] = f"{length_ft:g}"
        item = REBAR_PAY_ITEM.get(coating.lower())
        wpf = tags.get("rebar.weight_plf")
        if item is not None and wpf is not None:
            tags.update(_pay_tags(item, float(wpf) * length_ft))
        elif item is not None:
            # GFRP: item known, weight producer-specific -> qty left off
            tags.update(_pay_tags(item))
    return tags
