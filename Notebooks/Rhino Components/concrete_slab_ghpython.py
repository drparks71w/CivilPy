# r: civilpy
"""Concrete slab rebar generator — GHPython (Rhino 8, CPython 3) source.

Successor to "Concrete Slab.gh".  Improvements over the original:

* Bar size is a standard designator (#4, #5, ...) resolved through
  civilpy's ASTM rebar table instead of a raw diameter slider.
* Integer bar counts with the grid centered in the slab — no float
  accumulation, and the last bar always lands symmetrically.
* Separate top/bottom covers (deck-style 2.5 / 1.5 defaults per ODOT BDM)
  and correct BDM-style stacking: bottom mat carries the X-direction bars
  on the cover, top mat carries them nearest the surface.
* A report output that states the as-generated steel (bars, spacing,
  As per ft each way) instead of failing silently.

Component inputs (Type Hint in parentheses; all lengths in DOCUMENT units
except BarSize):
    Length      (float)  slab X dimension
    Width       (float)  slab Y dimension
    Depth       (float)  slab thickness
    CoverTop    (float)  clear cover, top surface (optional, default 2.5 in)
    CoverBottom (float)  clear cover, bottom surface (optional, default 1.5 in)
    CoverSide   (float)  clear cover, slab edges (optional, default 2.0 in)
    BarSize     (int)    standard bar designator, e.g. 5 (optional, #5)
    Spacing     (float)  bar spacing, both directions
Outputs:
    Rebar  (Curve, List)
    Slab   (Brep)
    Report (str)
"""

import Rhino
import Rhino.Geometry as rg

from civilpy.structural.steel import Rebar as RebarSize


def _inches(x):
    """`x` inches expressed in document units."""
    return x * Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Inches, Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem)


def _bar_positions(lo, hi, spacing):
    """Centered bar positions in [lo, hi] at `spacing` (>= 1 bar)."""
    run = hi - lo
    if run < 0:
        return []
    count = int(run / spacing) + 1
    total = (count - 1) * spacing
    start = lo + (run - total) / 2.0
    return [start + i * spacing for i in range(count)]


rebar_curves = []
Slab = None
report_lines = []

_required = ("Length", "Width", "Depth", "Spacing")
if not all(globals().get(k) for k in _required):
    Report = "Connect inputs: Length, Width, Depth, Spacing."
else:
    L, W, H, spacing = float(Length), float(Width), float(Depth), float(Spacing)
    size = int(BarSize) if globals().get("BarSize") else 5
    c_top = float(CoverTop) if globals().get("CoverTop") else _inches(2.5)
    c_bot = float(CoverBottom) if globals().get("CoverBottom") else _inches(1.5)
    c_side = float(CoverSide) if globals().get("CoverSide") else _inches(2.0)

    bar = RebarSize(size)
    db = _inches(float(bar.diameter.magnitude))
    area = float(bar.area.magnitude)  # in^2 (report only)

    # two stacked layers per mat + covers must fit inside the thickness
    if H < c_top + c_bot + 4.0 * db:
        Report = ("Slab too thin: {}+{} cover and four #{} layers need "
                  "{:.2f} but Depth is {:.2f}.".format(
                      c_top, c_bot, size, c_top + c_bot + 4 * db, H))
    elif spacing <= db:
        Report = "Spacing must exceed one bar diameter."
    else:
        x0, x1 = c_side + db / 2.0, L - c_side - db / 2.0
        y0, y1 = c_side + db / 2.0, W - c_side - db / 2.0

        # centerline z of each layer, bottom to top
        z_bot_y = c_bot + db / 2.0            # bottom mat, Y-direction bars
        z_bot_x = c_bot + db * 1.5            # bottom mat, X-direction bars
        z_top_x = H - c_top - db * 1.5        # top mat, X-direction bars
        z_top_y = H - c_top - db / 2.0        # top mat, Y-direction bars

        for x in _bar_positions(x0, x1, spacing):        # Y-direction bars
            for z in (z_bot_y, z_top_y):
                rebar_curves.append(rg.LineCurve(
                    rg.Point3d(x, y0, z), rg.Point3d(x, y1, z)))
        for y in _bar_positions(y0, y1, spacing):        # X-direction bars
            for z in (z_bot_x, z_top_x):
                rebar_curves.append(rg.LineCurve(
                    rg.Point3d(x0, y, z), rg.Point3d(x1, y, z)))

        Slab = rg.Box(
            rg.Plane.WorldXY, rg.Interval(0, L), rg.Interval(0, W),
            rg.Interval(0, H)).ToBrep()

        n_y = len(_bar_positions(x0, x1, spacing))
        n_x = len(_bar_positions(y0, y1, spacing))
        as_per_ft = area * _inches(12.0) / spacing
        report_lines = [
            "Mats: 2 x (#{} @ {:.2f}) each way".format(size, spacing),
            "Bars: {} Y-direction + {} X-direction per mat".format(n_y, n_x),
            "As = {:.3f} in^2/ft per layer".format(as_per_ft),
            "Covers: top {:.2f}, bottom {:.2f}, side {:.2f}".format(
                c_top, c_bot, c_side),
        ]
        Report = "\n".join(report_lines)

# the GH output is named "Rebar"; the civilpy class was imported as
# RebarSize so the names don't collide
Rebar = rebar_curves
