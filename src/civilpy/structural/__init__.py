#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Structural engineering package — the most developed part of CivilPy.

Highlights:

* ``SteelSection`` lookups from the AISC shapes database
  (:mod:`~civilpy.structural.steel`) and built-up plate sections
  (:mod:`~civilpy.structural.section_properties`).
* AASHTO LRFD design/rating in :mod:`civilpy.structural.aashto` (design
  vehicles, distribution factors, steel/concrete/prestressed/timber
  resistance, splices, columns, railing — see ``aashto.lrfd``).
* AREMA railroad design in :mod:`civilpy.structural.arema`.
* Strut-and-tie tools: solver (:mod:`~civilpy.structural.strut_and_tie`),
  Rhino authoring (:mod:`~civilpy.structural.rhino_stm`), and the
  topology-optimization pipeline (:mod:`civilpy.structural.stm_topology`).
* Bridge substructure designers (:mod:`~civilpy.structural.abutment`,
  :mod:`~civilpy.structural.pier`), ODOT standard-drawing designers
  (:mod:`civilpy.structural.odot`), classic analysis tools (influence
  lines, moment distribution, shear flow, Mohr's circle), and interfaces to
  MIDAS Civil and CANDE.
"""

