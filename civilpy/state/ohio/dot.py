import os
import re
import folium
import pandas as pd


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


def check_file_names(file_list, regex_pattern):
    pass


default_bridge_labels = [
    'Bridge Status Code', 'Bridge Status Description calc',
    'Structure File Number', 'District Number', 'Deck Area',
    'Overall Structure Length', 'Over 20 Ft (Fedl Brdg) (Y/N/Null) calc',
    'Sufficiency Rating', 'Sufficiency Rating Converted calc', 'SD/FO',
    'SD/FO calc', 'Functional Class Code', 'Functional Class Old Name calc',
    'Functional Class Old Group calc', 'Functional Class FHWA Code calc',
    'Functional Class New Code calc', 'Funct Class New Name calc',
    'Maintenance Responsibility Code',
    'Maintenance Responsibility Description calc',
    'Maintenance Responsibility plus Null calc', 'Type Service On Bridge Code',
    'Type of Service On Bridge Description calc',
    'Type Service Under Bridge Code', 'County Code', 'Highway System Code',
    'Invent Hwy Sys Name calc', 'Invent Hwy Sys Description calc', 'Route',
    'Inventory Route', 'Route On Bridge Code', 'Route On Bridge Description calc',
    'Route Under Bridge Code', 'Route Under Bridge Description calc',
    'Facility Carried By Structure', 'Feature Intersected', 'Latitude',
    'Longitude', 'NHS Code', 'NHS (Y/N) calc', 'NHS Description calc',
    'Year Rebuilt Calc', 'Load Rating Year', 'Main Span Type Code',
    'Main Structure Type', 'Load Inventory Rating', 'Inventory County',
    'FIPS Number', 'BTRS Link Number', 'BTRS Linked (Y/N) calc', 'Analyzed By',
    'Approach Alignment Code', 'Approach Guardrail Code',
    'Approach Pavement Grade Code', 'Approach Pavement Material Code',
    'Approach Roadway Width', 'Approach Slab ', 'Approach Slab Length',
    'Approach Span Description Code', 'Approach Span Material Code',
    'Approach Span Type Code', 'Approach Spans', 'Approach Structure Type',
    'BARS Code', 'Bearing Device1 Code', 'Bearing Device2 Code',
    'Bridge Roadway Width Cb Cb', 'Bypass Length', 'Calculated Deck Geometry',
    'Calculated Structural Evaluation', 'Calculated Underclearance',
    'Channel Protection Type Code', 'Min Horizontal Clearance On Bridge Cardinal',
    'Min Horizontal Clearance On Bridge Non-Cardinal',
    'Min Horizontal Clearance Under Cardinal',
    'Min Horizontal Clearance Under Non-Cardinal',
    'Min Lateral Clearance Cardinal Left',
    'Min Lateral Clearance Cardinal Right',
    'Min Lateral Clearance Non-Cardinal Left',
    'Min Lateral Clearance Non-Cardinal Right',
    'Min Lateral Clearance Under Cardinal Left',
    'Min Lateral Clearance Under Cardinal Right',
    'Min Lateral Clearance Under Non-Cardinal Left',
    'Min Lateral Clearance Under Non-Cardinal Right',
    'Min Vertical Clearance Bridge Cardinal',
    'Min Vertical Clearance Bridge Non-Cardinal',
    'Min Vertical Clearance Under Bridge Cardinal',
    'Min Vertical Clearance Under Bridge Non-Cardinal',
    'Clearance Practical Max Vertical On Bridge',
    'Clearance Practical Max Vertical Under Bridge', 'Combined',
    'Composite Structure Code', 'Culvert Fill Depth',
    'Culvert Headwalls/Endwalls Type Code', 'Culvert Length',
    'Culvert Sufficiency Rating Default', 'Culvert Type Code',
    'Curb/Sidewalk Material Type Left',
    'Curb/Sidewalk Material Type Right', 'Curb/Sidewalk Type Left',
    'Curb/Sidewalk Type Right', 'Deck Concrete Type Code',
    'Deck Drainage Type Code', 'Deck Protection External Code',
    'Deck Protection Internal Code', 'Deck Type Code',
    'Deck Width Out/Out', 'Design Load Code', 'Directional Suffix Code',
    'Expansion Joint Retrofit1 Code', 'Expansion Joint Retrofit2 Code',
    'Expansion Joint Retrofit3 Code', 'Expansion Joint Type1 Code',
    'Expansion Joint Type2 Code', 'Expansion Joint Type3 Code',
    'Expansion Joint With Trough Retrofit1',
    'Expansion Joint With Trough Retrofit2',
    'Expansion Joint With Trough Retrofit3',
    'Future ADT', 'Future ADT Year', 'Haunched Girder',
    'Haunched Girder Depth', 'Highway Designation Code',
    'Hinge Code', 'Horizontal Curve Radius', 'Lanes On Number',
    'Lanes Under Number', 'Macro Corridor', 'Main Member Depth',
    'Main Member Type Code', 'Main Span Description Code',
    'Main Span Material Code', 'Main Spans Number', 'Major Rehab Date',
    'Maximum Span Length', 'Median Code', 'Median Type1 Code',
    'Median Type2 Code', 'Median Type3 Code', 'Method Of Analysis Code',
    'Moment Plates Code', 'MPO Code', 'Min Vertical Clearance Lift Bridge',
    'Navigable Stream', 'Navigable Stream Horizontal Clearance',
    'Navigable Stream Vertical Clearance', 'Ohio Percent Of Legal Load',
    'On/Under', 'Operating Rating HS', 'Parallel Structure Code',
    'Paint Condition Rating Date', 'Paint Supplier', 'Paint Surface Area',
    'Preferred Route', 'Railing Type Code',
    'Ramp Lateral Under Clearance Cardinal Left',
    'Ramp Lateral Under Clearance Cardinal Right',
    'Ramp Lateral Under Clearance Non-Cardinal Left',
    'Ramp Lateral Under Clearance Non-Cardinal Right',
    'Ramp Roadway Width Cardinal', 'Ramp Roadway Width Non-Cardinal',
    'Ramp Vertical Under Clearance Cardinal',
    'Ramp Vertical Under Clearance Non-Cardinal', 'Record Add Date',
    'Record Update Date', 'Remarks', 'Retire Reason Code',
    'SFN Control Authority', 'Sidewalk Width Left',
    'Sidewalk Width Right', 'Skew', 'Slope Protection Type Code',
    'Software Of Rating Analysis', 'Inventory Special Designation',
    'Straight Line Kilometers', 'Straight Line Mileage',
    'Structure Location', 'Toll Road', 'Total Spans',
    'Traffic Direction Code', 'Water Direction Code',
    'Waterway Adequacy Code', 'Wearing Surface Date',
    'Wearing Surface Thickness', 'Wearing Surface Type Code', 'Total',
    'SubClass', 'Subclass1', 'SubClass2', 'Cty', '9', '8', '7', '6',
    'A', '5', '4', '3', '2', '1', '0', 'N', 'Maintained',
    'Inventoried', 'Date Built', 'Contractor Name', 'Drainage Area',
    'Framing Type', 'Historical Bridge Type Code',
    'Historical Builder Code', 'Historical Significance Code',
    'Longitudinal Member Type', 'Microfilm Number',
    'Original Project Number', 'Structural Steel Protection Code',
    'Railing Structural Steel Type', 'Standard Drawing Number',
    'Stream Velocity', 'Structural Steel Fabricator',
    'Structural Steel Paint Type Code', 'Structural Steel Pay Weight',
    'Predominant Structural Steel Type', 'Boat Inspection',
    'Critical Structure', 'Dive Inspection', 'Dive Inspection Date',
    'Dive Inspection Frequency', 'Fracture Critical Inspection',
    'Fracture Critical Inspection Date',
    'Fracture Critical Inspection Frequency', 'Inspection Frequency',
    'Inspection Responsibility Code', 'Probe Inspection',
    'Probe Inspection Frequency', 'Scour Critical Code',
    'Snooper Inspection', 'Special Inspection', 'Special Inspection Date',
    'Special Inspection Frequency', 'Major Bridge Indicator (Y/N)',
    'NBIS Length (Y/N)', 'Aperture Card Original',
    'Aperture Fabrication', 'Aperture Repairs', 'Bridge Dedicated Name',
    'Cable Stayed', 'Catwalks', 'Designated National Network', 'Fencing',
    'Fencing Height', 'Flared', 'GASB 34', 'Glare Screen', 'Lighting',
    'Noise Barrier', 'Other Features', 'Post Tensioned', 'Railroad Code',
    'Scenic Waterway', 'Seismic Susceptibility Code', 'Signs Attached On',
    'Signs Attached Under', 'Splash Guard', 'Strahnet Highway Designation',
    'Temporary Barrier', 'Temporary Debris Netting', 'Temporary Shored',
    'Temporary Structure', 'Temporary Subdecking', 'Utility - Electric',
    'Utility - Gas', 'Utility - Other', 'Utility - Sewer',
    'Utility - Telephone', 'Utility - TV Cable', 'Utility - Water',
    'Abutment Forward Material Code', 'Abutment Forward Type Code',
    'Abutment Rear Material Code', 'Abutment Rear Type Code',
    'Dynamic Load Test Abutment Forward', 'Dynamic Load Test Abutment Rear',
    'Dynamic Load Test Pier Predominate', 'Dynamic Load Test Pier Type1',
    'Dynamic Load Test Pier Type2', 'Foundation Abutment Forward Code',
    'Foundation Abutment Rear Code', 'Foundation Length Abutment',
    'Foundation Length Pier', 'Foundation Pier Predominate Code',
    'Foundation Pier Type1 Code', 'Foundation Pier Type2 Code',
    'Pier Predominant  ', 'Pier Predominate Material Code',
    'Pier Predominate Type Code', 'Pier Type1 Number',
    'Pier Type1 Material Code', 'Pier Type1 Type Code',
    'Pier Type2 Number', 'Pier Type2 Material Code',
    'Pier Type2 Type Code', 'Pile Log', 'Static Load Test Abutment Forward',
    'Static Load Test Abutment Rear', 'Static Load Test Pier Predominate',
    'Static Load Test Pier Type1', 'Static Load Test Pier Type2'
]


