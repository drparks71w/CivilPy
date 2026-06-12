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

### Analysis / loads (done)
- [x] 4.6.2.2.2b/.3a Interior moment & shear DFs (I-girders, type a/e/k) — `distribution.moment_df_interior`, `shear_df_interior`
- [x] 4.6.2.2.2d/.3b Exterior DFs via e-factor — `distribution.moment_df_exterior`, `shear_df_exterior`
- [x] 4.6.2.2.2e/.3c Skew corrections — `distribution.skew_correction_*`
- [x] 3.6.2 Dynamic load allowance — `distribution.dynamic_load_allowance`

### Decks and railings
- [x] A13.3.1 Parapet yield-line resistance — `railing.parapet_yield_line_capacity`
- [x] A13.4.2 Deck overhang collision tension — `railing.deck_overhang_collision_tension`
- [x] Table A13.2-1 test-level forces (NCHRP 350 era, 1st–9th Ed.) — `railing.TEST_LEVEL_LOADS`

## To do (rough priority order)

### Prestressed — refined losses & details
- [ ] 5.9.3.2.1 Anchorage set

### Steel
- [ ] 6.10.11.2 Bearing stiffeners
- [ ] 6.10.3 Constructibility
- [ ] Appendix A6 (compact-web negative flexure), B6 (moment redistribution)
- [ ] 6.13 splices (flange/web), block shear 6.13.4, fillet welds 6.13.3

### Analysis / loads
- [ ] 4.6.2.2 DFs for other cross-section types (boxes, slabs, T-beams); lever-rule helper
- [ ] 4.6.2.6 Effective flange width (edition delta: 2008 change)
- [ ] 3.6.1.1.2 Multiple presence factors (standalone)

### Other
- [ ] RC columns: 5.6.4.x reinforcement limits, biaxial flexure
- [ ] Deflections/camber 5.6.3.5.2
- [ ] Timber Chapter 8 adjustment-factor chain
- [ ] Box-culvert variants of Ch. 5 checks
- [ ] 10th Ed. MASH railing forces (Table A13.2-1 revision) — verify values
- [ ] LRFR (MBE) rating-factor wrappers around these checks
