import numbers
import unittest
from civilpy.state.ohio.dot import Project


class TestProject(unittest.TestCase):
    def setUp(self, pid=96213):
        # Creates a 'test bridge' and makes sure none of the attributes have changed
        self.tp = Project(pid)

    def tearDown(self):
        pass

    def test_init(self):

        self.assertIsInstance(self.tp.objectid, int)
        self.assertIsInstance(self.tp.gis_id, int)
        self.assertEqual(self.tp.pid_nbr, 96213)
        self.assertEqual(self.tp.district_nbr, 6)
        self.assertEqual(self.tp.locale_short_nme, 'MRW')
        self.assertEqual(self.tp.county_nme, 'Morrow')
        self.assertEqual(self.tp.project_nme, 'MRW SR 314 (8.080) (20.57)')
        self.assertEqual(self.tp.contract_type, 'Standard Build')
        self.assertEqual(self.tp.primary_fund_category_txt, 'District Preservation (Pv & Br)')
        self.assertEqual(self.tp.project_manager_nme, 'HIPP, JEFFREY P')
        self.assertEqual(self.tp.reservoir_year, None)
        self.assertEqual(self.tp.tier, None)
        self.assertEqual(self.tp.odot_letting, 'ODOT Let')
        self.assertEqual(self.tp.schedule_type_short_nme, 'Standard')
        self.assertEqual(self.tp.env_project_manager_nme, 'TURNER, AMY S')
        self.assertEqual(self.tp.area_engineer_nme, 'DENNIS, WADE R')
        self.assertEqual(self.tp.project_engineer_nme, 'STOVER, DONALD L')
        self.assertEqual(self.tp.design_agency, 'DISTRICT 6-ENGINEERING')
        self.assertEqual(self.tp.sponsoring_agency, 'DISTRICT 6-PLANNING')
        self.assertEqual(self.tp.pdp_short_name, 'Path 2')
        self.assertEqual(self.tp.primary_work_category, 'Bridge Preservation')
        self.assertEqual(self.tp.project_status, 'Not Filed')
        self.assertEqual(self.tp.fiscal_year, '2024')
        self.assertEqual(self.tp.inhouse_design_full_nme, 'HIPP, JEFFREY P')
        self.assertEqual(self.tp.est_total_constr_cost, 650000)
        self.assertEqual(self.tp.state_project_nbr, None)
        self.assertEqual(self.tp.constr_vendor_nme, None)
        self.assertEqual(self.tp.stip_flag, None)
        self.assertEqual(self.tp.current_stip_co_amt, None)
        self.assertEqual(self.tp.project_plans_url, 'http://contracts.dot.state.oh.us/search.jsp?cabinetId=1002&PID_NUM=96213')
        self.assertEqual(self.tp.project_addenda_url, 'http://contracts.dot.state.oh.us/search.jsp?cabinetId=1000&PID_NUM=96213')
        self.assertEqual(self.tp.project_proposal_url, 'http://contracts.dot.state.oh.us/search.jsp?cabinetId=1003&PID_NUM=96213')
        self.assertEqual(self.tp.fmis_proj_desc, None)
        self.assertEqual(self.tp.award_milestone_dt, 1699228800000)
        self.assertEqual(self.tp.begin_constr_milestone_dt, 1713139200000)
        self.assertEqual(self.tp.end_constr_milestone_dt, 1722470400000)
        self.assertEqual(self.tp.open_traffic_dt, None)
        self.assertEqual(self.tp.central_office_close_dt, None)
        self.assertIsInstance(self.tp.source_last_updated, int)
        self.assertIsInstance(self.tp.cod_last_updated, int)
        self.assertEqual(self.tp.preserv_funds_ind, 'Y')
        self.assertEqual(self.tp.major_brg_funds_ind, 'N')
        self.assertEqual(self.tp.major_new_funds_ind, 'N')
        self.assertEqual(self.tp.major_rehab_funds_ind, 'N')
        self.assertEqual(self.tp.mpo_funds_ind, 'N')
        self.assertEqual(self.tp.safety_funds_ind, 'N')
        self.assertEqual(self.tp.local_funds_ind, 'N')
        self.assertEqual(self.tp.other_funds_ind, 'N')
        self.assertEqual(self.tp.nlf_id, 'SMRWSR00314**C')
        self.assertEqual(self.tp.ctl_begin, 8.108)
        self.assertEqual(self.tp.ctl_end, None)
        self.assertEqual(self.tp.gis_feature_type, 'POINT')
        self.assertEqual(self.tp.route_type, 'SR')
        self.assertEqual(self.tp.route_id, '00314')
        self.assertEqual(self.tp.structure_file_nbr, '5903033')
        self.assertEqual(self.tp.main_structure_type, '505N')
        self.assertEqual(self.tp.sufficiency_rating, '065.9')
        self.assertEqual(self.tp.ovrl_structure_length, 19.9)
        self.assertEqual(self.tp.deck_area, 637)
        self.assertEqual(self.tp.deck_width, 32)
        self.assertEqual(self.tp.feature_intersect, '                         ')
        self.assertEqual(self.tp.year_built, '1973')
        self.assertEqual(self.tp.longitude_begin_nbr, -82.696729)
        self.assertEqual(self.tp.latitude_begin_nbr, 40.457102)
        self.assertEqual(self.tp.longitude_end_nbr, None)
        self.assertEqual(self.tp.latitude_end_nbr, None)
        self.assertEqual(self.tp.county_cd_work_location, 'MRW')
        self.assertEqual(self.tp.county_nme_work_location, 'MORROW')
        self.assertEqual(self.tp.district_work_location, '06')
        self.assertEqual(self.tp.pavement_treatment_type, None)
        self.assertEqual(self.tp.pavement_treatment_category, None)
        self.assertEqual(self.tp.created_user, 'TIMS@P31_AG')
        self.assertIsInstance(self.tp.created_date, int)
        self.assertEqual(self.tp.last_edited_user, 'TIMS@P31_AG')
        self.assertIsInstance(self.tp.last_edited_date, int)


if __name__ == '__main__':
    unittest.main()
