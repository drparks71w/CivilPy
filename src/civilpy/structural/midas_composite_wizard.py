#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Steel Composite Girder Bridge wizard (All Frame / Composite Steel I) as
pure ``/db`` payload builders for MIDAS Civil NX.

The Civil NX wizard has no API route, so a scripted build has to emit the
same model the wizard would: girders on a curved, superelevated, skewed
layout, transverse dummy deck beams, cross frames hung off rigid links,
bearing elastic links to a pier-cap/column substructure, the deck-pour
construction stages, and the load/lane/vehicle set.  Everything here is a
pure function of :class:`WizardInputs` and returns ``{id: {...}}`` *assign*
dictionaries keyed by table, ready for
``MidasCivil.put_db(table, assign)`` in :data:`TABLE_ORDER`.

What the wizard generates (observed on Civil NX 2025 v2.1, 2026-09-02, for
the three-span curved tutorial; counts are for 5 girders, 60+96+60 ft, 4/6/4
bracing divisions, 3 ft deck strips) and how this module maps to it:

===========================  ======================================================
Wizard object                Here
===========================  ======================================================
Girder elements              :func:`girder_lines` -- nodes at every 3 ft deck
(group "Girder", 440,        line, bracing line, splice and 10th point plus the
sections *Steel girder-1_1*  skewed support crossings; **the wizard copies the
/ *-2_1*)                    user's composite sections into "_1" working copies
                             and assigns those**, leaving 3/4 unused.
Transverse deck strips       :func:`deck_strips` -- one radial line per deck
(group "Dummy Beam", 730,    spacing, **each girder bay split at mid-bay** (two
section GirderWizRect-       elements per bay) plus one overhang stub each side
angle_12, material           = 10 elements per line; zero-weight copy of the deck
"Dummy Material")            material; rectangle deck-thickness x strip spacing.
"Dummy Beam2" (168,          NOT reproduced yet -- placement unknown; export the
GirderWizRectangle_9)        wizard model to JSON and diff (see checklist).
Cross frames (group          :func:`cross_frames` -- V-brace: top chord split at
"Bracing", 268; 112 truss)   the apex, bottom chord, two diagonals; chords BEAM,
                             diagonals TRUSS; chord end nodes are slaves of the
                             girder node (RIGD, 75 masters = 15 lines x 5 girders).
Support diaphragms           :func:`cross_frames` single-beam branch (W/C shape
                             at the gap below the top flange).
Substructure (groups         :func:`substructure` -- bearing seats 1 ft (link
"Substructure" 2 columns,    length) below the girder node line, pier cap laid
"Coping" 14 = 7 per cap)     along the skew line through the seats (**the cap
                             follows the superelevated bearing line, so a
                             single 48->75 tapered section reads as a wedge**),
                             one zero-length element at the column node (wizard
                             artifact), column to a fixed base.
Tapered Group                NOT created by the wizard (tutorial p.44 step) --
                             :func:`post_wizard_tapered_groups`.
Composite Section for C.S.   Created by the wizard with h = v/s = 0 and ages 0 --
                             analysis refuses until :func:`post_wizard_cscs`
                             sets h = v/s > 0 (slab 2A/u) and ages 1 / 28 d.
Span Information             NOT created by the wizard (tutorial p.47) --
                             :func:`span_information`.
10th-point groups            ten groups "10th Point Girder-n-i/j" (30 each) --
                             :func:`tenth_point_groups`.
Stages                       Stage1 10 d, Stage2 10, Stage3-1 10, Stage3-2 0,
                             Stage3-3 10, Stage3-4 0, Stage4 10, Stage5 10000 --
                             :func:`construction_stages`.
===========================  ======================================================

Unit sequence the tutorial follows (the stored model is unit-free, but the
file should *open* the way the guide leaves it): lbf/in for materials and
sections, kips/ft from the wizard Layout tab on, lbf/in again for the
stiffener/design pages.  :func:`build` returns tables in one unit system
(kips/ft) and a leading ``UNIT`` block; switch units around the property
tables only if the reviewer will open the section dialogs.

Verification checklist (run only when a live session is offered):

1. ``doc/EXPORT`` the wizard-generated model to JSON and diff NODE/ELEM/
   GRUP/SECT/STAG/CSCS/ELNK/RIGD against :func:`build` -- resolve the
   "Dummy Beam2" family and the exact node counts (wizard: 1,147 nodes,
   1,622 elements incl. 112 truss).
2. Confirm the cross-frame apex/chord node arrangement and rigid-link DOF.
3. Confirm the composite working-copy sections ("_1") are byte-identical to
   the user sections and whether anything references 3/4.
4. Re-check that ``SAVEAS`` still discards results and that the moving-load
   tracer capture still terminates the client (both true on 2025 v2.1).

Live-verified schema notes are kept with :mod:`civilpy.structural.midas`;
the ones specific to this wizard are in the function docstrings below.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence


# ------------------------------------------------------------------ inputs
@dataclass
class GirderPlates:
    """Steel I-girder plates in inches: web ``hw x tw``, top flange
    ``b1 x tf1``, bottom flange ``b2 x tf2`` (composite Steel-I Type1 vSIZE
    order is ``[Hw, tw, B1, tf1, B2, tf2]``)."""
    hw: float = 36.0
    tw: float = 0.5
    b1: float = 14.0
    tf1: float = 0.75
    b2: float = 14.0
    tf2: float = 0.75

    @property
    def depth_in(self) -> float:
        return self.hw + self.tf1 + self.tf2

    def vsize(self, scale: float = 1.0) -> list[float]:
        return [v * scale for v in (self.hw, self.tw, self.b1, self.tf1, self.b2, self.tf2)]


