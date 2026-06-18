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

"""Ohio DOT prestressed box beam standard designs and load ratings (PSBDD-1-25).

Design data and load ratings transcribed from the Ohio DOT Design Data
Sheet PSBDD-1-25, "Prestressed Concrete Composite / Non-Composite Adjacent
Box Beams" (Office of Structural Engineering, 2025-07-18, rev. 2026-01-16,
4 sheets).  This is the companion to the construction-detail drawing
PSBD-1-25 (see :mod:`civilpy.structural.odot.box_beam`).

The drawing covers two families -- composite (CB, sheets 1-2) and
non-composite (B, sheets 3-4) -- of 48 in wide adjacent box beams at five
depths (17, 21, 27, 33, 42 in).  Two tables are carried here:

``design`` (PSBDD-1-25 sheets 1 & 3)
    Per box and span: strand eccentricity (beam, and for composite the
    composite section), number of strands and their placement (rows at 2,
    4, 6 in from the bottom), stirrup-zone layout, camber at release (D0)
    and erection (D30), residual deflection, and the bearing pad type.
    The tensile-bar schedule and debonding lengths on the drawing are not
    carried here.

``load rating`` (PSBDD-1-25 sheets 2 & 4)
    LRFR rating factors (adjusted load factors, mainline interstate) for
    each box, span, and bridge width (24/28/32 ft = 6/7/8 beams), across
    the 16 rating vehicles tabulated on the sheet: HL-93 inventory and
    operating, the emergency (EV2/EV3) and specialized-hauling (SU4-SU7)
    vehicles, the AASHTO legal types (Type 3, 3-3, 3S2), and the Ohio
    permit/legal trucks (S-2F1, S-3F1, S-5C1, S-PL60T, S-PL65T).

Lengths in inches, spans in feet.  The values were extracted from the
drawing's text layer and validated (strand placement sums to the strand
count; operating exceeds inventory on every line); the drawing remains the
controlling document.

Design assumptions (per the sheet's design notes): AASHTO LRFD BDS 10th Ed.
(2024) + ODOT BDM, HL-93, skew <= 30 deg, roadway width 24-32 ft,
f'c = 7 ksi (f'ci = 5 ksi), Grade 60 reinforcing, 0.5 in 270 ksi
low-relaxation strand (0.167 sq in).
"""

import csv
import os
from dataclasses import dataclass, field

_RES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res")
_DESIGN_CSV = os.path.join(_RES_DIR, "psbdd_1_25_design.csv")
_RATING_CSV = os.path.join(_RES_DIR, "psbdd_1_25_load_rating.csv")

#: Rating vehicles in the order tabulated on PSBDD-1-25 (keys into
#: :attr:`BoxBeamRating.rating_factors`).
RATING_VEHICLES: tuple[str, ...] = (
    "inv", "op", "ev2", "ev3", "s2f1", "s3f1", "s5c1", "spl60t", "spl65t",
    "su4", "su5", "su6", "su7", "type3", "type33", "type3s2",
)


@dataclass(frozen=True)
class BoxBeamDesign:
    """One standard box-beam design line (PSBDD-1-25 sheets 1 & 3).

    ``e_composite`` is ``None`` for non-composite beams.  ``strands_2in`` /
    ``strands_4in`` / ``strands_6in`` are the strand counts in the rows 2,
    4, and 6 in above the soffit (their sum is ``n_strands``).  Camber
    values are at release (``camber_d0``) and erection (``camber_d30``);
    ``deflection`` is the residual midspan deflection under remaining dead
    load.  All lengths in inches.
    """

    beam_type: str          # "composite" or "non_composite"
    box: str                # e.g. "CB27-48"
    depth: int              # in
    width: int              # in (48)
    span: int               # ft
    e_beam: float           # in
    e_composite: float | None  # in
    n_strands: int
    strands_2in: int
    strands_4in: int
    strands_6in: int
    stirrup_w_pairs: int
    stirrup_zone_x: float   # in (length of the close-stirrup zone)
    stirrup_y: float        # in (spacing tag Y)
    stirrup_z: float        # in (spacing tag Z)
    camber_d0: float        # in
    camber_d30: float       # in
    deflection: float       # in
    bearing_type: str       # "B1" or "B2"


