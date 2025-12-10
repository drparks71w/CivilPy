import re
import json
from types import SimpleNamespace

import requests
from pathlib import Path
from datetime import datetime
from requests.auth import HTTPBasicAuth
from typing import List, Dict, Union, Optional
from IPython.display import display, Image as IPImage

from .aw_fields import aw_fields

base_url = "https://ohiodot-it-api.bentley.com"


def get_assetwise_secrets():
    """Loads API secrets from a JSON file."""
    with open(Path.home() / "secrets.json", 'r') as file:
        secrets = json.load(file)
    return secrets['BENTLEY_ASSETWISE_KEY_NAME'], secrets['BENTLEY_ASSETWISE_API']


username, password = get_assetwise_secrets()


# For when you only want to look at a single field and know it's id
def get_field_definition_by_id(base_api_url: str, username: str, password: str, fe_id: int,
                               api_type: str = "api") -> dict:
    """
    Retrieves a single field definition (Field object) from the AssetWise API by its fe_id
    using Basic Auth.

    This function uses the GET /api/Field/{fe_id} endpoint.

    Args:
        base_api_url (str): The base URL of the AssetWise API (e.g., "https://ohiodot-it-api.bentley.com").
        username (str): The key name for Basic Authentication.
        password (str): The API key for Basic Authentication.
        fe_id (int): The ID of the field to retrieve.
        api_type (str, optional): The API type, "api" or "mobile". Defaults to "api".

    Returns:
        dict: A dictionary representing the field object, containing its properties
              (e.g., 'fe_name', 'fe_id', 'fe_description').
              Returns an error message string if the request fails or data cannot be parsed.
    """
    # Use the specific endpoint for getting a field by its ID
    endpoint_path = f"/{api_type}/Field/{fe_id}"  # [3]
    url = f"{base_api_url}{endpoint_path}"

    auth = HTTPBasicAuth(username, password)  #
    headers = {
        "Accept": "application/json"
    }

    try:
        # Use GET method as per documentation for /{apiType}/Field/{fe_id} [3]
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()  # Raises an HTTPError for 4xx/5xx responses

        data = response.json()

        if data.get("success"):
            # For a single item return, the 'data' key directly contains the object [6]
            return data.get("data", {})
        else:
            return f"API returned an error: {data.get('errorMessage', 'Unknown error')}"

    except requests.exceptions.RequestException as req_err:
        status_code = response.status_code if response is not None else "N/A"
        response_text = response.text if response is not None else "N/A"
        return f"An error occurred: {req_err} (Status Code: {status_code}, Response: {response_text})"
    except ValueError:
        return "Failed to decode JSON response."


def get_bridge_by_sfn(
        sfn: str,
        include_coordinates: bool = True,
        include_parent: bool = False
) -> dict:
    """
    Retrieves a specific bridge asset by its SFN (Structure File Number) using the AssetWise API.

    Args:
        sfn (str): The SFN/asset code of the bridge to retrieve (e.g., '0702870').
        include_coordinates (bool): Whether to include asset coordinates in the response. Defaults to True.
        include_parent (bool): Whether to include the parent as_id in the response. Defaults to False.

    Returns:
        dict: A dictionary representing the bridge asset data.

    Raises:
        requests.exceptions.HTTPError: If the API request encounters an HTTP error.
    """
    base_url = "https://ohiodot-it-api.bentley.com"
    api_url = f"{base_url}/api/Asset/GetAssetByAsCode/{sfn}"

    query_params = {
        "IncludeCoordinates": include_coordinates,
        "IncludeParent": include_parent
    }

    headers = {
        "Accept": "application/json"
    }

    response = requests.get(
        api_url,
        params=query_params,
        headers=headers,
        auth=HTTPBasicAuth(username, password)
    )

    response.raise_for_status()
    return response.json()['data']


