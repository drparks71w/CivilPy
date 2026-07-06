"""Deck slab, parapets, and railing geometry for the girder-line model
(stage **G6**, the *deck* companion to :mod:`civilpy.structural.rhino_gdr`).

Given a girder-line bridge (the tagged ``.3dm`` the ``GirderLines`` / ``GirderShape``
commands author, read by :func:`~civilpy.structural.rhino_gdr.read_girder_model`),
this builds the riding surface the girders carry:

* a **deck slab** spanning the full bridge length across all girder lines plus an
  overhang on each side;
* a **parapet** swept along each deck edge, its cross-section taken from the ODOT
  bridge-railing catalog (:mod:`civilpy.structural.odot.bridge_railing`); and
* an optional **railing** (a steel top rail) atop each edge.

The geometry is written to a companion ``.3dm`` the ``GirderDeck`` command imports
(the same write-back handoff the splice pipeline uses), tagged ``gdr.kind=deck |
parapet | railing`` so the girder reader — which only consumes ``girder`` and
``support`` — ignores it, while the deck's engineering payload (deck thickness,
the per-girder deck DC1 and per-parapet DC2 line loads) rides along in the tags
for the analysis model to pick up.

The slab and parapet **shapes** are display geometry (like the cosmetic girder
sections); the **loads** they carry are the real contribution to the MIDAS model.
``rhino3dm`` is an optional dependency imported lazily.
"""

#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

from __future__ import annotations

import uuid
import warnings
from dataclasses import dataclass

from civilpy.structural.odot.bridge_railing import BRIDGE_RAILINGS
from civilpy.structural.rhino_gdr import (
    GTAG, GirderBridge, read_girder_model, _require_rhino3dm, _box_mesh, _fmt_num,
)

#: Default deck slab thickness (in) when the model carries no ``gdr.deck_t``.
DEFAULT_DECK_T_IN = 8.5
#: Default deck overhang beyond each exterior girder line (ft).
DEFAULT_OVERHANG_FT = 3.5
#: Reinforced-concrete unit weight (pcf) for deck and parapet dead load.
CONCRETE_PCF = 150.0
#: Default parapet designation (36 in New Jersey, TL-4).
DEFAULT_PARAPET = "BR-1 (36 in)"


@dataclass
class DeckModel:
    """Summary of a generated deck: geometry counts plus the dead-load
    quantities the analysis model needs. Lengths in the units named; loads in
    kips/ft (klf)."""

    deck_t_in: float
    width_ft: float
    length_ft: float
    overhang_ft: float
    girder_spacing_ft: float
    n_girder_lines: int
    deck_dc1_klf_interior: float   # deck self-weight on an interior girder
    parapet: str
    parapet_height_in: float
    parapet_dc2_klf_each: float    # one parapet's weight (both edges carry one)
    railing: str | None
    railing_dc2_klf_each: float
    n_deck: int
    n_parapet: int
    n_railing: int

    @property
    def total_dc2_klf(self) -> float:
        """Combined parapet + railing dead load from both edges (klf), the
        value the two exterior girders share as DC2."""
        return 2.0 * (self.parapet_dc2_klf_each + self.railing_dc2_klf_each)


def parapet_dc2_klf(designation: str, *, concrete_pcf: float = CONCRETE_PCF):
    """Dead load of one parapet/railing run (klf) from the catalog: the gross
    concrete ``section_area`` × unit weight for a concrete barrier, else the
    steel ``weight_per_ft``. Returns 0.0 when the catalog states neither."""
    r = _railing(designation)
    if r.section_area is not None:
        return r.section_area / 144.0 * concrete_pcf / 1000.0
    if r.weight_per_ft is not None:
        return r.weight_per_ft / 1000.0
    return 0.0


def _railing(designation: str):
    try:
        return BRIDGE_RAILINGS[designation]
    except KeyError:
        raise KeyError(
            f"unknown bridge-railing designation {designation!r}; choose one of "
            f"{sorted(BRIDGE_RAILINGS)}")


def _extents(bridge: GirderBridge):
    """(x_min, x_max, girder Ys sorted) in feet from the girder-line nodes."""
    xs = [n.x for n in bridge.model.nodes.values()]
    ys = sorted({round(n.y, 4) for n in bridge.model.nodes.values()})
    return min(xs), max(xs), ys