@dataclass
class WizardInputs:
    """The wizard's four tabs.  Lengths in feet unless the name says inches;
    stations are measured along the reference line."""
    # Layout
    spans: Sequence[float] = (60.0, 96.0, 60.0)
    radius: float = 450.0                       # convex: circle centre to the right
    skews_deg: Sequence[float] = (12.0, 19.0, 29.3, 34.3)
    deck_width: float = 30.0
    layout_offset: float = -7.0                 # reference line -> deck centre (negative = left)
    superelevation: float = -0.052              # bank rotation, constant here
    profile: Sequence[tuple[float, float]] = ((0.0, 0.0), (216.0, 0.0))   # (station, elevation)
    # Section
    girder_offsets: Sequence[float] = (-19.0, -13.0, -7.0, -1.0, 5.0)
    deck_thickness_in: float = 8.0
    haunch_in: float = 1.0
    deck_strip_spacing: float = 3.0
    bracing_divisions: Sequence[int] = (4, 6, 4)
    splices: Sequence[float] = (35.0, 80.5, 135.5, 181.0)     # section change stations
    positive_plates: GirderPlates = field(default_factory=GirderPlates)
    negative_plates: GirderPlates = field(default_factory=lambda: GirderPlates(tf1=1.25, tf2=1.625))
    negative_zones: Sequence[tuple[float, float]] = ((35.0, 80.5), (135.5, 181.0))
    gap_top: float = 0.5                        # chord end to top flange, ft
    gap_bottom: float = 0.5
    diaphragm_gap: Sequence[float] = (1.3125, 1.0208)          # abutment 1 (W12x40), abutment 2 (C15x33.9)
    pier_cap_length: float = 30.0
    pier_heights: Sequence[float] = (18.75, 17.25)
    link_length: float = 1.0
    link_stiffness: float = 1.0e10
    # Load
    barrier_widths: Sequence[float] = (1.5, 13.5, 0.0, 13.5, 1.5)   # b1..b5
    wet_concrete_kcf: float = 0.15
    barrier_klf: float = 0.14
    wearing_kcf: float = 0.14
    wearing_thickness: float = 0.26
    lane_centres_from_left_edge: Sequence[float] = (9.5, 21.5)
    impact_pct: int = 33
    # ids
    matl_steel: int = 1
    matl_deck: int = 2
    matl_pier: int = 3
    matl_dummy: int = 4
    sect_chord: int = 1
    sect_brace: int = 2
    sect_girder_pos: int = 3
    sect_girder_neg: int = 4
    sect_cap: int = 5
    sect_column: int = 6
    sect_diaphragm: Sequence[int] = (7, 8)
    sect_strip: int = 9

    @property
    def support_stations(self) -> list[float]:
        s, out = 0.0, [0.0]
        for L in self.spans:
            s += L
            out.append(s)
        return out

    @property
    def deck_edges(self) -> tuple[float, float]:
        c = self.layout_offset
        return c - self.deck_width / 2, c + self.deck_width / 2


# --------------------------------------------------------------- geometry
def _z_ref(w: WizardInputs, s: float) -> float:
    pts = list(w.profile)
    if s <= pts[0][0]:
        (s0, z0), (s1, z1) = pts[0], pts[1]
    elif s >= pts[-1][0]:
        (s0, z0), (s1, z1) = pts[-2], pts[-1]
    else:
        for (s0, z0), (s1, z1) in zip(pts, pts[1:]):
            if s0 <= s <= s1:
                break
    return z0 + (z1 - z0) * (s - s0) / (s1 - s0)


def deck_elevation(w: WizardInputs, s: float, offset: float) -> float:
    """Deck-top elevation at reference station ``s`` and lateral ``offset``:
    profile grade at the deck centre plus the bank rotation."""
    return _z_ref(w, s) + w.superelevation * (offset - w.layout_offset)


def plan_xy(w: WizardInputs, theta: float, offset: float) -> tuple[float, float]:
    """Plan coordinates on the line at lateral ``offset`` for central angle
    ``theta``.  Convex layout: circle centre at ``(0, -R)``, travel starts at
    the origin heading +x, positive offset (right) is toward the centre."""
    r = w.radius - offset
    return r * math.sin(theta), -w.radius + r * math.cos(theta)


def support_theta(w: WizardInputs, k: int, offset: float) -> float:
    """Central angle where skewed support line ``k`` crosses the line at
    ``offset`` (skew rotates the radial line about the reference point)."""
    R = w.radius
    th0, a = w.support_stations[k] / R, math.radians(w.skews_deg[k])
    r = R - offset
    t = R * math.cos(a) - math.sqrt(max(R * R * math.cos(a) ** 2 - R * R + r * r, 0.0))
    px, py = plan_xy(w, th0, 0.0)
    qx, qy = px - t * math.sin(th0 - a), py - t * math.cos(th0 - a)
    return math.atan2(qx, qy + R)


def girder_section_at(w: WizardInputs, s: float) -> int:
    return w.sect_girder_neg if any(a <= s < b for a, b in w.negative_zones) else w.sect_girder_pos


def deck_segment(w: WizardInputs, s: float) -> int:
    edges = [-1e9, *w.splices, 1e9]
    for i, (a, b) in enumerate(zip(edges, edges[1:]), 1):
        if a <= s < b:
            return i
    return len(edges) - 1