def get_asset_report_files_metadata(
        asset_id: int,
        api_type: str = "api",
        include_asset_file: bool = True
) -> List[Dict[str, Union[int, str, bool, Dict]]]:
    """
    Retrieves metadata for files associated with a specific asset that are
    also mapped to reports.
    """
    username, password = get_assetwise_secrets()
    api_url = f"{base_url}/{api_type}/AssetFilesReportMap/GetAssetFilesForAsset/{asset_id}"
    query_params = {"IncludeAssetFile": include_asset_file}
    headers = {"Accept": "application/json"}

    print(f"Requesting URL: {api_url} with query params: {query_params}")

    response = requests.get(
        api_url,
        params=query_params,
        headers=headers,
        auth=HTTPBasicAuth(username, password)
    )
    response.raise_for_status()

    print(f"Successfully retrieved file metadata for asset {asset_id}.")
    return response.json().get('data', [])


def download_asset_file_by_id(
    file_id: int,
    api_type: str = "api",
    get_as_thumbnail: bool = False
) -> bytes:
    """
    Downloads the binary content of a specific asset file.
    """
    username, password = get_assetwise_secrets()
    api_url = f"{base_url}/{api_type}/AssetFile/Download/{file_id}"
    query_params = {"get_as_thumbnail": get_as_thumbnail}
    headers = {"Accept": "application/octet-stream"}

    print(f"Requesting download for file ID: {file_id} with thumbnail option: {get_as_thumbnail}")

    response = requests.get(
        api_url,
        params=query_params,
        headers=headers,
        auth=HTTPBasicAuth(username, password)
    )
    response.raise_for_status()

    print(f"Successfully downloaded file ID: {file_id}.")
    return response.content


def get_asset_cover_image(asset_id: int, api_type: str = "api") -> Union[bytes, None]:
    """
    Retrieves the designated cover image for a specific asset by its ID.

    This function directly calls the GET /{apiType}/AssetFile/GetAssetCoverImage/{as_id} endpoint,
    which is the most efficient way to get the cover photo.

    Args:
        asset_id (int): The unique ID of the asset.
        api_type (str): The API type, typically 'api'. Defaults to 'api'.

    Returns:
        bytes: The binary content of the image file, or None if no cover image is found (returns 404).
    """
    username, password = get_assetwise_secrets()
    api_url = f"{base_url}/{api_type}/AssetFile/GetAssetCoverImage/{asset_id}"
    headers = {"Accept": "application/octet-stream"}

    print(f"Requesting cover image for asset ID: {asset_id} at URL: {api_url}")

    response = requests.get(
        api_url,
        headers=headers,
        auth=HTTPBasicAuth(username, password)
    )

    # A 404 status code from this endpoint specifically means no cover image was found.
    if response.status_code == 404:
        print("API returned 404: No cover image is designated for this asset.")
        return None

    # For other errors, raise an exception.
    response.raise_for_status()

    print(f"Successfully retrieved cover image for asset {asset_id}.")
    return response.content


