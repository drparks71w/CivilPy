#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Preliminary bridge-type feasibility and selection advisor.

The first gate of the conceptual-design loop: given a span arrangement, say
which superstructure types are *reasonable* and steer the engineer away from
ones that are not.  A 300 ft single span asked of a reinforced concrete slab
has to be redirected to a continuous steel plate girder (or a comparable
long-span type) before any detailing or analysis happens -- that redirect is
the job of :func:`assess`.

This is **planning-level guidance, not a code check.**  The span ranges are
practical/economical envelopes drawn from ODOT BDM Section 302 (structure type
studies) and common AASHTO practice, not hard limits: a type near the edge of
its range is flagged "marginal," and the controlling span (the longest, and for
simple spans the *only* span) is what a type is judged against.  The engineer
still runs the real design; civilpy only keeps the conceptual phase honest.

Pure Python (no numpy/heavy deps) so it runs anywhere the rest of the
station/offset stack does, including Rhino's bundled CPython.

Conventions: spans in feet, one entry per span in ``spans_ft`` (a single-span
bridge is ``[L]``).  A type is "continuous" if it carries negative moment over
interior supports; single-span or simple-span-made-continuous-for-live-load
types are marked accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── the catalog ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BridgeType:
    """One superstructure family and the span envelope it is economical in.

    ``min_span_ft`` / ``max_span_ft`` bound a *single span* of this type;
    ``max_span_ft`` is the practical/economical ceiling, above which the type
    is infeasible (not merely uneconomical).  ``needs_continuity`` marks types
    that only reach their upper range as a continuous unit (so a single-span
    request is capped lower, at ``simple_max_span_ft``).
    """

    key: str
    name: str
    material: str                       # "concrete", "prestressed", "steel"
    min_span_ft: float
    max_span_ft: float
    simple_max_span_ft: float | None = None   # cap when used as a single span
    needs_continuity: bool = False
    note: str = ""

    def simple_ceiling_ft(self) -> float:
        """Economical single-span ceiling (falls back to ``max_span_ft``)."""
        if self.simple_max_span_ft is not None:
            return self.simple_max_span_ft
        return self.max_span_ft


#: Common ODOT superstructure types, ordered short-span to long-span.  Ranges
#: are conceptual-design envelopes (ODOT BDM 302 / AASHTO practice), deliberately
#: generous at the top; see the module docstring.
CATALOG: tuple[BridgeType, ...] = (
    BridgeType(
        "rc_slab", "Reinforced concrete slab (single span)", "concrete",
        min_span_ft=11.0, max_span_ft=40.0, simple_max_span_ft=40.0,
        note="ODOT SB-1-24 covers 11-38 ft; reinforced slab gets uneconomical "
             "and heavy past ~40 ft.",
    ),
    BridgeType(
        "rc_slab_cont", "Continuous reinforced concrete slab", "concrete",
        min_span_ft=20.0, max_span_ft=60.0, simple_max_span_ft=40.0,
        needs_continuity=True,
        note="ODOT CS-1-24; negative moment over piers extends the slab to "
             "~60 ft interior spans.",
    ),
    BridgeType(
        "adjacent_box", "Prestressed adjacent box beams", "prestressed",
        min_span_ft=20.0, max_span_ft=100.0,
        note="Shallow, fast to erect; adjacent-box distribution + transverse "
             "post-tensioning.",
    ),
    BridgeType(
        "ps_i_girder", "Prestressed I-girder, composite deck", "prestressed",
        min_span_ft=40.0, max_span_ft=160.0,
        note="AASHTO/ODOT I-beams; made continuous for live load over piers.",
    ),
    BridgeType(
        "steel_rolled", "Steel rolled-beam, composite deck", "steel",
        min_span_ft=40.0, max_span_ft=120.0,
        note="Rolled W-shapes; economical single or continuous spans.",
    ),
    BridgeType(
        "steel_plate_girder", "Continuous steel plate girder, composite deck",
        "steel", min_span_ft=90.0, max_span_ft=400.0, simple_max_span_ft=180.0,
        needs_continuity=True,
        note="Welded plate girders with field splices and flange transitions; "
             "the workhorse long-span type.",
    ),
)

_BY_KEY = {t.key: t for t in CATALOG}


def get_type(key: str) -> BridgeType:
    """Look up a catalog type by key; ``KeyError`` with the valid keys if bad."""
    try:
        return _BY_KEY[key]
    except KeyError:
        raise KeyError(
            f"unknown bridge type {key!r}; valid keys: "
            + ", ".join(_BY_KEY)) from None


# ── feasibility ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Feasibility:
    """How a single type scores against a span arrangement."""

    type: BridgeType
    verdict: str                # "ok" | "marginal" | "infeasible"
    controlling_span_ft: float
    continuous: bool
    reasons: tuple[str, ...] = ()

    @property
    def feasible(self) -> bool:
        return self.verdict != "infeasible"


