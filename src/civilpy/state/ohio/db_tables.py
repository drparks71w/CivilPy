import os
import sys
import logging
from pathlib import Path
from collections import defaultdict
from pydantic import ValidationError


def setup_django_environment(project_root):
    """
    Configures the Django environment by adding the project path to sys.path
    and detecting the settings module.
    """
    path_obj = Path(project_root).resolve()

    if not path_obj.exists():
        raise FileNotFoundError(f"Project path does not exist: {path_obj}")

    # 1. Add project to Python Path so 'bridges' app can be imported
    if str(path_obj) not in sys.path:
        sys.path.insert(0, str(path_obj))

    # 2. Detect Settings Module
    # Look for 'settings.py' to determine the module name (e.g., 'core.settings')
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")

    if not settings_module:
        potential_settings = []
        for root, dirs, files in os.walk(path_obj):
            if "settings.py" in files:
                # Calculate relative path to form module string
                rel_path = os.path.relpath(root, path_obj)
                if rel_path == ".":
                    # If settings.py is in root, assume folder name is package?
                    # Usually it's in a subdir. Let's look for subdir.
                    continue
                module_str = rel_path.replace(os.sep, ".") + ".settings"
                potential_settings.append(module_str)

        if potential_settings:
            # Default to the first found, or prefer 'core.settings' if available
            settings_module = "core.settings" if "core.settings" in potential_settings else potential_settings[0]
            print(f"ℹ️  Auto-detected Django settings: {settings_module}")
        else:
            print("⚠️  Could not auto-detect settings.py. Defaulting to 'core.settings'.")
            settings_module = "core.settings"

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)

    # 3. Allow Sync (Critical for Jupyter/Script usage)
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

    try:
        import django
        django.setup()
        print("✅ Django configured successfully.")
    except Exception as e:
        print(f"❌ Failed to setup Django: {e}")
        sys.exit(1)


