#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""AASHTO LRFD 6.13.6.1 — bolted field-splice *designer* for steel plate
girders.

Given the girder section on each side of a splice, the splice-centerline
loads, and the bolt / splice-plate / clearance selections, this module sizes
the flange and web bolt counts, lays out the bolt pattern (gage, pitch, edge,
end) and splice-plate lengths, and runs the AASHTO limit-state checks by
feeding the article-level primitives in
:mod:`civilpy.structural.aashto.lrfd.steel` and
:mod:`civilpy.structural.aashto.lrfd.splices`.

Units are kip, inch, ksi throughout (moments are supplied in kip-ft and
converted internally).  The design procedure follows the 8th/9th Edition
simplified flange-force method (C6.13.6.1.3b, 6.13.6.1.3c); the bolt shear
coefficient is the 8th-Edition value (0.56/0.45) via ``design_year``.

Known limitations mirrored from the reference procedure: AASHTO 6.10.1.8
(tension flanges with holes) is not checked; two-row seal-gage edge cases and
rolled-beam splices with >10% inner/outer plate-area difference are flagged
rather than resolved.

The web bolt group is sized for the design shear plus the geometric
(maximum-pitch) requirement.  When the flanges cannot resist the full splice
moment, AASHTO 6.13.6.1.3c transfers the excess as a horizontal web force
``Huw = (Aw/2)*(Rh*Fcf + Rcf*fncf)`` that can dominate the web bolt count; the
elastic flange stresses ``Fcf``/``fncf`` require a composite section-property
analysis that this module does not yet perform, so that governing case is
reported through the flange ``Mflange``/slip checks (which fail) rather than by
enlarging the web group.  A ``NOTICE``-level flange check therefore signals a
splice whose web should be re-designed by hand for the moment couple.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural.aashto.lrfd.core import CheckResult
from civilpy.structural.aashto.lrfd import steel, splices

# --- material / bolt reference tables (AASHTO / RCSC, kip-in-ksi) ----------

# Fy, Fu (ksi) by grade string.
STEEL_GRADES: dict[str, tuple[float, float]] = {
    "Grade 36": (36.0, 58.0),
    "Grade 50": (50.0, 65.0),
    "Grade 50CR": (50.0, 70.0),
    "Grade 50W": (50.0, 70.0),
    "HPS Grade 50W": (50.0, 70.0),
    "HPS Grade 70W": (70.0, 85.0),
    "HPS Grade 100W": (100.0, 110.0),
}

BOLT_FU: dict[str, float] = {"A325": 120.0, "A490": 150.0}

# Standard hole diameter (in) by bolt diameter (in) — Table 6.13.2.6.7-1.
STANDARD_HOLE_DIA: dict[float, float] = {
    0.625: 0.6875, 0.75: 0.8125, 0.875: 0.9375, 1.0: 1.125,
    1.125: 1.25, 1.25: 1.375, 1.375: 1.5,
}

# Standard minimum edge/end distance (in) by bolt diameter — Table 6.13.2.6.6-1.
STANDARD_MIN_EDGE_END: dict[float, float] = {
    0.625: 0.875, 0.75: 1.0, 0.875: 1.125, 1.0: 1.25,
    1.125: 1.5, 1.25: 1.625, 1.375: 1.71875,
}


def _grade(material: str) -> tuple[float, float]:
    try:
        return STEEL_GRADES[material]
    except KeyError:
        raise ValueError(f"unknown steel grade {material!r}")


def _hole_dia(d_bolt: float) -> float:
    return STANDARD_HOLE_DIA.get(round(d_bolt, 4), d_bolt + 0.0625)


def _min_edge_end(d_bolt: float) -> float:
    return STANDARD_MIN_EDGE_END.get(round(d_bolt, 4), 1.25 * d_bolt)


def _ceil_mult(x: float, m: int) -> int:
    """Round ``x`` up to the nearest positive multiple of ``m`` (Excel CEILING)."""
    if x <= 0:
        return m
    return int(math.ceil(x / m)) * m