class BridgeObject:
    def __init__(self, SFN, query='SELECT * FROM table',
                 column_labels=default_bridge_labels,
                 data_path="G:\\ref\\New folder\\Bridges.tsv"):
        self.query = query
        print("WARN - Using test data from a static source, some results may be inaccurate (11/15/2021)")
        df = pd.read_csv(f'{data_path}',
                         sep='\t', low_memory=False)

        bridge_details = df.iloc[df.index[df['Structure File Number'] == SFN]].iloc[0].to_dict()

        self.raw_data = bridge_details

        dirty_long = str(self.raw_data['Longitude'])
        dirty_lat = str(self.raw_data['Latitude'])

        self.clean_lat = float(dirty_lat[:2]) + (float(dirty_lat[2:4]) / 60) + (
                    float(f'{dirty_lat[4:6]}.{dirty_lat[6:]}') / 3600)
        self.clean_long = -(float(dirty_long[:2]) + (
                    (float(dirty_long[2:4]) / 60) + (float(f'{dirty_long[4:6]}.{dirty_long[6:]}') / 3600)))

    def get_summary(self):
        substring_1 = f"{self.raw_data['County Code']} - "
        substring_2 = f"{self.raw_data['Facility Carried By Structure']} over "
        substring_3 = f"{self.raw_data['Feature Intersected']}"

        temp_string = substring_1 + substring_2 + substring_3
        print(f'Report for SFN: {self.raw_data["Structure File Number"]} ({temp_string})')

        print(f'\nLatitude: {self.clean_lat:.5f}, Longitude: {self.clean_long:.5f}')

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
        url = url + self.raw_data['County Code'] + '&route=' + self.raw_data['Route']