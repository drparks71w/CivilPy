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

"""AASHTO LRFD Bridge Design Specifications — independent design checks.

Each check is a pure function of primitive inputs (kip, inch, ksi) so members
can be "designed" by looping candidate sizes through the checks without any
external software.  The same articles can be verified in AASHTOWare BrR; the
article numbering here mirrors the spec-check classes in BrR's
``aashto.brdr.analyticaltools.spec`` engine so results can be compared
check-for-check.

>>> from civilpy.structural.aashto import lrfd
>>> lrfd.ARTICLES["6.10.8.2.2"]  # doctest: +ELLIPSIS
<function flange_local_buckling_resistance at ...>
"""

from civilpy.structural.aashto.lrfd.core import ARTICLES, CheckResult, article
from civilpy.structural.aashto.lrfd.editions import LRFD_EDITIONS, lrfd_edition
from civilpy.structural.aashto.lrfd.steel import (
    flange_local_buckling_resistance,
    lateral_torsional_buckling_resistance,
    tension_flange_resistance,
    web_shear_resistance,
    hybrid_factor,
    web_load_shedding_factor,
    compact_composite_positive_flexure,
    proportion_limits,
    fatigue_resistance,
    FATIGUE_DETAIL_CATEGORIES,
    tension_member_resistance,
    compression_member_resistance,
    bolt_shear_resistance,
    bolt_slip_resistance,
    bolt_bearing_resistance,
    BOLT_PRETENSION,
    bearing_stiffener_resistance,
    web_bend_buckling,
    constructibility_compression_flange,
    shear_connector_strength,
    shear_connector_fatigue_pitch,
    block_shear_resistance,
    fillet_weld_resistance,
)
from civilpy.structural.aashto.lrfd.concrete import (
    rc_rectangular_flexural_resistance,
    rc_minimum_reinforcement,
    rc_shear_resistance,
    rc_crack_control_spacing,
    rc_crack_control_z_factor,
    rc_mcft_beta_theta,
    MCFTParams,
    rc_min_transverse_reinforcement,
    rc_max_stirrup_spacing,
    rc_longitudinal_reinforcement,
    rc_interface_shear,
    rc_torsion_threshold,
    INTERFACE_SHEAR_CASES,
)
from civilpy.structural.aashto.lrfd.distribution import (
    DistributionFactor,
    longitudinal_stiffness_kg,
    moment_df_interior,
    shear_df_interior,
    moment_df_exterior,
    shear_df_exterior,
    skew_correction_moment,
    skew_correction_shear,
    dynamic_load_allowance,
    effective_flange_width,
    multiple_presence_factor,
    lever_rule_exterior,
)
from civilpy.structural.aashto.lrfd.timber import (
    TIMBER_PHI,
    format_conversion_ckf,
    size_factor_cf,
    incising_factor_ci,
    time_effect_clambda,
    beam_stability_cl,
    bearing_factor_cb,
    timber_flexural_resistance,
)
from civilpy.structural.aashto.lrfd.appendix_a6 import (
    st_venant_j,
    web_plastification_factors,
    a6_flange_local_buckling,
    a6_lateral_torsional_buckling,
    a6_tension_flange_yielding,
)
from civilpy.structural.aashto.lrfd.columns import (
    rc_column_axial_resistance,
    rc_column_reinforcement_limits,
    rc_spiral_reinforcement,
    moment_magnification,
)
from civilpy.structural.aashto.lrfd.railing import (
    TEST_LEVEL_LOADS,
    TestLevelLoad,
    parapet_yield_line_capacity,
    parapet_test_level_check,
    deck_overhang_collision_tension,
)
from civilpy.structural.aashto.lrfd.prestressed import (
    ps_strand_stress_at_nominal,
    ps_flexural_resistance,
    ps_transfer_compression_check,
    ps_transfer_tension_check,
    ps_service_compression_check,
    ps_service_tension_check,
    ps_elastic_shortening_loss,
    ps_approximate_longterm_loss,
    ps_section_age_adjustment,
    ps_refined_loss_shrinkage_girder,
    ps_refined_loss_creep_girder,
    ps_refined_loss_relaxation,
    ps_refined_loss_shrinkage_deck_stage,
    ps_refined_loss_creep_deck_stage,
    ps_deck_shrinkage_gain,
    ps_friction_loss,
    ps_strand_development,
    ps_splitting_resistance,
    ps_anchorage_set_loss,
)
from civilpy.structural.aashto.lrfd.creep_shrinkage import (
    creep_coefficient,
    shrinkage_strain,
    factor_time_development,
)

