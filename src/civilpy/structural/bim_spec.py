#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Storable parametric Spec records — the BIM system's schema authority.

The queryable-BIM architecture stores every parameter needed to run the
:mod:`civilpy.structural.aashto.lrfd` checks from scratch as a JSON
document (Postgres JSONB on the application side).  This module declares
those records **once**, as plain dataclasses of JSON-safe primitives:

* every field carries its engineering metadata (``unit``, bounds, enum
  options, the checks that consume it) in ``dataclasses.field(metadata=)``
  — one declaration drives validation, documentation, and the
  check-coverage test;
* :func:`record_to_dict` / :func:`record_from_dict` round-trip a record
  through a JSON document with no schema declared anywhere else (add a
  field here and the document simply carries an extra key);
* JSON is not type-checked on write, so :meth:`SpecRecord.validate` is
  the type guarantor — validate before save;
* the record *reconstitutes* the executed-design objects the geometry
  builders in :mod:`civilpy.structural.substructure_layout` consume, so
  a record read back from storage can regenerate geometry, the tagged
  ``.3dm`` emit, and every check input without the session that authored
  it.

The first element modeled end-to-end is the single-column hammerhead
pier (:class:`HammerheadPierRecord`); other substructure types follow
the same pattern.  :data:`HAMMERHEAD_CHECK_INPUTS` is the coverage map
tying each LRFD check consuming a hammerhead to the record fields that
feed it — the test suite walks it, so a check added without a mapped
input path (or a field renamed out from under one) fails loudly instead
of rotting silently.