class AssetWiseBridge:
    def __init__(self, sfn: str):
        self.sfn = sfn

        # Fetch Core Asset Identity
        raw_data = get_bridge_by_sfn(sfn, include_coordinates=True)
        if not raw_data:
            raise ValueError(f"No AssetWise asset found for SFN '{sfn}'")

        # Dynamically assign core attributes, converting dicts to SimpleNamespace where possible
        for key, value in raw_data.items():
            if isinstance(value, dict):
                try:
                    value = SimpleNamespace(**value)
                except TypeError:
                    pass
            setattr(self, key, value)

        # Initialize placeholders
        self._elements = None
        self._inspections = None
        self._snbi_data = None
        self._decoded_attributes = None

    @property
    def attributes(self) -> Dict[str, Union[str, int, float]]:
        """Lazy-loads and maps 'fe_id' to human-readable names."""
        if self._decoded_attributes is None:
            self._decoded_attributes = self._fetch_and_decode_values()
        return self._decoded_attributes

    @property
    def elements(self) -> List[Dict]:
        if self._elements is None:
            self._elements = get_elements_for_asset(base_url, username, password, self.as_id)
        return self._elements

    @property
    def inspections(self) -> List[Dict]:
        if self._inspections is None:
            self._inspections = get_all_approved_inspections(self.as_id)
        return self._inspections

    @property
    def snbi_data(self) -> Dict[str, Optional[str]]:
        """Returns a flattened dictionary keyed by SNBI label."""
        if self._snbi_data is None:
            raw = get_all_odot_snbi_data(self.as_id)
            # Flatten the nested list-of-dicts structure into a single K:V dict
            self._snbi_data = {
                entry['label']: entry.get('value')
                for entries in format_assetwise_output(raw).values()
                for entry in entries if entry.get('label')
            }

            # Inject defaults if missing from report
            defaults = {
                'B.ID.01: Bridge Number': self.sfn,
                'B.ID.02: Bridge Name': getattr(self, 'as_name', None),
                'NBI 009: Location': getattr(self, 'location', None)
            }
            for k, v in defaults.items():
                if k not in self._snbi_data and v: self._snbi_data[k] = v

        return self._snbi_data

    def _fetch_and_decode_values(self) -> Dict[str, Union[str, int, float]]:
        """Internal helper to fetch and map CurrentValues."""
        api_url = f"{base_url}/api/CurrentValue/GetCurrentValuesByAssetId/{self.as_id}"
        try:
            response = requests.get(api_url, auth=HTTPBasicAuth(username, password))
            response.raise_for_status()
            raw_rows = response.json().get('data', [])
        except Exception as e:
            print(f"Error fetching attributes: {e}")
            return {}

        decoded_data = {}
        for row in raw_rows:
            fid = row.get('fe_id')
            if not fid: continue

            val = row.get('cv_plain_text') or row.get('cv_value')
            if not val: continue

            # Map ID to Name
            field_name = aw_fields.get(str(fid), f"Field_{fid}")
            decoded_data[field_name] = val

        return decoded_data

    def find(self, pattern: str) -> Dict[str, Union[str, int, float]]:
        """Search keys in SNBI Data and Attributes using regex."""
        combined = {**self.snbi_data, **self.attributes}
        return {k: v for k, v in combined.items() if re.search(pattern, str(k), re.IGNORECASE)}

    def get_cover_photo(self, display_photo: bool = True):
        try:
            img = get_asset_cover_image(self.as_id)
            if img and display_photo and IPImage: display(IPImage(data=img))
            return img
        except Exception:
            return None

    def __repr__(self) -> str:
        return f"<AssetWiseBridge SFN: '{self.sfn}' ID: {getattr(self, 'as_id', '?')}>"


def get_elements_for_asset(base_api_url: str, username: str, password: str, as_id: int, api_type: str = "api") -> List[
    Dict]:
    """
    Retrieves elements and their condition states for a specific asset.
    Uses the GET /{apiType}/StructureElement/GetElements/{objectType}/{objectId}/{asId}/{segmentId}/{elementId} endpoint.
    objectType for Asset is 0. [4, 6, 25-51]
    segmentId and elementId are set to 0 to indicate retrieval of all segments and elements under the given asset,
    based on common API conventions for integer path parameters.
    """
    object_type_asset = 0  # As per ObjectType enum, 0 = Asset [128, etc.]

    # Construct the endpoint path to get all elements for a specific asset.
    # We use objectType, objectId (as_id), asId, segmentId, and elementId.
    # The segmentId parameter is noted as 'allowEmptyValue' in the documentation [52],
    # and 0 is a common convention for "all" or "not specified" for integer IDs in API paths.
    # We apply the same convention for elementId, which is also a required integer path parameters
    endpoint_path = f"/{api_type}/StructureElement/GetElements/{object_type_asset}/{as_id}/{as_id}/0/0"
    url = f"{base_api_url}{endpoint_path}"

    auth = HTTPBasicAuth(username, password)  # [13-15]
    headers = {
        "Accept": "application/json"  # [13-15, 53]
    }

    response = None  # Define response here so it's available in except block
    try:
        response = requests.get(url, headers=headers, auth=auth)  # Use GET method [4-6]
        response.raise_for_status()  # Raise an exception for HTTP errors [13-15, 20]

        data = response.json()

        if data.get("success"):  # Check if the API response was successful [21]
            # The 'data' field contains the list of Elements objects [5, 6, 54]
            # Each 'Elements' object includes an 'elementState' with condition details [1-3]
            return data.get("data", [])
        else:
            print(
                f"API returned an error while fetching elements for asset ID {as_id}: {data.get('errorMessage', 'Unknown error')}")
            return []

    except requests.exceptions.RequestException as req_err:
        status_code = response.status_code if response is not None else "N/A"
        response_text = response.text if response is not None else "N/A"
        print(
            f"An HTTP request error occurred while fetching elements for asset ID {as_id}: {req_err} (Status Code: {status_code}, Response: {response_text})")
        return []
    except ValueError:
        print(f"Failed to decode JSON response for elements for asset ID {as_id}.")
        return []


