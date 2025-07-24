AASHTOWARE_TABLES = {
    "ABW_BRIDGE_SUB_LRFDDSN_SETTING": {
        "Used": True,
        "Columns": ['bridge_id', 'lrfd_design_setting_id', 'name', 'descr',
       'bridge_lrfd_factor_id', 'preliminary_design_setting_ind',
       'final_design_setting_ind', 'dynamic_load_allow_method_type',
       'dla_simple_fatigue_frac_impact', 'dla_simple_other_ls_impact',
       'vehicle_summary_display_type', 'last_change_timestamp',
       'limit_num_dsgn_load_combo_ind', 'cw_num_loadcombo_axial_bending',
       'ftg_num_loadcombo_brg_capacity', 'lrfd_analysis_module_guid',
       'lrfd_spec_edition_guid'],
        "Length": 6
    },
    "ABW_MA_STRUSS_ELEM_LOSS_RANGE": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'super_struct_mbr_id',
       'super_struct_spng_mbr_alt_id', 'truss_mbr_alt_element_id',
       'truss_element_loss_range_id', 'ma_struss_elem_loss_range_type',
       'start_dist', 'length', 'spng_mbr_def_id', 'ref_panel_point_id'],
        "Length": 0
    },
    "ABW_MCB_SEG_DECK": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'segment_id',
       'segment_deck_id', 'super_ref_line_type', 'super_ref_line_ref_type',
       'super_ref_line_ref_web_id'],
        "Length": 5
    },
    "ABW_MATL_CONC": {
        "Used": True,
        "Columns": ['bridge_id', 'conc_id', 'name', 'descr', 'si_or_us_type',
       'comp_strength_28', 'initial_comp_strength', 'thermal_exp_coeff',
       'density_dl', 'density_e', 'std_mod_of_elast', 'poisson_ratio',
       'composition_type', 'shear_factor', 'std_initial_mod_of_elast',
       'last_change_timestamp', 'shrinkage_coef', 'lrfd_mod_of_elast',
       'lrfd_initial_mod_of_elast', 'splitting_tensile_strength',
       'lrfd_max_aggregate_size', 'std_mod_of_rupture', 'lrfd_mod_of_rupture'],
        "Length": 16182
    },
    "ABW_MATL_PS_BAR": {
        "Used": True,
        "Columns": ['bridge_id', 'ps_bar_id', 'name', 'descr', 'bar_diameter', 'bar_area',
       'bar_type', 'ultimate_tensile_strength', 'yield_strength',
       'modulus_of_elasticity', 'unit_load_per_length', 'epoxy_coated_ind'],
        "Length": 9
    },
    "ABW_MATL_PS_STRAND": {
        "Used": True,
        "Columns": ['bridge_id', 'matl_ps_strand_id', 'name', 'descr', 'si_or_us_type',
       'strand_type', 'strand_diameter', 'strand_area', 'weight_per_length',
       'ultimate_tensile_strength', 'yield_strength', 'mod_of_elast',
       'transfer_length_lrfd', 'transfer_length_std', 'epoxy_coated_ind',
       'last_change_timestamp'],
        "Length": 2987
    },
    "ABW_FL_FLOORBEAM_TRAVELWAY": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'travelway_id',
       'dist_left_girder_travelway', 'travelway_width'],
        "Length": 4
    },
    "ABW_FLINE_MBR": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'super_struct_mbr_id',
       'fline_location_type', 'length', 'girder_spacing',
       'deck_crack_control_param_z'],
        "Length": 0
    },
    "ABW_MCB_TEND_PROF_DEF_DETAIL": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'segment_id',
       'tendon_profile_id', 'detail_id', 'profile_type',
       'inflect_point_left_percent', 'inflect_point_low_percent',
       'inflect_point_right_percent', 'inflect_point_left_dist',
       'inflect_point_low_dist', 'inflect_point_right_dist',
       'vert_offset_left_end_dist', 'vert_offset_le_meas_from_type',
       'vert_offset_left_dist', 'vert_offset_l_meas_from_type',
       'vert_offset_low_dist', 'vert_offset_lo_meas_from_type',
       'vert_offset_right_dist', 'vert_offset_r_meas_from_type',
       'vert_offset_right_end_dist', 'vert_offset_re_meas_from_type'],
        "Length": 12
    },
    "ABW_STL_ANGLE": {
        "Used": True,
        "Columns": ['bridge_id', 'stl_shape_id', 'angle_size_1', 'angle_size_2',
       'angle_thick', 'nominal_weight_or_mass', 'k', 'area', 'ixx', 'yxx',
       'iyy', 'xyy', 'rzz', 'zztantheta'],
        "Length": 8204
    },
    "ABW_STL_ANGLE_CONN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_BEAM_ASSEMBLY": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'stl_assembly_id',
       'stl_component_id', 'dist'],
        "Length": 230917
    },
    "ABW_WEB_DISTRIB_LOAD": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'segment_id', 'web_id',
       'web_distr_load_id', 'direction_type', 'load_case_id', 'dist', 'length',
       'load_start', 'load_end', 'local_axis_ind', 'ws_field_measured_ind',
       'flexure_percent_of_load', 'shear_percent_of_load', 'description',
       'reference_point_type'],
        "Length": 0
    },
    "BRIDGE": {
        "Used": False,
        "Columns": ['brkey', 'bridge_id', 'struct_num', 'strucname', 'featint', 'fhwa_regn', 'district',
                    'county', 'facility', 'location', 'custodian', 'owner', 'adminarea',
                    'bridgegroup', 'nstatecode', 'n_fhwa_reg', 'bb_pct', 'bb_brdgeid', 'propwork',
                    'workby', 'nbiimpcost', 'nbirwcost', 'nbitotcost', 'nbiyrcost', 'yearbuilt',
                    'yearrecon', 'histsign', 'designload', 'servtypon', 'servtypund', 'sumlanes',
                    'mainspans', 'appspans', 'maxspan', 'length', 'deck_area', 'bridgemed', 'skew',
                    'materialmain', 'designmain', 'materialappr', 'designappr', 'dkstructyp', 'dkmembtype',
                    'dksurftype', 'dkprotect', 'deckwidth', 'lftcurbsw', 'rtcurbsw', 'strflared', 'refvuc', 'refhuc',
                    'hclrurt', 'hclrult', 'lftbrnavcl', 'navcntrol', 'navhc', 'navvc', 'paralstruc', 'tempstruc',
                    'nbislen', 'latitude', 'longitude', 'vclrover', 'vclrunder', 'placecode', 'implen', 'fips_state',
                    'tot_length', 'nextinspid', 'crewhrs', 'flaggerhrs', 'helperhrs', 'snooperhrs', 'spcrewhrs',
                    'spequiphrs', 'on_off_sys', 'ratingdate', 'rater_ini', 'orload', 'ortype', 'irload', 'irtype',
                    'posting', 'req_op_rat', 'def_op_rat', 'fc_detail', 'altorload', 'altormeth', 'altirload',
                    'altirmeth', 'otherload', 'truck1or', 'truck2or', 'truck3or', 'truck1ir', 'truck2ir', 'truck3ir',
                    'srstatus', 'userkey1', 'userkey2', 'userkey3', 'userkey4', 'userkey5', 'userkey6', 'userkey7',
                    'userkey8', 'userkey9', 'userkey10', 'userkey11', 'userkey12', 'userkey13', 'userkey14',
                    'userkey15', 'btrigger', 'traceflag', 'createdatetime', 'createuserkey', 'modtime', 'userkey',
                    'docrefkey', 'notes'],
        "Length": 0
    },
    "COPTIONS": {
        "Used": True,
        "Columns": ['optionname', 'optionval', 'defaultval', 'helpid', 'description'],
        "Length": 1
    },
    "MULTIMEDIA": {
        "Used": True,
        "Columns": [
            'docrefkey', 'sequence', 'context', 'fileloc', 'fileref', 'filetype', 'agencytype', 'status',
            'reportflag', 'userkey1', 'userkey2', 'userkey3', 'userkey4', 'userkey5', 'createdatetime',
            'createuserkey', 'modtime', 'userkey', 'notes'
        ],
        "Length": 1
    },
    "ABW_TRUSS_LINE_MBR": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'truss_location_type', 'length',
                    'truss_spacing', 'settlement_load_case_id', 'deck_crack_control_param_z', 'deck_exposure_factor'],
        "Length": 1
    },
    "ABW_TRUSS_LINE_SUPPORT": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'truss_line_support_id', 'dist', 'x_translation_type',
            'y_translation_type', 'z_rotation_type', 'x_translation_spring_constant', 'y_translation_spring_constant',
            'z_rotation_spring_constant', 'x_translation_settlement', 'y_translation_settlement',
            'z_rotation_settlement', 'override_zrot_spring_const_ind'
        ],
        "Length": 0
    },
    "ABW_TRUSSDEF_ELEMENT_CONC_LOAD": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'truss_def_element_id', 'element_load_id', 'dist',
            'force_x', 'force_y', 'force_z', 'moment_z'
        ],
        "Length": 0
    },
    "ABW_RESULTS_CONC_LS_SUMMARY": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'conc_ls_summary_id', 'flex_type', 'load_type_id', 'vehicle_type',
            'summary_type', 'event_lrfd_factor_id', 'event_ls_id', 'stage_id', 'shear', 'moment', 'horz_shear'
        ],
        "Length": 0
    },
    "ABW_RESULTS_CONC_XSEC_PROP": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'conc_xsec_prop_id', 'moment_sign_type', 'depth',
            'gross_xsection_area', 'gross_moment_of_inertia', 'cracked_neutral_axis_loc', 'cracked_moment_of_inertia',
            'section_modulus_conc_top', 'section_modulus_conc_bot', 'section_modulus_reinf_top',
            'section_modulus_reinf_bot'
        ],
        "Length": 0
    },
    "ABW_LIB_MATL_TIMBER_SAWN_ITEM": {
        "Used": True,
        "Columns": [
            'timber_matl_id', 'sawn_timber_matl_item_id', 'timber_commercial_grade_id', 'timber_size_classification_id',
            'timber_grading_rule_agency_id', 'unit_asd_bending_stress', 'unit_asd_tens_stress_parallel',
            'unit_asd_shear_stress_parallel', 'unit_asd_comp_stress_perp', 'unit_asd_comp_stress_parallel',
            'mod_of_elast', 'density', 'unit_lrfd_bending_stress', 'unit_lrfd_tens_stress_parallel',
            'unit_lrfd_shear_stres_parallel', 'unit_lrfd_comp_stress_perp', 'unit_lrfd_comp_stress_parallel',
            'lrfd_mod_of_elast', 'asd_notes', 'lrfd_notes'
        ],
        "Length": 152
    },
    "ABW_SYS_LRFD_LS": {
        "Used": True,
        "Columns": ['sys_lrfd_ls_id', 'name', 'descr'],
        "Length": 13
    },
    "ABW_SUBSDEF_MODEL_SETTING": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'model_setting_id', 'default_ind', 'num_equal_element_cap_span',
            'num_equal_element_col_seg', 'footing_element_type', 'use_cracked_moi_ind', 'cracked_moi_top_col_wall_pct',
            'cracked_moi_bot_col_wall_pct', 'use_long_stl_reinf_ei_calc_ind', 'prov_moment_rel_col_cap_ind'
        ],
        "Length": 16
    },
    "ABW_SUPER_BR_FORCE_SUB": {
        "Used": False,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'lane_set_id', 'num_lanes', 'braking_force', 'braking_force_ul'],
        "Length": 0
    },
    "ABW_CONC_CURB_SIDEWALK": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'curb_id', 'load_case_id', 'use_type', 'offset_ref_type', 'conc_id',
            'bridge_ref_line_id', 'straight_ind', 'offset_start', 'offset_end', 'bot_width_start', 'top_width_start',
            'bot_width_end', 'top_width_end', 'avg_thick', 'conc_density', 'measured_to_left_face_ind',
            'pedestrian_load'
        ],
        "Length": 1177
    },
    "ABW_CONC_RAILING": {
        "Used": True,
        "Columns": [
            'bridge_id', 'conc_railing_id', 'name', 'descr', 'si_or_us_type', 'barrier_type', 'conc_id', 'x1', 'x2',
            'x3', 'x4', 'x5', 'y1', 'y2', 'y3', 'y4', 'dist_to_cg', 'additional_load', 'conc_density',
            'last_change_timestamp'
        ],
        "Length": 8604
    },
    "ABW_CONC_RAILING_LOC": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'conc_railing_location_id', 'load_case_id', 'offset_ref_type',
            'stl_railing_id', 'conc_railing_id', 'bridge_ref_line_id', 'conc_railing_offset_start',
            'conc_railing_offset_end', 'steel_railing_offset', 'straight_ind', 'conc_railing_face_left_ind',
            'stl_railing_face_left_ind', 'measured_to_front_face_ind'
        ],
        "Length": 16833
    },
    "ABW_BRIDGE_DIAPHRAGM_DEF_CON": {
        "Used": True,
        "Columns": [
            'bridge_id', 'diaphragm_def_id', 'connection_id', 'name', 'support_type', 'y_dist', 'meas_from_type'
        ],
        "Length": 36127
    },
    "ABW_SUBSDEF_FOUND_FK": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'subsdef_found_id', 'as_built_found_alt_id', 'current_found_alt_id'],
        "Length": 34
    },
    "ABW_STL_BUILTUP_IBEAM_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id'],
        "Length": 524
    },
    "ABW_STL_LONG_STIFF": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'stl_component_id', 'stl_angle_shape_id', 'web_weld_id', 'length', 'width',
            'vert_dist', 'vert_dist_by_web_fraction', 'dist_ref_type', 'thick', 'short_leg_attachment_ind',
            'stl_long_stiff_type', 'last_change_timestamp', 'long_stiff_side_type'
        ],
        "Length": 3073
    },
    "ABW_EVENT_VEHICLE_TEMPLATE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'stl_component_id', 'stl_angle_shape_id', 'web_weld_id', 'length', 'width',
            'vert_dist', 'vert_dist_by_web_fraction', 'dist_ref_type', 'thick', 'short_leg_attachment_ind',
            'stl_long_stiff_type', 'last_change_timestamp', 'long_stiff_side_type'
        ],
        "Length": 3073
    },
    "ABW_LEG_ANAL_PT_REINF_CONC": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'leg_id', 'frame_mbr_alt_leg_id', 'anal_pt_id',
            'lrfd_shear_comp_method_type', 'override_shear_reinf_ind', 'percent_shear', 'shear_dist', 'shear_beta',
            'shear_theta', 'shear_sx', 'stirrup_matl_stl_reinf_id', 'stirrup_rebar_id', 'stirrup_num_legs',
            'stirrup_area', 'lfr_ignore_shear_ind'
        ],
        "Length": 0
    },
    "ABW_RESULTS_CRIT_LOAD_LRFD": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'crit_load_lrfd_id', 'stage_id', 'event_lrfd_factor_id', 'event_ls_id',
            'moment_max', 'moment_max_cvehicle_id', 'moment_max_crit_dl_type', 'moment_min', 'moment_min_cvehicle_id',
            'moment_min_crit_dl_type', 'axial_max', 'axial_max_cvehicle_id', 'axial_max_crit_dl_type', 'axial_min',
            'axial_min_cvehicle_id', 'axial_min_crit_dl_type', 'shear_max', 'shear_max_cvehicle_id',
            'shear_max_crit_dl_type', 'shear_min', 'shear_min_cvehicle_id', 'shear_min_crit_dl_type', 'reaction_max',
            'reaction_max_cvehicle_id', 'reaction_max_crit_dl_type', 'reaction_min', 'reaction_min_cvehicle_id',
            'reaction_min_crit_dl_type', 'y_defl_max', 'y_defl_max_cvehicle_id', 'y_defl_max_crit_dl_type',
            'y_defl_min', 'y_defl_min_cvehicle_id', 'y_defl_min_crit_dl_type'
        ],
        "Length": 0
    },
    "ABW_RESULTS_DL_ACTION": {
        "Used": True,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'dl_action_id', 'dead_load_case_id', 'side_type', 'moment', 'axial',
            'shear', 'reaction', 'x_defl', 'y_defl', 'top_flange_moment', 'bot_flange_moment', 'torsion'
        ],
        "Length": 332658
    },
    "ABW_RESULTS_LL_ACTION": {
        "Used": True,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'll_action_id', 'stage_id', 'll_vehicle_id', 'll_vehicle_type',
            'moment_pos', 'moment_neg', 'axial_pos', 'axial_neg', 'shear_pos', 'shear_neg', 'reaction_pos',
            'reaction_neg', 'x_defl_pos', 'x_defl_neg', 'y_defl_pos', 'y_defl_neg', 'reaction_percent_impact_pos',
            'reaction_percent_impact_neg', 'deflection_percent_impact_pos', 'deflection_percent_impact_neg',
            'moment_percent_impact_pos', 'moment_percent_impact_neg', 'shear_percent_impact_pos',
            'shear_percent_impact_neg', 'concurrent_moment_pos', 'concurrent_moment_neg', 'concurrent_shear_pos',
            'concurrent_shear_neg', 'top_flange_moment_pos', 'top_flange_moment_neg', 'bot_flange_moment_pos',
            'bot_flange_moment_neg', 'torsion_pos', 'torsion_neg'
        ],
        "Length": 442877
    },
    "ABW_RESULTS_LS_SUMMARY_DETAIL": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'stl_ls_summary_id', 'ls_summary_detail_id', 'summary_type',
            'flex_moment_resist', 'flex_stress_resist', 'shear_force', 'service_stress_top', 'service_stress_bot',
            'bearing_force'
        ],
        "Length": 0
    },
    "ABW_RESULTS_PS_CONC_STRESS": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'ps_conc_stress_id', 'flex_type', 'load_type_id', 'vehicle_type',
            'summary_type', 'load_combo_type', 'stress_type', 'event_lrfd_factor_id', 'event_ls_id', 'stage_id',
            'top_flng_stress', 'bot_flng_stress', 'deck_stress'
        ],
        "Length": 0
    },
    "ABW_RESULTS_RC_SERVICE_STRESS": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'rc_service_stress_id', 'flex_type', 'load_type_id', 'vehicle_type',
            'summary_type', 'spec_id', 'spec_article_id', 'event_lrfd_factor_id', 'event_ls_id', 'stage_id', 'stress',
            'moment', 'check_required_ind'
        ],
        "Length": 0
    },
    "ABW_RESULTS_SPNG_MBR_ALT_XY": {
        "Used": True,
        "Columns": ['spng_mbr_alt_event_id', 'report_id', 'spng_mbr_alt_xy_id', 'point_id', 'y'],
        "Length": 21380
    },
    "ABW_RESULTS_STL_XSEC_PROP": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'xsection_report_id', 'stl_xsec_prop_id', 'point_id', 'effective_slab_width',
            'effective_slab_thickness', 'depth', 'area', 'moment_of_inertia', 'c_bot', 'section_modulus_top',
            'section_modulus_bot', 'section_modulus_conc', 'section_modulus_reinf'
        ],
        "Length": 0
    },
    "ABW_RIVET_DEF": {
        "Used": True,
        "Columns": [
            'bridge_id', 'rivet_def_id', 'name', 'descr', 'rivet_type', 'undriven_rivet_diameter', 'hole_diameter',
            'fu', 'last_change_timestamp'
        ],
        "Length": 7
    },
    "ABW_RSLT_CONCURRENT_LL_ACTION": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'concurrent_ll_action_id', 'll_vehicle_type', 'basis_envelope_type',
            'envelope_pos_neg_type', 'll_vehicle_id', 'vehicle_lead_axle_loc', 'vehicle_direction_type', 'moment',
            'shear', 'axial', 'y_defl'
        ],
        "Length": 0
    },
    "ABW_SHEAR_CONN_CHANNEL_FIELD": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'shear_conn_id', 'stl_channel_id', 'channel_length',
            'long_spacing'
        ],
        "Length": 0
    },
    "ABW_FLOORSYS_UNIT_GEOMETRY": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'unit_geometry_id', 'unit_num', 'floorsys_stringer_group_def_id',
            'mirror_stringer_group_def_type', 'ref_floor_beam_mbr_loc_id', 'unit_ref_type',
            'dist_start_stringer_group_def', 'current_mbr_alt_name_template', 'existing_mbr_alt_name_template'
        ],
        "Length": 571
    },
    "ABW_FLRBM_STRINGER_DL_REACTION": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'floor_beam_mbr_id', 'dl_reaction_id', 'stringer_mbr_id', 'stage_id',
            'user_defined_reaction', 'override_computed_ind', 'up_to_date_ind'
        ],
        "Length": 21990
    },
    "ABW_PIER_WSHFT_SHEAR_REINF": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'wall_shaft_id', 'shear_reinf_id', 'rebar_id', 'stl_reinf_id',
            'trans_num_legs', 'long_num_legs', 'start_dist', 'num_spaces', 'bar_spacing'
        ],
        "Length": 0
    },
    "ABW_MULTIMEDIA": {
        "Used": True,
        "Columns": [
            'bridge_id', 'multimedia_id', 'context', 'fileloc', 'fileref', 'filetype', 'agency_type_param_id', 'status',
            'reportflag', 'userkey1', 'userkey2', 'userkey3', 'userkey4', 'userkey5', 'notes', 'creation_event_id',
            'last_modified_event_id'
        ],
        "Length": 7
    },
    "ABW_LIB_MATL_SOIL": {
        "Used": True,
        "Columns": [
            'soil_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'soil_unit_load', 'sat_soil_unit_load',
            'lrfd_lrfr_at_rest_lep_coeff', 'lrfd_lrfr_active_lep_coeff', 'lrfd_lrfr_passive_lep_coeff',
            'lfr_max_lat_soil_press', 'lfr_min_lat_soil_press', 'lrfr_at_rest_lep_coeff'
        ],
        "Length": 2
    },
    "ABW_LIB_MATL_ALUMINUM": {
        "Used": True,
        "Columns": ['aluminum_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'yield_strength', 'tens_strength', 'thermal_exp_coeff', 'density', 'mod_of_elast'],
        "Length": 4
    },
    "ABW_MATL_TIMBER": {
        "Used": True,
        "Columns": [
            'bridge_id', 'timber_id', 'name', 'descr', 'si_or_us_type', 'matl_timber_type', 'density',
            'grading_method_type', 'last_change_timestamp'
        ],
        "Length": 85
    },
    "ABW_MATL_SOIL": {
        "Used": True,
        "Columns": [
            'bridge_id', 'soil_id', 'name', 'descr', 'si_or_us_type', 'soil_unit_load', 'sat_soil_unit_load',
            'lrfd_lrfr_at_rest_lep_coeff', 'lrfd_lrfr_active_lep_coeff', 'lrfd_lrfr_passive_lep_coeff',
            'lfr_max_lat_soil_press', 'lfr_min_lat_soil_press', 'lrfr_at_rest_lep_coeff'
        ],
        "Length": 1258
    },
    "ABW_METAL_PIPE_CULVERT_DEF": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'culvert_def_id', 'metal_pipe_culvert_struct_type',
            'ncspa_struct_category_type', 'dd_backfill_material_type', 'dd_relative_compaction',
            'lrfr_cons_dd_plastic_mom_ind', 'lrfr_cons_mult_load_ln_ind', 'lfr_cons_dd_plastic_mom_ind',
            'lfr_cons_mult_load_ln_ind', 'span_length', 'rise', 'rise_above_haunch', 'actual_top_radius_type',
            'straight_edge_length', 'mid_ordinate', 'actual_top_radius', 'material_type', 'section_properties_name',
            'section_properties_thickness', 'section_properties_area', 'section_properties_radius',
            'section_properties_i', 'section_properties_mp', 'section_properties_seam_str', 'pipe_crown_deflections',
            'buckling_str_adjust_factor', 'seam_str_adjust_factor', 'percent_thickness_remaining', 'average_depth_fill',
            'minimum_cover_depth', 'water_height', 'clear_roadway_width', 'matl_stl_structural_id', 'matl_aluminum_id',
            'pavement_reduct_factor', 'pavement_reduct_fact_comment', 'wearing_surface_density',
            'wearing_surface_thickness', 'thickness_field_measured_ind', 'section_properties_gage'
        ],
        "Length": 64
    },
    "ABW_CULVERT": {
        "Used": True,
        "Columns": [
            'bridge_id', 'bridge_design_alt_id', 'culvert_id', 'name', 'descr', 'dist', 'offset', 'angle',
            'start_station', 'last_modified_event_id', 'creation_event_id', 'last_change_timestamp',
            'vehicle_path_long_increment'
        ],
        "Length": 1219
    },
    "ABW_SYS_LRFR_LOADING": {
        "Used": True,
        "Columns": ['sys_lrfr_loading_id', 'name', 'descr'],
        "Length": 3
    },
    "ABW_SYS_LRFR_LOAD_GROUP": {
        "Used": True,
        "Columns": ['sys_lrfr_load_group_id', 'name', 'descr'],
        "Length": 5
    },
    "ABW_SYS_REPORT": {
        "Used": True,
        "Columns": [
            'sys_report_id', 'descr', 'report_keyword_1_id', 'report_keyword_2_id', 'report_keyword_3_id',
            'report_keyword_4_id', 'report_keyword_5_id', 'report_keyword_6_id', 'stored_unit_id', 'si_unit_id',
            'us_unit_id', 'data_type'
        ],
        "Length": 3
    },
    "ABW_SYS_REPORT_KEYWORD": {
        "Used": False,
        "Columns": ['report_keyword_id', 'keyword', 'descr'],
        "Length": 0
    },
    "ABW_SYS_SUBTYPE_TABLES": {
        "Used": True,
        "Columns": ['subtype_table_id', 'table_name', 'type_define', 'type_identifier', 'discriminator_col'],
        "Length": 226
    },
    "ABW_SUPER_FR_FORCE_SUB": {
        "Used": False,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'fr_force_set_id', 'span_location_type'],
        "Length": 0
    },
    "ABW_SUPER_LL_PATTERN_SUB": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'll_pattern_id', 'load_pattern_number', 'descr'],
        "Length": 0
    },
    "ABW_SUPER_LOAD_SCENARIO": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'load_scenario_id', 'name', 'descr'],
        "Length": 14954
    },
    "ABW_SUPER_LOAD_SCENARIO_ITEM": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'load_scenario_id', 'load_scenario_item_id', 'load_case_id'],
        "Length": 48545
    },
    "ABW_SUPER_PED_LL_REACT_SUB": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'ped_ll_set_id', 'span_location_type', 'use_override_values_ind'],
        "Length": 4
    },
    "ABW_PIER_WSHFT_FLEX_REINF": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'wall_shaft_id', 'reinf_set_id', 'start_dist', 'straight_length',
            'reinf_pattern_def_id', 'hook_at_start_ind', 'hook_at_end_ind', 'developed_at_start_ind',
            'developed_at_end_ind', 'reinf_set_num', 'follows_profile_ind', 'head_at_start_ind', 'head_at_end_ind'
        ],
        "Length": 0
    },
    "ABW_PIER_WSHFT_RECT_XSECT": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'wall_shaft_id', 'wall_shaft_xsection_id', 'width', 'depth'],
        "Length": 0
    },
    "ABW_PIER_WSHFT_REINF_PATT_DET": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'wall_shaft_id', 'reinf_pattern_def_id', 'reinf_bar_id', 'rebar_id',
            'stl_reinf_id', 'bundle_type', 'x_coordinate', 'y_coordinate'
        ],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_DIAPH_MBR": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'left_spng_mbr_id', 'right_spng_mbr_id',
            'left_spng_mbr_dist', 'right_spng_mbr_dist', 'diaph_def_id'
        ],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_LOADING_PATH": {
        "Used": True,
        "Columns": [
            'bridge_id', 'bridge_design_alt_id', 'super_struct_id', 'loading_path_id', 'nsg_vehicle_path_type',
            'nsg_vehicle_cen_line_loc', 'adjacent_vehicle_path_type', 'adjacent_vehicle_cen_line_loc'
        ],
        "Length": 10577
    },
    "ABW_PIER_COL_REINF_PATTERN_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'pier_column_id', 'reinf_pattern_def_id', 'name', 'bundled_bars_ind'],
        "Length": 12
    },
    "ABW_STL_TRUSS_XSECTION_CPLATE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'element_xsection_id', 'cover_plate_id', 'width', 'thick',
            'relative_position', 'stl_structural_id', 'side_weld_id', 'end_weld_id', 'bolt_rivet_hole_size',
            'bolt_rivet_hole_effective_num', 'bolt_rivet_eff_area_deduction'
        ],
        "Length": 2
    },
    "ABW_STL_WEB_COVER_PLATE": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'stl_component_id', 'length', 'relative_position', 'depth_start',
            'depth_end', 'depth_variation_type'
        ],
        "Length": 0
    },
    "ABW_STL_WEB_LOSS_RANGE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'range_id', 'percent_thick_loss'],
        "Length": 733
    },
    "ABW_STL_WEB_PLATE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'stl_component_id', 'end_weld_id', 'length', 'depth_start', 'depth_end',
            'depth_variation_type'
        ],
        "Length": 25968
    },
    "ABW_STL_XSECTION": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'xsection_id', 'name', 'xsection_type', 'web_depth',
            'web_thick', 'flng_thick_bot', 'flng_thick_top', 'flng_width_bot', 'flng_width_top', 'top_offset',
            'bot_offset', 'top_angle_shape_id', 'bot_angle_shape_id', 'top_angle_horz_leg_thick',
            'top_angle_horz_leg_length', 'top_angle_vert_leg_length', 'top_angle_vert_leg_thick',
            'bot_angle_horz_leg_length', 'bot_angle_horz_leg_thick', 'bot_angle_vert_leg_length',
            'bot_angle_vert_leg_thick', 'web_stl_id', 'top_flng_stl_id', 'bot_flng_stl_id', 'stl_shape_id',
            'stl_shape_stl_id', 'top_angle_stl_id', 'bot_angle_stl_id', 'deck_conc_id', 'deck_eff_width_lrfd',
            'deck_eff_width_std', 'deck_eff_thick', 'haunch_dim_type', 'deck_composite_ind', 'top_flng_web_weld_id',
            'bot_flng_web_weld_id', 'web_bolt_hole_size', 'web_top_bolt_hole_num', 'web_bot_bolt_hole_num',
            'top_flng_bolt_hole_size', 'top_flng_bolt_hole_num', 'bot_flng_bolt_hole_size', 'bot_flng_bolt_hole_num',
            'modular_ratio', 'haunch_width', 'haunch_thick', 'deck_actual_thick', 'deck_tributary_width',
            'use_no_detail_properties_ind', 'no_detail_stl_area', 'no_detail_stl_moi', 'no_detail_stl_section_modulus',
            'no_detail_stl_id', 'xsection_deck_type', 'generic_deck_density', 'generic_deck_thick',
            'generic_deck_tributary_width', 'deck_timber_id', 'deck_nail_id', 'adj_tdeck_shear_factor',
            'adj_tdeck_flex_wet_service', 'adj_tdeck_shear_wet_service', 'adj_tdeck_compr_wet_service',
            'adj_tdeck_mod_wet_service', 'adj_tdeck_size_factor', 'adj_tdeck_volume_factor',
            'adj_tdeck_flat_use_factor', 'adj_tdeck_rep_use_factor', 'adj_tdeck_load_sharing_factor',
            'adj_tdeck_load_dur_factor', 'tdeck_total_thick', 'tdeck_plank_width', 'tdeck_lamination_width',
            'tdeck_tributary_width', 'tdeck_nominal_thick', 'tdeck_nominal_width', 'lfd_timber_ll_dist_dist_width',
            'shear_flex_moisture_cond_type', 'bearing_moisture_cond_type', 'stiffness_moisture_cond_type',
            'timber_deck_type', 'deck_load_case_id', 'deck_loadcase_engineassign_ind'
        ],
        "Length": 8311
    },
    "ABW_ANALYSIS_EVENT": {
        "Used": True,
        "Columns": [
            'event_id', 'analysis_method_type', 'analysis_event_type', 'structural_analysis_type',
            'nsg_vehicle_path_type', 'nsg_vehicle_cen_line_loc', 'adjacent_vehicle_path_type',
            'adjacent_vehicle_cen_line_loc', 'std_ll_ss_df_compute_type', 'lrfr_permit_lane_load',
            'lrfr_exc_permit_lane_load_ind', 'lane_impact_loading_type', 'genpref_template_id',
            'adjacent_veh_live_load_fact', 'td_fea_analysis_option_type'
        ],
        "Length": 204
    },
    "ABW_STL_THREADED_BAR": {
        "Used": False,
        "Columns": ['bridge_id', 'stl_component_id', 'struct_def_id', 'diameter', 'num_bars', 'end_config_type'],
        "Length": 0
    },
    "ABW_STL_TRANS_STIFF_ANGLE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'stl_component_id', 'stl_shape_id', 'vert_direction_ind',
            'short_leg_attachment_ind', 'num_bolts', 'dist_top_bolt', 'dist_bot_bolt', 'dist_from_top_flnge',
            'dist_from_bot_flnge', 'bolt_def_id'
        ],
        "Length": 463
    },
    "ABW_STL_TRANS_STIFF_GNRL_RANGE": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'stiff_range_id', 'dist', 'length', 'max_spacing',
            'stl_component_id'
        ],
        "Length": 0
    },
    "ABW_STL_TRANS_STIFF_LOC_RANGE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'stiff_range_id', 'stl_component_id', 'dist', 'spacing', 'num_stiff'],
        "Length": 224091
    },
    "ABW_CHECKED_OUT_BRIDGE": {
        "Used": False,
        "Columns": ['bridge_check_out_id', 'bridge_id', 'event_id'],
        "Length": 0
    },
    "ABW_STL_TRANS_STIFF_PLATE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'stl_component_id', 'top_flng_weld_id', 'bot_flng_weld_id', 'web_weld_id',
            'width', 'dist_from_top_flng', 'dist_from_bot_flng', 'out_clip_length_top', 'out_clip_length_bot',
            'ins_clip_horz_length_top', 'ins_clip_vert_length_top', 'ins_clip_horz_length_bot',
            'ins_clip_vert_length_bot', 'thick'
        ],
        "Length": 8248
    },
    "ABW_ADV_CONC_TENDON_RANGE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'tendon_range_id', 'tendon_profile_id', 'stage_id'
        ],
        "Length": 48
    },
    "ABW_DECK_PANEL_RATING_RESULTS": {
        "Used": False,
        "Columns": [
            'deck_panel_analysis_event_id', 'rating_results_summary_id', 'vehicle_id', 'vehicle_type',
            'design_method_type', 'rating_success_type', 'inv_capacity', 'opr_capacity', 'post_capacity',
            'safe_capacity', 'inv_rf', 'opr_rf', 'post_rf', 'safe_rf', 'inv_location', 'opr_location', 'post_location',
            'safe_location', 'inv_limit_state', 'opr_limit_state', 'post_limit_state', 'safe_limit_state',
            'lane_loading_type', 'impact_loading_type', 'results_flag_type', 'span_num', 'range_left_dist',
            'range_right_dist'
        ],
        "Length": 0
    },
    "ABW_DEF_ANAL_OPTION_SUBS_LOAD": {
        "Used": False,
        "Columns": [
            'bridge_id', 'bridge_design_alt_id', 'vehicle_id', 'sub_struct_loading_id', 'vehicle_type', 'axle_load'
        ],
        "Length": 0
    },
    "ABW_DESIGNRATIO_RESULT": {
        "Used": False,
        "Columns": [
            'spng_mbr_alt_event_id', 'point_id', 'rating_results_id', 'vehicle_id', 'vehicle_type',
            'design_method_type', 'design_capcity_type', 'design_capacity_force', 'design_capacity_stress',
            'design_capacity_moment', 'design_capacity_deflection', 'design_capacity_distance', 'design_capacity_area',
            'permit_capcity_type', 'permit_capacity_stress', 'permit_capacity_moment', 'permit_capacity_deflection',
            'permit_capacity_distance', 'permit_capacity_area', 'permit_capacity_force', 'fatigue_capcity_type',
            'fatigue_capacity_stress', 'fatigue_capacity_moment', 'fatigue_capacity_deflection',
            'fatigue_capacity_distance', 'fatigue_capacity_area', 'fatigue_capacity_force', 'design_design_ratio',
            'permit_design_ratio', 'fatigue_design_ratio', 'design_limit_state', 'permit_limit_state',
            'fatigue_limit_state', 'design_article_name', 'permit_article_name', 'fatigue_article_name'
        ],
        "Length": 0
    },
    "ABW_DIAPH_LOC": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'diaph_loc_id', 'left_spng_mbr_id', 'right_spng_mbr_id', 'left_spng_mbr_dist',
            'right_spng_mbr_dist', 'num_spaces', 'spacing', 'diaph_def_id', 'diaph_weight', 'diaphragm_def_id',
            'spacing_reference_type', 'curved_sys_left_spacing', 'curved_sys_right_spacing'
        ],
        "Length": 288711
    },
    "ABW_MBR_ALT_SUPPORT": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'super_struct_spng_mbr_alt_id', 'mbr_alt_support_id',
            'support_id', 'bearing_dist_left', 'bearing_dist_right', 'timber_brg_area_length', 'timber_brg_area_width'
        ],
        "Length": 32814
    },
    "ABW_BMDEF_ANAL_PT_STL": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'anal_pt_id', 'web_angle', 'trans_stiff_spacing',
            'trans_stiff_thick', 'trans_stiff_width', 'trans_stiff_stl_id', 'tens_field_action_ind', 'long_stiff_ind',
            'unsupported_length_flng', 'moi_net', 'dist_centroid', 'long_stiff_width', 'long_stiff_thick',
            'long_stiff_stl_id', 'web_net_area', 'percent_area_top_flng', 'bearing_stiff_stl_id',
            'allowable_shear_top_plate', 'allowable_shear_bot_plate', 'percent_area_bot_flng', 'bearing_stiff_clip',
            'bearing_stiff_thick', 'bearing_stiff_width', 'lateral_support_brace_ind', 'dist_cross_frame_left',
            'dist_cross_frame_right', 'allowable_fatigue', 'mbr_bolt_spacing_type', 'surface_type',
            'additional_fasteners_top_ind', 'additional_fasteners_bot_ind', 'number_stress_cycles', 'rh_bot_rebar',
            'rh_top_rebar', 'num_fatigue_cycles', 'bearing_stiff_num_pairs', 'bearing_stiff_spacing',
            'long_stiff_vert_dist', 'trans_stiff_num', 'bearing_stiff_attachment_type', 'long_stiff_vert_dist_ref_type',
            'override_diaph_ind', 'dist_diaph_left', 'dist_diaph_right', 'diaph_at_point_ind', 'trans_stiff_type',
            'override_long_stiff_ind', 'override_trans_stiff_ind', 'override_bearing_stiff_ind'
        ],
        "Length": 6
    },
    "ABW_METAL_BOX_CULVERT_DEF": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'culvert_def_id', 'span', 'rise', 'rc', 'rh', 'delta', 'd', 'l',
            'height_of_cover', 'material_type', 'section_properties_name', 'section_properties_mp_crown',
            'section_properties_mp_haunch', 'mp_crown_adjustment_factor', 'mp_haunch_adjustment_factor',
            'stl_structural_id', 'aluminum_id', 'pavement_reduct_factor', 'pavement_reduct_fact_comment',
            'wearing_surface_density', 'wearing_surface_thickness', 'thickness_field_measured_ind'
        ],
        "Length": 4
    },
    "ABW_MBR_ALT_TIMBER_DECK_RANGE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'super_struct_spng_mbr_alt_id', 'deck_range_id',
            'dist', 'length', 'timber_deck_type', 'deck_timber_id', 'deck_total_thick', 'deck_plank_width',
            'deck_lamination_width', 'deck_tributary_width_start', 'deck_tributary_width_end', 'deck_nail_id',
            'lfd_timber_ll_dist_dist_width', 'adj_deck_shear_factor', 'adj_deck_flex_wet_service',
            'adj_deck_shear_wet_service', 'adj_deck_compr_wet_service', 'adj_deck_mod_wet_service',
            'adj_deck_size_factor', 'adj_deck_volume_factor', 'adj_deck_flat_use_factor', 'adj_deck_rep_use_factor',
            'adj_deck_load_sharing_factor', 'adj_deck_load_dur_factor', 'shear_flex_moisture_cond_type',
            'bearing_moisture_cond_type', 'stiffness_moisture_cond_type', 'deck_nominal_thick', 'deck_nominal_width'
        ],
        "Length": 184
    },
    "ABW_MBR_ALT_TRUSS_LINE_SUPPORT": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'super_struct_spng_mbr_alt_id', 'support_id',
            'truss_line_support_id', 'bearing_dist_left', 'bearing_dist_right', 'timber_brg_area_length',
            'timber_brg_area_width'
        ],
        "Length": 0
    },
    "ABW_MBR_COLUMN_STIFFNESS": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'column_stiffness_id', 'column_mbr_id',
            'percent_stiffness'
        ],
        "Length": 0
    },
    "ABW_MBR_CONCENT_LOAD": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'mbr_concent_load_id', 'dist', 'force_x', 'force_y',
            'force_z', 'moment_x', 'moment_y', 'moment_z', 'load_case_id', 'local_axis_ind', 'flexure_percent_of_load',
            'shear_percent_of_load', 'description', 'apply_to_full_box_only_ind'
        ],
        "Length": 13902
    },
    "ABW_FRAME_COLUMN_MBR": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'support_line_id', 'frame_leg_def_id', 'name',
            'description', 'angle', 'length', 'column_distance_display_type', 'distance', 'x_translation_type',
            'y_translation_type', 'z_translation_type', 'x_rotation_type', 'y_rotation_type', 'z_rotation_type',
            'x_translation_spring_constant', 'y_translation_spring_constant', 'z_translation_spring_constant',
            'x_rotation_spring_constant', 'y_rotation_spring_constant', 'z_rotation_spring_constant',
            'x_translation_settlement', 'y_translation_settlement', 'z_translation_settlement', 'x_rotation_settlement',
            'y_rotation_settlement', 'z_rotation_settlement', 'settlement_load_case_id', 'bent_cap_width'
        ],
        "Length": 0
    },
    "ABW_FRAME_LEG_BRACE_LOC": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'leg_brace_loc_id', 'right_spng_mbr_id', 'right_leg_id', 'left_spng_mbr_id',
            'left_leg_id', 'left_leg_dist', 'right_leg_dist', 'num_spaces', 'spacing', 'brace_weight'
        ],
        "Length": 0
    },
    "ABW_FRAME_LEG_MBR_DEF": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'frame_leg_def_id', 'frame_leg_mbr_def_type', 'name', 'descr',
            'additional_self_weight', 'conn_self_weight_percent', 'creation_event_id', 'last_modified_event_id',
            'comment_id'
        ],
        "Length": 0
    },
    "ABW_FRAME_MBR_LEG": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'leg_id', 'name', 'descr',
            'frame_joint_support_line_id', 'fline_joint_node_id', 'angle', 'length', 'x_translation_type',
            'y_translation_type', 'z_translation_type', 'x_rotation_type', 'y_rotation_type', 'z_rotation_type',
            'x_translation_spring_constant', 'y_translation_spring_constant', 'z_translation_spring_constant',
            'x_rotation_spring_constant', 'y_rotation_spring_constant', 'z_rotation_spring_constant',
            'x_translation_settlement', 'y_translation_settlement', 'z_translation_settlement', 'x_rotation_settlement',
            'y_rotation_settlement', 'z_rotation_settlement', 'bent_cap_width'
        ],
        "Length": 0
    },
    "ABW_MCB_SEG_CONC_CURB_SIDEWALK": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'segment_id', 'curb_id', 'load_case_id', 'use_type',
            'offset_ref_type', 'conc_id', 'straight_ind', 'offset_start', 'offset_end', 'bot_width_start',
            'top_width_start', 'bot_width_end', 'top_width_end', 'avg_thick', 'conc_density',
            'measured_to_left_face_ind', 'pedestrian_load', 'bridge_ref_line_id'
        ],
        "Length": 1
    },
    "ABW_DECK_PANEL_EVENT_ERRORS": {
        "Used": False,
        "Columns": ['deck_panel_analysis_event_id', 'error_id', 'component_guid', 'component_error_id'],
        "Length": 0
    },
    "ABW_FLNG_LAT_BEND_STRESS_SUP": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'super_struct_spng_mbr_alt_id',
            'flng_lat_bend_stress_id', 'flng_lat_bend_stress_sup_id', 'support_num', 'girder_reaction_adj_factor'
        ],
        "Length": 17631
    },
    "ABW_STRGRP_LL_DISTFACT_RANGE": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'floorsys_stringer_group_def_id', 'template_id', 'range_id', 'dist', 'length',
            'single_lane_ll_distfactor', 'multi_lane_ll_distfactor', 'action_type'
        ],
        "Length": 0
    },
    "ABW_STRINGER_DL_REACT_DETAIL": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'floor_beam_mbr_id', 'dl_reaction_id', 'dl_reaction_detail_id', 'dl_case_id',
            'computed_reaction', 'results_timestamp'
        ],
        "Length": 43741
    },
    "ABW_CONC_BMDEF_SECTION_PROFILE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'section_profile_id', 'start_distance', 'length', 'start_width', 'end_width', 'conc_id', 'modular_ratio'],
        "Length": 3592
    },
    "ABW_CONC_BMDEF_VOID_RANGE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'void_range_id', 'section_pattern_id', 'start_distance',
            'length'
        ],
        "Length": 17
    },
    "ABW_CONC_BMDEF_WEB_PROFILE": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'web_profile_id', 'start_dist', 'length', 'start_depth',
            'end_depth', 'web_depth_variation_type', 'top_begin_width', 'top_end_width', 'bottom_begin_width',
            'bottom_end_width'
        ],
        "Length": 4292
    },
    "ABW_PS_PRECAST_BEAM_DEF": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'ps_precast_beam_def_type', 'curing_method_type',
            'curing_time', 'ignore_pos_supp_mom_rating_ind', 'lrfd_loss_calc_method_type', 'lrfr_loss_calc_method_type',
            'lfr_shear_comp_method_type', 'lrfr_cons_leg_tens_stlstrs_ind', 'lrfd_multispan_analysis_type',
            'lrfr_multispan_analysis_type', 'lfr_cons_mom_cap_reduct_ind', 'lrfd_cons_split_resist_art_ind',
            'lrfr_cons_split_resist_art_ind', 'lrfr_ignore_tens_rate_top_ind', 'asr_con_deck_reinf_devlen_ind',
            'lfr_con_deck_reinf_devlen_ind', 'lrfr_con_deck_reinf_devlen_ind', 'lrfd_con_deck_reinf_devlen_ind',
            'lrfr_mod_mcft_size_effect_ind', 'stl_brng_pl_emb_st_gr_end_ind', 'allow_cracking_girder_ends_ind'
        ],
        "Length": 1638
    },
    "ABW_CONC_BMDEF_WEB_WIDTH": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'web_width_id', 'top_begin_width', 'top_end_width',
            'bot_begin_width', 'bot_end_width', 'beam_def_support_id', 'start_dist', 'length'
        ],
        "Length": 10
    },
    "ABW_CONC_BMDF_VOID_SEC_PAT_DET": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'section_pattern_id', 'pattern_detail_id',
            'dist_left_edge', 'num_spaces', 'void_spacing', 'void_diameter'
        ],
        "Length": 4
    },
    "ABW_STL_STRUCT_TEE": {
        "Used": True,
        "Columns": ['bridge_id', 'stl_shape_id', 'shape_type', 'nominal_weight_or_mass', 'area', 'tee_depth_d', 'stem_thick_tw', 'stem_area', 'flng_width_bf', 'flng_thick_tf', 'dist_k', 'dist_y_to_cg', 'ixx', 'iyy'],
        "Length": 194
    },
    "ABW_SUB_STRUCT_WA_BUOYANCY": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'sub_wa_buoy_id', 'sys_design_water_level_id', 'sub_struct_def_component_id', 'calc_buoy_submerge_vol', 'calc_buoy_force', 'ovr_buoy_submerge_vol', 'ovr_buoy_force'],
        "Length": 0
    },
    "ABW_SUB_STRUCT_WA_STREAM_PRESS": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'sub_wa_stream_pressure_id', 'sys_design_water_level_id', 'calc_long_stream_pressure', 'calc_trans_stream_pressure', 'ovr_long_stream_pressure', 'ovr_trans_stream_pressure'],
        "Length": 0
    },
    "ABW_SUB_STRUCT_WS_LOAD": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'sub_ws_load_id', 'sub_struct_def_component_id', 'design_height_z', 'wind_pressure_pd', 'height_operator_type', 'comparison_height', 'sys_design_water_level_id', 'wind_pressure_pz', 'sys_lrfd_ls_id'],
        "Length": 123
    },
    "ABW_SUB_STRUCT_WS_SKEW": {
        "Used": True,
        "Columns": [
            'bridge_id', 'struct_def_id', 'sub_ws_load_id', 'skew_angle_id', 'skew_angle', 'calc_wind_press_pd_long',
            'calc_wind_press_pd_trans', 'ovr_wind_press_pd_long', 'ovr_wind_press_pd_trans',
            'calc_wind_press_pd_long_ul', 'calc_wind_press_pd_trans_ul', 'ovr_wind_press_pd_long_ul',
            'ovr_wind_press_pd_trans_ul', 'calc_wind_press_pz_long', 'calc_wind_press_pz_trans',
            'ovr_wind_press_pz_long', 'ovr_wind_press_pz_trans', 'calc_wind_press_pz_long_ul',
            'calc_wind_press_pz_trans_ul', 'ovr_wind_press_pz_long_ul', 'ovr_wind_press_pz_trans_ul'
        ],
        "Length": 615
    },
    "ABW_SUBS_STREAM_FLOW": {
        "Used": True,
        "Columns": ['bridge_id', 'bridge_design_alt_id', 'sub_struct_id', 'stream_flow_info_id', 'sys_design_water_level_id', 'water_elevation', 'design_velocity', 'scour_elevation', 'consider_ice_dynamic_ind', 'consider_ice_hanging_dam_ind', 'consider_ice_jam_ind', 'consider_ice_adhesion_ind', 'consider_stream_flow_ind'],
        "Length": 7680
    },
    "ABW_SUBSALT_DLA_LIMIT_STATE": {
        "Used": False,
        "Columns": ['bridge_id', 'bridge_design_alt_id', 'sub_struct_id', 'sub_struct_alt_id', 'dla_limit_state_id', 'lrfd_factor_id', 'ls_id', 'impact_factor'],
        "Length": 0
    },
    "ABW_MCB_WEB_SHEAR_REINF_RANGE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'segment_id', 'web_id', 'range_id', 'span_num', 'shear_reinf_def_id', 'start_dist', 'num_spaces', 'spacing'],
        "Length": 197
    },
    "ABW_MCELL_BOX_BDEF_SLAB_REINF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'segment_id', 'reinf_id', 'reinf_type', 'overhang_type', 'cell_type', 'cell_num', 'stl_reinf_id', 'ref_point_type', 'support_midspan_num', 'trans_ref_line_id', 'direction_type', 'start_distance', 'length', 'num_bars', 'num_bars_left_web', 'rebar_id', 'clear_cover', 'measured_from_type', 'bar_spacing', 'side_cover', 'start_fully_developed_ind', 'end_fully_developed_ind', 'head_at_start_ind', 'head_at_end_ind'],
        "Length": 69
    },
    "ABW_MULTI_CELL_BOX_BDEF_WEB_FK": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'segment_id', 'web_id', 'same_as_web_id'],
        "Length": 29
    },
    "ABW_RESULTS_CRIT_LOAD_LFR": {
        "Used": True,
        "Columns": ['spng_mbr_alt_event_id', 'point_id', 'crit_load_lfr_id', 'load_group_id', 'stage_id', 'moment_max', 'moment_max_cvehicle_id', 'moment_min', 'moment_min_cvehicle_id', 'axial_max', 'axial_max_cvehicle_id', 'axial_min', 'axial_min_cvehicle_id', 'shear_max', 'shear_max_cvehicle_id', 'shear_min', 'shear_min_cvehicle_id', 'reaction_max', 'reaction_max_cvehicle_id', 'reaction_min', 'reaction_min_cvehicle_id', 'y_defl_max', 'y_defl_max_cvehicle_id', 'y_defl_min', 'y_defl_min_cvehicle_id'],
        "Length": 16875
    },
    "ABW_SUPER_STRUCT_ALT": {
        "Used": True,
        "Columns": ['bridge_id', 'bridge_design_alt_id', 'super_struct_id', 'super_struct_alt_id', 'name', 'descr', 'struct_def_id', 'last_modified_event_id', 'creation_event_id', 'comment_id', 'last_change_timestamp'],
        "Length": 13647
    },
    "ABW_GUSSET_PARTIAL_SHEAR_PLANE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'gusset_def_id', 'gusset_plate_def_id', 'gusset_partial_shear_plane_id', 'gusset_plate_member_def_id', 'shear_plane_direction_type', 'length', 'thickness', 'advanced_options_ind', 'override_angle'],
        "Length": 77
    },
    "ABW_SUPER_STRUCT_DL_REACT_SUB": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'dl_reaction_set_id', 'span_location_type', 'up_to_date_ind', 'results_timestamp', 'override_ind'],
        "Length": 5
    },
    "ABW_LIB_ANAL_OPTION_SUBS_LOAD": {
        "Used": False,
        "Columns": ['sub_struct_analysis_options_id', 'vehicle_id', 'sub_struct_loading_id', 'vehicle_type', 'axle_load'],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_LL_REACT_SUB": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'll_reaction_set_id', 'span_location_type', 'up_to_date_ind', 'results_timestamp'],
        "Length": 5
    },
    "ABW_SUPER_STRUCT_MBR": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'super_struct_mbr_type', 'last_modified_event_id', 'creation_event_id', 'comment_id', 'name', 'descr', 'last_change_timestamp'],
        "Length": 85384  # //TODO - Important
    },
    "ABW_LIB_BOLT": {
        "Used": True,
        "Columns": ['lib_bolt_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'lfd_bearing_shear_threads_inc', 'lfd_bearing_shear_threads_exc', 'lfd_slip_class_a_std', 'lfd_slip_class_a_oversize', 'lfd_slip_class_a_long_trans', 'lfd_slip_class_a_long_parallel', 'lfd_slip_class_b_std', 'lfd_slip_class_b_oversize', 'lfd_slip_class_b_long_trans', 'lfd_slip_class_b_long_parallel', 'lfd_slip_class_c_std', 'lfd_slip_class_c_oversize', 'lfd_slip_class_c_long_trans', 'lfd_slip_class_c_long_parallel', 'lrfd_kh_std', 'lrfd_kh_oversize', 'lrfd_kh_long_slot_trans', 'lrfd_kh_long_slot_parallel', 'lrfd_ks_class_a', 'lrfd_ks_class_b', 'lrfd_ks_class_c', 'asd_slip_class_a_std', 'asd_slip_class_a_oversize', 'asd_slip_class_a_long_trans', 'asd_slip_class_a_long_parallel', 'asd_slip_class_b_std', 'asd_slip_class_b_oversize', 'asd_slip_class_b_long_trans', 'asd_slip_class_b_long_parallel', 'asd_slip_class_c_std', 'asd_slip_class_c_oversize', 'asd_slip_class_c_long_trans', 'asd_slip_class_c_long_parallel', 'asd_bearing_shear_threads_inc', 'asd_bearing_shear_threads_exc', 'lrfd_ks_class_d', 'lrfd_kc_class_a', 'lrfd_kc_class_b', 'lrfd_kc_class_c', 'lrfd_kc_class_d'],
        "Length": 12
    },
    "ABW_SUPSTRUCTDEF_BRACING_MBR": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'bracing_id', 'mbr_id', 'name', 'lrfr_condition_factor_type', 'lrfr_field_meas_sect_prop_ind', 'last_change_timestamp'],
        "Length": 9
    },
    "ABW_LIB_BOLT_DIAMETER": {
        "Used": True,
        "Columns": ['lib_bolt_id', 'bolt_diameter_id', 'diameter', 'lrfd_tensile_strength', 'lrfd_required_tension'],
        "Length": 92
    },
    "ABW_SYS_DB_MAINTENANCE": {
        "Used": True,
        "Columns": ['maintenance_keyword', 'name', 'descr', 'development_timestamp', 'maintenance_type_flag', 'maintenance_source', 'version_applied'],
        "Length": 53
    },
    "ABW_LIB_MATL_PS_STRAND": {
        "Used": True,
        "Columns": ['matl_ps_strand_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'strand_type', 'strand_diameter', 'strand_area', 'weight_per_length', 'ultimate_tensile_strength', 'yield_strength', 'mod_of_elast', 'transfer_length_lrfd', 'transfer_length_std', 'epoxy_coated_ind', 'checksum'],
        "Length": 28
    },
    "ABW_SYS_DB_MAINTENANCE_STAGE": {
        "Used": True,
        "Columns": ['maintenance_keyword', 'stage_keyword', 'name', 'descr', 'maintenance_stage_timestamp'],
        "Length": 114
    },
    "ABW_LIB_MATL_WEARING_SURFACE": {
        "Used": True,
        "Columns": ['lib_matl_wearing_surface_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'density'],
        "Length": 4
    },
    "ABW_TIMBER_BEAM_SHAPE": {
        "Used": True,
        "Columns": ['bridge_id', 'timber_beam_shape_id', 'name', 'descr', 'si_or_us_type', 'timber_beam_shape_type', 'last_change_timestamp'],
        "Length": 50
    },
    "ABW_LOAD_PALETTE_TEMPL_LOADING": {
        "Used": False,
        "Columns": ['load_palette_template_id', 'loading_id', 'sys_lrfd_loading_id', 'use_ind', 'override_ind'],
        "Length": 0
    },
    "ABW_FLNG_LAT_BEND_STRESS": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'super_struct_spng_mbr_alt_id', 'flng_lat_bend_stress_id', 'load_case_name', 'load_case_description', 'stage_id', 'load_type', 'incl_analysis_line_girder_ind', 'incl_analysis_three_d_ind', 'consider_design_review_ind', 'consider_lrfr_rating_ind'],
        "Length": 3965
    },
    "ABW_SYS_BRM_SYNC_SETTING": {
        "Used": True,
        "Columns": ['brm_sync_setting_id', 'brdr_bridge_column', 'brdr_bridge_column_name', 'sync_enabled_ind', 'override_enabled_enabled_ind', 'override_enabled_ind', 'brm_data_table', 'brm_data_column', 'brm_default_data_table', 'brm_default_data_column'],
        "Length": 15
    },
    "ABW_WSS_WL_SUPER_MBR_WIND": {
        "Used": False,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'wind_effect_id', 'wind_effect_detail_id', 'spng_mbr_bearing_loc_id', 'wss_long_force', 'wss_trans_force', 'wss_vert_reaction', 'wl_long_force', 'wl_trans_force', 'wl_vert_reaction', 'wss_long_force_ul', 'wss_trans_force_ul', 'wss_vert_reaction_ul', 'wl_long_force_ul', 'wl_trans_force_ul', 'wl_vert_reaction_ul'],
        "Length": 0
    },
    "ABW_DETAILED_TRUSS_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'detailed_truss_def_type', 'even_num_panels_ind', 'symmetrical_ind', 'asr_inv_axialtens_gross_factor', 'asr_opr_axialtens_gross_factor', 'asr_inv_axialtens_net_factor', 'asr_opr_axialtens_net_factor', 'asr_inv_compression_factor', 'asr_opr_compression_factor', 'lrfr_condition_factor_type', 'lrfr_system_factor_type', 'override_lrfd_factor_id', 'override_lfr_factor_id', 'override_lrfr_factor_id', 'asr_analysis_module_guid', 'lfr_analysis_module_guid', 'beam_def_units_type', 'default_analysis_method_type', 'default_conn_hole_diameter', 'default_xsection_conn_type', 'default_end_conn_type', 'default_stl_matl_id', 'impact_factor_type', 'impact_factor_adjustment', 'impact_factor_override', 'lrfd_fatigue_impact_factor', 'lrfd_constant_impact_factor', 'model_truss_mbr_as_beam_ind', 'lrfd_analysis_module_guid', 'lrfr_analysis_module_guid', 'override_asr_factor_id', 'asr_spec_edition_choice_type', 'lfr_spec_edition_choice_type', 'lrfd_spec_edition_choice_type', 'lrfr_spec_edition_choice_type', 'asr_spec_edition_guid', 'lfr_spec_edition_guid', 'lrfd_spec_edition_guid', 'lrfr_spec_edition_guid', 'lrfr_field_meas_sect_prop_ind', 'lrfr_system_fact_override_ind', 'lrfr_system_fact_override'],
        "Length": 27
    },
    "ABW_WSS_WL_SUPER_WIND_EFFECT": {
        "Used": False,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'wind_effect_id', 'skew_angle', 'sys_lrfd_ls_id'],
        "Length": 0
    },
    "ABW_SYS_METAL_BOX_COLUMN_LABEL": {
        "Used": True,
        "Columns": ['label_id', 'label_value'],
        "Length": 15
    },
    "ABW_EVENT_VEHICLE": {
        "Used": True,
        "Columns": ['event_id', 'event_vehicle_id', 'vehicle_id', 'inventory_ind', 'operating_ind', 'design_ind', 'permit_ind', 'fatigue_ind', 'scale_factor', 'single_lane_ind', 'tandem_train_ind', 'impact_override_factor', 'impact_override_ind', 'frequency_type', 'loading_condition_type', 'permit_live_load_override_ind', 'permit_ll_override_factor', 'adjacent_vehicle_id', 'lrfr_legal_ind', 'lrfr_permit_ind', 'lrfr_inventory_ind', 'lrfr_operating_ind', 'legal_pair_ind', 'lrfr_fatigue_ind', 'legal_live_load_override_ind', 'legal_ll_override_factor', 'lrfr_legal_haul_ind', 'asr_lfr_permit_inventory_ind', 'asr_lfr_permit_operating_ind', 'asr_lfr_legal_inventory_ind', 'asr_lfr_legal_operating_ind'],
        "Length": 1529
    },
    "ABW_TIMBER_RECT_SAWN_BEAM_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'adj_beam_flat_use_factor', 'adj_beam_rep_use_factor', 'lrfd_adj_incise_flex_shear', 'lrfd_adj_incise_bearing', 'lrfd_adj_incise_modulus'],
        "Length": 65
    },
    "ABW_PARAMETER": {
        "Used": True,
        "Columns": ['parameter_id', 'table_name', 'field_name', 'parmvalue', 'shortdesc', 'longdesc'],
        "Length": 162
    },
    "ABW_ADV_CONC_XSECTION": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'xsection_id', 'xsection_type', 'name', 'top_flng_conc_id', 'top_flng_cj', 'top_flng_stress_limit_id', 'other_parts_stress_limit_id', 'other_parts_conc_id', 'computed_wt1', 'computed_wt2', 'area', 'ixx', 'iyy', 'j'],
        "Length": 12
    },
    "ABW_BMDEF_DECK_REINF_RANGE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'deck_reinf_range_id', 'dist', 'length', 'stl_reinf_id', 'num_bars', 'rebar_id', 'vert_dist', 'vert_dist_reference_type'],
        "Length": 212
    },
    "ABW_BMDEF_SHEAR_CONN_RANGE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'shear_conn_range_id', 'dist', 'length', 'num_spaces', 'num_across', 'shear_connector_id', 'spacing_across', 'cluster_pitch', 'number_rows_in_cluster', 'number_of_clusters', 'stud_pitch'],
        "Length": 92
    },
    "ABW_BMDEF_SIDEWALK_LL": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'bmdef_sidewalk_ll_id', 'sidewalk_load', 'load_case_id'],
        "Length": 0
    },
    "ABW_BMDEF_STL_FATIGUE_LOC": {
        "Used": False,
        "Columns": [
            'bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'anal_pt_id', 'stl_fatigue_loc_id', 'vert_dist',
            'lfd_fatigue_category_type', 'lfd_allow_fatigue_stress', 'lrfd_fatigue_category_type',
            'lrfd_nom_fatigue_resistance', 'vert_dist_ref_type'
        ],
        "Length": 0
    },
    "ABW_BOLT_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'bolt_def_id', 'bolt_designation', 'name', 'descr', 'bolt_diameter', 'hole_diameter', 'connection_type', 'hole_size_type', 'load_direction_type', 'surface_class_type', 'asd_allow_shear_stress', 'asd_allow_bearing_stress', 'asd_slip_resistance', 'lfd_allow_shear_stress', 'lfd_allow_bearing_stress', 'lfd_slip_resistance', 'lrfd_min_tensile_strength', 'lrfd_required_tension', 'lrfd_kh_factor', 'lrfd_ks_factor', 'exclude_threads_ind', 'last_change_timestamp', 'grip_length', 'hole_type', 'lrfd_kc_factor'],
        "Length": 251
    },
    "ABW_BRIDGE_DESIGN_PARAM": {
        "Used": True,
        "Columns": ['bridge_id', 'long_force_load_dist_type', 'trans_force_load_dist_type', 'consider_induced_vert_reac_ind', 'horz_roadway_design_speed', 'horz_roadway_radius_curvature', 'curve_direction_type', 'cap_top_reinf_min_rebar_id', 'cap_top_reinf_max_rebar_id', 'cap_top_reinf_min_bar_spacing', 'cap_top_reinf_max_num_layers', 'cap_top_reinf_min_layer_dist', 'cap_bot_reinf_max_rebar_id', 'cap_bot_reinf_min_rebar_id', 'cap_bot_reinf_min_bar_spacing', 'cap_bot_reinf_max_num_layers', 'cap_bot_reinf_min_layer_dist', 'cap_shr_reinf_min_rebar_id', 'cap_shr_reinf_max_rebar_id', 'cap_shr_reinf_min_bar_spacing', 'cap_shr_reinf_max_ctc_spacing', 'cap_shr_reinf_min_clear_cover', 'cap_reinf_round_spacing_to', 'cw_flex_reinf_min_rebar_id', 'cw_flex_reinf_max_rebar_id', 'cw_flex_reinf_min_bar_spacing', 'cw_flex_reinf_max_ctc_spacing', 'cw_flex_reinf_max_num_layers', 'cw_flex_reinf_min_layer_dist', 'cw_flex_reinf_pct_area_max', 'cw_flex_reinf_pct_area_min', 'cw_shr_reinf_min_clear_cover', 'cw_shr_spiral_min_rebar_id', 'cw_shr_spiral_max_rebar_id', 'cw_shr_spiral_min_bar_spacing', 'cw_shr_spiral_ctc_pitch', 'cw_shr_ties_min_rebar_id', 'cw_shr_ties_max_rebar_id', 'cw_shr_ties_min_bar_spacing', 'cw_shr_ties_max_ctc_spacing', 'cw_shr_consider_seismicreq_ind', 'ftg_flex_reinf_min_rebar_id', 'ftg_flex_reinf_max_rebar_id', 'ftg_flex_reinf_min_bar_spacing', 'ftg_flex_reinf_max_ctc_spacing', 'ftg_flex_reinf_min_top_cover', 'ftg_flex_reinf_min_bot_cover', 'ftg_flex_reinf_side_cover', 'ftg_flex_topmost_bar_dir_type', 'ftg_flex_botmost_bar_dir_type', 'geo_ftg_min_width', 'geo_ftg_max_width', 'geo_ftg_width_increment', 'geo_ftg_min_length', 'geo_ftg_max_length', 'geo_ftg_length_increment', 'geo_ftg_min_aspect_ratio', 'geo_ftg_max_aspect_ratio', 'geo_ftg_thick_increment', 'geo_ftg_spread_min_thick', 'geo_ftg_spread_max_thick', 'geo_ftg_pile_min_thick', 'geo_ftg_pile_max_thick'],
        "Length": 13188
    },
    "ABW_BRIDGE_DIAPHRAGM_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'diaphragm_def_id', 'name', 'diaphragm_type', 'material_type', 'conc_id', 'conc_thick', 'conc_height', 'num_elements_fixed_members', 'member_connection_bolt_def_id', 'tension_only_diag_sys_ind'],
        "Length": 9404
    },
    "ABW_TRUSS_DEF_ELEMENT": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'truss_def_element_id', 'element_xsection_id', 'begin_panel_point_id', 'end_panel_point_id', 'name', 'x_axis_unbraced_length', 'y_axis_unbraced_length', 'k_value', 'end_connection_type'],
        "Length": 542
    },
    "ABW_TRUSS_DEF_INTERM_SUPPORT": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'intermediate_support_id', 'panel_point_id', 'x_translation_type', 'y_translation_type', 'z_rotation_type', 'x_translation_spring_constant', 'y_translation_spring_constant', 'z_rotation_spring_constant'],
        "Length": 0
    },
    "ABW_TRUSS_DEF_PANEL_POINT": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'panel_point_id', 'name', 'x_coord', 'y_coord', 'location_type'],
        "Length": 372
    },
    "ABW_TRUSS_DEF_SPAN": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'span_id', 'length', 'dist', 'cantilever_ind'],
        "Length": 99
    },
    "ABW_SUPER_LL_REACT_SUB_DETAIL": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'll_reaction_set_id', 'live_load_id', 'vehicle_id', 'vehicle_type', 'min_single_lane_reaction', 'min_impact_factor_override', 'max_single_lane_reaction', 'max_impact_factor_override'],
        "Length": 20
    },
    "ABW_SUPER_LOAD_CASE": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'load_case_id', 'name', 'stage_id', 'descr', 'load_type', 'load_application_time'],
        "Length": 48393
    },
    "ABW_SUPER_MBR_ENVIRONMENT_LOAD": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'mbr_environmental_load_id', 'spng_mbr_bearing_loc_id', 'wso_vert_reaction', 'tu_long_force_temp_rise', 'tu_long_force_temp_fall', 'sh_long_force', 'cr_long_force', 'wso_vert_reaction_ul', 'tu_long_force_temp_rise_ul', 'tu_long_force_temp_fall_ul', 'sh_long_force_ul', 'cr_long_force_ul', 'wso_str_iii_vert_reaction', 'wso_serv_iv_vert_reaction', 'wso_str_iii_vert_reaction_ul', 'wso_serv_iv_vert_reaction_ul'],
        "Length": 20
    },
    "ABW_SUPER_PED_LL_SUB_DETAIL": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'ped_ll_set_id', 'ped_ll_react_detail_id', 'super_struct_def_id', 'curb_id', 'min_calc_reaction', 'min_calc_uniform_load', 'min_ovr_uniform_load', 'max_calc_reaction', 'max_calc_uniform_load', 'max_ovr_uniform_load'],
        "Length": 1
    },
    "ABW_BOT_FLANGE_LAT_BRACING_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'lateral_bracing_def_id', 'name', 'stl_shape_type', 'stl_shape_id', 'stl_structural_id', 'connection_type', 'angle_vert_leg_type', 'member_connection_type', 'member_connection_bolt_def_id', 'num_bolt_lines', 'num_bolts_per_line', 'bolt_line_trans_spacing', 'bolt_line_long_spacing', 'start_work_point_offset', 'end_work_point_offset', 'girder_attach_area_deduction'],
        "Length": 124
    },
    "ABW_ANAL_PT_REINF_CONC": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'super_struct_mbr_id', 'super_struct_spng_mbr_alt_id', 'anal_pt_id', 'lrfd_shear_comp_method_type', 'override_shear_reinf_ind', 'percent_shear', 'shear_dist', 'shear_beta', 'shear_theta', 'shear_sx', 'stirrup_matl_stl_reinf_id', 'stirrup_rebar_id', 'stirrup_num_legs', 'stirrup_area', 'stirrup_angle_alpha', 'stirrup_spacing', 'horz_shear_stl_reinf_id', 'horz_shear_rebar_id', 'horz_shear_num_legs', 'horz_shear_reinf_area', 'horz_shear_angle_alpha', 'horz_shear_reinf_spacing', 'lfr_ignore_shear_ind', 'override_reinf_develop_ind', 'lrfr_ignore_shear_dsnleg_ind', 'lrfr_ignore_shear_permit_ind', 'lrfr_cons_prm_tens_stlstrs_ind'],
        "Length": 2913
    },
    "ABW_BEAM_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'beam_def_type', 'xsection_based_ind', 'beam_use_type', 'beam_def_units_type', 'flrbm_cantilever_ind', 'flrbm_left_cantilever_length', 'flrbm_right_cantilever_length', 'flrbm_length', 'beam_projection_start', 'beam_projection_end', 'impact_factor_type', 'impact_factor_adjustment', 'impact_factor_override', 'lrfd_constant_impact_factor', 'lrfd_fatigue_impact_factor', 'default_conc_matl_id', 'default_beam_conc_matl_id', 'default_stl_reinf_id', 'default_beam_stl_reinf_id', 'default_stirrup_stl_reinf_id', 'default_beam_timber_id', 'default_deck_timber_id', 'default_stl_plate_matl_id', 'default_ps_strand_matl_id', 'default_bolt_def_id', 'default_nail_id', 'default_weld_id', 'haunch_embedded_flng_ind', 'haunch_dim_type', 'asr_inv_rebar_factor', 'asr_inv_concrete_factor', 'asr_inv_structural_stl_factor', 'asr_inv_stirrup_factor', 'asr_inv_bearing_stiff_factor', 'asr_inv_ps_conc_comp_factor', 'asr_inv_ps_conc_tension_factor', 'asr_inv_ps_mom_capacity_factor', 'asr_opr_rebar_factor', 'asr_opr_concrete_factor', 'asr_opr_structural_stl_factor', 'asr_opr_stirrup_factor', 'asr_opr_bearing_stiff_factor', 'asr_opr_ps_conc_comp_factor', 'asr_opr_ps_conc_tension_factor', 'asr_opr_ps_mom_capacity_factor', 'asr_opr_timber_adj_allw_stress', 'override_lfr_factor_id', 'override_lrfd_factor_id', 'asr_analysis_module_guid', 'lfr_analysis_module_guid', 'lrfd_analysis_module_guid', 'default_analysis_method_type', 'lrfr_analysis_module_guid', 'nsg_analysis_module_guid', 'lrfr_condition_factor_type', 'lrfr_system_factor_type', 'override_lrfr_factor_id', 'lrfd_poi_gen_tenth_points_ind', 'lrfr_poi_gen_tenth_points_ind', 'lfr_poi_gen_tenth_points_ind', 'asr_poi_gen_tenth_points_ind', 'lrfd_poi_gen_xsec_chng_pts_ind', 'lrfr_poi_gen_xsec_chng_pts_ind', 'lfr_poi_gen_xsec_chng_pts_ind', 'asr_poi_gen_xsec_chng_pts_ind', 'lrfd_poi_gen_userdef_pts_ind', 'lrfr_poi_gen_userdef_pts_ind', 'lfr_poi_gen_userdef_pts_ind', 'asr_poi_gen_userdef_pts_ind', 'lrfd_distfact_app_method_type', 'lrfr_distfact_app_method_type', 'lfr_distfact_app_method_type', 'override_asr_factor_id', 'asr_spec_edition_choice_type', 'lfr_spec_edition_choice_type', 'lrfd_spec_edition_choice_type', 'lrfr_spec_edition_choice_type', 'asr_spec_edition_guid', 'lfr_spec_edition_guid', 'lrfd_spec_edition_guid', 'lrfr_spec_edition_guid', 'lrfr_field_meas_sect_prop_ind', 'lrfr_system_fact_override_ind', 'lrfr_system_fact_override', 'self_load_case_id', 'self_loadcase_engineassign_ind', 'default_top_flng_matl_conc_id', 'shear_conn_input_method_type'],
        "Length": 49045
    },
    "ABW_TEMP_LOAD": {
        "Used": True,
        "Columns": ['bridge_id', 'multimedia_id', 'context', 'fileloc', 'fileref', 'filetype', 'agency_type_param_id', 'status', 'reportflag', 'userkey1', 'userkey2', 'userkey3', 'userkey4', 'userkey5', 'notes', 'creation_event_id', 'last_modified_event_id'],
        "Length": 7
    },
    "ABW_TENDON_PROFILE_ANCH_REINF": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'tendon_profile_id', 'anchorage_reinf_id', 'num_legs', 'rebar_id', 'start_distance', 'num_spaces', 'spacing'],
        "Length": 0
    },
    "ABW_TENDON_PROFILE_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'tendon_profile_id', 'name', 'start_dist_into_start', 'end_dist_from_end', 'inflection_point_method_type', 'profile_assigned_to_type', 'pt_ps_matl_ps_strand_id', 'pt_ps_matl_pt_bar_id', 'pt_input_method_type', 'pt_jacking_force', 'pt_jacking_stress_ratio', 'pt_jacking_end_type', 'duct_grouting_type', 'pt_duct_diameter', 'sl_lrfd_prior_to_seating', 'sl_lrfd_anchor_and_couplers', 'sl_lrfd_elsewhere_length', 'sl_lrfd_service_limit', 'anch_general_zone_design_type', 'anch_bearing_plate_width', 'anch_bearing_plate_length', 'anch_bearing_plate_thickness', 'anch_spalling_reinf_num_bars', 'anch_spalling_rebar_id', 'starting_span', 'ending_span', 'sl_std_prior_to_seating', 'sl_std_anchor_and_couplers', 'sl_std_elsewhere_length', 'sl_std_service_limit', 'distribute_jforce_equal_ind', 'stage_id'],
        "Length": 48
    },
    "ABW_TENDON_PROFILE_DEF_DETAIL": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'tendon_profile_id', 'detail_id', 'profile_type', 'inflect_point_left_percent', 'inflect_point_low_percent', 'inflect_point_right_percent', 'inflect_point_left_dist', 'inflect_point_low_dist', 'inflect_point_right_dist', 'vert_offset_left_end_dist', 'vert_offset_le_meas_from_type', 'vert_offset_left_dist', 'vert_offset_l_meas_from_type', 'vert_offset_low_dist', 'vert_offset_lo_meas_from_type', 'vert_offset_right_dist', 'vert_offset_r_meas_from_type', 'vert_offset_right_end_dist', 'vert_offset_re_meas_from_type'],
        "Length": 72
    },
    "ABW_TIMBER_BEAM_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'timber_beam_def_type', 'overhang_left', 'overhang_right', 'adj_beam_shear_factor', 'adj_beam_flex_wet_service', 'adj_beam_shear_wet_service', 'adj_beam_compr_wet_service', 'adj_beam_mod_wet_service', 'adj_beam_size_factor', 'adj_beam_load_dur_factor', 'stiffness_moisture_cond_type', 'bearing_moisture_cond_type', 'shear_flex_moisture_cond_type', 'adj_bearing', 'lrfd_adj_flex_wet_service', 'lrfd_adj_shear_wet_service', 'lrfd_adj_bearing_wet_service', 'lrfd_adj_mod_wet_service', 'lrfd_adj_format_conv', 'lrfd_adj_format_conv_bearing', 'lrfd_adj_size_flexure', 'lrfd_adj_size_modulus', 'lrfd_adj_flat_use', 'lrfd_adj_bearing', 'lrfd_adj_deck', 'lrfd_adj_time_effect_str_i', 'lrfd_adj_time_effect_str_ii', 'timber_beam_shape_id', 'timber_id', 'asd_adj_beam_stability', 'lrfd_adj_beam_stability'],
        "Length": 65
    },
    "ABW_LIB_MATL_STL_STRUCTURAL": {
        "Used": True,
        "Columns": ['stl_structural_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'yield_strength', 'tens_strength', 'toughness', 'thermal_exp_coeff', 'density', 'mod_of_elast', 'checksum'],
        "Length": 63
    },
    "ABW_CULVERT_STRUCT_FK": {
        "Used": True,
        "Columns": ['stl_structural_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'yield_strength', 'tens_strength', 'toughness', 'thermal_exp_coeff', 'density', 'mod_of_elast', 'checksum'],
        "Length": 63
    },
    "ABW_GENERAL_PREFERENCE": {
        "Used": True,
        "Columns": ['general_preference_id', 'name', 'keyword', 'preference_cat_id', 'preference_xml'],
        "Length": 531
    },
    "ABW_GENERAL_PREFERENCE_CAT": {
        "Used": True,
        "Columns": ['preference_cat_id', 'parent_preference_cat_id', 'name'],
        "Length": 96
    },
    "ABW_RC_CULVERT_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'culvert_def_id', 'rc_culvert_def_type'],
        "Length": 1246
    },
    "ABW_TRUSS_DEF_SUPPORT": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'support_id', 'panel_point_id', 'x_translation_type', 'y_translation_type', 'z_rotation_type'],
        "Length": 252
    },
    "ABW_ADV_CONC_BDEF_GRD_SPACING": {
        "Used": False,
        "Columns": ['bridge_id', 'struct_def_id', 'spng_mbr_def_id', 'girder_spacing_id', 'start_distance', 'length', 'left_side_bay_width_start', 'left_side_bay_width_end', 'right_side_bay_width_start', 'right_side_bay_width_end'],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_DEF_FK": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'current_load_scenario_id', 'deck_load_case_id', 'deck_loadcase_engineassign_ind'],
        "Length": 14836
    },
    "ABW_SUBSDEF_FOUND_DEF_DISTLOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_FK": {
        "Used": True,
        "Columns": ['bridge_id', 'bridge_design_alt_id', 'super_struct_id', 'current_super_struct_alt_id', 'as_built_super_struct_alt_id'],
        "Length": 13559
    },
    "ABW_SUPER_STRUCT_FRAME_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_LL_DIST_SUB": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'll_dist_set_id', 'span_location_type', 'distribution_method_type', 'load_display_type', 'use_override_values_ind'],
        "Length": 5
    },
    "ABW_SUPER_STRUCT_SPNG_MBR_FK": {
        "Used": True,
        "Columns": ['bridge_id', 'sub_struct_def_id', 'll_dist_set_id', 'span_location_type', 'distribution_method_type', 'load_display_type', 'use_override_values_ind'],
        "Length": 5
    },
    "ABW_SUBSDEF_FOUND_DEF_UNIFLOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_MODEL_SET_FIXITY": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'model_setting_id', 'fixity_condition_id', 'sub_struct_def_component_id', 'location_type', 'long_support_type', 'trans_support_type', 'long_rot_spring_constant', 'trans_rot_spring_constant'],
        "Length": 49
    },
    "ABW_SUBSDEF_MODEL_SET_MBR_REL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_MODEL_SET_POI": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_DESIGN_WATER_LEVEL": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'model_setting_id', 'fixity_condition_id', 'sub_struct_def_component_id', 'location_type', 'long_support_type', 'trans_support_type', 'long_rot_spring_constant', 'trans_rot_spring_constant'],
        "Length": 49
    },
    "ABW_SYS_LRFD_LOADING": {
        "Used": True,
        "Columns": ['sys_lrfd_loading_id', 'name', 'descr', 'sort_order'],
        "Length": 31
    },
    "ABW_FLOORSYS_STRUCT_DEF": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'floorsys_struct_def_type', 'main_member_config_type', 'deck_type', 'member_spacing_display_type', 'main_members_support_deck_ind', 'stringer_frame_into_flrbm_ind', 'num_stringer_units', 'modular_ratio_sustained_factor', 'deck_crack_control_param_z', 'wearing_surface_matl_name', 'wearing_surface_desc', 'wearing_surface_density', 'wearing_surface_thick', 'truck_traffic_frac_single_lane', 'num_lanes_avail_truck', 'override_truck_traffic_ind', 'dl_distribution1_type', 'dl_distribution2_type', 'deck_exposure_factor', 'thick_field_mea_ind'],
        "Length": 118
    },
    "ABW_LIB_SUB_LRFD_DS_VEH_LOAD": {
        "Used": True,
        "Columns": ['bridge_id', 'struct_def_id', 'floorsys_struct_def_type', 'main_member_config_type', 'deck_type', 'member_spacing_display_type', 'main_members_support_deck_ind', 'stringer_frame_into_flrbm_ind', 'num_stringer_units', 'modular_ratio_sustained_factor', 'deck_crack_control_param_z', 'wearing_surface_matl_name', 'wearing_surface_desc', 'wearing_surface_density', 'wearing_surface_thick', 'truck_traffic_frac_single_lane', 'num_lanes_avail_truck', 'override_truck_traffic_ind', 'dl_distribution1_type', 'dl_distribution2_type', 'deck_exposure_factor', 'thick_field_mea_ind'],
        "Length": 118
    },
    "ABW_LIB_SUB_LRFD_DSG1N_SETTING": {
        "Used": True,
        "Columns": ['lrfd_design_setting_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'lrfd_factor_id', 'preliminary_design_setting_ind', 'final_design_setting_ind', 'dynamic_load_allow_method_type', 'dla_simple_fatigue_frac_impact', 'dla_simple_other_ls_impact', 'vehicle_summary_display_type', 'last_change_timestamp', 'limit_num_dsgn_load_combo_ind', 'cw_num_loadcombo_axial_bending', 'ftg_num_loadcombo_brg_capacity', 'lrfd_analysis_module_guid', 'lrfd_spec_edition_guid'],
        "Length": 4
    },
    "ABW_LIB_TIMBER_RECT_BEAM_SHAPE": {
        "Used": True,
        "Columns": ['timber_beam_shape_id', 'width', 'height', 'glulam_ind', 'num_glulam_laminations', 'nominal_weight', 'nominal_height', 'nominal_width', 'area', 'ixx', 'cg_bot', 'sxx_top', 'sxx_bot'],
        "Length": 1
    },
    "ABW_LIB_VEHICLE": {
        "Used": True,
        "Columns": ['vehicle_id', 'name', 'descr', 'library_type', 'si_or_us_type', 'uniform_lane_load', 'moment_conc_load', 'shear_conc_load', 'constant_gage_dist', 'constant_contact_width', 'second_equal_conc_load_ind', 'vehicle_weight', 'constant_gage_dist_ind', 'constant_contact_width_ind', 'sld_design_review_ind', 'sld_inv_rating_ind', 'sld_sl_rating_ind', 'sld_opr_rating_ind', 'sld_pst_rating_ind', 'lrfd_rating_ind', 'std_rating_ind', 'lrfd_design_ind', 'std_design_ind', 'tandem_load', 'tandem_spacing', 'tandem_trans_spacing', 'notional_ind', 'last_change_timestamp', 'vehicle_gage_type', 'lrfr_rating_ind', 'private_ind', 'owner_id'],
        "Length": 415
    },
    "ABW_LIB_VEHICLE_AXLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_HAUNCH_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_BOLT_RIVET_FIELD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_DIAPH_DEF_LOC_CON": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ADV_CONC_BDEF_FLEX_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_REF_LINE_HORZ": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_ENVIRONMENTAL_PARAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_LEGAL_LOADS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_LEGAL_LOADS_HAUL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_LF_TABLE_VALUE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_LOAD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_PERMIT_LIMITED": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_PERMIT_ROUTINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_CHANNEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_COVER_PLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_COVER_PLATE_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_EYE_BAR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_FATIGUE_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_FLNG_ANGLE_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_FLNG_FLAT_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_FLNG_PLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_GENERAL_PLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_ISHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_DEF_RCBOX_SEG_CELL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_DEF_RCBOX_SEG_WALL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_VEHICLE_PATH": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_CONC_POUR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_CORR_METAL_PANEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_GENERIC_PANEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_PS_SHAPE_STRAND_GRID": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_PS_TEE_BEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_PS_UBEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_REBAR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STAY_IN_PLACE_FORM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STL_ANGLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STL_CHANNEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STL_ISHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STL_RAILING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STL_STRUCT_TEE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SUB_LRFD_DS_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_DEF_RC_SEGMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ADV_CONC_PRECAST_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ADV_CONC_XSECT_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_AGENCY_WIND_EFFECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_SPAN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_STRGRP_FLOOR_BEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GIRDER_SYS_FRAME_CONN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GIRDER_SYS_INT_DIAPH": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GIRDER_SYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GLINE_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_DIAPH_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GLINE_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_VEHICLE_AXLE_WHEEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_WELDED_WIRE_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LL_DISTFACTOR_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_LF_TABLE_VALUE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_LOAD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_BRM_SYNC_SETTING_VALUE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEAM_DEF_KNEE_BRACE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEAM_HINGE_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCELL_BDEF_TRANS_REF_LINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_DATABASE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_WEB_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_ANAL_PT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_PANEL_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ABUTMENT_SUB_STRUCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEAM_DEF_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEARING_ELASTOMERIC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEARING_POT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEARING_ROCKER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_EARTH_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_ICE_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_PILE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_PS_PILE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_TIMBER_SIZE_CLASS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_TIMBER_SPECIES": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_VEHICLE_LFD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ADV_CONC_CIP_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LOADCOMBO_SETTING_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LOAD_PALETTE_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_SCHCPLT_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_XSEC_CPLATE_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRINGER_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRUCT_DEF_STRINGER_DLCASE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBALT_ANALYSIS_OPTIONS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBALT_ANALYSIS_OPTIONS_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBALT_ANAL_OPTION_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSALT_LOADCOMBO_SETTING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSALT_LOAD_PALETTE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSALT_LRFD_LOAD_COMBO": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSALT_WATERLEVEL_SETTING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_FOUND": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPPORT_LINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPSTRUCTDEF_BRAC_MBR_LOSS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_DATA_DICTIONARY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_UNIT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_TIMBER_COMMERCIALGRADE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_TIMBER_GRAD_RULE_AGNCY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_XSCCPLT_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_IMPORT_MESSAGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_SHAPE_STRAND_GRID": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_CONN_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MODIFICATION_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_TEE_BEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PARTIAL_SUPER_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PERSON": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_CAP_BOT_COLUMN_BAY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_CAP_COL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_CAP_ENCASEMENT_WALL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_CAP_PILE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_COL_CIRC_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_COL_FOUNDATION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_COL_RECT_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_UBEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_BEAM_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GENPREF_TEMPLATE_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CHECK_IN_OUT_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_COMMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_COMMENT_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CONC_LEG_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_BEARING_STIFF_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CREATION_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORSYS_STRINGER_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_CONC_RAILING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_CORR_METAL_PANEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_LF_TABLE_VALUE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_LOAD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RESULTS_CRIT_STRESSES_ASR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_CORR_MP_CULV_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_CORRUGATED_MP_CULV": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SPRL_RIB_MP_CULV_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RATING_TOOL_PERM_SCENARIO": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_BOX_CULVERT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_BOX_CULVERT_DEF_CELL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_LEG_CIRC_XSECT_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_LEG_RECT_XSECT_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_LEG_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_LEG_XSECTION_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_VARIABLE_XSECTION_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_XSECTION_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_XSECTION_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_BOX_BEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_BOX_INT_DIAPH_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_CONC_STRESS_LIMIT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_CONC_STRESS_LIMIT_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_IBEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_BEAM_CONT_REBAR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_BEAM_SPAN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_MILD_STL_LAYOUT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_STRAND_LAYOUT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PROPERTIES": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_SHAPE_MILD_STEEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CHECKED_OUT_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_LL_DISTFACTOR_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BF_LAT_BRACING_PROPERTIES": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CHECKOUT_AUTHORIZATION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_SUB_LRFD_DSVEH_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_WATER_LEVEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_TABLE_PROPERTIES": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CONC_BMDEF_EFF_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CONC_BMDEF_FRAME_CONN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CONC_BMDEF_REINF_PROFILE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_BRDR_TABLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_QW": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_REINF_BAR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_SHEAR_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_TZ": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DRILL_SHAFT_FOUND_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_PILE_DEF_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_PANEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_TYPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_TIMBER_PANEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GROUP_BRIDGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GROUP_USER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GROUP_ITEM_USER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GROUP_ITEM_BRIDGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_TRANS_STIFF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GUSSET_PLATE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GUSSET_PLATE_MEMBER_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LANE_POSITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LEG_ANAL_PT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LEG_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LEG_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LEG_SHEAR_REINF_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_CONC_COORD_SHAPE_COORD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_EXCHANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_CAP_FLEX_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_CAP_SHEAR_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_COL_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_COL_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_ENCASEMENT_WALL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_WALL_SHAFT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_WALL_SHAFT_SEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_WALL_TOP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_WALL_TOP_SEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_WEB_WALL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_ENCSW_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_ENCSW_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_ENCSW_RECT_XSECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_ENCSW_ROUNDNOSE_XSECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SHEAR_CONN_FIELD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SHEAR_CONN_SPIRAL_FIELD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_IMPORT_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_IMPORT_MESSAGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SHEAR_CONN_STUD_FIELD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SHEAR_CONNECTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_INSPECTION_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SHEAR_REINF_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SLAB_SYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_RC_COL_RECT_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_RC_COL_ROUNDNOSE_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_RC_COL_USR_XSEC_COORD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_RC_COL_WEDGENOSE_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_SUB_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_SUBSDEF_COLUMN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_SUBSDEF_COLUMN_SEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_TOP_CAP_SEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WALL_SHAFT_CONCLOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WALL_SHAFT_DISTLOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_UBEAM_INT_DIAPH_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PT_LOSS_PROPERTIES": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RATING_RESULTS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RATING_RESULTS_SUMMARY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_FOUND_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_FOUND_DEF_CONCLOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ADV_CONC_RC_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_GUSSET_PLATE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ABUTMENT_SUB_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ACCESS_PRIVILEGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANALYSIS_REPORTS_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT_CONC_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_APPROVAL_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GUSSET_PLATE_PANEL_POINT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_STRGRP_DEF_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_STL_PANEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DEFAULT_ANALYSIS_OPTIONS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DEF_ANALYSIS_OPTIONS_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DEF_ANAL_OPTION_LS_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DEF_ANAL_OPTION_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DESIGN_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DIAPH_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ERROR_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ERROR_MESSAGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FATIGUE_GROSS_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LFR_LOADING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RESULTS_CRIT_LOAD_ASR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORSYS_FLOOR_BEAM_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORSYS_MBR_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_DEF_DL_DIST": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_BR_FORCE_SUB_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_CE_FORCE_SUB": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_CE_FORCE_SUB_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_DL_REACT_SUB_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_DLREACT_SUB_OVERRIDE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LFR_FACT_SPEC_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LFR_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_CIRC_LEG_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_FRAMESHAFT_PIER_STR_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_FRAME_PIER_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_I_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_LEG_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_PIER_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_PILEBENT_PIER_STR_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_RECT_LEG_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_SLAB_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_SOLIDSHAFT_PIER_STR_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_TEE_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_WALL_PIER_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MATL_ALUMINUM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MACHINE_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_BAR_MARK_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GLINE_MBR_FRAME_CONN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SLAB_SYS_STRUCT_DEF_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WALL_SHAFT_FOUNDATION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WALL_TOP_WALL_SHAFT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WSHFT_REINF_PATT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_CONC_DECK_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORBEAM_MBR_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_LOAD_FACTOR_TABLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_LOAD_FACTOR_TABLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_LOAD_FACTOR_TABLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLINE_NODE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORLINE_FLOOR_BEAM_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_ANAL_MODULE_MBR_TYPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORLINE_MBR_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORLINE_STRINGER_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GIRDER_MBR_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_MBR_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRINGER_MBR_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_XSECTION_COVER_PLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_XSECTION_ELEMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_XSECTION_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_XSECTION_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STLBD_TOPFL_LSUP_LOC_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STLBD_TOPFLNG_LATSUP_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_STRUCT_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_BDEF_SEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_INT_DIAPH": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_SEG_LANE_POSITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_SEG_STRIPED_LANE_POS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_SEG_WEARING_SURFACE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DIAPH_PROPERTIES": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_STREAM_FLOW_EFFECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_SUB_LRFD_DS_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SPIRAL_RIB_MP_CULV": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STR_PL_MP_CULV_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STRUCT_PLATE_MP_CULV": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_METAL_PIPE_CULVERT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_METAL_BOX_CULVERT_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_TIMBER_PILE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_TU_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_TIMBER_GLULAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_TMBR_GLULAM_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TEMP_GRADIENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_LINE_GRD_ENG_DEFAULT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_MODULE_SPEC_DEFAULT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_THREE_D_ENG_DEFAULT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_INT_SUPPORT_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_INTERMEDIATE_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_SPEC_EDITION_SOIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FL_FLOORBEAM_STRINGER_SPAN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_CONN_LOCATION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_SIDEWALK_LL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TIMBTRUSS_ELEMENT_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_DEF_ELEMENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEARING_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_EXPLORER_SETTING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_EVENT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_EVENT_COMPONENT_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GROUP_ACCESS_PRIVILEGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LC_SETTING_WATERLEVEL_TEMP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_TIMBER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_PS_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STL_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_TIMBER_BEAM_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WALL_TOP_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WALL_TOP_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WEB_WALL_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WEB_WALL_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STLTRUSS_ELEMENT_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_TEND_PROF_ANCH_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RATING_TOOL_ANAL_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CONC_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_DEF_SEG_ANAL_PT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_DEF_SEGMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_HAUNCH_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_COMMAND_TIMBER_TRUSS_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_COMMAND_TRUSS_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DETAILED_STL_TRUSS_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DETAILED_TIMBER_TRUSS_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MA_STRS_IELEM_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_TRUSS_ROLLED_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLOORSYS_STRUCT_DEF_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLRBM_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FRAME_COLUMN_MBR_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_DEFAULT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_PILE_DEF_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_PILE_FOUND_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_SPREAD_FOUND_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_DEF_PEDESTAL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RESULTS_CONTROL_UNF_ACTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_FACTOR_SPEC_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_FACTOR_SPEC_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_ANAL_MODULE_HELP_MENU": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_SPECIFICATION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_SPECIFICATION_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_DIAPHRAGM_DEF_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_DEF_RC_BOX_SEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVERT_STRUCT_DEF_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTIPLE_PRESENCE_FACTORS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_NAIL_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_BOT_CAP_SEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_COL_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_COL_REINF_PAT_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_COL_SHEAR_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_CAP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_CAP_CONCENT_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_CAP_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_SEG_DECK_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_REF_LINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_TENDON_PROFILE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_TRUSS_BUILTUP_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MC_BOX_WEB_DISTFACT_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_STLFLNG_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MATL_STL_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MATL_STL_STRUCTURAL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MATL_TIMBER_SAWN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_SUB_LRFD_DS_LS_VEH": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_SUB_LRFD_DS_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_XSEC_CELL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_XSECT_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FLNG_LAT_BEND_STRESS_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TENDON_PROFILE_DEF_WEBDUCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVDEF_SEG_ANAL_PT_RC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_CONC_PANEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SPNG_MBR_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DESIGNRATIO_RSLTS_SUMMARY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_FOUND_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRIPED_LANE_POSITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRUCT_DEF_DISTRIB_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRUCT_DEF_REF_LINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRUCT_DEF_REF_LINE_HORZ": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_ANAL_OPTION_SUBS_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_ANAL_AXIAL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_ANAL_ELEV": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_CURVE_ELEV": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_FLEX_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_FOUND_LAYER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_PY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_FLNGANGL_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_FLNGFLAT_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_STL_TRUSS_ELEMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_STLBM_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_STLCPLT_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_STLWEB_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSALT_LRFD_LOAD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_BEARING_LINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_BEARING_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_CLOSED_BOX_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFR_LOAD_FACTOR_TABLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_BRDR_COLUMN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_BRDR_FOREIGN_KEY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPSTRUCTDEF_BRACING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_RANGE_APP_VALUE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_LEGAL_LOADS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_LEGAL_LOADS_HAUL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_LF_TABLE_VALUE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_LOAD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_PERMIT_LIMITED": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_PERMIT_ROUTINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_CONC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_IRON": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_PS_BAR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_STL_PS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_STL_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TIMBER_RECT_BEAM_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TOP_FLNG_LAT_SUP_LOC_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TOP_FLNG_LAT_SUPPORT_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_MBR_SPAN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_SPNG_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_BDEF_WEB": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_SEG_CONC_RAILING_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_SEG_STL_RAILING_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_WINDBRAC_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_SUB_STRUCT_INTERFACE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_ENVIR_LOAD_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_ENVIRONMENTAL_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_FR_FORCE_SUB_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_LL_DIST_SUB_WDLA": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_LL_DIST_SUB_WODLA": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_LL_PATTERN_SUB_ITEM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_CONC_DECK_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_CONTRAFLEX_POINTS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_DECK_REINF_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_DIAPH_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_GENERIC_DECK_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_GLINE_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_LEG_BRACE_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_SHEAR_CONN_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MA_STRS_IE_ANG_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MA_STRS_IE_CHAN_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MA_STRS_IE_CPLT_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEARING_SPHERICAL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MA_STRS_IE_FLNG_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MA_STRS_IE_WEB_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBRALT_STLIBM_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_WELD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_NAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_PS_BOX_BEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_PS_IBEAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_PS_SHAPE_MILD_STEEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "PARAMTRS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ROADWAY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "USERS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_AGENCY_STREAM_FLOW_EFFECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SLAB_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_LRFD_RANGE_OF_APP_ROW": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_LRFD_RANGE_APP_LABEL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_SUPER_STRUCT_STAGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_TABLE_RELATIONSHIPS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_TYPE_CATEGORY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_TEND_PROF_DEF_WEBDUCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TFS_FLOORLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TFS_FLOORSYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TF_FLOORLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TF_FLOORSYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_DEF_COMMAND": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_WALL_SUB_STRUCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_WALL_SUB_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_WIND_BRACE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_PLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_RAILING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_RAILING_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_RIVET_BOLT_CONN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTICELL_BOX_TENDON_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT_LRFD_OVERRIDE_CAP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FRAME_SYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_FLOOR_BEAM_MBR_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_STRGRP_DIAPH": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEAM_SHEAR_REINF_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_ANALYSIS_MODULE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BEARING_TIMBER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_COMPONENT_ERRORS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_ANALPT_LRFD_OVRD_CAP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_ANALPT_LRFR_OVRD_CAP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_FACT_SPEC_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFR_FACT_SPEC_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_ELEMENT_XSECTION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_RC_PILE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_SETTLEMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_SH_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_SPNG_MBR_BRNG_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUBSDEF_STREAM_FLOW": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_ANALYSIS_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_ANAL_EVENT_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_ANAL_OPTION_LS_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_ANAL_REPORTS_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_DEF_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_DEF_PILE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_STRUCT_STL_PILE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_DEF_WALL_SHAFT_XSECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_ENCASEMENT_WALL_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_ENCSW_USERDEF_XSECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_RC_COL_USERDEF_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_SUBSDEF_COLUMN_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_SUB_STRUCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WALL_SHAFT_COL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FS_FLOORLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FS_FLOORSYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GFS_FLOORLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GFS_FLOORSYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GF_FLOORLINE_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GF_FLOORSYS_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GIRDER_FLRBM_STRUCT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GIRDER_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GIRDER_SYS_STRUCT_DEF_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_FLNG_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_IBEAM_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_LEG_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_NON_DETAILED_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_PLATE_IBEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_ROLLED_IBEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_SCH_CPLATE_LOSS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WSHFT_ROUNDNOSE_XSECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GENPREF_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_METAL_BOX_CULVERT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_SUPPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRACKET_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_COMMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DETAIL_TRUSS_DEF_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SPNG_MBR_ALT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT_LRFR_OVERRIDE_CAP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_MATL_TIMBER_SAWN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SPEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SPEC_ARTICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_STANDARD_LOAD_GROUP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRUCT_DEF_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SUB_ANALYSIS_OPTIONS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SUB_LRFD_DS_LS_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_SUB_LRFD_DS_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WSHFT_USERXSECT_COORD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_EVENT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_EVENT_COMP_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_ANAL_MOD_SPEC_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_ANAL_MODULE_FEATURE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BOT_FLANGE_LAT_BRACING_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TENDON_DEF_WEB_JFORCE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LFR_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LFR_FACTOR_SPEC_EDITION": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LFR_LOADING": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT_TIMBER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANALYSIS_EVENT_TEMPLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BAR_MARK_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT_STL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_GUSSET_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FRAME_MBR_ALT_LEG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_STRGRPDEF_TEMPLATE_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_STRINGER_UNIT_LAYOUT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_SPNG_MBR_ALT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_ANAL_MODULE_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_BRIDGE_EXPLORER_COLUMN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_USER_PROFILE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_ROLLED_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_UNIT_CATEGORY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_SECTION_PROPERTY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_ANALYSIS_OPTIONS_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_ANAL_OPTION_LS_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_ANAL_OPTION_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_CONC_COORD_SHAPE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_SPLICE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STL_SPLICE_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUPER_STRUCT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_AGENCY_BRIDGE_DESIGN_PARAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ADV_CONC_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CULVDEF_RCBOX_SEG_REINPROF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ADV_CONC_PT_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_ANAL_PT_PS_CONC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BMDEF_ANAL_PT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSSDEF_ELEMENT_DIST_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_UNIT_TOLERANCE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_WEARING_SURFACE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MULTI_CELL_BOX_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCELL_BOX_STRUCT_DEF_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_WELD_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_WIND_LOAD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_EVENT_LRFD_FACTOR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_EVENT_LRFD_LS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SPNG_MBR_ALT_EVENTS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RESULTS_DL_CASE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_DECK_PANEL_ANALYSIS_EVENTS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_INTEREST_PT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_SPEC_CHECK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LRFD_SPEC_CHECK_COMMENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MBR_ALT_EVENTS_EXPORT_LOG": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SPNG_MBR_ALT_EVENT_ERRORS": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SPNG_MBR_ALT_EVENTS_REPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RESULTS_GENERIC_REPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RESULTS_STL_XSEC_REPORT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RESULTS_STL_LS_SUMMARY": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BRIDGE_WIND_EFFECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_CONC_BMDEF_VOID_SEC_PAT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_AGENCY_ENVIRONMENTAL_PARAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SECONDARY_EVENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FRAME_LEG_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FRAME_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FRAME_SPNG_MBR": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FRAME_SYS_STRUCT_DEF_FK": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_GIRDER_MBR_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_STRINGER_GROUP_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_STRINGER_MBR_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_SUPPORT_LINE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_FSYS_TRUSS_MBR_LOC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_ENCSW_USERXSECT_COORD": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_RC_COL_CIRC_XSEC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_COMMAND_STL_TRUSS_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUP_STR_THR_D_NODE_GEN_TOL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PIER_WSHFT_USERDEF_XSECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PROJECT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PROJECT_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PROJECT_ENGINEER": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PROJECT_GROUP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PROJECT_GROUP_DETAIL": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_BOX_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_IBEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_SLAB_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_TEE_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_PS_PRECAST_UBEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_RANGE_OF_APP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_LIB_LRFD_RANGE_OF_APP_ROW": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_ARCH_CULVERT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_RC_PIPE_CULVERT_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SUB_DR_SHAFT_REINF_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TRUSS_GUSSET_PLATE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_MSEG_TND_DEF_JFORCE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_MSEG_TND_PRF_ANCH_REIN": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_MSEG_TND_PRF_DEF_DET": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_MSEG_TND_PRF_DEF_WBDCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_MULTI_SEG_TND_PRF_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_MULTISEG_SLAB_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_MULTISEG_TENDON_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_SEG_LL_DISTFACT_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_TEND_PROF_DEF_DET": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_TENDON_PROFILE_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_TENDON_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_THICKNESS_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_TND_PRF_ANCH_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_TND_PRF_DEF_WEBDCT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STRUCT_DEF_EXC_ANAL_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_SYS_BRM_VEHICLE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_BOT_FLNG_LAT_SUP_LOC_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_ANAL_PT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_ANAL_PT_COMPONENT": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_ANAL_PT_CONC_REINF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_ANAL_PT_PS_CONC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCB_WEB_ANAL_PT_REINF_CONC": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCBW_ANAL_PT_LRFD_OVR_CAP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MCBW_ANAL_PT_LRFR_OVR_CAP": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_STLBD_BOTFL_LSUP_LOC_RANGE": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_TIMBER_GLULAM_BEAM_DEF": {
        "Used": False,
        "Columns": [],
        "Length": 0
    },
    "ABW_MATL_TIMBER_GLULAM": {
        "Used": False,
        "Columns": [],
        "Length": 0
    }
}