class _Mesh:
    """Node/element accumulator with tags, so groups can be derived."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.elems: dict[str, dict] = {}
        self.groups: dict[str, dict[str, set]] = defaultdict(lambda: {"N": set(), "E": set()})
        self.tags: dict[tuple, tuple] = {}
        self._n = self._e = 0

    def node(self, x, y, z, tag=None) -> int:
        self._n += 1
        self.nodes[str(self._n)] = {"X": round(x, 6), "Y": round(y, 6), "Z": round(z, 6)}
        if tag:
            self.tags[("N", self._n)] = tag
        return self._n

    def elem(self, n1, n2, sect, matl, etype="BEAM", group=None, tag=None) -> int:
        self._e += 1
        self.elems[str(self._e)] = {"TYPE": etype, "MATL": matl, "SECT": sect, "NODE": [n1, n2], "ANGLE": 0}
        if tag:
            self.tags[("E", self._e)] = tag
        if group:
            self.groups[group]["E"].add(self._e)
            self.groups[group]["N"].update((n1, n2))
        return self._e

    def xyz(self, n) -> tuple[float, float, float]:
        d = self.nodes[str(n)]
        return d["X"], d["Y"], d["Z"]


def reference_stations(w: WizardInputs) -> tuple[list[float], list[float], list[float]]:
    """(deck-strip stations, bracing-line stations, 10th-point stations)."""
    S = w.support_stations
    strips, s = [], 0.0
    while s <= S[-1] + 1e-6:
        strips.append(round(s, 4))
        s += w.deck_strip_spacing
    braces = [round(S[k] + w.spans[k] * j / n, 4) for k, n in enumerate(w.bracing_divisions) for j in range(1, n)]
    tenth = [round(S[k] + w.spans[k] * j / 10, 4) for k in range(len(w.spans)) for j in range(1, 10)]
    return strips, braces, tenth


def girder_lines(w: WizardInputs, m: _Mesh, merge_tol_ft: float = 0.5) -> dict:
    """Girder nodes/elements.  Node keys are ``("S", k)`` for the support
    crossings and ``("R", station)`` for radial lines; radial points closer
    than ``merge_tol_ft`` to another point are dropped (the wizard's
    "generate 10th point elements" behaves the same way)."""
    strips, braces, tenth = reference_stations(w)
    stations = sorted(set(strips) | set(braces) | set(w.splices) | set(tenth))
    R = w.radius
    gnodes, chains, elems = {}, {}, {}
    for i, o in enumerate(w.girder_offsets):
        pts = {("S", k): support_theta(w, k, o) for k in range(len(w.support_stations))}
        lo, hi = pts[("S", 0)], pts[("S", len(w.support_stations) - 1)]
        tol = merge_tol_ft / (R - o)
        for st in stations:
            th = st / R
            if lo + tol < th < hi - tol and all(abs(th - t) > tol for t in pts.values()):
                pts[("R", st)] = th
        chain = []
        for key, th in sorted(pts.items(), key=lambda kv: kv[1]):
            x, y = plan_xy(w, th, o)
            n = m.node(x, y, deck_elevation(w, th * R, o), ("G", i, key))
            gnodes[(i, key)] = n
            chain.append((th, n))
        chains[i] = chain
        elems[i] = []
        for (t1, n1), (t2, n2) in zip(chain, chain[1:]):
            smid = (t1 + t2) / 2 * R
            elems[i].append(m.elem(n1, n2, girder_section_at(w, smid), w.matl_steel, group="Girder", tag=("GIRDER", i, smid)))
    return {"nodes": gnodes, "chains": chains, "elems": elems}


def deck_strips(w: WizardInputs, m: _Mesh, g: dict) -> None:
    """Transverse dummy deck beams, wizard style: on every deck-spacing
    radial line, each girder bay is split at mid-bay (two elements) and one
    overhang stub runs to each deck edge -- 10 elements per line for five
    girders.  Group "Dummy Beam"; the pour-stage groups "Dummy Beam-D1"
    (positive zones) / "Dummy Beam-D2" (negative zones) are derived from the
    line's station."""
    strips, _, _ = reference_stations(w)
    left, right = w.deck_edges
    for st in strips:
        th = st / w.radius
        line = [(i, g["nodes"][(i, ("R", st))]) for i in range(len(w.girder_offsets)) if (i, ("R", st)) in g["nodes"]]
        if len(line) < 2:
            continue
        seg = deck_segment(w, st)
        pour = "Dummy Beam-D1" if seg % 2 == 1 else "Dummy Beam-D2"

        def strip(n1, n2):
            e = m.elem(n1, n2, w.sect_strip, w.matl_dummy, group="Dummy Beam", tag=("STRIP", st))
            m.groups[pour]["E"].add(e)
            m.groups[pour]["N"].update((n1, n2))

        if line[0][0] == 0:
            x, y = plan_xy(w, th, left)
            strip(m.node(x, y, deck_elevation(w, st, left)), line[0][1])
        for (_, n1), (_, n2) in zip(line, line[1:]):
            x1, y1, z1 = m.xyz(n1)
            x2, y2, z2 = m.xyz(n2)
            mid = m.node((x1 + x2) / 2, (y1 + y2) / 2, (z1 + z2) / 2)
            strip(n1, mid)
            strip(mid, n2)
        if line[-1][0] == len(w.girder_offsets) - 1:
            x, y = plan_xy(w, th, right)
            strip(line[-1][1], m.node(x, y, deck_elevation(w, st, right)))


def cross_frames(w: WizardInputs, m: _Mesh, g: dict) -> dict[int, list[int]]:
    """Intermediate V-braces on the bracing lines and at the interior
    supports, single-beam diaphragms at the abutments.  Returns
    ``{girder node: [slave nodes]}`` for the rigid links."""
    _, braces, _ = reference_stations(w)
    rigid: dict[int, list[int]] = defaultdict(list)
    slab = (w.deck_thickness_in + w.haunch_in) / 12
    ng = len(w.girder_offsets)

    def depth_at(s):
        p = w.negative_plates if girder_section_at(w, s) == w.sect_girder_neg else w.positive_plates
        return p.depth_in / 12

    def vbrace(keys, s_ref):
        d = depth_at(s_ref)
        top, bot = [], []
        for i in range(ng):
            n = g["nodes"][(i, keys[i])]
            x, y, z = m.xyz(n)
            t = m.node(x, y, z - slab - w.gap_top)
            b = m.node(x, y, z - slab - d + w.gap_bottom)
            rigid[n] += [t, b]
            top.append(t)
            bot.append(b)
        for i in range(ng - 1):
            (x1, y1, z1), (x2, y2, z2) = m.xyz(top[i]), m.xyz(top[i + 1])
            apex = m.node((x1 + x2) / 2, (y1 + y2) / 2, (z1 + z2) / 2)
            m.elem(top[i], apex, w.sect_chord, w.matl_steel, group="Bracing", tag=("XF", s_ref))
            m.elem(apex, top[i + 1], w.sect_chord, w.matl_steel, group="Bracing", tag=("XF", s_ref))
            m.elem(bot[i], bot[i + 1], w.sect_chord, w.matl_steel, group="Bracing", tag=("XF", s_ref))
            m.elem(bot[i], apex, w.sect_brace, w.matl_steel, "TRUSS", group="Bracing", tag=("XF", s_ref))
            m.elem(bot[i + 1], apex, w.sect_brace, w.matl_steel, "TRUSS", group="Bracing", tag=("XF", s_ref))

    def diaphragm(keys, sect, gap):
        ns = []
        for i in range(ng):
            n = g["nodes"][(i, keys[i])]
            x, y, z = m.xyz(n)
            dn = m.node(x, y, z - slab - gap)
            rigid[n].append(dn)
            ns.append(dn)
        for i in range(ng - 1):
            m.elem(ns[i], ns[i + 1], sect, w.matl_steel, group="Bracing", tag=("DIA", sect))

    for st in braces:
        vbrace([("R", st)] * ng, st)
    last = len(w.support_stations) - 1
    diaphragm([("S", 0)] * ng, w.sect_diaphragm[0], w.diaphragm_gap[0])
    for k in range(1, last):
        vbrace([("S", k)] * ng, w.support_stations[k])
    diaphragm([("S", last)] * ng, w.sect_diaphragm[1], w.diaphragm_gap[1])
    for n, slaves in rigid.items():
        m.groups["Bracing"]["N"].update([n, *slaves])
    return dict(rigid)


