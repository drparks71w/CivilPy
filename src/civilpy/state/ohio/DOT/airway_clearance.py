#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Airway/Highway Clearance Analysis (L&D Vol. 3 §1407.1, 14 CFR Part 77.9).

Pure geometry + rules, no I/O: feed it a site, a set of aviation facilities
(airports / heliports with runway ends) and the heights that will exist at
the site, and it returns which notification surfaces are penetrated, by how
much, and what follows (FAA Form 7460-1, plan note G118A/B/C, the sample
letter of Figure 1407-7, and the 7460-1 point rows of §1407.1.7).

Notification surfaces (Part 77.9(a)(2), restated in L&D §1407.1.2)::

    slope   horizontal reach   facility
    100:1   20,000 ft          airport with any runway longer than 3,200 ft
     50:1   10,000 ft          airport whose longest runway is <= 3,200 ft
     25:1    5,000 ft          heliport (from the landing and takeoff area)

measured "from the nearest point of the nearest runway".  Notification is
also required for anything more than 200 ft above ground level regardless
of airports (Part 77.9(a)(1)).  The surface at the site therefore sits at::

    surface_elev = runway_elev + distance_to_nearest_runway_point / slope

and an object penetrates when ``site_elev + object_height > surface_elev``.

Facility data comes from the FAA NASR subscription (``APT_BASE``,
``APT_RWY``, ``APT_RWY_END`` CSVs); the dataclasses below mirror the
handful of columns needed so callers can build them from any source.

::

    from civilpy.state.ohio.DOT.airway_clearance import (
        Facility, Runway, RunwayEnd, HeightClass, screen)

    result = screen(41.403147, -81.825317, site_elev_ft=819.0,
                    facilities=[cle, ...],
                    heights=[HeightClass("light poles", 30, "appurtenance"),
                             HeightClass("crane", 60, "equipment")])
    result.notification_required        # True for CUY-291-0299
    result.controlling.surface_elev_ft  # 850.4 (CLE 10/28 end 28, 100:1)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date

__all__ = [
    "NM_FT", "MI_FT", "MAX_NOTIFICATION_REACH_FT", "AGL_NOTIFICATION_FT", "MARGINAL_FT",
    "EQUIPMENT_HEIGHTS", "TRAVERSE_WAY_ADJUSTMENTS", "LONG_RUNWAY_FT",
    "Facility", "Runway", "RunwayEnd", "HeightClass", "HeightResult",
    "FacilityResult", "ScreeningResult", "screen", "surface_for",
    "haversine_ft", "nearest_runway_point", "equipment_height_hint",
    "light_pole_height_from_design", "structure_high_point_hint",
    "expected_plan_note", "detect_g118_notes", "analysis_letter",
    "form_7460_rows", "to_dms",
]

NM_FT = 6076.115          # international nautical mile in feet
MI_FT = 5280.0
MAX_NOTIFICATION_REACH_FT = 20000.0   # widest Part 77.9 reach; screening radius
AGL_NOTIFICATION_FT = 200.0            # Part 77.9(a)(1)
LONG_RUNWAY_FT = 3200.0                # Part 77.9(a)(2)(i)/(ii) split
#: §1407.1.7 asks for points accurate to 20 ft vertically; an object whose
#: top is within this of the surface is reported *marginal* and treated as
#: needing notification (the FAA pre-screen decides, not a 1-ft margin).
MARGINAL_FT = 20.0

#: L&D Vol. 3 Figure 1407-3 — maximum operating height of construction
#: equipment by work type (ft) and the controlling equipment.  "Average
#: heights for the specific types of projects ... adjusted as necessary".
EQUIPMENT_HEIGHTS: dict[str, tuple[float | None, str]] = {
    "barrier_construction": (50, "Crane"),
    "bikeways": (25, "Truck"),
    "bridge_painting": (None, "Containment structure (bridge height + 10 ft)"),
    "culverts": (50, "Crane"),
    "deck_overlays": (25, "Truck"),
    "earthwork": (25, "Truck"),
    "guardrail": (25, "Auger"),
    "highway_lighting": (None, "Pole height"),
    "house_demolition": (25, "Excavator"),
    "large_bridges": (100, "Crane"),
    "mowing_landscaping": (10, "Mower"),
    "noise_walls": (25, "Crane"),
    "pavement_marking": (12, "Truck"),
    "pavement_repair": (25, "Raised dump truck"),
    "pile_driving": (50, "Crane"),
    "resurfacing": (25, "Raised dump truck"),
    "rest_areas": (50, "Crane"),
    "slope_repair": (25, "Excavator / grader"),
    "small_bridges": (60, "Crane"),
    "traffic_signals": (50, "Cherry picker"),
    "trash_collection": (25, "Truck"),
}

