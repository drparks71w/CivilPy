#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Composite steel-girder transformed-section properties (AASHTO LRFD 6.10.1.1)
and the flange design stress ``fcf`` a bolted field splice needs (stage **B4**).

A steel plate/rolled girder acts on three sections through its life:

* **non-composite** (bare steel) carries the wet-slab dead load ``DC1``;
* **long-term composite** (deck transformed by ``3n`` for creep) carries the
  superimposed dead load ``DC2 + DW``;
* **short-term composite** (deck transformed by ``n``) carries live load.

Under *negative* moment the slab cracks, so the composite section is the steel
plus the longitudinal deck reinforcement only.  Summing each load case's stress
on its own section gives ``fcf`` -- the actual factored flange stress that
AASHTO 6.13.6.1.3b uses (via :func:`flange_design_stress_fcf`) to size the
splice, instead of the conservative full-yield fallback.

Geometry is measured in inches from the **bottom of the bottom flange**.  Deck
concrete is transferred by its modular ratio; areas in the flanges' bolt-hole
region can be deducted for the "with holes" section per 6.10.1.8.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from civilpy.structural.aashto.lrfd.bolted_field_splice import GirderSide, _grade


def modular_ratio(fc: float, e_s: float = 29000.0) -> float:
    """Steel/concrete modular ratio ``n = Es/Ec`` (AASHTO C6.10.1.1.1b), with
    ``Ec = 1820*sqrt(fc)`` ksi.  ``fc`` in ksi.  (fc = 4.0 -> n ~= 8.)"""
    e_c = 1820.0 * math.sqrt(fc)
    return e_s / e_c


@dataclass
class _Part:
    """One transformed rectangle/area: area ``a`` (in^2), centroid height ``y``
    (in), and own inertia ``i0`` about its own centroid (in^4)."""
    a: float
    y: float
    i0: float = 0.0


@dataclass
class SectionProps:
    """Transformed-section properties about the elastic neutral axis.

    ``area`` and ``inertia`` are transformed (steel) values; ``y_na`` is the
    neutral-axis height above the bottom of the bottom flange (in).
    """
    area: float
    inertia: float
    y_na: float

    def stress(self, moment_kft: float, y_fiber: float) -> float:
        """Bending stress (ksi) at height ``y_fiber`` for ``moment_kft`` (k-ft),
        tension positive at fibers below the neutral axis for a positive (sagging)
        moment.  ``sigma = M*c/I`` with ``c = y_na - y_fiber``."""
        c = self.y_na - y_fiber
        return moment_kft * 12.0 * c / self.inertia


def _section_props(parts: list[_Part]) -> SectionProps:
    area = sum(p.a for p in parts)
    y_na = sum(p.a * p.y for p in parts) / area
    # parallel-axis theorem: each part contributes its own inertia plus A*d^2
    inertia = sum(p.i0 + p.a * (p.y - y_na) ** 2 for p in parts)
    return SectionProps(area=area, inertia=inertia, y_na=y_na)


