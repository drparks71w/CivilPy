#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Live-load-effect ratio matrices and governing-case identification for
legal-load rating-factor prediction.

A bridge's capacity is the same no matter which truck crosses it, so an
unknown rating factor follows from a known one by scaling with the 1D
live-load effect ratio::

    RF_new = RF_known * (E_known / E_new)

The inventory, however, stores only the final governing RF per vehicle
without saying whether positive moment, negative moment, or shear
controlled — and for continuous bridges the adjacent-span lengths are
unknown too.  Both hidden parameters are recovered by matrix matching:
the empirical relative-RF matrix ``R[i,j] = RF_i / RF_j`` built from the
known vehicles is compared against theoretical demand-ratio matrices
``T[i,j] = E_j / E_i`` for each candidate action (and, for continuous
bridges, each candidate span ratio), and the candidate minimizing the
Frobenius norm of the residual ``R - T`` is the governing case.

Demands come from :class:`~civilpy.structural.continuous_beam.UnitResponses`
envelopes: a simply supported bridge is its longest span; a continuous
bridge is the three-span sub-model ``r*L | L | r*L`` on pinned-roller
supports.  Everything is a pure live-load ratio, so distribution factors,
condition/system factors, and any live-load factor applied uniformly
across vehicles cancel; ``im`` exists for the one loading whose parts it
does not scale uniformly (HL-93's unfactored lane).

Reference: Sung, Khoury, Malloy & Pfingsten, *Methodology for Assigning
Load Factors for AASHTO Rating Vehicle*, ODOT/ORITE draft report,
PID 123396 (2026).  The positive-moment critical-section alignment check
recommended there for spans under ~50 ft is not yet implemented; envelope
peak stations are carried on :class:`DemandBasis` for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

import numpy as np

from civilpy.structural.aashto.vehicles import RATING_VEHICLES
from civilpy.structural.continuous_beam import ContinuousBeam, UnitResponses

#: Structural actions whose demand envelopes can govern a rating.
ACTIONS = ("positive_moment", "negative_moment", "shear")

#: The FHWA-mandated legal trucks whose RFs the method predicts.
NEW_LEGAL_TRUCKS = ("Type 3", "Type 3S2", "Type 3-3")

#: The ten already-rated configurations in the Ohio inventory.
OHIO_KNOWN_VEHICLES = ("HL-93", "HS20", "2F1", "3F1", "4F1", "5C1",
                       "SU4", "SU5", "SU6", "SU7")


@dataclass(frozen=True)
class DemandBasis:
    """Envelope peak demands for a set of vehicles on one beam
    configuration (``span_ratio`` is ``None`` for a simple span).  All
    demands are magnitudes; ``positive_moment_station`` locates each
    vehicle's M+ peak for the critical-section alignment check."""

    span: float
    span_ratio: float | None
    vehicles: tuple
    positive_moment: np.ndarray
    negative_moment: np.ndarray
    shear: np.ndarray
    positive_moment_station: np.ndarray

    def effects(self, action: str, vehicles=None) -> np.ndarray:
        """Demands for ``action``, optionally reordered to ``vehicles``."""
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}; one of {ACTIONS}")
        values = getattr(self, action)
        if vehicles is None:
            return values
        idx = [self.vehicles.index(name) for name in vehicles]
        return values[idx]


def _vehicle_demands(unit: UnitResponses, vehicle, im: float):
    """(M+, |M-|, |V|, M+ station) magnitudes for one catalog vehicle:
    axle envelope times ``1 + im``, plus the unfactored patterned lane
    load where the loading defines one (HL-93)."""
    env = unit.envelope(*vehicle.train())
    m_max = env.moment_max * (1.0 + im)
    m_min = env.moment_min * (1.0 + im)
    v_hi = env.shear_max * (1.0 + im)
    v_lo = env.shear_min * (1.0 + im)
    if vehicle.lane_load_klf:
        lane = unit.envelope([0.0], [0.0], lane_klf=vehicle.lane_load_klf)
        m_max = m_max + lane.moment_max
        m_min = m_min + lane.moment_min
        v_hi = v_hi + lane.shear_max
        v_lo = v_lo + lane.shear_min
    k = int(np.argmax(m_max))
    return (float(m_max[k]), float(max(0.0, -m_min.min())),
            float(max(v_hi.max(), -v_lo.min())), float(env.stations[k]))


