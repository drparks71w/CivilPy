import os
import re
import folium
import pandas as pd
from pathlib import Path
from PIL import Image, ImageSequence
import math
import tifftools
from natsort import natsorted
from bs4 import BeautifulSoup
from urllib.request import urlopen
import json
import requests


def help_function():
    """
    To use the dicts, import them into python, and then use the two letter code to get the translations, i.e.
    basemap_labels['BA'] will return "Aerial Mapping"

    General Notes:
    General File Naming Format:
        nnnnn(n)_aa###.dgn where:
            nnnnnn - 5 (or 6) digit PID
            aa     - Two letter code signifying sheet type (see dicts)
            ###    - Three digit number identifying the number of drawings of the same type

    Bridge Design File Naming Format:
        nnnnnn_SFNyyyyyyy_aa###.dgn where:
            nnnnnn   - PID
            yyyyyyy  - 7 digit SFN of the structure
            aa       - Two character bridge plan sheet type
            ###      - Three digit number identifying the number of drawings of the same type

    Culvert Design File Naming Format:
        nnnnnn_CFNyyyyyyy_aa###.dgn where:
            nnnnnn  - PID
            yyyyyyy - 7 digit CFN number of the culvert
            aa      - Two character drainage plan sheet type
            ###     - Three digit number identifying the number of drawings of the same type

    Wall Design File Naming Format:
        nnnnnn_WALLyyy_aa###.dgn where:
            nnnnnn  - PID
            yyy     - Three digit wall number
            aa      - Two digit wall plan sheet type
            ###     - Three digit number identifying the number of drawings of the same type
    """


basemap_labels = {
    'KB': '3D Model KB',
    'KM': '3D Modeling KM',
    'BC': 'Aerial and Ground Combined',
    'BA': 'Aerial Mapping',
    'BS': 'Bridge',
    'KD': 'Digital Terrain Model',
    'BD': 'Drainage',
    'FD': 'Field Digital Terrain Model',
    'BK': 'Geometry',
    'BI': 'Geotechnical',
    'BL': 'Landscaping',
    'BH': 'Lighting',
    'BM': 'MOT',
    'PC': 'Point Cloud',
    'BR': 'Right-of-Way',
    'BP': 'Roadway',
    'BG': 'Signals',
    'KS': 'Superelevation',
    'FB': 'Survey Field Book',
    'BT': 'Traffic Control',
    'BU': 'Utilities',
    'BW': 'Wall'
}

bridge_labels = {
    'SB': 'Bearing',
    'SD': 'Deck Plan',
    'SQ': 'Estimated Quantities',
    'SX': 'Expansion Device Details',
    'SF': 'Forward Abutment',
    'SO': 'Foundation Plan',
    'SN': 'General Notes',
    'SG': 'General Plan',
    'SM': 'Miscellaneous Details',
    'SI': 'Piers',
    'SA': 'Railing',
    'SR': 'Rear Abutment',
    'SL': 'Reinforcing Steel List',
    'SV': 'Removal',
    'SH': 'Sheeting',
    'SP': 'Site Plan',
    'SC': 'Staged Construction Details',
    'SS': 'Superstructure Details',
    'ST': 'Transverse Section'
}

drainage_labels = {
    'XD': 'Channel Cross Sections',
    'DC': 'Culvert Details',
    'DD': 'Details',
    'DE': 'Erosion Control',
    'DM': 'Miscellaneous Details',
    'DN': 'Notes',
    'DP': 'Plan and Profile or Plan',
    'DF': 'Profile',
    'DQ': 'Quantity Table',
    'DB': 'Schematic Plan',
    'DS': 'Sub-Summary'
}

