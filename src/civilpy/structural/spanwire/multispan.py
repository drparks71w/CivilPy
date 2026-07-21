#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Multi-segment span-wire configurations — Wye, H, Delta, Box.

Segments of messenger wire join at free-floating **bullrings**; poles
anchor the outer ends.  The legacy SWISS configurations map onto a small
graph: Wye (3 poles, 1 ring), H (4 poles, 2 rings), Delta (3 poles, 3
rings + 3 interior sides), Box (4 poles, 4 rings + 4 interior sides).

Plan geometry is given in coordinates (ft, math convention: +x east,
bearings in degrees counterclockwise from +x).  Two solves happen:

**Horizontal (tension relations).**  Each segment carries a constant
horizontal tension along its plan direction; each bullring must be in plan
equilibrium.  For open topologies (Simple, Wye, H) the ratios between
segment tensions follow directly.  Closed topologies (Delta, Box) are
overdetermined by one: SWISS resolves this by rotating pole 2's tail about
its bullring until the system balances, and reports the rotation.  This
module does the same — the balance pole's tail direction is treated as
unknown, the required direction is recovered from equilibrium, and
``balance_rotation_deg`` reports how far the input geometry was from
balance (SWISS calls the system "in balance" within 1 degree).  The
solved tensions always correspond to the balanced (rotated) geometry,
matching SWISS's primary behavior.  (SWISS's optional "warp" mode — hold
pole 2 and distort the ring quadrilateral instead — is not yet
implemented.)

**Vertical (sag).**  Pole attachment elevations are knowns; bullring
elevations float.  Vertical equilibrium of each massless ring is linear in
the ring elevations for a trial reference tension, so each trial solves a
small linear system, and the reference tension is bisected until the
system sag (highest attachment minus lowest wire point anywhere) matches
the required sag — the same scheme the SWISS manual describes.

Units: lb, ft, degrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from civilpy.structural.spanwire.solver import SimpleSpan, SpanLoad

#: SWISS reports "system is in balance" when pole 2 is within a degree.
BALANCE_TOLERANCE_DEG = 1.0


@dataclass(frozen=True)
class SegmentDef:
    """One wire segment between two named nodes.

    Load positions are measured from the ``start`` node along the plan
    length.
    """

    name: str
    start: str
    end: str
    wire_weight_plf: float = 0.0
    loads: tuple[SpanLoad, ...] = ()


@dataclass(frozen=True)
class SegmentResult:
    name: str
    start: str
    end: str
    tension_relation: float
    horizontal_tension_lb: float
    start_elevation_ft: float
    end_elevation_ft: float
    start_reaction_lb: float
    end_reaction_lb: float
    low_point_x_ft: float
    low_point_elevation_ft: float


@dataclass(frozen=True)
class SystemSolution:
    reference_segment: str
    reference_tension_lb: float
    sag_ft: float
    segments: tuple[SegmentResult, ...]
    ring_elevations: dict[str, float]
    balance_pole: str | None
    balance_rotation_deg: float
    balanced_pole_position: tuple[float, float] | None

    @property
    def in_balance(self) -> bool:
        return abs(self.balance_rotation_deg) <= BALANCE_TOLERANCE_DEG

    @property
    def low_point_elevation_ft(self) -> float:
        return min(s.low_point_elevation_ft for s in self.segments)

    def pole_tensions(self) -> dict[str, float]:
        """Stringing tension pulling on each pole (dead load only), lb."""
        tensions: dict[str, float] = {}
        for seg in self.segments:
            for node in (seg.start, seg.end):
                if node in self.ring_elevations:
                    continue
                tensions[node] = seg.horizontal_tension_lb
        return tensions


