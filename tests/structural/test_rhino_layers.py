#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the shared Rhino layer taxonomy (civilpy.structural.rhino_layers),
which pins Deck/Superstructure/Substructure to the C# RhinoODOTExtension's
``Core/Gdr.cs`` (commit 34f7051) so civilpy's own write-back ``.3dm`` files
already carry the same nested layer tree a fully-assembled model would."""

import pytest

rhino3dm = pytest.importorskip("rhino3dm")

from civilpy.structural import rhino_layers as rl


def test_authoritative_paths_match_gdr_cs():
    # Transcribed byte-for-byte from ODOT Rhino Plugin/Core/Gdr.cs.
    assert rl.LAYER_DECK_GROUP == "Deck"
    assert rl.LAYER_BRIDGE_DECK == "Deck::Bridge Deck"
    assert rl.LAYER_BARRIERS == "Deck::Traffic Barriers"
    assert rl.LAYER_REBAR == "Deck::Rebar"
    assert rl.LAYER_LANE_MARKINGS == "Deck::Lane Markings"
    assert rl.LAYER_SUPERSTRUCTURE == "Superstructure"
    assert rl.LAYER_GIRDERS == "Superstructure::Girders"
    assert rl.LAYER_SPLICES == "Superstructure::Splices"
    assert rl.LAYER_BEARINGS == "Superstructure::Bearings"
    assert rl.LAYER_DISPLAY == "Superstructure::Display"
    assert rl.LAYER_BOX_BEAMS == "Superstructure::Box Beams"
    assert rl.LAYER_TENDONS == "Superstructure::Tendons"
    assert rl.LAYER_DIAPHRAGMS == "Superstructure::Diaphragms"
    assert rl.LAYER_TIE_RODS == "Superstructure::Tie Rods"
    assert rl.LAYER_SUBSTRUCTURE == "Substructure"


def test_proposed_groups_are_flat_names_pending_reconciliation():
    assert rl.LAYER_CULVERT == "Culvert"
    assert rl.LAYER_SITE == "Site"


def test_ensure_layer_creates_missing_parents():
    f = rhino3dm.File3dm()
    idx = rl.ensure_layer(f, rl.LAYER_GIRDERS)
    assert f.Layers[idx].FullPath == "Superstructure::Girders"
    paths = {l.FullPath for l in f.Layers}
    assert paths == {"Superstructure", "Superstructure::Girders"}


def test_ensure_layer_is_idempotent():
    f = rhino3dm.File3dm()
    i1 = rl.ensure_layer(f, rl.LAYER_BRIDGE_DECK)
    i2 = rl.ensure_layer(f, rl.LAYER_BRIDGE_DECK)
    assert i1 == i2
    assert len(list(f.Layers)) == 2   # Deck (parent) + Deck::Bridge Deck


def test_ensure_layer_shares_parent_across_leaves():
    f = rhino3dm.File3dm()
    rl.ensure_layer(f, rl.LAYER_GIRDERS)
    rl.ensure_layer(f, rl.LAYER_SPLICES)
    parents = [l for l in f.Layers if l.FullPath == "Superstructure"]
    assert len(parents) == 1


def test_ensure_layer_default_colors_applied():
    f = rhino3dm.File3dm()
    idx = rl.ensure_layer(f, rl.LAYER_BOX_BEAMS)
    lyr = f.Layers[idx]
    assert (lyr.Color[0], lyr.Color[1], lyr.Color[2]) == \
        rl.DEFAULT_COLORS[rl.LAYER_BOX_BEAMS][:3]