def _controlling_span(spans_ft) -> float:
    if not spans_ft or any(s <= 0 for s in spans_ft):
        raise ValueError("spans_ft must be a non-empty list of positive spans")
    return float(max(spans_ft))


def evaluate_type(bt: BridgeType, spans_ft, *,
                  marginal_band: float = 0.10) -> Feasibility:
    """Score one type against ``spans_ft``.

    A single-span arrangement (``len(spans_ft) == 1``) is judged against the
    type's *simple* ceiling; a multi-span arrangement lets continuous types use
    their full range.  Within ``marginal_band`` (fraction) of either end of the
    range the verdict is "marginal" rather than "ok".
    """
    span = _controlling_span(spans_ft)
    continuous = len(spans_ft) > 1
    ceiling = bt.max_span_ft if continuous else bt.simple_ceiling_ft()
    reasons: list[str] = []
    verdict = "ok"

    if bt.needs_continuity and not continuous:
        reasons.append(
            f"{bt.name} reaches its long spans only as a continuous unit; a "
            f"single {span:.0f} ft span is capped at {ceiling:.0f} ft.")

    if span > ceiling:
        verdict = "infeasible"
        reasons.append(
            f"controlling span {span:.0f} ft exceeds the ~{ceiling:.0f} ft "
            f"ceiling for {bt.name}.")
    elif span < bt.min_span_ft:
        verdict = "infeasible"
        reasons.append(
            f"controlling span {span:.0f} ft is below the ~{bt.min_span_ft:.0f} "
            f"ft floor for {bt.name} (a lighter/cheaper type fits).")
    else:
        lo = bt.min_span_ft + marginal_band * (ceiling - bt.min_span_ft)
        hi = ceiling - marginal_band * (ceiling - bt.min_span_ft)
        if span > hi:
            verdict = "marginal"
            reasons.append(
                f"controlling span {span:.0f} ft is near the top of the "
                f"economical range for {bt.name} (~{ceiling:.0f} ft).")
        elif span < lo:
            verdict = "marginal"
            reasons.append(
                f"controlling span {span:.0f} ft is near the bottom of the "
                f"range for {bt.name}; a shorter-span type may be cheaper.")
        else:
            reasons.append(
                f"controlling span {span:.0f} ft sits comfortably in the "
                f"{bt.min_span_ft:.0f}-{ceiling:.0f} ft range for {bt.name}.")

    return Feasibility(type=bt, verdict=verdict, controlling_span_ft=span,
                       continuous=continuous, reasons=tuple(reasons))


def feasible_types(spans_ft, *, include_marginal: bool = True) -> list[Feasibility]:
    """Every catalog type that is not infeasible for ``spans_ft``, ordered by
    how centered the controlling span sits in each type's range (best first)."""
    scored = [evaluate_type(bt, spans_ft) for bt in CATALOG]
    keep = [f for f in scored
            if f.feasible and (include_marginal or f.verdict == "ok")]

    def centering(f: Feasibility) -> float:
        bt = f.type
        ceiling = bt.max_span_ft if f.continuous else bt.simple_ceiling_ft()
        mid = 0.5 * (bt.min_span_ft + ceiling)
        half = 0.5 * (ceiling - bt.min_span_ft) or 1.0
        # 0 at the range center, ->1 at the edges; "ok" beats "marginal"
        return abs(f.controlling_span_ft - mid) / half + (
            0.0 if f.verdict == "ok" else 0.5)

    return sorted(keep, key=centering)


# ── re-split arrangements (the "make it continuous" redirect) ────────────────

@dataclass(frozen=True)
class Recommendation:
    """A redirect target: a type *and* the span arrangement it wants.

    ``spans_ft`` may differ from what the engineer asked for -- the whole point
    of the long-span redirect is to turn one over-long span into a continuous
    unit of several feasible spans.  ``resplit`` is True when that happened.
    """

    type: BridgeType
    spans_ft: tuple[float, ...]
    verdict: str                # "ok" | "marginal"
    resplit: bool
    reason: str

    def describe(self) -> str:
        if self.resplit:
            n = len(self.spans_ft)
            each = self.spans_ft[0]
            arr = f"{n} spans of ~{each:.0f} ft"
        else:
            arr = "as arranged"
        tag = "" if self.verdict == "ok" else f" ({self.verdict})"
        return f"{self.type.name}{tag}: {arr} -- {self.reason}"