geotechnical_labels = {
    'YL': 'Geohazard Boring Logs',
    'YC': 'Geohazard Cover',
    'YX': 'Geohazard Cross Sections',
    'YD': 'Geohazard Lab Data',
    'YP': 'Geohazard Plan and Profile',
    'YF': 'Geohazard Profile',
    'IC': 'Soil Profile Cover',
    'IX': 'Soil Profile Cross Sections',
    'ID': 'Soil Profile Lad Data',
    'IP': 'Soil Profile, Plan and Profile or Plan',
    'IF': 'Soil Profile, Profile Only',
    'ZL': 'Structure Foundation Exploration Boring Logs',
    'ZC': 'Structure Foundation Exploration Cover',
    'ZD': 'Structure Foundation Exploration Lab Data',
    'ZP': 'Structure Foundation Exploration Plan and Profile',
    'ZF': 'Structure Foundation Exploration Profile'
}

landscaping_labels = {
    'PD': 'Details',
    'PM': 'Miscellaneous Details',
    'PN': 'Notes',
    'PP': 'Plan',
    'PB': 'Schematic Plan',
    'PS': 'Sub-Summary',
}

lighting_labels = {
    'LC': 'Circuit Diagrams',
    'LD': 'Details',
    'LE': 'Elevation Views',
    'LG': 'General Summary',
    'LM': 'Miscellaneous',
    'LN': 'Notes',
    'LP': 'Plan',
    'LQ': 'Quantity Table',
    'LB': 'Schematic Plan',
    'LS': 'Sub-Summary'
}

mot_labels = {
    'XM': 'Cross Sections',
    'MD': 'Detour Plan',
    'MM': 'Miscellaneous',
    'MN': 'Notes',
    'MP': 'Phase Plan and Profile or Plan',
    'MH': 'Phase Details',
    'MF': 'Profile',
    'MQ': 'Quantity Table',
    'MB': 'Schematic Plan',
    'MS': 'Sub-Summary',
    'MY': 'Typical Sections'
}

row_labels = {
    'RC': 'Centerline Plat',
    'RL': 'Legend',
    'RM': 'Property Map',
    'RR': 'Railroad Plat',
    'RB': 'RW Boundary',
    'RD': 'RW Detail',
    'RT': 'RW Topo',
    'RS': 'Summary of Additional RW'
}

roadway_labels = {
    'GC': 'Calculations/Computations',
    'XS': 'Cross Sections',
    'GD': 'Drive Details',
    'GX': 'Fencing Plan',
    'GN': 'General Notes',
    'GG': 'General Summary',
    'XG': 'Grading Plan',
    'GR': 'Guardrail/Barrier Details',
    'GI': 'Intersection/Interchange Details',
    'GJ': 'Maintenance Data',
    'GM': 'Miscellaneous',
    'GA': 'Pavement Details',
    'GP': 'Plan and Profile or Plan',
    'GF': 'Profile',
    'GQ': 'Quantity Table',
    'GB': 'Schematic Plan',
    'GS': 'Sub-Summary',
    'GE': 'Superelevation Table',
    'GT': 'Title Sheet',
    'GY': 'Typical Sections'
}

signal_labels = {
    'CD': 'Details',
    'CG': 'General Summary',
    'CM': 'Miscellaneous',
    'CN': 'Notes',
    'CP': 'Plan',
    'CQ': 'Quantity Table',
    'CS': 'Sub-Summary'
}

traffic_control_labels = {
    'TC': 'Calculations/Computations',
    'TD': 'Details',
    'TE': 'Elevation Views',
    'TN': 'General Notes',
    'TG': 'General Summary',
    'TM': 'Miscellaneous',
    'TP': 'Plan',
    'TQ': 'Quantity Table',
    'TB': 'Schematic Plan',
    'TS': 'Sub-Summary'
}

utility_labels = {
    'UC': 'Calculations/Computations',
    'UD': 'Details',
    'UE': 'Elevation Views',
    'UG': 'General Summary',
    'UM': 'Miscellaneous',
    'UN': 'Notes',
    'UP': 'Plan and Profile or Plan',
    'UF': 'Profile',
    'UQ': 'Quantity Table',
    'UB': 'Schematic Plan',
    'US': 'Sub-Summary'
}