@lru_cache(maxsize=512)
def _demand_basis(span: float, span_ratio, vehicles: tuple, step: float,
                  im: float) -> DemandBasis:
    if span_ratio is None:
        beam = ContinuousBeam([0.0, span])
    else:
        r = float(span_ratio)
        beam = ContinuousBeam([0.0, r * span, (1.0 + r) * span,
                               (1.0 + 2.0 * r) * span])
    unit = UnitResponses.from_beam(beam, step=step)
    rows = [_vehicle_demands(unit, RATING_VEHICLES[name], im)
            for name in vehicles]
    m_pos, m_neg, shear, station = (np.array(col) for col in zip(*rows))
    return DemandBasis(span, span_ratio, vehicles, m_pos, m_neg, shear,
                       station)


def simple_span_demands(span: float, vehicles=OHIO_KNOWN_VEHICLES
                        + NEW_LEGAL_TRUCKS, *, step: float = 0.5,
                        im: float = 0.0) -> DemandBasis:
    """Demand basis for a simply supported span of ``span`` ft (results
    are cached per configuration)."""
    return _demand_basis(round(float(span), 3), None, tuple(vehicles),
                         float(step), float(im))


def three_span_demands(max_span: float, span_ratio: float,
                       vehicles=OHIO_KNOWN_VEHICLES + NEW_LEGAL_TRUCKS, *,
                       step: float = 1.0, im: float = 0.0) -> DemandBasis:
    """Demand basis for the continuous three-span sub-model
    ``r*L | L | r*L`` with ``L = max_span`` and ``r = span_ratio``
    (results are cached per configuration)."""
    return _demand_basis(round(float(max_span), 3),
                         round(float(span_ratio), 4), tuple(vehicles),
                         float(step), float(im))


def relative_rf_matrix(rfs) -> np.ndarray:
    """Empirical relative-RF matrix ``R[i,j] = rf[i] / rf[j]`` (unit
    diagonal, reciprocal-symmetric)."""
    v = np.asarray(rfs, dtype=float)
    return v[:, None] / v[None, :]


def demand_ratio_matrix(effects) -> np.ndarray:
    """Theoretical relative-RF matrix from live-load effects: capacity
    cancels, so ``T[i,j] = E_j / E_i`` predicts ``RF_i / RF_j``."""
    e = np.asarray(effects, dtype=float)
    return e[None, :] / e[:, None]


def residual_norm(rfs, effects) -> float:
    """Frobenius norm of ``relative_rf_matrix(rfs) -
    demand_ratio_matrix(effects)`` — the matrix-matching objective."""
    return float(np.linalg.norm(relative_rf_matrix(rfs)
                                - demand_ratio_matrix(effects)))


@dataclass(frozen=True)
class RFPrediction:
    """A predicted rating factor: the average over the known vehicles'
    individually scaled predictions, kept alongside for spread checks."""

    vehicle: str
    rf: float
    per_known: dict

    @property
    def spread(self) -> float:
        """Max minus min of the per-known-vehicle predictions."""
        values = list(self.per_known.values())
        return max(values) - min(values)


@dataclass(frozen=True)
class GoverningCase:
    """Outcome of the matrix-matching identification: the governing
    action, the best-fit span ratio (``None`` for simple spans), the
    residual norms behind the choice, the demand basis at the identified
    configuration, and the predicted RFs for the target vehicles."""

    action: str
    span_ratio: float | None
    norm: float
    norms: dict
    basis: DemandBasis
    known_vehicles: tuple
    predictions: dict
    span_ratios: np.ndarray | None = None
    sweep: dict | None = None   # action -> norm per candidate span ratio


