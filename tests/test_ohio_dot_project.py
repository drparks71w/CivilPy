import unittest
from civilpy.state.ohio.dot import Project


class TestProject(unittest.TestCase):
    def setUp(self, pid=112664):
        # Creates a 'test bridge' and makes sure none of the attributes have changed
        self.tp = Project(pid)

    def tearDown(self):
        pass

    def test_init(self):

        self.assertEqual(self.tp.objectid, 33700661)
        self.assertEqual(self.tp.gis_id, 69805)
        self.assertEqual(self.tp.pid_nbr, 112664)
        self.assertEqual(self.tp.district_nbr, 6)
        self.assertEqual(self.tp.locale_short_nme, 'FRA')
        self.assertEqual(self.tp.county_nme, 'Franklin')
        self.assertEqual(self.tp.project_nme, 'D06-FY23 Bridge Repair')
        self.assertEqual(self.tp.contract_type, 'Standard Build')
        self.assertEqual(self.tp.primary_fund_category_txt, 'District Preservation (Pv & Br)')
        self.assertEqual(self.tp.project_manager_nme, 'PARKS, DANE RICHARD')
        self.assertEqual(self.tp.reservoir_year, None)
        self.assertEqual(self.tp.tier, None)
        self.assertEqual(self.tp.odot_letting, 'ODOT Let')
        self.assertEqual(self.tp.schedule_type_short_nme, 'Standard')
        self.assertEqual(self.tp.env_project_manager_nme, 'GARTNER, JANICE M')
        self.assertEqual(self.tp.area_engineer_nme, 'WISE, DANIEL S')
        self.assertEqual(self.tp.project_engineer_nme, 'FIRIS, BENJAMIN L')
        self.assertEqual(self.tp.design_agency, 'DISTRICT 6-ENGINEERING')
        self.assertEqual(self.tp.sponsoring_agency, 'DISTRICT 6-BRIDGES')
        self.assertEqual(self.tp.pdp_short_name, 'Path 1')
        self.assertEqual(self.tp.primary_work_category, 'Bridge Preservation')
        self.assertEqual(self.tp.project_status, 'Filed')
        self.assertEqual(self.tp.fiscal_year, '2023')
        self.assertEqual(self.tp.inhouse_design_full_nme, 'BLOOR, CLAYTON  ')
        self.assertEqual(self.tp.est_total_constr_cost, 571848.74)
        self.assertEqual(self.tp.state_project_nbr, None)
        self.assertEqual(self.tp.constr_vendor_nme, None)
        self.assertEqual(self.tp.stip_flag, None)
        self.assertEqual(self.tp.current_stip_co_amt, None)
        self.assertEqual(self.tp.project_plans_url, 'http://contracts.dot.state.oh.us/search.jsp?cabinetId=1002&PID_NUM=112664')
        self.assertEqual(self.tp.project_addenda_url, 'http://contracts.dot.state.oh.us/search.jsp?cabinetId=1000&PID_NUM=112664')
        self.assertEqual(self.tp.project_proposal_url, 'http://contracts.dot.state.oh.us/search.jsp?cabinetId=1003&PID_NUM=112664')
        self.assertEqual(self.tp.fmis_proj_desc, None)
        self.assertEqual(self.tp.award_milestone_dt, 1676851200000)
        self.assertEqual(self.tp.begin_constr_milestone_dt, 1681516800000)
        self.assertEqual(self.tp.end_constr_milestone_dt, 1693440000000)
        self.assertEqual(self.tp.open_traffic_dt, None)
        self.assertEqual(self.tp.central_office_close_dt, None)
        self.assertEqual(self.tp.source_last_updated, 1674950400000)
        self.assertEqual(self.tp.cod_last_updated, 1674950400000)
        self.assertEqual(self.tp.preserv_funds_ind, 'Y')
        self.assertEqual(self.tp.major_brg_funds_ind, 'N')
        self.assertEqual(self.tp.major_new_funds_ind, 'N')
        self.assertEqual(self.tp.major_rehab_funds_ind, 'N')
        self.assertEqual(self.tp.mpo_funds_ind, 'N')
        self.assertEqual(self.tp.safety_funds_ind, 'N')
        self.assertEqual(self.tp.local_funds_ind, 'N')
        self.assertEqual(self.tp.other_funds_ind, 'N')
        self.assertEqual(self.tp.nlf_id, 'CFRACR00122**C')
        self.assertEqual(self.tp.ctl_begin, 6.3)
        self.assertEqual(self.tp.ctl_end, None)
        self.assertEqual(self.tp.gis_feature_type, 'POINT')
        self.assertEqual(self.tp.route_type, 'CR')
        self.assertEqual(self.tp.route_id, '00122')
        self.assertEqual(self.tp.structure_file_nbr, '2508923')
        self.assertEqual(self.tp.main_structure_type, '402N')
        self.assertEqual(self.tp.sufficiency_rating, '088.5')
        self.assertEqual(self.tp.ovrl_structure_length, 240)
        self.assertEqual(self.tp.deck_area, 18480)
        self.assertEqual(self.tp.deck_width, 77)
        self.assertEqual(self.tp.feature_intersect, "ALUM CREEK DRIVE         ")
        self.assertEqual(self.tp.year_built, '1986')
        self.assertEqual(self.tp.longitude_begin_nbr, -82.931349)
        self.assertEqual(self.tp.latitude_begin_nbr, 39.91958)
        self.assertEqual(self.tp.longitude_end_nbr, None)
        self.assertEqual(self.tp.latitude_end_nbr, None)
        self.assertEqual(self.tp.county_cd_work_location, 'FRA')
        self.assertEqual(self.tp.county_nme_work_location, 'FRANKLIN')
        self.assertEqual(self.tp.district_work_location, '06')
        self.assertEqual(self.tp.pavement_treatment_type, None)
        self.assertEqual(self.tp.pavement_treatment_category, None)
        self.assertEqual(self.tp.created_user, 'TIMS@P31_AG')
        self.assertEqual(self.tp.created_date, 1674983382000)
        self.assertEqual(self.tp.last_edited_user, 'TIMS@P31_AG')
        self.assertEqual(self.tp.last_edited_date, 1674983382000)


if __name__ == '__main__':
    unittest.main()
