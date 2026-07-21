#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Span-wire hardware catalog — signal heads, sign panels, messenger wires.

The bundled data (``res/odot_codelist.xml``) is ODOT's SWISS ``CodeList.xml``
(the 2010 "KRD" prototype revision that added backplated signals).  Signal
weights are lb, heights ft, projected areas sq ft; sign weights are psf with
a lb hanger allowance; wire weights are lb per ft.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CODELIST = Path(__file__).parent / "res" / "odot_codelist.xml"


@dataclass(frozen=True)
class SignalHead:
    code: str
    category: str
    sections: int
    lens_size_in: int
    material: str
    weight_lb: float
    height_ft: float
    area_sqft: float


@dataclass(frozen=True)
class SignPanel:
    code: str
    category: str
    weight_psf: float
    hanger_lb: float
    area_factor: float


@dataclass(frozen=True)
class WireType:
    code: str
    category: str
    section: str
    weight_plf: float


@dataclass(frozen=True)
class SpanWireCatalog:
    signals: dict[str, SignalHead]
    signs: dict[str, SignPanel]
    wires: dict[str, WireType]


def _text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    if child is None or child.text is None:
        raise ValueError(f"catalog entry missing <{tag}>")
    return child.text.strip()


def load_codelist(path: str | Path = DEFAULT_CODELIST) -> SpanWireCatalog:
    """Parse a SWISS ``CodeList.xml`` into a :class:`SpanWireCatalog`.

    The legacy file declares UTF-8 but may actually be cp1252 (its comments
    contain em dashes), so decoding falls back accordingly.
    """
    raw = Path(path).read_bytes()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        text = raw.decode("cp1252")
        # Drop the XML declaration so the re-decoded string parses cleanly.
        if text.lstrip().startswith("<?"):
            text = text[text.index("?>") + 2 :]
        root = ET.fromstring(text)

    signals = {}
    for el in root.iter("SIGNAL"):
        signal = SignalHead(
            code=_text(el, "CODE"),
            category=_text(el, "CATEGORY"),
            sections=int(_text(el, "SECTIONS")),
            lens_size_in=int(_text(el, "LENS_SIZE")),
            material=_text(el, "MATERIAL"),
            weight_lb=float(_text(el, "WEIGHT")),
            height_ft=float(_text(el, "HEIGHT")),
            area_sqft=float(_text(el, "AREA")),
        )
        signals[signal.code] = signal

    signs = {}
    for el in root.iter("SIGN"):
        sign = SignPanel(
            code=_text(el, "CODE"),
            category=_text(el, "CATEGORY"),
            weight_psf=float(_text(el, "WEIGHT")),
            hanger_lb=float(_text(el, "HANGER")),
            area_factor=float(_text(el, "AREA_FACTOR")),
        )
        signs[sign.code] = sign

    wires = {}
    for el in root.iter("WIRE"):
        wire = WireType(
            code=_text(el, "CODE"),
            category=_text(el, "CATEGORY"),
            section=_text(el, "SECTION"),
            weight_plf=float(_text(el, "WEIGHT")),
        )
        wires[wire.code] = wire

    return SpanWireCatalog(signals=signals, signs=signs, wires=wires)


__all__ = [
    "DEFAULT_CODELIST",
    "SignalHead",
    "SignPanel",
    "WireType",
    "SpanWireCatalog",
    "load_codelist",
]
