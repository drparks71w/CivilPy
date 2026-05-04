"""Beam analysis module for shear force, bending moment, and deflection diagrams.

Sign conventions follow AISC Steel Construction Manual (Table 3-23):
  - Loads: positive = downward (gravity direction)
  - Shear V: positive = left portion of beam has upward resultant (left-face-up)
  - Moment M: positive = sagging (concave up, bottom-fiber tension)
  - Reactions: positive = upward
  - Deflection: negative = downward (shown below zero line)

All units are US customary: lengths in feet (ft), forces in kips, moments in kip·ft.
Deflection calculations require E in ksi and I in in⁴; results are in inches.

Overhanging beams (AISC Table 3-23 Cases 24–28) are fully supported.  The pinned
and rolling supports may be placed anywhere within the beam span — they do not need
to coincide with the beam ends.  When a support is interior, the beam simply
overhangs that support on one or both sides.

Examples
--------
Simply supported beam (supports at ends):

>>> my_beam = Beam(9)
>>> my_beam.pinned_support = 0
>>> my_beam.rolling_support = 9
>>> my_beam.add_loads([PointLoadV(20, 4.5)])
>>> F_Ax, F_Ay, F_By = my_beam.get_reaction_forces()
>>> round(F_Ay, 4), round(F_By, 4)
(10.0, 10.0)

Overhanging beam — AISC Case 26 (P at free overhang end):
Beam 0–12 ft, pin at x=0, roller at x=8, 10-kip load at x=12.
Expected: R_A = −5 kips (down), R_B = 15 kips (up).

>>> ob = Beam(12)
>>> ob.pinned_support = 0
>>> ob.rolling_support = 8
>>> ob.add_loads([PointLoadV(10, 12)])
>>> F_Ax, F_Ay, F_By = ob.get_reaction_forces()
>>> round(F_Ay, 4), round(F_By, 4)
(-5.0, 15.0)

"""

#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
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

from collections import namedtuple
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Polygon, Rectangle, RegularPolygon
from matplotlib.collections import PatchCollection
import numpy as np
from sympy import integrate, lambdify, Piecewise, sympify, symbols, solve, linsolve
from sympy.abc import x


# plt.rc('text', usetex=True)  # This makes the plot text prettier... but SLOWER


class PointLoadV(namedtuple("PointLoadV", "force, coord")):
    """Vertical point load: (force in kips, coord in ft). Positive = downward.

    Examples
    --------
    >>> external_force = PointLoadV(30, 3)  # 30 kips downwards at x=3 ft
    >>> external_force
    PointLoadV(force=30, coord=3)
    """


class PointLoadH(namedtuple("PointLoadH", "force, coord")):
    """Horizontal point load: (force in kips, coord in ft). Positive = rightward.

    Examples
    --------
    >>> external_force = PointLoadH(10, 9)  # 10 kips to the right at x=9 ft
    >>> external_force
    PointLoadH(force=10, coord=9)
    """


class DistributedLoadV(namedtuple("DistributedLoadV", "expr, span")):
    """Distributed vertical load (kips/ft) over a span interval (ft). Positive = downward.

    Examples
    --------
    >>> snow_load = DistributedLoadV("2*x+1", (0, 10))  # downward, linearly varying, 0 to 10 ft
    """


class DistributedLoadH(namedtuple("DistributedLoadH", "expr, span")):
    """Distributed horizontal load (kips/ft) over a span interval (ft).

    Examples
    --------
    >>> wind_load = DistributedLoadH("0.5", (0, 20))  # 0.5 kips/ft over full span

    """


class PointTorque(namedtuple("PointTorque", "torque, coord")):
    """Point clockwise torque: (torque in kip·ft, coord in ft).

    Examples
    --------
    >>> applied_moment = PointTorque(30, 4)  # 30 kip·ft clockwise at x=4 ft

    """