#: L&D Vol. 3 §1407.1.3 — height added above a traverse way for the
#: vehicles that use it (applies over the traveled way and shoulders).
TRAVERSE_WAY_ADJUSTMENTS: dict[str, float] = {
    "interstate": 17.0,      # interstates, freeways, expressways
    "public_road": 15.0,     # all other public roads and commercial drives
    "private_road": 10.0,
    "railroad": 23.0,
}

#: FAA NASR ``SITE_TYPE_CODE`` values.
SITE_TYPES = {"A": "airport", "H": "heliport", "C": "seaplane base",
              "G": "gliderport", "U": "ultralight", "B": "balloonport"}


# -- data ----------------------------------------------------------------------

@dataclass
class RunwayEnd:
    """One end of a runway (NASR ``APT_RWY_END``)."""
    end_id: str
    lat: float
    lon: float
    elev_ft: float | None = None


@dataclass
class Runway:
    """A runway (NASR ``APT_RWY``) with its two ends.  Heliport pads and
    water runways are runways too — their ``length_ft`` drives the slope."""
    runway_id: str
    length_ft: float | None
    ends: list[RunwayEnd] = field(default_factory=list)


@dataclass
class Facility:
    """An airport / heliport (NASR ``APT_BASE``).

    ``use`` is the NASR ``FACILITY_USE_CODE`` (``PU`` public, ``PR``
    private); ``ownership`` the ``OWNERSHIP_TYPE_CODE`` (``PU``, ``PR``,
    ``MA``/``MN``/``MR`` military).  Military airports are public-use for
    Part 77 purposes (77.9(d)(2))."""
    facility_id: str
    name: str
    site_type: str            # NASR SITE_TYPE_CODE: A, H, C, G, U, B
    lat: float
    lon: float
    elev_ft: float | None = None
    use: str = "PU"
    ownership: str = "PU"
    runways: list[Runway] = field(default_factory=list)
    status: str = "O"         # NASR ARPT_STATUS: O operational, CI/CP closed

    @property
    def is_heliport(self) -> bool:
        return self.site_type == "H"

    @property
    def is_military(self) -> bool:
        return self.ownership in {"MA", "MN", "MR"}

    @property
    def is_public_use(self) -> bool:
        return self.use == "PU" or self.is_military

    @property
    def longest_runway_ft(self) -> float:
        return max((r.length_ft or 0.0) for r in self.runways) if self.runways else 0.0

    @property
    def kind(self) -> str:
        return SITE_TYPES.get(self.site_type, self.site_type)


@dataclass
class HeightClass:
    """Something that will stand at the site: the finished structure's high
    point, an appurtenance (light pole, sign, fence) or construction
    equipment.  ``height_ft`` is above ``site_elev_ft`` (the ground / deck
    the object stands on); ``base_offset_ft`` lets a pole on a 3-ft parapet
    or a crane on a lower approach be placed without a second site."""
    label: str
    height_ft: float
    kind: str = "structure"       # structure | appurtenance | equipment
    count: int = 1
    base_offset_ft: float = 0.0
    note: str = ""

    def top_elev(self, site_elev_ft: float) -> float:
        return site_elev_ft + self.base_offset_ft + self.height_ft


# -- geometry ------------------------------------------------------------------

_R_EARTH_FT = 6371008.8 * 3.280839895


