"""Geometric clearance checks for tagged reinforcing/anchor centerlines.

Bars are swept circular envelopes in feet. Results concern physical overlap,
not development length, structural capacity, concrete cover or code spacing.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def segment_distance(p, q, r, s):
    """Minimum Euclidean distance, including parallel and zero-length segments."""
    u, v, w = _sub(q, p), _sub(s, r), _sub(p, r)
    a, b, c, d, e = _dot(u, u), _dot(u, v), _dot(v, v), _dot(u, w), _dot(v, w)
    clamp = lambda x: min(1., max(0., x))
    if a < 1e-24:
        sc, tc = 0., clamp(e/c) if c > 1e-24 else 0.
    elif c < 1e-24:
        sc, tc = clamp(-d/a), 0.
    else:
        denom = a*c-b*b
        sc = clamp((b*e-c*d)/denom) if denom > 1e-14*a*c else 0.
        tc = (b*sc+e)/c
        if tc < 0.:
            tc, sc = 0., clamp(-d/a)
        elif tc > 1.:
            tc, sc = 1., clamp((b-d)/a)
    delta = tuple(w[i]+sc*u[i]-tc*v[i] for i in range(3))
    return math.sqrt(_dot(delta, delta))


@dataclass(frozen=True)
class Clash:
    first: str
    second: str
    clearance_in: float
    category: str


def check_clearance(objects, group_pairs, *, required_clearance_in=0., tolerance_in=0.001):
    """Check selected ``clash.group`` pairs; negative clearance is penetration.

    Uses AABB broad-phase rejection then all centerline segments, including
    bent bars. Tangency within tolerance is not reported as penetration.
    """
    if required_clearance_in < 0 or tolerance_in < 0:
        raise ValueError("Clearance and tolerance must be nonnegative")
    groups = {}
    for obj in objects:
        group = obj.tags.get("clash.group")
        if not group:
            continue
        radius = obj.radius_ft or float(obj.tags["rebar.dia_in"])/24.
        pts = obj.points
        bounds = tuple((min(p[k] for p in pts)-radius,
                        max(p[k] for p in pts)+radius) for k in range(3))
        groups.setdefault(group, []).append((obj, radius, bounds))
    result, seen = [], set()
    gap = required_clearance_in/12.
    for ga, gb in group_pairs:
        for a, ra, ba in groups.get(ga, ()):
            for b, rb, bb in groups.get(gb, ()):
                ids = tuple(sorted((a.tags['bim.id'], b.tags['bim.id'])))
                if ids[0] == ids[1] or ids in seen:
                    continue
                seen.add(ids)
                if any(ba[k][1]+gap < bb[k][0] or bb[k][1]+gap < ba[k][0] for k in range(3)):
                    continue
                distance = min(segment_distance(p, q, r, s)
                               for p, q in zip(a.points, a.points[1:])
                               for r, s in zip(b.points, b.points[1:]))
                clear = 12*(distance-ra-rb)
                if clear < required_clearance_in-tolerance_in:
                    result.append(Clash(*ids, clear, f"{ga}/{gb}"))
    return tuple(result)