class Beam:
    """
    Represents a one-dimensional beam that can take axial and tangential loads.

    Through the method `add_loads`, a Beam object can accept a list of:

    * PointLoad objects, and/or
    * DistributedLoad objects.

    Notes
    -----
    * Supports only statically determinate beams with exactly one pinned and
      one roller support.
    * Supports may be placed at any x-coordinate within the beam span.  When a
      support is interior to the span the beam overhangs that support on one or
      both sides (AISC Table 3-23 Cases 24–28).
    * Units: lengths in ft, forces in kips, moments in kip·ft.
      Deflection requires E in ksi and I in in⁴; result is in inches.

    """

    def __init__(self, span: float = 10):
        """Initializes a Beam object of a given length.

        Parameters
        ----------
        span : float or int
            Length of the beam span. Must be positive, and the pinned and rolling
            supports can only be placed within this span. The default value is 10.

        """
        self._x0 = 0
        self._x1 = span
        self._pinned_support = 2
        self._rolling_support = 8

        self._loads = []
        self._distributed_forces_x = []
        self._distributed_forces_y = []
        self._normal_forces = []
        self._shear_forces = []
        self._bending_moments = []

    @property
    def length(self):
        """float or int: Length of the beam. Must be positive."""
        return self._x1 - self._x0

    @length.setter
    def length(self, length: float):
        if length > 0:
            self._x1 = self._x0 + length
        else:
            raise ValueError("The provided length must be positive.")

    @property
    def pinned_support(self):
        """float or int: x-coordinate of the beam's pinned support. Must be
        within the beam span."""
        return self._pinned_support

    @pinned_support.setter
    def pinned_support(self, x_coord: float):
        if self._x0 <= x_coord <= self._x1:
            self._pinned_support = x_coord
        else:
            raise ValueError("The pinned support must be located within the beam span.")

    @property
    def rolling_support(self):
        """float or int: x-coordinate of the beam's rolling support. Must be
        within the beam span."""
        return self._rolling_support

    @rolling_support.setter
    def rolling_support(self, x_coord: float):
        if self._x0 <= x_coord <= self._x1:
            self._rolling_support = x_coord
        else:
            raise ValueError("The rolling support must be located within the beam span.")

    def add_loads(self, loads: list):
        """Apply an arbitrary list of (point- or distributed) loads to the beam.

        Parameters
        ----------
        loads : iterable
            An iterable containing DistributedLoad or PointLoad objects to
            be applied to the Beam object. Note that the load application point
            (or segment) must be within the Beam span.

        """
        for load in loads:
            supported_load_types = (DistributedLoadH, DistributedLoadV, PointLoadH, PointLoadV, PointTorque)
            if isinstance(load, supported_load_types):
                # Vertical loads: positive = downward
                # AISC convention: positive load is downward.
                # Internal logic (integration/reactions) often expects positive = upward.
                # In Beam.get_reaction_forces:
                # F_Ry = sum(integrate(load, (x, x0, x1)) for load in self._distributed_forces_y) +
                #        sum(f.force for f in self._point_loads_y())
                # If these are upward forces, sum(forces) = -sum(reactions)
                # So if user provides positive P (downward), we store -P (upward).
                if isinstance(load, PointLoadV):
                    self._loads.append(PointLoadV(-load.force, load.coord))
                elif isinstance(load, DistributedLoadV):
                    self._loads.append(DistributedLoadV(f"-({load.expr})", load.span))
                else:
                    self._loads.append(load)
            else:
                raise TypeError(
                    "The provided loads must be one of the supported types: {0}".format(supported_load_types))
        self._update_loads()

    def get_reaction_forces(self):
        """
        Calculates the reaction forces at the supports, given the applied loads.

        The first and second values correspond to the horizontal and vertical
        forces of the pinned support. The third one is the vertical force at the
        rolling support.

        Returns
        -------
        F_Ax, F_Ay, F_By: (float, float, float)
            reaction force components for pinned (x,y) and rolling (y) supports
            respectively.

        """
        x0, x1 = self._x0, self._x1
        xA, xB = self._pinned_support, self._rolling_support
        # self._distributed_forces_y stores forces in UPWARD positive convention (negated from user input)
        F_Rx = sum(integrate(load, (x, x0, x1)) for load in self._distributed_forces_x) + \
               sum(f.force for f in self._point_loads_x())
        F_Ry = sum(integrate(load, (x, x0, x1)) for load in self._distributed_forces_y) + \
               sum(f.force for f in self._point_loads_y())
        M_R = sum(integrate(load * x, (x, x0, x1)) for load in self._distributed_forces_y) + \
              sum(f.force * f.coord for f in self._point_loads_y()) + \
              sum(-1 * f.torque for f in self._point_torques())
        # Equilibrium:
        # Sum Fx = 0 => F_Ax + F_Rx = 0 => F_Ax = -F_Rx
        # Sum Fy = 0 => F_Ay + F_By + F_Ry = 0
        # Sum M_A = 0 => F_By * (xB - xA) + M_R_A = 0
        # M_R_A is moment of applied forces about xA: integral(w * (x - xA)) + sum(P * (x - xA)) - sum(T)
        # M_R_A = M_R - xA * F_Ry
        
        # Original code used:
        # A = [[-1, 0, 0], [0, -1, -xA], [0, -1, -xB]].T, b = [F_Rx, F_Ry, M_R]
        # Transposed A:
        # [[-1,  0,  0],
        #  [ 0, -1, -1],
        #  [ 0, -xA, -xB]]
        # A.dot(reactions) = b
        # -F_Ax = F_Rx => F_Ax = -F_Rx (Correct)
        # -F_Ay - F_By = F_Ry => F_Ay + F_By = -F_Ry (Correct: sum reactions + sum applied = 0)
        # -xA*F_Ay - xB*F_By = M_R => xA*F_Ay + xB*F_By = -M_R (Correct: sum moments = 0)
        
        A = np.array([[-1, 0, 0],
                      [0, -1, -xA],
                      [0, -1, -xB]]).T
        b = np.array([F_Rx, F_Ry, M_R])
        F_Ax, F_Ay, F_By = np.linalg.inv(A).dot(b)
        return F_Ax, F_Ay, F_By

    def plot(self):
        """Generates a single figure with 4 plots corresponding respectively to:

        - a schematic of the loaded beam
        - normal force diagram,
        - shear force diagram, and
        - bending moment diagram.

        These plots can be generated separately with dedicated functions.

        Returns
        -------
        figure : `~matplotlib.figure.Figure`
            Returns a handle to a figure with the 3 subplots: Beam schematic,
            shear force diagram, and bending moment diagram.

        """
        fig = plt.figure(figsize=(6, 10))
        fig.subplots_adjust(hspace=0.4)

        ax1 = fig.add_subplot(4, 1, 1)
        self.plot_beam_diagram(ax1)

        ax2 = fig.add_subplot(4, 1, 2)
        self.plot_normal_force(ax2)

        ax3 = fig.add_subplot(4, 1, 3)
        self.plot_shear_force(ax3)

        ax4 = fig.add_subplot(4, 1, 4)
        self.plot_bending_moment(ax4)

        return fig

    def plot_beam_diagram(self, ax=None):
        """Returns a schematic of the beam and all the loads applied on it.
        """
        plot01_params = {'ylabel': "Beam loads", 'yunits': r'kips / ft',
                         'color': "g",
                         'inverted': False}  # Set to False
        if ax is None:
            ax = plt.figure(figsize=(6, 2.5)).add_subplot(1, 1, 1)
        ax.set_title("Loaded beam diagram")

        # Negate the distributed forces here so it plots upright and positive
        dist_forces = sum(self._distributed_forces_y) if self._distributed_forces_y else sympify(0)
        self._plot_analytical(ax, -1 * dist_forces, **plot01_params)

        self._draw_beam_schematic(ax)
        return ax.get_figure()

    def plot_normal_force(self, ax=None):
        """Returns a plot of the normal force as a function of the x-coordinate.
        """
        plot02_params = {'ylabel': "Normal force", 'yunits': r'kips',
                         'color': "b"}
        if ax is None:
            ax = plt.figure(figsize=(6, 2.5)).add_subplot(1, 1, 1)
        self._plot_analytical(ax, sum(self._normal_forces), **plot02_params)
        return ax.get_figure()

    def plot_shear_force(self, ax=None):
        """Returns a plot of the shear force as a function of the x-coordinate.
        """
        plot03_params = {'ylabel': "Shear force", 'yunits': r'kips',
                         'color': "r"}
        if ax is None:
            ax = plt.figure(figsize=(6, 2.5)).add_subplot(1, 1, 1)
        self._plot_analytical(ax, sum(self._shear_forces), **plot03_params)
        return ax.get_figure()

    def plot_bending_moment(self, ax=None):
        """Returns a plot of the bending moment as a function of the x-coordinate.
        """
        plot04_params = {'ylabel': "Bending moment", 'yunits': r'kip·ft',
                         'xlabel': "Beam axis", 'xunits': "ft",
                         'color': "y"}
        if ax is None:
            ax = plt.figure(figsize=(6, 2.5)).add_subplot(1, 1, 1)
        self._plot_analytical(ax, sum(self._bending_moments), **plot04_params)
        return ax.get_figure()

    def _plot_analytical(self, ax: plt.axes, sym_func, title: str = "", maxmin_hline: bool = True, xunits: str = "",
                         yunits: str = "", xlabel: str = "", ylabel: str = "", color=None, inverted=False):
        """
        Auxiliary function for plotting a sympy.Piecewise analytical function.
        """
        x_vec = np.linspace(self._x0, self._x1, int(min(self.length * 1000 + 1, 1e4)))
        y_lam = lambdify(x, sym_func, "numpy")
        y_vec = np.array([y_lam(t) for t in x_vec])

        if inverted:
            y_vec *= -1

        if color:
            a, b = x_vec[0], x_vec[-1]
            verts = [(a, 0)] + list(zip(x_vec, y_vec)) + [(b, 0)]
            poly = Polygon(verts, facecolor=color, edgecolor='0.5', alpha=0.4)
            ax.add_patch(poly)

        if maxmin_hline:
            tol = 1e-3
            max_val = max(y_vec)
            min_val = min(y_vec)

            # 1. Plot Maximum
            if abs(max_val) > tol:
                ax.axhline(y=max_val, linestyle='--', color="g", alpha=0.5)
                max_idx = y_vec.argmax()
                ax.annotate(
                    '${:0.1f}'.format(max_val * (1 - 2 * inverted)).rstrip('0').rstrip('.') + " $ {}".format(
                        yunits),
                    xy=(x_vec[max_idx], max_val), xytext=(5, 5), xycoords=('data', 'data'),
                    textcoords='offset points', va='bottom', size=12)

            # 2. Plot Minimum (ONLY if it's different from the maximum)
            if abs(min_val) > tol and abs(max_val - min_val) > tol:
                ax.axhline(y=min_val, linestyle='--', color="g", alpha=0.5)
                min_idx = y_vec.argmin()
                ax.annotate(
                    '${:0.1f}'.format(min_val * (1 - 2 * inverted)).rstrip('0').rstrip('.') + " $ {}".format(
                        yunits),
                    xy=(x_vec[min_idx], min_val), xytext=(5, -5), xycoords=('data', 'data'),
                    textcoords='offset points', va='top', size=12)

        xspan = x_vec.max() - x_vec.min()
        ax.set_xlim([x_vec.min() - 0.01 * xspan, x_vec.max() + 0.01 * xspan])

        # 3. Add padding to the Y-axis so the floating text isn't cut off at the bottom/top
        ymin, ymax = ax.get_ylim()
        yspan = ymax - ymin
        if yspan > 0:
            ax.set_ylim([ymin - 0.15 * yspan, ymax + 0.15 * yspan])

        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)

        if title:
            ax.set_title(title)

        if xlabel or xunits:
            ax.set_xlabel('{} [{}]'.format(xlabel, xunits))

        if ylabel or yunits:
            ax.set_ylabel("{} [{}]".format(ylabel, yunits))

        return ax

    def _draw_beam_schematic(self, ax):
        """Auxiliary function for plotting the beam object and its applied loads.
        """
        # Adjust y-axis
        ymin, ymax = -5, 5
        ylim = (min(ax.get_ylim()[0], ymin), max(ax.get_ylim()[1], ymax))
        ax.set_ylim(ylim)
        xspan = ax.get_xlim()[1] - ax.get_xlim()[0]
        yspan = ylim[1] - ylim[0]

        # Draw beam body
        beam_left, beam_right = self._x0, self._x1
        beam_length = beam_right - beam_left
        beam_height = yspan * 0.06
        beam_bottom = -(0.75) * beam_height
        beam_top = beam_bottom + beam_height
        beam_body = Rectangle(
            (beam_left, beam_bottom), beam_length, beam_height, fill=True,
            facecolor="brown", alpha=0.7
        )
        ax.add_patch(beam_body)

        # Markers at beam supports
        # Pinned support: Triangle
        pinned_support = Polygon(np.array([self.pinned_support + 0.02 * xspan * np.array((-1, 1, 0)),
                                           beam_bottom + 0.05 * np.array((-1, -1, 0)) * yspan]).T)

        # Rolling support: Circle
        rolling_support_center = (self.rolling_support, beam_bottom - 0.025 * yspan)
        rolling_support = Circle(rolling_support_center, 0.01 * xspan, facecolor="black")

        ax.add_patch(pinned_support)
        ax.add_patch(rolling_support)

        # Draw arrows at point loads
        arrowprops = dict(arrowstyle="simple", color="darkgreen", shrinkA=0.1, mutation_scale=18)
        for load in self._point_loads_y():
            x0 = x1 = load[1]
            if load[0] < 0:
                y0, y1 = beam_top, beam_top + 0.17 * yspan
            else:
                y0, y1 = beam_bottom, beam_bottom - 0.17 * yspan
            ax.annotate("",
                        xy=(x0, y0), xycoords='data',
                        xytext=(x1, y1), textcoords='data',
                        arrowprops=arrowprops
                        )

        for load in self._point_loads_x():
            x0 = load[1]
            y0 = y1 = (beam_top + beam_bottom) / 2.0
            if load[0] < 0:
                x1 = x0 + xspan * 0.05
            else:
                x1 = x0 - xspan * 0.05
            ax.annotate("",
                        xy=(x0, y0), xycoords='data',
                        xytext=(x1, y1), textcoords='data',
                        arrowprops=arrowprops
                        )

        # Draw a round arrow at point torques
        for load in self._point_torques():  # pragma: no cover
            xc = load[1]
            yc = (beam_top + beam_bottom) / 2.0
            width = yspan * 0.17
            height = xspan * 0.05
            arc_len = 180

            if load[0] < 0:
                start_angle = 90
                endX = xc + (height / 2) * np.cos(np.radians(arc_len + start_angle))
                endY = yc + (width / 2) * np.sin(np.radians(arc_len + start_angle))
            else:
                start_angle = 270
                endX = xc + (height / 2) * np.cos(np.radians(start_angle))
                endY = yc + (width / 2) * np.sin(np.radians(start_angle))

            orientation = start_angle + arc_len
            arc = Arc([xc, yc], width, height, angle=start_angle, theta2=arc_len, capstyle='round', linestyle='-',
                      lw=2.5, color="darkgreen")
            arrow_head = RegularPolygon((endX, endY), 3, radius=height * 0.35, orientation=np.radians(orientation), color="darkgreen")
            ax.add_patch(arc)
            ax.add_patch(arrow_head)

        ax.axes.get_yaxis().set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        # ax.tick_params(left="off")

    def _update_loads(self):
        x0 = self._x0

        self._distributed_forces_x = [self._create_distributed_force(f) for f in self._distributed_loads_x()]
        self._distributed_forces_y = [self._create_distributed_force(f) for f in self._distributed_loads_y()]

        rxns = self.get_reaction_forces()
        self._solve_indeterminate_reactions()
        rxns = self.get_reaction_forces()

        if len(rxns) == 3:
            f_ax, f_ay, f_by = rxns
        elif len(rxns) == 4:
            # ProppedCantileverBeam returns (F_Ax, F_Ay, M_A, F_By)
            f_ax, f_ay, _, f_by = rxns
        elif len(rxns) == 5:
            # FixedFixedBeam returns (F_Ax, F_Ay, M_A, F_By, M_B)
            f_ax, f_ay, _, f_by, _ = rxns
        elif len(rxns) == 2:
            f_ax = 0.0
            f_ay, f_by = rxns
        else:
            raise ValueError(f"Unexpected number of reaction forces: {len(rxns)}")

        pinned_support_load_x = PointLoadH(f_ax, self._pinned_support)
        pinned_support_load_y = PointLoadV(f_ay, self._pinned_support)
        rolling_support_load = PointLoadV(f_by, self._rolling_support)

        self._normal_forces = [-1 * integrate(load, (x, x0, x)) for load in self._distributed_forces_x]
        self._normal_forces.extend(-1 * self._effort_from_pointload(f) for f in self._point_loads_x())
        self._normal_forces.append(-1 * self._effort_from_pointload(pinned_support_load_x))

        self._shear_forces = [integrate(load, (x, x0, x)) for load in self._distributed_forces_y]
        self._shear_forces.extend(self._effort_from_pointload(f) for f in self._point_loads_y())
        self._shear_forces.append(self._effort_from_pointload(pinned_support_load_y))
        self._shear_forces.append(self._effort_from_pointload(rolling_support_load))

        self._bending_moments = [integrate(load, (x, x0, x)) for load in self._shear_forces]
        self._bending_moments.extend(self._effort_from_pointload(f) for f in self._point_torques())

    def _create_distributed_force(self, load: DistributedLoadH or DistributedLoadV, shift: bool = True):
        """
        Create a sympy.Piecewise object representing the provided distributed load.

        :param expr: string with a valid sympy expression.
        :param interval: tuple (x0, x1) containing the extremes of the interval on
        which the load is applied.
        :param shift: when set to False, the x-coordinate in the expression is
        referred to the left end of the beam, instead of the left end of the
        provided interval.
        :return: sympy.Piecewise object with the value of the distributed load.
        """
        expr, interval = load
        x0, x1 = interval
        expr = sympify(expr)
        if shift:
            expr.subs(x, x - x0)
        else:  # pragma: no cover
            pass
        return Piecewise((0, x < x0), (0, x > x1), (expr, True))

    def _solve_indeterminate_reactions(self):
        """Hook for indeterminate beams to solve for redundant reactions."""
        pass

    def _effort_from_pointload(self, load: PointLoadH or PointLoadV):
        """
        Create a sympy.Piecewise object representing the shear force caused by a
        point load.

        :param value: float or string with the numerical value of the point load.
        :param coord: x-coordinate on which the point load is applied.
        :return: sympy.Piecewise object with the value of the shear force produced
        by the provided point load.
        """
        value, coord = load
        return Piecewise((0, x < coord), (value, True))

    def _point_loads_x(self):
        for f in self._loads:
            if isinstance(f, PointLoadH):
                yield f

    def _point_loads_y(self):
        for f in self._loads:
            if isinstance(f, PointLoadV):
                yield f

    def _distributed_loads_x(self):
        for f in self._loads:
            if isinstance(f, DistributedLoadH):
                yield f

    def _distributed_loads_y(self):
        for f in self._loads:
            if isinstance(f, DistributedLoadV):
                yield f

    def _point_torques(self):
        for f in self._loads:
            if isinstance(f, PointTorque):
                yield f

    def get_moment_function(self):
        return sum(self._bending_moments)

    def get_bending_moment(self):
        """Alias for get_moment_function to maintain compatibility with older notebook cells."""
        return self.get_moment_function()

    def get_envelope(self, loads: list, step_size: float = 0.5):
        """
        Calculates the shear and moment envelope for a moving load or set of loads.

        Parameters
        ----------
        loads : list
            A list of PointLoadV objects representing the moving load configuration.
            The coordinates of these loads should be relative to the first load (at 0).
        step_size : float
            The distance to move the load at each step.

        Returns
        -------
        x_vec : ndarray
            The x-coordinates along the beam.
        max_shear : ndarray
            Maximum shear at each x.
        min_shear : ndarray
            Minimum shear at each x.
        max_moment : ndarray
            Maximum moment at each x.
        min_moment : ndarray
            Minimum moment at each x.
        """
        x_vec = np.linspace(self._x0, self._x1, int(min(self.length * 100 + 1, 5000)))
        max_shear = np.full_like(x_vec, -np.inf)
        min_shear = np.full_like(x_vec, np.inf)
        max_moment = np.full_like(x_vec, -np.inf)
        min_moment = np.full_like(x_vec, np.inf)

        # Determine the range of motion
        # The load moves from where the first load is at x=0 to where the last load is at x=L
        load_offsets = [load.coord for load in loads]
        min_offset = min(load_offsets)
        max_offset = max(load_offsets)
        
        # Start so that the leading edge of the vehicle starts at x=0
        # and end so that the trailing edge finishes at x=L
        start_pos = -max_offset
        end_pos = self.length - min_offset

        current_pos = start_pos
        while current_pos <= end_pos + 1e-9:
            # Create a temporary copy of the beam to avoid modifying the original indefinitely
            # Actually, we can just update loads on 'self' if we are careful, 
            # but it's safer to use a temporary setup.
            
            # Save original loads
            original_loads = list(self._loads)
            
            # Shift loads to current position
            shifted_loads = []
            for load in loads:
                shifted_pos = current_pos + load.coord
                # Only add loads that are on the beam
                if 0 <= shifted_pos <= self.length:
                    shifted_loads.append(PointLoadV(load.force, shifted_pos))
            
            if shifted_loads:
                # Clear and add shifted loads
                self._loads = []
                self.add_loads(shifted_loads)
                
                # Get shear and moment functions
                shear_func = sum(self._shear_forces)
                moment_func = sum(self._bending_moments)
                
                shear_lam = lambdify(x, shear_func, "numpy")
                moment_lam = lambdify(x, moment_func, "numpy")
                
                # Evaluate at x_vec
                # lambdify might return a scalar if func is constant
                y_shear = shear_lam(x_vec)
                if not isinstance(y_shear, np.ndarray):
                    y_shear = np.full_like(x_vec, y_shear)
                    
                y_moment = moment_lam(x_vec)
                if not isinstance(y_moment, np.ndarray):
                    y_moment = np.full_like(x_vec, y_moment)
                
                max_shear = np.maximum(max_shear, y_shear)
                min_shear = np.minimum(min_shear, y_shear)
                max_moment = np.maximum(max_moment, y_moment)
                min_moment = np.minimum(min_moment, y_moment)
            
            # Reset loads for next step
            self._loads = original_loads
            self._update_loads()
            
            current_pos += step_size
            
        return x_vec, max_shear, min_shear, max_moment, min_moment

    def plot_envelope(self, x_vec, max_shear, min_shear, max_moment, min_moment, ax=None):
        """
        Plots the shear and moment envelopes.
        """
        if ax is None:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10))
        else:
            fig = ax.get_figure()
            ax1 = ax
            # If only one ax is provided, we might have trouble. 
            # Better to just create a new figure if ax is None.
            
        if ax is None:
            ax1.plot(x_vec, max_shear, 'r-', label='Max Shear')
            ax1.plot(x_vec, min_shear, 'b-', label='Min Shear')
            ax1.fill_between(x_vec, min_shear, max_shear, color='gray', alpha=0.3)
            ax1.set_title("Shear Envelope")
            ax1.set_ylabel("Shear (kips)")
            ax1.grid(True)
            ax1.legend()

            ax2.plot(x_vec, max_moment, 'r-', label='Max Moment')
            ax2.plot(x_vec, min_moment, 'b-', label='Min Moment')
            ax2.fill_between(x_vec, min_moment, max_moment, color='gray', alpha=0.3)
            ax2.set_title("Moment Envelope")
            ax2.set_ylabel("Moment (kip-ft)")
            ax2.set_xlabel("Distance (ft)")
            ax2.grid(True)
            ax2.legend()
            
            return fig
        else:
            # If a single ax was passed, just plot both on it? 
            # No, that's messy. Let's assume user wants standard plot if ax is None.
            return None

    def get_deflection_function(self, E_ksi, I_in4):
        """Returns the symbolic deflection function δ(x) in inches.

        Parameters
        ----------
        E_ksi : float
            Modulus of elasticity in ksi (e.g. 29000 for steel).
        I_in4 : float
            Moment of inertia in in⁴. Can be a Pint quantity — magnitude is used.
        """
        try:
            I_in4 = float(I_in4.magnitude)
        except AttributeError:
            I_in4 = float(I_in4)
        EI = E_ksi * I_in4  # kip·in²
        # x is in ft, M is in kip·ft.  Substituting x_in = 12*x_ft into EI d²δ/dx² = M
        # gives d²δ_in/dx_ft² = 1728 * M_kip·ft / EI_kip·in²  (factor = 12³)
        M = self.get_moment_function()  # kip·ft
        C1, C2 = symbols("C1 C2")
        slope = integrate(1728 * M / EI, x) + C1
        defl = integrate(slope, x) + C2
        xA, xB = self._pinned_support, self._rolling_support
        sol = solve([defl.subs(x, xA), defl.subs(x, xB)], [C1, C2])
        return defl.subs(sol)

    def plot_deflection(self, E_ksi, I_in4, ax=None):
        """Plots the deflection diagram in inches.

        Parameters
        ----------
        E_ksi : float
            Modulus of elasticity in ksi.
        I_in4 : float or Pint quantity
            Moment of inertia in in⁴.
        """
        defl_func = self.get_deflection_function(E_ksi, I_in4)
        params = {
            'ylabel': "Deflection", 'yunits': "in",
            'xlabel': "Beam axis", 'xunits': "ft",
            'color': "purple",
        }
        if ax is None:
            ax = plt.figure(figsize=(6, 2.5)).add_subplot(1, 1, 1)
        ax.set_title("Deflection diagram")
        self._plot_analytical(ax, defl_func, **params)
        return ax.get_figure()

    def plot_all(self):
        """Generates a figure with 4 subplots: beam diagram, shear, moment, deflection.

        Parameters are obtained from the beam's existing loads. Deflection is omitted
        (use plot() or call plot_deflection() separately with E and I values).
        Returns a figure with shear and moment only alongside the beam diagram.
        """
        fig = plt.figure(figsize=(6, 10))
        fig.subplots_adjust(hspace=0.4)
        ax1 = fig.add_subplot(4, 1, 1)
        self.plot_beam_diagram(ax1)
        ax2 = fig.add_subplot(4, 1, 2)
        self.plot_normal_force(ax2)
        ax3 = fig.add_subplot(4, 1, 3)
        self.plot_shear_force(ax3)
        ax4 = fig.add_subplot(4, 1, 4)
        self.plot_bending_moment(ax4)
        return fig


