#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Rolled-girder + field-splice optimizer (stage **B5** -- "a better design").

Sweeps candidate rolled shapes and, for each, (1) checks the girder carries the
span's governing factored moment (φ·Mp = φ·Fy·Zx, the compact-shape plastic
moment -- a conservative gate that ignores the extra composite capacity), and
(2) auto-sizes the flange/web splice plates and designs the bolted field splice
with the ODOT/NSBA method.  Feasible shapes (girder OK **and** splice OK) are
ranked by total cost -- girder steel weight plus splice fabrication/erection --
so the lightest adequate design surfaces, to compare against the as-built.

Cost model (all parameters overridable): steel at ``$/lb`` over the girder
length, plus per-bolt ``$fab`` fabrication and ``field_min`` erection minutes at
``$/min``.  The absolute dollars are illustrative; the *ranking* is the point.

This is the splice-region optimizer; a full B5 also folds in Service II,
fatigue, 6.10.2 proportion, and deflection limit states and lets the section
vary between splice pieces -- built on this same sweep."""

from __future__ import annotations

from dataclasses import dataclass


def weight_lb_ft(label: str) -> float:
    """Nominal weight (lb/ft) of an AISC shape from ``steel.W`` (falls back to
    the trailing number in the label, which *is* the nominal weight)."""
    from civilpy.structural import steel
    try:
        return float(steel.W(label).weight.to("pound/foot").magnitude)
    except Exception:
        return float(label.upper().split("X")[-1])


def girder_plastic_moment(label: str, f_y: float = 50.0) -> float:
    """Plastic moment capacity ``Mp = Fy*Zx`` (kip-ft) of a rolled shape."""
    from civilpy.structural import steel
    z_x = float(steel.W(label).Z_x.to("inch**3").magnitude)
    return f_y * z_x / 12.0


def auto_splice_plates(left_label: str, right_label: str,
                       grade: str = "Grade 50", *, weld_size: float = 0.3125):
    """Proportion the flange (``PlatePair``) and web (``WebPlate``) splice plates
    for a shape pair using the NSBA sizers + the AISC geometry."""
    from civilpy.structural import steel
    from civilpy.structural.aashto.lrfd import PlatePair, WebPlate
    from civilpy.structural.aashto.lrfd.splices import (
        size_flange_splice_plates, size_web_splice_plate,
    )
    left, right = steel.W(left_label), steel.W(right_label)

    def _in(q):
        return float(q.to("inch").magnitude)

    tf_gov = max(_in(left.flange_thickness), _in(right.flange_thickness))
    fp = size_flange_splice_plates(
        _in(left.flange_width), _in(right.flange_width), tf_gov,
        _in(left.web_thickness), _in(right.web_thickness), weld_size=weld_size)
    if fp.inner_width <= 0:
        raise ValueError(f"{left_label}: flange too narrow for inner plates")
    plates = PlatePair(grade, fp.inner_thickness, fp.inner_width,
                       fp.outer_thickness, fp.outer_width, 2)
    web_depth = min(_in(left.depth) - 2 * _in(left.flange_thickness),
                    _in(right.depth) - 2 * _in(right.flange_thickness))
    clearance = max(_in(left.k_design), _in(right.k_design))
    wp = size_web_splice_plate(web_depth, _in(left.web_thickness),
                               _in(right.web_thickness),
                               flange_clearance=clearance)
    return plates, WebPlate(grade, wp.thickness, 2)


def _search_feasible_splice(shape, loads, *, grade, deck_thickness,
                            deck_eff_width, rebar_area, deck_fc, bolts,
                            design_year):
    """Find the fewest-bolt splice design for a uniform ``shape`` girder that
    passes every check, by growing the web plate thickness, web bolt columns,
    and flange plate thickness within bounded steps.  Returns the passing
    :class:`SpliceDesign`, or the last (failing) one if none passes."""
    from civilpy.structural.aashto.lrfd import PlatePair, WebPlate
    from civilpy.structural.aashto.lrfd.composite import design_rolled_splice

    base_plates, base_web = auto_splice_plates(shape, shape, grade)
    last = None
    # prefer fewer web columns (cheaper), then thicker plates as needed
    for web_rows in (4, 5, 6):
        for web_t in (base_web.thickness, 0.375, 0.4375, 0.5, 0.5625):
            if web_t < base_web.thickness - 1e-9:
                continue
            for bump in (0.0, 0.0625, 0.125):
                plates = PlatePair(
                    grade, base_plates.inner_thickness + bump,
                    base_plates.inner_width,
                    base_plates.outer_thickness + bump,
                    base_plates.outer_width, 2)
                d = design_rolled_splice(
                    shape, shape, loads, grade=grade,
                    deck_thickness=deck_thickness, deck_eff_width=deck_eff_width,
                    rebar_area=rebar_area, deck_fc=deck_fc, bolts=bolts,
                    top_plates=plates, bottom_plates=plates,
                    web_plate=WebPlate(grade, web_t, 2),
                    top_flange_rows=2, bottom_flange_rows=2, web_rows=web_rows,
                    bolt_spacing=3.0, flange_edge=1.5, flange_end=1.5,
                    web_edge=1.5, web_end=1.5, design_year=design_year)
                last = d
                if d.ok:
                    return d
    return last


@dataclass
class GirderOption:
    """One candidate shape's feasibility + cost."""
    shape: str
    weight_lb_ft: float
    steel_lb: float
    total_bolts: int
    steel_cost: float
    splice_cost: float
    total_cost: float
    girder_ok: bool
    splice_ok: bool

    @property
    def ok(self) -> bool:
        return self.girder_ok and self.splice_ok


