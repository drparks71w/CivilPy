# AASHTO LRFD check porting status

Running checklist of spec-article checks implemented as independent
functions in this package.  Article numbers are current (10th Edition)
numbering; functions register in `lrfd.ARTICLES`.  Checks default to
current-edition values; `design_year` selects historical values where
wired (see `editions.py`).

## Done

### Steel (Chapter 6)
- [x] 6.10.8.2.2 Compression flange local buckling — `steel.flange_local_buckling_resistance`
- [x] 6.10.8.2.3 Lateral torsional buckling — `steel.lateral_torsional_buckling_resistance`
- [x] 6.10.8.1.2 Tension flange — `steel.tension_flange_resistance`
- [x] 6.10.9 Web shear incl. tension field — `steel.web_shear_resistance`
- [x] 6.10.1.10.1 Hybrid factor Rh — `steel.hybrid_factor`
- [x] 6.10.1.10.2 Web load-shedding Rb — `steel.web_load_shedding_factor`
- [x] 6.10.7.1.2 Compact composite positive flexure (+6.10.7.3 ductility flag) — `steel.compact_composite_positive_flexure`
- [x] 6.10.2 Proportion limits — `steel.proportion_limits`
- [x] 6.6.1.2.5 Load-induced fatigue (categories A–E') — `steel.fatigue_resistance`
- [x] 6.8.2.1 Tension members yield/rupture — `steel.tension_member_resistance`
- [x] 6.9.4.1.1 Column buckling (design_year: pre-2015 phi_c=0.90) — `steel.compression_member_resistance`
- [x] 6.13.2.7/.8/.9 Bolt shear/slip/bearing — `steel.bolt_*_resistance`
- [x] A6.2 Web plastification Rpc/Rpt — `appendix_a6.web_plastification_factors`
- [x] A6.3.2 / A6.3.3 FLB & LTB in moment format (+ St. Venant J helper) — `appendix_a6`
- [x] A6.4 Tension flange yielding — `appendix_a6.a6_tension_flange_yielding`
- [x] 6.10.1.9.1 Web bend-buckling Fcrw — `steel.web_bend_buckling`
- [x] 6.10.3.2.1 Constructibility compression flange — `steel.constructibility_compression_flange`
- [x] 6.10.10.4 / 6.10.10.1.2 Shear connectors (strength + fatigue pitch) — `steel.shear_connector_*`
- [x] 6.13.4 Block shear rupture — `steel.block_shear_resistance`
- [x] 6.13.3.2.4 Fillet weld shear — `steel.fillet_weld_resistance`
- [x] 6.13.6.1.3b/c Flange & web splice design forces (8E method) — `splices`

### Reinforced concrete (Chapter 5)
- [x] 5.6.3.2 Rectangular flexural resistance — `concrete.rc_rectangular_flexural_resistance`
- [x] 5.6.3.3 Minimum reinforcement (design_year: pre-2012 1.2·Mcr) — `concrete.rc_minimum_reinforcement`
- [x] 5.7.3.3 Shear resistance (simplified β/θ) — `concrete.rc_shear_resistance`
- [x] 5.6.7 Crack control, spacing method — `concrete.rc_crack_control_spacing`
- [x] 5.6.7 pre-2005 z-factor method — `concrete.rc_crack_control_z_factor`
- [x] 5.7.3.4.2 MCFT general β/θ — `concrete.rc_mcft_beta_theta` (feeds `rc_shear_resistance`)
- [x] 5.7.2.5 Min transverse reinforcement — `concrete.rc_min_transverse_reinforcement`
- [x] 5.7.2.6 Max stirrup spacing — `concrete.rc_max_stirrup_spacing`
- [x] 5.7.3.5 Longitudinal reinforcement — `concrete.rc_longitudinal_reinforcement`
- [x] 5.7.4 Interface shear transfer — `concrete.rc_interface_shear`
- [x] 5.7.2.1 Torsion threshold — `concrete.rc_torsion_threshold`
- [x] 5.6.3.5.2 Effective moment of inertia (Branson) — `concrete.rc_effective_moment_of_inertia`
- [x] 2.5.2.6.2 Optional deflection criteria — `concrete.deflection_limit`
- [x] 5.6.4.4 Column axial resistance (tied/spiral) — `columns.rc_column_axial_resistance`
- [x] 5.6.4.2 Column reinforcement limits — `columns.rc_column_reinforcement_limits`
- [x] 5.6.4.6 Spiral reinforcement — `columns.rc_spiral_reinforcement`
- [x] 4.5.3.2.2b Moment magnification — `columns.moment_magnification`
- [x] 5.6.4.5 P-M interaction (strain compatibility, rect + circular) — `columns.rc_pm_interaction_diagram`, `rc_pm_capacity_check`
- [x] 5.6.4.5 Biaxial flexure (moment-contour + Bresler reciprocal) — `columns.rc_biaxial_check`

### Prestressed concrete (Chapter 5)
- [x] 5.6.3.1.1 Strand stress at nominal resistance — `prestressed.ps_strand_stress_at_nominal`
- [x] 5.6.3.2.2 Flexural resistance — `prestressed.ps_flexural_resistance`
- [x] 5.9.2.3.1a Transfer compression limit (design_year: pre-2016 0.60) — `prestressed.ps_transfer_compression_check`
- [x] 5.9.2.3.1b Transfer tension limit — `prestressed.ps_transfer_tension_check`
- [x] 5.9.2.3.2a Service compression limits — `prestressed.ps_service_compression_check`
- [x] 5.9.2.3.2b Service tension limit — `prestressed.ps_service_tension_check`
- [x] 5.9.3.2.3a Elastic shortening loss — `prestressed.ps_elastic_shortening_loss`
- [x] 5.9.3.3 Approximate time-dependent losses — `prestressed.ps_approximate_longterm_loss`
- [x] 5.4.2.3.2 / 5.4.2.3.3 Creep & shrinkage models (design_year: pre-2015 ktd) — `creep_shrinkage`
- [x] 5.9.3.4.2a–c Refined losses, transfer→deck — `prestressed.ps_refined_loss_*`
- [x] 5.9.3.4.3a/b/d Refined losses, deck→final + deck-shrinkage gain — `prestressed.ps_refined_loss_*_deck_stage`, `ps_deck_shrinkage_gain`
- [x] 5.9.3.2.2 Friction loss (PT) — `prestressed.ps_friction_loss`
- [x] 5.9.4.3.2 Strand development length — `prestressed.ps_strand_development`
- [x] 5.9.4.4.1 Splitting resistance — `prestressed.ps_splitting_resistance`
- [x] 5.9.3.2.1 Anchorage set loss — `prestressed.ps_anchorage_set_loss`

### Analysis / loads (done)
- [x] 4.6.2.2.2b/.3a Interior moment & shear DFs (I-girders, type a/e/k) — `distribution.moment_df_interior`, `shear_df_interior`
- [x] 4.6.2.2.2d/.3b Exterior DFs via e-factor — `distribution.moment_df_exterior`, `shear_df_exterior`
- [x] 4.6.2.2.2e/.3c Skew corrections — `distribution.skew_correction_*`
- [x] 3.6.2 Dynamic load allowance — `distribution.dynamic_load_allowance`
- [x] 4.6.2.6 Effective flange width (design_year: pre-2008 three-way min) — `distribution.effective_flange_width`
- [x] 3.6.1.1.2 Multiple presence + lever-rule exterior DF — `distribution.multiple_presence_factor`, `lever_rule_exterior`
- [x] 4.6.2.3 Slab equivalent strip widths (incl. skew) — `distribution.slab_equivalent_strip`
- [x] 4.6.2.2.2b type (g) box-beam moment DFs — `distribution.moment_df_interior_box`
- [x] 4.6.2.2.3a type (g) box-beam shear DFs — `distribution.shear_df_interior_box`
- [x] 4.6.2.2.2b/.3a type (d) multicell box DFs — `distribution.*_df_interior_multicell`
- [x] 4.6.2.2.2b/.3a spread box beam DFs — `distribution.*_df_interior_spread_box`
- (T-beams, type (e), share the type a/e/k I-girder formulas above)
- [x] 6.10.11.2.3 Bearing stiffener bearing resistance — `steel.bearing_stiffener_resistance`

### Timber (Chapter 8)
- [x] 8.4.4.2 CKF, 8.4.4.4 CF, 8.4.4.7 Ci, 8.4.4.9 Clambda — `timber`
- [x] 8.6.2 Beam stability CL (KbE by grading) — `timber.beam_stability_cl`
- [x] 8.8.3 Bearing factor Cb — `timber.bearing_factor_cb`
- [x] 8.6 Flexural resistance — `timber.timber_flexural_resistance`
- [x] 8.4.4.5 Cv glulam volume factor — `timber.volume_factor_cv`
- [x] 8.7 Column stability Cp — `timber.column_stability_cp`
- [x] 8.4.4.3 Wet service CM (sawn + glulam, footnote waivers) — `timber.wet_service_cm`
- [x] 8.4.4.6 Flat use Cfu (sawn table + glulam (12/d)^(1/9)) — `timber.flat_use_cfu`
- [x] 8.4.4.8 Deck factor Cd — `timber.deck_factor_cd`
- [x] 8.8.2 Tension members — `timber.timber_tension_resistance`
- [x] 8.7 Compression members (Pr = phi*Fc*Ag*Cp) — `timber.timber_compression_resistance`

### LRFR (MBE Section 6A)
- [x] 6A.4.2.1 General rating equation (condition/system factors, 0.85 floor) — `lrfr.rating_factor`
- [x] 6A.4.4.2.3a Legal load factor by ADTT — `lrfr.legal_load_factor`
- [x] 6A.8.3 Posting load — `lrfr.posting_load`
- [x] 6A.4.5.4.2a Permit load factors (routine GVW/AL bands + special crossings, ADTT interpolation, agency overrides) — `lrfr.permit_load_factor`

### Strut-and-tie (5.8.2 — implemented from spec)
- [x] 5.8.2.4 Tie resistance — `stm.stm_tie_resistance`
- [x] 5.8.2.5 Node/strut crushing (nu table, confinement) — `stm.stm_node_resistance`
- [x] 5.8.2.6 Crack-control reinforcement ratio — `stm.stm_crack_control_reinforcement`
- (truss solver + diagram: `civilpy.structural.strut_and_tie`)

### Appendix B6 (steel moment redistribution)
- [x] B6.2.1 / B6.2.2 / B6.2.4 scope checks — `appendix_b6.b6_web_proportions`, `b6_flange_proportions`, `b6_bracing_limit`
- [x] B6.5 Effective plastic moment (enhanced B6.5.1 + ordinary B6.5.2) — `appendix_b6.b6_effective_plastic_moment`
- [x] B6.3.3.1 / B6.4.2.1 Redistribution moments (0.2|Me| cap) — `appendix_b6.b6_redistribution_moment`

### Decks and railings
- [x] A13.3.1 Parapet yield-line resistance — `railing.parapet_yield_line_capacity`
- [x] A13.4.2 Deck overhang collision tension — `railing.deck_overhang_collision_tension`
- [x] Table A13.2-1 test-level forces (verified unchanged 1st–10th Ed.; 10th Ed. min rail height H added) — `railing.TEST_LEVEL_LOADS`

## To do (rough priority order)


### Other
- [x] 5.12.7.3 Box-culvert slab shear (>=2 ft fill, single-cell floors) — `concrete.box_culvert_slab_shear`
- [x] Box-culvert soil-structure interaction → `civilpy.structural.cande.BoxCulvertModel` builds and runs CANDE Level-2 box models via the `cande-wrapper` package (replaces a standalone 3.6.1.2.6 port; CANDE handles load through fill directly)
