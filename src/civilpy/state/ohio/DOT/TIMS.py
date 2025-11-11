# Use this section to extract data from TIMs and Assetwise to QA the data
import json
import requests
import pandas as pd
from datetime import datetime, timedelta


# NBI Code Dictionaries for Material and Design/Construction Type
NBI_MATERIAL_CODES = {
    '1': 'Concrete',
    '2': 'Concrete Continuous',
    '3': 'Steel',
    '4': 'Steel Continuous',
    '5': 'Prestressed Concrete',
    '6': 'Prestressed Concrete Continuous',
    '7': 'Wood or Timber',
    '8': 'Masonry',
    '9': 'Aluminum, Wrought Iron, or Cast Iron',
    '0': 'Other',
}

NBI_DESIGN_TYPE_CODES = {
    '01': 'Slab',
    '02': 'Stringer/Multi-beam or Girder',
    '03': 'Girder and Floorbeam System',
    '04': 'Tee Beam',
    '05': 'Box Beam or Girders - Multiple',
    '06': 'Box Beam or Girders - Single or Spread',
    '07': 'Frame',
    '08': 'Orthotropic',
    '09': 'Truss - Deck',
    '10': 'Truss - Thru',
    '11': 'Arch - Deck',
    '12': 'Arch - Thru',
    '13': 'Suspension',
    '14': 'Stayed Girder',
    '15': 'Movable - Lift',
    '16': 'Movable - Bascule',
    '17': 'Movable - Swing',
    '18': 'Tunnel',
    '19': 'Culvert',
    '20': 'Mixed types',
    '21': 'Segmental Box Girder',
    '22': 'Channel Beam',
    '00': 'Other',
}


def get_tims_data(data_source='Roadway'):
    types = {
        'Roadway': "https://gis.dot.state.oh.us/arcgis/rest/services/TIMS/Roadway_Information/MapServer/8",
        'Bridge': "https://gis.dot.state.oh.us/arcgis/rest/services/TIMS/Assets/MapServer/5"
    }

    metadata_url = types[data_source]
    query_url = metadata_url + "/query"

    data = requests.get(f"{metadata_url}?f=json").json()
    all_fields = [field['name'] for field in data.get('fields', [])]

    # Set the batch size (MaxRecordCount limit)
    # BATCH_SIZE = int(data['maxRecordCount'])
    BATCH_SIZE = 1000

    # Initialize an empty list to store all feature attributes
    all_attributes = []
    offset = 0

    while True:
        params = {
            'where': '1=1',
            'outFields': ','.join(all_fields),
            'resultOffset': offset,
            'resultRecordCount': BATCH_SIZE,
            'returnGeometry': False,
            'f': 'json'
        }

        try:
            response = requests.post(query_url, data=params)
            response.raise_for_status()
            data = response.json()

            # Check for features in the response
            features = data.get('features', [])

            if not features:
                print(f"No more features found. Fetched {offset} total records.")
                break

            # Extract attributes and add to the main list
            attributes_list = [feature['attributes'] for feature in features]
            all_attributes.extend(attributes_list)

            print(f"Fetched {len(attributes_list)} records. Total so far: {len(all_attributes)}")

            # Increment the offset for the next loop iteration
            offset += BATCH_SIZE

        except requests.exceptions.HTTPError as err:
            print(f"HTTP Error: {err}")
            break
        except Exception as err:
            print(f"An error occurred: {err}")
            break

    # Build the final DataFrame from all collected attributes
    if all_attributes:
        df = pd.DataFrame(all_attributes)
        print("DataFrame successfully created with shape:", df.shape)
    else:
        print("Failed to retrieve any data.")

    return df