def optimize_splice_shape(loads, candidates, *, length_ft: float,
                          max_factored_moment: float, deck_thickness: float,
                          deck_eff_width: float, rebar_area: float = 0.0,
                          deck_fc: float = 4.0, grade: str = "Grade 50",
                          f_y: float = 50.0, bolt_dia: float = 0.875,
                          steel_cost_per_lb: float = 1.5, bolt_fab: float = 20.0,
                          field_min_per_bolt: float = 10.0,
                          labor_per_min: float = 1.5, design_year: int = 2016):
    """Sweep ``candidates`` (uniform-shape girders) and return a list of
    :class:`GirderOption`, ranked feasible-first then by ``total_cost``.

    ``loads`` is the unfactored splice demand; ``max_factored_moment`` is the
    girder's governing Strength I moment (from the envelope) used for the
    plastic-moment gate.  Shapes whose flanges are too narrow to splice are
    skipped.
    """
    from civilpy.structural.aashto.lrfd import BoltSpec
    from civilpy.structural.aashto.lrfd.composite import design_rolled_splice

    bolt_cost = bolt_fab + field_min_per_bolt * labor_per_min
    bolts = BoltSpec("A325", bolt_dia, flange_threads_excluded=False,
                     web_threads_excluded=False, surface_class="C",
                     hole_type="oversize")
    options = []
    for shape in candidates:
        girder_ok = girder_plastic_moment(shape, f_y) >= max_factored_moment
        try:
            d = _search_feasible_splice(
                shape, loads, grade=grade, deck_thickness=deck_thickness,
                deck_eff_width=deck_eff_width, rebar_area=rebar_area,
                deck_fc=deck_fc, bolts=bolts, design_year=design_year)
        except Exception:
            continue
        if d is None:
            continue
        n_bolts = sum(c.total_bolts for c in d.components)
        w = weight_lb_ft(shape)
        steel_lb = w * length_ft
        steel_cost = steel_lb * steel_cost_per_lb
        splice_cost = n_bolts * bolt_cost
        options.append(GirderOption(
            shape=shape, weight_lb_ft=w, steel_lb=steel_lb,
            total_bolts=n_bolts, steel_cost=steel_cost, splice_cost=splice_cost,
            total_cost=steel_cost + splice_cost, girder_ok=girder_ok,
            splice_ok=d.ok))
    options.sort(key=lambda o: (not o.ok, o.total_cost))
    return options


def cheapest_feasible(options):
    """The lowest-cost fully-feasible :class:`GirderOption`, or ``None``."""
    return next((o for o in options if o.ok), None)