def haversine_ft(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in feet (mean-sphere; < 0.3 % error, well
    inside the 50-ft horizontal accuracy §1407.1.7 asks for)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * _R_EARTH_FT * math.asin(math.sqrt(h))


def _local_xy(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """Equirectangular projection (ft) centred on the site — accurate to a
    few feet over the 20,000-ft screening reach."""
    k = math.cos(math.radians(lat0))
    x = math.radians(lon - lon0) * k * _R_EARTH_FT
    y = math.radians(lat - lat0) * _R_EARTH_FT
    return x, y


def _unproject(lat0: float, lon0: float, x: float, y: float) -> tuple[float, float]:
    k = math.cos(math.radians(lat0))
    return (lat0 + math.degrees(y / _R_EARTH_FT),
            lon0 + math.degrees(x / (k * _R_EARTH_FT)))


def nearest_runway_point(site_lat: float, site_lon: float, runway: Runway
                         ) -> tuple[float, tuple[float, float], RunwayEnd | None, float]:
    """``(distance_ft, (lat, lon), nearest_end, t)`` for the point of
    ``runway`` closest to the site.  ``t`` is the position along the runway
    from ``ends[0]`` (0) to ``ends[1]`` (1); ``nearest_end`` is the end the
    point lies closest to (its elevation is the surface datum).  A runway
    with a single located end degenerates to that end."""
    ends = [e for e in runway.ends if e.lat is not None and e.lon is not None]
    if not ends:
        raise ValueError(f"runway {runway.runway_id} has no located ends")
    if len(ends) == 1:
        e = ends[0]
        return haversine_ft(site_lat, site_lon, e.lat, e.lon), (e.lat, e.lon), e, 0.0
    a, b = ends[0], ends[1]
    ax, ay = _local_xy(site_lat, site_lon, a.lat, a.lon)
    bx, by = _local_xy(site_lat, site_lon, b.lat, b.lon)
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    t = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
    px, py = ax + t * dx, ay + t * dy
    lat, lon = _unproject(site_lat, site_lon, px, py)
    dist = haversine_ft(site_lat, site_lon, lat, lon)
    return dist, (lat, lon), (a if t <= 0.5 else b), t


def surface_for(facility: Facility) -> tuple[float, float]:
    """``(slope, reach_ft)`` of the Part 77.9(a)(2) notification surface
    that applies to ``facility``."""
    if facility.is_heliport:
        return 25.0, 5000.0
    if facility.longest_runway_ft > LONG_RUNWAY_FT:
        return 100.0, 20000.0
    return 50.0, 10000.0


# -- results -------------------------------------------------------------------

@dataclass
class HeightResult:
    height: HeightClass
    top_elev_ft: float
    surface_elev_ft: float

    @property
    def margin_ft(self) -> float:
        """Positive = clear below the surface; negative = penetration."""
        return self.surface_elev_ft - self.top_elev_ft

    @property
    def penetrates(self) -> bool:
        """Strict geometric penetration."""
        return self.margin_ft < 0

    @property
    def marginal(self) -> bool:
        """Clear, but by less than :data:`MARGINAL_FT`."""
        return 0 <= self.margin_ft < MARGINAL_FT

    @property
    def verdict(self) -> str:
        return "penetrates" if self.penetrates else ("marginal" if self.marginal else "clear")

    @property
    def notify(self) -> bool:
        """Conservative call: penetrates or marginal."""
        return self.margin_ft < MARGINAL_FT

    def as_dict(self) -> dict:
        return {"label": self.height.label, "kind": self.height.kind,
                "height_ft": self.height.height_ft, "count": self.height.count,
                "top_elev_ft": round(self.top_elev_ft, 1),
                "surface_elev_ft": round(self.surface_elev_ft, 1),
                "margin_ft": round(self.margin_ft, 1),
                "penetrates": self.penetrates, "verdict": self.verdict,
                "notify": self.notify, "note": self.height.note}


@dataclass
class FacilityResult:
    facility: Facility
    distance_ft: float                     # site → facility reference point
    runway_distance_ft: float              # site → nearest point of nearest runway
    runway: Runway | None
    runway_point: tuple[float, float]
    runway_end: RunwayEnd | None
    datum_elev_ft: float                   # elevation the surface rises from
    datum_source: str                      # "runway end 28" / "airport elevation"
    slope: float
    reach_ft: float
    heights: list[HeightResult] = field(default_factory=list)

    @property
    def within_reach(self) -> bool:
        return self.runway_distance_ft <= self.reach_ft

    @property
    def surface_elev_ft(self) -> float:
        return self.datum_elev_ft + self.runway_distance_ft / self.slope

    @property
    def penetrations(self) -> list[HeightResult]:
        """Heights that strictly penetrate this facility's surface."""
        return [h for h in self.heights if h.penetrates] if self.within_reach else []

    @property
    def notifications(self) -> list[HeightResult]:
        """Heights that penetrate *or* are marginal (the conservative set)."""
        return [h for h in self.heights if h.notify] if self.within_reach else []

    @property
    def penetrates(self) -> bool:
        return bool(self.penetrations)

    @property
    def notify(self) -> bool:
        return bool(self.notifications)

    def clearance_below_surface_ft(self, site_elev_ft: float) -> float:
        """The "(Z) feet between the notification surface and the project"
        of Figure 1407-7 — the blank in plan note G118B/C."""
        return self.surface_elev_ft - site_elev_ft

    def as_dict(self, site_elev_ft: float | None = None) -> dict:
        f = self.facility
        d = {
            "facility_id": f.facility_id, "name": f.name, "kind": f.kind,
            "use": "military" if f.is_military else ("public" if f.is_public_use else "private"),
            "lat": f.lat, "lon": f.lon, "elev_ft": f.elev_ft,
            "distance_ft": round(self.distance_ft),
            "distance_nm": round(self.distance_ft / NM_FT, 2),
            "distance_mi": round(self.distance_ft / MI_FT, 2),
            "runway_id": self.runway.runway_id if self.runway else None,
            "runway_length_ft": self.runway.length_ft if self.runway else None,
            "runway_end_id": self.runway_end.end_id if self.runway_end else None,
            "runway_point": {"lat": round(self.runway_point[0], 6),
                             "lon": round(self.runway_point[1], 6)},
            "runway_distance_ft": round(self.runway_distance_ft),
            "runway_distance_mi": round(self.runway_distance_ft / MI_FT, 2),
            "datum_elev_ft": round(self.datum_elev_ft, 1),
            "datum_source": self.datum_source,
            "slope": self.slope, "reach_ft": self.reach_ft,
            "within_reach": self.within_reach,
            "surface_elev_ft": round(self.surface_elev_ft, 1),
            "penetrates": self.penetrates, "notify": self.notify,
            "heights": [h.as_dict() for h in self.heights],
        }
        if site_elev_ft is not None:
            d["clearance_below_surface_ft"] = round(
                self.clearance_below_surface_ft(site_elev_ft), 1)
        return d


@dataclass
class ScreeningResult:
    site_lat: float
    site_lon: float
    site_elev_ft: float
    heights: list[HeightClass]
    facilities: list[FacilityResult]       # sorted by runway distance
    agl_notification: bool                 # any height > 200 ft AGL

    @property
    def in_reach(self) -> list[FacilityResult]:
        return [f for f in self.facilities if f.within_reach]

    @property
    def penetrating(self) -> list[FacilityResult]:
        """Facilities with a strict penetration."""
        return [f for f in self.facilities if f.penetrates]

    @property
    def notifying(self) -> list[FacilityResult]:
        """Facilities with a penetration or a marginal clearance."""
        return [f for f in self.facilities if f.notify]

    @property
    def strict_penetration(self) -> bool:
        return bool(self.penetrating) or self.agl_notification

    @property
    def controlling(self) -> FacilityResult | None:
        """The in-reach facility whose surface is lowest at the site (the
        one that governs), else the nearest facility for context."""
        if self.in_reach:
            return min(self.in_reach, key=lambda f: f.surface_elev_ft)
        return self.facilities[0] if self.facilities else None

    @property
    def analysis_required(self) -> bool:
        """§1407.1.7: an analysis must be documented whenever the project is
        within 20,000 ft of any airport or heliport."""
        return any(f.distance_ft <= MAX_NOTIFICATION_REACH_FT
                   or f.runway_distance_ft <= MAX_NOTIFICATION_REACH_FT
                   for f in self.facilities)

    @property
    def faa_notification_required(self) -> bool:
        """Form 7460-1: a public-use / military surface is penetrated (or
        cleared by less than :data:`MARGINAL_FT`), or anything exceeds
        200 ft AGL."""
        return self.agl_notification or any(
            f.notify and f.facility.is_public_use for f in self.facilities)

    @property
    def owner_coordination_required(self) -> bool:
        """§1407.1.8: a private facility's surface is penetrated — owner +
        Office of Aviation coordination, note G118C, no FAA filing."""
        return any(f.notify and not f.facility.is_public_use
                   for f in self.facilities)

    @property
    def notification_required(self) -> bool:
        return self.faa_notification_required or self.owner_coordination_required

    @property
    def status(self) -> str:
        if self.faa_notification_required:
            return "faa_notification"
        if self.owner_coordination_required:
            return "owner_coordination"
        if self.analysis_required:
            return "analysis_only"
        return "not_required"

    def as_dict(self) -> dict:
        ctl = self.controlling
        return {
            "site": {"lat": self.site_lat, "lon": self.site_lon,
                     "elev_ft": self.site_elev_ft,
                     "lat_dms": to_dms(self.site_lat, "lat"),
                     "lon_dms": to_dms(self.site_lon, "lon")},
            "status": self.status,
            "analysis_required": self.analysis_required,
            "faa_notification_required": self.faa_notification_required,
            "owner_coordination_required": self.owner_coordination_required,
            "agl_notification": self.agl_notification,
            "strict_penetration": self.strict_penetration,
            "marginal_ft": MARGINAL_FT,
            "controlling_facility_id": ctl.facility.facility_id if ctl else None,
            "plan_note": expected_plan_note(self),
            "facilities": [f.as_dict(self.site_elev_ft) for f in self.facilities],
        }


def screen(site_lat: float, site_lon: float, site_elev_ft: float,
           facilities: list[Facility], heights: list[HeightClass],
           search_ft: float = MAX_NOTIFICATION_REACH_FT * 3,
           include_closed: bool = False) -> ScreeningResult:
    """Evaluate every ``facility`` within ``search_ft`` of the site.

    Facilities beyond their own surface's reach are still reported (with
    ``within_reach=False``) so a negative screen can say *which* airport is
    nearest and by how much it misses — the second acceptance case of the
    feature.  The surface datum is the elevation of the runway end nearest
    the closest runway point (what the FAA OE/AAA pre-screen and ODOT
    consultant letters use); facilities with no located runway ends fall
    back to the facility reference point and published elevation.
    """
    results: list[FacilityResult] = []
    for fac in facilities:
        if not include_closed and fac.status and fac.status.upper().startswith("C"):
            continue
        ref_dist = haversine_ft(site_lat, site_lon, fac.lat, fac.lon)
        if ref_dist > search_ft:
            continue
        slope, reach = surface_for(fac)
        best = None
        for rwy in fac.runways:
            try:
                dist, pt, end, _t = nearest_runway_point(site_lat, site_lon, rwy)
            except ValueError:
                continue
            if best is None or dist < best[0]:
                best = (dist, pt, end, rwy)
        if best is None:
            rwy_dist, point, end, rwy = ref_dist, (fac.lat, fac.lon), None, None
            datum = fac.elev_ft if fac.elev_ft is not None else 0.0
            datum_src = "facility elevation" if fac.elev_ft is not None else "unknown (0 assumed)"
        else:
            rwy_dist, point, end, rwy = best
            if end is not None and end.elev_ft is not None:
                datum, datum_src = end.elev_ft, f"runway {rwy.runway_id} end {end.end_id}"
            elif fac.elev_ft is not None:
                datum, datum_src = fac.elev_ft, "facility elevation"
            else:
                datum, datum_src = 0.0, "unknown (0 assumed)"
        fr = FacilityResult(fac, ref_dist, rwy_dist, rwy, point, end, datum,
                            datum_src, slope, reach)
        fr.heights = [HeightResult(h, h.top_elev(site_elev_ft), fr.surface_elev_ft)
                      for h in heights]
        results.append(fr)
    results.sort(key=lambda r: r.runway_distance_ft)
    agl = any(h.height_ft + h.base_offset_ft > AGL_NOTIFICATION_FT for h in heights)
    return ScreeningResult(site_lat, site_lon, site_elev_ft, list(heights), results, agl)


# -- designer hints --------------------------------------------------------------

def equipment_height_hint(work_types: list[str] | None = None,
                          bridge_height_ft: float | None = None,
                          pole_height_ft: float | None = None) -> dict:
    """Conservative construction-equipment height from Figure 1407-3: the
    tallest allowance among ``work_types`` (keys of :data:`EQUIPMENT_HEIGHTS`).
    Defaults to *small bridges* (60 ft, crane) — the allowance ODOT
    consultants apply to a typical deck replacement."""
    work_types = work_types or ["small_bridges"]
    best_h, best_src, best_type = 0.0, "", ""
    for wt in work_types:
        h, src = EQUIPMENT_HEIGHTS[wt]
        if h is None:
            if wt == "bridge_painting" and bridge_height_ft is not None:
                h = bridge_height_ft + 10.0
            elif wt == "highway_lighting" and pole_height_ft is not None:
                h = pole_height_ft
            else:
                continue
        if h > best_h:
            best_h, best_src, best_type = h, src, wt
    return {"height_ft": best_h, "controlling": best_src, "work_type": best_type,
            "reference": "L&D Vol. 3 Fig. 1407-3",
            "note": "Average height for the work type; adjust for the actual "
                    "crane charts. Large bridges (long spans, segmental, "
                    "erection over water) use 100 ft."}


_POLE_DESIGN = re.compile(r"\bA\s*(\d{1,2})\s*B\s*(\d{2,3})\b", re.IGNORECASE)


def light_pole_height_from_design(code: str) -> float | None:
    """ODOT light-pole design code ``A<arm>B<mounting height>`` (Item 625,
    e.g. ``A10B30`` = 10-ft arm, 30-ft mounting height) → mounting height
    in feet.  The luminaire sits at the mounting height, so this is the
    pole's overall height for Part 77 purposes."""
    m = _POLE_DESIGN.search(code or "")
    return float(m.group(2)) if m else None


def structure_high_point_hint(ground_elev_ft: float, *,
                              vertical_clearance_ft: float | None = None,
                              max_span_ft: float | None = None,
                              feature_under: str = "public_road",
                              deck_elev_ft: float | None = None) -> dict:
    """Conservative guess at the finished structure's high point when the
    plans' profile is not to hand.

    Uses the deck elevation if known, else stacks minimum vertical
    clearance (BDM 16.5 ft over roadways, 23 ft over rail, default by
    ``feature_under``), a span-depth allowance (``max_span/22``, ≥ 3 ft)
    and 3.5 ft of deck + parapet on top of the ground elevation.  Always
    replace with the plan profile before filing."""
    parts = []
    if deck_elev_ft is not None:
        high = deck_elev_ft + 3.5
        parts.append(("deck elevation", deck_elev_ft), )
        parts.append(("parapet / railing", 3.5))
        basis = "deck elevation + parapet"
    else:
        clr = vertical_clearance_ft
        if clr is None:
            clr = {"railroad": 23.0, "interstate": 16.5, "public_road": 16.5,
                   "private_road": 14.5, "waterway": 0.0, "none": 0.0}.get(feature_under, 16.5)
        depth = max(3.0, (max_span_ft or 0.0) / 22.0)
        high = ground_elev_ft + clr + depth + 3.5
        parts = [("ground elevation (DEM)", ground_elev_ft),
                 ("vertical clearance", clr),
                 ("superstructure depth (span/22, min 3 ft)", round(depth, 1)),
                 ("deck + parapet", 3.5)]
        basis = "ground + clearance + depth + parapet"
    return {"high_point_elev_ft": round(high, 1), "basis": basis,
            "components": parts,
            "note": "Conservative stack-up; confirm against the plan profile "
                    "(highest point of the superstructure, §1407.1.7)."}


# -- plan notes ------------------------------------------------------------------

def expected_plan_note(result: ScreeningResult) -> dict:
    """Which G118 note the plans should carry (L&D §1407.1.7 / §1407.1.8 and
    the ODOT general-notes designer notes):

    * **G118A** — construction equipment penetrates a public-use surface;
      the blank height is the FAA-approved height and the ASN is filled in.
    * **G118B** — inside the influence area (within reach) but equipment
      clears; the blank height is the clearance below the surface.
    * **G118C** — equipment penetrates a private facility's surface.
    * ``None`` — no facility within reach.
    """
    equip = [h for h in result.heights if h.kind == "equipment"]
    ctl = result.controlling
    if ctl is None or not result.in_reach:
        return {"note": None, "height_ft": None,
                "reason": "no airport or heliport within its notification reach"}
    pub_pen = [f for f in result.in_reach if f.facility.is_public_use
               and any(h.notify and h.height.kind == "equipment" for h in f.heights)]
    prv_pen = [f for f in result.in_reach if not f.facility.is_public_use
               and any(h.notify and h.height.kind == "equipment" for h in f.heights)]
    if pub_pen:
        f = min(pub_pen, key=lambda r: r.surface_elev_ft)
        return {"note": "G118A", "height_ft": None,
                "facility_id": f.facility.facility_id,
                "reason": f"construction equipment penetrates the {f.slope:.0f}:1 "
                          f"surface of {f.facility.name}; height blank = FAA-approved "
                          "height, plus the Aeronautical Study Number"}
    if prv_pen:
        f = min(prv_pen, key=lambda r: r.surface_elev_ft)
        return {"note": "G118C", "facility_id": f.facility.facility_id,
                "height_ft": round(f.clearance_below_surface_ft(result.site_elev_ft), 1),
                "reason": f"construction equipment penetrates the surface of private "
                          f"facility {f.facility.name}; coordinate with the owner"}
    f = min(result.in_reach, key=lambda r: r.surface_elev_ft)
    return {"note": "G118B", "facility_id": f.facility.facility_id,
            "height_ft": round(f.clearance_below_surface_ft(result.site_elev_ft), 1),
            "reason": (f"within the influence area of {f.facility.name}; equipment "
                       f"({', '.join(h.label for h in equip) or 'none entered'}) clears "
                       "— height blank = clearance below the surface")}


_G118_HEADER = re.compile(r"AIRWAY\s*/\s*HIGHWAY\s+CLEARANCE\s+FOR\s+AIRPORTS?\s+AND\s+HELIPORTS?",
                          re.IGNORECASE)
_G118_HEIGHT = re.compile(r"SHALL\s+EXCEED\s+A\s+HEIGHT\s+OF\s+(_{2,}|\d+(?:\.\d+)?)\s*FT",
                          re.IGNORECASE)
_G118_ASN = re.compile(r"AERONAUTICAL\s+STUD(?:Y|IES)\s+NUMBERS?\s+(?:ARE\s+)?(_{2,}|\d{4}-[A-Z]{3}-\d+-[A-Z]+)?",
                       re.IGNORECASE)
_ASN_ANY = re.compile(r"\b(\d{4}-[A-Z]{3}-\d{1,6}-[A-Z]{2,3})\b")


def detect_g118_notes(plan_text: str) -> list[dict]:
    """Find G118-family notes in extracted plan text and read their blanks.

    Returns one dict per note found: ``{"note": "G118A"|"G118B"|"G118C",
    "height_ft": float|None, "height_blank": bool, "asn": str|None,
    "asn_blank": bool}``.  The variants share a header, so the body
    distinguishes them: G118C names a *private-use* facility; G118A talks
    about *resubmitting* an aeronautical study; G118B just says *submit*.
    """
    text = re.sub(r"[ \t]+", " ", plan_text)
    found = []
    for m in _G118_HEADER.finditer(text):
        body = text[m.end(): m.end() + 2500]
        upper = body.upper()
        if "PRIVATE-USE" in upper or "PRIVATE USE AIRPORT" in upper:
            note = "G118C"
        elif "RESUBMIT" in upper or "NEW FAA FORM" in upper:
            note = "G118A"
        else:
            note = "G118B"
        hm = _G118_HEIGHT.search(body)
        height_blank = hm is None or hm.group(1).startswith("_")
        height = None if height_blank else float(hm.group(1))
        asn = None
        am = _ASN_ANY.search(body)
        if am:
            asn = am.group(1)
        entry = {"note": note, "height_ft": height, "height_blank": height_blank,
                 "asn": asn, "asn_blank": note == "G118A" and asn is None}
        found.append(entry)
    return found


# -- deliverables ------------------------------------------------------------------

def to_dms(value: float, axis: str = "lat") -> str:
    """Decimal degrees → ``41° 24' 11.33" N`` (what Form 7460-1 wants)."""
    hemi = ("N" if value >= 0 else "S") if axis == "lat" else ("E" if value >= 0 else "W")
    v = abs(value)
    d = int(v)
    m_full = (v - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    if round(s, 2) >= 60:
        s = 0.0
        m += 1
    if m >= 60:
        m = 0
        d += 1
    return f"{d}° {m:02d}' {s:05.2f}\" {hemi}"


def _fmt_ft(x: float) -> str:
    return f"{x:,.1f}"


def analysis_letter(result: ScreeningResult, *, project_label: str, pid: str,
                    addressee: str = "District Production Administrator",
                    district: str = "", author: str = "", author_title: str = "",
                    letter_date: date | None = None) -> str:
    """Plain-text Airway/Highway Clearance Analysis letter following L&D
    Figure 1407-7, filled from the screening (the content consultants
    currently write by hand — distances in NM and miles, elevations, the
    surface height, and the resulting plan-note call)."""
    letter_date = letter_date or date.today()
    ctl = result.controlling
    lines = [letter_date.strftime("%B %d, %Y"), "", addressee]
    if district:
        lines.append(f"ODOT, District {district}")
    lines += ["", "Re:  Airway/Highway Clearance Analysis",
              f"     {project_label}", f"     PID No. {pid}", "", "To whom it may concern:", ""]
    if ctl is None:
        lines.append("No airport or heliport was found within 60,000 ft of the project; "
                     "an Airway/Highway Clearance Analysis is not required "
                     "(L&D Vol. 3 §1407.1.7).")
    else:
        in_reach = result.in_reach
        near = result.facilities[0]
        lines.append(
            f"We have reviewed the subject project location and determined that the "
            f"project {'is' if in_reach else 'is not'} within the notification surface of "
            f"{('a public-use' if ctl.facility.is_public_use else 'a private-use')} "
            f"{ctl.facility.kind}, {ctl.facility.name} ({ctl.facility.facility_id}), located "
            f"{ctl.distance_ft / NM_FT:.1f} nautical miles ({ctl.distance_ft / MI_FT:.2f} mi) "
            f"from the project." if in_reach else
            f"We have reviewed the subject project location and determined that the "
            f"project is not within the notification surface of any airport or heliport. "
            f"The nearest is {near.facility.name} ({near.facility.facility_id}), a "
            f"{near.facility.kind} {near.distance_ft / NM_FT:.1f} nautical miles "
            f"({near.distance_ft / MI_FT:.2f} mi) away, whose {near.slope:.0f}:1 surface "
            f"reaches {near.reach_ft:,.0f} ft; the nearest runway point is "
            f"{near.runway_distance_ft:,.0f} ft from the project.")
        others = [f for f in result.facilities if f is not ctl][:4]
        if others:
            lines.append("")
            lines.append("Other facilities considered: " + "; ".join(
                f"{f.facility.name} ({f.facility.kind}, {f.distance_ft / NM_FT:.1f} NM, "
                f"{'inside' if f.within_reach else 'outside'} its {f.slope:.0f}:1 reach)"
                for f in others) + ".")
        if in_reach:
            lines.append("")
            lines.append(
                f"The closest point of {ctl.facility.name} (runway "
                f"{ctl.runway.runway_id if ctl.runway else 'reference point'}) is "
                f"{ctl.runway_distance_ft:,.0f} ft ({ctl.runway_distance_ft / MI_FT:.2f} mi) "
                f"from the project. The {ctl.datum_source} elevation is "
                f"{_fmt_ft(ctl.datum_elev_ft)} ft. The highest elevation of the project is "
                f"{_fmt_ft(result.site_elev_ft)} ft. The {ctl.slope:.0f}:1 notification surface "
                f"is therefore at {_fmt_ft(ctl.surface_elev_ft)} ft over the project, "
                f"{_fmt_ft(ctl.clearance_below_surface_ft(result.site_elev_ft))} ft above it.")
            for h in ctl.heights:
                verdict = ("encroaches into" if h.penetrates else
                           "clears (marginally, within survey accuracy)" if h.marginal
                           else "clears")
                lines.append(
                    f"  - {h.height.label} ({h.height.kind}, {h.height.height_ft:g} ft"
                    f"{' x ' + str(h.height.count) if h.height.count > 1 else ''}): top "
                    f"elevation {_fmt_ft(h.top_elev_ft)} ft {verdict} the surface by "
                    f"{abs(h.margin_ft):.1f} ft.")
        note = expected_plan_note(result)
        lines.append("")
        if result.faa_notification_required:
            lines.append("FAA Form 7460-1 notification is required for the items that encroach "
                         "or clear by less than 20 ft (one form for the permanent structure, "
                         "one for construction equipment / temporary structures, "
                         "L&D §1407.1.7).")
        elif result.owner_coordination_required:
            lines.append("Coordination with the private facility owner and the ODOT Office of "
                         "Aviation is required (L&D §1407.1.8); FAA coordination is not.")
        else:
            lines.append("FAA notification is not required.")
        if note["note"]:
            h = f" with a permissible height of {note['height_ft']:g} ft" if note.get("height_ft") else ""
            lines.append(f"Plan note {note['note']} applies{h}: {note['reason']}.")
    lines += ["", "Respectfully,", "", author or "", author_title or ""]
    return "\n".join(l for l in lines).rstrip() + "\n"


def form_7460_rows(result: ScreeningResult,
                   points: list[dict] | None = None) -> list[dict]:
    """Rows for the pre-filled Form 7460-1 data sheet.

    ``points`` are the §1407.1.7 study points: ``{"label", "lat", "lon",
    "ground_elev_ft", "height_ft", "kind"}`` (beginning / end / high point
    / closest point to runway / each light pole / each crane position).
    With no points the site itself is expanded once per height class.
    Each row carries NAD83 DMS coordinates, site elevation, height AGL and
    overall AMSL — the 7460-1 items 5–7 and 9."""
    rows = []
    if not points:
        points = [{"label": h.label, "lat": result.site_lat, "lon": result.site_lon,
                   "ground_elev_ft": result.site_elev_ft + h.base_offset_ft,
                   "height_ft": h.height_ft, "kind": h.kind, "count": h.count}
                  for h in result.heights]
    ctl = result.controlling
    for i, p in enumerate(points, 1):
        ground = float(p.get("ground_elev_ft", result.site_elev_ft))
        height = float(p.get("height_ft", 0.0))
        row = {"no": i, "label": p.get("label", f"point {i}"), "kind": p.get("kind", "structure"),
               "count": p.get("count", 1),
               "lat": p["lat"], "lon": p["lon"],
               "lat_dms": to_dms(p["lat"], "lat"), "lon_dms": to_dms(p["lon"], "lon"),
               "datum": "NAD83", "site_elev_ft": round(ground, 1),
               "height_agl_ft": round(height, 1), "overall_amsl_ft": round(ground + height, 1)}
        if ctl is not None:
            # re-evaluate the controlling surface at this point's own distance
            if ctl.runway is not None:
                d, _pt, _end, _t = nearest_runway_point(p["lat"], p["lon"], ctl.runway)
            else:
                d = haversine_ft(p["lat"], p["lon"], ctl.facility.lat, ctl.facility.lon)
            surf = ctl.datum_elev_ft + d / ctl.slope
            row.update({"nearest_facility": ctl.facility.facility_id,
                        "runway_distance_ft": round(d),
                        "surface_elev_ft": round(surf, 1),
                        "margin_ft": round(surf - (ground + height), 1),
                        "penetrates": (ground + height) > surf and d <= ctl.reach_ft,
                        "notify": (surf - (ground + height)) < MARGINAL_FT and d <= ctl.reach_ft})
        rows.append(row)
    return rows
