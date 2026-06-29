# Rhino ↔ Jupyter Design Philosophy

*Status: in development on branch `Modeling-Pipeline`. The Python read/write
bridge and a RhinoPython authoring prototype have shipped; a compiled C# plugin
and a Midas API path are planned. This document records the architectural
decisions, the schema contract, and the divided roadmap for using Rhino 3D as the
modeling front-end for civilpy structural analysis (starting with strut-and-tie).
See [Roadmap and separation of responsibilities](#roadmap-and-separation-of-responsibilities)
for the live task list.*

## Motivation

The current notebook workflow builds a model imperatively:

```python
model.add_node("A", 0, 0)
model.add_support("A", fix_x=True, fix_y=True)
model.add_load("E", fy=-600)
model.add_member("A", "B")
```

This is clunky for detailing real geometry. Rhino is a far better authoring
surface (best value for features + API accessibility), so the goal is to **draw
the model in Rhino and analyze it in Jupyter**, with a clean round trip.

The reference problem is FHWA-NHI-17-071 Example 1, already drawn in
`NHI17071_Ex_1.3dm` (units: **feet**, drawn flat in the **XZ plane** / front
elevation, Y = 0 throughout).

## Core principle

> **Geometry carries what is spatial; tags carry what is scalar.**

- *Spatial facts* live in the geometry: a member's connectivity is its endpoints,
  a load's direction is the arrow's vector, a support's location is its point.
- *Scalar / typed facts* live in **object user text** (Rhino attribute user
  text — a per-object key/value dictionary): magnitude, DOF fixity, and "kind".
- The **visual symbol** is either a chosen *block* (for supports — a fixed glyph)
  or the *drawn geometry itself* (for loads — the arrow is the data).

User text travels **with the object**, independent of its layer. This is
deliberately chosen over a layer-name convention: layers stay free for the
user's visual organization, and moving/recoloring/regrouping an object never
breaks the analysis. This is also how Grasshopper and Rhino plugins turn a plain
curve into a "smart" object.

**IFC alignment (forward-looking).** Vanilla Rhino has no native IFC-typed data,
so user text is the right carrier today. But we should keep the door open to a
future IFC bridge by naming tags after IFC structural concepts where sensible —
e.g. supports map to `IfcStructuralPointConnection`, loads to
`IfcStructuralLoadSingleForce`, members to `IfcStructuralCurveMember`. If a
better native carrier appears (an IFC-enabled object type via VisualARQ or a
future Rhino feature), the schema can migrate to it without changing the
geometry-vs-tags principle.

## The tag schema (`stm.*` namespace)

Encoded as Rhino object user text. Draft — names not final.

| Object kind | Geometry | Tags |
|---|---|---|
| Member | curve (line/polyline) | `stm.kind=member` preferred; an untagged curve falls back to a member |
| Support | block instance (or point) | `stm.kind=support`, `stm.fix_*` DOF flags (see below) |
| Load | line / arrow | `stm.kind=load`, `stm.kips=600` (direction from the line's vector) |

**Members:** tagging `stm.kind=member` is the explicit, preferred form, but the
importer treats any untagged curve as a member so quick sketches still work.

**Support fixity — store 6-DOF, consume the 2D subset.** Even though the current
STM solver is a 2D pin-jointed truss (translational DOF only), the tag schema
records the full set so the same model can later drive frame analysis and the
Midas API (true 3D, moving loads) without re-authoring:

`stm.fix_x`, `stm.fix_y`, `stm.fix_z`, `stm.fix_rx`, `stm.fix_ry`, `stm.fix_rz`
(booleans). A friendly `stm.support=pin|roller-v|roller-h|fixed|custom` sets the
common cases; explicit `stm.fix_*` flags override for custom fixity. The STM
importer reads only the in-plane translations (`fix_x`, `fix_y`); the rest is
forward-compatible metadata.

Nodes are **not** authored explicitly. They are derived by snapping member
endpoints together within a tolerance, deduping, and auto-labeling (A, B, C…
ordered left→right then bottom→top, so labels are stable and read like an
elevation). Supports/loads attach to whichever derived node they coincide with.

### Plane mapping

The model is drawn in the XZ plane (front elevation). The 2D analysis uses
(x, y). Map **X → x, Z → y**, with gravity = −Z. The importer should detect the
working plane rather than hard-coding it.

## Automatic visual representation

The feature we want: declaring an object's *kind* should produce the right
*symbol* automatically — a load is an arrow oriented with the force, a pin is a
triangle, a roller is a circle, a fixed support is a hatched line.

Mechanism options in Rhino:

1. **Block instances as symbols (preferred for supports).** Define a block per
   symbol type (`STM_Pin` triangle, `STM_Roller` circle, `STM_Fixed` hatch,
   `STM_Load` arrow). An inserted instance carries three things `rhino3dm` can
   read: the geometry (the glyph, drawn correctly and automatically), a transform
   (position + rotation → location and direction/skew), and attributes/user text
   (the structural data). Magnitude can scale the block.
2. **Generated symbol geometry from tags.** A "rebuild symbols" script reads tags
   and (re)draws triangle/circle/hatch/arrow geometry on a derived layer. Source
   data stays minimal; symbols are disposable and always consistent. Requires
   running the refresh.
3. **Display conduit (live overlay).** A `Rhino.Display.DisplayConduit` draws
   symbols on screen in real time from tags, without creating saved geometry.
   Most "alive"; most moving parts; overlay isn't persisted as geometry.

**Leaning:** blocks for supports (discrete glyph types; rotation handles skewed
supports cleanly), and loads as a tagged line/arrow (the geometry *is* the
direction, which is more robust than parsing block rotation; magnitude in a tag).

### Authoring commands (run locally in Rhino)

Small RhinoCommon/Python commands make "declare = draw the symbol + stamp the
tags" a single step, e.g.:

- `STMSupport` → pick a point → choose Pin / Roller / Fixed → inserts the correct
  symbol block **and** writes the DOF tags.
- `STMLoad` → pick the node, drag direction, type kips → draws the arrow and
  writes `stm.kips`.

These run in Rhino's script editor with no AI agent at runtime, so they are
compatible with the ODOT environment (see constraints).

## The analysis bridge

The **tagged `.3dm` is the source of truth.** Three possible bridges to Jupyter:

| Bridge | What it is | Cost |
|---|---|---|
| **File round-trip (`rhino3dm`)** | Notebook reads/writes the saved `.3dm`; Rhino and Jupyter stay decoupled. | Tiny pip package; not live (save, then re-run). |
| **Analysis inside Rhino's Python** | Rhino 8 ships CPython 3 + pip; run analysis from the ScriptEditor with full RhinoCommon. | One environment; weaker Jupyter UX; must pip civilpy/numpy into Rhino. |
| **RhinoInside (`rhino-inside`)** | Load full Rhino into normal CPython so the notebook gets RhinoCommon live. | Powerful; heavyweight; licensing + harder IT approval. |

**Decision:** anchor on the **file round-trip via `rhino3dm`** for the analysis
read, even if Rhino is present. It keeps analysis reproducible and decoupled from
whether Rhino is running. Reserve live RhinoCommon for *authoring and visuals*,
not for the analysis read.

Target notebook surface:

```python
model = StrutAndTieModel.from_3dm(r"...\NHI17071_Ex_1.3dm")
model.plot()           # existing matplotlib view
forces = model.forces  # feeds the AASHTO capacity checks unchanged
```

Optional write-back: `results_to_3dm(model, path)` colors members strut/tie and
adds force labels for review in Rhino.

## Constraints

- **ODOT / AI policy:** AI tools (Claude) are prohibited on ODOT machines. The
  constraint is therefore that everything we build must be **self-contained and
  runnable by the user with no AI agent at runtime**, with dependencies tame
  enough for IT approval. It is *not* a statement about Rhino — Rhino is expected
  to be available in the ODOT environment. (This corrects an earlier assumption
  that conflated "no Claude at ODOT" with "no Rhino at ODOT".)
- **Dependencies:** `rhino3dm` is a small pip package; `numpy`/`matplotlib`
  already in use. RhinoInside adds the most approval risk.

## Resolved decisions

1. **Tag carrier:** object user text (`stm.*` namespace), unless a native
   IFC-enabled data type becomes available (see IFC alignment).
2. **Members:** `stm.kind=member` preferred; untagged curves fall back to member.
3. **Symbols:** blocks, with explicit per-DOF fixity overrides; schema stores
   full 6-DOF for future frame/Midas use, STM consumes the 2D subset.
4. **Load magnitude:** tag value (`stm.kips`) with a text label on the arrow.
   Optional later polish: scale the arrow proportionally over a typical band
   (~1–80 kips covers pedestrian to rail axle loads). Minor enhancement.
5. **First build scope:** importer + write-back + authoring commands — but settle
   the authoring-tool question below first.

## Authoring layer: Python scripts vs. compiled plugin

The authoring tools (create a load/support object: insert the symbol block +
stamp the tags) can be delivered two ways. This matters for **accessibility** —
the target audience includes non-programmers (students, intro users) who are
wary of running Python scripts, and a toolbar button labeled "Add Load" is
*1000× more approachable* than "run this script".

| Path | What it is | Pros | Cons |
|---|---|---|---|
| **Python scripts** | RhinoCommon/`rhinoscriptsyntax` run via ScriptEditor; can be aliased to commands and pinned to toolbar buttons. | Fast to prototype; same language as civilpy; validates schema + block geometry quickly. | Distribution/install is manual; users must trust/enable scripts. |
| **C# / .NET plugin** | Compiled `.rhp` (RhinoCommon). Real commands, toolbar buttons, Eto.Forms panels. Distributable via Rhino's **Yak** package manager (`_PackageManager` → install → buttons appear). | Professional, trusted install; native UI buttons; the accessible answer for non-programmers. | Separate C# codebase + build/packaging alongside Python civilpy; two languages. |
| **C++ (Rhino C++ SDK)** | Native plugin. | Maximum performance/SDK access. | Heaviest; **no benefit here over C#** — recommend against. |

**Recommendation:** prototype the command logic in **Python** first (cheap, nails
down the tag schema and block geometry), then port the proven commands to a
**C# RhinoCommon plugin** distributed via Yak for the button-driven UX. C# over
C++ — C++ buys nothing for insert-block + set-user-text commands.

This language split is *validated by the architecture*: because the source of
truth is the tagged `.3dm`, the C# authoring plugin and the Python analysis
never talk directly — they communicate only through the file + tag schema. Each
can be built and versioned independently.

### Mock-up — Python prototype (`STMLoad`)

Illustrative only, not built. Shows the command flow and where tags are stamped.

```python
import Rhino
import scriptcontext as sc

def STMLoad():
    # 1. pick the node the load acts on
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt("Pick loaded node")
    if gp.Get() != Rhino.Input.GetResult.Point:
        return
    node = gp.Point()

    # 2. drag the arrow to set direction
    gd = Rhino.Input.Custom.GetPoint()
    gd.SetCommandPrompt("Drag load direction")
    gd.SetBasePoint(node, True)
    if gd.Get() != Rhino.Input.GetResult.Point:
        return
    tip = gd.Point()

    # 3. magnitude
    gn = Rhino.Input.Custom.GetNumber()
    gn.SetCommandPrompt("Load magnitude (kips)")
    gn.Get()
    kips = gn.Number()

    # 4. insert the arrow block oriented along node->tip, scaled by band
    xform = _orient_and_scale("STM_Load", node, tip, kips)
    iref_id = sc.doc.Objects.AddInstanceObject(_defn("STM_Load"), xform)

    # 5. stamp the tags (the "advanced object")
    obj = sc.doc.Objects.FindId(iref_id)
    a = obj.Attributes
    a.SetUserString("stm.kind", "load")
    a.SetUserString("stm.kips", str(kips))
    sc.doc.Objects.ModifyAttributes(obj, a, True)
    sc.doc.Views.Redraw()
```

### Mock-up — C# plugin command equivalent

```csharp
[CommandStyle(Style.ScriptRunner)]
public class STMLoadCommand : Command
{
    public override string EnglishName => "STMLoad";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        if (RhinoGet.GetPoint("Pick loaded node", false, out Point3d node)
                != Result.Success) return Result.Cancel;
        if (RhinoGet.GetPoint("Drag load direction", false, out Point3d tip)
                != Result.Success) return Result.Cancel;
        double kips = 0;
        if (RhinoGet.GetNumber("Load magnitude (kips)", false, ref kips)
                != Result.Success) return Result.Cancel;

        var xform = OrientAndScale("STM_Load", node, tip, kips);
        var idefIndex = doc.InstanceDefinitions.Find("STM_Load").Index;

        var attr = new ObjectAttributes();
        attr.SetUserString("stm.kind", "load");
        attr.SetUserString("stm.kips", kips.ToString());

        doc.Objects.AddInstanceObject(idefIndex, xform, attr);
        doc.Views.Redraw();
        return Result.Success;
    }
    // A toolbar button just runs "! _STMLoad" — one click for the user.
}
```

The toolbar button (`.rui`) issues `! _STMLoad`, so the end user clicks "Add
Load" and never sees code. Same pattern for `STMSupport` (choose Pin/Roller/Fixed
or set custom DOF) and a future `STMMember`.

## Implementation status (what shipped)

The first build landed on branch `Modeling-Pipeline`:

- **`civilpy.structural.rhino_stm`** — the read/write bridge (optional
  `rhino3dm` dep, `pip install civilpy[rhino]`):
  - `model_from_3dm(path, plane="auto", tol=...)` and the convenience
    `StrutAndTieModel.from_3dm(...)` — reads members (tagged or untagged
    fallback), supports, and loads; derives + labels nodes; detects the plane.
    Understands **both** Rhino-authored block-instance symbols **and** the
    tagged points/lines this package writes. Now parses once into the canonical
    hub and projects to 2D (see S2/S3 below).
  - `read_structural_model(path, plane="auto", tol=...)` (also
    `model_from_3dm(..., as_model=True)`) — reads the same file into the
    canonical `StructuralModel` hub, keeping full 3D coordinates, 6-DOF
    restraints, support presets, stable ids, and 3D load vectors.
  - `model_to_3dm(model, path)` / `StrutAndTieModel.to_3dm(...)` — writes a
    tagged model.
  - `results_to_3dm(model, path)` — solved-model write-back (ties red, struts
    blue, force + reaction text dots).
  - `build_template(path)` — starter `.3dm` with the STM layers.
- **Assets:** `templates/STM_Template.3dm` (layers) and
  `Notebooks/NHI17071_Ex_1_STM.3dm` (the tagged Example 1, round-trip-verified
  against the FHWA worked values — bottom tie 1012.5 kips, vertical tie 600).
- **Authoring prototype:** `src/civilpy/structural/rhino_scripts/stm_authoring.py` — RhinoPython
  `STMTemplate` / `STMSupport` / `STMLoad`, run inside Rhino.
- **Tests:** `tests/structural/test_rhino_stm.py` (skipped without `rhino3dm`).

### rhino3dm constraint that shaped the writer

rhino3dm 8.x's `InstanceDefinitions.Add` corrupts process memory
probabilistically (verified: it segfaults under repeated calls regardless of
curve type, and a cyclic-GC pass during construction triggers it). It is not
safe in a library function. Consequences, all already reflected above:

- The **Python writer emits tagged points (supports) and tagged lines
  (loads/members)** — only the rock-solid `AddLine`/`AddPoint` paths. This still
  honors *geometry spatial, tags scalar*; the arrow line's vector is the force
  direction, `stm.kips` is the magnitude.
- **Symbol *blocks* are created inside Rhino** (RhinoCommon's instance API is
  reliable), by `src/civilpy/structural/rhino_scripts/stm_authoring.py` and, later, the C# plugin —
  ensured on first use, the standard plugin pattern. `build_template` therefore
  ships **layers only**.
- The **reader still parses block-instance symbols**, so models authored with
  the rich Rhino symbols import correctly.

The earlier symbol/glyph mock-ups remain the spec the in-Rhino tools implement.

## Package coherence: the canonical structural model

*This is a long-term architectural track, not a one- or two-PR change. It is
documented here, before more is built, so every increment moves toward a coherent
package instead of adding another disconnected representation. The Rhino work is
the forcing function that surfaced the need, but the payoff is package-wide.*

### The actual goal

The deliverables wanted are **Rhino → STM** and **Rhino → Midas**. Note what both
share: a single Rhino read that must feed *two* different consumers. If each
consumer gets its own bespoke reader, the package fragments. The cohesive answer
is one read into a **canonical structural model**, then independent adapters off
of it:

```
                          ┌──────────────────────────┐
        tagged .3dm  ───► │  canonical StructuralModel │ ───► STM solver (2D view)
        (Rhino)           │  (IFC-aligned vocabulary)  │ ───► Midas payloads → API
        IFC 4.3      ◄──► │  nodes · elements · 6-DOF  │ ───► .3dm write-back (results)
        (from_ifc/        │  restraints · loads ·      │ ───► capacity checks (forces→ratings)
         to_ifc)          │  cases · results · ids     │ ◄──► IFC 4.3 (+ Pset_CivilPy_*)
        MIDAS model  ───► │                            │
        (future read)     └──────────────────────────┘
                                   the hub
```

`Rhino → STM` = read into the hub, project to 2D, solve. `Rhino → Midas` = read
into the **same** hub, serialize to payloads, push. The Rhino reader is written
once; the two adapters never touch each other. This is the same decoupling logic
already used at the file boundary (§Roadmap), pushed one level inward to the
in-memory model.

### What exists today — and the seams

Cross-checking the package, there are **three in-memory representations of "a
structure"**, none of which is shared:

1. **`StrutAndTieModel` / `Truss`** — `nodes{label:(x,y)}`, `members[(a,b)]`,
   `loads{node:[fx,fy]}`, `supports{node:(fix_x,fix_y)}`. **2D, 2-DOF, single
   implicit load case.** Solver = method of joints.
2. **`TrussBridge`** — its *own* 3D node/element generation, typed `Member`
   classes carrying `midas_type` + `expected`, deck/lane/floor load path. Emits
   MIDAS payloads via `midas_payloads()` / `to_midas()`.
3. **MIDAS payload dicts** — `{table:{id:{...}}}`, 3D, 7-char `CONS` DOF strings,
   real element types. Produced independently by `TrussBridge` *and* by
   `midas_models` (curved/bifurcated/abutment/soil-spring builders).

The seams that hurt coherence:

- **Lossy STM model.** `supports` holds only `(fix_x, fix_y)`. The full 6-DOF a
  Midas boundary condition needs exists only in the `.3dm` tags, so a
  Rhino→Midas path that went *through* `StrutAndTieModel` would silently drop
  `fix_z/rx/ry/rz`. Rhino→Midas must therefore **not** route through the 2D STM
  model — another reason for a richer hub.
- **Two Midas serializers.** `TrussBridge.midas_payloads()` and `midas_models.*`
  each encode NODE/ELEM/CONS/UNIT/MATL independently. The CONS-string,
  unit-block, and steel-material encodings are duplicated and can drift.
- **Two node-derivation strategies.** `rhino_stm` snaps/labels nodes from
  geometry; `TrussBridge` generates them from panel geometry. Both legitimately
  exist, but neither produces a shared node object.

### The decision: a data hub + adapters (composition), engines stay separate

**Composition, not a shared solver base class.** The three analysis paradigms in
the package solve genuinely different math — pin-jointed method of joints
(`StrutAndTieModel`/`Truss`/`TrussBridge`), continuous-beam/frame relaxation
(`MomentDistribution`, `pier.solve_continuous_beam`/`MultiColumnBent`), and an
external FEM (`cande.BoxCulvertModel`). Forcing them under one inheritance tree
would couple unrelated algorithms. But they all *describe the same kind of
thing*: a discretized structure with geometry, restraints, loads, and results.

So share the **data**, not the behavior:

- **`StructuralModel`** — a pure data hub (dataclasses: `Node`, `Element`,
  `Restraint` (6-DOF), `Load`, `LoadCase`, `Result`). **3D, full 6-DOF,
  multi-case, stable ids.** No solver lives on it — it is the interchange
  representation, the in-memory analogue of the tagged `.3dm`.
- **Engines consume/produce the hub.** `StrutAndTieModel` keeps its method-of-
  joints solver but gains `from_structural_model(hub)` / `to_structural_model()`
  (a 2D projection in/out). `TrussBridge` becomes a *generator* that emits the
  hub. Solvers never inherit from the hub; they hold or build one.
- **Adapters are pure functions over the hub.** `from_3dm(path) ->
  StructuralModel`, `to_3dm(model)`, `midas_payloads(model)`,
  `push_midas(model, client)`. Each is independently testable with no live
  session, mirroring the existing `midas_models` pure-builder style.
- **The typed `Member` taxonomy migrates onto the hub element's `role`.**
  `TopChord`/`Diagonal`/… and their `midas_type` + `expected` become a `role`
  attribute on `Element`, which simultaneously drives (a) Midas element type and
  (b) which AASHTO capacity check runs. One taxonomy, two uses.
- **Capacity calculators read `Result`, not geometry.** The stateless design side
  (`aashto`, `steel`, `wood`, `concrete`, `section_properties`, the
  `beam_bending` stress helpers) consume forces → ratings. They hang off the
  hub's results, completing the package story: *analysis models produce a hub;
  the hub feeds solvers, exporters, and checks.*

### IFC 4.3 as the hub vocabulary (and where it must be extended)

**Decision: align the hub to the IFC 4.3 `IfcStructuralAnalysisDomain`, and
extend it for the analysis↔design gap via property sets — not a schema fork.**
This continues the IFC alignment already chosen for the `stm.*` tag names
(§Core principle), so the vocabulary is consistent end to end:
**Rhino tag → hub field → IFC entity.**

A common misconception is that IFC is "just visual." Its *structural analysis*
domain is in fact a real linear-idealization schema and covers most of the hub:

| Hub concept | IFC 4.3 entity | Notes |
|---|---|---|
| analysis model | `IfcStructuralAnalysisModel` | 2D/3D container |
| node | `IfcStructuralPointConnection` | |
| support / restraint (6-DOF) | `IfcBoundaryNodeCondition` (+ `…Warping` for the 7th DOF) | maps directly to the MIDAS `CONS` `DX DY DZ RX RY RZ RW` string |
| member (strut/tie/beam) | `IfcStructuralCurveMember` | `PredefinedType`: tie ≈ `TENSION_MEMBER`, strut ≈ `COMPRESSION_MEMBER`, also `PIN_JOINED_MEMBER` / `RIGID_JOINED_MEMBER` |
| plate / wall | `IfcStructuralSurfaceMember` | future (shell models) |
| load case | `IfcStructuralLoadCase` (subtype of `IfcStructuralLoadGroup`) | the `stm.case` tag |
| point load | `IfcStructuralLoadSingleForce(Warping)` via `IfcStructuralPointAction` | |
| line / area load | `IfcStructuralLoadLinearForce` / `…PlanarForce` | |
| result / reaction | `IfcStructuralPointReaction` / `…CurveReaction` in `IfcStructuralResultGroup` | |
| bridge geometry / alignment | `IfcAlignment`, `IfcBridge` | the 4.3 infrastructure additions |

So nodes, **full 6-DOF supports**, members, load cases, and reactions are already
standard — that is the bulk of the canonical hub, for free and interoperable.

**The genuine gaps are the analysis↔design bridge** — which is exactly the STM
and reinforcement territory civilpy is built for:

1. **Reinforcement as analysis input.** `IfcReinforcingBar`, `IfcReinforcingMesh`
   (the rebar *mat*), and `IfcTendon` exist — but in the *physical/detailing*
   model, **not linked as properties of an analysis member**. For STM the tie
   *is* rebar, so this missing association is precisely the one needed.
   → `Pset_CivilPy_TieReinforcement` on the curve member, or an
   `IfcRelAssociates` link to the physical `IfcReinforcingMesh`.
2. **STM nodal-zone semantics** — CCC/CCT/CTT node classification, nodal-zone
   stress limits, bearing/anchorage detail (AASHTO 5.8.2.5). Absent from the
   analysis domain. → `Pset_CivilPy_STMNode`.
3. **Capacity / code-check data** — φFₙ, demand/capacity ratios, governing limit
   state. → `Pset_CivilPy_CapacityCheck` (results, attached to members/nodes).
4. **Vehicular live load / traffic lanes / influence** — IFC analysis carries
   static load cases, not the moving-load + lane concepts the Midas `LLAN` path
   uses (4.3 added the alignment/bridge *infrastructure*, not live-load
   definitions). → `Pset_CivilPy_LiveLoad`, or keep lane data in the Midas
   adapter until a standard emerges.

**Mechanism:** extend through buildingSMART's sanctioned route — `IfcPropertySet`
(`Pset_CivilPy_*`) and `IfcClassificationReference` on standard entities — never a
forked schema. **The hub stays clean civilpy dataclasses** whose field names
mirror these IFC entities; `ifcopenshell` appears only at the `from_ifc`/`to_ifc`
boundary as an optional dependency (`pip install civilpy[ifc]`, mirroring
`[rhino]`), so the solvers never carry a heavy IFC dependency. IFC becomes one
more adapter off the hub, alongside `.3dm` and MIDAS — not the in-memory model
itself.

This adds an IFC spoke to the hub diagram: `from_ifc(path) -> StructuralModel`
and `to_ifc(model, path)`, making civilpy models interoperable with any
IFC-aware tool (Revit, Tekla, SAP2000/ETABS IFC export, Civil NX IFC) while the
`Pset_CivilPy_*` layer carries the reinforcement/STM/design data the standard
omits.

### Scope boundary (deliberate non-goals, for now)

- **Frame/beam and FEM paradigms are not folded in yet.** `MomentDistribution`,
  `pier`, and `cande` stay as-is. But the hub's `Node`/`Element`/`Load`
  vocabulary should be designed general enough that a frame or beam engine
  *could* later consume it — design for it, don't build it.
- **`StrutAndTieModel`'s existing 2D convenience API stays.** Backward
  compatibility is a hard constraint; the hub is added *underneath*, not in place
  of, the current `add_node/add_member` surface. Existing notebooks keep working.

### Incremental, non-breaking migration

Each stage is independently shippable, additive, and leaves all current tests
green. Stop-anywhere ordering:

- [x] **S1 — Define `StructuralModel`** dataclasses (`Node`/`Element`/`Restraint`/
  `Load`/`LoadCase`/`Result`), 3D + 6-DOF + ids + cases. Pure data, fully
  unit-tested. Nothing else changes yet. **→ Shipped (Python):**
  `src/civilpy/structural/structural_model.py` + `tests/structural/
  test_structural_model.py` (27 tests). IFC-aligned field vocabulary;
  `Restraint.to_constraint_string()` emits the MIDAS 7-char `CONS` string,
  `.to_2d()` projects to the STM `(fix_x, fix_y)` subset; `member_type` defaults
  to `auto`; `Units` carried as kips/ft labels (conversion stays in adapters);
  `check()` provides the named pre-solve diagnostics. Resolved open questions:
  name = `StructuralModel`; units = explicit labels, not pint in the hub.
- [x] **S2 — `rhino_stm` reads into the hub. → Shipped.** `rhino_stm.
  read_structural_model(path, plane="auto", tol=...)` (and `model_from_3dm(...,
  as_model=True)`) return the rich hub with full 6-DOF, genuine 3D node
  coordinates, the support preset, stable ids, and full 3D load vectors. A
  single `_read_raw` parser now feeds both the hub reader and the 2D path, so
  the two never drift. This unblocks Rhino→Midas (the 6-DOF fixity the lossy
  `StrutAndTieModel` dropped now survives the read).
- [x] **S3 — STM ↔ hub interconversion. → Shipped.**
  `StrutAndTieModel.from_structural_model(hub, plane="auto")` projects the hub
  to 2D; `.to_structural_model(plane="XZ")` lifts the 2D model back up (carrying
  solved forces/reactions into a `Result`). `model_from_3dm` now parses once
  into the hub and returns `from_structural_model(hub)` — the 2D path is a thin
  projection of the hub, public behavior unchanged (all prior tests green).
- [x] **S4 — One Midas serializer. → Shipped (Python).** Extracted the shared
  encoding into `midas_models` helpers — `STEEL_PROPS`, `unit_block` /
  `unit_block_for(Units)`, `steel_material_block`, `placeholder_section_block`,
  `constraint_assign` — and `TrussBridge` now builds its UNIT/MATL through them
  (output byte-identical, regression-tested). Added
  `midas_models.midas_payloads(StructuralModel)` (pure; emits UNIT/MATL/SECT/
  NODE/ELEM/CONS/STLD/CNLD, mapping the hub's full 6-DOF restraints to the
  `CONS` string and loads to STLD cases + CNLD nodal forces) and
  `push_midas(model, midas=None, **client_kwargs)` (mirrors
  `TrussBridge.to_midas`'s per-table `{"sent": n} | {"error": ...}` report).
  **This is the Rhino→Midas adapter**: `read_structural_model(path)` →
  `push_midas(hub)`, never through the lossy 2D STM model. (CNLD layout follows
  the manual, unverified against a live Civil NX session.)
- [ ] **S5 — Refactor `TrussBridge` onto the shared serializer.** Have
  `TrussBridge.midas_payloads()` build the hub then call the shared serializer,
  collapsing the two Midas encoders into one. Keep its public API and report
  shape identical (regression-test against current output).
- [ ] **S6 — Migrate the `Member` taxonomy to `Element.role`.** Map role →
  `midas_type` and role → capacity check in one place; `TrussBridge` and the hub
  share it.
- [ ] **S7 — Wire capacity checks to `Result`.** A thin path from hub results into
  the existing AASHTO/steel/wood/concrete calculators, so a solved hub can be
  rated without manual force plumbing.
- [ ] **S8 — IFC adapter (optional `[ifc]` dep).** `from_ifc`/`to_ifc` over the
  hub via `ifcopenshell`, mapping the entity table above and reading/writing the
  `Pset_CivilPy_*` extension sets. Pure, fixture-tested against a small committed
  `.ifc`. Independent of S2–S6; can land whenever IFC interop is wanted.
- [ ] **S9 — `Pset_CivilPy_*` extension schema.** Define and document the
  reinforcement (rebar mat/tie), STM nodal-zone, capacity-check, and live-load
  property sets — the analysis↔design data IFC omits. This is the long-tail
  standards work; version it explicitly.

### Risks / open questions to settle as we go

- [x] **Hub vs. an external schema. → Resolved: IFC 4.3-aligned dataclasses.**
  The hub mirrors the `IfcStructuralAnalysisDomain` vocabulary with
  `Pset_CivilPy_*` extensions for the reinforcement/STM/design gap; `ifcopenshell`
  is an optional adapter, not the in-memory model (see §"IFC 4.3 as the hub
  vocabulary"). Remaining sub-question: confirm IFC 4.3's structural-analysis
  entities are unchanged from IFC4 (they are stable; 4.3's additions are the
  alignment/bridge infra) so we can target 4.3 for bridges without losing the
  analysis entities.
- [x] **Naming. → Resolved: `StructuralModel`.** No collision with the existing
  `*Model` classes (`BoxCulvertModel` is unrelated); matches the name used
  throughout this doc.
- [ ] **How far does "general enough for frames" go** before it's speculative
  generality? Bias toward what the truss/STM/Midas paths actually need now.
  (S1 leans lean: 3D coords, 6-DOF restraints, force+moment loads, element
  `role`/`member_type`/`midas_type` — enough for truss/STM/Midas, no shell/FE
  fields yet.)
- [x] **Units in the hub. → Resolved: explicit labels, conversion in adapters.**
  The hub carries a lightweight `Units(force, length)` (default kips/ft); numeric
  conversion stays in adapters (e.g. `midas.convert_node_units` via the
  `civilpy.general.units` pint registry), keeping the hub dependency-light.

## Roadmap and separation of responsibilities

Two codebases are now developed **in parallel** by two agents:

- **Python (this repo, `civilpy`)** — the analysis + file-bridge side. Owner: the
  Python agent.
- **C# / .NET RhinoCommon plugin (separate solution, built in Rider)** — the
  authoring + UI side, distributed via Yak. Owner: the C# agent.

They **never call each other.** The only thing they share is the **tag schema +
file format contract** below. Treat that contract as the API between the two
projects: neither side may change a tag name, value encoding, units convention,
or plane mapping without updating §"Shared contract" *and* notifying the other
agent. This is the whole reason the file-round-trip architecture was chosen — it
lets the two languages ship and version independently.

```
   C# plugin (Rider)              tagged .3dm                Python (civilpy)
   ─────────────────         (source of truth)            ─────────────────
   STMSupport  ─┐                                          ┌─ model_from_3dm
   STMLoad      ├──── writes ──►  stm.* user text  ◄── reads ─┤  solve()
   STMMember   ─┘                 + geometry          writes ─┤  results_to_3dm
   STMResults  ◄──── reads ───────────────────────────────────┘
        ▲                                                       │
        └──────────── (future) Midas API  ◄────────────────────┘
```

### Shared contract (frozen interface — change deliberately)

Both sides MUST agree on all of the following. The Python side is the reference
implementation (`src/civilpy/structural/rhino_stm.py` constants); the C# side
mirrors it.

| Item | Value | Notes |
|---|---|---|
| Tag namespace | `stm.` prefix on all keys | object user text (attribute user strings) |
| Member | `stm.kind=member` | untagged curve also accepted as member |
| Member type | `stm.member=auto\|tie\|strut` | `auto` is the default and is **never written** (absent tag = auto); `tie`/`strut` are optional author overrides |
| Support | `stm.kind=support` | block instance **or** point geometry |
| Support preset | `stm.support=pin\|roller-v\|roller-h\|fixed\|custom` | sets common DOF; `fix_*` overrides win |
| DOF flags | `stm.fix_x/y/z/rx/ry/rz` = `true\|false` | lowercase booleans; full 6-DOF stored |
| Load | `stm.kind=load`, `stm.kips=<float>` | direction from arrow line vector (tip − tail) |
| Units | model unit system = **feet**; forces in **kips** | reader honors `File3dm.Settings.ModelUnitSystem` |
| Plane | drawn in **XZ** (front elevation), gravity = −Z | reader auto-detects; X→x, Z→y |
| Block names | `STM_Pin`, `STM_Roller_V`, `STM_Roller_H`, `STM_Fixed`, `STM_Load` | C# creates them; Python reader maps them back |
| Result colors | tie = red `(200,0,0)`, strut = blue `(0,0,255)` | written by `results_to_3dm`; C# `STMResults` reads/recolors |
| File version | write `.3dm` v7+ | both sides read v5–v8 |

**Open contract questions to resolve jointly before they harden:**

- [ ] **Stable object identity.** Auto-derived node labels (A, B, C…) are
  positional and will renumber if geometry moves. For results write-back and for
  Midas, decide whether the C# plugin stamps a persistent `stm.id` (GUID) on each
  authored object so Python can round-trip results to the *same* object rather
  than by nearest-point. **Recommendation: yes** — cheap on the C# side, removes
  all nearest-node ambiguity. Owner: joint; C# stamps, Python reads/preserves.
- [x] **Member type hint. → Resolved.** `stm.member` is part of the contract with
  values `auto | tie | strut`. **`auto` is the invisible default** — the analysis
  decides from the solved sign (tension = tie, compression = strut), and an
  untagged or `auto` member is never written explicitly (keeps clean models
  clean). `tie` and `strut` are **optional author overrides** that force the
  classification regardless of sign — for detailing intent or to flag a member
  the author expects to behave a certain way. Python: read the hint, honor it for
  display/classification, and warn if a forced `tie` solves in compression (or
  vice-versa) — that mismatch is a useful modeling signal, not an error. C# UI:
  default has no `stm.member` tag; the override is a non-default dropdown choice.
- [ ] **Load combinations / cases.** A `stm.case=<name>` tag so one file can hold
  multiple load cases. Needed before Midas (which is multi-case by nature).
  Defer, but reserve the tag name now.

### Python side — TODO (this repo)

Shipped (see "Implementation status"): `model_from_3dm`, `model_to_3dm`,
`results_to_3dm`, `build_template`, `StrutAndTieModel.from_3dm/.to_3dm`, 8 tests.

**Already in the codebase — reuse, do not rebuild** (verified by cross-checking
`strut_and_tie.py`, `truss.py`, `truss_builder.py`, `midas.py`, `midas_models.py`):

- **Solver-time validation already exists.** `StrutAndTieModel.solve()` raises a
  clear `ValueError` for an indeterminate/unstable model (the
  `members + reactions != 2*nodes` count check) and for singular geometry
  (catches `np.linalg.LinAlgError` → "unstable model geometry"). So the
  "mechanism" item below is an *augmentation*, not a from-scratch build.
- **The MIDAS export idiom already exists.** `TrussBridge.midas_payloads()`
  returns `{table: assign}` bodies and `TrussBridge.to_midas(midas=None,
  **client_kwargs)` sends them table-by-table and returns a per-table
  `{"sent": n} | {"error": ...}` report. **This is the pattern the STM→MIDAS
  adapter must copy** — same method names, same report shape.
- **The CONS constraint-string format is already established:** `TrussBridge`
  writes `"1110000"` (pin) / `"0110000"` (roller) — the 7-char `DX DY DZ RX RY RZ
  RW`. The STM adapter reuses this exact encoding.
- **Unit conversion already has a home:** `midas.convert_node_units` uses
  `civilpy.general.units` (pint). Reuse that pint registry for the inch/mm/m → ft
  read conversion rather than hand-rolling factors.
- **`Truss` *is* `StrutAndTieModel`** (subclass, identical solver/plot). The
  node-snap/auto-label derivation in `rhino_stm` is genuinely unique to the Rhino
  importer — `truss_builder` generates nodes from panel geometry, so there's
  nothing to reuse there. No duplication to remove.

Remaining (revised against the above):

- [ ] **Honor `stm.id` on read/write** once the contract question is resolved —
  preserve a per-object GUID through `from_3dm` → `solve` → `results_to_3dm` so
  results land back on the authored object, not by nearest point.
- [ ] **Read the `stm.member` hint** (`auto` default; `tie`/`strut` override):
  honor a forced classification for display/classification, and warn when a
  forced `tie` solves in compression (or vice-versa) — a modeling signal, not an
  error. Absent tag = `auto` = classify by solved sign.
- [ ] **Load-case support** (`stm.case`): today `add_load` accumulates everything
  into a single implicit case (`self.loads[node] += ...`). Add per-case grouping
  and solve-per-case. Gate behind the contract decision.
- [ ] **Augment validation with pre-solve diagnostics.** The determinacy +
  singular-matrix errors already fire at `solve()`; add *actionable* pre-solve
  checks on top — name the unsupported/dangling node, flag a load on a node with
  no member, distinguish under- vs over-constrained — so an imported Rhino model
  fails with a fixable message, not just the generic count mismatch.
- [ ] **Unit robustness:** convert a file authored in inches/mm/m to feet on read
  (currently assumes feet) via `File3dm.Settings.ModelUnitSystem` **+ the
  existing `civilpy.general.units` pint registry** (mirror
  `midas.convert_node_units`).
- [x] **Preserve full 6-DOF for the MIDAS path. → Done (S2).**
  `StrutAndTieModel.supports` is still lossy `(fix_x, fix_y)`, but
  `read_structural_model` now retains the full `stm.fix_*` as 6-DOF
  `Restraint`s on the hub, so the MIDAS adapter reads from the hub (not the 2D
  model) and `fix_z/rx/ry/rz` reach `CONS` intact.
- [ ] **3D / out-of-plane guard:** detect when geometry is not planar within
  tolerance and warn (the 2D STM solver silently projects today).
- [ ] **Proportional arrow scaling on write** (minor polish): scale the written
  load line over the ~1–80 kip band so `results_to_3dm` reads cleanly.
- [ ] **Tests to add:**
  - [ ] inch/mm/meter file → feet conversion round-trips.
  - [ ] block-instance authored support/load (simulate the C# output) imports
    identically to the tagged-point/line form. *(Build the block instance via a
    fixture `.3dm` committed under `tests/data/`, since rhino3dm can't safely
    create blocks — author it once in Rhino, check it in.)*
  - [ ] `stm.id` preservation through the full round trip (once implemented).
  - [ ] pre-solve diagnostics name the offending node (extends the existing
    determinacy-error test coverage).
  - [ ] STM→MIDAS adapter emits the right `CONS` string from `stm.fix_*` (pure
    payload test, no live session — mirror the `midas_models` test style).
  - [ ] FHWA Example 2 (cantilever bent cap) reproduces published forces.
- [ ] **Example 2** end-to-end in the notebook (cantilever bent cap), mirroring
  Example 1.
- [ ] **Docstrings + a short `docs/` how-to** for the notebook surface.

### C# / .NET plugin side — TODO (separate Rider solution)

The plugin is the accessible authoring front end: toolbar buttons, no scripts.
Port the proven logic from `src/civilpy/structural/rhino_scripts/stm_authoring.py` (the schema + glyph
spec) to RhinoCommon. All commands `[CommandStyle(Style.ScriptRunner)]`.

> **Code organization (mandatory).** Keep UI separate from command logic. Eto
> view/dialog/panel classes live in a `Views/` folder; `Command` subclasses live
> in a `Commands/` folder and contain only orchestration (get input → call a
> service/model → report). **Do not build Eto layouts inline inside
> `RunCommand`** — a command shows a view and acts on its result; it does not
> define the view. Shared schema/glyph/tag logic goes in a third folder (e.g.
> `Core/` or `Stm/`) so both commands and views reuse it. This keeps the
> `stm.*`-stamping logic testable and prevents the dialog code from tangling with
> the document-edit code.

- [~] **Project scaffold:** RhinoCommon plugin targeting Rhino 8 (targets
  `net7.0;net48`), `.rhp` output, Yak build target wired in the `.csproj`, and the
  `Commands/` · `Views/` · `Core/` folder split above. **Done:** folder split,
  both target frameworks build clean (0 warnings), git repo initialized. **Still
  open:** Yak `manifest.yml` + `.rui` toolbar (deferred to the packaging step).
- [x] **`STMTemplate`** — ensure the STM layers and create the symbol block
  definitions (`STM_Pin/Roller_V/Roller_H/Fixed/Load`) on first use. This is the
  command that legitimately uses `InstanceDefinitions.Add` — **safe in C#**,
  which is precisely why block creation lives here and not in Python. **Shipped:**
  `Commands/STMTemplateCommand.cs` (EnglishName `STMTemplate`) →
  `Core/StmDocument.EnsureTemplate`. Layers, glyph geometry, support presets, and
  tag keys are ported 1:1 from `src/civilpy/structural/rhino_scripts/stm_authoring.py` into
  `Core/Stm.cs` + `Core/StmDocument.cs` (the C# mirror of the frozen contract).
- [x] **`STMSupport`** — pick point → choose Pin/Roller-V/Roller-H/Fixed (or
  Custom with a DOF checkbox panel) → insert the correct block → stamp
  `stm.kind=support`, `stm.support`, and the six `stm.fix_*` flags. **Shipped:**
  `Commands/STMSupportCommand.cs` → `Core/StmDocument.AddSupport` /
  `AddCustomSupport`. Type chosen via a command-line option list on the point
  pick; **Custom** is implemented now as 6 Free/Fixed command-line toggles (not
  yet the Eto checkbox panel — that lands with the Views/ panel work). Inserts on
  the `STM::Supports` layer; self-heals by calling `EnsureTemplate` first so it
  works even if `STMTemplate` was never run.
- [x] **`STMLoad`** — pick node → drag direction → enter kips → insert `STM_Load`
  block rotated local +X onto the force direction (the orientation logic the
  Python prototype flagged as "eyeball this"), add a `"<kips> kips"` text label,
  stamp `stm.kind=load`, `stm.kips`. **Shipped:** `Commands/STMLoadCommand.cs` →
  `Core/StmDocument.AddLoad`. Rubber-band direction drag (`DrawLineFromPoint`);
  self-heals via `EnsureTemplate`; guards zero-length direction (→ warn + abort)
  and warns on non-positive / out-of-band (~1–80 kip) magnitudes without blocking.
  `stm.kips` is written with `StmDocument.FormatKips` (invariant '.' decimal,
  trailing zeros trimmed) so the Python `float()` parse never trips on a locale
  comma. Label text dot sits at the unit-glyph arrow tip. Optional proportional
  scaling still deferred (minor polish).
- [ ] **`STMMember`** — draw/select curves, tag `stm.kind=member`. Member type is
  `auto` by default: do **not** write an `stm.member` tag in the default case
  (auto is invisible). Offer `tie`/`strut` as an optional override (a non-default
  dropdown/option) that writes `stm.member=tie|strut` only when chosen.
- [ ] **`STMResults`** (read-back) — load a `results.3dm` (or re-color in place):
  recolor ties red / struts blue and show force labels, per the result-color
  contract. Lets the engineer review Python's output without leaving Rhino.
- [ ] **Stable IDs:** if adopted, stamp `stm.id` (GUID) on every authored object
  and preserve it through edits. *(C# owns minting; Python only reads.)*
- [ ] **Input validation + user feedback (do not assume perfect input).** The
  mock-ups above show the happy path only; real commands must guard every pick
  and tag read, and tell the user what went wrong via `RhinoApp.WriteLine`
  (warning) rather than throwing or silently no-op'ing. Minimum:
  - Cancelled/empty selection (`GetResult` ≠ `Success`, null point) → return
    `Result.Cancel` quietly.
  - Wrong geometry type (e.g. `STMLoad` got a surface, `STMMember` got a point)
    → `RhinoApp.WriteLine("STMMember: select a curve; skipping <id>.")` and skip.
  - **Missing/!malformed tags on a selected object** (e.g. an object with no
    `stm.kind`, or `stm.kips` that won't parse) → warn and skip:
    `RhinoApp.WriteLine("Selected member lacks the stm.kind tag — run STMMember to tag it.")`.
  - Zero-length load direction (tail == tip) → warn, abort that load.
  - Out-of-band magnitude (≤ 0, or far outside the ~1–80 kip band) → warn but
    allow (don't block legitimate edge cases).
  Return `Result.Failure` only on an actual exception; use `Result.Nothing`/
  `Cancel` for user-driven aborts so the command history stays clean.
- [ ] **Eto.Forms panel** (nice-to-have): a dockable panel (in `Views/`) listing
  supports/loads with editable magnitudes/DOF, instead of command-line prompts.
  The panel only reads/writes the model via the shared `Core/` services — no
  document edits in the view code.
- [ ] **Yak packaging + install docs** so a non-programmer does
  `_PackageManager` → install → buttons appear.
- [ ] **Contract conformance test:** author one of each object via the plugin,
  save, and confirm `StrutAndTieModel.from_3dm` reads it identically to the
  hand-tagged fixture. This is the cross-language integration check — keep a
  shared sample `.3dm` both repos test against.

### Rhino → Midas — TODO (future, Python side)

The wanted deliverable is **Rhino → Midas**, not STM → Midas: read the tagged
`.3dm` into the canonical `StructuralModel` (§Package coherence), then serialize
that hub to Midas — *without* routing through the lossy 2D `StrutAndTieModel`
(which would drop `fix_z/rx/ry/rz`). The 6-DOF fixity and reserved load-case tags
exist specifically so the same authored `.3dm` can drive MIDAS Civil NX (true 3D,
moving loads).

**Build on what already exists — do *not* start a new module.** civilpy already
ships the Midas plumbing:

- `civilpy.structural.midas.MidasCivil` — the API client: `get_db`/`put_db`/
  `post_db`/`delete_db`, typed helpers (`nodes`, `put_nodes`, `elements`,
  `put_elements`, `supports`, `put_supports`, `static_loads`, `put_static_loads`,
  `set_units`), document ops (`open`/`analyze`/`save`), results (`result_table`,
  `beam_forces`), and model triage (`summarize`/`capability`). Error/retry
  classes included.
- `civilpy.structural.midas_models` — pure payload builders returning the
  `{id: {...}}` *assign* dicts the API expects (`curved_girder_model`,
  `bifurcated_girder_model`, `abutment_connection`, `soil_spring_supports`).

The conventions already match the STM contract, which is the whole point of the
6-DOF design:

- MIDAS `CONS` boundary conditions use a 7-char flag string `DX DY DZ RX RY RZ
  RW` (`'1'` = fixed). The STM `stm.fix_x/y/z/rx/ry/rz` flags map **directly**
  onto the first six characters (RW/warping = `0`): e.g. a pin
  (`fix_x,fix_y`) → `"110000 0"` → `"1100000"`.
- MIDAS default units are **KIPS / FT** (`set_units`), matching the STM contract.

**There is already a working precedent to copy:** `TrussBridge.midas_payloads()`
+ `TrussBridge.to_midas()` do exactly this for truss bridges — build the
`{table: assign}` bodies (NODE/ELEM/CONS/STLD/…) and push them with a per-table
report. The Rhino→Midas serializer should be the same shape, just driven by the
canonical hub instead of `TrussBridge`'s internal model.

So the work is a **hub → MIDAS serializer** modeled on `TrussBridge`, reusing the
existing client and builders — not a fresh bridge (this is stage **S4** above):

- [x] Add `midas_payloads(StructuralModel)` / `push_midas(model, midas=None,
  **client_kwargs)` mirroring `TrussBridge`'s signatures and per-table report
  shape: emit `NODE` / `ELEM` / `CONS` / `STLD` assign dicts (pure, testable with
  no live session), then push via `MidasCivil.put_db`. **Done (S4):** in
  `midas_models`, sharing the extracted `unit_block`/`steel_material_block`/
  `constraint_assign`/`placeholder_section_block` encoders with `TrussBridge`.
- [x] `Rhino → Midas` end-to-end = `from_3dm(as_model=True)` → `push_midas(...)`;
  no `StrutAndTieModel` in the path. **Done (S4)** — covered by
  `TestRhinoToMidas` in `test_rhino_stm.py`.
- [x] Map `stm.fix_*` (6-DOF) → the `CONS` constraint flag string; map
  `stm.kips` + load direction → an `STLD` static load case + `CNLD` nodal force.
  **Done (S4)** via `Restraint.to_constraint_string()`. `stm.case` → MIDAS load
  case names still pending the load-case tag adoption.
- [ ] Pull results back with the existing `result_table` / `beam_forces`, and
  optionally feed them to `results_to_3dm` for review in Rhino (closing the loop:
  Rhino → civilpy → MIDAS → civilpy → Rhino).
- [ ] Reuse `model_from_3dm` as the front parser — the `.3dm` stays the single
  source of truth; MIDAS is just another consumer of the parsed model.
- [ ] This is where the **3D** geometry (not just the XZ projection) and the full
  6-DOF data finally get consumed — validate the schema carried enough; extend
  the parser to real 3D if STM was projecting.
- [ ] Confirm auth/licensing via the existing `~/secrets.json` `MIDAS_API_KEY`
  path the client already uses (no new auth mechanism needed).

### Quick status board

| Area | Python (civilpy) | C# plugin (Rider) |
|---|---|---|
| File read/write bridge | ✅ shipped | n/a |
| Solve + results write-back | ✅ shipped | reads results (`STMResults`) ☐ |
| Authoring commands | prototype in `src/civilpy/structural/rhino_scripts/` ✅ | `STMTemplate`+`STMSupport`+`STMLoad` ✅; `STMMember/Results` ☐ |
| Symbol block creation | intentionally **not** here (rhino3dm bug) | ✅ `STMTemplate` owns this (`Core/StmDocument`) |
| Stable object IDs | read/preserve ☐ | mint/stamp ☐ |
| Load cases | ☐ | ☐ |
| Validation/diagnostics | solve-time checks ✅; pre-solve diagnostics ☐ | ☐ |
| Canonical `StructuralModel` hub | S1–S4 shipped ✅ (`structural_model.py`, `rhino_stm.read_structural_model`, `StrutAndTieModel.{from,to}_structural_model`, `midas_models.midas_payloads`/`push_midas`); S5–S9 ☐ | n/a |
| IFC 4.3 alignment + `Pset_CivilPy_*` | schema mapping documented ✅; adapter/extension ☐ | n/a |
| Rhino → STM | ✅ shipped (via `model_from_3dm`) | n/a |
| Rhino → Midas | ✅ shipped (`read_structural_model` → `midas_models.push_midas`); shares one encoder with `TrussBridge` | n/a |
| Packaging | pip extra ✅ | Yak ☐ |
