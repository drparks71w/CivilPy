#  CivilPy
#  Copyright (C) 2026 Dane Parks
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
"""Shared credential loading for the ODOT AssetWise integrations.

Kept dependency-free (stdlib only) so it can be imported anywhere without
pulling in the heavier ``AssetWise`` module. The loader is cached so the
``secrets.json`` file is read once per process instead of on every API call.
"""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_assetwise_secrets():
    """Return ``(key_name, api_key)`` from ``~/secrets.json``.

    Cached for the life of the process. Raises ``FileNotFoundError`` if the
    file is absent and ``KeyError`` if the expected keys are missing — callers
    that must stay import-safe should guard accordingly.
    """
    with open(Path.home() / "secrets.json", "r") as file:
        secrets = json.load(file)
    return secrets["BENTLEY_ASSETWISE_KEY_NAME"], secrets["BENTLEY_ASSETWISE_API"]
