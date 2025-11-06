# Use this section to extract data from TIMs and Assetwise to QA the data
import json
import requests
import pandas as pd

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