def substructure(w: WizardInputs, m: _Mesh, g: dict) -> dict:
    """Bearing seats, abutment supports, pier caps and columns.

    Seats sit ``link_length`` below the bottom flange under each girder
    support node; abutment seats are fixed (1111110).  The pier cap runs
    along the skew line through its five seats with ``(cap_length - width)/2``
    tips, **seven elements per cap including a zero-length one at the column
    node** (the wizard's artifact -- the cap chain and the column share the
    column-top position through two coincident nodes); column to a fixed
    base ``pier_height`` below.  Returns links, supports and the cap element
    lists for the tapered groups."""
    slab = (w.deck_thickness_in + w.haunch_in) / 12
    elinks, cons, caps, col_base, seats = {}, {}, {}, {}, {}
    ng, last = len(w.girder_offsets), len(w.support_stations) - 1
    centre_i = min(range(ng), key=lambda i: abs(w.girder_offsets[i] - w.layout_offset))
    for k in range(last + 1):
        p = w.negative_plates if girder_section_at(w, w.support_stations[k]) == w.sect_girder_neg else w.positive_plates
        d = p.depth_in / 12
        bb = []
        for i in range(ng):
            n = g["nodes"][(i, ("S", k))]
            x, y, z = m.xyz(n)
            b = m.node(x, y, z - slab - d - w.link_length, ("BRG", k, i))
            bb.append(b)
            K = w.link_stiffness
            elinks[str(len(elinks) + 1)] = {"NODE": [n, b], "LINK": "GEN", "ANGLE": 0, "R_S": [False] * 6,
                                            "SDR": [K, K, K, 0, 0, 0], "bSHEAR": False, "DR": [0.5, 0.5],
                                            "BNGR_NAME": "Bearing"}
        seats[k] = bb
        if k in (0, last):
            for b in bb:
                cons[str(b)] = {"ITEMS": [{"ID": 1, "GROUP_NAME": "Support", "CONSTRAINT": "1111110"}]}
            continue
        (x1, y1, z1), (x5, y5, z5) = m.xyz(bb[0]), m.xyz(bb[-1])
        L = math.hypot(x5 - x1, y5 - y1)
        ext = (w.pier_cap_length - L) / 2
        ux, uy, uz = (x5 - x1) / L, (y5 - y1) / L, (z5 - z1) / L
        tip_l = m.node(x1 - ux * ext, y1 - uy * ext, z1 - uz * ext)
        tip_r = m.node(x5 + ux * ext, y5 + uy * ext, z5 + uz * ext)
        xc, yc, zc = m.xyz(bb[centre_i])
        col_top = m.node(xc, yc, zc)                          # coincident with the seat (wizard artifact)
        chain = [tip_l, *bb[:centre_i + 1], col_top, *bb[centre_i + 1:], tip_r]
        caps[k] = [m.elem(a, b, w.sect_cap, w.matl_pier, group="Coping", tag=("CAP", k)) for a, b in zip(chain, chain[1:])]
        base = m.node(xc, yc, zc - w.pier_heights[k - 1], ("COLBASE", k))
        m.elem(base, col_top, w.sect_column, w.matl_pier, group="Substructure", tag=("COL", k))
        cons[str(base)] = {"ITEMS": [{"ID": 1, "GROUP_NAME": "Support", "CONSTRAINT": "1111110"}]}
        col_base[k] = base
    for k, bb in seats.items():
        m.groups["Substructure" if k in (0, last) else "Coping"]["N"].update(bb)
    return {"ELNK": elinks, "CONS": cons, "caps": caps, "col_base": col_base, "seats": seats}


def tenth_point_groups(w: WizardInputs, m: _Mesh, g: dict) -> dict[str, dict]:
    """The wizard's ten "10th Point Girder-n-i/j" output groups: for every
    girder, the elements whose i-end (or j-end) sits on a 10th-point line.
    Returns ``{name: {"N": set, "E": set}}``."""
    _, _, tenth = reference_stations(w)
    keys = {("R", st) for st in tenth}
    out = {}
    for i, chain in g["chains"].items():
        node_key = {n: key for (gi, key), n in g["nodes"].items() if gi == i}
        ei, ej = set(), set()
        for e in g["elems"][i]:
            n1, n2 = m.elems[str(e)]["NODE"]
            if node_key.get(n1) in keys:
                ei.add(e)
            if node_key.get(n2) in keys:
                ej.add(e)
        out[f"10th Point Girder-{i + 1}-i"] = {"E": ei, "N": {n for e in ei for n in m.elems[str(e)]["NODE"]}}
        out[f"10th Point Girder-{i + 1}-j"] = {"E": ej, "N": {n for e in ej for n in m.elems[str(e)]["NODE"]}}
    return out


