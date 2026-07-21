#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO LRFD-LTS Table 3.4-1 — load combinations.

Only the combinations exercised by the validated notebook proof of concept
are transcribed so far; transcribe the remaining Table 3.4-1 rows from the
spec before relying on this module for combinations not listed here.

Fatigue I applies galloping, natural wind gust, and vortex shedding each at
1.0 — **separately**, not summed.
"""

from __future__ import annotations

LTS_LOAD_COMBINATIONS = {
    # Strength wind check: 1.0*W at the structure's MRI wind (Table 3.8-1),
    # with DC at 1.1 (max) / 0.9 (min).
    "Extreme I": {"DC_max": 1.1, "DC_min": 0.9, "W": 1.0},
    # Serviceability (deflection) at the 10-yr MRI wind of Fig. 3.8-4.
    "Service I": {"DC": 1.0, "W": 1.0, "wind_mri_years": 10},
    # Wind-induced fatigue loads, each applied separately at 1.0.
    "Fatigue I": {"galloping": 1.0, "natural_wind_gust": 1.0, "vortex_shedding": 1.0},
}

__all__ = ["LTS_LOAD_COMBINATIONS"]
