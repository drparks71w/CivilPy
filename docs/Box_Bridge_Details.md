# Box-beam bridge detail examples

The packaged API is `civilpy.structural.box_bridge_details.BoxDetailInput`
and `detailed_box_bridge_emit(inputs)`. Inputs select the abutment,
foundation, rail, termination, grade and crossfall within the documented
60 ft, eight-beam example envelope. This is a coordination-model generator,
not a general span-sizing or foundation-design solver.

Install `civilpy[rhino]`, then generate the gallery from any directory:

```powershell
python -m civilpy.structural.box_bridge_gallery --output ./bridge_examples
# Equivalent installed command:
civilpy-box-bridges --output ./bridge_examples
```

Generate the models and reports from the repository root:

```powershell
.venv/Scripts/python.exe scripts/generate_box_bridge_details.py
```

For native Rhino slab faces, run `scripts/refine_box_bridge_slabs_rhino.py`
in Rhino 8 against the generated gallery (`__rhino_doc__` is the target
document). This replaces each deck mesh with a capped longitudinal loft in
the live document and all five generated 3DM files. The loft is checked for
validity and closure, and surface isocurves are disabled. Repeat this step
after regenerating the portable mesh files.

With civilpy installed in Rhino's Python environment, the same supported API is:

```python
from civilpy.structural.rhino_box_slabs import refine
refine(__rhino_doc__, r"C:\path\to\bridge_examples")
```

When loading the generated JSON through `draw_bim_emit.py`, native deck
lofts are created automatically. `native_slabs=False` explicitly requests
the portable mesh representation. The driver can find its Rhino adapter in
this checkout without installing civilpy in Rhino. When executing the driver
with `exec`, supply its real `__file__` in the execution namespace.

Outputs are in `Notebooks/output/box_bridge_details/` (ignored generated files):
`integral.3dm`, `semi-integral.3dm`, `seat.3dm`, `seat-shafts.3dm`, and
`Box Bridge Detail Gallery.3dm`. JSON files carry the same geometry for the
existing Rhino emit driver. Each example has a `.clashes.json` report; the
combined report is `summary.json`. The gallery offsets the examples 90 ft
transversely; individual models use their actual local coordinates in feet.

These are **synthetic coordination examples, not construction-ready designs**.
The outputs intentionally retain unresolved clashes. No project identifiers,
survey, employee information or proprietary bridge geometry is used.

## Included geometry

All four examples have eight CB27-48 beams, a 60 ft span and zero skew.
The integral and semi-integral examples have 2% crowned surfaces; the
conventional example has a 2% one-way crossfall. Roadway grades are 1%, -0.5%
and 0.5%, respectively. A small parabolic roadway profile changes topping
thickness independently of the straight beam grade. Approaches continue the
end tangent and cross slope. Surface flow traces show the open fascia outlets.

| File | Abutment / foundation | Bridge rail | Roadside end treatments |
|---|---|---|---|
| `integral` | Integral / flexible HP piles | DBR-2 with DBR-3 retrofit | Buried in backslope, MGS-4.5 |
| `semi-integral` | Semi-integral / spread footing | DBR-2 with DBR-3 retrofit | Type A concrete anchors, existing restricted local-road comparison |
| `seat` | Conventional / spread footing | DBR-2 with DBR-3 retrofit | Buried upstream; Type T downstream, one-way +X scenario |
| `seat-shafts` | Conventional / six 42 in drilled shafts | TST-2 comparison | Buried upstream; Type T downstream, one-way +X scenario |

The DBR faces are corrugated W-beam sheets, with W6x25 posts, backup tubes,
the DBR-3 upper taper and lower 15-degree flare. GR-3.4 Type 4 bridge transitions
include the specified post sequence, nested panels and omitted rail attachments
at posts 2, 3, 4, 6 and 8. A 50 ft height transition raises the 27.75 in DBR/Type 5
rail to 31 in MGS, within the BDM's four-panel limit. The TST comparison includes
bridge-side adapter envelopes, nested/single thrie panels, and W-to-thrie transition.

Terminations extend beyond the bridge transitions and approach slabs. The
buried option includes the flare, height reduction, rub rail, anchor plate and
soil covering the end. Type A includes a gradually twisted rail, concrete
anchor and reinforcement. Type T includes BCT posts, ground tubes, cable,
strut and rounded end. It is restricted to the downstream end in a one-way
traffic example; no Type T is put on an exposed upstream end. Roadway pavement
continues through the treatment. `terrain_context` layers can be enabled to
show approach fill supporting the roadside posts; they start hidden for
substructure review. Actual soil, scour, length of need and roadside grading
remain site-specific design inputs.

