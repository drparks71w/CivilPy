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
    "511E12100": PayItem("511E12100", "Class QC2 concrete, superstructure (deck) [CONFIRM]",
                         "cy", "511", 1),
    "512E10000": PayItem("512E10000", "Concrete, parapet/railing [CONFIRM]",
                         "cy", "512", 1),
    "516E10000": PayItem("516E10000", "Elastomeric bearing [CONFIRM]",
                         "ea", "516", 1),
}


def pay_item(code: str) -> PayItem:
    return PAY_ITEMS[code]


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
    black; ``size`` the bar number (#), diameter in eighths of an inch."""
    dia_in = size / 8.0
    weight_plf = {3: 0.376, 4: 0.668, 5: 1.043, 6: 1.502, 7: 2.044,
                  8: 2.670, 9: 3.400, 10: 4.303, 11: 5.313}.get(size)
    tags = {"mat.spec": "reinforcing steel", "rebar.size": f"#{size}",
            "rebar.dia_in": f"{dia_in:g}", "rebar.coating": coating}
    if weight_plf is not None:
        tags["rebar.weight_plf"] = f"{weight_plf:g}"
    return tags


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


def rebar_tags(bid: str, *, size: int, coating: str = "epoxy", mat: str = "top",
               bend: str = "straight", length_ft: float | None = None,
               scd: str | None = None) -> dict:
    tags = {**_base("rebar", bid, scd=scd), "rebar.mat": mat,
            "rebar.bend": bend, **rebar_mat(size, coating)}
    if length_ft is not None:
        tags["rebar.length_ft"] = f"{length_ft:g}"
        wpf = tags.get("rebar.weight_plf")
        if wpf is not None:
            tags.update(_pay_tags(
                "509E00200" if coating == "epoxy" else "509E00100",
                float(wpf) * length_ft))
    return tags
