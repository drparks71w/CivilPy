#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT AS-2-15 Approach Slab Installation — the drawable subset.

Transcribed from Ohio DOT Standard Construction Drawing **AS-2-15**
(revised 01-20-2023, 14 sheets).  The drawing remains the controlling
document.

AS-2-15 covers how the AS-1-15 approach slab meets the roadway: the
**reinforced concrete sleeper slab** under the approach-slab/pavement
joint (Type A and Type C installations), the 25-foot flexible pavement
transition, underdrains, and the joint systems.  The sleeper slab is the
parametric geometry this module generates; the fourteen installation
configurations are cataloged as data (``INSTALLATION_INDEX``).  Type B
has **no** sleeper slab — it uses a reinforced joint mesh measured by the
square yard.

Design basis (sheet 14): AASHTO LRFD (2014) + ODOT BDM (2007); HL-93;
FWS 0.060 ksf; concrete f'c = 4.5 ksi; fy = 60 ksi.  The sleeper slab is
measured by the linear foot along the skew at the end of the approach
slab and placed parallel to that skew.

Conventions match :mod:`civilpy.structural.odot.approach_slab`: X along
stations (increasing away from the bridge), Y transverse, Z up; feet in
plan, inches for section dimensions.  The layout origin sits on the
sleeper slab centerline (directly under the approach-slab/pavement
joint) at the y = 0 edge, with z = 0 at the TOP of the sleeper slab.
"""

import math
from dataclasses import dataclass, field

Point = tuple[float, float, float]  # (x, y, z) feet

SCD = "AS-2-15"
REVISION = "01-20-2023"

# ── design data (sheet 14) ───────────────────────────────────────────────

CONCRETE_STRENGTH_KSI = 4.5
REBAR_YIELD_KSI = 60.0
FUTURE_WEARING_SURFACE_KSF = 0.060
LIVE_LOAD = "HL-93"

# ── sleeper slab (sheet 1, section A-A; identical on the type C sheets) ──

SLEEPER_WIDTH_FT = 8.0        # 4'-0" each side of the joint
SLEEPER_THICKNESS_IN = 9.0
SLEEPER_COVER_IN = 3.0        # 3 in clear, typ.
SS501_COUNT = 8               # 8 - SS501 @ 1'-0" = 7'-0", 6 in edges
SS501_SPACING_IN = 12.0
SS501_EDGE_IN = 6.0
SS502_SPACING_MAX_IN = 12.0   # parallel to CL roadway, perp. spacing
SIDE_COVER_TOTAL_FT = 0.5     # SS501 length A = (W - 0.5)/cos(theta)
SS502_LENGTH_BASE_FT = 7.5    # SS502 length B = 7.5/cos(theta)
BAR_SIZE = 5                  # SS5xx marks
STAGE_LAP_SPLICE_FT = 2.5     # 2'-6" SS501 lap at longitudinal joints

# Drainage (sheet 1 plan/elevation + section A-A).
UNDERDRAIN_PIPE_DIA_IN = 6.0      # perforated, CMS 707.31 / 605.03
UNDERDRAIN_TRENCH_WIDTH_IN = 15.0  # 1'-3" beyond the pavement-side edge
UNDERDRAIN_TRENCH_DEPTH_IN = 10.0
AGGREGATE_DRAIN_WIDTH_FT = 2.0     # centered on the sleeper centerline
AGGREGATE_DRAIN_DEPTH_FT = 1.0     # CMS 605.07

# Joint over the sleeper (note 11): 20 in x 3 in polymer modified asphalt
# joint system (SS 846) when the plans carry the pay item, else the
# AS-1-15 sheet 2/2 detail C joint sealer.
PMA_JOINT_WIDTH_IN = 20.0
PMA_JOINT_THICKNESS_IN = 3.0

FLEXIBLE_PAVEMENT_LENGTH_FT = 25.0   # the transition pavement (T2)


# ── installation catalog (sheet 1 index + sheet 14 notes) ────────────────

@dataclass(frozen=True)
class Installation:
    """One AS-2-15 installation configuration."""

    type: str                # "A" | "B" | "C"
    sheets: tuple[int, ...]
    wall: str                # abutment/wall condition
    pavement: str            # "flexible" | "rigid" | "flexible or rigid"
    has_sleeper_slab: bool
    joint: str


INSTALLATION_INDEX: tuple[Installation, ...] = (
    Installation("A", (1, 2), "cast-in-place turnback wingwalls "
                 "(jointless or jointed superstructure)", "flexible",
                 True, "polymer modified asphalt joint system (SS 846) "
                 "or AS-1-15 detail C joint sealer"),
    Installation("B", (3,), "any", "flexible", False,
                 "reinforced joint mesh (measured by SY along the skew)"),
    Installation("B", (4,), "any", "rigid", False,
                 "reinforced joint mesh (measured by SY along the skew)"),
    Installation("C", (6, 7, 8), "MSE walls", "flexible", True,
                 "armorless preformed joint seal"),
    Installation("C", (9, 10, 11), "cast-in-place turnback wingwalls",
                 "flexible", True, "armorless preformed joint seal"),
    Installation("C", (12,), "MSE walls", "rigid", True,
                 "armorless preformed joint seal"),
    Installation("C", (13,), "cast-in-place turnback wingwalls", "rigid",
                 True, "armorless preformed joint seal"),
)


def installations(type_: str) -> tuple[Installation, ...]:
    """All cataloged configurations of the given installation type."""
    found = tuple(i for i in INSTALLATION_INDEX if i.type == type_)
    if not found:
        raise ValueError(
            "AS-2-15 installation types are 'A', 'B', and 'C', "
            f"not {type_!r}")
    return found


def ss501_length_ft(width_ft: float, skew_deg: float = 0.0) -> float:
    """SS501 length A = (W - 0.5')/cos(theta) (sheet 1 bending table)."""
    return ((width_ft - SIDE_COVER_TOTAL_FT)
            / math.cos(math.radians(skew_deg)))


def ss502_length_ft(skew_deg: float = 0.0) -> float:
    """SS502 length B = 7.5'/cos(theta) (sheet 1 bending table)."""
    return SS502_LENGTH_BASE_FT / math.cos(math.radians(skew_deg))


def ss502_count(width_ft: float) -> int:
    """SS502 bars at 1'-0" max, measured perpendicular to CL roadway,
    across the (W - 0.5) bar band — spaces rounded up."""
    if width_ft <= SIDE_COVER_TOTAL_FT:
        raise ValueError("approach slab width must exceed 0.5 ft")
    spaces = 12.0 * (width_ft - SIDE_COVER_TOTAL_FT) / SS502_SPACING_MAX_IN
    return int(math.ceil(spaces - 1e-9)) + 1


# ── layout ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SleeperSlabInput:
    """Inputs for a Type A / Type C sleeper slab: the approach slab width
    it supports and the skew it parallels."""

    width_ft: float
    skew_deg: float = 0.0
    installation: str = "A"


@dataclass(frozen=True)
class BarRun:
    mark: str
    size: int
    points: tuple[Point, ...]


@dataclass(frozen=True)
class SleeperSlabLayout:
    """The generated sleeper slab.  ``outline`` is the counterclockwise
    plan parallelogram at z = 0 (top of sleeper); the solid extends down
    ``SLEEPER_THICKNESS_IN``.  ``underdrain`` is the pipe centerline;
    ``pma_joint`` is the joint-system outline sitting on the sleeper top
    over the centerline, and ``aggregate_drain`` the trench outline
    below the slab."""

    inputs: SleeperSlabInput
    outline: tuple[Point, Point, Point, Point]
    thickness_in: float
    bars: tuple[BarRun, ...]
    underdrain: tuple[Point, Point]
    pma_joint: tuple[Point, Point, Point, Point]
    aggregate_drain: tuple[Point, Point, Point, Point]
    measured_length_ft: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_sleeper_slab(inp: SleeperSlabInput) -> SleeperSlabLayout:
    """Generate the sleeper slab under the approach-slab/pavement joint.

    Raises ``ValueError`` for a Type B installation (no sleeper slab),
    an unknown type, or out-of-range width/skew."""
    if inp.installation not in ("A", "B", "C"):
        raise ValueError(
            "AS-2-15 installation types are 'A', 'B', and 'C', "
            f"not {inp.installation!r}")
    if inp.installation == "B":
        raise ValueError(
            "Type B installation has no reinforced concrete sleeper slab "
            "(it uses a reinforced joint mesh; see AS-2-15 sheets 3-5)")
    if inp.width_ft <= SIDE_COVER_TOTAL_FT:
        raise ValueError("approach slab width must exceed 0.5 ft")
    if abs(inp.skew_deg) >= 60.0:
        raise ValueError("skew beyond 60 degrees is not supported")

    from civilpy.structural.steel import Rebar

    W = inp.width_ft
    tan_skew = math.tan(math.radians(inp.skew_deg))
    cos = math.cos(math.radians(inp.skew_deg))
    # The 8 ft sleeper width and its 12 in bar spacings are true
    # (perpendicular to the skewed centerline) dimensions — that is what
    # makes SS502's tabulated length (8 - 0.5)/cos(theta); longitudinal
    # extents therefore stretch by sec(theta).
    half = SLEEPER_WIDTH_FT / 2.0 / cos
    t_ft = SLEEPER_THICKNESS_IN / 12.0

    def pt(u: float, y: float, z: float) -> Point:
        return (u + y * tan_skew, y, z)

    outline = (pt(-half, 0.0, 0.0), pt(-half, W, 0.0),
               pt(half, W, 0.0), pt(half, 0.0, 0.0))

    db = float(Rebar(BAR_SIZE).diameter.magnitude)
    z_501 = -(SLEEPER_THICKNESS_IN - SLEEPER_COVER_IN - db / 2.0) / 12.0
    z_502 = z_501 + db / 12.0   # tied on top of the SS501 layer

    bars: list[BarRun] = []
    # SS501: 8 bars parallel to the sleeper centerline (the skew), on
    # true 12 in centers with 6 in edges.
    ya, yb = 0.25, W - 0.25
    for i in range(SS501_COUNT):
        n_off = -SLEEPER_WIDTH_FT / 2.0 + SS501_EDGE_IN / 12.0 \
            + i * SS501_SPACING_IN / 12.0
        u = n_off / cos
        bars.append(BarRun("SS501", BAR_SIZE,
                           (pt(u, ya, z_501), pt(u, yb, z_501))))
    # SS502: parallel to CL roadway, spaced <= 12 in perpendicular to it;
    # the bar's plan run equals its tabulated length B = 7.5/cos(theta).
    n2 = ss502_count(W)
    u_run = ss502_length_ft(inp.skew_deg) / 2.0
    for i in range(n2):
        frac = i / (n2 - 1) if n2 > 1 else 0.5
        y = 0.25 + frac * (W - SIDE_COVER_TOTAL_FT)
        bars.append(BarRun("SS502", BAR_SIZE,
                           (pt(-u_run, y, z_502), pt(u_run, y, z_502))))

    # Underdrain: 6 in perforated pipe centered in the 1'-3" x 10 in
    # trench along the pavement-side edge of the sleeper slab.
    pipe_u = (SLEEPER_WIDTH_FT / 2.0
              + UNDERDRAIN_TRENCH_WIDTH_IN / 24.0) / cos
    pipe_z = -(t_ft + UNDERDRAIN_TRENCH_DEPTH_IN / 12.0
               - UNDERDRAIN_PIPE_DIA_IN / 24.0)
    underdrain = (pt(pipe_u, 0.0, pipe_z), pt(pipe_u, W, pipe_z))

    # Polymer modified asphalt joint: 20 in x 3 in centered over the CL.
    jw = PMA_JOINT_WIDTH_IN / 24.0 / cos
    pma = (pt(-jw, 0.0, 0.0), pt(-jw, W, 0.0),
           pt(jw, W, 0.0), pt(jw, 0.0, 0.0))

    # Aggregate drain: 2'-0" wide x 1'-0" deep, centered on the CL,
    # directly below the sleeper slab.
    dw = AGGREGATE_DRAIN_WIDTH_FT / 2.0 / cos
    agg = (pt(-dw, 0.0, -t_ft), pt(-dw, W, -t_ft),
           pt(dw, W, -t_ft), pt(dw, 0.0, -t_ft))

    # measured by the linear foot along the skew, full slab width
    measured = W / cos

    notes = (
        f"Type {inp.installation} installation: sleeper slab "
        f"{SLEEPER_WIDTH_FT:g} ft x {SLEEPER_THICKNESS_IN:g} in, parallel "
        f"to the {inp.skew_deg:g} deg skew",
        f"SS501: {SS501_COUNT} x {ss501_length_ft(W, inp.skew_deg):.2f} ft; "
        f"SS502: {n2} x {ss502_length_ft(inp.skew_deg):.2f} ft (#5)",
        "Not modeled: 25 ft flexible pavement transition and thickness "
        "tapers, bond breaker, aggregate-drain outlets (DM-4.1), pipe "
        "outlet details (DM-1.1/1.2), MSE-wall / turnback-wingwall "
        "variations, Type B reinforced joint mesh.",
    )

    return SleeperSlabLayout(
        inputs=inp,
        outline=outline,
        thickness_in=SLEEPER_THICKNESS_IN,
        bars=tuple(bars),
        underdrain=underdrain,
        pma_joint=pma,
        aggregate_drain=agg,
        measured_length_ft=measured,
        notes=notes,
    )
