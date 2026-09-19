"""Run in Rhino 8 after generating the box bridge gallery.

Replace deck mesh envelopes with capped longitudinal lofts, both in the
target document and generated files. RhinoCommon is required for solid lofts;
the portable rhino3dm exporter retains its closed mesh fallback.
"""
import math
from pathlib import Path



def slab_solid(mesh):
    """Return a valid capped loft for an unskewed, X-stationed deck mesh."""
    import Rhino
    stations = {}
    for p in mesh.Vertices:
        stations.setdefault(float(p.X), set()).add((float(p.Y), float(p.Z)))
    sizes = {len(ring) for ring in stations.values()}
    if len(stations) < 2 or len(sizes) != 1 or not sizes.issubset({4, 6}):
        raise ValueError('Expected corresponding four- or six-point deck sections along X')
    curves = []
    for x, yz in sorted(stations.items()):
        cy = sum(y for y, z in yz)/len(yz)
        cz = sum(z for y, z in yz)/len(yz)
        ring = sorted(yz, key=lambda p: math.atan2(p[1]-cz, p[0]-cy))
        points = [Rhino.Geometry.Point3d(x, y, z) for y, z in ring]
        curves.append(Rhino.Geometry.Polyline(points+[points[0]]).ToNurbsCurve())
    lofts = Rhino.Geometry.Brep.CreateFromLoft(
        curves, Rhino.Geometry.Point3d.Unset, Rhino.Geometry.Point3d.Unset,
        Rhino.Geometry.LoftType.Normal, False)
    if not lofts or len(lofts) != 1:
        raise ValueError('Slab loft failed')
    solid = lofts[0].CapPlanarHoles(1e-5)
    if solid is None or not solid.IsValid or not solid.IsSolid:
        raise ValueError('Slab loft is not a valid closed solid')
    if solid.SolidOrientation == Rhino.Geometry.BrepSolidOrientation.Inward:
        solid.Flip()
    return solid


def refine(doc, output):
    """Refine the gallery and four scenario files using RhinoCommon.

    Idempotent: existing solid slabs are retained. Coordinates use feet.
    The caller saves the live document after reviewing it.
    """
    import Rhino
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.HiddenObjects = True
    settings.NormalObjects = True
    changed = 0
    for obj in list(doc.Objects.GetObjectList(settings)):
        is_example = obj.Attributes.GetUserString('bim.id') in {
            name+'-TOPPING' for name in ('integral', 'semi-integral', 'seat', 'seat-shafts')}
        is_example = is_example or obj.Attributes.GetUserString('geometry.native') == 'station_loft'
        if is_example and obj.Attributes.GetUserString('bim.type') == 'deck' and isinstance(obj.Geometry, Rhino.Geometry.Mesh):
            doc.Objects.Replace(obj.Id, slab_solid(obj.Geometry))
            attrs = obj.Attributes.Duplicate()
            attrs.WireDensity = -1
            doc.Objects.ModifyAttributes(obj.Id, attrs, True)
            changed += 1
    for name in ('integral', 'semi-integral', 'seat', 'seat-shafts', 'Box Bridge Detail Gallery'):
        path = Path(output)/(name+'.3dm')
        model = Rhino.FileIO.File3dm.Read(str(path))
        for obj in list(model.Objects):
            if obj.Attributes.GetUserString('bim.type') == 'deck' and isinstance(obj.Geometry, Rhino.Geometry.Mesh):
                solid = slab_solid(obj.Geometry)
                attrs = obj.Attributes.Duplicate()
                attrs.WireDensity = -1
                model.Objects.Delete(obj.Id)
                model.Objects.AddBrep(solid, attrs)
        temp = path.with_name(path.stem+'.native.3dm')
        if not model.Write(str(temp), 7):
            raise OSError('Could not save refined slab model')
        temp.replace(path)
    doc.Views.Redraw()
    print('Replaced {} live deck meshes with closed lofted solids'.format(changed))
