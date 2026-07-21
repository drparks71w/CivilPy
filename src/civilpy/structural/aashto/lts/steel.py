#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AASHTO LRFD-LTS Section 5 — steel member checks for pole-type supports.

Units follow the aashto package convention: kip, inch, ksi.  Round-tube
flexure mirrors AISC 360 F8 (the source of the LTS provisions); compactness
limits are LTS Table 5.8.2-1.  Productionized from the validated
``Notebooks/Wind Load Calc.ipynb`` LTS-1 proof of concept.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from civilpy.structural.aashto.lts.core import CheckResult, lts_article

E_STEEL = 29_000.0  # ksi


@dataclass(frozen=True)
class RoundTube:
    """Hollow round section, dimensions in inches."""

    od: float
    t: float

    def __post_init__(self):
        if self.t <= 0 or self.od <= 2 * self.t:
            raise ValueError("need od > 2*t > 0")

    @property
    def id(self) -> float:
        return self.od - 2 * self.t

    @property
    def area(self) -> float:
        return math.pi / 4 * (self.od**2 - self.id**2)

    @property
    def inertia(self) -> float:
        return math.pi / 64 * (self.od**4 - self.id**4)

    @property
    def section_modulus(self) -> float:
        return self.inertia / (self.od / 2)

    @property
    def plastic_modulus(self) -> float:
        return (self.od**3 - self.id**3) / 6

    @property
    def radius_of_gyration(self) -> float:
        return math.sqrt(self.inertia / self.area)


@lts_article("5.8.2", "Round tube flexural resistance")
def round_tube_flexural_resistance(
    tube: RoundTube, f_y: float, m_u: float | None = None, phi: float = 0.9
) -> CheckResult:
    """phi*Mn for a hollow round in flexure, kip-in.

    Compactness per LTS Table 5.8.2-1 (``lambda_p = 0.07 E/Fy``); the
    noncompact and slender branches follow AISC 360 F8, with applicability
    capped at ``D/t = 0.45 E/Fy``.
    """
    lam = tube.od / tube.t
    lam_p = 0.07 * E_STEEL / f_y
    lam_r = 0.31 * E_STEEL / f_y
    lam_max = 0.45 * E_STEEL / f_y
    if lam > lam_max:
        raise ValueError(f"D/t = {lam:.1f} exceeds the 0.45E/Fy = {lam_max:.1f} limit")

    if lam <= lam_p:
        slenderness = "compact"
        m_n = f_y * tube.plastic_modulus
    elif lam <= lam_r:
        slenderness = "noncompact"
        m_n = (0.021 * E_STEEL / lam + f_y) * tube.section_modulus
    else:
        slenderness = "slender"
        m_n = (0.33 * E_STEEL / lam) * tube.section_modulus

    return CheckResult(
        article="5.8.2",
        name="Round tube flexural resistance",
        capacity=m_n,
        demand=m_u,
        phi=phi,
        details={
            "D/t": lam,
            "lambda_p": lam_p,
            "lambda_r": lam_r,
            "slenderness": slenderness,
            "S": tube.section_modulus,
            "Z": tube.plastic_modulus,
        },
    )


@lts_article("5.10", "Compression resistance, cantilever column")
def compression_resistance(
    area: float,
    radius_of_gyration: float,
    unbraced_length: float,
    f_y: float,
    k: float = 2.1,
    p_u: float | None = None,
    phi: float = 0.9,
) -> CheckResult:
    """phi*Pn for a column, kips (lengths in inches).

    ``k = 2.1`` is the recommended design value for a cantilever
    (fixed-free) pole.  Column curve per AISC 360 E3, which the LTS
    provisions mirror.
    """
    klr = k * unbraced_length / radius_of_gyration
    f_e = math.pi**2 * E_STEEL / klr**2
    if f_y / f_e <= 2.25:
        f_cr = 0.658 ** (f_y / f_e) * f_y
    else:
        f_cr = 0.877 * f_e
    return CheckResult(
        article="5.10",
        name="Compression resistance, cantilever column",
        capacity=f_cr * area,
        demand=p_u,
        phi=phi,
        details={"KL/r": klr, "Fe": f_e, "Fcr": f_cr},
    )


def moment_magnifier(p_u: float, p_e: float) -> float:
    """Second-order magnifier ``B = 1 / (1 - Pu/Pe)``.

    ``p_e`` is the Euler load on the effective length, kips.
    """
    if p_u >= p_e:
        raise ValueError("Pu >= Pe: member is unstable under second-order effects")
    return 1.0 / (1.0 - p_u / p_e)


@lts_article("5.12.1", "Combined axial and flexural interaction")
def combined_force_interaction(
    p_u: float,
    p_r: float,
    m_u: float,
    m_r: float,
    p_e: float | None = None,
) -> CheckResult:
    """Axial + flexure interaction per Eqs. 5.12.1-2 / 5.12.1-3.

    ``p_r`` and ``m_r`` are factored resistances (phi included).  When
    ``p_e`` is given, the moment term is amplified by the second-order
    magnifier.  Torsion and shear terms drop out for Tu = 0 (a symmetric
    attachment); extend here when a torsion case arises.

    The returned ``CheckResult`` carries the interaction sum as ``demand``
    against a ``capacity`` of 1.0, so ``ok`` reads normally.
    """
    b_mag = 1.0 if p_e is None else moment_magnifier(p_u, p_e)
    if p_u / p_r >= 0.2:
        equation = "5.12.1-2"
        total = p_u / p_r + (8.0 / 9.0) * (b_mag * m_u / m_r)
    else:
        equation = "5.12.1-3"
        total = p_u / (2.0 * p_r) + b_mag * m_u / m_r
    return CheckResult(
        article="5.12.1",
        name="Combined axial and flexural interaction",
        capacity=1.0,
        demand=total,
        phi=1.0,
        details={"B": b_mag, "equation": equation, "Pu/Pr": p_u / p_r},
    )


__all__ = [
    "E_STEEL",
    "RoundTube",
    "round_tube_flexural_resistance",
    "compression_resistance",
    "moment_magnifier",
    "combined_force_interaction",
]