def _floor_eighth(x: float) -> float:
    return math.floor(x * 8.0) / 8.0


def _block_shear(n_shear, l_shear, holes_shear, n_tension, tens_gross,
                 holes_tension, t, f_y, f_u, hole, p_u, name):
    """Block-shear rupture (6.13.4) for a rectangular tear-out.  ``n_shear``
    parallel shear planes of gross length ``l_shear`` (each crossing
    ``holes_shear`` holes) and ``n_tension`` tension planes of gross length
    ``tens_gross`` (each crossing ``holes_tension`` holes), all of thickness
    ``t``.  Wraps :func:`steel.block_shear_resistance`."""
    a_vg = n_shear * l_shear * t
    a_vn = a_vg - n_shear * holes_shear * hole * t
    a_tn = (n_tension * tens_gross - n_tension * holes_tension * hole) * t
    res = steel.block_shear_resistance(
        a_vg=a_vg, a_vn=max(a_vn, 0.0), a_tn=max(a_tn, 0.0),
        f_y=f_y, f_u=f_u, p_u=p_u)
    res.name = name
    return res


# --- structured inputs ------------------------------------------------------

@dataclass(frozen=True)
class Flange:
    """One flange of one girder side."""

    material: str
    thickness: float
    width: float

    @property
    def area(self) -> float:
        return self.thickness * self.width


@dataclass(frozen=True)
class GirderSide:
    """The plate-girder cross section on one side of the splice."""

    top_flange: Flange
    bottom_flange: Flange
    web_material: str
    web_thickness: float
    web_depth: float
    haunch: float = 0.0
    stiffener_spacing_ft: float | None = None  # d_o
    stiffened: bool = True


@dataclass(frozen=True)
class SpliceLoads:
    """Unfactored moment (kip-ft) and shear (kip) at the splice centerline."""

    dc1_m: float = 0.0
    dc1_v: float = 0.0
    dc2_m: float = 0.0
    dc2_v: float = 0.0
    dw_m: float = 0.0
    dw_v: float = 0.0
    ll_pos_m: float = 0.0
    ll_pos_v: float = 0.0
    ll_neg_m: float = 0.0
    ll_neg_v: float = 0.0
    deck_cast_m: float = 0.0
    deck_cast_v: float = 0.0


@dataclass(frozen=True)
class BoltSpec:
    bolt_type: str = "A325"
    diameter: float = 0.875
    flange_threads_excluded: bool = True
    web_threads_excluded: bool = False
    surface_class: str = "B"  # Ks class
    hole_type: str = "standard"  # Kh


@dataclass(frozen=True)
class PlatePair:
    """Inner + outer splice plates for a flange (user-selected, then checked)."""

    material: str
    inner_thickness: float
    inner_width: float
    outer_thickness: float
    outer_width: float
    shear_planes: int = 2

    @property
    def inner_area(self) -> float:
        # two inner plates (one each side of the web).
        return 2.0 * self.inner_thickness * self.inner_width

    @property
    def outer_area(self) -> float:
        return self.outer_thickness * self.outer_width


@dataclass(frozen=True)
class WebPlate:
    material: str
    thickness: float
    shear_planes: int = 2


@dataclass(frozen=True)
class SpliceInput:
    left: GirderSide
    right: GirderSide
    loads: SpliceLoads
    bolts: BoltSpec
    top_plates: PlatePair
    bottom_plates: PlatePair
    web_plate: WebPlate
    deck_composite: bool = True
    deck_thickness: float = 0.0
    deck_eff_width: float = 0.0
    fc: float = 4.0
    top_flange_rows: int = 4
    bottom_flange_rows: int = 4
    web_rows: int = 2
    bolt_spacing: float = 3.0       # pitch and gage between adjacent bolts
    flange_edge: float = 2.0
    flange_end: float = 1.5
    web_edge: float = 2.0
    web_end: float = 1.5
    web_weld_size: float = 0.3125
    web_weld_clearance: float = 0.375
    girder_gap: float = 0.75
    entering_tightening: float = 3.0
    design_year: int = 2020


