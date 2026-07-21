#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO LRFD-LTS Section 11 — wind-induced fatigue loads and resistance.

Fatigue I applies galloping, natural wind gust, and vortex shedding each at
1.0, separately (Table 3.4-1).  Fatigue stress ranges are elastic — they
ride on ``S``, not ``Z``.  Vortex shedding (11.7.1.3) is not implemented
yet; it governs slender tapered poles, not span-wire assemblies.

Productionized from the validated ``Notebooks/Wind Load Calc.ipynb`` LTS-1
proof of concept.
"""

from __future__ import annotations


def galloping_pressure(importance_factor: float = 1.0) -> float:
    """P_G per Eq. 11.7.1.1-1, psf — an equivalent static shear applied
    **vertically** over the attachment's frontal area."""
    return 21.0 * importance_factor


def natural_wind_gust_pressure(cd: float, importance_factor: float = 1.0) -> float:
    """P_NW per Eq. 11.7.1.2-1, psf — horizontal, on everything exposed."""
    return 5.2 * cd * importance_factor


# Table 11.9.3.1-1 Detail 5.4 — fillet-welded tube-to-transverse-plate
# socket.  CAFT (ksi) banded by the infinite-life stress concentration
# factor K_I (Eq. 11.9.3.1-1): each entry is (K_I upper bound, CAFT).
DETAIL_5_4_CAFT_BANDS = ((4.0, 7.0), (6.5, 4.5), (7.7, 2.6))

# Anchor rods are Category D.
ANCHOR_ROD_CAFT = 7.0


def tube_to_plate_caft(k_i: float | None = None) -> float:
    """CAFT (ksi) for a socket-welded tube-to-transverse-plate connection.

    Pass ``k_i`` when Eq. 11.9.3.1-2 is valid for the geometry; pass
    ``None`` when the geometry falls outside the equation's calibration
    window (NCHRP 10-70 covered signal poles and high-masts) to adopt the
    worst band, 2.6 ksi, as a floor rather than argue for an uncomputable
    number.
    """
    if k_i is None:
        return DETAIL_5_4_CAFT_BANDS[-1][1]
    for upper, caft in DETAIL_5_4_CAFT_BANDS:
        if k_i <= upper:
            return caft
    raise ValueError(f"K_I = {k_i:.2f} exceeds the Detail 5.4 limit of 7.7")


__all__ = [
    "galloping_pressure",
    "natural_wind_gust_pressure",
    "DETAIL_5_4_CAFT_BANDS",
    "ANCHOR_ROD_CAFT",
    "tube_to_plate_caft",
]
