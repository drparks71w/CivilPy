"""Closed lofted envelopes for road surfaces and formed roadside hardware."""
from civilpy.structural.rhino_bim import (
    EmitObject, _newell_normal, _plane_basis, _triangulate_loop,
)


def swept_solid(layer, sections, tags):
    """Loft corresponding closed polygon rings into one capped mesh.

    Rings are counterclockwise looking along the sweep. Each longitudinal
    strip shares station vertices so its surface shades continuously. Adjacent
    strips and caps retain separate vertices to preserve section corners
    without averaging cap normals into the roadway surface.
    """
    sections = tuple(tuple(r) for r in sections)
    n = len(sections[0]) if sections else 0
    if len(sections) < 2 or n < 3 or any(len(s) != n for s in sections):
        raise ValueError("Need at least two corresponding polygon rings")
    normal = _newell_normal(sections[0])
    travel = tuple(sum(p[i] for p in sections[1])/n-sum(p[i] for p in sections[0])/n
                   for i in range(3))
    if sum(a*b for a,b in zip(normal, travel)) < 0:
        sections = tuple(tuple(reversed(s)) for s in sections)
    vertices, faces = [], []

    def face(points):
        start = len(vertices)
        vertices.extend(points)
        faces.append(tuple(range(start, len(vertices))))

    for j in range(n):
        k = (j+1) % n
        start = len(vertices)
        for ring in sections:
            vertices.extend((ring[j], ring[k]))
        for i in range(len(sections)-1):
            a = start + 2*i
            faces.append((a, a+1, a+3, a+2))
    for index in (0, -1):
        ring = sections[index]
        e1, e2 = _plane_basis(_newell_normal(ring))
        pts2 = [(sum(p[i]*e1[i] for i in range(3)),
                 sum(p[i]*e2[i] for i in range(3))) for p in ring]
        for a, b, c in _triangulate_loop(pts2):
            face(tuple(ring[i] for i in ((a,c,b) if index == 0 else (a,b,c))))
    return EmitObject("mesh", layer, tuple(vertices), tags, faces=tuple(faces))
