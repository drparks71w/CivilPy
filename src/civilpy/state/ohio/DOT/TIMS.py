# Use this section to extract data from TIMs and Assetwise to QA the data
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