def get_inspection_reports_for_asset(
        asset_id: int,
        reports_to_return: int = 99,  # Defaults to 5 of the most recent reports
        api_type: str = "api"
) -> List[Dict[str, Union[int, str, bool, Dict]]]:
    """
    Retrieves recent inspection reports for a specific asset, regardless of report status.

    Args:
        asset_id (int): The unique ID of the asset.
        reports_to_return (int): The number of most recent reports to return. Defaults to 5.
        api_type (str): The API type, typically 'api'. Defaults to 'api' [20].

    Returns:
        List[Dict]: A list of dictionaries, each representing an InspectionReportHelper object.
                    Returns an empty list if no data is found or an error occurs.
    Raises:
        requests.exceptions.HTTPError: If the API request encounters an HTTP error.
    """
    username, password = get_assetwise_secrets()
    api_url = f"{base_url}/{api_type}/InspectionReport/GetMostRecentReportsForAsset/{asset_id}"
    query_params = {"reportsToReturn": reports_to_return}
    headers = {"Accept": "application/json"}

    response = requests.get(
        api_url,
        params=query_params,
        headers=headers,
        auth=HTTPBasicAuth(username, password)
    )
    response.raise_for_status()  # Raise an exception for HTTP errors

    # The 'data' field contains the list of InspectionReportHelper objects
    return response.json().get('data', [])


def get_full_inspection_report(
        ast_id: int,
        api_type: str = "api"
) -> Dict[str, Union[int, str, bool, List, Dict]]:
    """
    Retrieves the full details of a specific inspection report by its Asset Task ID (ast_id).
    This includes all fields, such as recorded condition states within the 'values' array,
    and various inspection dates.

    Args:
        ast_id (int): The unique Asset Task ID (e.g., 332776) of the inspection report.
                      This ID is provided by the InspectionReportHelper.
        api_type (str): The API type, typically 'api'. Defaults to 'api'.

    Returns:
        Dict: A dictionary representing the complete InspectionReport object.
              This object contains fields like 'ast_inspection_date', 'ast_begin_date',
              'ast_end_date', and a 'values' array, where detailed condition states
              and their specific recording dates are expected.

    Raises:
        requests.exceptions.HTTPError: If the API request encounters an HTTP error (e.g., 4xx or 5xx response).
    """
    username, password = get_assetwise_secrets()  # Authenticates the request
    base_url = "https://ohiodot-it-api.bentley.com"  # Base URL for the AssetWise API

    # Constructs the API endpoint for retrieving a single InspectionReport by ast_id
    api_url = f"{base_url}/{api_type}/Value/GetValuesForReport/{ast_id}"

    headers = {
        "Accept": "application/json"  # Specifies that the client expects a JSON response
    }

    print(f"Requesting full inspection report for AST ID: {ast_id} at URL: {api_url}")

    response = requests.get(
        api_url,
        headers=headers,
        auth=HTTPBasicAuth(username, password)
    )

    # Raises an HTTPError for bad responses (4xx or 5xx)
    response.raise_for_status()

    print(f"Successfully retrieved full inspection report for AST ID: {ast_id}.")

    # Extracts the 'data' field from the JSON response, which contains the InspectionReport object
    return response.json().get('data', {})