# --- structured results -----------------------------------------------------

@dataclass
class ComponentDesign:
    name: str
    bolt_rows: int
    total_bolts: int
    strength_bolts: int
    slip_bolts: int
    controlling_bolts: int
    design_force: float                 # kip (Pfy for flange, Vuw for web)
    gage_bolts: float = 0.0
    gage_groups: float = 0.0
    pitch: float = 0.0
    pitch_groups: float = 0.0
    edge: float = 0.0
    end: float = 0.0
    plate_thickness: float = 0.0
    plate_width: float = 0.0
    plate_length: float = 0.0
    long_joint: bool = False
    checks: list[CheckResult] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(c.ok is not False for c in self.checks)


@dataclass
class SpliceDesign:
    factored_moments: dict
    factored_shears: dict
    top_flange: ComponentDesign
    bottom_flange: ComponentDesign
    web: ComponentDesign

    @property
    def components(self) -> list[ComponentDesign]:
        return [self.top_flange, self.bottom_flange, self.web]

    @property
    def checks(self) -> list[CheckResult]:
        out: list[CheckResult] = []
        for c in self.components:
            out.extend(c.checks)
        return out

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.components)


# --- load combinations ------------------------------------------------------

def _factor_loads(loads: SpliceLoads) -> tuple[dict, dict]:
    """Factored moments (kip-ft) and shears (kip) for the governing splice
    load combinations: Strength I (+/-), Service II (+/-), Deck Casting."""
    lo = loads
    dc = lo.dc1_m + lo.dc2_m
    m = {
        "deck_cast": 1.4 * lo.deck_cast_m,
        "strength_pos": 1.25 * lo.dc1_m + 1.25 * lo.dc2_m + 1.5 * lo.dw_m
        + 1.75 * lo.ll_pos_m,
        "strength_neg": 0.9 * lo.dc1_m + 0.9 * lo.dc2_m + 0.65 * lo.dw_m
        + 1.75 * lo.ll_neg_m,
        "service_pos": dc + lo.dw_m + 1.3 * lo.ll_pos_m,
        "service_neg": dc + lo.dw_m + 1.3 * lo.ll_neg_m,
    }
    dcv = lo.dc1_v + lo.dc2_v
    v = {
        "deck_cast": 1.4 * lo.deck_cast_v,
        "service_pos": dcv + lo.dw_v + 1.3 * lo.ll_pos_v,
        "service_neg": dcv + lo.dw_v + 1.3 * lo.ll_neg_v,
    }
    return m, v


# --- flange design ----------------------------------------------------------

def _flange_pfy(flange: Flange, n_rows: int, hole_dia: float):
    """Design force Pfy for one flange (6.13.6.1.3b) and its areas."""
    fy, fu = _grade(flange.material)
    a_g = flange.area
    a_n = (flange.width - n_rows * hole_dia) * flange.thickness
    res = splices.flange_splice_design_force(a_n=a_n, a_g=a_g, f_y=fy, f_u=fu)
    return res.capacity, a_g, a_n, res.details["Ae"], fy, fu


