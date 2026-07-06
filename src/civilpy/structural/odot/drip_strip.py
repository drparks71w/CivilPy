#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT DS-1-92 Drip Strip for Structures with Over the Side Drainage.

Transcribed from Ohio DOT Standard Construction Drawing **DS-1-92**
(revised 07-15-22, 2 sheets).  The drawing remains the controlling
document.

The drip strip is a bent stainless steel sheet cast into (or fastened to)
the fascia edge of the deck: a 4-1/2 in perforated plate is embedded
horizontally with a 3 in leg bent up 90 degrees against the formwork;
after form removal the leg is bent out to its final 45 degree position.
The **lower strip** runs continuously along the full length of each side
of the bridge (pieces tightly butted, never lapped); a short **upper
strip** (1'-6" for DBR-2-73 and TST-1-99 railings, 2'-0" for TST-2-21) is
added at each railing post, its leg turned up while the lower strip's leg
turns down.  On prestressed box beams without a cast deck the bent strips
are instead fastened to the beam edge with 1-1/4 in x 3/32 in button head
spikes with deformed shanks or expansion anchors at 1'-6" c/c max, all
devices galvanized or stainless.

Material: stainless steel, minimum 22 gage, ASTM A167 Type 304, mill
finish.  Measurement: by the foot, totaling upper and lower strips (pay
item "Special, Steel Drip Strip").

Conventions match the other SCD modules: plan lengths in feet, section
dimensions in inches.
"""

import math
from dataclasses import dataclass

SCD = "DS-1-92"
REVISION = "07-15-22"

# ── strip cross-section (sheet 2, sections H-H) ──────────────────────────

EMBED_WIDTH_IN = 4.5        # perforated plate cast into the deck edge
LEG_LENGTH_IN = 3.0         # free leg, formed up 90 deg, final 45 deg
FINAL_BEND_DEG = 45.0
MIN_GAGE = 22               # ASTM A167, Type 304, mill finish
GAGE_THICKNESS_IN = 0.031   # nominal 22-gage stainless sheet (display)

# Perforations in the embedded plate (sheet 2, view G-G).
HOLE_DIAMETER_IN = 1.5
HOLE_SPACING_IN = 4.0       # along each row
HOLE_ROW_STAGGER_IN = 2.0   # second row offset
HOLE_ROW_EDGE_IN = 1.5      # rows sit 1-1/2 in from each plate edge

# Box-beam fastening (sheet 1, diamond note).
SPIKE_LENGTH_IN = 1.25
SPIKE_SHANK_DIAMETER_IN = 3.0 / 32.0
FASTENER_SPACING_MAX_IN = 18.0

PAY_ITEM = "Special, Steel Drip Strip"


# ── railing-dependent data (sheet 2, views A-A .. F-F) ───────────────────

@dataclass(frozen=True)
class DripStripPlacement:
    """Upper-strip length and the strip root depth below the deck (or
    wearing) surface for one railing type."""

    railing: str
    upper_strip_length_in: float
    root_depth_in: float      # bend line below the concrete deck surface


PLACEMENTS: dict[str, DripStripPlacement] = {
    "DBR-2-73": DripStripPlacement("DBR-2-73", 18.0, 2.5),
    "TST-1-99": DripStripPlacement("TST-1-99", 18.0, 2.0),
    "TST-2-21": DripStripPlacement("TST-2-21", 24.0, 2.0),
}

#: Deck/structure families the sheet details (each shown with all three
#: railings; "deck on concrete or steel beam similar").
STRUCTURE_TYPES = ("concrete slab", "noncomposite box beam",
                   "composite box beam")


def placement(railing: str) -> DripStripPlacement:
    """Placement data for a railing type; raises ``ValueError`` listing
    the railings DS-1-92 details."""
    try:
        return PLACEMENTS[railing]
    except KeyError:
        raise ValueError(
            f"DS-1-92 details drip strips for railings "
            f"{sorted(PLACEMENTS)}, not {railing!r}"
        ) from None


def upper_strip_length_in(railing: str) -> float:
    return placement(railing).upper_strip_length_in


# ── section profile ──────────────────────────────────────────────────────

def strip_profile_in(kind: str, *, bent: bool = True,
                     include_embedded: bool = True
                     ) -> tuple[tuple[float, float], ...]:
    """Cross-section polyline of one strip, inches, in the (h, v) plane:
    h positive outward from the fascia face (h = 0 at the bend line),
    v positive up.

    ``kind`` is ``"upper"`` (leg turned up 45 degrees) or ``"lower"``
    (leg turned down).  ``bent=False`` gives the pre-placement shape (leg
    vertical against the form).  ``include_embedded=False`` returns only
    the exposed leg.
    """
    if kind not in ("upper", "lower"):
        raise ValueError("kind must be 'upper' or 'lower'")
    sign = 1.0 if kind == "upper" else -1.0
    if bent:
        a = math.radians(FINAL_BEND_DEG)
        tip = (LEG_LENGTH_IN * math.cos(a), sign * LEG_LENGTH_IN * math.sin(a))
    else:
        tip = (0.0, sign * LEG_LENGTH_IN)
    pts = ((0.0, 0.0), tip)
    if include_embedded:
        pts = ((-EMBED_WIDTH_IN, 0.0),) + pts
    return pts


def hole_centers_in(strip_length_in: float) -> list[tuple[float, float]]:
    """Perforation centers over a strip of the given length, in the
    embedded-plate plane: (s, w) with s along the strip from its start and
    w measured from the bend line into the deck (0 to EMBED_WIDTH_IN).

    Two staggered rows 1-1/2 in from each plate edge, 4 in c/c along each
    row, second row offset 2 in (view G-G)."""
    if strip_length_in <= 0:
        raise ValueError("strip length must be positive")
    rows = (
        (HOLE_ROW_EDGE_IN, HOLE_SPACING_IN / 2.0),        # near the bend
        (EMBED_WIDTH_IN - HOLE_ROW_EDGE_IN,
         HOLE_SPACING_IN / 2.0 + HOLE_ROW_STAGGER_IN),
    )
    r = HOLE_DIAMETER_IN / 2.0
    centers = []
    for w, s in rows:
        while s <= strip_length_in - r:
            if s >= r:
                centers.append((s, w))
            s += HOLE_SPACING_IN
    return centers


# ── runs along the fascia ────────────────────────────────────────────────

@dataclass(frozen=True)
class StripRun:
    """One strip piece along the fascia: stations in feet from the start
    of the run, plus which profile it carries."""

    kind: str            # "upper" | "lower"
    start_ft: float
    end_ft: float

    @property
    def length_ft(self) -> float:
        return self.end_ft - self.start_ft


def drip_strip_runs(length_ft: float, post_stations_ft: tuple[float, ...],
                    railing: str) -> tuple[StripRun, ...]:
    """The strip pieces along ONE fascia edge: the continuous lower strip
    over the full length plus an upper strip centered at each railing
    post (clipped to the fascia).  Raises ``ValueError`` for an unknown
    railing or non-positive length."""
    if length_ft <= 0:
        raise ValueError("fascia length must be positive")
    p = placement(railing)
    half = p.upper_strip_length_in / 24.0   # half length, ft
    runs = [StripRun("lower", 0.0, length_ft)]
    for s in post_stations_ft:
        if s < -half or s > length_ft + half:
            raise ValueError(
                f"post station {s} ft is outside the fascia (0 to "
                f"{length_ft} ft)")
        runs.append(StripRun("upper", max(s - half, 0.0),
                             min(s + half, length_ft)))
    return tuple(runs)


def pay_length_ft(runs: tuple[StripRun, ...], sides: int = 1) -> float:
    """Measured length (ft): the total of upper and lower strips.
    ``sides=2`` doubles a single-fascia takeoff for both edges."""
    return sides * sum(r.length_ft for r in runs)