class CantileverBeam(Beam):
    """A cantilever beam: fixed at x=0, free at x=span.

    Loads and coordinates use the same conventions as Beam (kips, ft).

    Example
    -------
    >>> cb = CantileverBeam(10)
    >>> cb.add_loads([PointLoadV(-5, 10)])   # 5 kip downward at free end
    >>> V, M = cb.get_reaction_forces()
    >>> round(float(V), 4), round(float(M), 4)
    (5.0, 50.0)
    """

    def __init__(self, span: float = 10):
        self._x0 = 0
        self._x1 = span
        self._fixed_support = 0.0
        self._loads = []
        self._distributed_forces_x = []
        self._distributed_forces_y = []
        self._normal_forces = []
        self._shear_forces = []
        self._bending_moments = []

    def get_reaction_forces(self):
        """Returns (V_A, M_A) at the fixed support (vertical reaction and fixed moment).

        V_A is positive upward; M_A is positive counter-clockwise.
        """
        x0, x1 = self._x0, self._x1
        F_Ry = sum(integrate(load, (x, x0, x1)) for load in self._distributed_forces_y) + \
               sum(f.force for f in self._point_loads_y())
        M_R = sum(integrate(load * x, (x, x0, x1)) for load in self._distributed_forces_y) + \
              sum(f.force * f.coord for f in self._point_loads_y()) + \
              sum(-1 * f.torque for f in self._point_torques())
        V_A = -F_Ry
        M_A = -M_R
        return float(V_A), float(M_A)

    def _update_loads(self):
        x0 = self._x0
        self._distributed_forces_x = [self._create_distributed_force(f) for f in self._distributed_loads_x()]
        self._distributed_forces_y = [self._create_distributed_force(f) for f in self._distributed_loads_y()]

        V_A, M_A = self.get_reaction_forces()
        fixed_shear = PointLoadV(V_A, self._fixed_support)
        fixed_moment = PointTorque(-M_A, self._fixed_support)

        self._normal_forces = [-1 * integrate(load, (x, x0, x)) for load in self._distributed_forces_x]
        self._normal_forces.extend(-1 * self._effort_from_pointload(f) for f in self._point_loads_x())

        self._shear_forces = [integrate(load, (x, x0, x)) for load in self._distributed_forces_y]
        self._shear_forces.extend(self._effort_from_pointload(f) for f in self._point_loads_y())
        self._shear_forces.append(self._effort_from_pointload(fixed_shear))

        self._bending_moments = [integrate(load, (x, x0, x)) for load in self._shear_forces]
        self._bending_moments.extend(self._effort_from_pointload(f) for f in self._point_torques())
        self._bending_moments.append(self._effort_from_pointload(fixed_moment))

    def get_deflection_function(self, E_ksi, I_in4):
        """Returns the symbolic deflection function δ(x) in inches.

        Boundary conditions: δ(0) = 0, δ'(0) = 0 (fixed end).
        """
        try:
            I_in4 = float(I_in4.magnitude)
        except AttributeError:
            I_in4 = float(I_in4)
        EI = E_ksi * I_in4
        M = self.get_moment_function()  # kip·ft, x in ft
        C1, C2 = symbols("C1 C2")
        slope = integrate(1728 * M / EI, x) + C1
        defl = integrate(slope, x) + C2
        sol = solve([slope.subs(x, 0), defl.subs(x, 0)], [C1, C2])
        return defl.subs(sol)

    def plot_beam_diagram(self, ax=None):
        """Returns a schematic of the cantilever beam."""
        plot01_params = {'ylabel': "Beam loads", 'yunits': r'kips / ft',
                         'color': "g",
                         'inverted': False}  # Set to False
        if ax is None:
            ax = plt.figure(figsize=(6, 2.5)).add_subplot(1, 1, 1)
        ax.set_title("Loaded beam diagram (Cantilever)")

        # Negate the distributed forces here so it plots upright and positive
        dist_forces = sum(self._distributed_forces_y) if self._distributed_forces_y else sympify(0)
        self._plot_analytical(ax, -1 * dist_forces, **plot01_params)

        self._draw_cantilever_schematic(ax)
        return ax.get_figure()

    def _draw_cantilever_schematic(self, ax):
        """Draws the cantilever beam schematic with fixed wall at left end."""
        ymin, ymax = -5, 5
        ylim = (min(ax.get_ylim()[0], ymin), max(ax.get_ylim()[1], ymax))
        ax.set_ylim(ylim)
        xspan = ax.get_xlim()[1] - ax.get_xlim()[0]
        yspan = ylim[1] - ylim[0]

        beam_left, beam_right = self._x0, self._x1
        beam_length = beam_right - beam_left
        beam_height = yspan * 0.06
        beam_bottom = -(0.75) * beam_height
        beam_top = beam_bottom + beam_height

        beam_body = Rectangle(
            (beam_left, beam_bottom), beam_length, beam_height, fill=True,
            facecolor="brown", alpha=0.7
        )
        ax.add_patch(beam_body)

        # Fixed wall at left: hatch rectangle
        wall_width = xspan * 0.025
        wall = Rectangle(
            (beam_left - wall_width, beam_bottom - yspan * 0.07),
            wall_width, beam_height + yspan * 0.14,
            fill=True, facecolor="gray", alpha=0.8, hatch="////"
        )
        ax.add_patch(wall)

        # Arrows at point loads
        arrowprops = dict(arrowstyle="simple", color="darkgreen", shrinkA=0.1, mutation_scale=18)
        for load in self._point_loads_y():
            x0 = x1 = load[1]
            if load[0] < 0:
                y0, y1 = beam_top, beam_top + 0.17 * yspan
            else:
                y0, y1 = beam_bottom, beam_bottom - 0.17 * yspan
            ax.annotate("", xy=(x0, y0), xycoords='data', xytext=(x1, y1),
                        textcoords='data', arrowprops=arrowprops)

        ax.axes.get_yaxis().set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)