def _design_flange(inp: SpliceInput, position: str) -> ComponentDesign:
    b = inp.bolts
    hole = _hole_dia(b.diameter)
    if position == "top":
        left_f, right_f = inp.left.top_flange, inp.right.top_flange
        plates, n_rows = inp.top_plates, inp.top_flange_rows
    else:
        left_f, right_f = inp.left.bottom_flange, inp.right.bottom_flange
        plates, n_rows = inp.bottom_plates, inp.bottom_flange_rows

    pfy_l, ag_l, an_l, ae_l, fy_l, fu_l = _flange_pfy(left_f, n_rows, hole)
    pfy_r, *_ = _flange_pfy(right_f, n_rows, hole)
    pfy = min(pfy_l, pfy_r)                      # weaker flange governs
    ctrl = left_f if pfy_l <= pfy_r else right_f

    # filler on the thinner flange (thickness difference >= 1/8 in matters)
    filler_t = abs(left_f.thickness - right_f.thickness)
    a_f = filler_t * plates.outer_width
    a_p = min(min(left_f.area, right_f.area),
              plates.inner_area + plates.outer_area)
    filler = splices.filler_plate_reduction(a_f, a_p, filler_t)
    r_fill = filler.capacity

    # bolt shear capacity (double / single) for the flange group
    bolt = steel.bolt_shear_resistance(
        d_bolt=b.diameter, f_ub=BOLT_FU[b.bolt_type],
        n_planes=plates.shear_planes,
        threads_excluded=b.flange_threads_excluded,
        design_year=inp.design_year,
    )
    bolt_cap = bolt.factored_capacity  # phi already applied

    # strength bolt count
    strength_initial = pfy / (bolt_cap * r_fill)
    strength_bolts = _ceil_mult(strength_initial, n_rows)

    # slip capacity per bolt (Service II, phi = 1.0)
    slip = steel.bolt_slip_resistance(
        bolt_grade=b.bolt_type, d_bolt=b.diameter,
        n_planes=plates.shear_planes, hole_type=b.hole_type,
        surface_class=b.surface_class,
    )
    pt_per = slip.capacity

    m, _ = _factor_loads(inp.loads)
    # composite positive-moment arm and steel (non-composite) arm
    web_depth = inp.left.web_depth
    t_top = inp.left.top_flange.thickness
    t_bot = inp.left.bottom_flange.thickness
    arm_pos = ((inp.deck_thickness / 2.0 + inp.left.haunch + web_depth
                + t_bot / 2.0) if inp.deck_composite
               else web_depth + (t_top + t_bot) / 2.0)
    arm_steel = web_depth + (t_top + t_bot) / 2.0

    def slip_count(moment_kft, arm, rows):
        force = abs(moment_kft) * 12.0 / arm
        return _ceil_mult(force / pt_per, rows), force

    if position == "bottom":
        n_pos, f_pos = slip_count(m["service_pos"], arm_pos, n_rows)
        n_deck, f_deck = slip_count(m["deck_cast"], arm_steel, n_rows)
        slip_bolts = max(n_pos, n_deck)
        slip_force = max(f_pos, f_deck)
    else:
        slip_bolts, slip_force = slip_count(m["service_neg"], arm_steel,
                                            n_rows)

    # Controlling bolt count is sized for strength and the long-joint
    # reduction only; slip (a serviceability limit) is reported as a separate
    # check and does not increase the count (C6.13.6.1.3b / NSBA convention).
    controlling = strength_bolts
    cols = controlling // n_rows
    joint_len = (cols - 1) * inp.bolt_spacing
    long_joint = joint_len >= 38.0
    if long_joint:
        lj_cap = bolt_cap * 0.83
        lj_bolts = _ceil_mult(pfy / (lj_cap * r_fill), n_rows)
        controlling = max(controlling, lj_bolts)
        cols = controlling // n_rows

    # ---- geometric layout ----
    inner_w = plates.inner_width
    outer_w = plates.outer_width
    edge = inp.flange_edge
    end = inp.flange_end
    gage_bolts = ((inner_w - 2.0 * edge) / (n_rows / 2 - 1)
                  if n_rows > 2 else 0.0)
    gage_groups = outer_w - 2.0 * edge - 2.0 * (n_rows / 2 - 1) * gage_bolts
    pitch = inp.bolt_spacing
    pitch_groups = max(2.0 * end + inp.girder_gap, pitch)
    plate_length = 2.0 * end + 2.0 * ((cols - 1) * pitch) + pitch_groups

    comp = ComponentDesign(
        name=f"{position}_flange",
        bolt_rows=n_rows,
        total_bolts=controlling,
        strength_bolts=strength_bolts,
        slip_bolts=slip_bolts,
        controlling_bolts=controlling,
        design_force=pfy,
        gage_bolts=gage_bolts,
        gage_groups=gage_groups,
        pitch=pitch,
        pitch_groups=pitch_groups,
        edge=edge,
        end=end,
        plate_thickness=plates.outer_thickness,
        plate_width=outer_w,
        plate_length=plate_length,
        long_joint=long_joint,
        extra={"filler_R": r_fill, "Ae": ae_l, "arm_pos": arm_pos,
               "arm_steel": arm_steel, "cols": cols, "hole_dia": hole,
               "slip_force": slip_force, "pt_per": pt_per},
    )
    # Service II slip check (6.13.2.8): the provided bolts must furnish more
    # nominal slip resistance than the flange force at Service II.
    comp.checks.append(CheckResult(
        article="6.13.2.8", name=f"{position} flange Service II slip",
        capacity=controlling * pt_per, demand=slip_force))
    _flange_checks(inp, comp, plates, ctrl, pfy, fy_l, fu_l, hole, n_rows)
    return comp