def get_all_inspection_data(inspection_reports, field_ids):
    i = 0
    all_inspection_values = {}

    for inspection in inspection_reports:
        dt = datetime.fromisoformat(inspection['ast_date'])
        inspection_name = f"{dt.strftime('%m/%d/%Y')} - {inspection['reportType']['rt_name']} - {inspection['inspectionTypes'][0]['it_name']}"
        all_inspection_values[inspection_name] = {}
        print(f"{inspection_name}\n")

        inspection_values = get_full_inspection_report(inspection['ast_id'])

        for field in inspection_values:  # Very Slow, probably because of get_field_definition_by_id, should get built out ahead of time instead
            if field['fe_id'] in field_ids:
                field_values = {}
                field_values['fe_name'] = field_ids[field['fe_id']]
            else:
                field_values = get_field_definition_by_id(base_url, username, password, field['fe_id'])
                field_ids[field['fe_id']] = field_values
                print("**** NEW VALUE FOUND, THE DATABASE SHOULD BE UPDATED ****")

            key = field['fe_id']
            all_inspection_values[inspection_name][key] = (field_values['fe_name'], field['va_value'])

            i += 1

    return all_inspection_values


def get_all_odot_snbi_data(asset_id: int):
    # //TODO - This code is AI garbage and needs to be fixed and optimized
    username, password = get_assetwise_secrets()
    base_url = "https://ohiodot-it-api.bentley.com"

    response_data = []
    base_template_id = 1000000
    offset = 0
    consecutive_failures = 0
    MAX_RETRIES = 2  # Allow for 2 empty slots before assuming we are done

    while consecutive_failures < MAX_RETRIES:
        # Dynamically calculate the current Template ID
        # Note: We use integer math, not string concatenation, to safely handle 1000009 -> 1000010
        current_template_id = base_template_id + offset

        api_url = f"{base_url}/api/FormElement/GetRfgTemplateElements/{asset_id}/0/{current_template_id}"
        headers = {"Accept": "application/json"}

        try:
            response = requests.get(
                api_url,
                headers=headers,
                auth=HTTPBasicAuth(username, password)
            )

            # Check if the request was successful AND contained actual data
            if response.status_code == 200:
                json_data = response.json()

                # Some APIs return 200 OK but with "success": false or empty data
                if json_data.get('success') and json_data.get('data'):
                    response_data.append(json_data['data'])
                    consecutive_failures = 0  # Reset failure counter on success
                else:
                    consecutive_failures += 1
            elif response.status_code == 404:
                consecutive_failures += 1
            else:
                consecutive_failures += 1

        except Exception as e:
            print(f"[ERR]   Failed to fetch {current_template_id}: {e}")
            consecutive_failures += 1

        offset += 1

    return response_data


# Global cache to prevent re-fetching the same field definitions repeatedly
field_definition_cache = {}

# Global cache to prevent re-fetching the same field definitions repeatedly
field_definition_cache = {}


def format_assetwise_output(response):
    """
    Organizes SNBI data and dynamically resolves missing Field Names (healing Unnamed Fields).
    """
    element_dict = {}
    username, password = get_assetwise_secrets()

    # Step 1: Group elements by el_id
    for page in response:
        for instance in page:
            for element in instance['elements']:
                el_id = element['el_id']

                if element.get('field') is None:
                    fe_id = element.get('fe_id')

                    if fe_id:
                        # Check our cache first so we don't spam the API
                        if fe_id in field_definition_cache:
                            element['field'] = field_definition_cache[fe_id]
                        else:
                            # We have an ID but no Name. Fetch it manually.
                            try:
                                field_def = get_field_definition_by_id(base_url, username, password, fe_id)
                                if isinstance(field_def, dict) and 'fe_name' in field_def:
                                    field_definition_cache[fe_id] = field_def
                                    element['field'] = field_def
                            except Exception:
                                pass  # If lookup fails, it stays Unnamed

                field = element.get('field')
                value = (element.get('value'), field)
                element_dict.setdefault(el_id, []).append(value)

    # Step 2: Organize values into a clean structure
    organized_dict = {}

    for el_id, entries in element_dict.items():
        organized_dict[el_id] = []

        for value, field in entries:
            # Define a safe label, checking if field exists
            label = field['fe_name'] if field else f"Unnamed Field (el_id: {el_id})"

            # If the value is a list (but not a string), unpack it
            if isinstance(value, list) and not isinstance(value, str):
                for item in value:
                    organized_dict[el_id].append({
                        'label': label,
                        'value': item.get('value') if isinstance(item, dict) else item
                    })
            else:
                organized_dict[el_id].append({
                    'label': label,
                    'value': value
                })

    return organized_dict