# ------------------------------------------------------------- properties
def property_tables(w: WizardInputs, *, fc_deck_psi=4000.0, fc_pier_psi=3500.0, length_unit_ft=True) -> dict:
    """MATL/TDMT/TDME/TMAT/SECT for the tutorial set.  ``length_unit_ft``
    scales the inch inputs to the model unit; pass False to push the
    property tables while the session is in lbf/in as the guide does.

    Live-verified strings: ``ASTM(S)``/``A572-50``, ``ASTM(RC)``/``Grade
    C4000``; DB sections ``AISC``+``L4x4x5/8``, ``AISC10(US)``+``W12X40``;
    the TD-material link table is ``TMAT``; tapered user sections need
    ``TYPE`` 2 (``TYPE`` 3 is stored as calculated properties and the solver
    then refuses tapered groups); ``OFFSET_PT`` ``"CT"`` = centre-top."""
    L = 1 / 12 if length_unit_ft else 1.0            # inch -> model length
    F = 144.0 if length_unit_ft else 1.0             # psi  -> model stress (ksf via /1000 below)
    Ec_psi = 33000 * 0.145 ** 1.5 * math.sqrt(fc_deck_psi / 1000) * 1000
    E_dummy = Ec_psi * F / (1000 if length_unit_ft else 1)   # ksf or psi
    fc_d = fc_deck_psi * F / (1000 if length_unit_ft else 1)
    fc_p = fc_pier_psi * F / (1000 if length_unit_ft else 1)
    matl = {
        str(w.matl_steel): {"TYPE": "STEEL", "NAME": "A572-50", "DAMP_RAT": 0.02,
                            "PARAM": [{"P_TYPE": 1, "STANDARD": "ASTM(S)", "CODE": "", "DB": "A572-50"}]},
        str(w.matl_deck): {"TYPE": "CONC", "NAME": "Grade C4000", "DAMP_RAT": 0.05,
                           "PARAM": [{"P_TYPE": 1, "STANDARD": "ASTM(RC)", "CODE": "", "DB": "Grade C4000"}]},
        str(w.matl_pier): {"TYPE": "CONC", "NAME": "Grade C3500", "DAMP_RAT": 0.05,
                           "PARAM": [{"P_TYPE": 1, "STANDARD": "ASTM(RC)", "CODE": "", "DB": "Grade C3500"}]},
        str(w.matl_dummy): {"TYPE": "USER", "NAME": "Dummy Material", "DAMP_RAT": 0.05, "bMASS_DENS": False,
                            "PARAM": [{"P_TYPE": 2, "ELAST": E_dummy, "POISN": 0.2, "THERMAL": 5.5e-6, "DEN": 0.0, "MASS": 0.0}]},
    }
    tdmt = {"1": {"NAME": "C4000 C&S", "CODE": "AASHTO", "STR": fc_d, "HU": 70, "VOL": 1.0 * L, "AGE": 3, "bEXPOSE": False},
            "2": {"NAME": "C3500 C&S", "CODE": "AASHTO", "STR": fc_p, "HU": 70, "VOL": 1.0 * L, "AGE": 3, "bEXPOSE": False}}
    tdme = {"1": {"NAME": "C4000 Comp", "TYPE": "CODE", "CODENAME": "ACI", "STRENGTH": fc_d, "A": 4, "B": 0.85},
            "2": {"NAME": "C3500 Comp", "TYPE": "CODE", "CODENAME": "ACI", "STRENGTH": fc_p, "A": 4, "B": 0.85}}
    tmat = {str(w.matl_deck): {"TDMT_NAME": "C4000 C&S", "TDME_NAME": "C4000 Comp"},
            str(w.matl_pier): {"TDMT_NAME": "C3500 C&S", "TDME_NAME": "C3500 Comp"}}

    def before(shape, **kw):
        d = {"OFFSET_PT": "CC", "OFFSET_CENTER": 0, "USER_OFFSET_REF": 0, "HORZ_OFFSET_OPT": 0,
             "USERDEF_OFFSET_YI": 0, "VERT_OFFSET_OPT": 0, "USERDEF_OFFSET_ZI": 0,
             "USE_SHEAR_DEFORM": True, "USE_WARPING_EFFECT": False, "SHAPE": shape}
        d.update(kw)
        return d

    def db(name, shape, dbname, sname):
        return {"SECTTYPE": "DBUSER", "SECT_NAME": name,
                "SECT_BEFORE": before(shape, DATATYPE=1, SECT_I={"DB_NAME": dbname, "SECT_NAME": sname})}

    stiff = {"POSITION": 0, "REFERENCE_OF_D": 0, "STIFF_CNT": [2, 2, 0, 0],
             "STIFF_SHAPE": [{"NAME": "Long Stiffener", "SHAPE_TYPE": 0, "SIZE": [3.6 * L, 0.9 * L, 0, 0, 0, 0, 0, 0]}],
             "STIFF_LEFT": [{"SPACING": 12 * L, "SHAPE": 0, "USE_CALC": False}] * 2,
             "STIFF_RIGHT": [{"SPACING": 12 * L, "SHAPE": 0, "USE_CALC": False}] * 2}

    def composite(name, plates: GirderPlates):
        return {"SECTTYPE": "COMPOSITE", "SECT_NAME": name,
                "SECT_BEFORE": dict(before("I", OFFSET_PT="CT"), SECT_I={"vSIZE": plates.vsize(L), "STIFFENER": stiff},
                                    MATL_ELAST=29.0e6 / Ec_psi, MATL_DENS=0.490 / 0.150, MATL_POIS_S=0.3,
                                    MATL_POIS_C=0.2, MATL_THERMAL=1.3, USE_MULTI_ELAST=False,
                                    LONGTERM_ESEC=0, SHRINK_ESEC=0),
                "SECT_AFTER": {"SLAB": [72 * L, w.deck_thickness_in * L, w.haunch_in * L]}}

    sect = {
        str(w.sect_chord): db("L4x4x5/8", "L", "AISC", "L4x4x5/8"),
        str(w.sect_brace): db("L4x4x1/2", "L", "AISC", "L4x4x1/2"),
        str(w.sect_girder_pos): composite("Steel girder-1", w.positive_plates),
        str(w.sect_girder_neg): composite("Steel girder-2", w.negative_plates),
        str(w.sect_cap): {"SECTTYPE": "TAPERED", "SECT_NAME": "Pier cap",
                          "SECT_BEFORE": dict(before("SB", OFFSET_PT="CT", USER_OFFSET_REF=1), USERDEF_OFFSET_YJ=0,
                                              USERDEF_OFFSET_ZJ=0, TYPE=2,
                                              SECT_I={"vSIZE": [48 * L, 54 * L, 0, 0, 0, 0, 0, 0]},
                                              SECT_J={"vSIZE": [75 * L, 54 * L, 0, 0, 0, 0, 0, 0]}, Y_VAR=1, Z_VAR=1)},
        str(w.sect_column): {"SECTTYPE": "DBUSER", "SECT_NAME": "Pier",
                             "SECT_BEFORE": before("SB", DATATYPE=2, SECT_I={"vSIZE": [48 * L, 78 * L, 0, 0, 0, 0, 0, 0, 0, 0]})},
        str(w.sect_diaphragm[0]): db("W12x40", "H", "AISC10(US)", "W12X40"),
        str(w.sect_diaphragm[1]): db("C15x33.9", "C", "AISC10(US)", "C15X33.9"),
        str(w.sect_strip): {"SECTTYPE": "DBUSER", "SECT_NAME": "GirderWizRectangle",
                            "SECT_BEFORE": before("SB", OFFSET_PT="CT", DATATYPE=2,
                                                  SECT_I={"vSIZE": [w.deck_thickness_in * L, w.deck_strip_spacing * 12 * L,
                                                                    0, 0, 0, 0, 0, 0, 0, 0]})},
    }
    return {"MATL": matl, "TDMT": tdmt, "TDME": tdme, "TMAT": tmat, "SECT": sect}