wall_labels = {
    'WC': 'Calculations/Computations',
    'WX': 'Cross Sections',
    'WD': 'Details',
    'WE': 'Elevation',
    'WQ': 'Estimated Quantities',
    'WT': 'Foundation',
    'WM': 'Miscellaneous',
    'WN': 'Notes',
    'WP': 'Plan and Profile or Plan',
    'WF': 'Profile',
    'WB': 'Schematic Plan',
    'WH': 'Sheeting',
    'WL': 'Steel List',
    'WS': 'Sub-Summary',
    'WY': 'Typical Section'
}

all_labels = {
    'basemap_labels': basemap_labels,
    'bridge_labels': bridge_labels,
    'drainage_labels': drainage_labels,
    'geotechnical_labels': geotechnical_labels,
    'landscaping_labels': landscaping_labels,
    'lighting_labels': lighting_labels,
    'mot_labels': mot_labels,
    'row_labels': row_labels,
    'roadway_labels': roadway_labels,
    'signal_labels': signal_labels,
    'traffic_control_labels': traffic_control_labels,
    'utility_labels': utility_labels,
    'wall_labels': wall_labels
}

# These are the 4 regular expressions I built to match our file conventions
gen_file_pattern = re.compile(r"\d{5,6}_\w{2}\d{3}.dgn$")
bridge_file_pattern = re.compile(r"\d{5,6}_SFN\d{7}_\w{2}\d{3}.dgn$")
culvert_file_pattern = re.compile(r"\d{5,6}_CFN\d{7}_\w{2}\d{3}.dgn$")
wall_file_pattern = re.compile(r"\d{5,6}_WALL\d{3}_\w{2}\d{3}.dgn$")


def filter_files_by_category(file_list, label_set):
    """
    Takes a list of files, and determines if any of them contain the labels specific to bridge files from ODOT CADD
    standards.

    :param file_list:
        An unfiltered list of all files to be searched
    :param label_set:
        The category of file you want returned, from the keys in the "all_labels" dictionary above
    :return category_files: a list of files containing relevant category info
    """

    temp_list = []
    category_files = []

    # Builds a list of all files containing the strings in 'bridge labels'
    for file in file_list:
        for label in label_set:
            if label in os.path.basename(file):
                temp_list.append(file)
            else:
                pass

    # Drop "EngData" folder files, generally contains reference files, not project ones
    for file in temp_list:
        if "EngData" not in file:
            category_files.append(file)
        else:
            pass

    return category_files


def get_bridge_data_from_tims(sfn):
    url = f"https://gis.dot.state.oh.us/arcgis/rest/services/TIMS/Assets/MapServer/5/query?where=SFN%3D{sfn}&text=&objectIds=&time=&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&relationParam=&outFields=*&returnGeometry=true&returnTrueCurves=false&maxAllowableOffset=&geometryPrecision=&outSR=&having=&returnIdsOnly=false&returnCountOnly=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&returnZ=false&returnM=false&gdbVersion=&historicMoment=&returnDistinctValues=false&resultOffset=&resultRecordCount=&queryByDistance=&returnExtentOnly=false&datumTransformation=&parameterValues=&rangeValues=&quantizationParameters=&featureEncoding=esriDefault&f=html"
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html5lib')

    bridge_link = soup.find_all('a')

    full_data_url = "https://gis.dot.state.oh.us/" + bridge_link[-1].get('href')
    full_data_url_json = full_data_url + '?f=pjson'

    print(f"\nRetrieving data from url at {full_data_url_json}\n")

    response = urlopen(full_data_url_json)
    data_json = json.loads(response.read())

    extracted_data = data_json['feature']['attributes']

    return extracted_data


