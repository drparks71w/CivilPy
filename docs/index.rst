CivilPy
=======

**CivilPy** is a Python toolkit for practicing civil engineers. It bundles
unit-aware calculation tools (built on `Pint <https://pint.readthedocs.io>`_),
design checks from the AASHTO LRFD and AREMA specifications, geotechnical
data models, hydraulics, and utilities for working with agency data sources
such as ODOT TIMS and Bentley AssetWise.

CivilPy is released under the :ref:`MIT License <license>`.

Installation
------------

.. code-block:: bash

   pip install civilpy

Optional extras pull in heavier dependencies only when you need them:

.. code-block:: bash

   pip install "civilpy[db]"         # PostgreSQL / Oracle / SSH-tunnel tools
   pip install "civilpy[geo]"        # folium mapping
   pip install "civilpy[jupyter]"    # notebook export helpers
   pip install "civilpy[pdf]"        # PDF/plan-sheet processing

Quick start
-----------

Most of CivilPy works with dimensioned quantities from the shared Pint unit
registry:

.. code-block:: python

   from civilpy.general import units
   from civilpy.structural.steel import SteelSection

   beam = SteelSection("W36X150")
   beam.weight     # 150 lbf/ft, as a Pint quantity
   beam.I_x        # strong-axis moment of inertia (9040 in^4)

   M = 150 * units("kip * ft")
   sigma = (M / beam.S_x).to("ksi")

Package overview
----------------

===============================  ====================================================
Package                          What it covers
===============================  ====================================================
:mod:`civilpy.structural`        Steel/concrete/timber design, AASHTO LRFD & AREMA
                                 checks, strut-and-tie tools, influence lines,
                                 substructure designers, MIDAS & CANDE interfaces
:mod:`civilpy.geotech`           Boring logs (DIGGS/PDF parsing), SPT corrections,
                                 shallow/deep foundations, lateral earth pressure
:mod:`civilpy.water_resources`   Open-channel & pipe hydraulics, bridge scour,
                                 ODOT culvert standards
:mod:`civilpy.transportation`    Roadway geometry, horizontal/vertical curves,
                                 FHWA NBI utilities
:mod:`civilpy.state`             Agency-specific tools (ODOT TIMS/AssetWise,
                                 SNBI validation, plan-review checklists)
:mod:`civilpy.general`           Shared unit registry, photo/EXIF tools,
                                 database helpers
===============================  ====================================================

.. toctree::
   :maxdepth: 3
   :caption: API Reference:

   civilpy

.. todo::
   The design notes currently sitting in the ``docs/`` folder
   (``StrutAndTieSolver.md``, ``SNBIValidationRules.md``,
   ``Rhino Design Philosophy.md``) are not part of the Sphinx build; wire
   them in with ``myst-parser`` or convert them to reST. The stray
   ``ifc_file_example_1.ifc`` fixture should move to ``tests/`` or ``res/``.

.. _license:

License
-------

CivilPy is distributed under the MIT License — see the
`LICENSE <https://gitlab.com/dane.parks/civilpy/-/blob/master/LICENSE>`_ file
for the full text.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