class TIMSBridge:
    """
    Represents a single bridge from the TIMS database, fetched by its SFN.
    Attributes are dynamically created from the fetched data keys (converted to lowercase).

    Example:
        bridge = TIMSBridge('2102374')
        print(bridge.lanes)  # Access data as attributes
    """
    _API_URL = "https://tims.dot.state.oh.us/ags/rest/services/Assets/Bridge_Inventory/MapServer/0/query"

    def __init__(self, sfn: str):
        """
        Initializes the TIMSBridge object by fetching data for the given SFN.

        Args:
            sfn (str): The Structure File Number (SFN) of the bridge to fetch.

        Raises:
            ValueError: If no bridge is found for the specified SFN.
            RuntimeError: If there is a network or API error.
        """
        self.sfn = sfn  # Store the original SFN
        data = self._fetch_bridge_data()

        if not data:
            raise ValueError(f"No bridge found with SFN '{sfn}'")

        # Dynamically assign attributes from the fetched data, converting keys to lowercase
        # for Pythonic attribute access (e.g., bridge.deck_area instead of bridge['DECK_AREA'])
        for key, value in data.items():
            setattr(self, key.lower(), value)

    def _fetch_bridge_data(self) -> dict | None:
        """
        Internal method to query the TIMS API for the bridge data.
        """
        params = {
            "where": f"SFN = '{self.sfn}'",
            "outFields": "*",
            "f": "json",
            "returnGeometry": "true",
            "resultRecordCount": 1,
        }
        try:
            resp = requests.get(self._API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                # Raise a specific error that includes the API's message
                raise RuntimeError(f"TIMS/ArcGIS API error: {data['error']}")

            features = data.get("features", [])
            if not features:
                return None

            return features[0].get("attributes", {})
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error fetching bridge data for SFN '{self.sfn}': {e}") from e

    def __repr__(self) -> str:
        """
        Provides a nicely formatted, developer-friendly representation of the TIMSBridge object.
        """
        # Helper to safely get attributes that might not exist on all records
        def get(attr, default='N/A'):
            return getattr(self, attr, default)

        # Convert timestamp for 'yr_built' to just the year if it exists
        year_built_str = 'N/A'
        if hasattr(self, 'yr_built') and self.yr_built is not None:
            try:
                # The epoch for many systems is 1970-01-01.
                # Adding the timestamp (in seconds) as a timedelta to the epoch
                # correctly handles pre-1970 (negative) timestamps on all platforms.
                epoch = datetime(1970, 1, 1)
                dt = epoch + timedelta(seconds=self.yr_built / 1000)
                year_built_str = dt.strftime('%Y')
            except (ValueError, TypeError, OSError):
                # Fallback for unexpected formats
                year_built_str = str(self.yr_built)

        # Translate material and type codes to descriptions
        material_code = get('main_str_mtl_cd', 'N/A')
        material_desc = NBI_MATERIAL_CODES.get(str(material_code), 'Unknown')

        type_code = get('main_str_type_cd', 'N/A')
        type_desc = NBI_DESIGN_TYPE_CODES.get(str(type_code), 'Unknown')

        material_type_str = f"{material_desc} / {type_desc} ({material_code}/{type_code})"

        # Create a clickable Google Maps link for the coordinates
        lat = get('latitude_dd', 0)
        lon = get('longitude_dd', 0)
        map_url = f"https://www.google.com/maps?q={lat},{lon}"

        repr_str = (
            f"<TIMSBridge SFN: '{self.sfn}'>\n"
            f"  Route Carried: {get('str_loc_carried')}\n"
            f"  NLFID:         {get('nlfid')}\n"
            f"  Location:      {get('county_cd')} County, District {get('district')}\n"
            f"  Location Map:  {map_url}\n"
            f"\n"
            f"  -- Characteristics --\n"
            f"  Lanes On:      {get('lanes_on')}\n"
            f"  Year Built:    {year_built_str}\n"
            f"  Material/Type: {material_type_str} (Main Span)\n"
            f"\n"
            f"  -- Condition Ratings --\n"
            f"  Sufficiency:   {get('suff_rating')}\n"
            f"  Deck:          {get('deck_summary')}\n"
            f"  Superstructure:{get('sups_summary')}\n"
            f"  Substructure:  {get('subs_summary')}\n"
            f"\nFor a full list of available attributes, use help(TIMSBridge)."
        )
        return repr_str


def get_bridge_sfns_by_district(district=None,
                                url = "https://tims.dot.state.oh.us/ags/rest/services/Assets/Bridge_Inventory/MapServer/0/query"
                                ):
    """
    Queries the TIMS API for bridges in a specific district and returns a list of SFNs.

    Args:
        district (int, optional): The district number (1-12).
                                 If None, all bridges are queried. Defaults to None.

    Returns:
        list: A list of SFNs (as strings or numbers, whatever the API returns),
              or an empty list if no records are found or an error occurs.
    """

    # 1. Define query parameters based on district input
    out_fields = 'SFN'  # Only query the SFN field for efficiency
    return_geometry = False

    if district is not None and 1 <= district <= 12:
        # Format district as a two-digit string (e.g., 6 -> '06', 12 -> '12')
        district_str = str(district).zfill(2)
        where_clause = f"DISTRICT = '{district_str}'"
        print(f"Querying API for District {district_str}...")
    else:
        where_clause = "1=1"
        print("No district specified, gathering all bridges...")

    # 2. Define the API Parameters
    params = {
        'where': where_clause,
        'outFields': out_fields,
        'returnGeometry': str(return_geometry).lower(),
        'f': 'json'
    }

    # 3. Make the API Request
    print(f"URL: {url}")
    print(f"Filter: {where_clause}")

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()

        # 4. Process the Response
        if 'features' in data and data['features']:
            features = data['features']
            print(f"\nSuccess! Found {len(features)} features.")

            # Extract just the SFN from each feature's attributes
            # This is a list comprehension, which is very efficient.
            sfn_list = [
                feature['attributes']['SFN']
                for feature in features
                if 'attributes' in feature and 'SFN' in feature['attributes']
            ]
            return sfn_list

        elif 'error' in data:
            print(f"API returned an error: {data['error']['message']}")
        else:
            print("Query was successful, but no features were found matching the criteria.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the API request: {e}")
        print("Please check the URL and your network connection.")
    except json.JSONDecodeError:
        print("Error: Could not decode the response from the server. The service might be down.")
    except KeyError:
        # This would happen if a feature is missing 'attributes' or 'SFN'
        print("Error: Data was returned but was missing the 'SFN' field in 'attributes'.")

    # Return an empty list if any issues occurred
    return []