class CompositeGirder:
    """Transformed-section model of one girder side + its composite deck.

    Rectangular idealization of the steel (two flanges + web); the deck is a
    ``deck_weff x deck_t`` slab whose bottom sits a ``haunch`` above the top of
    the top flange.  Optional longitudinal reinforcement ``rebar_area`` sits
    ``rebar_cover`` below the top of the slab (for the cracked negative section).
    """

    def __init__(self, side: GirderSide, *, deck_t: float, deck_weff: float,
                 deck_fc: float = 4.0, n: float | None = None,
                 rebar_area: float = 0.0, rebar_cover: float = 2.5,
                 hole_area_per_flange: float = 0.0):
        self.side = side
        self.deck_t = deck_t
        self.deck_weff = deck_weff
        self.n = n if n is not None else modular_ratio(deck_fc)
        self.rebar_area = rebar_area
        self.rebar_cover = rebar_cover
        self.hole_area = hole_area_per_flange

        tf_b = side.bottom_flange.thickness
        tf_t = side.top_flange.thickness
        bf_b = side.bottom_flange.width
        bf_t = side.top_flange.width
        dw = side.web_depth
        self.d = tf_b + dw + tf_t                       # steel depth
        # steel part centroids (y from bottom of bottom flange)
        self._y_bf_mid = tf_b / 2.0
        self._y_tf_mid = tf_b + dw + tf_t / 2.0
        i0_bf = bf_b * tf_b ** 3 / 12.0
        i0_web = side.web_thickness * dw ** 3 / 12.0
        i0_tf = bf_t * tf_t ** 3 / 12.0
        self._steel = [
            _Part(bf_b * tf_b, self._y_bf_mid, i0_bf),
            _Part(side.web_thickness * dw, tf_b + dw / 2.0, i0_web),
            _Part(bf_t * tf_t, self._y_tf_mid, i0_tf),
        ]
        # holes reduce both flanges (net section, 6.10.1.8)
        self._steel_holes = [
            _Part(bf_b * tf_b - hole_area_per_flange, self._y_bf_mid, i0_bf),
            _Part(side.web_thickness * dw, tf_b + dw / 2.0, i0_web),
            _Part(bf_t * tf_t - hole_area_per_flange, self._y_tf_mid, i0_tf),
        ]
        # deck + rebar geometry
        self._y_deck_mid = self.d + side.haunch + deck_t / 2.0
        self._y_rebar = self.d + side.haunch + deck_t - rebar_cover

    # fiber heights the splice cares about (flange mid-thickness)
    @property
    def y_bottom_flange(self) -> float:
        return self._y_bf_mid

    @property
    def y_top_flange(self) -> float:
        return self._y_tf_mid

    def props(self, state: str, *, holes: bool = False) -> SectionProps:
        """Transformed properties for ``state`` in
        ``{"steel", "n", "3n", "negative"}``.  ``"steel"`` is the bare girder;
        ``"n"``/``"3n"`` add the deck transformed by 1/n and 1/(3n) (positive
        moment); ``"negative"`` is the cracked section (steel + rebar)."""
        parts = list(self._steel_holes if holes else self._steel)
        if state == "steel":
            pass
        elif state in ("n", "3n"):
            ratio = self.n if state == "n" else 3.0 * self.n
            parts.append(_Part(
                self.deck_weff * self.deck_t / ratio, self._y_deck_mid,
                self.deck_weff * self.deck_t ** 3 / 12.0 / ratio))
        elif state == "negative":
            if self.rebar_area:
                parts.append(_Part(self.rebar_area, self._y_rebar))
        else:
            raise ValueError(f"unknown section state {state!r}")
        return _section_props(parts)

    def flange_stress(self, flange: str, moments: dict, *,
                      holes: bool = False) -> float:
        """Factored flange stress ``fcf`` (ksi) at the given flange
        (``"top"``/``"bottom"``) mid-thickness, summing each load case on its
        own section: ``DC1`` on bare steel, ``DC2``/``DW`` on the long-term
        (3n) composite, and live load on the short-term (n) composite (or the
        cracked ``negative`` section for the negative live-load case).

        ``moments`` supplies factored case moments (k-ft): ``dc1``, ``dc2``,
        ``dw``, and one of ``ll_pos`` / ``ll_neg``.  Tension is positive.
        """
        y = self.y_bottom_flange if flange == "bottom" else self.y_top_flange
        steel = self.props("steel", holes=holes)
        long_term = self.props("3n", holes=holes)
        s = 0.0
        s += steel.stress(moments.get("dc1", 0.0), y)
        s += long_term.stress(moments.get("dc2", 0.0) + moments.get("dw", 0.0), y)
        if "ll_neg" in moments:
            neg = self.props("negative", holes=holes)
            s += neg.stress(moments["ll_neg"], y)
        if "ll_pos" in moments:
            short_term = self.props("n", holes=holes)
            s += short_term.stress(moments["ll_pos"], y)
        return s
