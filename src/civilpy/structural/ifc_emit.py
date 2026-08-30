#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.
"""IFC backend for the neutral BrIM emit -- the format that leaves the shop.

:func:`~civilpy.structural.rhino_bim.objects_to_3dm` writes the model Rhino
reads.  This writes the one everybody else reads, and in particular the one
Bentley reads: OpenBridge Modeler, OpenRoads Designer and MicroStation all
import IFC, and unlike DWG, STEP or STL it is the only common format that
carries the *engineering* with the geometry.  A gusset plate arrives in OBM
as an ``IfcPlate`` named ``42113-in`` whose property sets say which joint it
belongs to, what it is made of, how much of its thickness is left, and what
its rating factor was -- none of which survives a mesh exchange.

That is the whole argument for IFC here.  STEP AP242 would carry the solids
and drop every tag; STL would drop the tags *and* the units.

Mapping
-------
============================  ==========================================
emit ``bim.type``             IFC entity
============================  ==========================================
``truss_chord_top/bottom``    ``IfcMember`` (``CHORD``)
``truss_vertical``            ``IfcMember`` (``POST``)
``truss_diagonal``            ``IfcMember`` (``BRACE``)
``truss_end_post``            ``IfcMember`` (``POST``)
``truss_strut``               ``IfcMember`` (``STRUT``)
``lateral_brace``/``sway_*``  ``IfcMember`` (``BRACE``)
``gusset_plate``              ``IfcPlate``
``rivet``                     ``IfcMechanicalFastener``
``floor_beam``/``stringer``   ``IfcBeam``
``deck``                      ``IfcSlab``
``repair``/``finding``        ``IfcBuildingElementProxy`` (review overlay)
``panel_point``               ``IfcAnnotation``
============================  ==========================================

Every tag namespace becomes its own property set (``CivilPy_bim``,
``CivilPy_pay``, ``CivilPy_gusset``, ``CivilPy_repair`` ...), so a reviewer
opening the file sees the blocks the way they were authored rather than one
flat bag of strings.

Units are **metres** -- the emit is in feet and is converted on the way out,
because a metric IFC is what every importer handles without argument (the
same choice ``design/ifc_export.py`` makes in snbi_ui).

Schema: ``IFC4`` by default, which is the most widely readable.  Pass
``schema="IFC4X3_ADD2"`` for the infrastructure schema, where the spatial
container becomes an ``IfcBridge`` instead of an ``IfcBuilding``.
"""
from __future__ import annotations

import math

FT_TO_M = 0.3048

#: ``bim.type`` -> (IFC entity, PredefinedType or None)
IFC_CLASS = {
    "truss_chord_top": ("IfcMember", "CHORD"),
    "truss_chord_bottom": ("IfcMember", "CHORD"),
    "truss_vertical": ("IfcMember", "POST"),
    "truss_diagonal": ("IfcMember", "BRACE"),
    "truss_end_post": ("IfcMember", "POST"),
    "truss_strut": ("IfcMember", "STRUT"),
    "lateral_brace": ("IfcMember", "BRACE"),
    "sway_brace": ("IfcMember", "BRACE"),
    "portal_brace": ("IfcMember", "BRACE"),
    "gusset_plate": ("IfcPlate", None),
    "rivet": ("IfcMechanicalFastener", None),
    "floor_beam": ("IfcBeam", "BEAM"),
    "stringer": ("IfcBeam", "JOIST"),
    "girder": ("IfcBeam", "BEAM"),
    "deck": ("IfcSlab", "FLOOR"),
    "panel_point": ("IfcAnnotation", None),
    "repair": ("IfcBuildingElementProxy", None),
    "finding": ("IfcBuildingElementProxy", None),
}

#: Emit kinds that carry no solid geometry and are written as annotations.
_NON_SOLID = ("point", "polyline")


def _require():
    try:
        import ifcopenshell
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise ImportError(
            "ifcopenshell is required for IFC export; install it with "
            "`pip install ifcopenshell`."
        ) from exc
    return ifcopenshell


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    if n < 1e-12:
        raise ValueError("zero-length vector")
    return (a[0] / n, a[1] / n, a[2] / n)


