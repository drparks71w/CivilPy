#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio DOT prestressed concrete I-beam bridge details (PSID-1-13).

Transcribed from Ohio DOT Standard Bridge Drawing PSID-1-13, "Prestressed
Concrete I-Beam Bridge Details" (rev. 07-18-2025, 10 sheets, sheet 1's
``SECTION PROPERTIES`` table). The drawing remains the controlling
document.

Six standard sections: AASHTO Type 2/3/4 and three deepened "Modified
AASHTO Type 4" webs (60/66/72 in overall depth) that share Type 4's
flange widths. Top/bottom flange widths are the published AASHTO
standard I-girder dimensions (12/18 in for Type II, 16/22 in for Type
III, 20/26 in for Type IV and its modified-depth variants) -- confirmed
against the Type 2 elevation's own dimensions on this sheet; not
re-verified pixel-by-pixel for Type 3/4 (see SCD_BUILD_QUESTIONS.md).

Like PSBD-1-25 (:mod:`civilpy.structural.odot.box_beam`), the *design*
data (strand patterns, camber, load ratings) lives on a companion sheet
this module does not encode (PSIDD-1-xx does not yet exist as an
archived SCD); only the section geometry and the sheet's own bar-mark/
bend-type legend are cataloged here.

Lengths in inches, area in in^2, weight in lb/ft, moment of inertia in
in^4, section moduli in in^3, unless noted. Spot-checked against the
drawing in the test suite.
"""

from dataclasses import dataclass, field

Point = tuple[float, float]  # (y, z) inches, section profile

SCD = "PSID-1-13"
REVISION = "07-18-2025"

REBAR_EPOXY_NOTE = "401-series bars (marked '(d)') shall be epoxy-coated"
WWR_NOTE = "all reinforcing steel may be replaced with equivalent welded wire reinforcement (WWR)"


@dataclass(frozen=True)
class PSIBeamSection:
    """One PSID-1-13 standard section (sheet 1 SECTION PROPERTIES table)."""

    name: str
    depth_in: float
    area_in2: float
    weight_plf: float
    yb_in: float           # centroid above bottom
    yt_in: float            # centroid below top
    i_in4: float
    sb_in3: float
    st_in3: float
    vol_surf_ratio: float
    top_flange_width_in: float
    bottom_flange_width_in: float
    max_bottom_flange_strands: int


#: PSID-1-13 standard I-beam sections, keyed by name.
PS_I_BEAM_SECTIONS: dict[str, PSIBeamSection] = {
    "AASHTO Type 2": PSIBeamSection(
        "AASHTO Type 2", 36.0, 369.0, 384.0, 15.83, 20.17, 50_979, 3_221,
        2_527, 3.371, 12.0, 18.0, 26),
    "AASHTO Type 3": PSIBeamSection(
        "AASHTO Type 3", 45.0, 560.0, 583.0, 20.27, 24.73, 125_390, 6_185,
        5_071, 4.056, 16.0, 22.0, 40),
    "AASHTO Type 4": PSIBeamSection(
        "AASHTO Type 4", 54.0, 789.0, 822.0, 24.73, 29.27, 260_741, 10_542,
        8_909, 4.741, 20.0, 26.0, 52),
    "Modified AASHTO Type 4 (60in)": PSIBeamSection(
        "Modified AASHTO Type 4 (60in)", 60.0, 860.0, 896.0, 28.74, 31.26,
        384_705, 13_385, 12_307, 4.089, 20.0, 26.0, 52),
    "Modified AASHTO Type 4 (66in)": PSIBeamSection(
        "Modified AASHTO Type 4 (66in)", 66.0, 908.0, 946.0, 31.58, 34.42,
        492_212, 15_588, 14_299, 4.085, 20.0, 26.0, 52),
    "Modified AASHTO Type 4 (72in)": PSIBeamSection(
        "Modified AASHTO Type 4 (72in)", 72.0, 1015.0, 1058.0, 36.52, 35.48,
        684_726, 18_749, 19_299, 3.947, 20.0, 26.0, 52),
}


def ps_i_beam_section(name: str) -> PSIBeamSection:
    """Look up a PSID-1-13 standard section by name.

    Raises ``ValueError`` naming the valid sections otherwise."""
    try:
        return PS_I_BEAM_SECTIONS[name]
    except KeyError:
        raise ValueError(
            f"PSID-1-13 sections are {list(PS_I_BEAM_SECTIONS)}, "
            f"not {name!r}") from None


# ── layout (simplified I-shape; bulb radius/haunch fillets not modeled) ──

@dataclass(frozen=True)
class PSIBeamLayout:
    """A simplified I-shaped cross-section profile (top flange, web,
    bottom flange) -- straight-line approximation, no fillet/bulb radii --
    extruded ``length_ft``. Profile points (y, z) inches, y transverse,
    z up from the bottom; the beam centerline is y = 0."""

    section: PSIBeamSection
    profile: tuple[Point, ...]
    length_ft: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def layout_ps_i_beam(name: str, length_ft: float,
                     web_thickness_in: float = 8.0,
                     flange_thickness_in: float = 8.0) -> PSIBeamLayout:
    """Generate a simplified I-beam cross-section profile for ``name``
    (:func:`ps_i_beam_section`), extruded ``length_ft``.

    Raises ``ValueError`` for a non-positive length or an unknown section
    name."""
    if length_ft <= 0.0:
        raise ValueError("length_ft must be positive")
    s = ps_i_beam_section(name)
    D = s.depth_in
    tw = web_thickness_in
    tf = flange_thickness_in
    top_w, bot_w = s.top_flange_width_in, s.bottom_flange_width_in

    profile = (
        (-bot_w / 2.0, 0.0), (bot_w / 2.0, 0.0),
        (bot_w / 2.0, tf), (tw / 2.0, tf),
        (tw / 2.0, D - tf), (top_w / 2.0, D - tf),
        (top_w / 2.0, D), (-top_w / 2.0, D),
        (-top_w / 2.0, D - tf), (-tw / 2.0, D - tf),
        (-tw / 2.0, tf), (-bot_w / 2.0, tf),
    )

    notes = (
        f"PSID-1-13 {name}: depth {D:g} in, area {s.area_in2:g} in^2, "
        f"weight {s.weight_plf:g} lb/ft, I {s.i_in4:,.0f} in^4, length "
        f"{length_ft:g} ft",
        f"Max {s.max_bottom_flange_strands} permissible bottom flange "
        "strand locations (strand pattern itself is project-specific).",
        "Simplified straight-line I-shape -- true bulb/fillet radii, "
        "strand pattern, shipping strands, WWR/rebar (A/B/C/D/E/F/G "
        "series bars), and end-block details are not modeled.",
    )

    return PSIBeamLayout(section=s, profile=profile, length_ft=length_ft,
                         notes=notes)