def _flange_checks(inp, comp, plates, ctrl, pfy, fy, fu, hole, n_rows):
    """Splice-plate and girder-flange limit-state checks for one flange."""
    plate_fy, plate_fu = _grade(plates.material)
    sp = splices.splice_plate_design_force(
        pfy, plates.outer_area, plates.inner_area)
    checks = comp.checks

    cols = comp.extra["cols"]
    l_shear = comp.end + (cols - 1) * comp.pitch
    holes_shear = cols - 0.5

    for label, force, thk, width, a_g in (
        ("outer", sp.outer, plates.outer_thickness, plates.outer_width,
         plates.outer_area),
        ("inner", sp.inner, plates.inner_thickness, 2 * plates.inner_width,
         plates.inner_area),
    ):
        a_n = (width - n_rows * hole) * (a_g / width if width else 0.0)
        # factored yield on gross section (6.13.5.2 / 6.8.2.1)
        yield_r = 0.95 * plate_fy * a_g
        checks.append(CheckResult(
            article="6.13.5.2", name=f"{label} plate yield (tension)",
            capacity=yield_r, demand=force))
        # net-section reduction notice + fracture (6.13.5.2 / 6.13.6.1.3)
        nsr = splices.net_section_reduction_limit(a_n, a_g)
        checks.append(nsr)
        a_e = nsr.details["An_eff"]
        checks.append(CheckResult(
            article="6.13.6.1.3", name=f"{label} plate net-section fracture",
            capacity=0.80 * plate_fu * a_e, demand=force))
        # block shear on the splice plate (6.13.4): a single tear-out block,
        # two shear planes plus two tension planes through the end holes.
        checks.append(_block_shear(
            n_shear=2, l_shear=l_shear, holes_shear=holes_shear,
            n_tension=2, tens_gross=comp.gage_bolts + comp.edge,
            holes_tension=1.5, t=thk, f_y=plate_fy, f_u=plate_fu, hole=hole,
            p_u=force, name=f"{label} plate block shear"))

    # block shear on the girder flange (6.13.4): the two bolt groups can tear
    # out independently (Mode 1, four shear planes) or as one block around the
    # outside (Mode 2, two shear planes through the wider tension planes); the
    # smaller resistance governs.
    mode1 = _block_shear(
        n_shear=4, l_shear=l_shear, holes_shear=holes_shear, n_tension=2,
        tens_gross=comp.gage_bolts, holes_tension=1.0, t=ctrl.thickness,
        f_y=fy, f_u=fu, hole=hole, p_u=pfy,
        name="girder flange block shear (Mode 1)")
    mode2 = _block_shear(
        n_shear=2, l_shear=l_shear, holes_shear=holes_shear, n_tension=2,
        tens_gross=comp.gage_bolts + comp.edge, holes_tension=1.5,
        t=ctrl.thickness, f_y=fy, f_u=fu, hole=hole, p_u=pfy,
        name="girder flange block shear (Mode 2)")
    checks.append(mode1)
    checks.append(mode2)

    # bearing at the flange bolt holes (6.13.2.9): each bolt delivers the
    # lesser of its (filler-reduced) shear capacity or the hole bearing
    # resistance; interior holes govern the group total (end holes carry no
    # less than interior once bolt shear controls).
    r_fill = comp.extra["filler_R"]
    bolt = steel.bolt_shear_resistance(
        d_bolt=inp.bolts.diameter, f_ub=BOLT_FU[inp.bolts.bolt_type],
        n_planes=plates.shear_planes,
        threads_excluded=inp.bolts.flange_threads_excluded,
        design_year=inp.design_year)
    interior = steel.bolt_bearing_resistance(
        d_bolt=inp.bolts.diameter, t_ply=ctrl.thickness, f_u_ply=fu,
        clear_distance=comp.pitch - hole)
    per_bolt = min(bolt.factored_capacity * r_fill,
                   interior.factored_capacity)
    checks.append(CheckResult(
        article="6.13.2.9", name="girder flange bearing",
        capacity=per_bolt * comp.total_bolts, demand=pfy))


