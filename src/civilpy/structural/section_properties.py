"""
CivilPy
Copyright (C) 2019-2026 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from civilpy.structural.steel import W


class CrossSection:
    """
    A class for defining a built-up section by repeatedly adding plate
    dimensions.

    This class allows users to define a built-up cross-section by calling the
    instance and passing in the dimensions of each plate making up the section.
    The plates are assumed to be entered in order from the bottom to the top,
    and all shapes are assumed to be rectangles that do not overlap.

    Attributes:
        labels (list of str): A list of labels identifying each plate in the
            cross-section.
        dimensions (list): A list of tuples (width, height) for each
            plate.
        ys (list of float): The centroids of each plate along the y-axis.
        areas (list of float): The areas of each plate.
        moments (list of float): The first moments of area for each plate.
        I_ys (list of float): The second moments of area of each plate about
            its own centroid.
        I_gs (list of float): The second moments of area of each plate about
            the global centroid.
        area (float): The total area of the cross-section.
        moment (float): The first moment of area of the cross-section.
        I_y (float): The total second moment of area about the local centroid.
        I_g (float): The total second moment of area about the global centroid.
        I_n (int): The net inertia value, adjusted for global centroid.
        n (float): The location of the neutral axis.

    Args:
        label (str): A label to identify the plate in the cross-section (e.g.,
            "A", "B").
        dimensions (tuple): A tuple representing the plate dimensions (width,
            height).
        shape (str, optional): The shape of the plate (default is `None` for
            rectangles).

    Returns:
        CrossSection: An instance of the CrossSection object.
    """

    def __init__(self, label, dimensions=None, shape=None, y=None,
                 axis='strong'):
        """Initialise a built-up cross-section with its first plate or shape.

        Args:
            label (str): Identifier for this plate (e.g. ``"bottom flange"``).
            dimensions (tuple[float, float], optional): ``(width, height)`` of
                a rectangular plate in consistent units. Required when *shape*
                is ``None``.
            shape (W, optional): A steel wide-flange shape object from
                :mod:`civilpy.structural.steel`. When supplied, *dimensions*
                is derived from the shape's flange width and depth.
            y (float, optional): Distance from the datum to the centroid of
                this plate. Defaults to half the plate height (i.e. the plate
                sits with its bottom at y = 0).
            axis (str): ``'strong'`` (default) to use I_x and depth, or
                ``'weak'`` to use I_y and flange width for rolled shapes.
        """
        self.labels = [label, ]
        if shape:
            self.shape = shape  # //TODO - Replace with generalized function
            self.dimensions = [(
                self.shape.flange_width.magnitude,
                self.shape.depth.magnitude
            ), ]
            self.areas = [float(self.shape.area.magnitude), ]
            self.I_gs = [float(self.shape.I_x.magnitude), ]
        else:
            self.dimensions = [dimensions, ]
            self.areas = [dimensions[0] * dimensions[1], ]
            self.I_gs = [dimensions[0] * dimensions[1] ** 3 / 12, ]

        if not y:
            y = self.dimensions[0][1] / 2
            self.ys = [y, ]

        self.ys = [y, ]
        self.moments = [self.areas[0] * y, ]
        self.I_ys = [self.moments[0] * y, ]
        self.height = self.dimensions[0][1] / 2 + y
        self._calc_gen_properties()

    def __call__(self, label, dimensions=None, y=None, shape=None,
                 axis='strong'):
        """Append a new plate or shape to the cross-section.

        Calling the instance is the preferred way to build up a section
        incrementally. Each call delegates to :meth:`append_value` and
        recalculates aggregate section properties.

        Args:
            label (str): Identifier for the new plate.
            dimensions (tuple[float, float], optional): ``(width, height)`` of
                a rectangular plate. Required when *shape* is ``None``.
            y (float, optional): Centroid distance from the datum. When
                omitted, the plate is stacked directly on top of the current
                section.
            shape (W, optional): Rolled steel shape; overrides *dimensions*.
            axis (str): ``'strong'`` or ``'weak'`` axis for rolled shapes.
        """
        self.labels.append(label)
        if shape:
            self.shape = shape
        self.append_value(dimensions, y, shape)

    def __repr__(self):
        """Return a human-readable summary of all plates in the section.

        Returns:
            str: One line per plate with its label and ``(width, height)``
            dimensions.
        """
        return "\n".join([f"{x} {y}" for x, y in zip(
            self.labels,
            self.dimensions
        )])

    def append_value(self, dimensions=None, y=None, shape=None,
                     axis=None):
        """Add a plate or rolled shape to the cross-section and update properties.

        Four dispatch paths are supported:

        1. **Rectangular plate stacked on top** (``y=None``, ``shape=None``):
           plate sits directly above the current top of section.
        2. **Rolled shape at explicit y** (``shape`` provided, ``y`` provided):
           uses I_x or I_y depending on *axis*.
        3. **Rolled shape stacked on top** (``shape`` provided, ``y=None``):
           depth/flange width derived from shape; stacked on current top.
        4. **Rectangular plate at explicit y** (``shape=None``, ``y`` provided):
           plate placed with centroid at *y*.

        Args:
            dimensions (tuple[float, float], optional): ``(width, height)`` of
                a rectangular plate.
            y (float, optional): Centroid position from datum.
            shape (W, optional): Rolled steel shape object.
            axis (str, optional): ``'strong'`` or ``'weak'`` for rolled shapes.

        Note:
            :meth:`_calc_gen_properties` is called automatically after each
            plate is added.
        """
        if y is None and shape is None:  # Adding rect sect at top of xsection
            self.dimensions.append(dimensions)
            y = self.height + dimensions[1] / 2
            self.height = self.height + dimensions[1]
            area = self.dimensions[-1][0] * self.dimensions[-1][1]
            self.I_gs.append(
                (self.dimensions[-1][0] * self.dimensions[-1][1] ** 3) / 12)

        elif shape and y:  # Shape provided, with y value
            area = float(self.shape.area.magnitude)
            if axis == 'strong':
                self.dimensions.append((
                    self.shape.flange_width.magnitude,
                    self.shape.depth.magnitude))
                self.height += self.shape.depth.magnitude / 2 + y
                self.I_gs.append(float(self.shape.I_x.magnitude))
            else:
                self.dimensions.append((
                    self.shape.depth.magnitude,
                    self.shape.flange_width.magnitude
                ))
                self.height += self.shape.flange_width.magnitude / 2 + y
                self.I_gs.append(float(self.shape.I_y.magnitude))

        elif shape and y is None:  # Shape provided, no y value
            # //TODO - Update to account for non-symmetrical shapes
            # //TODO - Update to use a general function
            if axis == 'strong':
                self.dimensions.append((
                    self.shape.flange_width.magnitude,
                    self.shape.depth.magnitude))
            else:
                self.dimensions.append((
                    self.shape.depth.magnitude,
                    self.shape.flange_width.magnitude
                ))
            y = self.height + (self.shape.depth.magnitude / 2)
            self.height += self.shape.depth.magnitude
            area = float(self.shape.area.magnitude)
            self.I_gs.append(float(self.shape.I_x.magnitude))

        elif shape is None and y:  # Rectangular box at y height
            self.dimensions.append(dimensions)
            area = self.dimensions[-1][0] * self.dimensions[-1][1]
            self.I_gs.append(
                round((self.dimensions[-1][0] *
                       self.dimensions[-1][1] ** 3) /
                      12, 2))
        else:  # pragma: no cover
            print("Unexpected execution")
        self.areas.append(area)
        self.ys.append(float(y))
        self.moments.append(self.areas[-1] * self.ys[-1])
        self.I_ys.append(self.moments[-1] * self.ys[-1])

        self._calc_gen_properties()

    # //TODO - Update a function in the steel library to accept general input
    # //TODO - Update Steel library to ID symmetrical shapes (no y value)

    def check_negative_y_values(self):
        """Check whether any plate centroid lies below the datum (y < 0).

        Returns:
            bool: ``True`` if at least one y-coordinate key in
            ``self.plate_dims`` is negative, ``False`` otherwise.
        """
        for value in self.plate_dims.keys():
            if value < 0:
                return True
        return False

    def _calc_gen_properties(self):
        """Recalculate aggregate section properties from the current plate list.

        Updates the following instance attributes after each plate is added:

        - ``area``: total cross-sectional area.
        - ``moment``: first moment of area about the datum.
        - ``I_y``: sum of individual plate second moments about their own
          centroids.
        - ``I_g``: sum of individual plate second moments about the global
          centroid.
        - ``I_n``: net moment of inertia (parallel-axis adjustment applied).
        - ``n``: location of the elastic neutral axis from the datum.
        - ``plate_dims``: mapping of centroid y-values to plate heights.
        - ``cb``: distance from neutral axis to the extreme fibre.
        - ``S``: elastic section modulus.
        """
        self.area = sum(self.areas)
        self.moment = sum(self.moments)
        self.I_y = sum(self.I_ys)
        self.I_g = sum(self.I_gs)
        self.I_n = round(
            self.I_y + self.I_g - (self.moment ** 2 / self.area),
            1)
        self.n = round(self.moment / self.area, 3)
        self.plate_dims = {x: y[1] for x, y in zip(self.ys, self.dimensions)}
        # //TODO - have this check both negative and positive
        plate_dims = {x: y[1] for x, y in zip(self.ys, self.dimensions)}
        extr_neg_y = min(plate_dims.keys()) - \
                     plate_dims[min(plate_dims.keys())] / 2

        if self.check_negative_y_values():
            self.cb = extr_neg_y - self.n
        else:
            self.cb = self.height - self.n
        self.S = round(self.I_n / self.cb, 0)
