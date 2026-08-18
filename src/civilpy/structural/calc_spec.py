#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Calculation-package records: an executed set of spec-article checks as a
storable, sign-off-bearing document.

The warehouse-pivot W2 schema space (snbi_ui ``warehouse_pivot.md``): every
check run that a decision rests on becomes a :class:`CalcPackageRecord` —
what was checked (:class:`ArticleCheckRecord` mirrors
:class:`~civilpy.structural.aashto.lrfd.CheckResult` one-for-one), against
which engine/edition, from which stored input records, under whose name.
The application side stores the flattened document (JSONB) and archives the
rendered PDF; this module owns the schema, per the standing rule that the
civilpy Spec is the sole schema authority.

The lifecycle is the record's ``status``: ``draft`` (prepared) → ``checked``
(an independent checker signed) → ``released`` (approved — the application
side freezes the document at this gate).  Validation enforces that a status
never outruns its signatures.
"""
from __future__ import annotations

from dataclasses import dataclass

from civilpy.structural.bim_spec import (
    ElementRecord,
    Provenance,
    SpecRecord,
    spec_field,
)

__all__ = ["ArticleCheckRecord", "CalcPackageRecord"]


def _json_safe(value):
    """Details dicts arrive from check code with numpy scalars and tuples;
    the stored document holds JSON primitives only."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return value
    if hasattr(value, "item"):                 # numpy scalar
        return value.item()
    return str(value)


@dataclass(frozen=True)
class ArticleCheckRecord(SpecRecord):
    """One executed spec-article check, stored.  Mirrors
    :class:`~civilpy.structural.aashto.lrfd.CheckResult` field-for-field —
    plus the derived ``ratio``/``ok`` frozen in, because an archived calc
    must read the same forever even if the derivation logic evolves."""

    article: str = spec_field(desc="spec article number, e.g. 6.10.8.2.2")
    capacity: float = spec_field(unit="article-governing")
    name: str = spec_field("", desc="the article's check name")
    demand: float | None = spec_field(
        None, unit="article-governing",
        desc="None = capacity-only evaluation (no load effect applied)")
    phi: float = spec_field(1.0, gt=0.0)
    ratio: float | None = spec_field(
        None, desc="phi*capacity / demand; >= 1.0 passes; None w/o demand")
    ok: bool | None = spec_field(None)
    details: dict | None = spec_field(
        None, desc="intermediate values keyed by spec symbol (hand-calc "
                   "trail), JSON scalars only")

    @classmethod
    def from_check(cls, result) -> "ArticleCheckRecord":
        """Freeze a live :class:`~civilpy.structural.aashto.lrfd
        .CheckResult` into its stored form."""
        return cls(article=result.article, name=result.name,
                   capacity=float(result.capacity),
                   demand=None if result.demand is None
                   else float(result.demand),
                   phi=float(result.phi),
                   ratio=None if result.ratio is None
                   else float(result.ratio),
                   ok=result.ok,
                   details=_json_safe(result.details) or None)

    def _cross_validate(self):
        problems = [] if self.article.strip() else ["article: blank"]
        if self.demand is not None and self.ratio is None:
            problems.append("ratio: required when a demand is recorded")
        if self.demand is None and self.ok is not None:
            problems.append("ok: meaningless without a demand")
        return problems


@dataclass(frozen=True)
class CalcPackageRecord(ElementRecord):
    """An executed, signable set of article checks for one structure.

    ``input_refs`` names the stored records the run consumed (BridgeElement
    labels like ``"layout"`` / ``"girder-brr"``, or snapshot identifiers) —
    the reproducibility trail.  ``governing()`` is the worst demand-bearing
    check; a package with no demands anywhere is a capacity tabulation and
    has no governing check."""

    title: str = spec_field(desc="what this package demonstrates")
    engine: str = spec_field(desc="e.g. civilpy.structural.aashto.lrfd")
    engine_version: str = spec_field(desc="civilpy release or git rev")
    checks: tuple[ArticleCheckRecord, ...] = spec_field(())
    sfn: str | None = spec_field(None, desc="structure file number")
    spec_edition: str = spec_field(
        "AASHTO LRFD 9th Edition",
        desc="design/rating specification edition the articles cite")
    method: str = spec_field("LRFD", enum=("LRFD", "LRFR", "LFR", "ASR"))
    input_refs: tuple[str, ...] = spec_field(
        (), desc="stored records consumed: BridgeElement labels, "
                 "snapshot ids — the reproducibility trail")
    assumptions: tuple[str, ...] = spec_field(())
    status: str = spec_field("draft", enum=("draft", "checked", "released"))
    prepared_by: str = spec_field("")
    checked_by: str | None = spec_field(None)
    approved_by: str | None = spec_field(None)
    prepared_date: str | None = spec_field(None, desc="ISO YYYY-MM-DD")
    checked_date: str | None = spec_field(None, desc="ISO YYYY-MM-DD")
    approved_date: str | None = spec_field(None, desc="ISO YYYY-MM-DD")
    provenance: Provenance | None = spec_field(None)

    BIM_TYPE = "calc"
    SUBTYPE = "package"

    def __post_init__(self):
        if self.provenance is None:
            object.__setattr__(self, "provenance", Provenance())

    # ── derived reads ────────────────────────────────────────────────
    def governing(self) -> ArticleCheckRecord | None:
        """The demand-bearing check with the lowest capacity/demand ratio."""
        rated = [c for c in self.checks if c.ratio is not None]
        return min(rated, key=lambda c: c.ratio) if rated else None

    @property
    def all_ok(self) -> bool | None:
        """True/False over the demand-bearing checks; None if there are
        none (a capacity tabulation passes nothing and fails nothing)."""
        rated = [c.ok for c in self.checks if c.ok is not None]
        return all(rated) if rated else None

    def _cross_validate(self):
        problems = []
        if not self.title.strip():
            problems.append("title: blank")
        if not self.checks:
            problems.append("checks: at least one article check required")
        # tuple-of-record schedules aren't auto-recursed by validate()
        for i, c in enumerate(self.checks):
            problems += [f"checks[{i}].{p}" for p in c.validate()]
        if self.status in ("checked", "released") and not self.checked_by:
            problems.append(f"checked_by: required for status "
                            f"{self.status!r}")
        if self.status == "released" and not self.approved_by:
            problems.append("approved_by: required for status 'released'")
        return problems
