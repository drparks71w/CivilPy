#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""CivilPy — a Python toolkit for practicing civil engineers.

The package is organized by discipline:

* :mod:`civilpy.structural` — steel, concrete, and timber design checks,
  AASHTO LRFD / AREMA calculations, strut-and-tie tools, and bridge-specific
  designers (the most mature package).
* :mod:`civilpy.geotech` — boring-log data models and parsers, SPT
  corrections, foundations, and lateral earth pressure.
* :mod:`civilpy.water_resources` — open-channel and pipe hydraulics, and
  bridge scour.
* :mod:`civilpy.transportation` — roadway geometry and FHWA NBI utilities.
* :mod:`civilpy.state` — agency-specific tools (predominantly Ohio DOT).
* :mod:`civilpy.general` — shared helpers: the Pint unit registry
  (``civilpy.general.units``), photo/EXIF tools, and database utilities.
"""