Units follow the hub convention: layout-scale dimensions in **feet**
(``_ft``), section-scale in **inches** (``_in``), strengths in **ksi**.
"""

from __future__ import annotations

import types
import typing
from dataclasses import MISSING, dataclass, field, fields, is_dataclass

#: Bump when a saved document's meaning changes (not when a field is
#: merely added — additive keys are the point of the JSON substrate).
SCHEMA_VERSION = 1

#: Provenance tiers, element-level (decision 3 of the build plan):
#: per-field overrides ride in ``Provenance.field_sources`` only for
#: manually-entered values where a re-derivation trigger pays off.
SOURCES = ("brr", "plans", "manual")


def spec_field(default=MISSING, *, unit: str | None = None,
               desc: str | None = None, enum: tuple | None = None,
               gt: float | None = None, ge: float | None = None,
               checks: tuple[str, ...] = ()):
    """A dataclass field carrying its engineering metadata: ``unit``,
    bounds (``gt``/``ge``), ``enum`` options, and the article numbers of
    the ``checks`` consuming it.  The metadata rides on the one field
    declaration — validation and the coverage test both read it here."""
    md = {k: v for k, v in dict(unit=unit, desc=desc, enum=enum, gt=gt,
                                ge=ge, checks=checks).items()
          if v is not None and v != ()}
    if default is MISSING:
        return field(metadata=md)
    return field(default=default, metadata=md)


# ── serialization / validation base ───────────────────────────────────────

_JSON_SCALARS = (str, int, float, bool)


def _strip_optional(tp):
    """``X | None`` -> ``X`` (unchanged when not an optional)."""
    if typing.get_origin(tp) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


def record_to_dict(rec) -> dict:
    """Flatten a record to JSON-safe primitives (nested dicts/lists)."""
    def conv(v):
        if is_dataclass(v):
            return {f.name: conv(getattr(v, f.name)) for f in fields(v)}
        if isinstance(v, (tuple, list)):
            return [conv(x) for x in v]
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        return v
    return conv(rec)


def record_from_dict(cls, data: dict):
    """Rebuild ``cls`` from :func:`record_to_dict` output (tuples restored,
    nested records recursed via the type hints — the single schema)."""
    hints = typing.get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        v = data[f.name]
        tp = _strip_optional(hints[f.name])
        origin = typing.get_origin(tp)
        if v is None:
            kwargs[f.name] = None
        elif is_dataclass(tp):
            kwargs[f.name] = record_from_dict(tp, v)
        elif origin is tuple:
            args = typing.get_args(tp)
            inner = args[0] if args else None
            if inner is not None and is_dataclass(inner):
                kwargs[f.name] = tuple(record_from_dict(inner, x) for x in v)
            else:
                kwargs[f.name] = tuple(v)
        else:
            kwargs[f.name] = v
    return cls(**kwargs)


class SpecRecord:
    """Validation mixin: the type guarantor in front of a schema-free
    JSON store.  Checks every field against its annotation and its
    ``spec_field`` metadata (enum membership, ``gt``/``ge`` bounds),
    recursing into nested records.  Returns problem strings;
    ``validate(strict=True)`` raises instead."""

    def validate(self, *, strict: bool = False,
                 _prefix: str = "") -> list[str]:
        problems: list[str] = []
        hints = typing.get_type_hints(type(self))
        for f in fields(self):
            name = f"{_prefix}{f.name}"
            v = getattr(self, f.name)
            tp = _strip_optional(hints[f.name])
            if v is None:
                if hints[f.name] is tp:      # not optional
                    problems.append(f"{name}: required, got None")
                continue
            if is_dataclass(tp):
                if isinstance(v, tp):
                    problems += v.validate(_prefix=f"{name}.")
                else:
                    problems.append(f"{name}: expected {tp.__name__}, "
                                    f"got {type(v).__name__}")
                continue
            if tp in _JSON_SCALARS:
                if tp is float:
                    ok = (isinstance(v, (int, float))
                          and not isinstance(v, bool))
                elif tp is bool:
                    ok = isinstance(v, bool)
                elif tp is int:
                    ok = isinstance(v, int) and not isinstance(v, bool)
                else:
                    ok = isinstance(v, tp)
                if not ok:
                    problems.append(f"{name}: expected {tp.__name__}, "
                                    f"got {type(v).__name__}")
                    continue
            md = f.metadata
            if "enum" in md and v not in md["enum"]:
                problems.append(f"{name}: {v!r} not in {md['enum']}")
            if "gt" in md and isinstance(v, (int, float)) \
                    and v <= md["gt"]:
                problems.append(f"{name}: {v} must be > {md['gt']}")
            if "ge" in md and isinstance(v, (int, float)) \
                    and v < md["ge"]:
                problems.append(f"{name}: {v} must be >= {md['ge']}")
        try:
            problems += [f"{_prefix}{p}" for p in self._cross_validate()]
        except TypeError:
            pass                 # already reported as a type problem above
        if strict and problems:
            raise ValueError("; ".join(problems))
        return problems

    def _cross_validate(self) -> list[str]:
        """Override for multi-field rules (dimension consistency)."""
        return []


# ── provenance ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Provenance(SpecRecord):
    """Where this element's parameters came from.  ``source`` is the
    element-level tier; ``field_sources`` overrides it per field (dotted
    record path -> tier) for manually-entered values; ``doc_id`` /
    ``sheet`` point into the plans document store when
    ``source="plans"`` so a plan revision flags exactly which fields to
    re-verify."""

    source: str = spec_field("manual", enum=SOURCES)
    field_sources: dict | None = spec_field(
        None, desc="dotted path -> source tier")
    doc_id: str | None = spec_field(None, desc="plan_document id")
    sheet: str | None = spec_field(None)


# ── hammerhead pier: the Phase-1 vertical slice ───────────────────────────

@dataclass(frozen=True)
class PierCapRecord(SpecRecord):
    """The executed hammerhead cap design as parameters: overall envelope
    plus the governing STM tie's bar schedule (the outputs of
    :func:`~civilpy.structural.stm_topology.design.optimize_pier_cap`
    that geometry and checks consume — the sweep itself is not stored)."""

    span_ft: float = spec_field(unit="ft", gt=0.0,
                                desc="cap length along the support line")
    depth_ft: float = spec_field(unit="ft", gt=0.0,
                                 checks=("5.7.3.3", "5.6.7"),
                                 desc="full section depth at the column")
    thickness_ft: float = spec_field(unit="ft", gt=0.0,
                                     checks=("5.8.2.5", "5.8.2.6",
                                             "5.7.3.3", "5.7.2.5"),
                                     desc="cap width across the bridge")
    tie_bar_size: int = spec_field(unit="US bar #", ge=4,
                                   checks=("5.8.2.4", "5.6.7",
                                           "5.10.8.2.1"))
    tie_bar_count: int = spec_field(ge=1, checks=("5.8.2.4",))
    tie_at_top: bool = spec_field(True, desc="hammerhead cantilever: the "
                                  "governing tie is the top chord")
    tip_depth_ft: float | None = spec_field(
        None, unit="ft", gt=0.0,
        desc="soffit taper depth at the cantilever tips; None = prismatic")
    fc_ksi: float = spec_field(4.0, unit="ksi", gt=0.0,
                               checks=("5.8.2.5", "5.7.3.3", "5.7.2.5",
                                       "5.7.2.6", "5.10.8.2.1"))
    fy_ksi: float = spec_field(60.0, unit="ksi", gt=0.0,
                               checks=("5.8.2.4", "5.7.3.3", "5.7.2.5",
                                       "5.6.7", "5.10.8.2.1"))

    def _cross_validate(self):
        if (self.tip_depth_ft is not None
                and self.tip_depth_ft > self.depth_ft):
            return [f"tip_depth_ft: {self.tip_depth_ft} exceeds cap "
                    f"depth {self.depth_ft}"]
        return []


@dataclass(frozen=True)
class PierStemRecord(SpecRecord):
    """The hammerhead stem (single column): section, clear height, and
    the longitudinal steel the executed design carries.  Rectangular
    ``b_in x h_in`` (``b`` along the cap) or circular ``diameter_in``."""

    height_ft: float = spec_field(unit="ft", gt=0.0,
                                  checks=("4.5.3.2.2b",),
                                  desc="clear height, cap soffit to "
                                       "footing top")
    bars_area_in2: float = spec_field(unit="in^2", gt=0.0,
                                      checks=("5.6.4.4", "5.6.4.2",
                                              "5.6.4.5 check"),
                                      desc="total longitudinal steel")
    b_in: float | None = spec_field(None, unit="in", gt=0.0,
                                    checks=("5.6.4.4", "5.6.4.2",
                                            "5.6.4.5 check", "4.5.3.2.2b"))
    h_in: float | None = spec_field(None, unit="in", gt=0.0,
                                    checks=("5.6.4.4", "5.6.4.2",
                                            "5.6.4.5 check", "4.5.3.2.2b"))
    diameter_in: float | None = spec_field(
        None, unit="in", gt=0.0,
        checks=("5.6.4.4", "5.6.4.2", "5.6.4.5 check", "4.5.3.2.2b",
                "5.6.4.6"))
    bar_size: int = spec_field(9, unit="US bar #", ge=4,
                               desc="size the steel area is broken into")
    fc_ksi: float = spec_field(4.0, unit="ksi", gt=0.0,
                               checks=("5.6.4.4", "5.6.4.2",
                                       "5.6.4.5 check", "4.5.3.2.2b",
                                       "5.6.4.6"))
    fy_ksi: float = spec_field(60.0, unit="ksi", gt=0.0,
                               checks=("5.6.4.4", "5.6.4.2",
                                       "5.6.4.5 check"))
    spiral: bool = spec_field(False, checks=("5.6.4.4", "5.6.4.6"))
    fixity: str = spec_field("fixed-fixed",
                             enum=("fixed-fixed", "fixed-free"),
                             checks=("4.5.3.2.2b",))

    def _cross_validate(self):
        rect = self.b_in is not None and self.h_in is not None
        circ = self.diameter_in is not None
        if rect == circ:
            return ["give either b_in+h_in or diameter_in"]
        return []


@dataclass(frozen=True)
class FootingRecord(SpecRecord):
    """Spread-footing plan dims — a geotech deliverable, explicit inputs
    (mirrors :class:`~civilpy.structural.substructure_layout.FootingSpec`)."""

    length_ft: float = spec_field(unit="ft", gt=0.0,
                                  desc="along the cap axis")
    width_ft: float = spec_field(unit="ft", gt=0.0)
    thickness_ft: float = spec_field(unit="ft", gt=0.0)


@dataclass(frozen=True)
class CapDetailingRecord(SpecRecord):
    """Cap/stem detailing outside the STM schedule: covers, the shear
    stirrups the sectional checks run with, the D-region crack-control
    grid (5.8.2.6), and the bearing-seat plan side the node faces bear
    on."""

    cover_in: float = spec_field(3.0, unit="in", gt=0.0,
                                 checks=("5.6.7", "5.7.3.3"))
    stirrup_size: int = spec_field(5, unit="US bar #", ge=3,
                                   checks=("5.7.3.3", "5.7.2.5",
                                           "5.8.2.6"))
    stirrup_spacing_in: float = spec_field(12.0, unit="in", gt=0.0,
                                           checks=("5.7.3.3", "5.7.2.5",
                                                   "5.7.2.6", "5.8.2.6"))
    skin_bar_size: int = spec_field(5, unit="US bar #", ge=3,
                                    checks=("5.8.2.6",))
    skin_bar_spacing_in: float = spec_field(12.0, unit="in", gt=0.0,
                                            checks=("5.8.2.6",))
    seat_side_in: float = spec_field(27.0, unit="in", gt=0.0,
                                     checks=("5.8.2.5",),
                                     desc="bearing-seat plan side = node "
                                          "face bearing dimension")


@dataclass(frozen=True)
class HammerheadPierRecord(SpecRecord):
    """One hammerhead pier as a storable parametric record — the Phase-1
    vertical slice of the queryable-BIM schema.  ``standard`` +
    ``standard_year`` key the standards-catalog defaults lookup;
    :meth:`build` reconstitutes the geometry-builder spec so a record
    read back from storage regenerates placement, the tagged ``.3dm``
    emit, and the check inputs in :data:`HAMMERHEAD_CHECK_INPUTS`."""

    pier_cap: PierCapRecord
    pier_stem: PierStemRecord
    footing: FootingRecord | None = None
    detailing: CapDetailingRecord | None = spec_field(None)
    standard: str | None = spec_field(None, desc="ODOT standard drawing id")
    standard_year: int | None = spec_field(None, ge=1900)
    provenance: Provenance | None = spec_field(None)

    #: identity keys stamped into the flattened document
    BIM_TYPE = "pier"
    SUBTYPE = "hammerhead"

    def __post_init__(self):
        if self.detailing is None:
            object.__setattr__(self, "detailing", CapDetailingRecord())
        if self.provenance is None:
            object.__setattr__(self, "provenance", Provenance())

    # ── document round-trip ──────────────────────────────────────────
    def to_dict(self) -> dict:
        """The JSONB document: identity keys + flattened fields."""
        return {"bim.type": self.BIM_TYPE, "subtype": self.SUBTYPE,
                "schema_version": SCHEMA_VERSION, **record_to_dict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "HammerheadPierRecord":
        if data.get("bim.type", cls.BIM_TYPE) != cls.BIM_TYPE or \
                data.get("subtype", cls.SUBTYPE) != cls.SUBTYPE:
            raise ValueError(
                f"not a {cls.BIM_TYPE}/{cls.SUBTYPE} document: "
                f"{data.get('bim.type')}/{data.get('subtype')}")
        return record_from_dict(cls, data)

    # ── reconstitution: record -> executed-design objects ────────────
    def to_pier_column(self):
        """The :class:`~civilpy.structural.pier.PierColumn` the geometry
        builder consumes, carrying the stored steel as one layer at
        cover (geometry needs only the total; run the P-M checks with a
        real ring via :func:`stem_rebar_layers`)."""
        from civilpy.structural.pier import PierColumn
        from civilpy.structural.aashto.lrfd.columns import RebarLayer

        s = self.pier_stem
        return PierColumn(
            height=s.height_ft * 12.0,
            layers=[RebarLayer(area=s.bars_area_in2,
                               depth=self.detailing.cover_in)],
            f_c=s.fc_ksi, f_y=s.fy_ksi, b=s.b_in, h=s.h_in,
            diameter=s.diameter_in, spiral=s.spiral, fixity=s.fixity)

    def to_cap_design(self):
        """A :class:`~civilpy.structural.stm_topology.design.PierCapDesign`
        carrying the stored envelope + tie schedule (the record is the
        design's *output*; the optimizer sweep is not replayed)."""
        from types import SimpleNamespace

        from civilpy.structural.stm_topology.design import (
            DepthCandidate, PierCapDesign)

        c = self.pier_cap
        tie_y = c.depth_ft - 0.2 if c.tie_at_top else 0.2
        tie = SimpleNamespace(force=0.0, bar_size=c.tie_bar_size,
                              bar_count=c.tie_bar_count, member=("A", "B"))
        result = SimpleNamespace(
            report=SimpleNamespace(ties=[tie]),
            model=SimpleNamespace(nodes={"A": (0.0, tie_y),
                                         "B": (c.span_ft, tie_y)}))
        cand = DepthCandidate(depth=c.depth_ft, cost=0.0, concrete_cost=0.0,
                              steel_lb=0.0, strut_angle=0.0, node_ratio=0.0,
                              max_tie=0.0, complete=True, feasible=True,
                              result=result)
        return PierCapDesign(optimal=cand, candidates=[cand],
                             span=c.span_ft, thickness=c.thickness_ft)

    def build(self, layout, unit, **frame_kw):
        """Place the pier under ``layout`` — the same contract as the
        specs :func:`~civilpy.structural.substructure_layout
        .assemble_substructure` consumes, so a stored record slots
        straight into the emit pipeline."""
        from civilpy.structural.substructure_layout import (
            FootingSpec, HammerheadSpec)

        ftg = None
        if self.footing is not None:
            ftg = FootingSpec(length_ft=self.footing.length_ft,
                              width_ft=self.footing.width_ft,
                              thickness_ft=self.footing.thickness_ft)
        return HammerheadSpec(
            cap_design=self.to_cap_design(), column=self.to_pier_column(),
            tip_depth_ft=self.pier_cap.tip_depth_ft,
            footing=ftg).build(layout, unit, **frame_kw)


def stem_rebar_layers(record: HammerheadPierRecord, n_layers: int = 2):
    """Break the stored stem steel into strain-compatibility layers for
    the P-M checks: half at each face, ``cover`` from the extreme
    fibers (the conventional two-layer idealization of a ring)."""
    from civilpy.structural.aashto.lrfd.columns import RebarLayer

    s = record.pier_stem
    depth = s.diameter_in if s.diameter_in is not None else s.h_in
    c = record.detailing.cover_in
    per = s.bars_area_in2 / n_layers
    return [RebarLayer(area=per,
                       depth=c + (depth - 2.0 * c) * k / (n_layers - 1))
            for k in range(n_layers)]


# ── metrics sidecar ───────────────────────────────────────────────────────

def pier_metrics(geom) -> dict:
    """Derived metrics for one placed pier
    (:class:`~civilpy.structural.substructure_layout.PierGeometry`),
    reported at emit time — civilpy knows the semantic element, so this
    is cheaper and safer than re-measuring meshes.  The application side
    lands these next to the JSONB record and promotes the query-hot ones
    to generated columns."""
    cap = geom.cap
    cols = geom.columns
    m = {
        "cap_length_ft": cap.length_ft,
        "cap_width_ft": cap.width_ft,
        "cap_depth_ft": cap.depth_ft,
        "cap_volume_cy": round(cap.volume_cy, 3),
        "cap_top_elev_ft": cap.origin[2],
        "n_seats": len(geom.seats),
        "n_columns": len(cols),
        "n_piles": len(geom.piles),
    }
    if cap.soffit_profile is not None:
        m["tip_depth_ft"] = min(d for _, d in cap.soffit_profile)
    if cols:
        m["stem_height_ft"] = round(
            max(c.height_ft for c in cols), 3)
        m["stem_volume_cy"] = round(sum(c.volume_cy for c in cols), 3)
        z_lo = min(c.z_bot for c in cols)
    else:
        z_lo = min((p.head[2] - p.length_ft for p in geom.piles),
                   default=cap.origin[2] - cap.depth_ft)
    if geom.footings:
        m["footing_volume_cy"] = round(
            sum(f.volume_cy for f in geom.footings), 3)
        z_lo = min(z_lo, min(f.z_top - f.thickness_ft
                             for f in geom.footings))
    seats_cy = sum((s.side_in / 12.0) ** 2 * (s.height_in / 12.0) / 27.0
                   for s in geom.seats)
    m["concrete_cy"] = round(
        cap.volume_cy + seats_cy
        + sum(c.volume_cy for c in cols)
        + sum(f.volume_cy for f in geom.footings), 3)
    m["height_ft"] = round(cap.origin[2] - z_lo, 3)
    return m


# ── check-coverage map (the §3 forcing function) ──────────────────────────

#: How each LRFD check consuming a hammerhead resolves its inputs.
#: Values are ``("field", "<dotted record path>")`` for a direct read,
#: ``("derived", (<paths>...), "<how>")`` for a value computed from
#: record fields, and ``("loads", "<what>")`` for demand-side inputs
#: that come from the superstructure reactions / analysis, not the
#: element record.  ``tests/structural/test_bim_spec.py`` asserts every
#: required parameter of every listed check is mapped and every mapped
#: path exists on the record schema — a gap is a failing test, i.e. the
#: live backlog of missing parameters.
HAMMERHEAD_CHECK_INPUTS: dict[str, dict[str, tuple]] = {
    # cap D-region (STM)
    "5.8.2.4": {
        "a_st": ("derived", ("pier_cap.tie_bar_size",
                             "pier_cap.tie_bar_count"),
                 "bar area x count"),
        "f_y": ("field", "pier_cap.fy_ksi"),
        "p_u": ("loads", "governing tie force from the STM solve"),
    },
    "5.8.2.5": {
        "a_cn": ("derived", ("pier_cap.thickness_ft",
                             "detailing.seat_side_in"),
                 "node face area: seat side x min(cap width, seat side)"),
        "f_c": ("field", "pier_cap.fc_ksi"),
        "p_u": ("loads", "strut / node face force from the STM solve"),
    },
    "5.8.2.6": {
        "b_w": ("field", "pier_cap.thickness_ft"),
        "s_h": ("field", "detailing.stirrup_spacing_in"),
        "s_v": ("field", "detailing.skin_bar_spacing_in"),
        "a_s_horizontal": ("derived", ("detailing.skin_bar_size",),
                           "two-face skin bar area"),
        "a_s_vertical": ("derived", ("detailing.stirrup_size",),
                         "stirrup legs area"),
    },
    # cap sectional checks away from the D-region
    "5.7.3.3": {
        "b_v": ("field", "pier_cap.thickness_ft"),
        "d_v": ("derived", ("pier_cap.depth_ft", "detailing.cover_in",
                            "pier_cap.tie_bar_size"),
                "effective shear depth from the section"),
        "f_c": ("field", "pier_cap.fc_ksi"),
        "a_v": ("derived", ("detailing.stirrup_size",),
                "stirrup legs area"),
        "s": ("field", "detailing.stirrup_spacing_in"),
        "f_y": ("field", "pier_cap.fy_ksi"),
        "v_u": ("loads", "factored shear at the section"),
    },
    "5.7.2.5": {
        "b_v": ("field", "pier_cap.thickness_ft"),
        "s": ("field", "detailing.stirrup_spacing_in"),
        "f_c": ("field", "pier_cap.fc_ksi"),
        "a_v": ("derived", ("detailing.stirrup_size",),
                "stirrup legs area"),
    },
    "5.7.2.6": {
        "v_u": ("loads", "factored shear at the section"),
        "b_v": ("field", "pier_cap.thickness_ft"),
        "d_v": ("derived", ("pier_cap.depth_ft", "detailing.cover_in",
                            "pier_cap.tie_bar_size"),
                "effective shear depth from the section"),
        "f_c": ("field", "pier_cap.fc_ksi"),
    },
    "5.6.7": {
        "d_c": ("derived", ("detailing.cover_in", "pier_cap.tie_bar_size"),
                "cover + half bar diameter"),
        "h": ("field", "pier_cap.depth_ft"),
        "f_ss": ("loads", "service tie-steel stress"),
    },
    "5.10.8.2.1": {
        "d_b": ("derived", ("pier_cap.tie_bar_size",), "bar diameter"),
        "f_y": ("field", "pier_cap.fy_ksi"),
        "f_c": ("field", "pier_cap.fc_ksi"),
    },
    # stem (compression member)
    "5.6.4.4": {
        "a_g": ("derived", ("pier_stem.b_in", "pier_stem.h_in",
                            "pier_stem.diameter_in"), "gross area"),
        "a_st": ("field", "pier_stem.bars_area_in2"),
        "f_c": ("field", "pier_stem.fc_ksi"),
        "f_y": ("field", "pier_stem.fy_ksi"),
        "spiral": ("field", "pier_stem.spiral"),
        "p_u": ("loads", "factored axial from the cap reactions"),
    },
    "5.6.4.2": {
        "a_g": ("derived", ("pier_stem.b_in", "pier_stem.h_in",
                            "pier_stem.diameter_in"), "gross area"),
        "a_st": ("field", "pier_stem.bars_area_in2"),
        "f_c": ("field", "pier_stem.fc_ksi"),
        "f_y": ("field", "pier_stem.fy_ksi"),
    },
    "5.6.4.5 check": {
        "p_u": ("loads", "factored axial"),
        "m_u": ("loads", "factored (magnified) moment"),
        "layers": ("derived", ("pier_stem.bars_area_in2",
                               "detailing.cover_in", "pier_stem.h_in",
                               "pier_stem.diameter_in"),
                   "stem_rebar_layers()"),
        "f_c": ("field", "pier_stem.fc_ksi"),
        "f_y": ("field", "pier_stem.fy_ksi"),
        "h": ("field", "pier_stem.h_in"),
        "b": ("field", "pier_stem.b_in"),
        "diameter": ("field", "pier_stem.diameter_in"),
        "spiral": ("field", "pier_stem.spiral"),
    },
    "4.5.3.2.2b": {
        "p_u": ("loads", "factored axial"),
        "p_e": ("derived", ("pier_stem.b_in", "pier_stem.h_in",
                            "pier_stem.diameter_in",
                            "pier_stem.height_ft", "pier_stem.fixity",
                            "pier_stem.fc_ksi"),
                "Euler load from cracked EI and effective length"),
        "m_2": ("loads", "larger end moment"),
    },
}


def record_paths(cls) -> set[str]:
    """Every dotted field path reachable on a record class (Optionals
    unwrapped, nested records recursed) — the schema surface the
    coverage test resolves against."""
    out: set[str] = set()
    hints = typing.get_type_hints(cls)
    for f in fields(cls):
        out.add(f.name)
        tp = _strip_optional(hints[f.name])
        if is_dataclass(tp):
            out |= {f"{f.name}.{p}" for p in record_paths(tp)}
    return out