The deck is now **one continuous closed mesh**, with separate top, soffit and
perimeter faces. Profile sampling no longer creates separate solids with end
caps every two feet. Those caps and their averaged normals caused the previous
plank-like stripes; the corrected export retains sharp perimeter edges without
averaging side-face normals across the road surface.

* TST-2-21 open three-tube railing envelopes: W6x15 posts, HSS wall solids,
  side plates, two 1 in diameter x 32 in transverse f5 rods per post, and short
  lower anchorage envelopes. Posts are located around the transverse ties,
  maintaining 18 in minimum separation and 8 ft maximum post spacing.
* Two elastomeric pads at each beam end, positioned 10 in from each beam edge
  and 6 in from the end, following PSBD-1-25 sheet 6. This also corrects the
  original neutral box-beam emitter's one-pad-per-end inventory.
* #6 deck reinforcement, longitudinal spacing <=18 in and transverse <=9 in,
  with the transverse bars above the longitudinal mat and 2.5 in top cover.
* Beam reinforcement envelopes around the railing anchors, solid end blocks,
  diaphragms, and staggered transverse ties spanning no more than three beams.
* Separate substructure arrangements: integral single pile row and connected
  cap/backwall; semi-integral moving backwall above a spread footing; conventional
  backwall behind an expansion gap on either a spread footing or drilled shafts.
  Spread footings and shaft cages include reinforcement envelopes.
* AS-1-15 approach slab profiles and scheduled reinforcement at both ends,
  approach seats, AS-2-15 sleeper slabs, sleeper bars and underdrain envelopes.

## Clash review

`rebar_clash.check_clearance` uses circular bar/rod envelopes, AABB filtering,
and minimum segment-to-segment distance over each bent centerline. Negative
clearance means penetration. Tangency within 0.001 in is excluded; optional
positive clearance checks are supported. End envelopes are conservative.

The generated reports identify both object IDs and penetration depth. Red
`CLASH REVIEW` layers duplicate involved centerlines so they can be isolated
in Rhino. Bar centerlines and solid envelopes have separate layers. The live
gallery initially hides centerlines and clash overlays for exterior review.

The revised examples report 168 integral, 124 semi-integral and 168 for each conventional
clashes. There are no reported long railing-anchor clashes with the modeled
beam/deck reinforcement or tie rods. Remaining conflicts involve approach
anchors versus approach/abutment steel, and bearing dowels versus abutment
steel. These counts are **not** a whole-bridge clearance certificate: only the
listed group pairs are checked, and omitted geometry cannot be checked.

## Remaining detailing work

Foundation dimensions, HP10x42 pile lengths and substructure reinforcement
are stated coordination assumptions, not results of load/geotechnical design.
Bearing reactions, movement, beam camber, rail applicability and structural
reinforcement checks must be completed for an actual site. The examples use
a waterway setting consistent with the chosen open railing's application;
they do not establish suitability for every roadway or crossing.

The existing section/approach catalogs omit important fabrication geometry:
box keyways and void fillets, individualized strands, some end anchorage and
development, A-bar bends and D801 terminal hooks. The examples also omit
complete TST-2 fabrication plates/fasteners/splices, joint assemblies,
approach underdrain outlets, and beam-joint fit-up allowances. Railing and terminal
assemblies are dimensional envelopes, not fabrication drawings: corrugations use
sampled nominal width/depth profiles; not every bend radius, slot, bolt and BCT
breakaway cut is represented. The full connection hardware and complete bent-bar
shapes must be checked before accepting fabrication clearances.

Concrete and steel are initially exported as closed meshes for portable viewing;
the Rhino refinement step converts the decks to closed lofted solids. They
are geometric envelopes, not Boolean-cut fabrication parts. The roadway
deck curve is tessellated at 1 ft intervals (maximum vertical chord error below
0.001 in for the examples); dimensions are plan-projected.

## Railing applicability

The DBR examples are intentionally existing/retrofit comparisons on a non-NHS
waterway crossing where ODOT does not have major-maintenance responsibility.
BDM 309.4.3.4/.5 describe the restricted applications and distinguish DBR-2
from DBR-3. They are not general replacements for a MASH-rated railing on an
ODOT/NHS project. Type A also has application restrictions in L&D Volume 1
Section 603; this example is not a recommendation to install a turned-down
anchor on a general new roadway. The Type T examples assume the terminals are
outside opposing-traffic clear zones, as required by MGS-4.2. These applicability
assumptions are stored in the models and reports.

The source PDFs and restoration instructions are listed in
[ODOT Reference Library](ODOT_Reference_Library.md). The latest SCD PDFs are
available locally; existing Python catalogs are not automatically certified
against every newly downloaded revision.
