"""Mohr's circle for plane stress: principal stresses, maximum shear, and
the classic circle diagram with the rotated-element companion sketch.

Follows the same conventions as :mod:`civilpy.structural.beam_bending`:
plot methods accept an optional ``ax`` (a new figure is created when
omitted) and return the matplotlib figure so they drop straight into
Jupyter notebooks.  Stresses are sign-convention standard: tension
positive, and a positive ``tau_xy`` acts upward on the right (+x) face.
The shear axis is drawn positive-down so clockwise rotation of the
physical element matches counterclockwise travel around the circle, the
way it's taught.

Examples
--------
>>> mc = MohrsCircle(sigma_x=80, sigma_y=20, tau_xy=30)
>>> round(mc.sigma_1, 2), round(mc.sigma_2, 2)
(92.43, 7.57)
>>> round(mc.tau_max, 2)
42.43
>>> round(mc.theta_p_deg, 2)
22.5
>>> sx, sy, txy = mc.stresses_at(22.5)
>>> round(sx, 2), round(txy, 6)
(92.43, 0.0)
"""

#  CivilPy
#  Copyright (C) 2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import math

import matplotlib.pyplot as plt
import numpy as np


class MohrsCircle:
    """Plane-stress state and its Mohr's circle.

    Parameters are the normal stresses on the x and y faces and the shear
    ``tau_xy``, in any consistent stress unit (the unit label used on the
    plots can be set with ``units``).
    """

    def __init__(self, sigma_x: float, sigma_y: float, tau_xy: float,
                 units: str = "ksi"):
        self.sigma_x = sigma_x
        self.sigma_y = sigma_y
        self.tau_xy = tau_xy
        self.units = units

    # ── Derived quantities ────────────────────────────────────────────────

    @property
    def center(self) -> float:
        """Average normal stress (circle center)."""
        return (self.sigma_x + self.sigma_y) / 2.0

    @property
    def radius(self) -> float:
        return math.hypot((self.sigma_x - self.sigma_y) / 2.0, self.tau_xy)

    @property
    def sigma_1(self) -> float:
        """Major principal stress."""
        return self.center + self.radius

    @property
    def sigma_2(self) -> float:
        """Minor principal stress."""
        return self.center - self.radius

    @property
    def tau_max(self) -> float:
        """Maximum in-plane shear stress (= circle radius)."""
        return self.radius

    @property
    def theta_p_deg(self) -> float:
        """Angle from the x-axis to the major principal plane's normal
        (degrees, counterclockwise positive)."""
        return math.degrees(
            math.atan2(2.0 * self.tau_xy, self.sigma_x - self.sigma_y)
        ) / 2.0

    @property
    def theta_s_deg(self) -> float:
        """Angle to the maximum-shear orientation (45 deg from principal)."""
        return self.theta_p_deg - 45.0

    @property
    def tau_abs_max(self) -> float:
        """Absolute maximum shear including the out-of-plane circles
        (plane stress, sigma_3 = 0)."""
        return max(abs(self.sigma_1), abs(self.sigma_2),
                   abs(self.sigma_1 - self.sigma_2)) / 2.0

    def stresses_at(self, theta_deg: float) -> tuple[float, float, float]:
        """Stress components on an element rotated ``theta_deg``
        counterclockwise: (sigma_x', sigma_y', tau_x'y')."""
        two_t = math.radians(2.0 * theta_deg)
        half_diff = (self.sigma_x - self.sigma_y) / 2.0
        sx = (self.center + half_diff * math.cos(two_t)
              + self.tau_xy * math.sin(two_t))
        sy = (self.center - half_diff * math.cos(two_t)
              - self.tau_xy * math.sin(two_t))
        txy = -half_diff * math.sin(two_t) + self.tau_xy * math.cos(two_t)
        return sx, sy, txy

    # ── Plotting ──────────────────────────────────────────────────────────

    def plot(self, ax=None, show_out_of_plane: bool = False,
             theta_deg: float | None = None):
        """Draw the Mohr's circle with the X/Y stress points, principal
        stresses, and maximum shear labeled.

        ``show_out_of_plane`` adds the two sigma_3 = 0 circles governing
        the absolute maximum shear; ``theta_deg`` marks the stress point
        for an element rotated by that angle.  Returns the figure.
        """
        if ax is None:
            ax = plt.figure(figsize=(7, 7)).add_subplot(1, 1, 1)

        angles = np.linspace(0.0, 2.0 * np.pi, 361)
        ax.plot(self.center + self.radius * np.cos(angles),
                self.radius * np.sin(angles), color="b", lw=1.8)

        # X and Y face points and the diameter between them
        ax.plot([self.sigma_x, self.sigma_y], [self.tau_xy, -self.tau_xy],
                "k--", lw=0.8)
        ax.plot(self.sigma_x, self.tau_xy, "ko")
        ax.annotate(f"X ({self.sigma_x:.4g}, {self.tau_xy:.4g})",
                    (self.sigma_x, self.tau_xy),
                    textcoords="offset points", xytext=(8, 6))
        ax.plot(self.sigma_y, -self.tau_xy, "ko")
        ax.annotate(f"Y ({self.sigma_y:.4g}, {-self.tau_xy:.4g})",
                    (self.sigma_y, -self.tau_xy),
                    textcoords="offset points", xytext=(8, -12))

        # principal stresses and max shear
        for sig, name in ((self.sigma_1, r"$\sigma_1$"),
                          (self.sigma_2, r"$\sigma_2$")):
            ax.plot(sig, 0.0, "rs")
            ax.annotate(f"{name} = {sig:.4g}", (sig, 0.0),
                        textcoords="offset points", xytext=(6, 10),
                        color="r")
        ax.plot([self.center, self.center],
                [-self.radius, self.radius], "g:", lw=0.8)
        ax.annotate(rf"$\tau_{{max}}$ = {self.tau_max:.4g}",
                    (self.center, self.radius),
                    textcoords="offset points", xytext=(6, 6), color="g")

        if show_out_of_plane:
            for a, b in ((self.sigma_1, 0.0), (self.sigma_2, 0.0)):
                c, r = (a + b) / 2.0, abs(a - b) / 2.0
                ax.plot(c + r * np.cos(angles), r * np.sin(angles),
                        color="0.6", lw=1.0, ls="--")

        if theta_deg is not None:
            sx, _, txy = self.stresses_at(theta_deg)
            ax.plot(sx, txy, "m^", markersize=9)
            ax.annotate(rf"$\theta$ = {theta_deg:g}°", (sx, txy),
                        textcoords="offset points", xytext=(8, 0),
                        color="m")

        ax.axhline(0.0, color="k", lw=0.8)
        ax.axvline(0.0, color="k", lw=0.8)
        ax.set_xlabel(rf"$\sigma$ ({self.units})")
        ax.set_ylabel(rf"$\tau$ ({self.units})")
        ax.invert_yaxis()  # shear positive-down, textbook convention
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title("Mohr's Circle — Plane Stress")
        ax.grid(True, alpha=0.3)
        return ax.get_figure()

    def plot_element(self, theta_deg: float = 0.0, ax=None):
        """Sketch the square stress element rotated ``theta_deg`` with its
        normal- and shear-stress arrows labeled.  Returns the figure."""
        if ax is None:
            ax = plt.figure(figsize=(5, 5)).add_subplot(1, 1, 1)
        sx, sy, txy = self.stresses_at(theta_deg)
        t = math.radians(theta_deg)
        rot = np.array([[math.cos(t), -math.sin(t)],
                        [math.sin(t), math.cos(t)]])

        half = 1.0
        corners = np.array([[-half, -half], [half, -half],
                            [half, half], [-half, half], [-half, -half]])
        pts = corners @ rot.T
        ax.plot(pts[:, 0], pts[:, 1], "k-", lw=1.5)

        def arrow(face_center, direction, label, color):
            fc = rot @ np.asarray(face_center)
            d = rot @ np.asarray(direction)
            ax.annotate("", xy=fc + d, xytext=fc,
                        arrowprops=dict(arrowstyle="-|>", color=color))
            ax.annotate(label, fc + d * 1.25, ha="center", color=color)

        # normal stresses (arrows point outward for tension)
        s_scale = 0.8
        for sign in (1.0, -1.0):
            d = s_scale * math.copysign(1.0, sx) * sign
            arrow((sign * half, 0.0), (d, 0.0),
                  rf"$\sigma_{{x'}}$={sx:.4g}" if sign > 0 else "", "b")
            d = s_scale * math.copysign(1.0, sy) * sign
            arrow((0.0, sign * half), (0.0, d),
                  rf"$\sigma_{{y'}}$={sy:.4g}" if sign > 0 else "", "r")
        # shear couple
        tdir = math.copysign(0.7, txy)
        arrow((half * 1.15, 0.0), (0.0, tdir),
              rf"$\tau$={txy:.4g}", "g")
        arrow((-half * 1.15, 0.0), (0.0, -tdir), "", "g")

        ax.set_aspect("equal")
        ax.set_xlim(-3, 3)
        ax.set_ylim(-3, 3)
        ax.axis("off")
        ax.set_title(rf"Stress element at $\theta$ = {theta_deg:g}°")
        return ax.get_figure()
