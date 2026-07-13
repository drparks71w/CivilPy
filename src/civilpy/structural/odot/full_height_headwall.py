#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT full-height headwalls (HW-1.1).

Transcribed from Ohio DOT Standard Bridge Drawing **HW-1.1**, "Full-Height
Headwalls" (rev. 07-18-2025, 2 sheets).  The drawing remains the controlling
document.

HW-1.1 covers full-height headwalls with wingwalls for circular pipe or
pipe-arch culverts, 42 to 84 in inclusive, skewed or non-skewed.  **Type A**
(``skew_deg <= 10``) uses a wingwall symmetrical about the culvert
centerline, flared 45 deg each side; **Type B** (``skew_deg > 10``) uses an
asymmetric pair of wingwalls flared ``45 - skew/2`` and ``45 + skew/2`` deg
off the culvert centerline (sheet 1 plan views).  The dimension table
(sheet 2) tabulates quantities at four discrete skew angles (0, 15, 30,
45 deg); intermediate skews use the nearest tabulated bucket, which is
standard ODOT practice for this drawing (its own title reads "theta ~=").

Design basis (sheet 1 notes): internal friction angle of backfill soil
phi_bf = 30 deg, backfill unit weight = 120 pcf, foundation soil drained
friction angle phi_f = 28 deg, foundation undrained shear strength = 1500
psf, concrete unit weight = 150 pcf, backfill slope = 2:1.  Concrete Class
QC1 (f'c = 4000 psi).  Reinforcing steel ASTM A615/A616/A617 Grade 60,
epoxy coated.

Conventions match :mod:`civilpy.structural.odot.headwall`: X along the
culvert/wall centerline is not used here -- instead Y is along the
headwall face (wingwall spread direction), X is out from the culvert
centerline (positive downstream), Z is up with z = 0 at the flow line /
wall base.  Feet in plan, inches only where the sheet itself uses them
(pipe diameter, chamfer, weepholes).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "HW-1.1"
REVISION = "07-18-2025"

# ── design data (sheet 1 notes) ──────────────────────────────────────────

BACKFILL_FRICTION_ANGLE_DEG = 30.0        # phi_bf
BACKFILL_UNIT_WEIGHT_PCF = 120.0
FOUNDATION_FRICTION_ANGLE_DEG = 28.0       # phi_f, drained
FOUNDATION_UNDRAINED_SHEAR_STRENGTH_PSF = 1500.0
CONCRETE_UNIT_WEIGHT_PCF = 150.0
BACKFILL_SLOPE = 2.0                       # 2:1 (H:V)
CONCRETE_CLASS = "QC1"
CONCRETE_STRENGTH_PSI = 4000.0
REBAR_SPEC = "ASTM A615, A616, or A617 Grade 60 (epoxy coated)"
REBAR_YIELD_KSI = 60.0
CHAMFER_IN = 0.75                          # exposed corners
WEEPHOLE_DIA_IN = 4.0
WEEPHOLE_MIN_SPACING_FT = 6.0
WEEPHOLE_MAX_SPACING_FT = 10.0
POROUS_BACKFILL_THICKNESS_IN = 18.0        # 1'-6", behind wingwalls only
SKEW_TYPE_A_MAX_DEG = 10.0                 # Type A (symmetric) at/below this

#: Applicable pipe diameter/rise range (sheet 1 "APPLICATION" note).
MIN_DIAMETER_IN = 42.0
MAX_DIAMETER_IN = 84.0

#: The dimension table only tabulates quantities at these nominal skew
#: angles; ``nearest_skew_bucket`` snaps any input to the closest one.
SKEW_BUCKETS: tuple[float, ...] = (0.0, 15.0, 30.0, 45.0)


def nearest_skew_bucket(skew_deg: float) -> float:
    """Snap a skew angle to the nearest tabulated bucket (0/15/30/45 deg).

    The 0 deg cutoff is pinned to :data:`SKEW_TYPE_A_MAX_DEG` (10 deg) --
    sheet 1's own Type A/B boundary -- rather than the halfway point (7.5
    deg) so a skew that the sheet calls Type A never gets Type B's
    asymmetric wingwall data; 15/30/45 split at their halfway points
    (22.5, 37.5) as plain nearest-neighbor.  Raises ``ValueError`` for a
    skew outside the table's range (sheet 1 tabulates through 45 deg
    only; beyond that the standard drawing does not apply)."""
    s = abs(skew_deg)
    if s > 52.5:
        raise ValueError(
            f"HW-1.1 tabulates skew through 45 deg; {skew_deg:g} deg is "
            "out of range")
    if s <= SKEW_TYPE_A_MAX_DEG:
        return 0.0
    if s <= 22.5:
        return 15.0
    if s <= 37.5:
        return 30.0
    return 45.0


def _fi(feet: int, inches: float) -> float:
    """``feet`` + ``inches`` (a sheet dimension like 5'-4") as decimal feet."""
    return feet + inches / 12.0


@dataclass(frozen=True)
class SkewGroup:
    """One skew-angle column of the HW-1.1 table for a given pipe diameter.

    ``L1``/``h1`` are ``None`` at ``skew_deg == 0`` (Type A: only one
    wingwall shape, tabulated as ``L2``/``h2``, symmetric about the
    centerline)."""

    skew_deg: float
    L1: float | None       # ft, plan length of the acute-side wingwall
    L2: float               # ft, plan length of the obtuse-side wingwall
    h1: float | None       # ft, wall height at the L1 wingwall's far end
    h2: float               # ft, wall height at the L2 wingwall's far end
    concrete_cmp_cy: float  # corrugated-metal-pipe quantity, CY
    concrete_rcp_cy: float  # reinforced-concrete-pipe quantity, CY
    steel_lb: float


@dataclass(frozen=True)
class FullHeightHeadwallDesign:
    """One HW-1.1 table row (a pipe diameter), with all four skew columns."""

    diameter_in: float
    height_ft: float    # H, headwall height at the culvert centerline
    a_ft: float          # a (half-section corner offset)
    b_ft: float          # b
    c_ft: float          # c (plan corner dimension, see PLAN VIEW TYPE B)
    ts_ft: float         # t_s, wingwall/slab thickness
    bar_size: int        # primary #d bar size (bent bar "D")
    skews: tuple[SkewGroup, ...]

    def skew(self, skew_deg: float) -> SkewGroup:
        """The tabulated column for the nearest skew bucket to ``skew_deg``."""
        bucket = nearest_skew_bucket(skew_deg)
        for s in self.skews:
            if s.skew_deg == bucket:
                return s
        raise AssertionError(f"no SkewGroup for bucket {bucket!r}")  # pragma: no cover


def _row(diameter_in, h, a, b, c, ts, bar,
         s0, s15, s30, s45) -> FullHeightHeadwallDesign:
    return FullHeightHeadwallDesign(
        diameter_in=diameter_in, height_ft=h, a_ft=a, b_ft=b, c_ft=c,
        ts_ft=ts, bar_size=bar,
        skews=(
            SkewGroup(0.0, None, s0[0], None, s0[1], s0[2], s0[3], s0[4]),
            SkewGroup(15.0, *s15),
            SkewGroup(30.0, *s30),
            SkewGroup(45.0, *s45),
        ),
    )


#: HW-1.1 "FULL-HEIGHT HEADWALLS (ENGLISH)" table, sheet 2, keyed by pipe
#: diameter (inches).  L/H columns in feet-inches on the sheet, converted
#: with :func:`_fi`; concrete in CY, steel in lbs.
FULL_HEIGHT_HEADWALLS: dict[float, FullHeightHeadwallDesign] = {
    42.0: _row(
        42.0, _fi(5, 4), _fi(3, 3), _fi(1, 6), _fi(2, 6), _fi(1, 6), 5,
        s0=(_fi(3, 7), _fi(3, 6), 7.2, 7.1, 695),
        s15=(_fi(8, 9), _fi(4, 6), _fi(4, 1), _fi(3, 7), 7.6, 7.5, 656),
        s30=(_fi(7, 10), _fi(5, 9), _fi(3, 7), _fi(3, 8), 7.8, 7.7, 688),
        s45=(_fi(7, 10), _fi(7, 9), _fi(3, 7), _fi(3, 8), 9.0, 8.9, 794),
    ),
    48.0: _row(
        48.0, _fi(5, 10), _fi(3, 6), _fi(1, 6), _fi(2, 9), _fi(1, 6), 5,
        s0=(_fi(4, 4), _fi(3, 9), 8.8, 8.6, 861),
        s15=(_fi(10, 0), _fi(5, 4), _fi(4, 6), _fi(3, 10), 9.3, 9.1, 806),
        s30=(_fi(8, 9), _fi(6, 10), _fi(3, 10), _fi(3, 11), 9.4, 9.2, 833),
        s45=(_fi(8, 9), _fi(9, 2), _fi(3, 10), _fi(4, 0), 10.9, 10.8, 970),
    ),
    54.0: _row(
        54.0, _fi(6, 5), _fi(3, 9), _fi(1, 6), _fi(3, 0), _fi(1, 6), 5,
        s0=(_fi(5, 2), _fi(4, 2), 10.8, 10.5, 1001),
        s15=(_fi(11, 4), _fi(6, 3), _fi(5, 0), _fi(4, 2), 11.3, 11.0, 977),
        s30=(_fi(9, 8), _fi(7, 11), _fi(4, 2), _fi(4, 3), 11.2, 11.0, 1002),
        s45=(_fi(9, 8), _fi(10, 7), _fi(4, 2), _fi(4, 4), 13.1, 12.9, 1149),
    ),
    60.0: _row(
        60.0, _fi(7, 0), _fi(4, 0), _fi(1, 6), _fi(3, 3), _fi(1, 6), 5,
        s0=(_fi(5, 11), _fi(4, 5), 12.7, 12.4, 1151),
        s15=(_fi(12, 7), _fi(7, 2), _fi(5, 4), _fi(4, 6), 13.4, 13.1, 1127),
        s30=(_fi(10, 7), _fi(9, 0), _fi(4, 4), _fi(4, 7), 13.2, 12.9, 1124),
        s45=(_fi(10, 7), _fi(12, 0), _fi(4, 4), _fi(4, 7), 15.4, 15.1, 1306),
    ),
    72.0: _row(
        72.0, _fi(8, 2), _fi(4, 6), _fi(1, 7), _fi(3, 9), _fi(1, 6), 7,
        s0=(_fi(7, 5), _fi(5, 0), 17.5, 17.1, 1808),
        s15=(_fi(15, 1), _fi(8, 11), _fi(6, 2), _fi(5, 1), 18.5, 18.0, 1803),
        s30=(_fi(12, 5), _fi(11, 2), _fi(4, 10), _fi(5, 2), 18.0, 17.5, 1770),
        s45=(_fi(12, 5), _fi(14, 10), _fi(4, 10), _fi(5, 3), 21.0, 20.6, 2080),
    ),
    84.0: _row(
        84.0, _fi(9, 4), _fi(5, 0), _fi(1, 10), _fi(4, 3), _fi(1, 6), 8,
        s0=(_fi(9, 0), _fi(5, 8), 24.6, 24.0, 2608),
        s15=(_fi(17, 7), _fi(10, 9), _fi(7, 0), _fi(5, 9), 25.7, 25.1, 2563),
        s30=(_fi(14, 7), _fi(13, 4), _fi(5, 6), _fi(5, 10), 25.1, 24.5, 2559),
        s45=(_fi(14, 3), _fi(17, 8), _fi(5, 4), _fi(5, 10), 28.9, 28.3, 2943),
    ),
}


def full_height_headwall_design(diameter_in: float) -> FullHeightHeadwallDesign:
    """Look up the HW-1.1 table row for a pipe diameter (inches).

    Raises ``ValueError`` naming the tabulated sizes if ``diameter_in`` is
    not one of them."""
    try:
        return FULL_HEIGHT_HEADWALLS[diameter_in]
    except KeyError:
        valid = sorted(FULL_HEIGHT_HEADWALLS)
        raise ValueError(
            f"HW-1.1 tabulates pipe diameters {valid} in, not "
            f"{diameter_in!r}") from None


# ── layout (Type A symmetric + Type B asymmetric wingwalls) ──────────────
#
# Drawable subset: the headwall+wingwall unit as a single hip-roofed solid
# -- a vertical face at the culvert centerline (width = pipe diameter D,
# height = the tabulated H) with two wingwall planes swept from its top
# edge, sloping down at the embankment's 2:1 grade to the tabulated height
# (h1 or h2) at the far end of each wingwall (tabulated length L1 or L2).
# Type A (skew <= 10 deg) is symmetric: both wingwalls use L2/h2, flared 45
# deg off the centerline. Type B splits the flare angle by the skew per
# sheet 1's "45 - theta/2" plan callout: the acute-side wingwall (L1/h1)
# flares at (45 - skew/2) deg, the obtuse-side wingwall (L2/h2) at
# (45 + skew/2) deg (assumption -- the sheet only labels one angle
# explicitly; see SCD_BUILD_QUESTIONS.md).  Wall thickness/batter (a, b, c,
# t_s), the footing, reinforcing, weepholes, and porous backfill are
# cataloged as data, not drawn.


@dataclass(frozen=True)
class HeadwallInput:
    """Inputs for a full-height headwall + wingwall solid.

    ``diameter_in`` must be a tabulated pipe diameter; ``skew_deg`` is
    snapped to the nearest tabulated bucket (0/15/30/45 deg -- see
    :func:`nearest_skew_bucket`)."""

    diameter_in: float
    skew_deg: float = 0.0


@dataclass(frozen=True)
class FullHeightHeadwallLayout:
    """The generated headwall+wingwall unit.

    ``center_face`` is the vertical rectangular panel at the culvert
    centerline (X-Z plane at y = 0, width D centered on x = 0, height H);
    ``wing1``/``wing2`` are the two wingwall planes as
    ``(near_top, near_base, far_base, far_top)`` quads swept from the
    center face's top corners out to each wingwall's far end.  ``wing1``
    is the acute-side (L1/h1) wingwall, ``wing2`` the obtuse-side (L2/h2)
    wingwall; for Type A (skew snapped to 0) both use the L2/h2 data and
    are mirror images.  Origin: x = 0 on the culvert centerline, y = 0 at
    the headwall front face (wall behind, +y downstream), z = 0 at the
    flow line / wall base."""

    inputs: HeadwallInput
    table: FullHeightHeadwallDesign
    skew: SkewGroup
    skew_bucket_deg: float
    type_: str    # "A" or "B"
    center_face: tuple[Point, Point, Point, Point]
    wing1: tuple[Point, Point, Point, Point]
    wing2: tuple[Point, Point, Point, Point]
    concrete_cy: float
    steel_lb: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def _wingwall_quad(H: float, D: float, side: float, angle_deg: float,
                   L: float, h: float) -> tuple[Point, Point, Point, Point]:
    """One wingwall plane: from the center face's top-side corner
    ``(side*D/2, 0, H)`` down/out along ``angle_deg`` off the centerline
    (measured from the +Y downstream axis, positive toward ``side``) to a
    far top corner at height ``h``, plan length ``L``.  ``side`` is +1 or
    -1 (which face-corner the wingwall springs from)."""
    near_top = (side * D / 2.0, 0.0, H)
    near_base = (side * D / 2.0, 0.0, 0.0)
    dx = L * math.sin(math.radians(angle_deg)) * side
    dy = L * math.cos(math.radians(angle_deg))
    far_base = (side * D / 2.0 + dx, dy, 0.0)
    far_top = (side * D / 2.0 + dx, dy, h)
    return (near_top, near_base, far_base, far_top)


def layout_full_height_headwall(
    inp: HeadwallInput,
) -> FullHeightHeadwallLayout:
    """Generate the full-height headwall + wingwall solid.

    Raises ``ValueError`` (via :func:`full_height_headwall_design`) for an
    untabulated pipe diameter, and (via :func:`nearest_skew_bucket`) for a
    skew beyond the table's 45 deg range."""
    table = full_height_headwall_design(inp.diameter_in)
    bucket = nearest_skew_bucket(inp.skew_deg)
    skew = table.skew(bucket)
    type_ = "A" if bucket <= SKEW_TYPE_A_MAX_DEG else "B"

    H = table.height_ft
    D = inp.diameter_in / 12.0

    center_face = ((-D / 2.0, 0.0, 0.0), (D / 2.0, 0.0, 0.0),
                  (D / 2.0, 0.0, H), (-D / 2.0, 0.0, H))

    if type_ == "A":
        wing1 = _wingwall_quad(H, D, -1.0, 45.0, skew.L2, skew.h2)
        wing2 = _wingwall_quad(H, D, 1.0, 45.0, skew.L2, skew.h2)
    else:
        wing1 = _wingwall_quad(H, D, -1.0, 45.0 - bucket / 2.0,
                               skew.L1, skew.h1)
        wing2 = _wingwall_quad(H, D, 1.0, 45.0 + bucket / 2.0,
                               skew.L2, skew.h2)

    concrete_cy = skew.concrete_rcp_cy  # RCP (reinforced concrete pipe) default
    notes = (
        f"HW-1.1 Type {type_} full-height headwall for {inp.diameter_in:g} "
        f"in pipe at skew ~= {bucket:g} deg (input {inp.skew_deg:g} deg): "
        f"H {table.height_ft:.2f} ft, #{table.bar_size} bars, "
        f"{skew.concrete_cmp_cy:g} CY (CMP) / {skew.concrete_rcp_cy:g} CY "
        f"(RCP), {skew.steel_lb:g} lb steel",
        "Not modeled: wingwall batter/thickness (a, b, c, t_s cataloged "
        "only), footing, reinforcing bar layout, weepholes, porous "
        "backfill, chamfers, pipe-arch geometry, and end treatment "
        "(rigid vs. corrugated pipe) details.",
    )

    return FullHeightHeadwallLayout(
        inputs=inp,
        table=table,
        skew=skew,
        skew_bucket_deg=bucket,
        type_=type_,
        center_face=center_face,
        wing1=wing1,
        wing2=wing2,
        concrete_cy=concrete_cy,
        steel_lb=skew.steel_lb,
        notes=notes,
    )
