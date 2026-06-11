#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
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

import pandas as pd

# Load combinations and load factors per AASHTO LRFD Bridge Design Specifications.
# Table 3.4.1-1 — Load Combinations and Load Factors.
# Table 3.4.1-2 — Load Factors for Permanent Loads (gamma_p).
# Refer to the current edition of AASHTO LRFD for authoritative values.
load_combinations = {
    "Strength I": {
        "Description": "Basic load combination for normal vehicular use of the bridge",
        "DC": {"gamma": "$\gamma_p$", "Note": ""},
        "DW": {"gamma": "$\gamma_p$", "Note": ""},
        "EH": {"gamma": "$\gamma_p$", "Note": ""},
        "EV": {"gamma": "$\gamma_p$", "Note": ""},
        "ES": {"gamma": "$\gamma_p$", "Note": ""},
        "EL": {"gamma": "$\gamma_p$", "Note": ""},
        "PS": {"gamma": "$\gamma_p$", "Note": ""},
        "CR": {"gamma": "$\gamma_p$", "Note": ""},
        "SH": {"gamma": "$\gamma_p$", "Note": ""},

        "LL": {"gamma": 1.75, "Note": ""},
        "IM": {"gamma": 1.75, "Note": ""},
        "CE": {"gamma": 1.75, "Note": ""},
        "BR": {"gamma": 1.75, "Note": ""},
        "PL": {"gamma": 1.75, "Note": ""},
        "LS": {"gamma": 1.75, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": "$\gamma_{TG}$", "Note": ""},
        "SE": {"gamma": "$\gamma_{SE}$", "Note": ""},
        "DR": {"gamma": "$\gamma_{DR}$", "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Strength II": {
        "Description": "Load combination relating to the use of the bridge by Owner-specified special design vehicles, evaluation permit vehicles, or both",
        "DC": {"gamma": "$\gamma_p$", "Note": ""},
        "DW": {"gamma": "$\gamma_p$", "Note": ""},
        "EH": {"gamma": "$\gamma_p$", "Note": ""},
        "EV": {"gamma": "$\gamma_p$", "Note": ""},
        "ES": {"gamma": "$\gamma_p$", "Note": ""},
        "EL": {"gamma": "$\gamma_p$", "Note": ""},
        "PS": {"gamma": "$\gamma_p$", "Note": ""},
        "CR": {"gamma": "$\gamma_p$", "Note": ""},
        "SH": {"gamma": "$\gamma_p$", "Note": ""},

        "LL": {"gamma": 1.35, "Note": ""},
        "IM": {"gamma": 1.35, "Note": ""},
        "CE": {"gamma": 1.35, "Note": ""},
        "BR": {"gamma": 1.35, "Note": ""},
        "PL": {"gamma": 1.35, "Note": ""},
        "LS": {"gamma": 1.35, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": "$\gamma_{TG}$", "Note": ""},
        "SE": {"gamma": "$\gamma_{SE}$", "Note": ""},
        "DR": {"gamma": "$\gamma_{DR}$", "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Strength III": {
        "Description": "Load combination relating to the bridge exposed to wind velocity exceeding 55 mph",
        "DC": {"gamma": "$\gamma_p$", "Note": ""},
        "DW": {"gamma": "$\gamma_p$", "Note": ""},
        "EH": {"gamma": "$\gamma_p$", "Note": ""},
        "EV": {"gamma": "$\gamma_p$", "Note": ""},
        "ES": {"gamma": "$\gamma_p$", "Note": ""},
        "EL": {"gamma": "$\gamma_p$", "Note": ""},
        "PS": {"gamma": "$\gamma_p$", "Note": ""},
        "CR": {"gamma": "$\gamma_p$", "Note": ""},
        "SH": {"gamma": "$\gamma_p$", "Note": ""},

        "LL": {"gamma": 0.00, "Note": ""},
        "IM": {"gamma": 0.00, "Note": ""},
        "CE": {"gamma": 0.00, "Note": ""},
        "BR": {"gamma": 0.00, "Note": ""},
        "PL": {"gamma": 0.00, "Note": ""},
        "LS": {"gamma": 0.00, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 1.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},

        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": "$\gamma_{TG}$", "Note": ""},
        "SE": {"gamma": "$\gamma_{SE}$", "Note": ""},
        "DR": {"gamma": "$\gamma_{DR}$", "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Strength IV": {
        "Description": "Load combination relating to very high dead load to live load force effect ratios",
        "DC": {"gamma": "$\gamma_p$", "Note": ""},
        "DW": {"gamma": "$\gamma_p$", "Note": ""},
        "EH": {"gamma": "$\gamma_p$", "Note": ""},
        "EV": {"gamma": "$\gamma_p$", "Note": ""},
        "ES": {"gamma": "$\gamma_p$", "Note": ""},
        "EL": {"gamma": "$\gamma_p$", "Note": ""},
        "PS": {"gamma": "$\gamma_p$", "Note": ""},
        "CR": {"gamma": "$\gamma_p$", "Note": ""},
        "SH": {"gamma": "$\gamma_p$", "Note": ""},

        "LL": {"gamma": 0.00, "Note": ""},
        "IM": {"gamma": 0.00, "Note": ""},
        "CE": {"gamma": 0.00, "Note": ""},
        "BR": {"gamma": 0.00, "Note": ""},
        "PL": {"gamma": 0.00, "Note": ""},
        "LS": {"gamma": 0.00, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": 0.00, "Note": ""},
        "SE": {"gamma": 0.00, "Note": ""},
        "DR": {"gamma": 0.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Strength V": {
        "Description": "Load combination relating to normal vehicular use of the bridge with wind of 55 mph",
        "DC": {"gamma": "$\gamma_p$", "Note": ""},
        "DW": {"gamma": "$\gamma_p$", "Note": ""},
        "EH": {"gamma": "$\gamma_p$", "Note": ""},
        "EV": {"gamma": "$\gamma_p$", "Note": ""},
        "ES": {"gamma": "$\gamma_p$", "Note": ""},
        "EL": {"gamma": "$\gamma_p$", "Note": ""},
        "PS": {"gamma": "$\gamma_p$", "Note": ""},
        "CR": {"gamma": "$\gamma_p$", "Note": ""},
        "SH": {"gamma": "$\gamma_p$", "Note": ""},

        "LL": {"gamma": 1.35, "Note": ""},
        "IM": {"gamma": 1.35, "Note": ""},
        "CE": {"gamma": 1.35, "Note": ""},
        "BR": {"gamma": 1.35, "Note": ""},
        "PL": {"gamma": 1.35, "Note": ""},
        "LS": {"gamma": 1.35, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 1.00, "Note": ""},
        "WL": {"gamma": 1.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": "$\gamma_{TG}$", "Note": ""},
        "SE": {"gamma": "$\gamma_{SE}$", "Note": ""},
        "DR": {"gamma": "$\gamma_{DR}$", "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Extreme Event I": {
        "Description": "Load combination including earthquake",
        "DC": {"gamma": 1.00, "Note": ""},
        "DW": {"gamma": 1.00, "Note": ""},
        "EH": {"gamma": 1.00, "Note": ""},
        "EV": {"gamma": 1.00, "Note": ""},
        "ES": {"gamma": 1.00, "Note": ""},
        "EL": {"gamma": 1.00, "Note": ""},
        "PS": {"gamma": 1.00, "Note": ""},
        "CR": {"gamma": 1.00, "Note": ""},
        "SH": {"gamma": 1.00, "Note": ""},

        "LL": {"gamma": "$\gamma_{EQ}$", "Note": ""},
        "IM": {"gamma": "$\gamma_{EQ}$", "Note": ""},
        "CE": {"gamma": "$\gamma_{EQ}$", "Note": ""},
        "BR": {"gamma": "$\gamma_{EQ}$", "Note": ""},
        "PL": {"gamma": "$\gamma_{EQ}$", "Note": ""},
        "LS": {"gamma": "$\gamma_{EQ}$", "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": 0.00, "Note": ""},
        "TG": {"gamma": 0.00, "Note": ""},
        "SE": {"gamma": 0.00, "Note": ""},
        "DR": {"gamma": 1.00, "Note": ""},
        "EQ": {"gamma": 1.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Extreme Event II": {
        "Description": "Load combination relating to ice load, vessel collision, check flood, or certain hydraulic events",
        "DC": {"gamma": 1.00, "Note": ""},
        "DW": {"gamma": 1.00, "Note": ""},
        "EH": {"gamma": 1.00, "Note": ""},
        "EV": {"gamma": 1.00, "Note": ""},
        "ES": {"gamma": 1.00, "Note": ""},
        "EL": {"gamma": 1.00, "Note": ""},
        "PS": {"gamma": 1.00, "Note": ""},
        "CR": {"gamma": 1.00, "Note": ""},
        "SH": {"gamma": 1.00, "Note": ""},

        "LL": {"gamma": [0.50, 1.00], "Note": ""},
        "IM": {"gamma": [0.50, 1.00], "Note": ""},
        "CE": {"gamma": [0.50, 1.00], "Note": ""},
        "BR": {"gamma": [0.50, 1.00], "Note": ""},
        "PL": {"gamma": [0.50, 1.00], "Note": ""},
        "LS": {"gamma": [0.50, 1.00], "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": 0.00, "Note": ""},
        "TG": {"gamma": 0.00, "Note": ""},
        "SE": {"gamma": 0.00, "Note": ""},
        "DR": {"gamma": 1.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 1.00, "Note": ""},
        "IC": {"gamma": 1.00, "Note": ""},
        "CT": {"gamma": 1.00, "Note": ""},
        "CV": {"gamma": 1.00, "Note": ""},
    },
    "Service I": {
        "Description": "Load combination relating to normal operational use of the bridge with 55 mph wind",
        "DC": {"gamma": 1.00, "Note": ""},
        "DW": {"gamma": 1.00, "Note": ""},
        "EH": {"gamma": 1.00, "Note": ""},
        "EV": {"gamma": 1.00, "Note": ""},
        "ES": {"gamma": 1.00, "Note": ""},
        "EL": {"gamma": 1.00, "Note": ""},
        "PS": {"gamma": 1.00, "Note": ""},
        "CR": {"gamma": 1.00, "Note": ""},
        "SH": {"gamma": 1.00, "Note": ""},

        "LL": {"gamma": 1.00, "Note": ""},
        "IM": {"gamma": 1.00, "Note": ""},
        "CE": {"gamma": 1.00, "Note": ""},
        "BR": {"gamma": 1.00, "Note": ""},
        "PL": {"gamma": 1.00, "Note": ""},
        "LS": {"gamma": 1.00, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 1.00, "Note": ""},
        "WL": {"gamma": 1.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": "$\gamma_{TG}$", "Note": ""},
        "SE": {"gamma": "$\gamma_{SE}$", "Note": ""},
        "DR": {"gamma": 1.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Service II": {
        "Description": "Load combination intended to control yielding of steel structures and slip of slip-critical connections due to vehicular live load",
        "DC": {"gamma": 1.00, "Note": ""},
        "DW": {"gamma": 1.00, "Note": ""},
        "EH": {"gamma": 1.00, "Note": ""},
        "EV": {"gamma": 1.00, "Note": ""},
        "ES": {"gamma": 1.00, "Note": ""},
        "EL": {"gamma": 1.00, "Note": ""},
        "PS": {"gamma": 1.00, "Note": ""},
        "CR": {"gamma": 1.00, "Note": ""},
        "SH": {"gamma": 1.00, "Note": ""},

        "LL": {"gamma": 1.30, "Note": ""},
        "IM": {"gamma": 1.30, "Note": ""},
        "CE": {"gamma": 1.30, "Note": ""},
        "BR": {"gamma": 1.30, "Note": ""},
        "PL": {"gamma": 1.30, "Note": ""},
        "LS": {"gamma": 1.30, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": 0.00, "Note": ""},
        "SE": {"gamma": 0.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Service III": {
        "Description": "Load combination for longitudinal analysis relating to tension in prestressed concrete superstructures with the objective of crack control",
        "DC": {"gamma": 1.00, "Note": ""},
        "DW": {"gamma": 1.00, "Note": ""},
        "EH": {"gamma": 1.00, "Note": ""},
        "EV": {"gamma": 1.00, "Note": ""},
        "ES": {"gamma": 1.00, "Note": ""},
        "EL": {"gamma": 1.00, "Note": ""},
        "PS": {"gamma": 1.00, "Note": ""},
        "CR": {"gamma": 1.00, "Note": ""},
        "SH": {"gamma": 1.00, "Note": ""},

        "LL": {"gamma": "$\gamma_{LL}$", "Note": ""},
        "IM": {"gamma": "$\gamma_{LL}$", "Note": ""},
        "CE": {"gamma": "$\gamma_{LL}$", "Note": ""},
        "BR": {"gamma": "$\gamma_{LL}$", "Note": ""},
        "PL": {"gamma": "$\gamma_{LL}$", "Note": ""},
        "LS": {"gamma": "$\gamma_{LL}$", "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": "$\gamma_{TG}$", "Note": ""},
        "SE": {"gamma": "$\gamma_{SE}$", "Note": ""},
        "DR": {"gamma": 1.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Service IV": {
        "Description": "Load combination relating only to tension in prestressed concrete columns with the objective of crack control",
        "DC": {"gamma": 1.00, "Note": ""},
        "DW": {"gamma": 1.00, "Note": ""},
        "EH": {"gamma": 1.00, "Note": ""},
        "EV": {"gamma": 1.00, "Note": ""},
        "ES": {"gamma": 1.00, "Note": ""},
        "EL": {"gamma": 1.00, "Note": ""},
        "PS": {"gamma": 1.00, "Note": ""},
        "CR": {"gamma": 1.00, "Note": ""},
        "SH": {"gamma": 1.00, "Note": ""},

        "LL": {"gamma": 0.00, "Note": ""},
        "IM": {"gamma": 0.00, "Note": ""},
        "CE": {"gamma": 0.00, "Note": ""},
        "BR": {"gamma": 0.00, "Note": ""},
        "PL": {"gamma": 0.00, "Note": ""},
        "LS": {"gamma": 0.00, "Note": ""},

        "WA": {"gamma": 1.00, "Note": ""},
        "WS": {"gamma": 1.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 1.00, "Note": ""},
        "TU": {"gamma": "$\gamma_{TU}$", "Note": ""},
        "TG": {"gamma": 0.00, "Note": ""},
        "SE": {"gamma": 1.00, "Note": ""},
        "DR": {"gamma": 1.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Fatigue I": {
        "Description": "Fatigue and fracture load combination related to infinite load-induced fatigue life",
        "DC": {"gamma": 0.00, "Note": ""},
        "DW": {"gamma": 0.00, "Note": ""},
        "EH": {"gamma": 0.00, "Note": ""},
        "EV": {"gamma": 0.00, "Note": ""},
        "ES": {"gamma": 0.00, "Note": ""},
        "EL": {"gamma": 0.00, "Note": ""},
        "PS": {"gamma": 0.00, "Note": ""},
        "CR": {"gamma": 0.00, "Note": ""},
        "SH": {"gamma": 0.00, "Note": ""},

        "LL": {"gamma": 1.75, "Note": ""},
        "IM": {"gamma": 1.75, "Note": ""},
        "CE": {"gamma": 1.75, "Note": ""},
        "BR": {"gamma": 0.00, "Note": ""},
        "PL": {"gamma": 0.00, "Note": ""},
        "LS": {"gamma": 0.00, "Note": ""},

        "WA": {"gamma": 0.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 0.00, "Note": ""},
        "TU": {"gamma": 0.00, "Note": ""},
        "TG": {"gamma": 0.00, "Note": ""},
        "SE": {"gamma": 0.00, "Note": ""},
        "DR": {"gamma": 0.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    },
    "Fatigue II": {
        "Description": "Fatigue and fracture load combination related to finite load-induced fatigue life",
        "DC": {"gamma": 0.00, "Note": ""},
        "DW": {"gamma": 0.00, "Note": ""},
        "EH": {"gamma": 0.00, "Note": ""},
        "EV": {"gamma": 0.00, "Note": ""},
        "ES": {"gamma": 0.00, "Note": ""},
        "EL": {"gamma": 0.00, "Note": ""},
        "PS": {"gamma": 0.00, "Note": ""},
        "CR": {"gamma": 0.00, "Note": ""},
        "SH": {"gamma": 0.00, "Note": ""},

        "LL": {"gamma": 0.80, "Note": ""},
        "IM": {"gamma": 0.80, "Note": ""},
        "CE": {"gamma": 0.80, "Note": ""},
        "BR": {"gamma": 0.00, "Note": ""},
        "PL": {"gamma": 0.00, "Note": ""},
        "LS": {"gamma": 0.00, "Note": ""},

        "WA": {"gamma": 0.00, "Note": ""},
        "WS": {"gamma": 0.00, "Note": ""},
        "WL": {"gamma": 0.00, "Note": ""},
        "FR": {"gamma": 0.00, "Note": ""},
        "TU": {"gamma": 0.00, "Note": ""},
        "TG": {"gamma": 0.00, "Note": ""},
        "SE": {"gamma": 0.00, "Note": ""},
        "DR": {"gamma": 0.00, "Note": ""},
        "EQ": {"gamma": 0.00, "Note": ""},
        "BL": {"gamma": 0.00, "Note": ""},
        "IC": {"gamma": 0.00, "Note": ""},
        "CT": {"gamma": 0.00, "Note": ""},
        "CV": {"gamma": 0.00, "Note": ""},
    }
}

# Create a dataframe with load combinations as rows and load types as columns
load_combos_data = []
for combo_name, combo_data in load_combinations.items():
    row_data = {"Load Combination": combo_name, "Description": combo_data["Description"]}
    for load_type, load_info in combo_data.items():
        if load_type != "Description":
            row_data[load_type] = load_info["gamma"]
    load_combos_data.append(row_data)

aashto_load_combos_df = pd.DataFrame(load_combos_data)

# Permanent load factors - AASHTO LRFD Table 3.4.1-2
# Simple (most common) values for DC, DW, EL, ES. For EH and EV, use
# permanent_load_factors_detailed below when the sub-case matters.
permanent_load_factors = {
    "DC": {"Maximum": 1.25, "Minimum": 0.90},
    "DW": {"Maximum": 1.50, "Minimum": 0.65},
    "EH": {"Maximum": 1.50, "Minimum": 0.90},   # Active (governing); see detailed below
    "EL": {"Maximum": 1.00, "Minimum": 1.00},
    "EV": {"Maximum": 1.35, "Minimum": 0.90},   # Retaining structures; see detailed below
    "ES": {"Maximum": 1.50, "Minimum": 0.75}
}

# Detailed sub-case load factors for EH and EV per AASHTO LRFD Table 3.4.1-2.
# EH (Horizontal Earth Pressure) and EV (Vertical Earth Pressure) have multiple
# sub-cases depending on the structural system.  None means "not applicable" (only
# the governing direction applies to that sub-case).
permanent_load_factors_detailed = {
    "EH": {
        "Active":          {"Maximum": 1.50, "Minimum": 0.90},
        "At-Rest":         {"Maximum": 1.35, "Minimum": 0.90},
        "AEP-Anchored":    {"Maximum": 1.35, "Minimum": None},   # Anchored walls only
    },
    "EV": {
        "Overall-Stability":        {"Maximum": 1.00, "Minimum": None},
        "Retaining-Walls":          {"Maximum": 1.35, "Minimum": 1.00},
        "Rigid-Buried-Structure":   {"Maximum": 1.30, "Minimum": 0.90},
        "Rigid-Frames":             {"Maximum": 1.35, "Minimum": 0.90},
        "Flexible-Metallic":        {"Maximum": 1.50, "Minimum": 0.90},  # w/ approved backfill
        "Flexible-Thermoplastic":   {"Maximum": 1.30, "Minimum": 0.90},
    },
}

permanent_loads = [
    "CR", "DR", "DC", "DW", "EH", "EL", "ES", "EV", "PS", "SH"
]

transient_loads = [
    "BL", "BR", "CE", "CT", "CV", "EQ", "FR", "IC", "IM", "LL",
    "LS", "PL", "SE", "TG", "TU", "WA", "WL", "WS"
]

# Create a dataframe with descriptions for load types
load_type_descriptions = {
    "CR": "Force effects due to creep",
    "DR": "Drag load due to settlement of the adjacent ground",
    "DC": "Dead load of structural components and nonstructural attachments",
    "DW": "Dead load of wearing surfaces and utilities",
    "EH": "Horizontal earth pressure load",
    "EL": "Miscellaneous locked-in force effects resulting from the construction process, including jacking apart of cantilevers in segmental construction",
    "ES": "Earth surcharge load",
    "EV": "Vertical pressure from dead load of earth fill",
    "PS": "Secondary forces from post-tensioning for strength limit states; total prestress forces for service limit states",
    "SH": "Force effects due to shrinkage",
    "BL": "Blast Loading",
    "BR": "Vehicular braking force",
    "CE": "Vehicular centrifugal force",
    "CT": "Vehicular collision force",
    "CV": "Vessel collision force",
    "EQ": "Earthquake",
    "FR": "Friction",
    "IC": "Ice load",
    "IM": "Vehicular dynamic load allowance",
    "LL": "Vehicular live load",
    "LS": "Live load surcharge",
    "PL": "Pedestrian live load",
    "SE": "Force effects due to settlement",
    "TG": "Temperature gradient",
    "TU": "Uniform temperature",
    "WA": "Water load and stream pressure",
    "WL": "Wind on live load",
    "WS": "Wind load on structure"
}