def _prism_mesh(r3, profile_yz, x0, x1):
    """Extrude a Y-Z profile (list of (y, z), CCW) along X from x0 to x1 into a
    closed mesh: two end caps plus the side quads."""
    m = r3.Mesh()
    n = len(profile_yz)
    for x in (x0, x1):
        for (y, z) in profile_yz:
            m.Vertices.Add(x, y, z)
    # side faces between the two rings
    for i in range(n):
        j = (i + 1) % n
        m.Faces.AddFace(i, j, n + j, n + i)
    # end caps as triangle fans (profiles are small convex trapezoids)
    for i in range(1, n - 1):
        m.Faces.AddFace(0, i, i + 1)
        m.Faces.AddFace(n, n + i + 1, n + i)
    m.Normals.ComputeNormals()
    m.Compact()
    return m


def _parapet_profile(base_w_ft, top_w_ft, height_ft, y_edge, inward):
    """Trapezoid cross-section (list of (y, z)) with its vertical outer face at
    ``y_edge`` and the section growing ``inward`` (+1 toward the deck centerline,
    −1 away). Sits on the deck top (z = 0 local)."""
    y_base = y_edge + inward * base_w_ft
    y_top = y_edge + inward * top_w_ft
    # outer face vertical at y_edge; inner face battered from base to top
    return [(y_edge, 0.0), (y_base, 0.0), (y_top, height_ft), (y_edge, height_ft)]


