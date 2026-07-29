#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT (Ohio Department of Transportation) tools.

Clients and utilities for ODOT data systems — TIMS (:mod:`.TIMS`), Bentley
AssetWise (:mod:`.AssetWise`, :mod:`.assetwise_client`) — plus standard
bridge design-data tables (:mod:`.bridge`), plan-review checklists
(:mod:`.OSE`, :mod:`.stage_2_comments`), and plan-sheet ML/OCR helpers
(:mod:`.title_sheet`, :mod:`.gemini`).

The Midas bridge workflow (:mod:`.midas_bridge`) is re-exported here, so
either spelling of the package name reaches it::

    from civilpy.state.ohio.dot import midas_ohio_legal_loads
    from civilpy.state.ohio.DOT import midas_ohio_legal_loads
"""

from civilpy.state.ohio.DOT.midas_bridge import (  # noqa: F401
    DEFAULT_MODEL_PATH,
    API_MANUAL_ARTICLES,
    GirderModel,
    add_girder,
    add_moving_load_case,
    analyze,
    check_nonzero_envelopes,
    connect,
    ensure_base_stage,
    generate_lane_load,
    midas_ohio_legal_loads,
    moving_load_envelopes,
    new_model,
    save_model,
    set_moving_load_code,
    set_moving_load_control,
)

