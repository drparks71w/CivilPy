#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Quick-look figures for a :class:`~civilpy.scan.pipeline.ScanFeatures`.

Two views are enough to judge an extraction: the **elevation** along the
bridge axis (ground, deck line, superstructure band, substructure boxes,
span lengths) and the **plan** (deck outline, unit footprints, axis).
Both draw on ``matplotlib`` axes so they drop into a notebook or a report
figure; call :func:`save_overview` for a two-panel PNG.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from civilpy.scan.preprocess import to_axis_frame


def _sample(n: int, k: int, seed: int = 0) -> np.ndarray:
    if n <= k:
        return np.arange(n)
    return np.random.default_rng(seed).choice(n, k, replace=False)


def plot_elevation(res, ax=None, max_points: int = 400_000, point_size: float = 0.2):
    """Elevation view along the bridge axis: points coloured ground /
    structure, the deck line, the superstructure underside, unit boxes
    and span-length labels.  Returns the axes."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(16, 6))
    xyz = res.cloud.xyz
    sot = to_axis_frame(xyz, res.axis_origin, res.axis_direction)
    idx = _sample(len(xyz), max_points)
    g = res.ground[idx]
    ax.scatter(sot[idx][~g, 0], sot[idx][~g, 2], s=point_size, c="0.25", label="structure")
    ax.scatter(sot[idx][g, 0], sot[idx][g, 2], s=point_size, c="peru", label="ground")
    deck = res.deck
    if deck is not None:
        s_rng = (deck.corners[:, :2] - res.axis_origin) @ res.axis_direction
        ax.plot([s_rng.min(), s_rng.max()], [deck.elevation] * 2, c="tab:blue", lw=2.5, label="deck")
        if res.superstructure_depth is not None:
            z = deck.elevation - res.superstructure_depth
            ax.plot([s_rng.min(), s_rng.max()], [z, z], c="tab:blue", lw=1, ls="--",
                    label=f"superstructure underside (D={res.superstructure_depth:.1f} ft)")
    for u in res.units:
        s0, s1 = u.station_range
        colour = "tab:red" if u.role == "pier" else "tab:orange"
        ax.add_patch(plt.Rectangle((s0, u.z_bottom), s1 - s0, u.height, fill=False, ec=colour, lw=2))
        ax.annotate(f"{u.name}\n{u.height:.0f} ft", (0.5 * (s0 + s1), u.z_bottom - 1), ha="center",
                    va="top", fontsize=8, color=colour)
    if res.spans and deck is not None:
        y = deck.elevation + 4
        for sp in res.spans:
            ax.annotate("", (sp["start_station"], y), (sp["end_station"], y),
                        arrowprops=dict(arrowstyle="<->", color="tab:green"))
            label = f"{sp['length']:.1f} ft"
            if sp.get("min_clearance") is not None:
                label += f"\ncl. {sp['min_clearance']:.1f}"
            ax.annotate(label, (0.5 * (sp["start_station"] + sp["end_station"]), y + 1),
                        ha="center", va="bottom", fontsize=8, color="tab:green")
    ax.set_aspect("equal")
    ax.set_xlabel("station along bridge axis (ft)")
    ax.set_ylabel("elevation (local ft)")
    ax.legend(loc="lower left", fontsize=8, markerscale=20)
    return ax


def plot_plan(res, ax=None, max_points: int = 400_000, point_size: float = 0.2):
    """Plan view: points coloured by elevation, deck outline, plane
    footprints by role, unit footprints, the bridge axis.  Returns the axes."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 12))
    xyz = res.cloud.xyz
    idx = _sample(len(xyz), max_points)
    sc = ax.scatter(xyz[idx, 0], xyz[idx, 1], c=xyz[idx, 2], s=point_size, cmap="viridis")
    plt.colorbar(sc, ax=ax, label="elevation (local ft)", shrink=0.6)
    for p in res.planes:
        loop = p.boundary if p.boundary is not None else p.corners
        loop = np.vstack([loop, loop[:1]])
        colour = {"deck": "tab:blue", "soffit": "tab:cyan", "abutment": "tab:red",
                  "wingwall": "tab:orange", "barrier": "tab:purple", "truss": "tab:green",
                  "pier_face": "tab:red"}.get(p.role, "0.5")
        ax.plot(loop[:, 0], loop[:, 1], c=colour, lw=1.5 if p.role == "deck" else 0.8)
    for u in res.units:
        c = np.vstack([u.corners[:4], u.corners[:1]])
        ax.plot(c[:, 0], c[:, 1], c="tab:red" if u.role == "pier" else "tab:orange", lw=2)
        ax.annotate(u.name, u.corners[:4, :2].mean(axis=0), fontsize=7, ha="center")
    for c in res.cylinders:
        ax.add_patch(plt.Circle(c.center[:2], c.radius, fill=False, ec="tab:red", lw=1.5))
    o, d = res.axis_origin, res.axis_direction
    L = 0.5 * np.ptp(xyz[:, :2] @ d) if len(xyz) else 10.0
    ax.plot([o[0] - L * d[0], o[0] + L * d[0]], [o[1] - L * d[1], o[1] + L * d[1]],
            c="k", lw=0.5, ls=":")
    ax.set_aspect("equal")
    ax.set_xlabel("x (local ft)")
    ax.set_ylabel("y (local ft)")
    return ax


def save_overview(res, path, dpi: int = 90, title: Optional[str] = None) -> Path:
    """Two-panel PNG (plan over elevation)."""
    import matplotlib.pyplot as plt

    fig, (a0, a1) = plt.subplots(2, 1, figsize=(16, 16),
                                 gridspec_kw={"height_ratios": [2, 1]})
    plot_plan(res, ax=a0)
    plot_elevation(res, ax=a1)
    fig.suptitle(title or (res.cloud.source or "scan"))
    fig.tight_layout()
    path = Path(path)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


__all__ = ["plot_elevation", "plot_plan", "save_overview"]