def get_all_approved_inspections(as_id: int, api_type: str = "api") -> List[Dict]:
    """
    Retrieves ALL approved inspection reports for a specific asset.
    Uses the GET /{apiType}/InspectionReport/GetAllApproved/{as_id} endpoint.

    Args:
        as_id (int): The unique ID of the asset.
        api_type (str): The API type, typically 'api'. Defaults to 'api'.

    Returns:
        List[Dict]: A list of dictionaries, each representing an InspectionReportHelper object.
                    Returns an empty list if no data is found or an error occurs.
    """
    # 1. Get auth secrets, consistent with other functions
    username, password = get_assetwise_secrets()

    # 2. Construct URL from global base_url
    api_url = f"{base_url}/{api_type}/InspectionReport/GetAllApproved/{as_id}"

    # 3. Set headers and auth
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(username, password)

    # 4. Add logging
    print(f"Requesting all approved inspection reports for asset ID: {as_id} at URL: {api_url}")

    # 5. Use a robust try/except block for the request
    response = None  # Define response here so it's available in except block
    try:
        response = requests.get(api_url, headers=headers, auth=auth)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)

        data = response.json()

        if data.get("success"):
            return data.get("data", [])
        else:
            # Handle API-level error (success=false)
            print(f"API returned an error for asset {as_id}: {data.get('errorMessage', 'Unknown error')}")
            return []

    except requests.exceptions.RequestException as req_err:
        status_code = response.status_code if response is not None else "N/A"
        response_text = response.text if response is not None else "N/CSS"
        print(
            f"An HTTP request error occurred for asset {as_id}: {req_err} (Status Code: {status_code}, Response: {response_text})")
        return []
    except ValueError:  # Handle JSON decode error
        print(f"Failed to decode JSON response for asset ID {as_id}.")
        return []


def get_all_bridges_paged(
        starting_row: int = 0,
        items_per_page: int = 100,
        api_type: str = "api",
        include_coordinates: bool = False,
        include_parent: bool = False
):
    """
    Retrieves a paged list of assets from the AssetWise API using a POST request.

    Args:
        starting_row (int): The starting row for the page (0-indexed). Defaults to 0.
        items_per_page (int): The number of items to return per page. Defaults to 100.
        api_type (str): The API type, either "api" or "mobile". Defaults to "api".
        include_coordinates (bool): Whether to include asset coordinates in the response. Defaults to False.
        include_parent (bool): Whether to include the parent as_id in the response. Defaults to False.

    Returns:
        dict: A dictionary containing the API response data for assets, including pagination info.

    Raises:
        requests.exceptions.HTTPError: If the API request returns a non-200 status.
    """
    username, password = get_assetwise_secrets()

    api_url = f"https://ohiodot-it-api.bentley.com/{api_type}/Asset/GetAssets"

    # Query parameters (IncludeCoordinates and IncludeParent are query params for both GET and POST)
    query_params = {
        "IncludeCoordinates": include_coordinates,
        "IncludeParent": include_parent
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"  # Essential for sending JSON in the request body
    }

    # Request body for pagination, matching the RequestPaging schema
    request_body = {
        "starting": starting_row,
        "count": items_per_page
    }

    print(f"Requesting URL: {api_url} with query params: {query_params}, body: {request_body}")

    response = requests.post(
        api_url,
        params=query_params,
        headers=headers,
        auth=HTTPBasicAuth(username, password),
        json=request_body  # Send pagination data as JSON in the body
    )

    response.raise_for_status()  # Raise an exception for HTTP errors

    print("Successfully retrieved paged assets.")
    return response.json()
