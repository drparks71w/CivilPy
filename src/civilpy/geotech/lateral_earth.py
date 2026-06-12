"""Rankine and Coulomb lateral earth pressure with the classic pressure-
diagram plot — companions to the Culmann graphical method already in
:mod:`civilpy.geotech.culmanns`.

Units: ft, pcf inputs; pressures plotted in psf.

Examples
--------
>>> round(rankine_ka(30), 4)
0.3333
>>> round(rankine_kp(30), 1)
3.0
>>> wall = LateralEarthPressure(height=12, gamma=120, phi=30)
>>> round(wall.resultant, 0)   # 0.5*Ka*gamma*H^2 = 2880 lb/ft
2880.0
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see other modules for the full notice)

import math

import matplotlib.pyplot as plt
import numpy as np

GAMMA_WATER = 62.4  # pcf


def rankine_ka(phi_deg: float, beta_deg: float = 0.0) -> float:
    """Rankine active coefficient; ``beta_deg`` is the backfill slope.
    With a level backfill this is the familiar (1-sin)/(1+sin)."""
    phi, beta = math.radians(phi_deg), math.radians(beta_deg)
    if beta == 0.0:
        return (1.0 - math.sin(phi)) / (1.0 + math.sin(phi))
    cb, root = math.cos(beta), math.sqrt(
        math.cos(beta) ** 2 - math.cos(phi) ** 2
    )
    return cb * (cb - root) / (cb + root)


def rankine_kp(phi_deg: float, beta_deg: float = 0.0) -> float:
    """Rankine passive coefficient."""
    phi, beta = math.radians(phi_deg), math.radians(beta_deg)
    if beta == 0.0:
        return (1.0 + math.sin(phi)) / (1.0 - math.sin(phi))
    cb, root = math.cos(beta), math.sqrt(
        math.cos(beta) ** 2 - math.cos(phi) ** 2
    )
    return cb * (cb + root) / (cb - root)


def coulomb_ka(phi_deg: float, delta_deg: float = 0.0,
               beta_deg: float = 0.0, theta_deg: float = 0.0) -> float:
    """Coulomb active coefficient: wall friction ``delta``, backfill slope
    ``beta``, wall back-face batter ``theta`` from vertical."""
    phi, delta = math.radians(phi_deg), math.radians(delta_deg)
    beta, theta = math.radians(beta_deg), math.radians(theta_deg)
    num = math.cos(phi - theta) ** 2
    den = (
        math.cos(theta) ** 2 * math.cos(delta + theta)
        * (1.0 + math.sqrt(
            math.sin(phi + delta) * math.sin(phi - beta)
            / (math.cos(delta + theta) * math.cos(beta - theta))
        )) ** 2
    )
    return num / den


class LateralEarthPressure:
    """Active (or passive) pressure diagram on a wall of ``height`` ft
    retaining soil of unit weight ``gamma`` pcf and friction angle
    ``phi`` deg, with optional uniform surcharge (psf) and water table
    depth (ft below the top)."""

    def __init__(self, height: float, gamma: float, phi: float,
                 surcharge: float = 0.0, water_depth: float | None = None,
                 k: float | None = None, passive: bool = False):
        self.height = height
        self.gamma = gamma
        self.surcharge = surcharge
        self.water_depth = water_depth
        if k is not None:
            self.k = k
        else:
            self.k = rankine_kp(phi) if passive else rankine_ka(phi)

    def pressure_at(self, z: float) -> float:
        """Total lateral pressure (psf) at depth ``z`` ft: soil (buoyant
        below the water table) plus full water plus surcharge."""
        if self.water_depth is None or z <= self.water_depth:
            sigma_v = self.gamma * z
            u = 0.0
        else:
            zw = z - self.water_depth
            sigma_v = (self.gamma * self.water_depth
                       + (self.gamma - GAMMA_WATER) * zw)
            u = GAMMA_WATER * zw
        return self.k * (sigma_v + self.surcharge) + u

    @property
    def resultant(self) -> float:
        """Total thrust per ft of wall (lb/ft), by numeric integration."""
        z = np.linspace(0.0, self.height, 2001)
        p = np.array([self.pressure_at(zi) for zi in z])
        return float(np.trapezoid(p, z))

    @property
    def resultant_height(self) -> float:
        """Height of the thrust above the wall base (ft)."""
        z = np.linspace(0.0, self.height, 2001)
        p = np.array([self.pressure_at(zi) for zi in z])
        z_bar = float(np.trapezoid(p * z, z) / np.trapezoid(p, z))
        return self.height - z_bar

    def plot(self, ax=None):
        """Pressure-diagram plot: wall on the left, pressure wedge
        growing with depth, resultant arrow at its centroid."""
        if ax is None:
            ax = plt.figure(figsize=(6, 6)).add_subplot(1, 1, 1)
        z = np.linspace(0.0, self.height, 400)
        p = np.array([self.pressure_at(zi) for zi in z])
        ax.plot(p, -z, "b", lw=1.6)
        ax.fill_betweenx(-z, p, 0.0, color="b", alpha=0.15)
        ax.axvline(0.0, color="k", lw=3)  # the wall
        if self.water_depth is not None and self.water_depth < self.height:
            ax.axhline(-self.water_depth, color="c", ls="--", lw=1.0)
            ax.annotate("water table", (p.max() * 0.55, -self.water_depth),
                        color="c", fontsize=9,
                        textcoords="offset points", xytext=(0, 3))
        y_r = -(self.height - self.resultant_height)
        ax.annotate(
            f"P = {self.resultant:,.0f} lb/ft\n"
            f"@ {self.resultant_height:.2f} ft above base",
            (self.pressure_at(self.height - self.resultant_height), y_r),
            textcoords="offset points", xytext=(10, 0), color="r")
        ax.plot(self.pressure_at(self.height - self.resultant_height),
                y_r, "r<", markersize=10)
        ax.set_xlabel("Lateral pressure (psf)")
        ax.set_ylabel("Depth (ft)")
        ax.set_title("Lateral Earth Pressure Diagram")
        ax.grid(True, alpha=0.3)
        return ax.get_figure()
