#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Deprecated alias for :mod:`civilpy.state.ohio.DOT.TIMS`.

Everything that still had a caller was folded into ``DOT/TIMS.py`` in 2026-07;
this module re-exports those names so existing imports keep working. Import
from :mod:`civilpy.state.ohio.DOT.TIMS` instead.

Retired outright (no caller in civilpy, snbi_ui, or the notebooks):
``convert_latitudinal_values``, ``convert_longitudinal_values``,
``convert_place_code``, ``get_cty_from_code``, ``get_df_from_url``,
``get_historic_bridge_data``, ``odot_district_by_county``,
``design_feature_criteria``, ``factors_for_design_feature`` and
``fips_location``. Recover them from git history if one turns out to be needed.
"""

import warnings

from civilpy.state.ohio.DOT.TIMS import (  # noqa: F401
    NBIS_state_codes,
    Project,
    TimsBridge,
    all_labels,
    basemap_labels,
    bridge_file_pattern,
    bridge_labels,
    culvert_file_pattern,
    drainage_labels,
    filter_files_by_category,
    gen_file_pattern,
    geotechnical_labels,
    get_3_digit_st_cd_from_2,
    get_bridge_data_from_tims,
    get_project_data_from_tims,
    help_function,
    landscaping_labels,
    lighting_labels,
    mot_labels,
    odot_counties_by_district,
    ohio_counties,
    roadway_labels,
    row_labels,
    signal_labels,
    state_code_conversion,
    traffic_control_labels,
    utility_labels,
    wall_file_pattern,
    wall_labels,
)

__all__ = [
    "NBIS_state_codes",
    "Project",
    "TimsBridge",
    "all_labels",
    "basemap_labels",
    "bridge_file_pattern",
    "bridge_labels",
    "culvert_file_pattern",
    "drainage_labels",
    "filter_files_by_category",
    "gen_file_pattern",
    "geotechnical_labels",
    "get_3_digit_st_cd_from_2",
    "get_bridge_data_from_tims",
    "get_project_data_from_tims",
    "help_function",
    "landscaping_labels",
    "lighting_labels",
    "mot_labels",
    "odot_counties_by_district",
    "ohio_counties",
    "roadway_labels",
    "row_labels",
    "signal_labels",
    "state_code_conversion",
    "traffic_control_labels",
    "utility_labels",
    "wall_file_pattern",
    "wall_labels",
]

warnings.warn(
    "civilpy.state.ohio.DOT.legacy is deprecated; import from "
    "civilpy.state.ohio.DOT.TIMS instead.",
    DeprecationWarning,
    stacklevel=2,
)
