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

"""The canonical structural model: a pure, IFC-aligned interchange hub.

This is **stage S1** of the package-coherence track documented in
``docs/Rhino Design Philosophy.md``.  It is the in-memory analogue of a tagged
``.3dm`` / an IFC file: a discretized structure (nodes, elements, restraints,
loads, results) carrying **3D geometry, full 6-DOF restraints, multiple load
cases, and stable ids** -- everything the lossy 2D
:class:`~civilpy.structural.strut_and_tie.StrutAndTieModel` throws away.

It holds **no solver**.  By design the package's three analysis paradigms
(pin-jointed method of joints, continuous-beam/frame relaxation, external FEM)
solve different math and stay separate; what they share is this *data*.  The
model is the hub; ``rhino_stm``, the MIDAS serializer, ``.3dm`` write-back, the
future IFC adapter, and the capacity calculators are all spokes off it
(composition, not inheritance).

The vocabulary mirrors the IFC 4.3 ``IfcStructuralAnalysisDomain`` so a future
``from_ifc`` / ``to_ifc`` adapter is a direct mapping (see the entity table in
the design doc):

==================  ===========================================
hub type            IFC 4.3 entity
==================  ===========================================
:class:`Node`       ``IfcStructuralPointConnection``
:class:`Restraint`  ``IfcBoundaryNodeCondition``
:class:`Element`    ``IfcStructuralCurveMember``
:class:`Load`       ``IfcStructuralLoadSingleForce`` (point action)
:class:`LoadCase`   ``IfcStructuralLoadCase``
:class:`Result`     ``IfcStructuralResultGroup`` (reactions / forces)
:class:`StructuralModel`  ``IfcStructuralAnalysisModel``
==================  ===========================================

Units are carried as labels (default **kips / ft**, matching the rest of
``civilpy.structural`` and the Rhino tag contract); actual unit conversion is an
adapter concern (e.g. ``midas.convert_node_units`` already uses the
``civilpy.general.units`` pint registry), so the hub stays dependency-light.

Examples
--------
>>> m = StructuralModel()
>>> a = m.add_node(0, 0, 0, label="A")
>>> b = m.add_node(27, 0, 0, label="B")
>>> _ = m.add_element(a.id, b.id)
>>> m.add_restraint(a.id, preset="pin").to_constraint_string()
'1100000'
>>> m.add_restraint(b.id, preset="roller-v").to_2d()
(False, True)
>>> _ = m.add_load(b.id, fy=-600)
>>> len(m.nodes), len(m.elements), len(m.loads)
(2, 1, 1)
>>> m.check()           # no structural errors in this little model
[]
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace

# ── DOF / restraint conventions ───────────────────────────────────────────────

#: Translational + rotational degrees of freedom, in the order used everywhere
#: in the package -- it matches the ``stm.fix_*`` tag suffixes and the first six
#: characters of the MIDAS ``CONS`` constraint string ``DX DY DZ RX RY RZ RW``.
DOF_NAMES = ("x", "y", "z", "rx", "ry", "rz")

#: ``stm.member`` hint values (contract: ``auto`` is the never-written default;
#: ``tie`` / ``strut`` are optional author overrides).
MEMBER_TYPES = ("auto", "tie", "strut")

#: Friendly support presets, expressed in the **2D analysis-plane** axes the
#: ``stm.support`` contract uses (x = in-plane horizontal, y = in-plane
#: vertical, z = out-of-plane).  An adapter that knows the drawing plane maps
#: these to global 3D DOF; the 2D STM solver consumes ``fix_x`` / ``fix_y``
#: directly.  ``custom`` leaves everything free for explicit ``fix_*`` flags.
SUPPORT_PRESETS = {
    "pin": {"fix_x": True, "fix_y": True},
    "roller-v": {"fix_y": True},
    "roller-h": {"fix_x": True},
    "fixed": {"fix_x": True, "fix_y": True, "fix_rz": True},
    "custom": {},
}


def _new_id() -> str:
    """A fresh stable object id (hex uuid).  Mirrors the ``stm.id`` GUID the C#
    authoring plugin stamps, so ids survive a Rhino -> hub -> Rhino round trip."""
    return uuid.uuid4().hex


# ── Units ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Units:
    """Unit-system *labels* carried with a model (not a converter).

    Defaults match the package convention and the Rhino tag contract (kips /
    feet).  Conversion between systems is an adapter responsibility -- keep the
    hub free of a numeric-units dependency.
    """

    force: str = "kips"
    length: str = "ft"


# ── Geometry / topology ───────────────────────────────────────────────────────


@dataclass
class Node:
    """A connection point -- IFC ``IfcStructuralPointConnection``.

    ``id`` is stable (defaults to a uuid); ``label`` is the human name an
    importer derives (A, B, C…).  Coordinates are full 3D.
    """

    x: float
    y: float
    z: float = 0.0
    label: str | None = None
    id: str = field(default_factory=_new_id)

    @property
    def coords(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class Restraint:
    """A nodal boundary condition -- IFC ``IfcBoundaryNodeCondition``.

    Full 6-DOF booleans (``True`` = fixed).  Built directly or from a
    :data:`SUPPORT_PRESETS` name via :meth:`from_preset`.
    """

    node_id: str
    fix_x: bool = False
    fix_y: bool = False
    fix_z: bool = False
    fix_rx: bool = False
    fix_ry: bool = False
    fix_rz: bool = False
    preset: str | None = None

    @classmethod
    def from_preset(cls, node_id: str, preset: str) -> "Restraint":
        """Build a restraint from a friendly preset (``pin``/``roller-v``/
        ``roller-h``/``fixed``/``custom``)."""
        if preset not in SUPPORT_PRESETS:
            raise ValueError(
                f"unknown support preset {preset!r}; "
                f"choose from {sorted(SUPPORT_PRESETS)}"
            )
        return cls(node_id=node_id, preset=preset, **SUPPORT_PRESETS[preset])

    def flags(self) -> tuple[bool, bool, bool, bool, bool, bool]:
        """The six DOF flags in :data:`DOF_NAMES` order."""
        return (self.fix_x, self.fix_y, self.fix_z,
                self.fix_rx, self.fix_ry, self.fix_rz)

    def to_2d(self) -> tuple[bool, bool]:
        """In-plane translational fixity ``(fix_x, fix_y)`` -- what the 2D
        :class:`StrutAndTieModel` / :class:`Truss` solver consumes."""
        return (self.fix_x, self.fix_y)

    def to_constraint_string(self) -> str:
        """The MIDAS ``CONS`` 7-char flag string ``DX DY DZ RX RY RZ RW``
        (``'1'`` = fixed).  Warping (RW) is always ``0`` here.

        >>> Restraint.from_preset("n", "pin").to_constraint_string()
        '1100000'
        >>> Restraint.from_preset("n", "fixed").to_constraint_string()
        '1100010'
        """
        return "".join("1" if f else "0" for f in (*self.flags(), False))


@dataclass
class Element:
    """A line member between two nodes -- IFC ``IfcStructuralCurveMember``.

    ``role`` is the typed-component taxonomy (e.g. ``member``, ``top_chord``,
    ``diagonal``) that later drives capacity-check routing and the MIDAS element
    type.  ``member_type`` is the ``stm.member`` hint: ``auto`` (default; the
    solver classifies by sign) or a forced ``tie`` / ``strut``.  ``midas_type``
    is the export element type (``TRUSS`` / ``BEAM`` / ``TENS``).
    """

    node_a: str
    node_b: str
    role: str = "member"
    member_type: str = "auto"
    midas_type: str = "TRUSS"
    section: str | None = None
    material: str | None = None
    id: str = field(default_factory=_new_id)

    def __post_init__(self):
        if self.member_type not in MEMBER_TYPES:
            raise ValueError(
                f"member_type must be one of {MEMBER_TYPES}, "
                f"got {self.member_type!r}"
            )


# ── Loads ─────────────────────────────────────────────────────────────────────


@dataclass
class LoadCase:
    """A named load case -- IFC ``IfcStructuralLoadCase``."""

    name: str
    description: str = ""
    factor: float = 1.0


@dataclass
class Load:
    """A nodal force/moment -- IFC ``IfcStructuralLoadSingleForce`` applied via a
    point action.  Full 3D force (and optional moment) vector; ``case`` names the
    :class:`LoadCase` it belongs to (default ``"default"``)."""

    node_id: str
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0
    case: str = "default"
    id: str = field(default_factory=_new_id)

    @property
    def force(self) -> tuple[float, float, float]:
        return (self.fx, self.fy, self.fz)


# ── Results ───────────────────────────────────────────────────────────────────


@dataclass
class Result:
    """Solved results for one load case -- IFC ``IfcStructuralResultGroup``.

    ``element_forces`` maps element id -> axial force (tension positive, the
    package convention).  ``reactions`` maps node id -> a 6-tuple in
    :data:`DOF_NAMES` order.
    """

    case: str = "default"
    element_forces: dict[str, float] = field(default_factory=dict)
    reactions: dict[str, tuple[float, float, float, float, float, float]] = field(
        default_factory=dict
    )


# ── The hub ───────────────────────────────────────────────────────────────────


@dataclass
class StructuralModel:
    """Canonical structural model -- IFC ``IfcStructuralAnalysisModel``.

    A pure data container plus light add/lookup helpers.  No analysis lives
    here; engines and adapters consume or produce it.  Built incrementally:

    >>> m = StructuralModel()
    >>> n = m.add_node(0, 0, label="A")
    >>> m.add_restraint(n.id, preset="pin").to_2d()
    (True, True)
    """

    nodes: dict[str, Node] = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)
    restraints: dict[str, Restraint] = field(default_factory=dict)
    loads: list[Load] = field(default_factory=list)
    load_cases: dict[str, LoadCase] = field(default_factory=dict)
    results: dict[str, Result] = field(default_factory=dict)
    units: Units = field(default_factory=Units)

    # ── Builders ────────────────────────────────────────────────────────────

    def add_node(self, x: float, y: float, z: float = 0.0, *,
                 label: str | None = None, id: str | None = None) -> Node:
        node = Node(float(x), float(y), float(z), label=label,
                    **({"id": id} if id else {}))
        self.nodes[node.id] = node
        return node

    def add_element(self, node_a: str, node_b: str, *, role: str = "member",
                    member_type: str = "auto", midas_type: str = "TRUSS",
                    section: str | None = None, material: str | None = None,
                    id: str | None = None) -> Element:
        for n in (node_a, node_b):
            if n not in self.nodes:
                raise KeyError(f"element references unknown node id {n!r}")
        elem = Element(node_a, node_b, role=role, member_type=member_type,
                       midas_type=midas_type, section=section,
                       material=material, **({"id": id} if id else {}))
        self.elements[elem.id] = elem
        return elem

    def add_restraint(self, node_id: str, *, preset: str | None = None,
                      **flags: bool) -> Restraint:
        """Restrain a node, by ``preset`` and/or explicit ``fix_*`` flags.
        Explicit flags override the preset (matching the tag contract)."""
        if node_id not in self.nodes:
            raise KeyError(f"restraint references unknown node id {node_id!r}")
        if preset is not None:
            restraint = Restraint.from_preset(node_id, preset)
            if flags:
                restraint = replace(restraint, **flags)
        else:
            restraint = Restraint(node_id=node_id, **flags)
        self.restraints[node_id] = restraint
        return restraint

    def add_load(self, node_id: str, *, fx: float = 0.0, fy: float = 0.0,
                 fz: float = 0.0, mx: float = 0.0, my: float = 0.0,
                 mz: float = 0.0, case: str = "default",
                 id: str | None = None) -> Load:
        if node_id not in self.nodes:
            raise KeyError(f"load references unknown node id {node_id!r}")
        if case not in self.load_cases:
            self.load_cases[case] = LoadCase(name=case)
        load = Load(node_id, fx=fx, fy=fy, fz=fz, mx=mx, my=my, mz=mz,
                    case=case, **({"id": id} if id else {}))
        self.loads.append(load)
        return load

    # ── Lookup ──────────────────────────────────────────────────────────────

    def node_by_label(self, label: str) -> Node:
        for node in self.nodes.values():
            if node.label == label:
                return node
        raise KeyError(f"no node labeled {label!r}")

    def loads_in_case(self, case: str = "default") -> list[Load]:
        return [load for load in self.loads if load.case == case]

    def cases(self) -> list[str]:
        """Load-case names actually used by loads (plus any registered)."""
        used = {load.case for load in self.loads} | set(self.load_cases)
        return sorted(used)

    # ── Integrity ─────────────────────────────────────────────────────────────

    def check(self) -> list[str]:
        """Return a list of structural-integrity problems (empty = clean).

        Pure, geometry-level checks an importer can run *before* handing the
        model to a solver -- they name the offending object, unlike the generic
        determinacy error the solver raises later.  Flags: elements pointing at
        missing nodes, restraints/loads on missing nodes, zero-length elements,
        a model with no restraints, and nodes that no element touches.
        """
        problems: list[str] = []
        node_ids = set(self.nodes)
        touched: set[str] = set()

        for eid, e in self.elements.items():
            for n in (e.node_a, e.node_b):
                if n not in node_ids:
                    problems.append(f"element {eid}: unknown node {n!r}")
            touched.update((e.node_a, e.node_b))
            if e.node_a == e.node_b:
                problems.append(f"element {eid}: zero-length (same node both ends)")
            elif e.node_a in node_ids and e.node_b in node_ids:
                if self.nodes[e.node_a].coords == self.nodes[e.node_b].coords:
                    problems.append(f"element {eid}: coincident end nodes")

        for nid in self.restraints:
            if nid not in node_ids:
                problems.append(f"restraint on unknown node {nid!r}")
        for load in self.loads:
            if load.node_id not in node_ids:
                problems.append(f"load {load.id}: unknown node {load.node_id!r}")

        if self.nodes and not self.restraints:
            problems.append("model has no restraints -- it is a mechanism")
        for nid in node_ids - touched:
            label = self.nodes[nid].label or nid
            problems.append(f"node {label}: not connected to any element")

        return problems

    def __repr__(self):
        return (f"<StructuralModel {len(self.nodes)} nodes, "
                f"{len(self.elements)} elements, {len(self.restraints)} "
                f"restraints, {len(self.loads)} loads, "
                f"{len(self.cases())} case(s)>")