__all__ = [
    "ARTICLES",
    "CheckResult",
    "article",
    "flange_local_buckling_resistance",
    "lateral_torsional_buckling_resistance",
    "tension_flange_resistance",
    "web_shear_resistance",
    "hybrid_factor",
    "web_load_shedding_factor",
    "compact_composite_positive_flexure",
    "proportion_limits",
    "fatigue_resistance",
    "FATIGUE_DETAIL_CATEGORIES",
    "tension_member_resistance",
    "compression_member_resistance",
    "bolt_shear_resistance",
    "bolt_slip_resistance",
    "bolt_bearing_resistance",
    "BOLT_PRETENSION",
    "rc_rectangular_flexural_resistance",
    "rc_minimum_reinforcement",
    "rc_shear_resistance",
    "rc_crack_control_spacing",
    "rc_crack_control_z_factor",
    "rc_mcft_beta_theta",
    "MCFTParams",
    "rc_min_transverse_reinforcement",
    "rc_max_stirrup_spacing",
    "rc_longitudinal_reinforcement",
    "rc_interface_shear",
    "rc_torsion_threshold",
    "rc_column_axial_resistance",
    "rc_column_reinforcement_limits",
    "rc_spiral_reinforcement",
    "moment_magnification",
    "INTERFACE_SHEAR_CASES",
    "LRFD_EDITIONS",
    "lrfd_edition",
    "TEST_LEVEL_LOADS",
    "TestLevelLoad",
    "TIMBER_PHI",
    "format_conversion_ckf",
    "size_factor_cf",
    "incising_factor_ci",
    "time_effect_clambda",
    "beam_stability_cl",
    "bearing_factor_cb",
    "timber_flexural_resistance",
    "DistributionFactor",
    "longitudinal_stiffness_kg",
    "moment_df_interior",
    "shear_df_interior",
    "moment_df_exterior",
    "shear_df_exterior",
    "skew_correction_moment",
    "skew_correction_shear",
    "dynamic_load_allowance",
    "effective_flange_width",
    "multiple_presence_factor",
    "lever_rule_exterior",
    "st_venant_j",
    "web_plastification_factors",
    "a6_flange_local_buckling",
    "a6_lateral_torsional_buckling",
    "a6_tension_flange_yielding",
    "ps_anchorage_set_loss",
    "bearing_stiffener_resistance",
    "web_bend_buckling",
    "constructibility_compression_flange",
    "shear_connector_strength",
    "shear_connector_fatigue_pitch",
    "block_shear_resistance",
    "fillet_weld_resistance",
    "parapet_yield_line_capacity",
    "parapet_test_level_check",
    "deck_overhang_collision_tension",
    "ps_strand_stress_at_nominal",
    "ps_flexural_resistance",
    "ps_transfer_compression_check",
    "ps_transfer_tension_check",
    "ps_service_compression_check",
    "ps_service_tension_check",
    "ps_elastic_shortening_loss",
    "ps_approximate_longterm_loss",
    "ps_section_age_adjustment",
    "ps_refined_loss_shrinkage_girder",
    "ps_refined_loss_creep_girder",
    "ps_refined_loss_relaxation",
    "ps_refined_loss_shrinkage_deck_stage",
    "ps_refined_loss_creep_deck_stage",
    "ps_deck_shrinkage_gain",
    "ps_friction_loss",
    "ps_strand_development",
    "ps_splitting_resistance",
    "creep_coefficient",
    "shrinkage_strain",
    "factor_time_development",
]