ohio_counties = {
    "ADAMS": "ADA",
    "ALLEN": "ALL",
    "ASHLAND": "ASD",
    "ASHTABULA": "ATB",
    "ATHENS": "ATH",
    "AUGLAIZE": "AUG",
    "BELMONT": "BEL",
    "BROWN": "BRO",
    "BUTLER": "BUT",
    "CARROLL": "CAR",
    "CHAMPAIGN": "CHP",
    "CLARK": "CLA",
    "CLERMONT": "CLE",
    "CLINTON": "CLI",
    "COLUMBIANA": "COL",
    "COSHOCTON": "COS",
    "CRAWFORD": "CRA",
    "CUYAHOGA": "CUY",
    "DARKE": "DAR",
    "DEFIANCE": "DEF",
    "DELAWARE": "DEL",
    "ERIE": "ERI",
    "FAIRFIELD": "FAI",
    "FAYETTE": "FAY",
    "FRANKLIN": "FRA",
    "FULTON": "FUL",
    "GALLIA": "GAL",
    "GEAUGA": "GEA",
    "GREENE": "GRE",
    "GUERNSEY": "GUE",
    "HAMILTON": "HAM",
    "HANCOCK": "HAN",
    "HARDIN": "HAR",
    "HARRISON": "HAS",
    "HENRY": "HEN",
    "HIGHLAND": "HIG",
    "HOCKING": "HOC",
    "HOLMES": "HOL",
    "HURON": "HUR",
    "JACKSON": "JAC",
    "JEFFERSON": "JEF",
    "KNOX": "KNO",
    "LAKE": "LAK",
    "LAWRENCE": "LAW",
    "LICKING": "LIC",
    "LOGAN": "LOG",
    "LORAIN": "LOR",
    "LUCAS": "LUC",
    "MADISON": "MAD",
    "MAHONING": "MAH",
    "MARION": "MAR",
    "MEDINA": "MED",
    "MEIGS": "MEG",
    "MERCER": "MER",
    "MIAMI": "MIA",
    "MONROE": "MOE",
    "MONTGOMERY": "MOT",
    "MORGAN": "MRG",
    "MORROW": "MRW",
    "MUSKINGUM": "MUS",
    "NOBLE": "NOB",
    "OTTAWA": "OTT",
    "PAULDING": "PAU",
    "PERRY": "PER",
    "PICKAWAY": "PIC",
    "PIKE": "PIK",
    "PORTAGE": "POR",
    "PREBLE": "PRE",
    "PUTNAM": "PUT",
    "RICHLAND": "RIC",
    "ROSS": "ROS",
    "SANDUSKY": "SAN",
    "SCIOTO": "SCI",
    "SENECA": "SEN",
    "SHELBY": "SHE",
    "STARK": "STA",
    "SUMMIT": "SUM",
    "TRUMBULL": "TRU",
    "TUSCARAWAS": "TUS",
    "UNION": "UNI",
    "VAN WERT": "VAN",
    "VINTON": "VIN",
    "WARREN": "WAR",
    "WASHINGTON": "WAS",
    "WAYNE": "WAY",
    "WILLIAMS": "WIL",
    "WOOD": "WOO",
    "WYANDOT": "WYA",
}


NBIS_state_codes = {
    '014': 'Alabama',
    '308': 'Montana',
    '020': 'Alaska',
    '317': 'Nebraska',
    '049': 'Arizona',
    '329': 'Nevada',
    '056': 'Arkansas',
    '331': 'New Hampshire',
    '069': 'Californ',
    '342': 'New Jersey',
    '088': 'Colorado',
    '356': 'New Mexico',
    '091': 'Connecti',
    '362': 'New York',
    '103': 'Delaware',
    '374': 'North Carolina',
    '113': 'District of Columbia',
    '388': 'North Dakota',
    '124': 'Florida',
    '395': 'Ohio',
    '134': 'Georgia',
    '406': 'Oklahoma',
    '159': 'Hawaii',
    '410': 'Oregon',
    '160': 'Idaho',
    '423': 'Pennsylvania',
    '175': 'Illinois',
    '441': 'Rhode Island',
    '185': 'Indiana',
    '454': 'South Carolina',
    '197': 'Iowa',
    '468': 'South Dakota',
    '207': 'Kansas',
    '474': 'Tennessee',
    '214': 'Kentucky',
    '486': 'Texas',
    '226': 'Louisiana',
    '498': 'Utah',
    '231': 'Maine',
    '501': 'Vermont',
    '243': 'Maryland',
    '513': 'Virginia',
    '251': 'Massachusetts',
    '530': 'Washington',
    '265': 'Michigan',
    '543': 'West Virginia',
    '275': 'Minnesota',
    '555': 'Wisconsin',
    '284': 'Mississippi',
    '568': 'Wyoming',
    '297': 'Missouri',
    '721': 'Puerto Rico',
}