def validate_bridge_data(project_path, target_district=None):
    """
    Main function to run validation.
    """
    # --- 1. SETUP ---
    setup_django_environment(project_path)

    # Import Models (Must happen AFTER django.setup)
    try:
        from bridges.models import Bridge as DjangoBridge
        print("✅ Django Bridge model imported.")
    except ImportError as e:
        print(f"❌ Could not import 'bridges.models'. Is the app name correct? Error: {e}")
        return

    try:
        # Import the strict model directly from civilpy
        from civilpy.state.ohio.snbi import Bridge as SNBIBridge
        print("✅ CivilPy SNBI Bridge model imported.")
    except ImportError as e:
        print(f"❌ Could not import 'civilpy'. Please install it via pip. Error: {e}")
        return

    # --- 2. CONFIGURATION ---
    ODOT_DISTRICT_MAP = {
        "1": [3, 39, 63, 65, 125, 137, 161, 175],
        "2": [51, 69, 95, 123, 143, 147, 171, 173],
        "3": [5, 33, 43, 77, 93, 103, 139, 169],
        "4": [7, 99, 133, 151, 153, 155],
        "5": [31, 45, 59, 83, 89, 119, 127],
        "6": [41, 47, 49, 97, 101, 117, 129, 159],
        "7": [11, 21, 23, 37, 91, 107, 109, 113, 149],
        "8": [17, 25, 27, 57, 61, 135, 165],
        "9": [1, 15, 71, 79, 87, 131, 141, 145],
        "10": [9, 53, 73, 105, 111, 115, 121, 163, 167],
        "11": [13, 19, 29, 67, 75, 81, 157],
        "12": [35, 55, 85]
    }

    # --- 3. LOGGING SETUP ---
    log_filename = f"d{target_district}_validation_log.txt" if target_district else "statewide_validation_log.txt"

    # Reset handlers to avoid duplicates if run multiple times
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        filename=log_filename,
        filemode='w',
        format='%(message)s',
        level=logging.INFO
    )

    print(f"\n🔍 Starting Validation... (Detailed output logging to '{log_filename}')")

    # --- 4. QUERY BUILDER ---
    qs = DjangoBridge.objects.all()

    if target_district:
        if str(target_district) in ODOT_DISTRICT_MAP:
            target_counties = ODOT_DISTRICT_MAP[str(target_district)]
            qs = qs.filter(bl02_county_code__in=target_counties)
            print(f"   Targeting District {target_district} (Counties: {target_counties})")
            logging.info(f"Targeting District {target_district} (Counties: {target_counties})")
        else:
            print(f"   ⚠️ District {target_district} not found in map. Scanning all.")
            logging.warning(f"District {target_district} not found. Scanning statewide.")
    else:
        print("   Scanning Statewide.")

    # --- 5. VALIDATION LOOP ---
    django_bridges = qs.iterator()
    error_count = 0
    success_count = 0
    field_error_counts = defaultdict(int)

    for i, db_bridge in enumerate(django_bridges):
        if i % 1000 == 0 and i > 0:
            print(f"   Processed {i} bridges...")

        # Map Django Model Fields to Pydantic SNBI Fields
        data = {
            # B.ID (Identification)
            "BID01": db_bridge.bid01_bridge_number,
            "BID02": db_bridge.bid02_bridge_name,
            "BID03": db_bridge.bid03_prev_bridge_number if db_bridge.bid03_prev_bridge_number else "0",

            # B.L (Location)
            "BL01": db_bridge.bl01_state_code,
            "BL02": db_bridge.bl02_county_code,
            "BL03": db_bridge.bl03_place_code,
            "BL04": None,  # Cast below
            "BL05": db_bridge.bl05_latitude,
            "BL06": db_bridge.bl06_longitude,
            "BL07": db_bridge.bl07_border_bridge_num,
            "BL08": db_bridge.bl08_border_state_code,
            "BL09": db_bridge.bl09_border_insp_resp,
            "BL10": db_bridge.bl10_border_lead_state,
            "BL11": db_bridge.bl11_bridge_location,
            "BL12": db_bridge.bl12_mpo,

            # B.CL (Classification)
            "BCL01": db_bridge.bcl01_owner,
            "BCL02": db_bridge.bcl02_maint_resp,
            "BCL03": db_bridge.bcl03_land_access,
            "BCL04": db_bridge.bcl04_historic_sig,
            "BCL05": db_bridge.bcl05_toll,
            "BCL06": db_bridge.bcl06_emerg_evac,

            # B.RH (Roadside Hardware)
            "BRH01": db_bridge.brh01_railings,
            "BRH02": db_bridge.brh02_transitions,

            # B.G (Geometry)
            "BG01": db_bridge.bg01_nbis_len,
            "BG02": db_bridge.bg02_total_len,
            "BG03": db_bridge.bg03_max_span_len,
            "BG04": db_bridge.bg04_min_span_len,
            "BG05": db_bridge.bg05_width_out_to_out,
            "BG06": db_bridge.bg06_width_curb_to_curb,
            "BG07": db_bridge.bg07_left_curb_width,
            "BG08": db_bridge.bg08_right_curb_width,
            "BG09": db_bridge.bg09_appr_road_width,
            "BG10": db_bridge.bg10_median,
            "BG11": db_bridge.bg11_skew,
            "BG12": db_bridge.bg12_curved,
            "BG13": db_bridge.bg13_max_height,
            "BG14": db_bridge.bg14_sidehill,
            "BG15": db_bridge.bg15_irregular_area,
            "BG16": db_bridge.bg16_calc_deck_area,

            # B.LR (Loads & Rating)
            "BLR01": db_bridge.blr01_design_load,
            "BLR02": db_bridge.blr02_design_method,
            "BLR03": db_bridge.blr03_load_date,
            "BLR04": db_bridge.blr04_rating_method,
            "BLR05": db_bridge.blr05_inv_factor,
            "BLR06": db_bridge.blr06_opr_factor,
            "BLR07": db_bridge.blr07_legal_factor,
            "BLR08": db_bridge.blr08_permit_loads,

            # B.IR (Inspection Requirements)
            "BIR01": db_bridge.bir01_nstm_req,
            "BIR02": db_bridge.bir02_fatigue,
            "BIR03": db_bridge.bir03_underwater_req,
            "BIR04": db_bridge.bir04_complex_feature,

            # B.C (Condition Ratings)
            "BC01": db_bridge.bc01_deck_cond,
            "BC02": db_bridge.bc02_super_cond,
            "BC03": db_bridge.bc03_sub_cond,
            "BC04": db_bridge.bc04_culvert_cond,
            "BC05": db_bridge.bc05_rail_cond,
            "BC06": db_bridge.bc06_trans_cond,
            "BC07": db_bridge.bc07_bearing_cond,
            "BC08": db_bridge.bc08_joint_cond,
            "BC09": db_bridge.bc09_channel_cond,
            "BC10": db_bridge.bc10_prot_cond,
            "BC11": db_bridge.bc11_scour_cond,
            "BC12": db_bridge.bc12_cond_class,
            "BC13": db_bridge.bc13_lowest_rating,
            "BC14": db_bridge.bc14_nstm_cond,
            "BC15": db_bridge.bc15_underwater_cond,

            # B.AP (Appraisal)
            "BAP01": db_bridge.bap01_appr_align,
            "BAP02": db_bridge.bap02_overtopping,
            "BAP03": db_bridge.bap03_scour_vuln,
            "BAP04": db_bridge.bap04_scour_poa,
            "BAP05": db_bridge.bap05_seismic,

            # B.W (Work)
            # BW02 and BW03 omitted as they are in child tables, only checking Year Built
            "BW01": db_bridge.bw01_year_built,
        }

        # Casting Logic: Ensure District is Int
        if db_bridge.bl04_highway_district and str(db_bridge.bl04_highway_district).isdigit():
            data["BL04"] = int(db_bridge.bl04_highway_district)

        try:
            # Validate using the imported CivilPy strict model
            SNBIBridge(**data)
            success_count += 1
        except ValidationError as e:
            error_count += 1
            logging.info(f"\n❌ Bridge {db_bridge.bid01_bridge_number} Failed:")
            for err in e.errors():
                field_name = str(err['loc'][0])
                error_msg = err['msg']
                value = data.get(field_name)
                logging.info(f"   - Field: {field_name} | Value: '{value}' | Issue: {error_msg}")
                field_error_counts[field_name] += 1
            logging.info("-" * 40)

    # 6. RESULTS
    print(f"\n✅ Validation Complete.")
    print(f"   Success: {success_count}")
    print(f"   Errors:  {error_count}")
    print(f"   Log saved to: {os.path.abspath(log_filename)}")

    # Append summary to log
    logging.info("\n" + "=" * 40)
    logging.info("📊 ERROR SUMMARY BY FIELD")
    logging.info("=" * 40)
    for field, count in sorted(field_error_counts.items(), key=lambda item: item[1], reverse=True):
        logging.info(f"   - {field}: {count} failures")


if __name__ == "__main__":
    print("--- SNBI Bridge Validator ---")

    # Prompt for Project Path
    default_path = os.getcwd()
    path_input = input(f"Enter Django Project Root [Default: {default_path}]: ").strip()
    project_path = path_input if path_input else default_path

    # Prompt for District
    dist_input = input("Enter Target District (1-12) [Default: All]: ").strip()
    target_district = dist_input if dist_input else None

    validate_bridge_data(project_path, target_district)