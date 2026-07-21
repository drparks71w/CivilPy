#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Span-wire traffic signal support analysis (SWISS replacement).

Gravity sag-tension statics for signals and signs hung on messenger wire
between strain poles, plus the ODOT hardware catalog.  Pair with
:mod:`civilpy.structural.aashto.lts` for the LRFD-LTS load side.
"""

from civilpy.structural.spanwire.components import (
    DEFAULT_CODELIST,
    SignalHead,
    SignPanel,
    WireType,
    SpanWireCatalog,
    load_codelist,
)
from civilpy.structural.spanwire.solver import (
    SpanLoad,
    SpanSolution,
    SimpleSpan,
    swiss_design_factor,
    pole_base_moment,
)
from civilpy.structural.spanwire.multispan import (
    BALANCE_TOLERANCE_DEG,
    SegmentDef,
    SegmentResult,
    SystemSolution,
    SpanWireSystem,
)

__all__ = [
    "BALANCE_TOLERANCE_DEG",
    "SegmentDef",
    "SegmentResult",
    "SystemSolution",
    "SpanWireSystem",
    "DEFAULT_CODELIST",
    "SignalHead",
    "SignPanel",
    "WireType",
    "SpanWireCatalog",
    "load_codelist",
    "SpanLoad",
    "SpanSolution",
    "SimpleSpan",
    "swiss_design_factor",
    "pole_base_moment",
]
