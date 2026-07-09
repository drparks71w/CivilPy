"""OGRIP (Ohio Geographically Referenced Information Program) data access.

This module provides tools to discover and download LiDAR and imagery data from
the Ohio Statewide Imagery Program (OSIP).
"""

#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import requests
import numpy as np
from pathlib import Path

# OGRIP ArcGIS REST Services
# These are the identified services for OSIP tile indices.
OSIP_TILE_SERVICES = {
    "OSIP_III": "https://gis1.oit.ohio.gov/arcgis/rest/services/OSIP_III/MapServer/0",
    "OSIP_II": "https://gis1.oit.ohio.gov/arcgis/rest/services/OSIP_II/MapServer/0",
}

def find_las_tiles(bbox_wgs84, service="OSIP_III"):
    """Find OGRIP LiDAR tiles intersecting the given WGS84 bbox.

    Parameters
    ----------
    bbox_wgs84 : tuple
        (xmin, ymin, xmax, ymax) in decimal degrees.
    service : str
        The OSIP service to query (default "OSIP_III").

    Returns
    -------
    list[dict]
        List of tile metadata dictionaries (id, url, etc).
    """
    xmin, ymin, xmax, ymax = bbox_wgs84
    url = OSIP_TILE_SERVICES.get(service, service)

    params = {
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json"
    }

    resp = requests.get(f"{url}/query", params=params)
    resp.raise_for_status()
    data = resp.json()

    tiles = []
    for feat in data.get("features", []):
        attrs = feat["attributes"]
        # The LAS URL is typically in a field like 'LAS_URL' or constructed from 'TILE_ID'
        # We'll need to verify the exact field name from the service metadata.
        tiles.append(attrs)

    return tiles

def download_las_tile(tile_url, out_path):
    """Download a LiDAR tile from the given OGRIP URL."""
    resp = requests.get(tile_url, stream=True)
    resp.raise_for_status()

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return path
