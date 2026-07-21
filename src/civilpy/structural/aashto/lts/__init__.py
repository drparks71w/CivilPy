#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO LRFD Specifications for Structural Supports for Highway Signs,
Luminaires, and Traffic Signals (LRFD-LTS) — independent design checks.

Same philosophy as :mod:`civilpy.structural.aashto.lrfd`: pure functions of
primitive inputs.  Wind (Art. 3.8) works in psf / mph / ft, the dimensional
form of the spec equations; member checks (Section 5) follow the package's
kip / inch / ksi convention.

>>> from civilpy.structural.aashto import lts
>>> round(lts.height_factor(16.0), 3)
0.861
"""

from civilpy.structural.aashto.lts.core import CheckResult, LTS_ARTICLES, lts_article
from civilpy.structural.aashto.lts.wind import (
    MRI_YEARS,
    OHIO_WIND_SPEEDS,
    DIRECTIONALITY_FACTORS,
    GUST_EFFECT_MIN,
    CD_TRAFFIC_SIGNAL,
    height_factor,
    directionality_factor,
    cd_cylinder,
    cd_sign_panel,
    velocity_pressure,
    design_wind_pressure,
)
from civilpy.structural.aashto.lts.combinations import LTS_LOAD_COMBINATIONS
from civilpy.structural.aashto.lts.steel import (
    E_STEEL,
    RoundTube,
    round_tube_flexural_resistance,
    compression_resistance,
    moment_magnifier,
    combined_force_interaction,
)
from civilpy.structural.aashto.lts.fatigue import (
    galloping_pressure,
    natural_wind_gust_pressure,
    DETAIL_5_4_CAFT_BANDS,
    ANCHOR_ROD_CAFT,
    tube_to_plate_caft,
)

__all__ = [
    "CheckResult",
    "LTS_ARTICLES",
    "lts_article",
    "MRI_YEARS",
    "OHIO_WIND_SPEEDS",
    "DIRECTIONALITY_FACTORS",
    "GUST_EFFECT_MIN",
    "CD_TRAFFIC_SIGNAL",
    "height_factor",
    "directionality_factor",
    "cd_cylinder",
    "cd_sign_panel",
    "velocity_pressure",
    "design_wind_pressure",
    "LTS_LOAD_COMBINATIONS",
    "E_STEEL",
    "RoundTube",
    "round_tube_flexural_resistance",
    "compression_resistance",
    "moment_magnifier",
    "combined_force_interaction",
    "galloping_pressure",
    "natural_wind_gust_pressure",
    "DETAIL_5_4_CAFT_BANDS",
    "ANCHOR_ROD_CAFT",
    "tube_to_plate_caft",
]
