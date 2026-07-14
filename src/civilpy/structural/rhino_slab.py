#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Rhino emit layer for ODOT single span slab bridges (SB-1-24).

Turns the pure layout in :mod:`civilpy.structural.odot.slab_bridge` into
*tagged, transport-neutral* geometry records (:class:`EmitObject`), then
bakes them through whichever backend the caller has:

* :func:`write_slab_bridge` -- offline ``rhino3dm.File3dm``, no Rhino needed.
* The ``SB-1-24`` Grasshopper component -- builds ``Rhino.Geometry`` from the
  same records inside Rhino 8.
* Any live-document driver (an MCP agent, a plugin command) -- consumes the
  same records.

The point of the neutral record is that SB-1-24's engineering content is
described exactly once. A backend only decides *how* to draw a closed
polyline and how to stamp a user-string; it never decides where a bar goes.

Coordinates in the records are **feet**, matching the hub's ``Units`` and the
``gdr.``/``stm.`` tag contracts. Backends scale to the document's unit system.

Winding contract
----------------
:attr:`EmitObject.points` for a solid is a closed plan outline wound
**counter-clockwise viewed from +Z**, so its plane normal is +Z and
``extrude_ft`` (negative) drives the solid *down* from the top of slab at
z = 0. This is load-bearing, not cosmetic: ``layout_slab_bridge`` returns its
outline wound clockwise, whose plane normal is -Z, and feeding that straight
into ``Extrusion.Create(crv, -thickness, True)`` extrudes the slab **upward**
into z > 0 while the bar mats stay at z < 0 -- the "rebar appears below the
concrete deck" defect noted in the component's own TODO block. :func:`_ccw`
normalizes the winding here so no backend can reintroduce it.

User-text contract (``slab.`` namespace)
----------------------------------------
Mirrors ``gdr.``/``stm.``: a ``slab.kind`` discriminator marks structural
objects, and geometry *without* it is cosmetic display that readers ignore by
contract. See :func:`read_slab_bridge` for the round trip.