# --- web design -------------------------------------------------------------

def _web_vn(side: GirderSide) -> float:
    fy, _ = _grade(side.web_material)
    d_o = (side.stiffener_spacing_ft * 12.0
           if (side.stiffened and side.stiffener_spacing_ft) else None)
    kwargs = {}
    if d_o is not None:
        kwargs = dict(d_o=d_o, tension_field=True,
                      b_fc=side.top_flange.width, t_fc=side.top_flange.thickness,
                      b_ft=side.bottom_flange.width,
                      t_ft=side.bottom_flange.thickness)
    res = steel.web_shear_resistance(
        d_web=side.web_depth, t_w=side.web_thickness, f_yw=fy, **kwargs)
    return res.factored_capacity


def _design_web(inp: SpliceInput) -> ComponentDesign:
    b, wp = inp.bolts, inp.web_plate
    n_rows = inp.web_rows
    v_left = _web_vn(inp.left)
    v_right = _web_vn(inp.right)
    v_uw = min(v_left, v_right)

    bolt = steel.bolt_shear_resistance(
        d_bolt=b.diameter, f_ub=BOLT_FU[b.bolt_type], n_planes=wp.shear_planes,
        threads_excluded=b.web_threads_excluded, design_year=inp.design_year)
    bolt_cap = bolt.factored_capacity

    m, v = _factor_loads(inp.loads)
    h_w = 0.0  # flanges carry the moment in the standard case
    resultant = math.hypot(v_uw, h_w)
    strength_bolts = _ceil_mult(resultant / bolt_cap, n_rows)

    slip = steel.bolt_slip_resistance(
        bolt_grade=b.bolt_type, d_bolt=b.diameter, n_planes=wp.shear_planes,
        hole_type=b.hole_type, surface_class=b.surface_class)
    pt_per = slip.capacity
    slip_bolts = max(
        _ceil_mult(abs(v["deck_cast"]) / pt_per, n_rows),
        _ceil_mult(abs(v["service_pos"]) / pt_per, n_rows),
        _ceil_mult(abs(v["service_neg"]) / pt_per, n_rows),
    )

    # plate-height geometry -> maximum bolt count at max seal spacing
    max_seal = min(4.0 + 4.0 * wp.thickness, 7.0)
    max_h = inp.left.web_depth - 2.0 * (inp.web_weld_size
                                        + inp.web_weld_clearance)
    et = inp.entering_tightening
    wc = inp.web_weld_size + inp.web_weld_clearance

    def end_adj(inner_plate_t):
        if (wc + inp.web_end) > (et + inner_plate_t):
            f = inp.web_end
        else:
            f = (et + inner_plate_t) - wc
        return inp.web_end - f

    max_end_adj = min(end_adj(inp.top_plates.inner_thickness),
                      end_adj(inp.bottom_plates.inner_thickness))
    height_adj = max_h + 2.0 * max_end_adj
    pitch_bolts = n_rows * int(math.ceil(
        1.0 + (height_adj - 2.0 * inp.web_end) / max_seal))

    controlling = max(strength_bolts, slip_bolts, pitch_bolts)
    per_row = controlling // n_rows

    pitch = min(_floor_eighth(
        (height_adj - 2.0 * inp.web_end) / (per_row - 1)), max_seal)
    plate_height = pitch * (per_row - 1) + 2.0 * inp.web_end
    gage_bolts = inp.bolt_spacing
    gage_groups = 2.0 * inp.web_edge + inp.girder_gap
    plate_width = (2.0 * inp.web_edge + 2.0 * (n_rows - 1) * gage_bolts
                   + gage_groups)

    comp = ComponentDesign(
        name="web",
        bolt_rows=n_rows,
        total_bolts=controlling,
        strength_bolts=strength_bolts,
        slip_bolts=slip_bolts,
        controlling_bolts=controlling,
        design_force=v_uw,
        gage_bolts=gage_bolts,
        gage_groups=gage_groups,
        pitch=pitch,
        pitch_groups=0.0,
        edge=inp.web_edge,
        end=inp.web_end,
        plate_thickness=wp.thickness,
        plate_width=plate_width,
        plate_length=plate_height,
        extra={"pitch_bolts": pitch_bolts, "height_adj": height_adj,
               "per_row": per_row, "v_left": v_left, "v_right": v_right,
               "Vp_left": 0.58 * _grade(inp.left.web_material)[0]
               * inp.left.web_depth * inp.left.web_thickness},
    )
    _web_checks(inp, comp, v_uw)
    return comp


