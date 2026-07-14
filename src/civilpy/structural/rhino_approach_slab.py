#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""BrIM emit for the ODOT AS-1-15 reinforced concrete approach slab.

Turns an :class:`~civilpy.structural.odot.approach_slab.ApproachSlabInput`
into *tagged, transport-neutral* geometry records (the
:class:`~civilpy.structural.rhino_bim.EmitObject` vocabulary): the slab
solid, its plan outline, and every reinforcing bar the sheet schedules
(A, B501, C, and the D801/D802 anchor bars), each carrying ``bim.*`` /
``pay.*`` / ``mat.*`` / ``rebar.*`` user text on the human-readable
``Deck::Approach Slab`` layers.  All engineering content comes from
:func:`~civilpy.structural.odot.approach_slab.layout_approach_slab`;
this module only places and tags it.

Pay measurement follows the sheet: the slab prism carries the ITEM 526
plan-area quantity (sy) — that item *includes* the slab reinforcing, so
the A/B/C bars carry full ``rebar.*`` metadata (size, diameter, weight,
length) but **no pay block** (they would double-count the 526 area).
The D801/D802 anchor bars are the exception the sheet calls out ("paid
under Item 509"): each carries the ITEM 509 epoxy-reinforcing pay block
with its tabulated bar length (hooks included, even though hooks are not
drawn).  Every bar's ``rebar.dia_in`` / ``rebar.weight_plf`` ride along
so downstream BIM functions (clash checks, takeoffs) have real diameters
to work with.

Placement — the station/offset contract
---------------------------------------
An approach slab exists at an abutment of a bridge on a roadway
alignment, so the emit places the layout's local frame from:

``alignment`` + ``station_ft``
    A :class:`~civilpy.transportation.alignment.Alignment`; ``station_ft``
    is the **bridge-limit station** (the rear face of backwall / end of
    bridge line on the roadway centerline).  Top of slab sits at the
    profile elevation at that station (the slab is placed rigid; it does
    not follow grade or superelevation along its length).
``offset_ft``
    Transverse offset of the **slab center** from the alignment
    centerline (right positive, the roadway convention).  The width
    always builds symmetrically about that center, so ``offset_ft = 0``
    centers the slab on the roadway centerline.
``side``
    ``"near"`` — the abutment at the low-station end: the slab occupies
    stations *below* the bridge limit (you drive across it, then onto
    the bridge).  ``"far"`` — the high-station end: the slab occupies
    stations above the bridge limit.  The far slab is the near slab
    rotated 180 degrees about the placement point, which keeps the
    anchor bars at the bridge end and keeps both bridge-limit lines
    parallel for the same ``skew_deg`` input.

With no alignment the emit places the same frames on a default
due-north tangent through the origin (bridge limit at (0, 0, 0),
stations increasing along +Y, transverse along +X) — matching the
:class:`Alignment` bearing convention, so in Rhino the *Front* viewport
looks up-station at the slab end (width across the screen) and *Right*
shows the longitudinal section.

The record draws through the AS-1-15 Grasshopper component,
``Notebooks/Rhino Components/draw_bim_emit.py``, and
:func:`~civilpy.structural.rhino_bim.emit_to_3dm`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from civilpy.structural import bim
from civilpy.structural.odot.approach_slab import (
    ApproachSlabInput,
    ApproachSlabLayout,
    CONCRETE_STRENGTH_PSI,
    REVISION,
    SCD,
    b501_length_ft,
    layout_approach_slab,
)
from civilpy.structural.rhino_bim import EmitObject, Point
from civilpy.structural.rhino_layers import (
    LAYER_APPROACH_SLAB,
    LAYER_APPROACH_SLAB_REBAR,
)

SIDES = ("near", "far")


@dataclass(frozen=True)
class ApproachSlabEmit:
    """One placed approach slab — duck-compatible with
    :func:`~civilpy.structural.rhino_bim.emit_to_json`,
    :func:`~civilpy.structural.rhino_bim.emit_to_3dm`, and
    :func:`~civilpy.structural.rhino_bim.pay_item_quantities`."""

    layout: ApproachSlabLayout
    side: str
    objects: tuple[EmitObject, ...]
    doc_tags: dict[str, str] = field(default_factory=dict)


class _Frame:
    """The rigid placement frame: local (u, e, z) -> global (x, y, z).

    ``u`` is the layout's longitudinal coordinate (away from the bridge),
    ``e`` the transverse coordinate measured from the slab center.  For
    the near abutment the local frame is rotated 180 degrees in plan
    (``sgn = -1``), so ``u`` runs down-station and the anchor bars stay
    at the bridge limit."""

    def __init__(self, alignment, station_ft, offset_ft: float, sgn: float):
        if alignment is None:
            self.origin = (0.0, 0.0, 0.0)
            self.t = (0.0, 1.0)          # due north, the Alignment default
            self.r = (1.0, 0.0)
        else:
            f = alignment.frame_at(station_ft)
            self.origin = f["point"]
            self.t = f["tangent"]
            self.r = f["right"]
        self.offset = offset_ft
        self.sgn = sgn

    def point(self, u: float, e: float, z: float) -> Point:
        x0, y0, z0 = self.origin
        du = self.sgn * u
        de = self.sgn * e + self.offset
        return (x0 + du * self.t[0] + de * self.r[0],
                y0 + du * self.t[1] + de * self.r[1], z0 + z)

    def vector(self, du: float, de: float) -> Point:
        du, de = self.sgn * du, self.sgn * de
        return (du * self.t[0] + de * self.r[0],
                du * self.t[1] + de * self.r[1], 0.0)


def approach_slab_emit(inp: ApproachSlabInput, *, side: str = "near",
                       alignment=None, station_ft: float | None = None,
                       offset_ft: float = 0.0,
                       scd_year: int | str = 2015) -> ApproachSlabEmit:
    """Build the tagged BrIM geometry for one AS-1-15 approach slab.

    See the module docstring for the ``side`` / ``alignment`` /
    ``station_ft`` / ``offset_ft`` placement contract.  Raises
    ``ValueError`` for an unknown side, an alignment without a station,
    or whatever :func:`layout_approach_slab` raises for inputs outside
    the drawing's assumptions.
    """
    if side not in SIDES:
        raise ValueError(f"side must be one of {SIDES}, not {side!r}")
    if alignment is not None and station_ft is None:
        raise ValueError("placing on an alignment requires station_ft "
                         "(the bridge-limit station)")

    layout = layout_approach_slab(inp)
    design = layout.design
    W = inp.width_ft
    frame = _Frame(alignment, station_ft, offset_ft,
                   1.0 if side == "far" else -1.0)

    def place(p: Point) -> Point:
        return frame.point(p[0], p[1] - W / 2.0, p[2])

    objects: list[EmitObject] = []

    # ── slab solid: section profile swept across the (skewed) width ──────
    tan_skew = math.tan(math.radians(inp.skew_deg))
    profile_loop = tuple(frame.point(u, -W / 2.0, z)
                         for u, z in layout.profile)
    objects.append(EmitObject(
        kind="prism", layer=LAYER_APPROACH_SLAB, points=profile_loop,
        vector=frame.vector(W * tan_skew, W),
        tags=bim.approach_slab_tags(
            "APS-SLAB", SCD, scd_year=scd_year, length_ft=design.length_ft,
            width_ft=W, thickness_in=design.thickness_in,
            skew_deg=inp.skew_deg, fc_psi=CONCRETE_STRENGTH_PSI,
            area_sy=layout.pay_area_sy)))

    # plan outline at top of slab (display/reference; no pay block)
    objects.append(EmitObject(
        kind="polyline", layer=LAYER_APPROACH_SLAB,
        points=tuple(place(p) for p in layout.outline)
        + (place(layout.outline[0]),),
        tags={"bim.type": "approach_slab_outline", "bim.id": "APS-OUTLINE",
              "bim.scd": SCD}))

    # ── reinforcing: every scheduled bar, with real diameters ─────────────
    # ITEM 526 includes the slab bars, so only the anchor bars carry pay.
    lengths = {design.a_bar_mark: design.a_bar_length_ft,
               design.c_bar_mark: design.c_bar_length_ft,
               "B501": b501_length_ft(W, inp.skew_deg),
               layout.anchor_mark: layout.anchor_length_ft}
    counters: dict[str, int] = {}
    for bar in layout.bars:
        n = counters[bar.mark] = counters.get(bar.mark, 0) + 1
        anchor = bar.mark == layout.anchor_mark
        tags = bim.rebar_tags(
            f"APS-{bar.mark}-{n}", size=bar.size, coating="epoxy",
            mat="approach_slab", bend=bar.mark if anchor else "straight",
            length_ft=lengths[bar.mark], scd=SCD)
        tags["rebar.mark"] = bar.mark
        if not anchor:
            tags = {k: v for k, v in tags.items()
                    if not k.startswith("pay.")}
        objects.append(EmitObject(
            kind="polyline", layer=LAYER_APPROACH_SLAB_REBAR,
            points=tuple(place(p) for p in bar.points), tags=tags))

    doc_tags = {
        "bim.scd": SCD, "bim.scd_rev": REVISION,
        "bim.scd_year": str(scd_year), "bim.units": "ft",
        "aps.side": side,
        "aps.length_ft": f"{design.length_ft:g}",
        "aps.width_ft": f"{W:g}",
        "aps.skew_deg": f"{inp.skew_deg:g}",
        "aps.offset_ft": f"{offset_ft:g}",
    }
    if station_ft is not None:
        doc_tags["aps.station_ft"] = f"{station_ft:g}"

    return ApproachSlabEmit(layout=layout, side=side,
                            objects=tuple(objects), doc_tags=doc_tags)
