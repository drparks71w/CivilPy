import requests
import math
import urllib3
import folium
import webbrowser
import os

# Suppress the insecure request warning that is generated when verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def find_nearest_crossing(longitude: float, latitude: float, search_radius_miles: int = 5):
    """
    Queries the FRA Grade Crossing Esri endpoint to find the nearest crossing
    to a given set of GPS coordinates.

    Args:
        longitude: The longitude of the search point.
        latitude: The latitude of the search point.
        search_radius_miles: The radius in miles to search for crossings.

    Returns:
        A tuple containing the list of all found features and the nearest feature.
        Returns ([], None) if no features are found or an error occurs.
    """
    query_url = "https://fragis.fra.dot.gov/arcgis/rest/services/FRA/FRAGradeXing/MapServer/0/query"

    # Added POSXING to outFields to determine the type of crossing (at-grade, over, under)
    params = {
        'geometry': f'{longitude},{latitude}',
        'geometryType': 'esriGeometryPoint',
        'inSR': 4326,
        'spatialRel': 'esriSpatialRelIntersects',
        'distance': search_radius_miles,
        'units': 'esriSRUnit_StatuteMile',
        'outFields': 'CROSSING,STREET,RAILROAD,CITYNAME,STATENAME,DAYTHRU,NGHTTHRU,ACC_LINK,POSXING',
        'returnGeometry': 'true',
        'f': 'json'
    }

    print(f"Searching for grade crossings within {search_radius_miles} miles of ({latitude}, {longitude})...")

    try:
        response = requests.get(query_url, params=params, timeout=30, verify=False)
        response.raise_for_status()
        data = response.json()
        features = data.get('features', [])

        if not features:
            print("No grade crossings found within the search radius.")
            return [], None

        print(f"\nFound {len(features)} total crossings within the search radius.")
        nearest_feature = None
        min_distance = float('inf')

        for feature in features:
            geom = feature.get('geometry')
            if not geom:
                continue
            crossing_lon, crossing_lat = geom['x'], geom['y']
            distance = math.hypot(latitude - crossing_lat, longitude - crossing_lon)
            if distance < min_distance:
                min_distance = distance
                nearest_feature = feature

        return features, nearest_feature

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while querying the Esri endpoint: {e}")
        return [], None
    except KeyError as e:
        print(f"Error parsing the response from the server. Unexpected data format: {e}")
        return [], None


def create_crossing_map(search_lat, search_lon, all_crossings, nearest_crossing, target_railroad):
    """
    Creates a Folium map with all found crossings and saves it to an HTML file.
    Markers are styled to highlight a target railroad and crossing type.

    Args:
        search_lat: The latitude of the original search point.
        search_lon: The longitude of the original search point.
        all_crossings: A list of all crossing features found.
        nearest_crossing: The single nearest crossing feature.
        target_railroad: The railroad code to highlight on the map (e.g., 'CSX').
    """
    m = folium.Map(location=[search_lat, search_lon], zoom_start=13)

    folium.Marker(
        [search_lat, search_lon],
        popup="Your Search Location",
        icon=folium.Icon(color="purple", icon="info-sign")
    ).add_to(m)

    for crossing in all_crossings:
        attrs = crossing.get('attributes', {})
        geom = crossing.get('geometry', {})
        if not geom:
            continue

        crossing_lat, crossing_lon = geom.get('y'), geom.get('x')
        current_railroad = attrs.get('RAILROAD')

        day_trains = attrs.get('DAYTHRU', 0) or 0
        night_trains = attrs.get('NGHTTHRU', 0) or 0
        total_trains = day_trains + night_trains

        acc_link = attrs.get('ACC_LINK')
        link_html = f'<a href="{acc_link}" target="_blank">View Report</a>' if acc_link else "No report available"

        posxing_type = attrs.get('POSXING')
        crossing_type_desc = "At-Grade"
        if posxing_type == '2':
            crossing_type_desc = "Railroad Under Road"
        elif posxing_type == '3':
            crossing_type_desc = "Railroad Over Road"

        popup_html = f"""
        <b>Crossing ID:</b> {attrs.get('CROSSING')}<br>
        <b>Street:</b> {attrs.get('STREET', 'N/A')}<br>
        <b>Railroad:</b> {attrs.get('RAILROAD')}<br>
        <b>Type:</b> {crossing_type_desc}<br>
        <b>Total Daily Trains:</b> {total_trains}<br>
        <b>Accident History:</b> {link_html}
        """

        is_nearest = (crossing == nearest_crossing)
        is_target = (current_railroad == target_railroad)

        # --- Determine icon based on crossing type ---
        icon_name = 'train'  # Default icon
        if posxing_type == '1':  # At-Grade
            icon_name = 'road'
        elif posxing_type == '2':  # RR Under Grade
            icon_name = 'arrow-down'
        elif posxing_type == '3':  # RR Over Grade
            icon_name = 'arrow-up'

        if is_target:
            # --- For the target railroad, use stars with color-coding for traffic ---
            if is_nearest:
                pin_color = 'green'
            elif total_trains > 20:
                pin_color = 'red'
            elif total_trains > 5:
                pin_color = 'orange'
            else:
                pin_color = 'blue'

            folium.Marker(
                [crossing_lat, crossing_lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=pin_color, icon=icon_name, prefix="fa")
            ).add_to(m)
        else:
            # --- For all other railroads, use small circles ---
            pin_color = 'green' if is_nearest else 'gray'

            folium.CircleMarker(
                location=[crossing_lat, crossing_lon],
                radius=4,
                color=pin_color,
                fill=True,
                fill_color=pin_color,
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(m)

    map_filename = 'crossings_map.html'
    m.save(map_filename)
    print(f"\nMap has been saved to '{map_filename}'.")

    try:
        webbrowser.open('file://' + os.path.realpath(map_filename))
        print("Opening map in your default browser...")
    except Exception as e:
        print(f"Could not automatically open the map. Please open the file manually. Error: {e}")