"""Strut-and-tie authoring commands for Rhino (run *inside* Rhino).

This is the authoring half of the pipeline described in
``docs/Rhino Design Philosophy.md``.  It is meant to be run inside Rhino 8's
ScriptEditor (RhinoPython), not by the civilpy package -- it imports ``Rhino``
and ``rhinoscriptsyntax``, which only exist in-process.  It is therefore *not*
covered by the civilpy test suite; the read side (``civilpy.structural.
rhino_stm``) is.

It creates the symbol block definitions reliably (RhinoCommon's instance API is
stable, unlike standalone rhino3dm's) and stamps the same ``stm.*`` user text
the reader expects, so a model authored here imports with
``StrutAndTieModel.from_3dm(...)``.

Usage inside Rhino::

    import stm_authoring
    stm_authoring.STMTemplate()   # one-time: create layers + symbol blocks
    stm_authoring.STMSupport()    # place a pin / roller / fixed support
    stm_authoring.STMLoad()       # place a load arrow

Wire these to toolbar buttons (a button macro ``-_RunPythonScript (
import stm_authoring; stm_authoring.STMLoad())``) for one-click authoring.  The
long-term plan is a compiled C# plugin distributed via Yak; this prototype pins
down the schema and glyphs that plugin will reuse.
"""

import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

TAG = "stm."

LAYER_MEMBERS = "STM::Members"
LAYER_SUPPORTS = "STM::Supports"
LAYER_LOADS = "STM::Loads"

BLOCK_PIN = "STM_Pin"
BLOCK_ROLLER_V = "STM_Roller_V"
BLOCK_ROLLER_H = "STM_Roller_H"
BLOCK_FIXED = "STM_Fixed"
BLOCK_LOAD = "STM_Load"

# support type -> the fixity user text written onto the instance
SUPPORT_FIX = {
    "pin": {"fix_x": True, "fix_y": True},
    "roller-v": {"fix_y": True},
    "roller-h": {"fix_x": True},
    "fixed": {"fix_x": True, "fix_y": True, "fix_rz": True},
}
SUPPORT_BLOCK = {
    "pin": BLOCK_PIN,
    "roller-v": BLOCK_ROLLER_V,
    "roller-h": BLOCK_ROLLER_H,
    "fixed": BLOCK_FIXED,
}


# ── Setup: layers + symbol blocks ─────────────────────────────────────────────

def _ensure_layers():
    for name, color in (
        (LAYER_MEMBERS, (40, 40, 40)),
        (LAYER_SUPPORTS, (0, 110, 200)),
        (LAYER_LOADS, (0, 150, 0)),
    ):
        if not rs.IsLayer(name):
            rs.AddLayer(name, color)


def _pt(x, z):
    # glyphs are modeled in the XZ plane (front elevation), Y = 0
    return Rhino.Geometry.Point3d(x, 0.0, z)


def _ensure_block(name):
    """Create a symbol block definition from drawn glyph curves if absent."""
    if rs.IsBlock(name):
        return name
    ids = []
    if name == BLOCK_PIN:  # triangle, apex at the node
        ids.append(rs.AddPolyline(
            [_pt(0, 0), _pt(-0.4, -0.7), _pt(0.4, -0.7), _pt(0, 0)]))
    elif name in (BLOCK_ROLLER_V, BLOCK_ROLLER_H):  # a circle, top at the node
        ids.append(rs.AddCircle(rs.PlaneFromNormal(_pt(0, -0.35), (0, 1, 0)),
                                0.35))
    elif name == BLOCK_FIXED:  # wall line with hatch ticks
        ids.append(rs.AddLine(_pt(0, -0.6), _pt(0, 0.6)))
        for z in (-0.6, -0.3, 0.0, 0.3, 0.6):
            ids.append(rs.AddLine(_pt(0, z), _pt(-0.25, z - 0.25)))
    elif name == BLOCK_LOAD:  # arrow along local +X, tail at the node
        ids.append(rs.AddLine(_pt(0, 0), _pt(1.0, 0)))
        ids.append(rs.AddLine(_pt(1.0, 0), _pt(0.75, 0.12)))
        ids.append(rs.AddLine(_pt(1.0, 0), _pt(0.75, -0.12)))
    else:
        raise ValueError("unknown block: %s" % name)
    rs.AddBlock(ids, (0, 0, 0), name, delete_input=True)
    return name


def STMTemplate():
    """One-time setup: create the STM layers and symbol block definitions."""
    _ensure_layers()
    for name in (BLOCK_PIN, BLOCK_ROLLER_V, BLOCK_ROLLER_H, BLOCK_FIXED,
                 BLOCK_LOAD):
        _ensure_block(name)
    print("STM layers and symbol blocks ready.")


# ── Commands ──────────────────────────────────────────────────────────────────

def STMSupport():
    """Place a support symbol at a node and tag its fixity."""
    pt = rs.GetPoint("Pick the support node")
    if pt is None:
        return
    stype = rs.ListBox(["pin", "roller-v", "roller-h", "fixed"],
                       "Support type", "STM Support", "pin")
    if not stype:
        return
    _ensure_layers()
    block = _ensure_block(SUPPORT_BLOCK[stype])

    rs.CurrentLayer(LAYER_SUPPORTS)
    obj = rs.InsertBlock(block, pt)
    rs.SetUserText(obj, TAG + "kind", "support")
    rs.SetUserText(obj, TAG + "support", stype)
    fix = SUPPORT_FIX[stype]
    for dof in ("fix_x", "fix_y", "fix_z", "fix_rx", "fix_ry", "fix_rz"):
        rs.SetUserText(obj, TAG + dof, str(bool(fix.get(dof))).lower())
    return obj


def STMLoad():
    """Place a load arrow at a node, oriented along the force, tagged in kips."""
    node = rs.GetPoint("Pick the loaded node")
    if node is None:
        return
    tip = rs.GetPoint("Drag the load direction", node)
    if tip is None:
        return
    kips = rs.GetReal("Load magnitude (kips)", 1.0)
    if kips is None:
        return

    direction = Rhino.Geometry.Vector3d(tip - node)
    if not direction.Unitize():
        print("zero-length direction; aborted")
        return

    _ensure_layers()
    block = _ensure_block(BLOCK_LOAD)
    idef = sc.doc.InstanceDefinitions.Find(block, True)

    # rotate the block's local +X onto the force direction, then translate
    rot = Rhino.Geometry.Transform.Rotation(
        Rhino.Geometry.Vector3d(1, 0, 0), direction,
        Rhino.Geometry.Point3d(0, 0, 0))
    xform = Rhino.Geometry.Transform.Translation(node - Rhino.Geometry.Point3d(
        0, 0, 0)) * rot

    obj_id = sc.doc.Objects.AddInstanceObject(idef.Index, xform)
    rs.ObjectLayer(obj_id, LAYER_LOADS)
    rs.SetUserText(obj_id, TAG + "kind", "load")
    rs.SetUserText(obj_id, TAG + "kips", "%g" % kips)
    # a readable label next to the arrow
    sc.doc.Objects.AddTextDot("%g kips" % kips, tip)
    sc.doc.Views.Redraw()
    return obj_id


if __name__ == "__main__":
    # running the file directly in Rhino does the one-time setup
    STMTemplate()
