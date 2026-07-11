#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Shared Rhino layer taxonomy for civilpy's ``.3dm`` writers.

Every civilpy module that writes a ``.3dm`` (``rhino_gdr``, ``rhino_deck``,
``rhino_barrier``, ``rhino_box_beam``, and the ODOT SCD Grasshopper
components) should bake into these layers instead of inventing its own
flat names, so a file civilpy writes and the C# ``RhinoODOTExtension``
plugin reads (or vice versa) resolve to the *same* nested layer instead of
silently duplicating it under a differently-spelled one.

**Deck / Superstructure / Substructure are authoritative and pinned to the
C# side** -- transcribed byte-for-byte from
``ODOT Rhino Plugin/Core/Gdr.cs`` (``RhinoODOTExtension`` repo,
commit ``34f7051``, "GirderDeck command + Deck/Superstructure/Substructure
layer groups"). This mirrors NBIS/SNBI's three inspection groups (deck,
superstructure, substructure condition ratings), so the layer tree reads
the way a bridge is actually inspected and the same grouping can carry
straight through to Midas/BrR/AssetWise/IFC element groups later --
that alignment is the point of a shared layer taxonomy, not an
afterthought.

**Culvert and Site are civilpy-side PROPOSED additions** (not yet in
``Gdr.cs``) for the ODOT SCD standard-drawing components that are neither
deck, superstructure, nor substructure: headwalls/box culverts (Culvert)
and off-structure roadway items like approach slabs, portable barrier, and
drainage strips (Site). See the dated "PROPOSED" section in
``docs/Rhino Design Philosophy.md`` for the reconciliation request; do not
treat these two as frozen until the C# side signs off, same as every other
``gdr.*`` contract addition.
"""

# ── existing groups (authoritative -- Gdr.cs) ────────────────────────────

LAYER_DECK_GROUP = "Deck"
LAYER_BRIDGE_DECK = "Deck::Bridge Deck"
LAYER_BARRIERS = "Deck::Traffic Barriers"
LAYER_REBAR = "Deck::Rebar"
LAYER_LANE_MARKINGS = "Deck::Lane Markings"

LAYER_SUPERSTRUCTURE = "Superstructure"
LAYER_GIRDERS = "Superstructure::Girders"
LAYER_SPLICES = "Superstructure::Splices"
LAYER_BEARINGS = "Superstructure::Bearings"
LAYER_DISPLAY = "Superstructure::Display"
LAYER_BOX_BEAMS = "Superstructure::Box Beams"
LAYER_TENDONS = "Superstructure::Tendons"
LAYER_DIAPHRAGMS = "Superstructure::Diaphragms"
LAYER_TIE_RODS = "Superstructure::Tie Rods"

#: Reserved -- no elements are generated yet (matches Gdr.cs's own comment).
LAYER_SUBSTRUCTURE = "Substructure"

# ── PROPOSED groups (civilpy-side; pending C#-side reconciliation) ───────

LAYER_CULVERT = "Culvert"
LAYER_SITE = "Site"

#: PROPOSED leaves for the BrIM source-of-truth model (rhino_bim): concrete
#: haunches, welded shear studs, and bearing load plates get their own layers
#: under Superstructure so the composite-connection and bearing hardware can
#: be toggled/estimated independently of the girders.
LAYER_HAUNCHES = "Superstructure::Haunches"
LAYER_SHEAR_STUDS = "Superstructure::Shear Studs"
LAYER_LOAD_PLATES = "Superstructure::Load Plates"

#: Default RGBA colors, keyed by full layer path -- kept alongside the path
#: constants so every writer paints the same layer the same color.
DEFAULT_COLORS: dict[str, tuple[int, int, int, int]] = {
    LAYER_DECK_GROUP: (170, 170, 175, 255),
    LAYER_BRIDGE_DECK: (170, 170, 175, 255),
    LAYER_BARRIERS: (150, 150, 155, 255),
    LAYER_REBAR: (60, 120, 200, 255),
    LAYER_LANE_MARKINGS: (245, 225, 70, 255),
    LAYER_SUPERSTRUCTURE: (40, 40, 40, 255),
    LAYER_GIRDERS: (40, 40, 40, 255),
    LAYER_SPLICES: (200, 30, 30, 255),
    LAYER_BEARINGS: (0, 110, 200, 255),
    LAYER_DISPLAY: (110, 125, 140, 255),
    LAYER_BOX_BEAMS: (140, 140, 145, 255),
    LAYER_TENDONS: (200, 160, 20, 255),
    LAYER_DIAPHRAGMS: (100, 100, 180, 255),
    LAYER_TIE_RODS: (180, 60, 60, 255),
    LAYER_SUBSTRUCTURE: (120, 90, 70, 255),
    LAYER_CULVERT: (130, 150, 150, 255),
    LAYER_SITE: (150, 140, 120, 255),
    LAYER_HAUNCHES: (200, 200, 190, 255),
    LAYER_SHEAR_STUDS: (200, 120, 40, 255),
    LAYER_LOAD_PLATES: (90, 90, 100, 255),
}


def ensure_layer(f, full_path: str, color: tuple = None) -> int:
    """Ensure a nested ``"Group::Leaf"`` layer exists in an offline
    ``rhino3dm.File3dm``, creating any missing parents -- the Python-side
    mirror of the plugin's ``StmDocument.EnsureLayer`` (same "walk the
    ``::``-separated path, create what's missing" logic, since standalone
    ``rhino3dm`` has no ``FindByFullPath``, only parent-scoped
    ``FindName``).  Returns the leaf layer's index.

    ``color`` defaults to :data:`DEFAULT_COLORS`\\ ``[full_path]`` if not
    given and the path is one of the constants above."""
    import rhino3dm as r3

    parts = full_path.split("::")
    parent_id = None
    idx = -1
    accum = ""
    for part in parts:
        accum = part if not accum else f"{accum}::{part}"
        existing = f.Layers.FindName(part, parent_id)
        if existing.Index >= 0:
            idx = existing.Index
        else:
            lyr = r3.Layer()
            lyr.Name = part
            lyr.Color = color or DEFAULT_COLORS.get(accum, (128, 128, 128, 255))
            if parent_id is not None:
                lyr.ParentLayerId = parent_id
            idx = f.Layers.Add(lyr)
        parent_id = f.Layers[idx].Id
    return idx
