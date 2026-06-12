"""Open-channel flow for rectangular channels: critical/normal depth,
Froude number, and the specific-energy curve with alternate depths —
the diagram from every hydraulics course.

US units: ft, cfs; Manning with the 1.486 conversion.

Examples
--------
>>> ch = RectangularChannel(width=10, n=0.013, slope=0.002)
>>> round(ch.critical_depth(q=200), 3)
2.316
>>> yn = ch.normal_depth(q=200)
>>> ch.froude(q=200, y=yn) < 1.0   # mild slope -> subcritical
True
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see other modules for the full notice)

import math

import matplotlib.pyplot as plt
import numpy as np

G = 32.2  # ft/s^2


class RectangularChannel:
    def __init__(self, width: float, n: float = 0.013,
                 slope: float = 0.001):
        self.b = width
        self.n = n
        self.s = slope

    def critical_depth(self, q: float) -> float:
        """yc = (q_unit^2/g)^(1/3) for discharge ``q`` (cfs)."""
        q_unit = q / self.b
        return (q_unit**2 / G) ** (1.0 / 3.0)

    def manning_q(self, y: float) -> float:
        """Discharge at depth ``y`` by Manning's equation (cfs)."""
        a = self.b * y
        r = a / (self.b + 2.0 * y)
        return 1.486 / self.n * a * r ** (2.0 / 3.0) * math.sqrt(self.s)

    def normal_depth(self, q: float, tol: float = 1e-8) -> float:
        """Solve Manning for the uniform-flow depth by bisection."""
        lo, hi = tol, 1.0
        while self.manning_q(hi) < q:
            hi *= 2.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if self.manning_q(mid) < q:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return (lo + hi) / 2.0

    def specific_energy(self, q: float, y: float) -> float:
        """E = y + v^2/2g (ft)."""
        v = q / (self.b * y)
        return y + v**2 / (2.0 * G)

    def froude(self, q: float, y: float) -> float:
        v = q / (self.b * y)
        return v / math.sqrt(G * y)

    def friction_slope(self, q: float, y: float) -> float:
        """Sf from Manning's equation at depth ``y`` — the slope that
        would make ``y`` the normal depth for ``q``."""
        a = self.b * y
        r = a / (self.b + 2.0 * y)
        return (q * self.n / (1.486 * a * r ** (2.0 / 3.0))) ** 2

    def classify_profile(self, q: float, y: float) -> str:
        """Gradually-varied-flow profile class (M1, M2, S3, ...) for a
        flow depth ``y``: slope letter from normal vs. critical depth,
        zone number from where ``y`` sits relative to both."""
        yc = self.critical_depth(q)
        if self.s <= 0.0:
            letter, yn = ("H" if self.s == 0.0 else "A"), math.inf
        else:
            yn = self.normal_depth(q)
            if abs(yn - yc) / yc < 1e-3:
                letter = "C"
            elif yn > yc:
                letter = "M"
            else:
                letter = "S"
        upper, lower = max(yn, yc), min(yn, yc)
        if y > upper:
            zone = 1
        elif y > lower:
            zone = 2
        else:
            zone = 3
        if letter in ("H", "A") and zone == 1:
            zone = 2        # no zone 1 without a normal depth
        return f"{letter}{zone}"

    def gvf_profile(self, q: float, y_control: float, length: float,
                    n_steps: int = 400, upstream: bool | None = None):
        """Gradually-varied water-surface profile from a control depth,
        integrating dy/dx = (S0 - Sf)/(1 - Fr^2) with RK4.

        ``y_control`` is the known depth (e.g. pool elevation behind a
        dam for M1, the brink for M2); integration marches ``length`` ft
        upstream for subcritical controls and downstream for
        supercritical (override with ``upstream``).  Returns ``(x, y)``
        arrays with x positive downstream of the control (so an
        upstream march has negative stations) — integration stops early
        if the depth reaches critical, where GVF theory breaks down.
        """
        if upstream is None:
            upstream = self.froude(q, y_control) < 1.0
        yc = self.critical_depth(q)
        dx = length / n_steps * (-1.0 if upstream else 1.0)

        def dydx(y):
            fr2 = self.froude(q, y) ** 2
            return (self.s - self.friction_slope(q, y)) / (1.0 - fr2)

        xs, ys = [0.0], [float(y_control)]
        for _ in range(n_steps):
            y0 = ys[-1]
            k1 = dydx(y0)
            k2 = dydx(y0 + dx / 2.0 * k1)
            k3 = dydx(y0 + dx / 2.0 * k2)
            k4 = dydx(y0 + dx * k3)
            y1 = y0 + dx / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
            if y1 <= 0 or abs(y1 - yc) / yc < 5e-3:
                break
            xs.append(xs[-1] + dx)
            ys.append(y1)
        return np.array(xs), np.array(ys)

    def plot_gvf_profile(self, q: float, y_control: float, length: float,
                         ax=None, n_steps: int = 400,
                         upstream: bool | None = None):
        """Water-surface profile sketch: channel bottom on its slope,
        the GVF surface, normal and critical depth lines, the energy
        grade line, and the profile classification (M1, S2, ...).
        Returns the figure."""
        x, y = self.gvf_profile(q, y_control, length, n_steps, upstream)
        if ax is None:
            ax = plt.figure(figsize=(9, 5)).add_subplot(1, 1, 1)
        z_bot = -self.s * x
        ws = z_bot + y
        v = q / (self.b * y)
        egl = ws + v**2 / (2.0 * G)
        ax.plot(x, z_bot, "k-", lw=2.0, label="channel bottom")
        ax.plot(x, ws, "b-", lw=1.8, label="water surface")
        ax.plot(x, egl, "r--", lw=1.2, label="EGL")
        yc = self.critical_depth(q)
        ax.plot(x, z_bot + yc, "g:", lw=1.2, label=f"$y_c$ = {yc:.2f} ft")
        if self.s > 0:
            yn = self.normal_depth(q)
            ax.plot(x, z_bot + yn, "m-.", lw=1.2,
                    label=f"$y_n$ = {yn:.2f} ft")
        ax.fill_between(x, z_bot, ws, color="b", alpha=0.12)
        label = self.classify_profile(q, y_control)
        ax.set_title(f"GVF Profile — {label}, q = {q:g} cfs, "
                     f"S$_0$ = {self.s:g}")
        ax.set_xlabel("Station (ft, + downstream of control)")
        ax.set_ylabel("Elevation (ft)")
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, alpha=0.3)
        return ax.get_figure()

    def alternate_depths(self, q: float, energy: float,
                         tol: float = 1e-8) -> tuple[float, float]:
        """The sub- and supercritical depths sharing the given specific
        energy (raises if E is below the critical minimum)."""
        yc = self.critical_depth(q)
        e_min = self.specific_energy(q, yc)
        if energy < e_min:
            raise ValueError(f"E = {energy:g} ft < Emin = {e_min:.4g} ft")

        def solve(lo, hi):
            for _ in range(200):
                mid = (lo + hi) / 2.0
                if self.specific_energy(q, mid) > energy:
                    # branch direction differs above/below critical
                    if mid < yc:
                        lo = mid
                    else:
                        hi = mid
                else:
                    if mid < yc:
                        hi = mid
                    else:
                        lo = mid
                if hi - lo < tol:
                    break
            return (lo + hi) / 2.0

        return solve(tol, yc), solve(yc, energy * 1.5)

    def plot_specific_energy(self, q: float, ax=None,
                             energy: float | None = None,
                             y_max: float | None = None):
        """The E-y curve with the critical point marked and, optionally,
        the alternate depths for a given energy."""
        if ax is None:
            ax = plt.figure(figsize=(6.5, 6)).add_subplot(1, 1, 1)
        yc = self.critical_depth(q)
        top = y_max or 4.0 * yc
        ys = np.linspace(0.05 * yc, top, 400)
        es = [self.specific_energy(q, y) for y in ys]
        ax.plot(es, ys, "b", lw=1.6)
        ax.plot(es, es, "k:", lw=0.8)  # E = y asymptote
        e_c = self.specific_energy(q, yc)
        ax.plot(e_c, yc, "rs")
        ax.annotate(rf"critical ($y_c$={yc:.3g} ft)", (e_c, yc),
                    textcoords="offset points", xytext=(8, -4), color="r")
        if energy is not None:
            y1, y2 = self.alternate_depths(q, energy)
            ax.axvline(energy, color="g", ls="--", lw=0.9)
            for y_alt in (y1, y2):
                ax.plot(energy, y_alt, "g^")
                ax.annotate(f"{y_alt:.3g} ft", (energy, y_alt),
                            textcoords="offset points", xytext=(6, 0),
                            color="g")
        ax.set_xlabel("Specific energy E (ft)")
        ax.set_ylabel("Depth y (ft)")
        ax.set_title(f"Specific Energy — q = {q:g} cfs, b = {self.b:g} ft")
        ax.grid(True, alpha=0.3)
        return ax.get_figure()