class SpanWireSystem:
    """A network of wire segments joining poles and bullrings in plan."""

    def __init__(
        self,
        poles: dict[str, tuple[float, float]],
        rings: dict[str, tuple[float, float]],
        segments: list[SegmentDef] | tuple[SegmentDef, ...],
        pole_attachment_elevations: dict[str, float] | None = None,
        balance_pole: str | None = None,
    ):
        if set(poles) & set(rings):
            raise ValueError("pole and ring names must be distinct")
        self.poles = dict(poles)
        self.rings = dict(rings)
        self.segments = tuple(segments)
        names = [s.name for s in self.segments]
        if len(set(names)) != len(names):
            raise ValueError("segment names must be unique")

        nodes = {**self.poles, **self.rings}
        incident: dict[str, int] = {n: 0 for n in nodes}
        for seg in self.segments:
            for node in (seg.start, seg.end):
                if node not in nodes:
                    raise ValueError(f"segment {seg.name}: unknown node {node!r}")
                incident[node] += 1
        for pole in self.poles:
            if incident[pole] != 1:
                raise ValueError(f"pole {pole!r} must anchor exactly one segment")
        for ring in self.rings:
            if incident[ring] < 3:
                raise ValueError(f"bullring {ring!r} needs at least 3 segments")

        self.pole_attachment_elevations = {
            p: (pole_attachment_elevations or {}).get(p, 0.0) for p in self.poles
        }

        # Degree of static indeterminacy of the plan-equilibrium problem:
        # 2 equations per ring vs. (segments - 1) tension ratios.
        redundancy = 2 * len(self.rings) - (len(self.segments) - 1)
        if redundancy == 0:
            self.balance_pole = None
        elif redundancy == 1:
            if balance_pole is None:
                balance_pole = "P2" if "P2" in self.poles else None
            if balance_pole not in self.poles:
                raise ValueError(
                    "closed configuration: name a balance_pole to rotate for "
                    "system balance (SWISS rotates pole 2)"
                )
            self.balance_pole = balance_pole
        else:
            raise ValueError(
                f"unsupported topology: {len(self.segments)} segments / "
                f"{len(self.rings)} rings"
            )

    # -- plan geometry -----------------------------------------------------

    def _position(self, node: str) -> tuple[float, float]:
        return self.poles.get(node) or self.rings[node]

    def plan_length(self, seg: SegmentDef) -> float:
        (x0, y0), (x1, y1) = self._position(seg.start), self._position(seg.end)
        length = math.hypot(x1 - x0, y1 - y0)
        if length <= 0:
            raise ValueError(f"segment {seg.name} has zero plan length")
        return length

    def _direction_from(self, seg: SegmentDef, node: str) -> tuple[float, float]:
        """Unit plan vector pointing from ``node`` along the segment."""
        other = seg.end if node == seg.start else seg.start
        (x0, y0), (x1, y1) = self._position(node), self._position(other)
        length = self.plan_length(seg)
        return ((x1 - x0) / length, (y1 - y0) / length)

    def _balance_segment(self) -> SegmentDef | None:
        if self.balance_pole is None:
            return None
        return next(
            s for s in self.segments if self.balance_pole in (s.start, s.end)
        )

    # -- horizontal equilibrium: tension relations -------------------------

    def tension_relations(
        self, reference: str | None = None
    ) -> tuple[dict[str, float], float, tuple[float, float] | None]:
        """Segment tension ratios from bullring plan equilibrium.

        Returns ``(relations, balance_rotation_deg, balanced_pole_position)``
        with ``relations[reference] == 1.0``.  For closed configurations the
        balance pole's tail direction is solved from equilibrium; the
        rotation is the signed angle (+CCW) from the input direction to the
        balanced one, and the balanced pole position is where the pole lands.
        """
        balance_seg = self._balance_segment()
        reference = self._pick_reference(reference, balance_seg)
        if not self.rings:
            return {reference: 1.0}, 0.0, None

        unknowns = [s.name for s in self.segments if s.name != reference]
        if balance_seg is not None:
            unknowns.remove(balance_seg.name)
            unknowns += [f"{balance_seg.name}@x", f"{balance_seg.name}@y"]
        col = {name: i for i, name in enumerate(unknowns)}

        n_rows = 2 * len(self.rings)
        matrix = np.zeros((n_rows, len(unknowns)))
        rhs = np.zeros(n_rows)
        for r, ring in enumerate(self.rings):
            for seg in self.segments:
                if ring not in (seg.start, seg.end):
                    continue
                ux, uy = self._direction_from(seg, ring)
                if balance_seg is not None and seg.name == balance_seg.name:
                    # The tail force on the ring is an unknown vector.
                    matrix[2 * r, col[f"{seg.name}@x"]] = 1.0
                    matrix[2 * r + 1, col[f"{seg.name}@y"]] = 1.0
                elif seg.name == reference:
                    rhs[2 * r] -= ux
                    rhs[2 * r + 1] -= uy
                else:
                    matrix[2 * r, col[seg.name]] = ux
                    matrix[2 * r + 1, col[seg.name]] = uy

        solution, residual, rank, _ = np.linalg.lstsq(matrix, rhs, rcond=None)
        if rank < len(unknowns):
            raise ValueError("degenerate plan geometry: tensions are not unique")
        misclose = np.linalg.norm(matrix @ solution - rhs)
        if misclose > 1e-8:
            raise ValueError(
                "plan geometry cannot be balanced: equilibrium misclosure "
                f"{misclose:.3g} (check angles/coordinates)"
            )

        relations = {reference: 1.0}
        for seg in self.segments:
            if seg.name == reference or (
                balance_seg is not None and seg.name == balance_seg.name
            ):
                continue
            relations[seg.name] = float(solution[col[seg.name]])

        rotation = 0.0
        balanced_position = None
        if balance_seg is not None:
            ring = balance_seg.start if balance_seg.start in self.rings else balance_seg.end
            fx = float(solution[col[f"{balance_seg.name}@x"]])
            fy = float(solution[col[f"{balance_seg.name}@y"]])
            tension = math.hypot(fx, fy)
            relations[balance_seg.name] = tension
            ux, uy = self._direction_from(balance_seg, ring)
            required = math.atan2(fy, fx)
            actual = math.atan2(uy, ux)
            rotation = math.degrees(
                (required - actual + math.pi) % (2 * math.pi) - math.pi
            )
            rx, ry = self._position(ring)
            length = self.plan_length(balance_seg)
            balanced_position = (
                rx + length * math.cos(required),
                ry + length * math.sin(required),
            )

        bad = [name for name, rel in relations.items() if rel <= 1e-9]
        if bad:
            raise ValueError(
                f"geometry gives non-positive tension in {', '.join(bad)}: "
                "the wire cannot push (check angles — see the SWISS manual's "
                "wye-orientation warning)"
            )
        return relations, rotation, balanced_position

    def _pick_reference(
        self, reference: str | None, balance_seg: SegmentDef | None
    ) -> str:
        names = [s.name for s in self.segments]
        if reference is None:
            candidates = [
                n for n in names
                if balance_seg is None or n != balance_seg.name
            ]
            return candidates[-1]
        if reference not in names:
            raise ValueError(f"unknown reference segment {reference!r}")
        if balance_seg is not None and reference == balance_seg.name:
            raise ValueError("the balance pole's tail cannot be the reference")
        return reference

    # -- vertical equilibrium: ring elevations and sag ---------------------

    def _elevation(self, node: str, ring_elevations: dict[str, float]) -> float:
        if node in self.rings:
            return ring_elevations[node]
        return self.pole_attachment_elevations[node]

    def _spans(self, ring_elevations: dict[str, float]) -> dict[str, SimpleSpan]:
        return {
            seg.name: SimpleSpan(
                self.plan_length(seg),
                wire_weight_plf=seg.wire_weight_plf,
                start_elevation_ft=self._elevation(seg.start, ring_elevations),
                end_elevation_ft=self._elevation(seg.end, ring_elevations),
                loads=seg.loads,
            )
            for seg in self.segments
        }

    def _ring_elevations(
        self, relations: dict[str, float], h_ref: float
    ) -> dict[str, float]:
        """Solve vertical equilibrium of the massless rings (linear)."""
        ring_index = {name: i for i, name in enumerate(self.rings)}
        matrix = np.zeros((len(self.rings), len(self.rings)))
        rhs = np.zeros(len(self.rings))
        for ring, r in ring_index.items():
            for seg in self.segments:
                if ring not in (seg.start, seg.end):
                    continue
                other = seg.end if ring == seg.start else seg.start
                length = self.plan_length(seg)
                h_over_l = relations[seg.name] * h_ref / length
                span = SimpleSpan(
                    length, wire_weight_plf=seg.wire_weight_plf, loads=seg.loads
                )
                beam_r0 = span._beam_start_reaction
                beam_end = span.total_load_lb - beam_r0
                rhs[r] -= beam_r0 if ring == seg.start else beam_end
                matrix[r, r] += h_over_l
                if other in ring_index:
                    matrix[r, ring_index[other]] -= h_over_l
                else:
                    rhs[r] += h_over_l * self.pole_attachment_elevations[other]
        solution = np.linalg.solve(matrix, rhs)
        return {name: float(solution[i]) for name, i in ring_index.items()}

    def system_sag(self, relations: dict[str, float], h_ref: float) -> float:
        ring_elevations = self._ring_elevations(relations, h_ref)
        spans = self._spans(ring_elevations)
        low = min(
            spans[seg.name]._low_point(relations[seg.name] * h_ref)[1]
            for seg in self.segments
        )
        high = max(
            *self.pole_attachment_elevations.values(), *ring_elevations.values()
        )
        return high - low

    def solve(
        self,
        required_sag_ft: float,
        reference: str | None = None,
        tol_ft: float = 1e-6,
    ) -> SystemSolution:
        """Bisect the reference tension until the system sag matches."""
        relations, rotation, balanced_position = self.tension_relations(reference)
        reference_name = next(n for n, rel in relations.items() if rel == 1.0)

        total = sum(
            sum(p.weight_lb for p in seg.loads)
            + seg.wire_weight_plf * self.plan_length(seg)
            for seg in self.segments
        )
        if total <= 0:
            raise ValueError("system carries no load; sag is undefined")

        h_hi = max(total, 1.0)
        doublings = 0
        while self.system_sag(relations, h_hi) > required_sag_ft:
            h_hi *= 2.0
            doublings += 1
            if doublings > 80:
                raise ValueError(
                    f"required sag {required_sag_ft} ft is unreachable — it "
                    "must exceed the taut-system elevation spread"
                )
        h_lo = h_hi / 2.0
        while self.system_sag(relations, h_lo) < required_sag_ft:
            h_lo /= 2.0

        while h_hi - h_lo > max(1e-9, 1e-12 * h_hi):
            h_mid = (h_lo + h_hi) / 2.0
            if self.system_sag(relations, h_mid) > required_sag_ft:
                h_lo = h_mid
            else:
                h_hi = h_mid
            if abs(self.system_sag(relations, h_mid) - required_sag_ft) < tol_ft:
                h_lo = h_hi = h_mid
        h_ref = (h_lo + h_hi) / 2.0

        ring_elevations = self._ring_elevations(relations, h_ref)
        spans = self._spans(ring_elevations)
        results = []
        for seg in self.segments:
            span = spans[seg.name]
            h_seg = relations[seg.name] * h_ref
            low_x, low_y = span._low_point(h_seg)
            slope = span._chord_slope
            beam_r0 = span._beam_start_reaction
            results.append(
                SegmentResult(
                    name=seg.name,
                    start=seg.start,
                    end=seg.end,
                    tension_relation=relations[seg.name],
                    horizontal_tension_lb=h_seg,
                    start_elevation_ft=span.start_elevation_ft,
                    end_elevation_ft=span.end_elevation_ft,
                    start_reaction_lb=beam_r0 - h_seg * slope,
                    end_reaction_lb=(span.total_load_lb - beam_r0) + h_seg * slope,
                    low_point_x_ft=low_x,
                    low_point_elevation_ft=low_y,
                )
            )
        return SystemSolution(
            reference_segment=reference_name,
            reference_tension_lb=h_ref,
            sag_ft=self.system_sag(relations, h_ref),
            segments=tuple(results),
            ring_elevations=ring_elevations,
            balance_pole=self.balance_pole,
            balance_rotation_deg=rotation,
            balanced_pole_position=balanced_position,
        )

    def attachment_elevations(
        self,
        solution: SystemSolution,
        clearance_ft: float,
        pavement_elevation_ft: float = 0.0,
    ) -> dict[str, float]:
        """Absolute pole attachment elevations so the lowest wire point sits
        exactly ``clearance_ft`` above the pavement."""
        shift = (
            pavement_elevation_ft + clearance_ft - solution.low_point_elevation_ft
        )
        return {
            pole: elevation + shift
            for pole, elevation in self.pole_attachment_elevations.items()
        }

    def load_elevations(self, solution: SystemSolution) -> list[dict]:
        """Wire elevation at every hung load — the legacy results window's
        "Height of Each Signal or Sign Attachment Point above the Lowest".

        Returns one record per load: segment, label, x_ft, elevation_ft,
        and height_above_lowest_ft (relative to the lowest attachment
        point among all loads, the legacy zero convention).
        """
        records = []
        by_name = {s.name: s for s in solution.segments}
        for seg in self.segments:
            if not seg.loads:
                continue
            res = by_name[seg.name]
            span = SimpleSpan(
                self.plan_length(seg),
                wire_weight_plf=seg.wire_weight_plf,
                start_elevation_ft=res.start_elevation_ft,
                end_elevation_ft=res.end_elevation_ft,
                loads=seg.loads,
            )
            for load in seg.loads:
                records.append({
                    "segment": seg.name,
                    "label": load.label,
                    "x_ft": load.x_ft,
                    "elevation_ft": span.wire_elevation(
                        load.x_ft, res.horizontal_tension_lb),
                })
        if records:
            lowest = min(r["elevation_ft"] for r in records)
            for r in records:
                r["height_above_lowest_ft"] = r["elevation_ft"] - lowest
        return records

    # -- convenience builders ---------------------------------------------

    @classmethod
    def wye(
        cls,
        leg_lengths: tuple[float, float, float],
        leg_bearings_deg: tuple[float, float, float],
        loads: dict[str, list[SpanLoad]] | None = None,
        wire_weight_plf: float = 0.0,
        pole_attachment_elevations: dict[str, float] | None = None,
        wire_weights: dict[str, float] | None = None,
    ) -> "SpanWireSystem":
        """Three poles on one bullring.  Segments are named ``P1R1``,
        ``P2R1``, ``P3R1`` (load positions measured from the pole); the
        default tension reference is the last segment, matching SWISS's
        span-3 normalization."""
        return cls._from_tails(
            {"R1": (0.0, 0.0)},
            [("R1", length, bearing) for length, bearing in
             zip(leg_lengths, leg_bearings_deg)],
            sides=[],
            loads=loads,
            wire_weight_plf=wire_weight_plf,
            pole_attachment_elevations=pole_attachment_elevations,
            wire_weights=wire_weights,
        )

    @classmethod
    def h(
        cls,
        ring_positions: tuple[tuple[float, float], tuple[float, float]],
        tail_lengths: tuple[float, float, float, float],
        tail_bearings_deg: tuple[float, float, float, float],
        loads: dict[str, list[SpanLoad]] | None = None,
        wire_weight_plf: float = 0.0,
        pole_attachment_elevations: dict[str, float] | None = None,
        wire_weights: dict[str, float] | None = None,
    ) -> "SpanWireSystem":
        """H configuration: two bullrings joined by a crossbar, two pole
        tails on each ring.  Tails ``P1R1``/``P2R1`` hang off R1 and
        ``P3R2``/``P4R2`` off R2; the crossbar is ``R1R2``.  Statically
        determinate — no balance pole."""
        rings = {f"R{i + 1}": pos for i, pos in enumerate(ring_positions)}
        if len(rings) != 2:
            raise ValueError("h needs exactly 2 ring positions")
        tail_rings = ("R1", "R1", "R2", "R2")
        return cls._from_tails(
            rings,
            [(ring, length, bearing) for ring, (length, bearing) in
             zip(tail_rings, zip(tail_lengths, tail_bearings_deg))],
            sides=[("R1", "R2")],
            loads=loads,
            wire_weight_plf=wire_weight_plf,
            pole_attachment_elevations=pole_attachment_elevations,
            wire_weights=wire_weights,
        )

    @classmethod
    def delta(
        cls,
        ring_positions: tuple[tuple[float, float], ...],
        tail_lengths: tuple[float, float, float],
        tail_bearings_deg: tuple[float, float, float],
        loads: dict[str, list[SpanLoad]] | None = None,
        wire_weight_plf: float = 0.0,
        pole_attachment_elevations: dict[str, float] | None = None,
        balance_pole: str = "P2",
        wire_weights: dict[str, float] | None = None,
    ) -> "SpanWireSystem":
        """Three bullrings in a triangle, one pole tail off each ring.
        Segments: tails ``P1R1``..``P3R3``, sides ``R1R2``, ``R2R3``,
        ``R3R1``."""
        rings = {f"R{i + 1}": pos for i, pos in enumerate(ring_positions)}
        if len(rings) != 3:
            raise ValueError("delta needs exactly 3 ring positions")
        return cls._from_tails(
            rings,
            [(f"R{i + 1}", length, bearing) for i, (length, bearing) in
             enumerate(zip(tail_lengths, tail_bearings_deg))],
            sides=[("R1", "R2"), ("R2", "R3"), ("R3", "R1")],
            loads=loads,
            wire_weight_plf=wire_weight_plf,
            pole_attachment_elevations=pole_attachment_elevations,
            balance_pole=balance_pole,
            wire_weights=wire_weights,
        )

    @classmethod
    def box(
        cls,
        ring_positions: tuple[tuple[float, float], ...],
        tail_lengths: tuple[float, float, float, float],
        tail_bearings_deg: tuple[float, float, float, float],
        loads: dict[str, list[SpanLoad]] | None = None,
        wire_weight_plf: float = 0.0,
        pole_attachment_elevations: dict[str, float] | None = None,
        balance_pole: str = "P2",
        wire_weights: dict[str, float] | None = None,
    ) -> "SpanWireSystem":
        """Four bullrings in a quadrilateral, one pole tail off each ring
        ("box with 4 tails").  Segments: tails ``P1R1``..``P4R4``, sides
        ``R1R2``, ``R2R3``, ``R3R4``, ``R4R1``."""
        rings = {f"R{i + 1}": pos for i, pos in enumerate(ring_positions)}
        if len(rings) != 4:
            raise ValueError("box needs exactly 4 ring positions")
        return cls._from_tails(
            rings,
            [(f"R{i + 1}", length, bearing) for i, (length, bearing) in
             enumerate(zip(tail_lengths, tail_bearings_deg))],
            sides=[("R1", "R2"), ("R2", "R3"), ("R3", "R4"), ("R4", "R1")],
            loads=loads,
            wire_weight_plf=wire_weight_plf,
            pole_attachment_elevations=pole_attachment_elevations,
            balance_pole=balance_pole,
            wire_weights=wire_weights,
        )

    @classmethod
    def _from_tails(
        cls,
        rings: dict[str, tuple[float, float]],
        tails: list[tuple[str, float, float]],
        sides: list[tuple[str, str]],
        loads: dict[str, list[SpanLoad]] | None,
        wire_weight_plf: float,
        pole_attachment_elevations: dict[str, float] | None,
        balance_pole: str | None = None,
        wire_weights: dict[str, float] | None = None,
    ) -> "SpanWireSystem":
        """``wire_weights`` overrides the uniform ``wire_weight_plf`` per
        segment name — the legacy "Enable Variable Wire Weight" feature."""
        loads = dict(loads or {})
        wire_weights = dict(wire_weights or {})
        poles = {}
        segments = []

        def wire_for(name: str) -> float:
            return float(wire_weights.pop(name, wire_weight_plf))

        for i, (ring, length, bearing) in enumerate(tails):
            if length <= 0:
                raise ValueError("tail lengths must be positive")
            pole = f"P{i + 1}"
            rx, ry = rings[ring]
            angle = math.radians(bearing)
            poles[pole] = (rx + length * math.cos(angle),
                           ry + length * math.sin(angle))
            name = f"{pole}{ring}"
            segments.append(
                SegmentDef(name, pole, ring, wire_for(name),
                           tuple(loads.pop(name, ())))
            )
        for a, b in sides:
            name = f"{a}{b}"
            segments.append(
                SegmentDef(name, a, b, wire_for(name),
                           tuple(loads.pop(name, ())))
            )
        if loads:
            raise ValueError(f"loads reference unknown segments: {sorted(loads)}")
        if wire_weights:
            raise ValueError(
                f"wire_weights reference unknown segments: {sorted(wire_weights)}")
        return cls(
            poles,
            rings,
            segments,
            pole_attachment_elevations=pole_attachment_elevations,
            balance_pole=balance_pole,
        )


__all__ = [
    "BALANCE_TOLERANCE_DEG",
    "SegmentDef",
    "SegmentResult",
    "SystemSolution",
    "SpanWireSystem",
]