def build_deck(source, *, out_path, deck_t_in: float | None = None,
               overhang_ft: float = DEFAULT_OVERHANG_FT, haunch_in: float = 0.0,
               deck_bottom_z_ft: float = 0.0, parapet: str = DEFAULT_PARAPET,
               railing: str | None = None, railing_height_in: float = 42.0,
               concrete_pcf: float = CONCRETE_PCF, unit_system=None) -> DeckModel:
    """Generate the deck slab, edge parapets, and optional railing for a girder
    model and write them to ``out_path`` (a ``.3dm`` the ``GirderDeck`` command
    imports). ``source`` is a :class:`~civilpy.structural.rhino_gdr.GirderBridge`
    or a path to a girder ``.3dm``.

    ``deck_t_in`` defaults to the model's ``gdr.deck_t`` and then
    :data:`DEFAULT_DECK_T_IN`. The deck spans the full girder length and the full
    transverse girder spread plus ``overhang_ft`` on each side; its bottom sits at
    ``deck_bottom_z_ft`` + ``haunch_in`` above the girder-line plane (cosmetic —
    the girder line is the analysis reference). Returns a :class:`DeckModel` with
    the geometry counts and the DC1/DC2 dead loads.
    """
    bridge = source if isinstance(source, GirderBridge) else read_girder_model(source)
    r3 = _require_rhino3dm()

    if deck_t_in is None:
        deck_t_in = bridge.deck_t if bridge.deck_t is not None else DEFAULT_DECK_T_IN
    x0, x1, ys = _extents(bridge)
    if len(ys) < 2:
        raise ValueError("deck needs at least two girder lines to span between")
    y_lo, y_hi = ys[0], ys[-1]
    spacing = (y_hi - y_lo) / (len(ys) - 1)
    edge_lo, edge_hi = y_lo - overhang_ft, y_hi + overhang_ft
    width = edge_hi - edge_lo
    t_ft = deck_t_in / 12.0
    z_bot = deck_bottom_z_ft + haunch_in / 12.0
    z_top = z_bot + t_ft

    # dead loads
    dc1_interior = t_ft * spacing * concrete_pcf / 1000.0   # klf on an interior girder
    par = _railing(parapet)
    par_h_in = par.height if par.height is not None else 36.0
    dc2_parapet = parapet_dc2_klf(parapet, concrete_pcf=concrete_pcf)
    dc2_railing = parapet_dc2_klf(railing, concrete_pcf=concrete_pcf) if railing else 0.0

    f = r3.File3dm()
    f.Settings.ModelUnitSystem = unit_system or r3.UnitSystem.Feet
    # leaf layer names matching the C# Deck group (the GirderDeck importer
    # re-parents by gdr.kind; these are for a directly-opened .3dm)
    lay_deck = f.Layers.AddLayer("Bridge Deck", (170, 170, 175, 255))
    lay_par = f.Layers.AddLayer("Traffic Barriers", (150, 150, 155, 255))
    lay_rail = f.Layers.AddLayer("Traffic Barriers", (150, 150, 155, 255))

    # ── deck slab ─────────────────────────────────────────────────────────
    deck_attr = r3.ObjectAttributes()
    deck_attr.LayerIndex = lay_deck
    deck_attr.SetUserString(GTAG + "kind", "deck")
    deck_attr.SetUserString(GTAG + "id", str(uuid.uuid4()))
    deck_attr.SetUserString(GTAG + "deck.t", _fmt_num(deck_t_in))
    deck_attr.SetUserString(GTAG + "deck.width", _fmt_num(width))
    deck_attr.SetUserString(GTAG + "deck.overhang", _fmt_num(overhang_ft))
    deck_attr.SetUserString(GTAG + "deck.dc1", _fmt_num(dc1_interior))
    f.Objects.AddMesh(_box_mesh(r3, x0, x1, edge_lo, edge_hi, z_bot, z_top), deck_attr)

    # ── parapets on each edge ─────────────────────────────────────────────
    n_par = 0
    for y_edge, inward in ((edge_lo, +1.0), (edge_hi, -1.0)):
        base_w = (par.base_width or 18.0) / 12.0
        top_w = (par.top_width or par.base_width or 8.0) / 12.0
        prof = _parapet_profile(base_w, top_w, par_h_in / 12.0, y_edge, inward)
        prof = [(y, z_top + z) for (y, z) in prof]   # sit on the deck top
        pa = r3.ObjectAttributes()
        pa.LayerIndex = lay_par
        pa.SetUserString(GTAG + "kind", "parapet")
        pa.SetUserString(GTAG + "id", str(uuid.uuid4()))
        pa.SetUserString(GTAG + "parapet.designation", parapet)
        pa.SetUserString(GTAG + "parapet.h", _fmt_num(par_h_in))
        pa.SetUserString(GTAG + "parapet.dc2", _fmt_num(dc2_parapet))
        f.Objects.AddMesh(_prism_mesh(r3, prof, x0, x1), pa)
        n_par += 1

    # ── optional steel railing (a top rail box on each edge) ──────────────
    n_rail = 0
    if railing:
        rail_z = z_top + railing_height_in / 12.0
        rail_t = 0.5   # cosmetic 6 in square top rail
        for y_edge, inward in ((edge_lo, +1.0), (edge_hi, -1.0)):
            y_a = y_edge + inward * 0.25
            y_b = y_edge + inward * (0.25 + rail_t)
            ra = r3.ObjectAttributes()
            ra.LayerIndex = lay_rail
            ra.SetUserString(GTAG + "kind", "railing")
            ra.SetUserString(GTAG + "id", str(uuid.uuid4()))
            ra.SetUserString(GTAG + "railing.designation", railing)
            ra.SetUserString(GTAG + "railing.dc2", _fmt_num(dc2_railing))
            f.Objects.AddMesh(
                _box_mesh(r3, x0, x1, min(y_a, y_b), max(y_a, y_b),
                          rail_z, rail_z + rail_t), ra)
            n_rail += 1

    if not f.Write(str(out_path), 7):
        raise IOError(f"could not write deck model to {out_path}")

    return DeckModel(
        deck_t_in=deck_t_in, width_ft=width, length_ft=x1 - x0,
        overhang_ft=overhang_ft, girder_spacing_ft=spacing,
        n_girder_lines=len(ys), deck_dc1_klf_interior=dc1_interior,
        parapet=parapet, parapet_height_in=par_h_in,
        parapet_dc2_klf_each=dc2_parapet, railing=railing,
        railing_dc2_klf_each=dc2_railing,
        n_deck=1, n_parapet=n_par, n_railing=n_rail)


def read_deck_model(path):
    """Read the ``gdr.kind=deck | parapet | railing`` objects back from a deck
    ``.3dm``: a list of dicts with ``kind``, ``id``, and an ``attrs`` map of the
    kind's ``gdr.<kind>.*`` tags (numeric values as ``float``). Round-trips
    :func:`build_deck` and mirrors what the ``GirderDeck`` importer carries."""
    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")
    kinds = {"deck", "parapet", "railing"}
    out = []
    for obj in f.Objects:
        us = dict(obj.Attributes.GetUserStrings() or {})
        kind = us.get(GTAG + "kind")
        if kind not in kinds:
            continue
        prefix = GTAG + kind + "."
        attrs = {}
        for k, v in us.items():
            if not k.startswith(prefix):
                continue
            try:
                attrs[k[len(prefix):]] = float(v)
            except ValueError:
                attrs[k[len(prefix):]] = v
        out.append({"kind": kind, "id": us.get(GTAG + "id", ""), "attrs": attrs})
    return out