def _equal_split_for(bt: BridgeType, total_ft: float) -> tuple[float, ...] | None:
    """Fewest equal spans of ``bt`` that tile ``total_ft`` inside its range.

    Continuous types need at least two spans; returns ``None`` when no split
    from 1..12 spans lands every span in ``[min_span, max_span]``."""
    lo_n = 2 if bt.needs_continuity else 1
    for n in range(lo_n, 13):
        each = total_ft / n
        # a single span of a continuity-dependent type uses the simple ceiling
        ceiling = bt.max_span_ft if n > 1 else bt.simple_ceiling_ft()
        if bt.min_span_ft <= each <= ceiling:
            return tuple([round(each, 1)] * n)
    return None


def recommend_for_length(total_ft: float, *, exclude: str | None = None,
                         n: int = 3) -> list[Recommendation]:
    """Best types for crossing ``total_ft``, re-splitting into continuous units
    where a single span will not do.  Ranked fewest-spans then most-centered,
    ``ok`` before ``marginal``."""
    out: list[Recommendation] = []
    for bt in CATALOG:
        if bt.key == exclude:
            continue
        spans = _equal_split_for(bt, total_ft)
        if spans is None:
            continue
        f = evaluate_type(bt, spans)
        if not f.feasible:
            continue
        resplit = len(spans) > 1
        reason = (f"continuous {len(spans)}-span unit keeps each span in the "
                  f"{bt.min_span_ft:.0f}-{bt.max_span_ft:.0f} ft range"
                  if resplit else
                  f"single span fits the {bt.min_span_ft:.0f}-"
                  f"{bt.simple_ceiling_ft():.0f} ft range")
        out.append(Recommendation(bt, spans, f.verdict, resplit, reason))

    def rank(r: Recommendation) -> tuple:
        bt = r.type
        ceiling = bt.max_span_ft if len(r.spans_ft) > 1 else bt.simple_ceiling_ft()
        mid = 0.5 * (bt.min_span_ft + ceiling)
        half = 0.5 * (ceiling - bt.min_span_ft) or 1.0
        centering = abs(r.spans_ft[0] - mid) / half
        return (len(r.spans_ft), 0 if r.verdict == "ok" else 1, centering)

    return sorted(out, key=rank)[:n]


# ── the advisor ─────────────────────────────────────────────────────────────

@dataclass
class TypeAssessment:
    """The advisor's answer for a *requested* type against a span arrangement.

    ``allowed`` is True when the requested type is feasible (possibly marginal).
    When it is not, ``recommended`` holds the redirect targets (type + span
    arrangement), best first.
    """

    requested: BridgeType
    spans_ft: tuple[float, ...]
    result: Feasibility
    recommended: tuple[Recommendation, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.result.feasible

    @property
    def verdict(self) -> str:
        return self.result.verdict

    def summary(self) -> str:
        """A human-readable planning message (what the notebook/GH prints)."""
        span = self.result.controlling_span_ft
        arrangement = ("single span" if len(self.spans_ft) == 1
                       else f"{len(self.spans_ft)} spans, max {span:.0f} ft")
        head = f"{self.requested.name} for {arrangement}: {self.verdict.upper()}"
        lines = [head, *("  - " + r for r in self.result.reasons)]
        if not self.allowed and self.recommended:
            lines.append("  Recommended instead:")
            for r in self.recommended:
                lines.append("    * " + r.describe())
        return "\n".join(lines)


def assess(requested_key: str, spans_ft, *, n_recommend: int = 3) -> TypeAssessment:
    """Assess a requested bridge type against a span arrangement and, when it
    is infeasible, recommend the best feasible alternatives -- re-splitting an
    over-long single span into a continuous multi-span unit as needed.

    Parameters
    ----------
    requested_key : str
        Catalog key of the type the engineer wants (see :data:`CATALOG`).
    spans_ft : sequence of float
        Span lengths, feet; ``[L]`` for a single span.  The longest span
        controls type feasibility.
    n_recommend : int
        How many alternatives to return when the request is infeasible.

    Returns
    -------
    TypeAssessment
        ``.allowed`` / ``.verdict`` / ``.summary()`` and, on a redirect,
        ``.recommended`` (:class:`Recommendation` targets, ranked best-first).

    Examples
    --------
    >>> a = assess("rc_slab", [300.0])
    >>> a.allowed
    False
    >>> [r.type.material for r in a.recommended][:1]
    ['steel']
    >>> a.recommended[0].resplit          # 300 ft becomes a continuous unit
    True
    >>> assess("rc_slab", [30.0]).allowed
    True
    """
    bt = get_type(requested_key)
    result = evaluate_type(bt, spans_ft)
    recommended: tuple[Recommendation, ...] = ()
    if not result.feasible:
        # keep the total crossing length; propose types (re-split if needed)
        total = float(sum(spans_ft))
        recommended = tuple(
            recommend_for_length(total, exclude=bt.key, n=n_recommend))
    return TypeAssessment(
        requested=bt, spans_ft=tuple(float(s) for s in spans_ft),
        result=result, recommended=recommended)