class BridgeObject:
    def __init__(self, sfn):
        df = pd.read_csv(f'{data_path}', sep='\t', low_memory=False)
        self.SFN = sfn

        bridge_details = df.iloc[df.index[df['Structure File Number'] == sfn]].iloc[0].to_dict()

        self.raw_data = bridge_details
        self.photo_url = ''
        self.plan_sets_list = []

        # //TODO - Seperate the following lines into a function
        dirty_long = str(self.raw_data['Longitude'])
        dirty_lat = str(self.raw_data['Latitude'])

        self.clean_lat = float(dirty_lat[:2]) + (float(dirty_lat[2:4]) / 60) + (
                    float(f'{dirty_lat[4:6]}.{dirty_lat[6:]}') / 3600)
        self.clean_long = -(float(dirty_long[:2]) + (
                    (float(dirty_long[2:4]) / 60) + (float(f'{dirty_long[4:6]}.{dirty_long[6:]}') / 3600)))

        self.cty_rte_sec = self.get_summary()



    def get_map(self):
        # Figure out how ODOT Codes Lat and Long to know which of these is correct (currently best guess based on 1 bridge)
        # clean_long = -float(dirty_long[:2]) - (float(dirty_long[2:4]) + (float(dirty_long[4:8]) / 1000))
        # clean_lat = float(dirty_lat[:2]) + (float(dirty_lat[2:4]) + (float(dirty_lat[4:8]) / 1000))

        f = folium.Figure(width=1500, height=700)

        m = folium.Map(
            width=1500,
            height=700,
            location=[self.clean_lat, self.clean_long],
            zoom_start=14
        ).add_to(f)

        folium.Marker(
            location=[self.clean_lat, self.clean_long],
            popup=f"{self.raw_data[f'Structure File Number']}<br><br>Lat: {self.clean_lat}<br>Long: {self.clean_long}",
            tooltip=self.raw_data[f'Structure File Number'],
            icon=folium.Icon(icon="info-sign"),
        ).add_to(m)

        return m

    def get_photos(self):
        url = 'https://brphotos.dot.state.oh.us/Bridges.aspx?county='
        self.photo_url = url + self.raw_data['County Code'] + '&route=' + self.raw_data['Route']

    def get_d6_plan_sets(self, district_df_path="G:\\ref\\New folder\\PLANINDX.TXT"):
        """
        Using the "CTY-RT-SEC" from a SFN, this function finds the various
        plan sets potentially associated with that structure, it rounds the 'section'
        value up and down to be inclusive, effectively giving every plan segment
        for that 1 mile segment.

        :param district_df_path: set to default but overrideable to allow development on various devices without network
        access
        :return: Dumps .pdf files into a folder on the local machine at W:\CivilPy_Output\pulled_plans\
        """
        # //TODO - Replace this dataframe with a version that works with new plans, map other districts fs's
        d6_plans_df = pd.read_csv(district_df_path, delimiter='^', quotechar='~')
        county_code, route_num, section_num = self.cty_rte_sec.split('-')

        # The next four lines of code filter the d6_plans_df by county route section to get associated plans
        first_filtered_df = d6_plans_df[d6_plans_df['County_code'] == county_code]
        second_filtered_df = first_filtered_df[first_filtered_df['Route'] == route_num]
        third_filtered_df = second_filtered_df[second_filtered_df['Log_beg'] <= str(math.floor(float(section_num)))]
        fourth_filtered_df = third_filtered_df[third_filtered_df['Log_end'] >= math.ceil(float(section_num))]

        # Displays the results of the filter to the user via commandline, stores values in list for later
        list_of_plan_folder_paths = []

        for index, row in fourth_filtered_df.iterrows():
            list_of_plan_folder_paths.append(row['Path'])
            print(f"Plan set found:\n{row['Yr']}-{row['Type']}-{row['Archno']}\n{row['Commnt']}\n{row['Path']}\n\n")

        dict_of_all_paths = {}

        for folder in list_of_plan_folder_paths:
            dict_of_all_paths[folder] = self.get_tiff_files(folder)

        # Loop through each folder that was found, uses a natural sorting algo imported at top of file
        for folder, list_of_files in dict_of_all_paths.items():
            sorted_file_list = natsorted(list_of_files)

            tiff_objects_list = []

            # Create a folder to put the pdf plans into if it doesn't exist
            if os.path.exists(f"W:\\CivilPy_Output\\pulled_plans\\{self.SFN}"):
                pass
            else:
                os.mkdir(f"W:\\CivilPy_Output\\pulled_plans\\{self.SFN}")

            file_set_name = Path(sorted_file_list[0]).parent.name

            # Turns a list of file paths into a list of tiff objects loaded into memory
            for file in sorted_file_list:
                tiff_objects_list.append(tifftools.read_tiff(file))

            # Converts single page tiffs into multi-page tiffs
            for tiff_object in tiff_objects_list[1:]:
                tiff_objects_list[0]['ifds'].extend(tiff_object['ifds'])

            # Check if file exists, move on if so
            if os.path.exists(f"W:\\CivilPy_Output\\pulled_plans\\{self.SFN}\\{file_set_name}.tiff"):
                pass
            else:
                print(f"\nWriting tiff file to W:\\CivilPy_Output\\pulled_plans\\{self.SFN}\\{file_set_name}.tiff...\n")
                try:
                    tifftools.write_tiff(tiff_objects_list[0], f"W:\\CivilPy_Output\\pulled_plans\\{self.SFN}\\{file_set_name}.tiff")
                except(AttributeError):
                    print(f"There is a problem with the tiff file at \nW:\\CivilPy_Output\\"
                          f"pulled_plans\\{self.SFN}\\{file_set_name}.tiff\nYou might want to check there "
                          f"to resolve the issue\n\n")

            # Convert multipage tiff file to pdf
            try:
                self.tiff_to_pdf(f"W:\\CivilPy_Output\\pulled_plans\\{self.SFN}\\{file_set_name}.tiff")
            except:
                print(f"There was an error during conversion of the file: W:\\CivilPy_Output\\pulled_plans\\{self.SFN}"
                      f"\\{file_set_name}.tiff, it's possibly corrupted")


        return f"Files written to W:\\CivilPy_Output\\pulled_plans\\"

    def get_tiff_files(self, path):
        """
        This is a helper function to the self.get_d6_plansets() function, giving it a path to a folder returns a
        list of all files in that folder

        :return: list of tiff file paths
        """
        # Build a list of tiff files in the folder:
        root_path = Path(path)

        # List all the files in that directory location
        all_tiff_files = os.listdir(root_path)

        # Filter by tiff files
        tif_files = [f for f in all_tiff_files if f.lower().endswith('.tif')]

        # Display all the files for that plan set
        all_tiff_files = []

        print(f"folder: {path}")
        for file in tif_files:
            all_tiff_files.append(f"{root_path}\\{file}")
            print(f"{root_path}\\{file}", sep="\n")

        print('\n')

        return all_tiff_files


    def tiff_to_pdf(self, tiff_path: str) -> str:
        """
        Helper function to be used by the bridge object to convert tiff files to pdf
        :param tiff_path:
        :return:
        """
        pdf_path = tiff_path.replace('.tiff', '.pdf')
        if not os.path.exists(tiff_path): raise Exception(f'{tiff_path} does not find.')
        image = Image.open(tiff_path)

        images = []
        for i, page in enumerate(ImageSequence.Iterator(image)):
            page = page.convert("RGB")
            images.append(page)
        if len(images) == 1:
            images[0].save(pdf_path)
        else:
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
        return pdf_path