@dataclass(frozen=True)
class BoxBeamRating:
    """LRFR rating factors for one box / span / bridge width (PSBDD-1-25
    sheets 2 & 4).  ``rating_factors`` is keyed by :data:`RATING_VEHICLES`."""

    beam_type: str
    box: str
    width_ft: int
    n_beams: int
    span: int
    rating_factors: dict[str, float] = field(default_factory=dict)

    @property
    def inventory(self) -> float:
        """HL-93 inventory rating factor."""
        return self.rating_factors["inv"]

    @property
    def operating(self) -> float:
        """HL-93 operating rating factor."""
        return self.rating_factors["op"]


def _opt_float(x: str) -> float | None:
    x = x.strip()
    return float(x) if x else None


def _load_design() -> list[BoxBeamDesign]:
    out: list[BoxBeamDesign] = []
    with open(_DESIGN_CSV, newline="") as fh:
        for r in csv.DictReader(fh):
            out.append(
                BoxBeamDesign(
                    beam_type=r["beam_type"],
                    box=r["box"],
                    depth=int(r["depth_in"]),
                    width=int(r["width_in"]),
                    span=int(r["span_ft"]),
                    e_beam=float(r["e_beam_in"]),
                    e_composite=_opt_float(r["e_composite_in"]),
                    n_strands=int(r["n_strands"]),
                    strands_2in=int(r["strands_2in"]),
                    strands_4in=int(r["strands_4in"]),
                    strands_6in=int(r["strands_6in"]),
                    stirrup_w_pairs=int(r["stirrup_w_pairs"]),
                    stirrup_zone_x=float(r["stirrup_zone_x_in"]),
                    stirrup_y=float(r["stirrup_y_in"]),
                    stirrup_z=float(r["stirrup_z_in"]),
                    camber_d0=float(r["camber_d0_in"]),
                    camber_d30=float(r["camber_d30_in"]),
                    deflection=float(r["deflection_in"]),
                    bearing_type=r["bearing_type"],
                )
            )
    return out


def _load_ratings() -> list[BoxBeamRating]:
    out: list[BoxBeamRating] = []
    with open(_RATING_CSV, newline="") as fh:
        for r in csv.DictReader(fh):
            out.append(
                BoxBeamRating(
                    beam_type=r["beam_type"],
                    box=r["box"],
                    width_ft=int(r["width_ft"]),
                    n_beams=int(r["n_beams"]),
                    span=int(r["span_ft"]),
                    rating_factors={
                        v: float(r[f"rf_{v}"]) for v in RATING_VEHICLES
                    },
                )
            )
    return out


#: All standard box-beam designs (PSBDD-1-25 sheets 1 & 3).
BOX_BEAM_DESIGNS: list[BoxBeamDesign] = _load_design()

#: All box-beam load ratings (PSBDD-1-25 sheets 2 & 4).
BOX_BEAM_RATINGS: list[BoxBeamRating] = _load_ratings()

#: Standard box designations (e.g. ``"CB27-48"``, ``"B27-48"``).
BOX_DESIGNATIONS: tuple[str, ...] = tuple(
    dict.fromkeys(d.box for d in BOX_BEAM_DESIGNS)
)


def box_beam_design(box: str, span: int) -> BoxBeamDesign:
    """The design line for a box designation and span in feet."""
    for d in BOX_BEAM_DESIGNS:
        if d.box == box and d.span == span:
            return d
    raise KeyError(f"no PSBDD-1-25 design for {box} at span {span} ft")


def designs_for_box(box: str) -> list[BoxBeamDesign]:
    """All span designs for one box designation, shortest span first."""
    return [d for d in BOX_BEAM_DESIGNS if d.box == box]


def box_beam_rating(box: str, span: int, width_ft: int) -> BoxBeamRating:
    """The load rating for a box, span (ft), and bridge width (24/28/32 ft)."""
    for r in BOX_BEAM_RATINGS:
        if r.box == box and r.span == span and r.width_ft == width_ft:
            return r
    raise KeyError(
        f"no PSBDD-1-25 rating for {box} at span {span} ft, width {width_ft} ft"
    )