def predict_rating_factors(known_rfs: Mapping, basis: DemandBasis,
                           action: str, targets=NEW_LEGAL_TRUCKS) -> dict:
    """Scale each known RF to each target vehicle through the ``action``
    demand ratio and average: ``RF_t = mean_i(RF_i * E_i / E_t)``."""
    known = tuple(known_rfs)
    e_known = basis.effects(action, known)
    predictions = {}
    for target in targets:
        e_t = basis.effects(action, (target,))[0]
        per = {name: float(rf * e / e_t)
               for name, rf, e in zip(known, known_rfs.values(), e_known)}
        predictions[target] = RFPrediction(
            target, float(np.mean(list(per.values()))), per)
    return predictions


def _clean_known(known_rfs: Mapping) -> dict:
    known = {name: float(rf) for name, rf in known_rfs.items()
             if rf is not None and np.isfinite(rf) and rf > 0.0}
    unknown = sorted(set(known) - set(RATING_VEHICLES))
    if unknown:
        raise KeyError(f"vehicles not in RATING_VEHICLES: {unknown}")
    if len(known) < 2:
        raise ValueError("need at least two known rating factors to form "
                         "a relative-RF matrix")
    return known


def identify_governing_case(known_rfs: Mapping, max_span: float, *,
                            continuous: bool = False, span_ratios=None,
                            targets=NEW_LEGAL_TRUCKS, step: float | None = None,
                            im: float = 0.0) -> GoverningCase:
    """Identify the hidden governing action — and, for continuous
    bridges, the adjacent-span ratio — behind a bridge's known rating
    factors, then predict the target-vehicle RFs from it.

    ``known_rfs`` maps catalog vehicle names to their inventory RFs
    (``None``/NaN/non-positive entries are dropped).  Simple spans match
    positive moment against shear; ``continuous=True`` adds negative
    moment and sweeps ``span_ratios`` (default 1.00-1.80 by 0.01) for the
    global norm minimum across all actions.  ``step`` defaults to 0.5 ft
    for simple spans and 1.0 ft for the continuous sweep.

    >>> basis = simple_span_demands(80.0, ("HS20", "Type 3", "3F1", "SU4"))
    >>> rfs = {n: 900.0 / e for n, e in
    ...        zip(basis.vehicles, basis.shear) if n != "Type 3"}
    >>> case = identify_governing_case(rfs, 80.0)
    >>> case.action, round(case.predictions["Type 3"].rf, 3)
    ('shear', 19.983)
    """
    known = _clean_known(known_rfs)
    names = tuple(known) + tuple(t for t in targets if t not in known)
    rfs = np.array(list(known.values()))
    rf_matrix = relative_rf_matrix(rfs)

    def norms_for(basis):
        actions = ACTIONS if continuous else ("positive_moment", "shear")
        return {a: float(np.linalg.norm(
            rf_matrix - demand_ratio_matrix(basis.effects(a, tuple(known)))))
            for a in actions}

    if not continuous:
        basis = simple_span_demands(max_span, names,
                                    step=0.5 if step is None else step,
                                    im=im)
        norms = norms_for(basis)
        action = min(norms, key=norms.get)
        return GoverningCase(action, None, norms[action], norms, basis,
                             tuple(known),
                             predict_rating_factors(known, basis, action,
                                                    targets))

    ratios = (np.round(np.arange(1.0, 1.8001, 0.01), 2)
              if span_ratios is None else np.asarray(span_ratios, dtype=float))
    step = 1.0 if step is None else step
    sweep = {a: np.empty(ratios.size) for a in ACTIONS}
    bases = []
    for k, r in enumerate(ratios):
        basis = three_span_demands(max_span, r, names, step=step, im=im)
        bases.append(basis)
        for a, n in norms_for(basis).items():
            sweep[a][k] = n
    action = min(sweep, key=lambda a: sweep[a].min())
    k = int(np.argmin(sweep[action]))
    basis = bases[k]
    norms = {a: float(sweep[a][k]) for a in ACTIONS}
    return GoverningCase(action, float(ratios[k]), norms[action], norms,
                         basis, tuple(known),
                         predict_rating_factors(known, basis, action,
                                                targets),
                         span_ratios=ratios, sweep=sweep)