# ------------------------------------------------------------------ loads
def load_tables(w: WizardInputs, m: _Mesh, g: dict) -> dict:
    """Static cases / groups / self weight / beam loads.  Wet concrete =
    deck thickness x tributary width (equal to all girders), barrier on the
    exterior girders, wearing surface by roadway tributary width."""
    stld = {"1": {"NAME": "Self Weight", "TYPE": "D", "DESC": ""},
            "2": {"NAME": "Wet Concrete", "TYPE": "D", "DESC": ""},
            "3": {"NAME": "Barrier", "TYPE": "DC", "DESC": ""},
            "4": {"NAME": "Wearing Surface", "TYPE": "DW", "DESC": ""}}
    ldgr = {str(i + 1): {"NAME": n} for i, n in enumerate(["SW", "WetConc D1", "WetConc D2", "DC2", "DW"])}
    bodf = {"1": {"LCNAME": "Self Weight", "GROUP_NAME": "SW", "FV": [0, 0, -1]}}
    offs = list(w.girder_offsets)
    spacing = (offs[-1] - offs[0]) / (len(offs) - 1)
    w_wet = w.wet_concrete_kcf * w.deck_thickness_in / 12 * spacing
    left, right = w.deck_edges
    road_l, road_r = left + w.barrier_widths[0], right - w.barrier_widths[-1]
    trib = []
    for i, o in enumerate(offs):
        lo = road_l if i == 0 else (offs[i - 1] + o) / 2
        hi = road_r if i == len(offs) - 1 else (o + offs[i + 1]) / 2
        trib.append(hi - lo)
    w_ws = [w.wearing_kcf * w.wearing_thickness * t for t in trib]

    def item(i, lc, grp, q):
        return {"ID": i, "LCNAME": lc, "GROUP_NAME": grp, "CMD": "BEAM", "TYPE": "UNILOAD", "DIRECTION": "GZ",
                "USE_PROJECTION": False, "USE_ECCEN": False, "D": [0, 1, 0, 0], "P": [-q, -q, 0, 0]}

    bmld = {}
    for i, elems in g["elems"].items():
        for e in elems:
            smid = m.tags[("E", e)][2]
            grp = "WetConc D2" if girder_section_at(w, smid) == w.sect_girder_neg else "WetConc D1"
            items = [item(1, "Wet Concrete", grp, w_wet), item(2, "Wearing Surface", "DW", w_ws[i])]
            if i in (0, len(offs) - 1):
                items.append(item(3, "Barrier", "DC2", w.barrier_klf))
            bmld[str(e)] = {"ITEMS": items}
    return {"STLD": stld, "LDGR": ldgr, "BODF": bodf, "BMLD": bmld}


def moving_load_tables(w: WizardInputs, g: dict, sub: dict) -> dict:
    """AASHTO LRFD HL-93 (truck + tandem, independent), two line lanes riding
    the girders nearest the lane centres (ECC in local y, positive left),
    influence-line control, reaction nodes at the column bases.

    Live: LLAN items need ``CENT_F`` in (0, 1); ``MLSP`` (lane support
    negative moment) rejects every key form on 2025 v2.1 -- GUI step."""
    left, _ = w.deck_edges
    offs = list(w.girder_offsets)
    llan = {}
    for j, d in enumerate(w.lane_centres_from_left_edge, 1):
        centre = left + d
        gi = min(range(len(offs)), key=lambda i: abs(offs[i] - centre))
        ecc = -(centre - offs[gi])
        llan[str(j)] = {"COMMON": {"LL_NAME": f"Lane{j}", "LOAD_DIST": "LANE", "GROUP_NAME": "", "SKEW_START": 0,
                                   "SKEW_END": 0, "MOVING": "BOTH", "WHEEL_SPACE": 6.0, "WIDTH": 12.0,
                                   "OPT_AUTO_LANE": False, "ALLOW_WIDTH": 12.0},
                        "LANE_ITEMS": [{"ELEM": e, "ECC": round(ecc, 3), "SPAN_START": False, "CENT_F": 0.5}
                                       for e in g["elems"][gi]]}
    veh = lambda n: {"MVLD_CODE": 2, "VEHICLE_LOAD_NAME": n, "VEHICLE_LOAD_NUM": 1, "VEHICLE_TYPE_NAME": n,
                     "STANDARD_CODE": "AASHTO-LRFD", "VEH_DEFAULT": {"DYN_LOAD_ALLOWANCE": w.impact_pct, "CENT_F": False}}
    lanes = [f"Lane{j}" for j in range(1, len(llan) + 1)]
    subs = [{"VEHICLE_TYPE": "VL", "VEHICLE_NAME": v, "SCALE_FACTOR": 1, "MIN_LOADED_LANE": 0,
             "MAX_LOADED_LANE": len(lanes), "LANE_NAMES": lanes} for v in ("HL-93TDM", "HL-93TRK")]
    return {"MVCD": {"1": {"CODE": "AASHTO LRFD"}},
            "MVHL": {"1": veh("HL-93TDM"), "2": veh("HL-93TRK")},
            "LLAN": llan,
            "MVLD": {"1": {"LCNAME": "MLC", "DESC": "", "TYPE": 0,
                           "DEFAULT": {"SCALE_FACTORS": [1.2, 1.0, 0.85, 0.65, 0.65, 0.65], "COMB_OPTION": "INDEPENDENT",
                                       "LANE_FACTOR_TYPE": 1, "SUB_LOAD_DATAS": subs}}},
            "MVCT": {"1": {"METHOD": "EXACT", "POINT": "INF", "iIGP": 0, "iIGPN": 3, "PLATE": "NODAL", "bSTRCALC": True,
                           "bCONCURRENT": True, "bCONCLINK": True, "FRAME": "AXIAL", "bCSTRCALC": True,
                           "bREAC": True, "bRG": False, "RGN": "", "bDISP": True, "bDG": False, "DGN": "",
                           "bFM": True, "bFG": False, "FGN": "", "bL": True, "bLG": False, "LGN": ""}},
            "MLSR": {str(n): {"NODE": 0} for n in sub["col_base"].values()}}