=========================  ==================================================
tag                        meaning
=========================  ==================================================
``slab.kind``              ``slab`` | ``rebar`` (absent => display only)
``slab.scd``               source standard drawing, ``SB-1-24``
``slab.id``                stable GUID, survives a Rhino -> hub -> Rhino trip
``slab.mark``              bar mark ``A`` / ``B`` / ``M`` / ``N``
``slab.size``              bar size (imperial eighths, e.g. ``7`` => #7)
``slab.diameter_in``       nominal bar diameter, in (ASTM A615)
``slab.area_in2``          nominal bar area, in^2 (ASTM A615)
``slab.mat``               ``top`` | ``bottom`` reinforcing mat
``slab.length_ft``         bar length, ft (quantity take-off)
``slab.epoxy``             ``true`` -- SB-1-24 note requires epoxy coating
``slab.thickness_in``      slab thickness, in
``slab.fc_psi``            concrete strength, psi
``slab.pay_item``          ODOT CMS pay item, *only when supplied by caller*
=========================  ==================================================

.. warning::
   ``slab.pay_item`` is never guessed. ODOT CMS item numbers are contractual
   and civilpy does not ship a table of them; pass ``pay_items=`` to stamp
   them, or the tag is simply omitted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from civilpy.structural.odot.slab_bridge import (
    CONCRETE_STRENGTH_PSI,
    REBAR_YIELD_PSI,
    REVISION,
    SCD,
    SlabBridgeInput,
    SlabBridgeLayout,
    layout_slab_bridge,
)
from civilpy.structural.rhino_layers import (
    LAYER_BRIDGE_DECK,
    LAYER_REBAR,
    ensure_layer,
)

TAG = "slab."  # user-text namespace

Point = tuple[float, float, float]

#: Nominal bar diameter (in) by imperial bar size, ASTM A615.
BAR_DIAMETER_IN: dict[int, float] = {
    3: 0.375, 4: 0.500, 5: 0.625, 6: 0.750, 7: 0.875,
    8: 1.000, 9: 1.128, 10: 1.270, 11: 1.410,
}

#: Nominal bar area (in^2) by imperial bar size, ASTM A615.
BAR_AREA_IN2: dict[int, float] = {
    3: 0.11, 4: 0.20, 5: 0.31, 6: 0.44, 7: 0.60,
    8: 0.79, 9: 1.00, 10: 1.27, 11: 1.56,
}

#: Which mat each SB-1-24 longitudinal bar mark belongs to (sheet 1).
BAR_MAT: dict[str, str] = {"A": "bottom", "B": "top", "M": "bottom", "N": "top"}


# ── neutral emit records ──────────────────────────────────────────────────


@dataclass(frozen=True)
class EmitObject:
    """One drawable object, independent of any Rhino API.

    ``kind`` is ``"solid"`` (extrude ``points`` along ``extrude_ft``) or
    ``"curve"`` (polyline through ``points``). ``tags`` are the user strings
    to stamp verbatim, already prefixed with :data:`TAG`.
    """

    kind: str
    layer: str
    points: tuple[Point, ...]
    tags: dict[str, str] = field(default_factory=dict)
    extrude_ft: float | None = None
    closed: bool = False

    #: ``"solid"`` | ``"curve"`` | ``"point"``
    KINDS = ("solid", "curve", "point")


@dataclass(frozen=True)
class SlabEmit:
    """Everything a backend needs to draw one SB-1-24 slab bridge."""

    inputs: SlabBridgeInput
    layout: SlabBridgeLayout
    objects: tuple[EmitObject, ...]
    doc_tags: dict[str, str]

    def of_kind(self, kind: str) -> tuple[EmitObject, ...]:
        """The emitted objects whose ``slab.kind`` matches (``""`` = display)."""
        return tuple(o for o in self.objects
                     if o.tags.get(TAG + "kind", "") == kind)


# ── winding ───────────────────────────────────────────────────────────────


def _signed_area(pts: tuple[Point, ...]) -> float:
    """Twice the signed plan area (shoelace); > 0 means counter-clockwise
    viewed from +Z."""
    total = 0.0
    for i, (x0, y0, _) in enumerate(pts):
        x1, y1, _ = pts[(i + 1) % len(pts)]
        total += x0 * y1 - x1 * y0
    return total


def _ccw(pts: tuple[Point, ...]) -> tuple[Point, ...]:
    """Reorder a plan outline counter-clockwise (plane normal +Z).

    See the winding contract in the module docstring: an outline wound the
    other way silently extrudes the slab in the wrong direction.
    """
    return pts if _signed_area(pts) > 0 else tuple(reversed(pts))


# ── emit ──────────────────────────────────────────────────────────────────


def slab_emit(inp: SlabBridgeInput, *,
              pay_items: dict[str, str] | None = None) -> SlabEmit:
    """Build the tagged, transport-neutral geometry for one slab bridge.

    ``pay_items`` optionally maps ``"concrete"`` and ``"rebar"`` to ODOT CMS
    item strings; absent keys leave ``slab.pay_item`` unstamped rather than
    guessed.

    Raises whatever :func:`~civilpy.structural.odot.slab_bridge.layout_slab_bridge`
    raises for an untabulated span, bad edge condition, or excessive skew.
    """
    pay_items = pay_items or {}
    layout = layout_slab_bridge(inp)
    t_ft = layout.thickness_in / 12.0

    doc_tags = {
        TAG + "scd": SCD,
        TAG + "revision": REVISION,
        TAG + "span_ft": f"{inp.span_ft:g}",
        TAG + "width_ft": f"{inp.width_ft:g}",
        TAG + "skew_deg": f"{inp.skew_deg:g}",
        TAG + "thickness_in": f"{layout.thickness_in:g}",
        TAG + "bridge_length_ft": f"{layout.bridge_length_ft:.4f}",
        TAG + "edge_condition": inp.edge_condition,
        TAG + "fc_psi": f"{CONCRETE_STRENGTH_PSI:g}",
        TAG + "fy_psi": f"{REBAR_YIELD_PSI:g}",
        TAG + "units": "ft",
    }

    objects: list[EmitObject] = []

    # ── bridge-wide parameters ────────────────────────────────────────────
    # These ride on a dedicated ``slab.kind=bridge`` marker point, *not* on
    # the document string table: rhino3dm exposes no setter for RhinoDoc
    # .Strings and cannot read it back, so a document-level tag would be
    # write-only in the offline backend (the same contract
    # ``rhino_gdr._read_gdr_raw`` reads by).
    objects.append(EmitObject(
        kind="point", layer=LAYER_BRIDGE_DECK,
        points=((0.0, 0.0, 0.0),),
        tags={TAG + "kind": "bridge", **doc_tags},
    ))

    # ── the slab solid ────────────────────────────────────────────────────
    slab_tags = {
        TAG + "kind": "slab",
        TAG + "id": uuid.uuid4().hex,
        TAG + "scd": SCD,
        TAG + "material": "concrete",
        TAG + "fc_psi": f"{CONCRETE_STRENGTH_PSI:g}",
        TAG + "thickness_in": f"{layout.thickness_in:g}",
        TAG + "span_ft": f"{inp.span_ft:g}",
        TAG + "width_ft": f"{inp.width_ft:g}",
        TAG + "skew_deg": f"{inp.skew_deg:g}",
    }
    if "concrete" in pay_items:
        slab_tags[TAG + "pay_item"] = pay_items["concrete"]

    objects.append(EmitObject(
        kind="solid",
        layer=LAYER_BRIDGE_DECK,
        points=_ccw(layout.outline),
        tags=slab_tags,
        extrude_ft=-t_ft,   # down from top of slab at z = 0
        closed=True,
    ))

    # ── the A/B/M/N longitudinal bar mats ─────────────────────────────────
    for bar in layout.bars:
        (x0, y0, z0), (x1, y1, z1) = bar.points[0], bar.points[-1]
        length_ft = ((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5
        bar_tags = {
            TAG + "kind": "rebar",
            TAG + "id": uuid.uuid4().hex,
            TAG + "scd": SCD,
            TAG + "mark": bar.mark,
            TAG + "size": str(bar.size),
            TAG + "diameter_in": f"{BAR_DIAMETER_IN[bar.size]:g}",
            TAG + "area_in2": f"{BAR_AREA_IN2[bar.size]:g}",
            TAG + "mat": BAR_MAT[bar.mark],
            TAG + "length_ft": f"{length_ft:.4f}",
            TAG + "material": "steel",
            TAG + "fy_psi": f"{REBAR_YIELD_PSI:g}",
            TAG + "epoxy": "true",   # SB-1-24 sheet 2 note
        }
        if "rebar" in pay_items:
            bar_tags[TAG + "pay_item"] = pay_items["rebar"]
        objects.append(EmitObject(
            kind="curve", layer=LAYER_REBAR,
            points=bar.points, tags=bar_tags,
        ))

    # ── plan outline: cosmetic, no slab.kind (readers skip it by contract) ─
    objects.append(EmitObject(
        kind="curve", layer=LAYER_BRIDGE_DECK,
        points=_ccw(layout.outline), tags={}, closed=True,
    ))

    return SlabEmit(inputs=inp, layout=layout,
                    objects=tuple(objects), doc_tags=doc_tags)


def rebar_quantities(emit: SlabEmit) -> dict[str, dict]:
    """Bar count, total length (ft), and weight (lb) per mark -- the take-off
    the ``slab.diameter_in`` / ``slab.length_ft`` tags exist to support.

    Steel unit weight is 490 lb/ft^3, so a bar's weight is
    ``area_in2 / 144 * 490 * length_ft``.
    """
    out: dict[str, dict] = {}
    for obj in emit.of_kind("rebar"):
        mark = obj.tags[TAG + "mark"]
        length = float(obj.tags[TAG + "length_ft"])
        area = float(obj.tags[TAG + "area_in2"])
        rec = out.setdefault(mark, {
            "size": int(obj.tags[TAG + "size"]), "count": 0,
            "length_ft": 0.0, "weight_lb": 0.0})
        rec["count"] += 1
        rec["length_ft"] += length
        rec["weight_lb"] += area / 144.0 * 490.0 * length
    for rec in out.values():
        rec["length_ft"] = round(rec["length_ft"], 3)
        rec["weight_lb"] = round(rec["weight_lb"], 2)
    return out


# ── backend: offline .3dm ─────────────────────────────────────────────────


def write_slab_bridge(out_path, inp: SlabBridgeInput, *,
                      pay_items: dict[str, str] | None = None,
                      unit_system=None) -> SlabEmit:
    """Bake one SB-1-24 slab bridge into a new ``.3dm`` and return its
    :class:`SlabEmit`.

    Geometry is written in ``unit_system`` (default feet, so points round-trip
    1:1 through :func:`read_slab_bridge`). Objects land on the shared
    ``Deck::Bridge Deck`` / ``Deck::Rebar`` layers from
    :mod:`civilpy.structural.rhino_layers` -- *not* a per-drawing
    ``Deck::SB-1-24`` layer -- so a file civilpy writes and the C# plugin
    reads resolve to the same nested layer.
    """
    from civilpy.structural.rhino_stm import _require_rhino3dm

    r3 = _require_rhino3dm()
    emit = slab_emit(inp, pay_items=pay_items)

    f = r3.File3dm()
    f.Settings.ModelUnitSystem = unit_system or r3.UnitSystem.Feet

    layers = {name: ensure_layer(f, name)
              for name in (LAYER_BRIDGE_DECK, LAYER_REBAR)}

    keep = []  # hold attributes alive until after Write (see rhino_stm._gc_paused)
    for obj in emit.objects:
        attr = r3.ObjectAttributes()
        attr.LayerIndex = layers[obj.layer]
        for k, v in obj.tags.items():
            attr.SetUserString(k, v)
        keep.append(attr)

        pts = [r3.Point3d(*p) for p in obj.points]
        if obj.kind == "point":
            f.Objects.AddPoint(pts[0], attr)
        elif obj.kind == "solid":
            pl = r3.Polyline(pts + [pts[0]])
            ext = r3.Extrusion.Create(pl.ToNurbsCurve(), obj.extrude_ft, True)
            if ext is None:
                raise ValueError(
                    f"could not extrude the slab outline for span "
                    f"{inp.span_ft} ft -- is the outline degenerate?")
            f.Objects.AddExtrusion(ext, attr)
        else:
            f.Objects.AddPolyline(
                r3.Polyline(pts + [pts[0]] if obj.closed else pts), attr)

    if not f.Write(str(out_path), 7):
        raise IOError(f"could not write slab bridge to {out_path}")
    return emit


def slab_input_from_doc_tags(doc_tags: dict) -> SlabBridgeInput:
    """Rebuild a :class:`SlabBridgeInput` from the ``slab.`` document tags read
    off a ``.3dm`` (or authored by the GH component).

    This is the Rhino -> analysis handoff: the user-text attributes carry
    enough to regenerate the design, so an engineer who traced/authored a slab
    in Rhino can drive MIDAS from those tags alone. Values may arrive as floats
    (from :func:`read_slab_bridge`) or strings (raw user text); both work.
    """
    return SlabBridgeInput(
        span_ft=int(float(doc_tags["span_ft"])),
        width_ft=float(doc_tags["width_ft"]),
        skew_deg=float(doc_tags.get("skew_deg", 0.0)),
        edge_condition=str(doc_tags.get("edge_condition", "over_the_side")),
    )


def slab_midas_payloads(inp: SlabBridgeInput, *, level: str = "L1") -> dict:
    """MIDAS ``/db/*`` payloads for an SB-1-24 slab, with **concrete** material
    and a **solid-rectangle** strip section.

    Starts from the generic hub serialization
    (:func:`~civilpy.structural.midas_models.midas_payloads`) for
    NODE/ELEM/CONS/BEAM, then overrides the steel-centric MATL/SECT the hub
    emits by default: the material becomes concrete with ``Ec`` from ``f'c``
    (:func:`~civilpy.structural.midas_models.concrete_material_block`) and the
    section becomes the equivalent-strip rectangle -- 1 ft wide (the L1 loads
    are already scaled to a 1 ft strip by the ``1/E`` distribution factor) by
    the slab thickness (:func:`~civilpy.structural.midas_models.solid_rect_section_block`).
    """
    from civilpy.structural.midas_models import (
        concrete_material_block, constraint_assign, midas_payloads,
        solid_rect_section_block,
    )
    from civilpy.structural.odot.slab_bridge import (
        CONCRETE_STRENGTH_PSI, SlabBridgeComponent, slab_design,
    )

    hub = SlabBridgeComponent(inp).structural_model(level=level)
    payloads = midas_payloads(hub)

    design = slab_design(inp.span_ft)
    t_ft = design.thickness_in / 12.0
    payloads["MATL"] = concrete_material_block(
        name=f"Class-S-{CONCRETE_STRENGTH_PSI:g}", matl_id=1,
        fc_psi=CONCRETE_STRENGTH_PSI)
    payloads["SECT"] = solid_rect_section_block(
        width=1.0, height=t_ft, sect_id=1,
        name=f"Slab-strip-{design.thickness_in:g}in")

    # Restraints: the hub's pin/roller presets fix DX/DY in a *y-vertical 2D
    # plane*, but the MIDAS beam runs along global X with dead load in global Z
    # -- so those presets leave the vertical (Z) direction unrestrained and the
    # solve returns zero reactions. Override CONS with a proper 3D simple
    # support for a beam bending in the X-Z plane: the low-station node is a pin
    # (DX,DY,DZ,RX) and the high-station node a roller (DY,DZ), free to move
    # longitudinally. Flag order is DX DY DZ RX RY RZ RW ('1' = fixed).
    nodes = payloads["NODE"]
    lo = min(nodes, key=lambda i: nodes[i]["X"])
    hi = max(nodes, key=lambda i: nodes[i]["X"])
    cons = {lo: "1111000", hi: "0110000"}
    payloads["CONS"] = constraint_assign(
        {int(i): flags for i, flags in cons.items()})
    return payloads


def push_slab_to_midas(inp: SlabBridgeInput, *, level: str = "L1",
                       midas=None, **client_kwargs) -> dict:
    """Push an SB-1-24 slab to a live MIDAS Civil NX session and report per
    table.

    Builds :func:`slab_midas_payloads`, then PUTs each table in send order,
    continuing past individual table errors (same report shape as
    :func:`~civilpy.structural.midas_models.push_midas`). Pass a
    :class:`~civilpy.structural.midas.MidasCivil`, or let it build one from
    ``~/secrets.json``.
    """
    if midas is None:
        from civilpy.structural.midas import MidasCivil
        midas = MidasCivil(**client_kwargs)
    payloads = slab_midas_payloads(inp, level=level)
    report = {}
    # MIDAS PUT /db/* merges into an existing row, so a leftover MATL/SECT of a
    # *different* TYPE (e.g. a steel DB material at id 1) survives a concrete
    # PUT and corrupts the definition. Delete the definitional rows we are
    # about to write first, so the push is deterministic regardless of what the
    # open model already held. (NODE/ELEM/CONS/BEAM PUT-replace cleanly.)
    for table in ("MATL", "SECT"):
        if table in payloads:
            try:
                midas.delete_db(table, [int(i) for i in payloads[table]])
            except Exception:
                pass        # nothing to delete is fine; the PUT still runs
    for table, assign in payloads.items():
        try:
            midas.put_db(table, assign)
            report[table] = {"sent": len(assign)}
        except Exception as exc:
            report[table] = {"error": str(exc)}
    return report


def read_slab_bridge(path) -> dict:
    """Read a ``slab.``-tagged ``.3dm`` back into ``{"doc", "slab", "rebar"}``.

    ``doc`` is the document-level tag dict; ``slab`` and ``rebar`` are lists of
    ``{"points", "tags"}`` with numeric tag values cast to ``float`` and points
    converted to feet. Untagged (cosmetic) geometry is skipped by contract,
    the same rule :func:`~civilpy.structural.rhino_gdr.read_splice_results`
    follows.
    """
    from civilpy.structural.rhino_stm import _require_rhino3dm, _unit_to_feet

    r3 = _require_rhino3dm()
    f = r3.File3dm.Read(str(path))
    if f is None:
        raise FileNotFoundError(f"could not read 3dm file: {path}")
    scale = _unit_to_feet(f)

    def _cast(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            key = k[len(TAG):] if k.startswith(TAG) else k
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                out[key] = v
        return out

    def _pts(pl) -> tuple[Point, ...]:
        return tuple((pl[i].X * scale, pl[i].Y * scale, pl[i].Z * scale)
                     for i in range(len(pl)))

    result: dict = {"doc": {}, "slab": [], "rebar": []}
    for obj in f.Objects:
        attrs = obj.Attributes
        if attrs.IsInstanceDefinitionObject:
            continue
        us = dict(attrs.GetUserStrings() or {})
        kind = us.get(TAG + "kind")
        if kind == "bridge":
            # bridge-wide parameters ride here, not on the doc string table
            result["doc"] = _cast({k: v for k, v in us.items()
                                   if k != TAG + "kind"})
            continue
        if kind not in ("slab", "rebar"):
            continue        # cosmetic display geometry -- skipped by contract
        geo = obj.Geometry
        pts: tuple[Point, ...] = ()
        if hasattr(geo, "Profile3d"):               # Extrusion -> its profile
            pl = geo.Profile3d(0, 0).TryGetPolyline()
            if pl:
                pts = _pts(pl)
        elif hasattr(geo, "ToPolyline"):            # PolylineCurve
            pts = _pts(geo.ToPolyline())
        result[kind].append({"points": pts, "tags": _cast(us)})
    return result
