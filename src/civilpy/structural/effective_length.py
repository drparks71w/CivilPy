"""Column effective-length factors: the alignment-chart (nomograph)
equations solved exactly, so no more reading K off a fuzzy chart.

``g_a``/``g_b`` are the joint stiffness ratios sum(EI/L columns) /
sum(EI/L girders); use 10 for a pinned base and 1.0 for a fixed base
(the recommended practical values).

Examples
--------
>>> round(k_factor(1.0, 1.0, sway=False), 2)
0.77
>>> round(k_factor(1.0, 1.0, sway=True), 2)
1.32
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see other modules for the full notice)

import math


def _braced_residual(k, g_a, g_b):
    p = math.pi / k
    return (g_a * g_b / 4.0 * p**2 + (g_a + g_b) / 2.0
            * (1.0 - p / math.tan(p)) + 2.0 * math.tan(p / 2.0) / p - 1.0)


def _sway_residual(k, g_a, g_b):
    p = math.pi / k
    return (g_a * g_b * p**2 - 36.0) / (6.0 * (g_a + g_b)) - p / math.tan(p)


def k_factor(g_a: float, g_b: float, sway: bool = False,
             tol: float = 1e-9) -> float:
    """Effective length factor K from the alignment-chart transcendental
    equations — sidesway-inhibited (0.5 <= K <= 1.0) or sidesway-permitted
    (K >= 1.0) — solved by bisection."""
    residual = _sway_residual if sway else _braced_residual
    lo, hi = (1.0 + 1e-9, 50.0) if sway else (0.5 + 1e-9, 1.0 - 1e-12)
    r_lo = residual(lo, g_a, g_b)
    for _ in range(300):
        mid = (lo + hi) / 2.0
        r_mid = residual(mid, g_a, g_b)
        if (r_lo < 0.0) == (r_mid < 0.0):
            lo, r_lo = mid, r_mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2.0