class _Writer:
    """Builds one IFC file from neutral emit records."""

    def __init__(self, schema="IFC4", *, name="Model", project="CivilPy",
                 site="Site", author="civilpy", organization="ODOT"):
        ifcopenshell = _require()
        self.ios = ifcopenshell
        self.f = ifcopenshell.file(schema=schema)
        self.schema = self.f.schema
        self.name = name
        self._psets = 0
        self._build_header(project, site, name, author, organization)

    # -- boilerplate -------------------------------------------------------
    def _guid(self):
        return self.ios.guid.new()

    def _pt(self, xyz):
        return self.f.create_entity(
            "IfcCartesianPoint",
            Coordinates=tuple(float(v) * FT_TO_M for v in xyz))

    def _pt2(self, xy):
        return self.f.create_entity(
            "IfcCartesianPoint", Coordinates=(float(xy[0]) * FT_TO_M,
                                              float(xy[1]) * FT_TO_M))

    def _dir(self, xyz):
        return self.f.create_entity("IfcDirection",
                                    DirectionRatios=tuple(float(v) for v in xyz))

    def _axis2(self, origin, z=None, x=None):
        return self.f.create_entity(
            "IfcAxis2Placement3D", Location=self._pt(origin),
            Axis=self._dir(z) if z else None,
            RefDirection=self._dir(x) if x else None)

    def _build_header(self, project, site, name, author, organization):
        f = self.f
        person = f.create_entity("IfcPerson", FamilyName=author)
        org = f.create_entity("IfcOrganization", Name=organization)
        f.create_entity("IfcPersonAndOrganization", ThePerson=person,
                        TheOrganization=org)
        length = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
        area = f.create_entity("IfcSIUnit", UnitType="AREAUNIT",
                               Name="SQUARE_METRE")
        vol = f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT",
                              Name="CUBIC_METRE")
        units = f.create_entity("IfcUnitAssignment", Units=[length, area, vol])
        origin = self._axis2((0.0, 0.0, 0.0))
        self.ctx = f.create_entity(
            "IfcGeometricRepresentationContext", ContextType="Model",
            CoordinateSpaceDimension=3, Precision=1e-5,
            WorldCoordinateSystem=origin,
            TrueNorth=self._dir((0.0, 1.0, 0.0)))
        self.body = f.create_entity(
            "IfcGeometricRepresentationSubContext", ContextIdentifier="Body",
            ContextType="Model", ParentContext=self.ctx,
            TargetView="MODEL_VIEW")
        self.project = f.create_entity(
            "IfcProject", GlobalId=self._guid(), Name=project,
            UnitsInContext=units, RepresentationContexts=[self.ctx])

        place = f.create_entity("IfcLocalPlacement",
                                RelativePlacement=self._axis2((0.0, 0.0, 0.0)))
        self.site = f.create_entity(
            "IfcSite", GlobalId=self._guid(), Name=site,
            ObjectPlacement=place, CompositionType="ELEMENT")
        if self.schema.startswith("IFC4X3"):
            self.container = f.create_entity(
                "IfcBridge", GlobalId=self._guid(), Name=name,
                ObjectPlacement=place, CompositionType="ELEMENT",
                PredefinedType="GIRDER")
        else:
            self.container = f.create_entity(
                "IfcBuilding", GlobalId=self._guid(), Name=name,
                ObjectPlacement=place, CompositionType="ELEMENT")
        self.placement = place
        f.create_entity("IfcRelAggregates", GlobalId=self._guid(),
                        RelatingObject=self.project, RelatedObjects=[self.site])
        f.create_entity("IfcRelAggregates", GlobalId=self._guid(),
                        RelatingObject=self.site,
                        RelatedObjects=[self.container])

    # -- geometry ----------------------------------------------------------
    def _prism(self, points, vector):
        """``IfcExtrudedAreaSolid`` from a closed planar loop and its
        extrusion vector.  The loop is expressed in the profile's own plane,
        which is what IFC wants -- the emit's loops are already perpendicular
        to their extrusion, so the plane is well defined."""
        depth = _norm(vector)
        if depth < 1e-9 or len(points) < 3:
            return None
        n = _unit(vector)
        o = points[0]
        xd = None
        for p in points[1:]:
            d = _sub(p, o)
            d = _sub(d, tuple(c * _dot(d, n) for c in n))       # drop out-of-plane
            if _norm(d) > 1e-9:
                xd = _unit(d)
                break
        if xd is None:
            return None
        yd = _cross(n, xd)
        pts2 = []
        for p in points:
            d = _sub(p, o)
            pts2.append((_dot(d, xd), _dot(d, yd)))
        if abs(pts2[0][0] - pts2[-1][0]) > 1e-9 or abs(pts2[0][1] - pts2[-1][1]) > 1e-9:
            pts2.append(pts2[0])
        poly = self.f.create_entity(
            "IfcPolyline", Points=[self._pt2(p) for p in pts2])
        profile = self.f.create_entity(
            "IfcArbitraryClosedProfileDef", ProfileType="AREA",
            OuterCurve=poly)
        return self.f.create_entity(
            "IfcExtrudedAreaSolid", SweptArea=profile,
            Position=self._axis2(o, n, xd),
            ExtrudedDirection=self._dir((0.0, 0.0, 1.0)),
            Depth=depth * FT_TO_M)

    def _cylinder(self, points, radius_ft):
        base, tip = points[0], points[1]
        axis = _sub(tip, base)
        depth = _norm(axis)
        if depth < 1e-9 or not radius_ft:
            return None
        n = _unit(axis)
        ref = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
        xd = _unit(_cross(n, ref))
        profile = self.f.create_entity(
            "IfcCircleProfileDef", ProfileType="AREA",
            Radius=float(radius_ft) * FT_TO_M)
        return self.f.create_entity(
            "IfcExtrudedAreaSolid", SweptArea=profile,
            Position=self._axis2(base, n, xd),
            ExtrudedDirection=self._dir((0.0, 0.0, 1.0)),
            Depth=depth * FT_TO_M)

    def _polyline3(self, points):
        if len(points) < 2:
            return None
        return self.f.create_entity(
            "IfcPolyline", Points=[self._pt(p) for p in points])

    # -- properties --------------------------------------------------------
    def _psets_for(self, element, tags):
        """One ``IfcPropertySet`` per tag namespace, so ``bim.*``, ``pay.*``,
        ``mat.*``, ``repair.*`` arrive as the blocks they were written as."""
        groups = {}
        for k, v in tags.items():
            ns, _, leaf = k.partition(".")
            if not leaf:
                ns, leaf = "other", k
            groups.setdefault(ns, {})[leaf] = v
        sets = []
        for ns, kv in sorted(groups.items()):
            props = [
                self.f.create_entity(
                    "IfcPropertySingleValue", Name=str(k),
                    NominalValue=self.f.create_entity("IfcText", str(v)))
                for k, v in sorted(kv.items())]
            sets.append(self.f.create_entity(
                "IfcPropertySet", GlobalId=self._guid(),
                Name="CivilPy_%s" % ns, HasProperties=props))
        for ps in sets:
            self.f.create_entity(
                "IfcRelDefinesByProperties", GlobalId=self._guid(),
                RelatedObjects=[element], RelatingPropertyDefinition=ps)
        return sets

    # -- elements ----------------------------------------------------------
    def add(self, obj):
        """Write one emit record; returns the IFC element (or ``None``)."""
        tags = dict(getattr(obj, "tags", {}) or {})
        btype = tags.get("bim.type", "")
        cls, predef = IFC_CLASS.get(btype, ("IfcBuildingElementProxy", None))

        rep_item = None
        rep_type = "SweptSolid"
        if obj.kind == "prism":
            rep_item = self._prism(obj.points, obj.vector)
        elif obj.kind == "cylinder":
            rep_item = self._cylinder(obj.points, obj.radius_ft)
        elif obj.kind == "polyline":
            rep_item = self._polyline3(obj.points)
            rep_type = "Curve3D"
            cls = "IfcAnnotation"
            predef = None
        elif obj.kind == "point":
            cls = "IfcAnnotation"
            predef = None
        if rep_item is None and obj.kind not in _NON_SOLID:
            return None

        shape = None
        if rep_item is not None:
            srep = self.f.create_entity(
                "IfcShapeRepresentation", ContextOfItems=self.body,
                RepresentationIdentifier="Body", RepresentationType=rep_type,
                Items=[rep_item])
            shape = self.f.create_entity("IfcProductDefinitionShape",
                                         Representations=[srep])
        kwargs = dict(GlobalId=self._guid(),
                      Name=tags.get("bim.id") or obj.name or btype or "object",
                      Description=self._description(tags, btype),
                      ObjectPlacement=self.placement,
                      Representation=shape)
        if predef and cls != "IfcAnnotation":
            kwargs["PredefinedType"] = predef
        element = self.f.create_entity(cls, **kwargs)
        self._psets_for(element, tags)
        return element

    @staticmethod
    def _description(tags, btype):
        bits = [btype] if btype else []
        for k in ("truss.piece", "framing.piece", "gusset.face", "repair.item",
                  "finding.summary"):
            if tags.get(k):
                bits.append(str(tags[k]))
        return " | ".join(bits) or None

    def contain(self, elements):
        """Put the elements in the spatial container."""
        real = [e for e in elements if e is not None
                and not e.is_a("IfcAnnotation")]
        ann = [e for e in elements if e is not None and e.is_a("IfcAnnotation")]
        if real:
            self.f.create_entity(
                "IfcRelContainedInSpatialStructure", GlobalId=self._guid(),
                RelatingStructure=self.container, RelatedElements=real)
        if ann:
            self.f.create_entity(
                "IfcRelContainedInSpatialStructure", GlobalId=self._guid(),
                RelatingStructure=self.container, RelatedElements=ann)

    def write(self, path):
        self.f.write(str(path))


def objects_to_ifc(objects, path, *, schema: str = "IFC4",
                   name: str = "Model", project: str = "CivilPy",
                   site: str = "Site", author: str = "civilpy",
                   organization: str = "ODOT",
                   annotations: bool = True) -> dict:
    """Write neutral emit records to an IFC file.

    The third backend on the same records ``objects_to_3dm`` bakes, so the
    Rhino model and the IFC handed to OpenBridge Modeler are the same model,
    tag for tag.  ``annotations=False`` drops the marker points and
    centrelines, which most importers show as clutter.

    Returns per-``bim.type`` counts.
    """
    w = _Writer(schema, name=name, project=project, site=site, author=author,
                organization=organization)
    counts = {}
    elements = []
    for o in objects:
        if not annotations and o.kind in _NON_SOLID:
            continue
        e = w.add(o)
        if e is None:
            continue
        elements.append(e)
        key = (o.tags or {}).get("bim.type", "untyped")
        counts[key] = counts.get(key, 0) + 1
    w.contain(elements)
    w.write(path)
    return counts