def _web_checks(inp, comp, v_uw):
    wp = inp.web_plate
    fy, fu = _grade(wp.material)
    hole = _hole_dia(inp.bolts.diameter)
    checks = comp.checks
    # two web plates (double shear) resist the shear on the gross/net section
    a_g = 2.0 * comp.plate_length * wp.thickness
    per_row = comp.extra["per_row"]
    a_n = a_g - 2.0 * per_row * hole * wp.thickness
    # factored shear-yield resistance of the two web plates (6.13.5.2 /
    # 6.13.4-2): phi_v = 1.0 for shear.
    checks.append(CheckResult(
        article="6.13.5.2", name="web plate shear yield",
        capacity=1.0 * 0.58 * fy * a_g, demand=abs(v_uw)))
    checks.append(CheckResult(
        article="6.13.5.2", name="web plate shear rupture",
        capacity=0.80 * 0.58 * fu * a_n, demand=abs(v_uw)))
    bearing = steel.bolt_bearing_resistance(
        d_bolt=inp.bolts.diameter, t_ply=wp.thickness, f_u_ply=fu,
        clear_distance=comp.end - hole / 2.0)
    checks.append(CheckResult(
        article="6.13.2.9", name="web bearing",
        capacity=bearing.factored_capacity * comp.total_bolts,
        demand=abs(v_uw)))


# --- top-level entry --------------------------------------------------------

def design_splice(inp: SpliceInput) -> SpliceDesign:
    """Design a bolted field splice: size bolts, lay out the pattern, and run
    the AASHTO limit-state checks for both flanges and the web."""
    m, v = _factor_loads(inp.loads)
    top = _design_flange(inp, "top")
    bottom = _design_flange(inp, "bottom")
    web = _design_web(inp)

    # composite slab crushing check (Appendix D6.1) at the tension flange
    if inp.deck_composite and inp.deck_eff_width > 0:
        sc = splices.slab_crushing_resistance(
            f_c=inp.fc, b_eff=inp.deck_eff_width, t_s=inp.deck_thickness,
            demand_force=bottom.design_force)
        sc.name = "composite slab crushing"
        bottom.checks.append(sc)

    return SpliceDesign(factored_moments=m, factored_shears=v,
                        top_flange=top, bottom_flange=bottom, web=web)