# ------------------------------------------------------ construction stages
STAGE_DURATIONS = (("Stage1", 10), ("Stage2", 10), ("Stage3-1", 10), ("Stage3-2", 0),
                   ("Stage3-3", 10), ("Stage3-4", 0), ("Stage4", 10), ("Stage5", 10000))


def construction_stages() -> dict:
    """STAG/STCT in the wizard's shape: substructure first, girders +
    bracing with the bearings at DEFORMED position, positive-zone pour as
    load then composite, negative-zone pour then composite, after-composite
    loads, long-term.  Erection Load 1 = DC after (Barrier), Erection Load 2 =
    DW (Wearing Surface); accumulative, creep+shrinkage with strength
    variation."""
    stag = {
        "1": {"NAME": "Stage1", "DURATION": 10, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": [],
              "ACT_ELEM": [{"GRUP_NAME": "Substructure", "AGE": 28}, {"GRUP_NAME": "Coping", "AGE": 28}],
              "ACT_BNGR": [{"BNGR_NAME": "Support", "POS": "ORIGINAL"}], "ACT_LOAD": [{"LOAD_NAME": "SW", "DAY": "FIRST"}]},
        "2": {"NAME": "Stage2", "DURATION": 10, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": [],
              "ACT_ELEM": [{"GRUP_NAME": "Girder", "AGE": 0}, {"GRUP_NAME": "Bracing", "AGE": 0}],
              "ACT_BNGR": [{"BNGR_NAME": "Bearing", "POS": "DEFORMED"}, {"BNGR_NAME": "Bracing Link", "POS": "DEFORMED"}]},
        "3": {"NAME": "Stage3-1", "DURATION": 10, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": [],
              "ACT_LOAD": [{"LOAD_NAME": "WetConc D1", "DAY": "FIRST"}]},
        "4": {"NAME": "Stage3-2", "DURATION": 0, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": [],
              "ACT_ELEM": [{"GRUP_NAME": "Dummy Beam-D1", "AGE": 1}], "DACT_LOAD": [{"LOAD_NAME": "WetConc D1", "DAY": "FIRST"}]},
        "5": {"NAME": "Stage3-3", "DURATION": 10, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": [],
              "ACT_LOAD": [{"LOAD_NAME": "WetConc D2", "DAY": "FIRST"}]},
        "6": {"NAME": "Stage3-4", "DURATION": 0, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": [],
              "ACT_ELEM": [{"GRUP_NAME": "Dummy Beam-D2", "AGE": 1}], "DACT_LOAD": [{"LOAD_NAME": "WetConc D2", "DAY": "FIRST"}]},
        "7": {"NAME": "Stage4", "DURATION": 10, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": [],
              "ACT_LOAD": [{"LOAD_NAME": "DC2", "DAY": "FIRST"}, {"LOAD_NAME": "DW", "DAY": "FIRST"}]},
        "8": {"NAME": "Stage5", "DURATION": 10000, "bSV_RSLT": True, "bSV_STEP": False, "ADD_STEP": []},
    }
    stct = {"1": {"bLAST_FINAL": True, "FINAL_STAGE": "Stage5", "iINC_NLA": 0, "iNLA_TYPE": 1, "bINC_PDL": False,
                  "bINC_TDE": True, "bCNS": True, "TYPE": "BOTH", "iITER_CR": 5, "TOL_CR": 0.01, "bOUCC": False,
                  "bITS": False, "iITS": 2, "bATS": True, "iT10": 2, "iT100": 5, "iT1K": 7, "iT5K": 10, "iT10K": 20,
                  "bTTLE_CS": False, "bRCE": False, "bVAR": True, "bAPPLY_ELA": False, "bTTLE_ES": False, "iTTLE_ES": 0,
                  "vEREC": [{"LTYPECC": "Erection Load 1", "EREC": "DC", "vLCNAME": ["Barrier"]},
                            {"LTYPECC": "Erection Load 2", "EREC": "DW", "vLCNAME": ["Wearing Surface"]}],
                  "CPFC": "INTERNAL", "bEXT_REPL": False, "bCONV": False, "bTRUSS": False, "bBEAM": False,
                  "bCHANGE_CABLE": False, "bAPPLY_IMF": False, "bITD": False, "ITD": "ALL", "bLFFC": False,
                  "bCAMBER": False, "bSD": False, "iSDOPT": 0, "SDCONST": 0, "iBSC": 0,
                  "bCALC_CFF": False, "bCALC_CSP": True, "bSELFCONS": False, "bSAVE_OCS": False}}
    return {"BNGR": {"1": {"NAME": "Support", "AUTOTYPE": 0}, "2": {"NAME": "Bearing", "AUTOTYPE": 0},
                     "3": {"NAME": "Bracing Link", "AUTOTYPE": 0}},
            "STAG": stag, "STCT": stct}


# ------------------------------------------------ post-wizard tutorial steps
def post_wizard_cscs(w: WizardInputs, *, pos_section: int, neg_section: int, deck_material: int | None = None,
                     slab_h: float | None = None, steel_h: float = 0.05) -> dict:
    """Composite Section for Construction Stage (tutorial p.59).  The wizard
    creates the two rows with ``PARTINFO_H = PARTINFO_VS = 0`` and ages 0 and
    the solver then stops with *"v/s for each Part ... must be greater than
    0"*; this is the ``CSCS`` body with element age 1 d, material age 28 d
    and h = v/s (slab default 2A/u of ``72 x t`` in, model length unit ft).
    ``TYPE`` ``"NORMAL"`` is what the wizard writes."""
    t = w.deck_thickness_in
    h_slab = slab_h if slab_h is not None else (2 * 72 * t / (2 * (72 + t))) / 12
    mat = str(deck_material or w.matl_deck)

    def parts(stage):
        return [{"PART": 1, "MTYPE": "ELEM", "MAT": "", "CSTAGE": "", "AGE": 1, "PARTINFO_H": steel_h, "PARTINFO_VS": steel_h},
                {"PART": 2, "MTYPE": "MATL", "MAT": mat, "CSTAGE": stage, "AGE": 28, "PARTINFO_H": h_slab, "PARTINFO_VS": h_slab}]

    return {"1": {"SEC": pos_section, "ASTAGE": "Stage2", "TYPE": "NORMAL", "bTAP": False, "vPARTINFO": parts("Stage3-2")},
            "2": {"SEC": neg_section, "ASTAGE": "Stage2", "TYPE": "NORMAL", "bTAP": False, "vPARTINFO": parts("Stage3-4")}}


