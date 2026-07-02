#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
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