def plot_beam_full(beam, E=29000, I=None, title=""):
    """2×2 grid: beam diagram, shear, moment, deflection (if I provided).

    Parameters
    ----------
    beam : Beam or CantileverBeam
        A beam object with loads already applied.
    E : float
        Modulus of elasticity in ksi. Default 29000 (steel).
    I : float or Pint quantity, optional
        Moment of inertia in in⁴.  When omitted the deflection panel is hidden.
    title : str, optional
        Figure suptitle.
    """
    fig, axes = plt.subplots(2, 2, figsize=(12, 6))
    fig.subplots_adjust(hspace=0.45, wspace=0.35, top=0.88)
    if title:
        fig.suptitle(title, fontsize=11, fontweight="bold")

    beam.plot_beam_diagram(axes[0, 0])
    beam.plot_shear_force(axes[0, 1])
    beam.plot_bending_moment(axes[1, 0])

    if I is not None:
        beam.plot_deflection(E, I, axes[1, 1])
    else:
        axes[1, 1].set_visible(False)

    return fig


class ProppedCantileverBeam(Beam):
    """A propped cantilever beam: fixed at x=0, roller at x=span.

    Boundary conditions:
    - x = 0: slope = 0, deflection = 0
    - x = span: deflection = 0

    Examples
    --------
    >>> pcb = ProppedCantileverBeam(10)
    >>> pcb.add_loads([PointLoadV(5, 5)])  # 5 kip downward at midspan
    >>> R_A, V_A, M_A, R_B = pcb.get_reaction_forces()
    """

    def __init__(self, span: float = 10):
        super().__init__(span)
        self._pinned_support = 0.0
        self._rolling_support = span
        self._fixed_end_moment = 0.0

    def _solve_indeterminate_reactions(self):
        """Solves for the redundant reaction at the roller support using compatibility."""
        L = self.length
        R_B_sym = symbols("R_B_red")

        orig_loads = self._loads[:]
        # Add redundant R_B as an UPWARD reaction.
        # Beam.add_loads would negate a positive force (downward -> upward).
        # Here we directly append to self._loads which stores UPWARD positive forces.
        # So we append R_B_sym.
        self._loads.append(PointLoadV(R_B_sym, self._rolling_support))

        # Recompute components for moment function calculation
        self._distributed_forces_y = [self._create_distributed_force(f) for f in self._distributed_loads_y()]

        loads_y = list(self._point_loads_y())
        F_Ry = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
               sum(f.force for f in loads_y)

        M_R = sum(integrate(load * x, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
              sum(f.force * f.coord for f in loads_y) + \
              sum(-1 * f.torque for f in self._point_torques())

        V_A_static = -F_Ry
        M_A_static = -M_R

        shear_forces = [integrate(load, (x, self._x0, x)) for load in self._distributed_forces_y]
        shear_forces.extend(self._effort_from_pointload(f) for f in loads_y)
        shear_forces.append(self._effort_from_pointload(PointLoadV(V_A_static, 0)))

        bending_moments = [integrate(load, (x, self._x0, x)) for load in shear_forces]
        bending_moments.extend(self._effort_from_pointload(f) for f in self._point_torques())
        bending_moments.append(self._effort_from_pointload(PointTorque(-M_A_static, 0)))

        M_func = sum(bending_moments)

        slope_ei = integrate(M_func, x)
        defl_ei = integrate(slope_ei, x)

        sol = solve(defl_ei.subs(x, L), R_B_sym)

        if sol:
            self._redundant_R_B = float(sol[0])
        else:  # pragma: no cover
            self._redundant_R_B = 0.0

        self._loads = orig_loads
        self._fixed_end_moment = float(M_A_static.subs(R_B_sym, self._redundant_R_B))

    def get_reaction_forces(self):
        """Returns (F_Ax, V_A, M_A, R_B).
        V_A is vertical reaction at fixed end (upward positive).
        M_A is moment at fixed end (counter-clockwise positive).
        R_B is vertical reaction at roller (upward positive).
        """
        xA, xB = self._pinned_support, self._rolling_support
        F_Ry_ext = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
                   sum(f.force for f in self._point_loads_y())

        F_By = getattr(self, '_redundant_R_B', 0.0)
        F_Ay = -F_Ry_ext - F_By

        # Horizontal
        F_Rx = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_x) + \
               sum(f.force for f in self._point_loads_x())
        F_Ax = -F_Rx

        return F_Ax, F_Ay, self._fixed_end_moment, F_By

    def _update_loads(self):
        super()._update_loads()
        # Add the fixed end moment which super()._update_loads doesn't know about
        # It's at x=0
        fixed_moment_load = PointTorque(-self._fixed_end_moment, self._pinned_support)
        self._bending_moments.append(self._effort_from_pointload(fixed_moment_load))

    def get_deflection_function(self, E_ksi, I_in4):
        """Returns the symbolic deflection function δ(x) in inches.
        Boundary conditions: δ(0) = 0, δ'(0) = 0.
        """
        try:
            I_in4 = float(I_in4.magnitude)
        except AttributeError:
            I_in4 = float(I_in4)
        EI = E_ksi * I_in4
        M = self.get_moment_function()
        C1, C2 = symbols("C1 C2")
        slope = integrate(1728 * M / EI, x) + C1
        defl = integrate(slope, x) + C2
        # Use fixed end at x=0
        sol = solve([slope.subs(x, 0), defl.subs(x, 0)], [C1, C2])
        return defl.subs(sol)

    def _draw_beam_schematic(self, ax):
        """Draws propped cantilever: wall at left, roller at right."""
        ymin, ymax = -5, 5
        ylim = (min(ax.get_ylim()[0], ymin), max(ax.get_ylim()[1], ymax))
        ax.set_ylim(ylim)
        xspan = ax.get_xlim()[1] - ax.get_xlim()[0]
        yspan = ylim[1] - ylim[0]

        beam_left, beam_right = self._x0, self._x1
        beam_length = beam_right - beam_left
        beam_height = yspan * 0.06
        beam_bottom = -(0.75) * beam_height
        beam_top = beam_bottom + beam_height

        beam_body = Rectangle(
            (beam_left, beam_bottom), beam_length, beam_height, fill=True,
            facecolor="brown", alpha=0.7
        )
        ax.add_patch(beam_body)

        # Fixed wall at left
        wall_width = xspan * 0.025
        wall = Rectangle(
            (beam_left - wall_width, beam_bottom - yspan * 0.07),
            wall_width, beam_height + yspan * 0.14,
            fill=True, facecolor="gray", alpha=0.8, hatch="////"
        )
        ax.add_patch(wall)

        # Roller at right: Circle
        rolling_support_center = (self.rolling_support, beam_bottom - 0.025 * yspan)
        rolling_support = Circle(rolling_support_center, 0.01 * xspan, facecolor="black")
        ax.add_patch(rolling_support)

        # Arrows at point loads
        arrowprops = dict(arrowstyle="simple", color="darkgreen", shrinkA=0.1, mutation_scale=18)
        for load in self._point_loads_y():
            x0 = x1 = load[1]
            if load[0] < 0:
                y0, y1 = beam_top, beam_top + 0.17 * yspan
            else:
                y0, y1 = beam_bottom, beam_bottom - 0.17 * yspan
            ax.annotate("", xy=(x0, y0), xycoords='data', xytext=(x1, y1),
                        textcoords='data', arrowprops=arrowprops)

        ax.spines['left'].set_visible(False)


class ContinuousBeam(Beam):
    """A continuous beam with an arbitrary number of intermediate roller supports.

    Parameters
    ----------
    span : float
        Length of the beam.
    intermediate_supports : list of float
        x-coordinates of intermediate roller supports.
    """

    def __init__(self, span: float = 10, intermediate_supports: list = None):
        super().__init__(span)
        self._intermediate_supports = intermediate_supports if intermediate_supports else []
        self._redundant_reactions = {}

    def _solve_indeterminate_reactions(self):
        """Solves for redundant reactions at intermediate supports using compatibility (deflection=0)."""
        if not self._intermediate_supports:
            self._redundant_reactions = {}
            return

        xA, xB = self._pinned_support, self._rolling_support

        # Create symbols for redundant reactions
        R_syms = [symbols(f"R_int_{i}") for i in range(len(self._intermediate_supports))]

        orig_loads = self._loads[:]
        # Add redundant reactions as upward point loads
        for i, x_coord in enumerate(self._intermediate_supports):
            self._loads.append(PointLoadV(R_syms[i], x_coord))

        # Recompute distributed forces for calculation
        self._distributed_forces_y = [self._create_distributed_force(f) for f in self._distributed_loads_y()]

        # Total applied loads (including redundants)
        loads_y = list(self._point_loads_y())
        F_Ry = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
               sum(f.force for f in loads_y)
        M_R = sum(integrate(load * x, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
              sum(f.force * f.coord for f in loads_y) + \
              sum(-1 * f.torque for f in self._point_torques())

        # Solve for static reactions at A and B in terms of redundants
        # F_Ay + F_By + F_Ry = 0
        # F_By * (xB - xA) + M_R - xA * F_Ry = 0
        F_By_static = (xA * F_Ry - M_R) / (xB - xA)
        F_Ay_static = -F_Ry - F_By_static

        # Shear and Moment functions
        # For compatibility integration, we need to be careful with xA and xB locations.
        # It's easier to use the Beam._effort_from_pointload logic.
        
        shear_forces = [integrate(load, (x, self._x0, x)) for load in self._distributed_forces_y]
        shear_forces.extend(self._effort_from_pointload(f) for f in loads_y)
        shear_forces.append(self._effort_from_pointload(PointLoadV(F_Ay_static, xA)))
        shear_forces.append(self._effort_from_pointload(PointLoadV(F_By_static, xB)))

        bending_moments = [integrate(load, (x, self._x0, x)) for load in shear_forces]
        bending_moments.extend(self._effort_from_pointload(f) for f in self._point_torques())

        M_func = sum(bending_moments)

        # Deflection (integrated twice, EI omitted)
        slope_ei = integrate(M_func, x)
        defl_ei = integrate(slope_ei, x)

        # Boundary conditions at A and B (defl = 0)
        # EI*v(x) = defl_ei + C1*x + C2
        C1, C2 = symbols("C1_int C2_int")
        defl_eq = defl_ei + C1 * x + C2

        # Solve for C1, C2 using deflection at xA and xB is 0
        c_sol = solve([defl_eq.subs(x, xA), defl_eq.subs(x, xB)], [C1, C2])
        defl_final = defl_eq.subs(c_sol)

        # Compatibility: deflection at each intermediate support is 0
        compat_eqs = [defl_final.subs(x, xi) for xi in self._intermediate_supports]
        r_sol = solve(compat_eqs, R_syms)

        if isinstance(r_sol, dict):
            self._redundant_reactions = {xi: float(r_sol[Ri]) for xi, Ri in zip(self._intermediate_supports, R_syms)}
        elif len(R_syms) == 1 and r_sol:  # pragma: no cover
            if isinstance(r_sol, (list, tuple)):
                self._redundant_reactions = {self._intermediate_supports[0]: float(r_sol[0])}
            else:
                self._redundant_reactions = {self._intermediate_supports[0]: float(r_sol)}
        elif isinstance(r_sol, list) and r_sol:  # pragma: no cover
            # Handle multiple results if solve returns a list of solutions (usually only one for linear)
            res = r_sol if not isinstance(r_sol[0], (list, tuple)) else r_sol[0]
            self._redundant_reactions = {xi: float(val) for xi, val in zip(self._intermediate_supports, res)}
        else:  # pragma: no cover
            self._redundant_reactions = {xi: 0.0 for xi in self._intermediate_supports}

        self._loads = orig_loads
        # We do NOT call self._update_loads() here because it would cause infinite recursion.
        # Beam.add_loads calls _update_loads, which calls _solve_indeterminate_reactions.

    def get_reaction_forces(self):
        """Returns (F_Ax, F_Ay, F_By) where F_Ay and F_By are the base supports.
        Intermediate reactions can be retrieved from self._redundant_reactions.
        """
        F_Ry_ext = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
                   sum(f.force for f in self._point_loads_y())

        # Sum of redundant forces
        F_R_red = sum(self._redundant_reactions.values())
        M_R_red = sum(R * xi for xi, R in self._redundant_reactions.items())

        xA, xB = self._pinned_support, self._rolling_support
        M_R_ext = sum(integrate(load * x, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
                  sum(f.force * f.coord for f in self._point_loads_y()) + \
                  sum(-1 * f.torque for f in self._point_torques())

        F_Ry_total = F_Ry_ext + F_R_red
        M_R_total = M_R_ext + M_R_red

        F_By = (xA * F_Ry_total - M_R_total) / (xB - xA)
        F_Ay = -F_Ry_total - F_By

        F_Rx = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_x) + \
               sum(f.force for f in self._point_loads_x())
        F_Ax = -F_Rx

        return float(F_Ax), float(F_Ay), float(F_By)

    def _update_loads(self):
        super()._update_loads()
        # Ensure redundant reactions are NOT double-counted in diagrams.
        # super()._update_loads() already added reactions from get_reaction_forces()
        # which are at xA and xB. 
        # We only need to add the intermediate ones.
        # But wait, super()._update_loads() calls get_reaction_forces() which 
        # includes the effect of redundant reactions on xA and xB.
        # So we JUST need to add the intermediate point loads.
        for xi, R in self._redundant_reactions.items():
            load = PointLoadV(R, xi)
            self._shear_forces.append(self._effort_from_pointload(load))
            self._bending_moments.append(integrate(self._effort_from_pointload(load), (x, self._x0, x)))

    def _draw_beam_schematic(self, ax):
        super()._draw_beam_schematic(ax)
        # Draw intermediate supports
        ymin, ymax = -5, 5
        ylim = (min(ax.get_ylim()[0], ymin), max(ax.get_ylim()[1], ymax))
        ax.set_ylim(ylim)
        yspan = ylim[1] - ylim[0]

        beam_bottom = -0.75 * (yspan * 0.06)

        for xi in self._intermediate_supports:
            # Draw a circle for roller
            rolling_support_center = (xi, beam_bottom - 0.025 * yspan)
            rolling_support = Circle(rolling_support_center, 0.01 * (ax.get_xlim()[1] - ax.get_xlim()[0]), facecolor="black")
            ax.add_patch(rolling_support)


class FixedFixedBeam(Beam):
    """A fixed-fixed beam: fixed at x=0, fixed at x=span.

    Boundary conditions:
    - x = 0: slope = 0, deflection = 0
    - x = span: slope = 0, deflection = 0
    """

    def __init__(self, span: float = 10):
        super().__init__(span)
        self._pinned_support = 0.0
        self._rolling_support = span
        self._MA = 0.0
        self._MB = 0.0

    def _solve_indeterminate_reactions(self):
        """Solves for redundant reactions at the right support (R_B and M_B)."""
        L = self.length
        R_B_sym, M_B_sym = symbols("R_B_red M_B_red")

        orig_loads = self._loads[:]
        # R_B is upward reaction (+ R_B_sym), M_B is CCW (+ M_B_sym)
        # PointTorque(torque, coord) says "clockwise torque" in docstring.
        # So CCW M_B is added as -M_B_sym.
        self._loads.append(PointLoadV(R_B_sym, L))
        self._loads.append(PointTorque(-M_B_sym, L))

        self._distributed_forces_y = [self._create_distributed_force(f) for f in self._distributed_loads_y()]

        loads_y = list(self._point_loads_y())
        F_Ry = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
               sum(f.force for f in loads_y)
        M_R = sum(integrate(load * x, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
              sum(f.force * f.coord for f in loads_y) + \
              sum(-1 * f.torque for f in self._point_torques())

        V_A_static = -F_Ry
        M_A_static = -M_R

        shear_forces = [integrate(load, (x, self._x0, x)) for load in self._distributed_forces_y]
        shear_forces.extend(self._effort_from_pointload(f) for f in loads_y)
        shear_forces.append(self._effort_from_pointload(PointLoadV(V_A_static, 0)))

        bending_moments = [integrate(load, (x, self._x0, x)) for load in shear_forces]
        bending_moments.extend(self._effort_from_pointload(f) for f in self._point_torques())
        bending_moments.append(self._effort_from_pointload(PointTorque(-M_A_static, 0)))

        M_func = sum(bending_moments)

        slope_ei = integrate(M_func, x)
        defl_ei = integrate(slope_ei, x)

        # Compatibility: slope and deflection at x=L are 0
        sol = solve([slope_ei.subs(x, L), defl_ei.subs(x, L)], [R_B_sym, M_B_sym])

        if sol:
            self._redundant_R_B = float(sol[R_B_sym])
            self._redundant_M_B = float(sol[M_B_sym])
        else:  # pragma: no cover
            self._redundant_R_B = 0.0
            self._redundant_M_B = 0.0

        self._loads = orig_loads
        self._MA = float(M_A_static.subs({R_B_sym: self._redundant_R_B, M_B_sym: self._redundant_M_B}))

    def get_reaction_forces(self):
        F_Ry_ext = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_y) + \
                   sum(f.force for f in self._point_loads_y())
        F_By = getattr(self, '_redundant_R_B', 0.0)
        M_B = getattr(self, '_redundant_M_B', 0.0)
        F_Ay = -F_Ry_ext - F_By
        # Horizontal
        F_Rx = sum(integrate(load, (x, self._x0, self._x1)) for load in self._distributed_forces_x) + \
               sum(f.force for f in self._point_loads_x())
        F_Ax = -F_Rx

        # In AISC, both end moments for Case 15 are positive (sagging convention/magnitudes)
        # Our solver returns CCW positive. For a symmetric load, M_A (CCW) and M_B (CW) 
        # would have opposite signs if both are CCW-positive.
        # We return both as positive magnitudes here to match the notebook's expectations.
        return F_Ax, F_Ay, abs(self._MA), F_By, abs(M_B)

    def _update_loads(self):
        super()._update_loads()
        # Add fixed end moments
        ma_load = PointTorque(-self._MA, 0)
        mb_load = PointTorque(-self._redundant_M_B, self.length)
        self._bending_moments.append(self._effort_from_pointload(ma_load))
        self._bending_moments.append(self._effort_from_pointload(mb_load))

    def get_deflection_function(self, E_ksi, I_in4):
        try:
            I_in4 = float(I_in4.magnitude)
        except AttributeError:
            I_in4 = float(I_in4)
        EI = E_ksi * I_in4
        M = self.get_moment_function()
        C1, C2 = symbols("C1 C2")
        slope = integrate(1728 * M / EI, x) + C1
        defl = integrate(slope, x) + C2
        sol = solve([slope.subs(x, 0), defl.subs(x, 0)], [C1, C2])
        return defl.subs(sol)

    def _draw_beam_schematic(self, ax):
        """Draws fixed-fixed: wall at both ends."""
        ymin, ymax = -5, 5
        ylim = (min(ax.get_ylim()[0], ymin), max(ax.get_ylim()[1], ymax))
        ax.set_ylim(ylim)
        xspan = ax.get_xlim()[1] - ax.get_xlim()[0]
        yspan = ylim[1] - ylim[0]

        beam_left, beam_right = self._x0, self._x1
        beam_length = beam_right - beam_left
        beam_height = yspan * 0.06
        beam_bottom = -(0.75) * beam_height
        beam_top = beam_bottom + beam_height

        beam_body = Rectangle(
            (beam_left, beam_bottom), beam_length, beam_height, fill=True,
            facecolor="brown", alpha=0.7
        )
        ax.add_patch(beam_body)

        # Fixed wall at left
        wall_width = xspan * 0.025
        wall_left = Rectangle(
            (beam_left - wall_width, beam_bottom - yspan * 0.07),
            wall_width, beam_height + yspan * 0.14,
            fill=True, facecolor="gray", alpha=0.8, hatch="////"
        )
        ax.add_patch(wall_left)

        # Fixed wall at right
        wall_right = Rectangle(
            (beam_right, beam_bottom - yspan * 0.07),
            wall_width, beam_height + yspan * 0.14,
            fill=True, facecolor="gray", alpha=0.8, hatch="////"
        )
        ax.add_patch(wall_right)

        # Arrows at point loads
        arrowprops = dict(arrowstyle="simple", color="darkgreen", shrinkA=0.1, mutation_scale=18)
        for load in self._point_loads_y():
            x0 = x1 = load[1]
            if load[0] < 0:
                y0, y1 = beam_top, beam_top + 0.17 * yspan
            else:
                y0, y1 = beam_bottom, beam_bottom - 0.17 * yspan
            ax.annotate("", xy=(x0, y0), xycoords='data', xytext=(x1, y1),
                        textcoords='data', arrowprops=arrowprops)

        ax.axes.get_yaxis().set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
