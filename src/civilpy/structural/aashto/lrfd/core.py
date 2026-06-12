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

"""Shared result type and article registry for AASHTO LRFD checks.

Units convention for the whole package: kip, inch, ksi (US customary,
matching the dimensional form of the LRFD equations).  All checks are pure
functions — no I/O, no global state — so they can be vectorized or looped
over candidate member sizes.
"""

from dataclasses import dataclass, field

# Registry of check functions keyed by LRFD article number, populated by the
# @article decorator as check modules are imported.
ARTICLES: dict[str, callable] = {}


@dataclass
class CheckResult:
    """Outcome of a single spec-article check.

    ``capacity`` and ``demand`` are in the article's governing unit (stress,
    moment, or force); ``details`` carries the intermediate values an
    engineer would show in hand calcs, keyed by the symbol used in the
    spec.
    """

    article: str
    name: str
    capacity: float
    demand: float | None = None
    phi: float = 1.0
    details: dict = field(default_factory=dict)

    @property
    def factored_capacity(self) -> float:
        return self.phi * self.capacity

    @property
    def ratio(self) -> float | None:
        """Capacity/demand ratio (>= 1.0 passes); None when no demand given."""
        if self.demand is None:
            return None
        if self.demand == 0:
            return float("inf")
        return self.factored_capacity / self.demand

    @property
    def ok(self) -> bool | None:
        if self.demand is None:
            return None
        return self.ratio >= 1.0


def article(number: str, name: str):
    """Register a check function under its LRFD article number."""

    def decorator(func):
        func.article_number = number
        func.article_name = name
        ARTICLES[number] = func
        return func

    return decorator