def post_wizard_tapered_groups(cap_elements: dict[int, list[int]]) -> dict:
    """Tapered Group per pier cap (tutorial p.44): one linear/linear group over
    the whole cap chain.  The wizard does not create these, so without them
    every cap element tapers 48->75 on its own (sawtooth)."""
    return {str(i): {"NAME": f"Pier Cap - {i}", "ELEMLIST": list(els), "ZVAR": "LINEAR", "YVAR": "LINEAR"}
            for i, (k, els) in enumerate(sorted(cap_elements.items()), 1)}


def span_information(girder_chains: dict[int, list[int]], girder_elems: dict[int, list[int]],
                     support_nodes: Iterable[int], elems: dict[str, dict]) -> dict:
    """Composite Option > Span Information (tutorial p.47): one entry per girder
    per span, elements between consecutive support nodes, first element
    Support = I (or J when the element runs the other way), last = J, inner
    direction (-) local y, assignment by selection, span by element length.
    ``support_nodes`` are the girder-side bearing nodes (find them through
    ELNK, or through RIGD when the wizard hangs the link off a slave node)."""
    sup = set(support_nodes)
    out, k = {}, 0
    for gi in sorted(girder_chains):
        nodes, els = girder_chains[gi], girder_elems[gi]
        idx = [i for i, n in enumerate(nodes) if n in sup]
        for s in range(len(idx) - 1):
            k += 1
            run = els[idx[s]:idx[s + 1]]
            n_first, n_last = nodes[idx[s]], nodes[idx[s + 1]]
            items = []
            for j, e in enumerate(run):
                a, b = elems[str(e)]["NODE"][:2]
                flag = 0
                if j == 0:
                    flag = 1 if a == n_first else 2
                if j == len(run) - 1:
                    flag = 2 if b == n_last else 1
                items.append({"ELEM_KEY": e, "SUPPORT": flag})
            out[str(k)] = {"NAME": f"G{gi + 1}_Span {s + 1}", "bEXACTSPAN": False, "DIRECTION": 0, "SECTTYPE": 0,
                           "SPAN_BASE_ITEMS": items}
    return out


# ----------------------------------------------------------------- driver
TABLE_ORDER = ("UNIT", "MATL", "TDMT", "TDME", "TMAT", "SECT", "NODE", "ELEM", "TSGR", "GRUP", "BNGR", "CONS",
               "ELNK", "RIGD", "STLD", "LDGR", "BODF", "BMLD", "MVCD", "MVHL", "LLAN", "MVLD", "MVCT", "MLSR",
               "STAG", "STCT", "CSCS", "SPAN")
"""Push order that satisfies every cross-reference (groups before stages,
load groups before beam loads, lanes before moving load cases, ...)."""


def build(w: WizardInputs | None = None) -> tuple[dict, dict]:
    """Whole wizard-equivalent model.  Returns ``(payload, info)``:
    ``payload`` is ``{table: assign}`` for :data:`TABLE_ORDER` (kips/ft,
    ``UNIT`` included), ``info`` carries the girder chains/elements, support
    nodes, cap elements and column bases for post-processing."""
    w = w or WizardInputs()
    m = _Mesh()
    g = girder_lines(w, m)
    deck_strips(w, m, g)
    rigid = cross_frames(w, m, g)
    sub = substructure(w, m, g)
    tenth = tenth_point_groups(w, m, g)
    groups = {}
    for name in ["Substructure", "Coping", "Bracing", "Girder", "Dummy Beam", "Dummy Beam-D1", "Dummy Beam-D2"]:
        groups[name] = m.groups[name]
    groups.update(tenth)
    grup = {str(i + 1): {"NAME": n, "P_TYPE": 0, "N_LIST": sorted(v["N"]), "E_LIST": sorted(v["E"])}
            for i, (n, v) in enumerate(groups.items())}
    rigd = {str(n): {"ITEMS": [{"ID": 1, "GROUP_NAME": "Bracing Link", "DOF": 111111, "S_NODE": s}]} for n, s in rigid.items()}
    payload = {"UNIT": {"1": {"FORCE": "KIPS", "DIST": "FT", "HEAT": "BTU", "TEMPER": "F"}}}
    payload.update(property_tables(w))
    payload.update({"NODE": m.nodes, "ELEM": m.elems, "TSGR": post_wizard_tapered_groups(sub["caps"]), "GRUP": grup,
                    "CONS": sub["CONS"], "ELNK": sub["ELNK"], "RIGD": rigd})
    payload.update(load_tables(w, m, g))
    payload.update(moving_load_tables(w, g, sub))
    payload.update(construction_stages())
    payload["CSCS"] = post_wizard_cscs(w, pos_section=w.sect_girder_pos, neg_section=w.sect_girder_neg)
    support_nodes = [g["nodes"][(i, ("S", k))] for i in range(len(w.girder_offsets)) for k in range(len(w.support_stations))]
    chains = {i: [n for _, n in ch] for i, ch in g["chains"].items()}
    payload["SPAN"] = span_information(chains, g["elems"], support_nodes, m.elems)
    info = {"girder_chains": chains, "girder_elems": g["elems"], "support_nodes": support_nodes,
            "cap_elements": sub["caps"], "col_base": sub["col_base"], "seats": sub["seats"], "tags": m.tags}
    return payload, info


def push(client, payload: dict, *, chunk: int = 1500, tables: Sequence[str] = TABLE_ORDER) -> dict[str, str]:
    """Push ``payload`` in :data:`TABLE_ORDER` with ``client.put_db``; returns
    ``{table: "ok" | error}``.  Re-analyse afterwards: any ``/db`` write (and
    ``doc/SAVEAS``) discards existing results."""
    status = {}
    for table in tables:
        body = payload.get(table)
        if not body:
            continue
        items = list(body.items())
        try:
            for i in range(0, len(items), chunk):
                client.put_db(table, dict(items[i:i + chunk]))
            status[table] = "ok"
        except Exception as exc:  # noqa: BLE001 - report and continue
            status[table] = f"FAILED {exc}"
    return status
