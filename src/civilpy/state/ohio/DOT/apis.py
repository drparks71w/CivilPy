"""ODOT Standard Objects for bridge engineering workflows.

Provides Pythonic wrappers around ODOT's core data systems:

- **BrRBridge**: AASHTOWare Bridge Rating (BrR) database access
- **AssetwiseRawBridge**: Direct Bentley AssetWise API connection
- **BridgeDBAsset**: Internal Django REST API connection
- **MidasBridge** (+ sub-components): midas Civil REST API wrapper
- **TIMSBridge** / **TIMSProject** / **TIMSRoad**: TIMS ArcGIS REST wrappers
- **NHDFlowline** / **USGSStreamStats** / **USGSGauge**: USGS hydrology APIs
- **SNBIComplianceChecker**: FHWA SNBI field validation
- **BridgeEngineeringChecks**: High-level spatial analysis utilities
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _load_secrets() -> dict:
    """Load credentials from ~/secrets.json with fallback to ./secrets.json."""
    secrets_path = Path.home() / "secrets.json"
    if not secrets_path.exists():
        secrets_path = Path("secrets.json")
    if not secrets_path.exists():
        raise FileNotFoundError(
            "No secrets.json found in home directory or working directory."
        )
    with open(secrets_path, "r") as f:
        return json.load(f)


# ============================================================================
# BrR Bridge (AASHTOWare Bridge Rating)
# ============================================================================

class RatingMethod(str, Enum):
    """Load rating methodology designators."""
    ASR = "ASR"
    LFR = "LFR"
    LRFD = "LRFD"


class ControllingRating(BaseModel):
    """Controlling rating factors for a bridge analysis.

    Attributes:
        inventory_rf: Inventory rating factor.
        operating_rf: Operating rating factor.
        legal_rf: Legal load rating factor (legal inventory).
        permit_rf: Permit load rating factor (permit inventory).
        post_rf: Posting rating factor.
        safe_rf: Safe load rating factor.
        controlling_vehicle: Name of the controlling vehicle (e.g. 'HL-93').
        rating_method: Rating methodology used (ASR, LFR, or LRFD).
        limit_state: Controlling limit state description.
        span_num: Controlling span number.
        location: Controlling location along the member.
    """
    inventory_rf: Optional[float] = None
    operating_rf: Optional[float] = None
    legal_rf: Optional[float] = None
    permit_rf: Optional[float] = None
    post_rf: Optional[float] = None
    safe_rf: Optional[float] = None
    controlling_vehicle: Optional[str] = None
    rating_method: Optional[RatingMethod] = None
    limit_state: Optional[str] = None
    span_num: Optional[int] = None
    location: Optional[float] = None


class MemberCapacity(BaseModel):
    """Capacity data for a single structural member at an analysis point.

    Maps to ``ABW_RATING_RESULTS`` joined with ``ABW_INTEREST_PT`` for
    location data (span, distance along member).

    Attributes:
        member_id: Superstructure member ID (SUPER_STRUCT_MBR_ID).
        point_id: Analysis point ID within the event.
        span: Span number where this point occurs.
        dist: Distance along member to this point (feet).
        inv_rf: Inventory rating factor at this point.
        opr_rf: Operating rating factor at this point.
        inv_capacity: Inventory capacity at this point.
        opr_capacity: Operating capacity at this point.
        inv_limit_state: Controlling inventory limit state.
        opr_limit_state: Controlling operating limit state.
        vehicle_name: Vehicle used for this rating result.
        design_method_type: Integer design method code.
    """
    member_id: Optional[str] = None
    point_id: str
    span: Optional[int] = None
    dist: Optional[float] = None
    inv_rf: Optional[float] = None
    opr_rf: Optional[float] = None
    inv_capacity: Optional[float] = None
    opr_capacity: Optional[float] = None
    inv_limit_state: Optional[str] = None
    opr_limit_state: Optional[str] = None
    vehicle_name: Optional[str] = None
    design_method_type: Optional[int] = None


class VehicleLoad(BaseModel):
    """Vehicle load definition from BrR.

    Attributes:
        vehicle_id: BrR internal vehicle identifier.
        name: Human-readable name (e.g. 'HL-93', 'Type 3S2').
        gross_weight: Total vehicle weight in kips.
    """
    vehicle_id: int
    name: str
    gross_weight: Optional[float] = None


# Standard BrR vehicle ID -> name mapping (ODOT standard set)
BRR_VEHICLE_MAP: Dict[int, str] = {
    1: "HL-93",
    2: "HS 20-44",
    3: "Type 3",
    4: "Type 3S2",
    5: "Type 3-3",
    6: "SU4",
    7: "SU5",
    8: "SU6",
    9: "SU7",
    10: "EV2",
    11: "EV3",
    12: "OH 2F1",
    13: "OH 3F1",
    14: "OH 5C1",
    15: "PL 60T",
    16: "PL 65T",
}


def _create_brr_engine(connection_string: Optional[str] = None):
    """Create a SQLAlchemy engine for the BrR Oracle database.

    Args:
        connection_string: SQLAlchemy connection URL. If None, builds
            one from ``~/secrets.json`` keys ``BRR_ORACLE_HOST``,
            ``BRR_ORACLE_PORT``, ``BRR_ORACLE_SERVICE``,
            ``BRR_ORACLE_USER``, ``BRR_ORACLE_PASSWORD``.

    Returns:
        A ``sqlalchemy.engine.Engine`` instance.

    Raises:
        ImportError: If sqlalchemy is not installed.

    Example connection strings::

        # With cx_Oracle / oracledb driver
        "oracle+oracledb://user:pass@host:1521/?service_name=BRR"

        # With cx_Oracle (legacy)
        "oracle+cx_oracle://user:pass@host:1521/?service_name=BRR"

        # TNS alias
        "oracle+oracledb://user:pass@tns_alias"
    """
    try:
        from sqlalchemy import create_engine
    except ImportError:
        raise ImportError(
            "sqlalchemy is required for BrR database access. "
            "Install with: pip install sqlalchemy oracledb"
        )

    if connection_string:
        return create_engine(connection_string)

    secrets = _load_secrets()
    host = secrets.get("BRR_ORACLE_HOST", "localhost")
    port = secrets.get("BRR_ORACLE_PORT", "1521")
    service = secrets.get("BRR_ORACLE_SERVICE", "BRR")
    user = secrets.get("BRR_ORACLE_USER", "")
    password = secrets.get("BRR_ORACLE_PASSWORD", "")
    return create_engine(
        f"oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={service}"
    )


# BrR DESIGN_METHOD_TYPE integer -> RatingMethod mapping
# These codes come from ABW_SYS_TYPE where CATEGORY_ID matches design methods
BRR_DESIGN_METHOD_MAP: Dict[int, str] = {
    1: "ASR",
    2: "LFR",
    3: "LRFD",
}


class BrRBridge:
    """AASHTOWare Bridge Rating (BrR) bridge object.

    Connects to the BrR Oracle database (schema ``BRIDGEWARE``) via
    SQLAlchemy and populates sub-objects for controlling ratings,
    member capacities, and vehicle loads.

    The join path follows the BrR data model::

        ABW_BRIDGE (AGENCY_CODE = SFN)
          -> ABW_SPNG_MBR_ALT_EVENTS (on BRIDGE_ID)
            -> ABW_RATING_RESULTS_SUMMARY (on SPNG_MBR_ALT_EVENT_ID)
              -> ABW_LIB_VEHICLE (on VEHICLE_ID)
            -> ABW_INTEREST_PT + ABW_RATING_RESULTS (point-level)

    Args:
        bridge_id: The ODOT Structure File Number (SFN), stored as
            ``AGENCY_CODE`` in ``ABW_BRIDGE``.
        engine: A SQLAlchemy Engine connected to the BrR Oracle database.
            If None, creates one from ``~/secrets.json`` credentials.
        connection_string: Alternative SQLAlchemy URL string. Ignored if
            ``engine`` is provided.

    Example::

        from sqlalchemy import create_engine
        engine = create_engine("oracle+oracledb://user:pass@host:1521/?service_name=BRR")
        bridge = BrRBridge("2102226", engine=engine)
        print(bridge.controlling_rating.inventory_rf)
        print(bridge.nbi_info)

    .. note::
        Requires ``sqlalchemy`` and ``oracledb`` (or ``cx_Oracle``).
        The BrR database is an Oracle instance with schema ``BRIDGEWARE``.
    """

    def __init__(
        self,
        bridge_id: str,
        engine=None,
        connection_string: Optional[str] = None,
    ):
        self.bridge_id = bridge_id.strip()
        if engine is not None:
            self.engine = engine
        else:
            self.engine = _create_brr_engine(connection_string)

        self.controlling_rating: ControllingRating = ControllingRating()
        self.member_capacities: List[MemberCapacity] = []
        self.vehicle_loads: List[VehicleLoad] = []
        self.nbi_info: Dict[str, Any] = {}

        self._populate()

    def _text(self, sql: str):
        """Wrap a SQL string for SQLAlchemy execution.

        Returns:
            A ``sqlalchemy.text`` object.
        """
        from sqlalchemy import text
        return text(sql)

    def _populate(self):
        """Fetch and populate all sub-objects from BrR.

        Each query is wrapped in its own try/except so partial data
        is still available if one query fails.
        """
        try:
            self._fetch_nbi_info()
        except Exception as e:
            logger.error("CRITICAL: Failed to fetch NBI info for bridge %s. Most downstream analysis will fail. Error: %s",
                         self.bridge_id, e, exc_info=True)

        try:
            self._fetch_controlling_rating()
        except Exception as e:
            logger.error("Failed to fetch controlling rating for bridge %s. Error: %s",
                         self.bridge_id, e, exc_info=True)

        try:
            self._fetch_member_capacities()
        except Exception as e:
            logger.error("Failed to fetch member capacities for bridge %s. This will prevent point-level rating analysis. Error: %s",
                         self.bridge_id, e, exc_info=True)

        try:
            self._fetch_vehicle_loads()
        except Exception as e:
            logger.error("Failed to fetch vehicle loads for bridge %s. Rating results may lack vehicle details. Error: %s",
                         self.bridge_id, e, exc_info=True)

    def _fetch_nbi_info(self):
        """Fetch basic bridge identification from the NBI-style BRIDGE table.

        Populates ``self.nbi_info`` with BRKEY, year built, district,
        county, facility, feature intersected, and latest rating info.

        TODO (Dane): Verify the BRKEY value format. The BRIDGE table uses
        BRKEY as its PK while ABW_BRIDGE uses AGENCY_CODE. Run this to
        check the mapping:

            SELECT b.BRKEY, b.BRIDGE_ID, a.AGENCY_CODE, a.BRIDGE_ID
            FROM BRIDGEWARE.BRIDGE b, BRIDGEWARE.ABW_BRIDGE a
            WHERE b.BRIDGE_ID = a.AGENCY_CODE
            AND ROWNUM <= 10;
        """
        query = self._text("""
            SELECT BRKEY, BRIDGE_ID, STRUCT_NUM, STRUCNAME,
                   FEATINT, FACILITY, LOCATION,
                   DISTRICT, COUNTY, OWNER, CUSTODIAN,
                   YEARBUILT, RATINGDATE,
                   ORLOAD, ORTYPE, IRLOAD, IRTYPE, POSTING,
                   NOTES
            FROM BRIDGEWARE.BRIDGE
            WHERE BRIDGE_ID = :sfn
        """)
        with self.engine.connect() as conn:
            row = conn.execute(query, {"sfn": self.bridge_id}).fetchone()

        if row:
            self.nbi_info = {
                "brkey": row[0],
                "bridge_id": row[1],
                "struct_num": row[2],
                "name": row[3],
                "feature_intersected": row[4],
                "facility": row[5],
                "location": row[6],
                "district": row[7],
                "county": row[8],
                "owner": row[9],
                "custodian": row[10],
                "year_built": row[11],
                "rating_date": row[12],
                "operating_load": row[13],
                "operating_type": row[14],
                "inventory_load": row[15],
                "inventory_type": row[16],
                "posting": row[17],
                "notes": row[18],
            }

    def _fetch_controlling_rating(self):
        """Query BrR for the controlling rating factors.

        Joins ``ABW_BRIDGE`` -> ``ABW_SPNG_MBR_ALT_EVENTS`` ->
        ``ABW_RATING_RESULTS_SUMMARY`` -> ``ABW_LIB_VEHICLE``.

        Takes the row with the lowest ``INV_RF`` (most critical) across
        all members/events for this bridge.

        TODO (Dane): If you need to filter to only the latest analysis
        event (not all historical events), add a filter on
        ``e.UP_TO_DATE_INDICATOR = 'Y'``. Try:

            SELECT e.UP_TO_DATE_INDICATOR, COUNT(*)
            FROM BRIDGEWARE.ABW_SPNG_MBR_ALT_EVENTS e
            JOIN BRIDGEWARE.ABW_BRIDGE b ON e.BRIDGE_ID = b.BRIDGE_ID
            WHERE b.AGENCY_CODE = '2102226'
            GROUP BY e.UP_TO_DATE_INDICATOR;
        """
        query = self._text("""
            SELECT s.INV_RF,
                   s.OPR_RF,
                   s.LEGAL_INV_RF,
                   s.PERMIT_INV_RF,
                   s.POST_RF,
                   s.SAFE_RF,
                   v.NAME,
                   s.DESIGN_METHOD_TYPE,
                   s.INV_LIMIT_STATE,
                   s.SPAN_NUM,
                   s.INV_LOCATION
            FROM BRIDGEWARE.ABW_BRIDGE b
            JOIN BRIDGEWARE.ABW_SPNG_MBR_ALT_EVENTS e
                ON b.BRIDGE_ID = e.BRIDGE_ID
            JOIN BRIDGEWARE.ABW_RATING_RESULTS_SUMMARY s
                ON e.SPNG_MBR_ALT_EVENT_ID = s.SPNG_MBR_ALT_EVENT_ID
            JOIN BRIDGEWARE.ABW_LIB_VEHICLE v
                ON s.VEHICLE_ID = v.VEHICLE_ID
            WHERE b.AGENCY_CODE = :bridge_id
              AND s.INV_RF IS NOT NULL
            ORDER BY s.INV_RF ASC
            FETCH FIRST 1 ROWS ONLY
        """)
        with self.engine.connect() as conn:
            row = conn.execute(query, {"bridge_id": self.bridge_id}).fetchone()

        if row:
            method_int = row[7]
            method_str = BRR_DESIGN_METHOD_MAP.get(method_int)
            rating_method = None
            if method_str and method_str in RatingMethod.__members__:
                rating_method = RatingMethod(method_str)

            self.controlling_rating = ControllingRating(
                inventory_rf=row[0],
                operating_rf=row[1],
                legal_rf=row[2],
                permit_rf=row[3],
                post_rf=row[4],
                safe_rf=row[5],
                controlling_vehicle=row[6],
                rating_method=rating_method,
                limit_state=row[8],
                span_num=row[9],
                location=row[10],
            )

    def _fetch_member_capacities(self):
        """Query BrR for point-level rating results.

        Joins through the full path to ``ABW_RATING_RESULTS`` and
        ``ABW_INTEREST_PT`` to get span/distance info at each point.

        TODO (Dane): The SUPER_STRUCT_MBR_ID is on ABW_SPNG_MBR_ALT_EVENTS.
        To get member identity, run:

            SELECT e.SUPER_STRUCT_MBR_ID, e.STRUCT_DEF_ID,
                   COUNT(*) as result_count
            FROM BRIDGEWARE.ABW_SPNG_MBR_ALT_EVENTS e
            JOIN BRIDGEWARE.ABW_BRIDGE b ON e.BRIDGE_ID = b.BRIDGE_ID
            WHERE b.AGENCY_CODE = '2102226'
            GROUP BY e.SUPER_STRUCT_MBR_ID, e.STRUCT_DEF_ID;
        """
        query = self._text("""
            SELECT ip.POINT_ID,
                   ip.SPAN,
                   ip.DIST,
                   r.INV_RF,
                   r.OPR_RF,
                   r.INV_CAPACITY,
                   r.OPR_CAPACITY,
                   r.INV_LIMIT_STATE,
                   r.OPR_LIMIT_STATE,
                   v.NAME AS VEHICLE_NAME,
                   r.DESIGN_METHOD_TYPE,
                   e.SUPER_STRUCT_MBR_ID
            FROM BRIDGEWARE.ABW_BRIDGE b
            JOIN BRIDGEWARE.ABW_SPNG_MBR_ALT_EVENTS e
                ON b.BRIDGE_ID = e.BRIDGE_ID
            JOIN BRIDGEWARE.ABW_INTEREST_PT ip
                ON e.SPNG_MBR_ALT_EVENT_ID = ip.SPNG_MBR_ALT_EVENT_ID
            JOIN BRIDGEWARE.ABW_RATING_RESULTS r
                ON ip.SPNG_MBR_ALT_EVENT_ID = r.SPNG_MBR_ALT_EVENT_ID
                AND ip.POINT_ID = r.POINT_ID
            JOIN BRIDGEWARE.ABW_LIB_VEHICLE v
                ON r.VEHICLE_ID = v.VEHICLE_ID
            WHERE b.AGENCY_CODE = :bridge_id
            ORDER BY e.SUPER_STRUCT_MBR_ID, ip.SPAN, ip.DIST
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"bridge_id": self.bridge_id}).fetchall()

        for row in rows:
            self.member_capacities.append(
                MemberCapacity(
                    point_id=str(row[0]),
                    span=row[1],
                    dist=row[2],
                    inv_rf=row[3],
                    opr_rf=row[4],
                    inv_capacity=row[5],
                    opr_capacity=row[6],
                    inv_limit_state=row[7],
                    opr_limit_state=row[8],
                    vehicle_name=row[9],
                    design_method_type=row[10],
                    member_id=str(row[11]) if row[11] is not None else None,
                )
            )

    def _fetch_vehicle_loads(self):
        """Query BrR for vehicles used in this bridge's rating results.

        Only returns vehicles that appear in ``ABW_RATING_RESULTS_SUMMARY``
        for this bridge (not the full library).
        """
        query = self._text("""
            SELECT DISTINCT v.VEHICLE_ID,
                   v.NAME,
                   v.VEHICLE_WEIGHT
            FROM BRIDGEWARE.ABW_LIB_VEHICLE v
            JOIN BRIDGEWARE.ABW_RATING_RESULTS_SUMMARY s
                ON v.VEHICLE_ID = s.VEHICLE_ID
            JOIN BRIDGEWARE.ABW_SPNG_MBR_ALT_EVENTS e
                ON s.SPNG_MBR_ALT_EVENT_ID = e.SPNG_MBR_ALT_EVENT_ID
            JOIN BRIDGEWARE.ABW_BRIDGE b
                ON e.BRIDGE_ID = b.BRIDGE_ID
            WHERE b.AGENCY_CODE = :bridge_id
            ORDER BY v.VEHICLE_ID
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"bridge_id": self.bridge_id}).fetchall()

        self.vehicle_loads = [
            VehicleLoad(vehicle_id=r[0], name=r[1], gross_weight=r[2])
            for r in rows
        ]

    def get_all_rating_summaries(self) -> List[Dict[str, Any]]:
        """Get all rating result summaries for this bridge.

        Returns every vehicle/member combination rating, not just the
        controlling (lowest) one. Useful for detailed analysis.

        Returns:
            List of dicts with INV_RF, OPR_RF, vehicle name, etc.
        """
        query = self._text("""
            SELECT s.INV_RF, s.OPR_RF, s.POST_RF, s.SAFE_RF,
                   s.LEGAL_INV_RF, s.LEGAL_OPR_RF,
                   s.PERMIT_INV_RF, s.PERMIT_OPR_RF,
                   v.NAME AS VEHICLE_NAME,
                   s.DESIGN_METHOD_TYPE,
                   s.INV_LIMIT_STATE, s.OPR_LIMIT_STATE,
                   s.SPAN_NUM,
                   e.SUPER_STRUCT_MBR_ID
            FROM BRIDGEWARE.ABW_BRIDGE b
            JOIN BRIDGEWARE.ABW_SPNG_MBR_ALT_EVENTS e
                ON b.BRIDGE_ID = e.BRIDGE_ID
            JOIN BRIDGEWARE.ABW_RATING_RESULTS_SUMMARY s
                ON e.SPNG_MBR_ALT_EVENT_ID = s.SPNG_MBR_ALT_EVENT_ID
            JOIN BRIDGEWARE.ABW_LIB_VEHICLE v
                ON s.VEHICLE_ID = v.VEHICLE_ID
            WHERE b.AGENCY_CODE = :bridge_id
            ORDER BY s.INV_RF ASC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"bridge_id": self.bridge_id}).fetchall()

        return [
            {
                "inv_rf": r[0], "opr_rf": r[1],
                "post_rf": r[2], "safe_rf": r[3],
                "legal_inv_rf": r[4], "legal_opr_rf": r[5],
                "permit_inv_rf": r[6], "permit_opr_rf": r[7],
                "vehicle": r[8],
                "design_method": BRR_DESIGN_METHOD_MAP.get(r[9], str(r[9])),
                "inv_limit_state": r[10], "opr_limit_state": r[11],
                "span_num": r[12], "member_id": r[13],
            }
            for r in rows
        ]

    def get_roadway_info(self) -> List[Dict[str, Any]]:
        """Get roadway/route records from the NBI ROADWAY table.

        Returns:
            List of roadway dicts with ADT, route number, etc.
        """
        brkey = self.nbi_info.get("brkey")
        if not brkey:
            return []

        query = self._text("""
            SELECT ON_UNDER, KIND_HIGHWAY, LEVEL_SERVICE,
                   ROUTENUM, ROADWAY_NAME, ADTTOTAL, ADTYEAR, TRUCKPCT
            FROM BRIDGEWARE.ROADWAY
            WHERE BRKEY = :brkey
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"brkey": brkey}).fetchall()

        return [
            {
                "on_under": r[0], "kind_highway": r[1],
                "level_service": r[2], "route_num": r[3],
                "roadway_name": r[4], "adt": r[5],
                "adt_year": r[6], "truck_pct": r[7],
            }
            for r in rows
        ]

    def __repr__(self) -> str:
        cr = self.controlling_rating
        name = self.nbi_info.get("name") or self.nbi_info.get("facility") or ""
        return (
            f"BrRBridge('{self.bridge_id}'{f', {name!r}' if name else ''})\n"
            f"  Controlling Rating:\n"
            f"    Inventory RF: {cr.inventory_rf}\n"
            f"    Operating RF: {cr.operating_rf}\n"
            f"    Legal RF:     {cr.legal_rf}\n"
            f"    Permit RF:    {cr.permit_rf}\n"
            f"    Vehicle:      {cr.controlling_vehicle}\n"
            f"    Method:       {cr.rating_method}\n"
            f"    Limit State:  {cr.limit_state}\n"
            f"  Member Capacities: {len(self.member_capacities)} points\n"
            f"  Vehicle Loads:     {len(self.vehicle_loads)} vehicles"
        )


# ============================================================================
# AssetWise Raw Bridge (Direct Bentley API)
# ============================================================================

class AssetwiseRawBridge:
    """Direct connection to the Bentley AssetWise (InspectTech) API.

    Authenticates using credentials from ``~/secrets.json`` and pulls raw
    inspection records, element-level defect quantities (CS1-CS4), and
    attachment data.

    Args:
        sfn: The Structure File Number (ODOT bridge identifier).

    Example::

        bridge = AssetwiseRawBridge("2102226")
        print(bridge.current_values)
        elements = bridge.get_elements()

    .. note::
        Requires VPN access to ``ohiodot-it-api.bentley.com``.
    """

    BASE_URL = "https://ohiodot-it-api.bentley.com"

    def __init__(self, sfn: str):
        self.sfn = sfn
        secrets = _load_secrets()
        self._session = requests.Session()
        from requests.auth import HTTPBasicAuth
        self._session.auth = HTTPBasicAuth(
            secrets["BENTLEY_ASSETWISE_KEY_NAME"],
            secrets["BENTLEY_ASSETWISE_API"],
        )
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        self.as_id: Optional[str] = None
        self.current_values: Dict[int, str] = {}
        self._resolve_asset()

    def _resolve_asset(self):
        """Look up the as_id for this SFN via the Asset search endpoint.

        TODO (Dane): The exact endpoint for SFN -> as_id lookup may differ.
        Try these exploratory API calls and feed the JSON to Gemini:

        1) GET /api/Asset/GetAssetsByCode/{sfn}
           curl -u "$USER:$PASS" "https://ohiodot-it-api.bentley.com/api/Asset/GetAssetsByCode/2102226"

        2) If that doesn't work, try the search endpoint:
           GET /api/Asset/Search?query={sfn}

        3) Once you have as_id, verify current values:
           GET /api/CurrentValue/GetCurrentValuesByAssetId/{as_id}
        """
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/api/Asset/GetAssetsByCode/{self.sfn}"
            )
            if resp.status_code == 200:
                data = resp.json()
                assets = data.get("data", [])
                if assets:
                    self.as_id = str(assets[0].get("as_id", ""))
                    self._fetch_current_values()
                else:
                    logger.warning("AssetWise resolve: No asset found for SFN %s", self.sfn)
            else:
                logger.error("AssetWise resolve: API error %s for SFN %s: %s", 
                             resp.status_code, self.sfn, resp.text)
        except Exception as e:
            logger.error("AssetWise resolve: Request failed for SFN %s: %s", 
                         self.sfn, e, exc_info=True)

    def _fetch_current_values(self):
        """Fetch all current field values for this asset.

        Populates ``self.current_values`` as a dict mapping
        ``fe_id`` (int) -> ``value`` (str).
        """
        if not self.as_id:
            return
        url = f"{self.BASE_URL}/api/CurrentValue/GetCurrentValuesByAssetId/{self.as_id}"
        try:
            resp = self._session.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    for item in data.get("data", []):
                        fid = item.get("fe_id")
                        val = (item.get("cv_value")
                               or item.get("value")
                               or item.get("va_value"))
                        if fid is not None:
                            self.current_values[fid] = val
                else:
                    logger.warning("AssetWise values: API returned success=False for as_id=%s: %s", 
                                   self.as_id, data.get("message"))
            else:
                logger.error("AssetWise values: API error %s for as_id=%s: %s", 
                             resp.status_code, self.as_id, resp.text)
        except Exception as e:
            logger.error("AssetWise values: Request failed for as_id=%s: %s",
                         self.as_id, e, exc_info=True)

    def get_elements(self, report_id: Optional[str] = None) -> List[dict]:
        """Fetch element-level inspection data (CS1-CS4 quantities).

        Args:
            report_id: The inspection report ID. If None, fetches the
                most recent report.

        Returns:
            List of element dicts with keys like totalQuantity,
            state1-state4, se_display_id, etc.

        TODO (Dane): Verify the report_id discovery endpoint:
            GET /api/Report/GetReportsByAssetId/{as_id}
            Then use the most recent report_id automatically.
        """
        if not self.as_id:
            return []

        if report_id is None:
            report_id = self._get_latest_report_id()
            if report_id is None:
                return []

        url = (f"{self.BASE_URL}/api/StructureElement/"
               f"GetElements/1/{report_id}/{self.as_id}")
        try:
            resp = self._session.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    return data.get("value") or data.get("data") or []
                elif isinstance(data, list):
                    return data
        except Exception as e:
            logger.error("Failed to fetch elements for SFN %s: %s", self.sfn, e)
        return []

    def _get_latest_report_id(self) -> Optional[str]:
        """Discover the most recent inspection report ID.

        TODO (Dane): Confirm this endpoint path. Try:
            GET /api/Report/GetReportsByAssetId/{as_id}
        and look for the report with the latest date.
        """
        if not self.as_id:
            return None
        try:
            resp = self._session.get(
                f"{self.BASE_URL}/api/Report/GetReportsByAssetId/{self.as_id}"
            )
            if resp.status_code == 200:
                data = resp.json()
                reports = data.get("data", [])
                if reports:
                    latest = max(reports, key=lambda r: r.get("rp_date", ""))
                    return str(latest.get("rp_id", ""))
        except Exception as e:
            logger.warning("Failed to get reports for as_id=%s: %s",
                           self.as_id, e)
        return None

    def get_field_name(self, fe_id: int) -> str:
        """Look up the human-readable name for a field ID.

        Args:
            fe_id: The AssetWise field entity ID.

        Returns:
            The field name string, or 'Unknown'.
        """
        try:
            resp = self._session.get(f"{self.BASE_URL}/api/Field/{fe_id}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data["data"].get("fe_name", "Unknown")
        except Exception:
            pass
        return "Unknown"

    def __repr__(self) -> str:
        return (
            f"AssetwiseRawBridge(sfn='{self.sfn}', as_id={self.as_id}, "
            f"fields={len(self.current_values)})"
        )


# ============================================================================
# Bridge DB Asset (Internal Django REST API)
# ============================================================================

class BridgeDBAsset:
    """Client for the internal SNBI Django REST API.

    Connects to the PostGIS/Django backend and maps JSON responses to
    clean Python properties for QA/QC scripting and dashboards.

    Args:
        sfn: The Structure File Number.
        base_url: The internal API base URL (default: ``http://localhost:8000``).

    Example::

        bridge = BridgeDBAsset("2102226")
        print(bridge.condition)     # "Good" / "Fair" / "Poor"
        print(bridge.snbi_status)   # "Compliant" / "Non-Compliant"
        print(bridge.coordinates)   # {"lat": 40.123, "lng": -82.456}
    """

    def __init__(self, sfn: str, base_url: str = "http://localhost:8000"):
        self.sfn = sfn
        self._base_url = base_url.rstrip("/")
        self._data: Dict[str, Any] = {}
        self._fetch()

    def _fetch(self):
        """Pull bridge data from the internal API."""
        url = f"{self._base_url}/api/bridges/{self.sfn}/"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            self._data = resp.json()
        except requests.RequestException as e:
            logger.warning("Failed to fetch bridge %s from API: %s", self.sfn, e)
            self._data = {}

    @property
    def condition(self) -> Optional[str]:
        """Bridge condition: 'Good', 'Fair', or 'Poor'."""
        return self._data.get("condition")

    @property
    def snbi_status(self) -> Optional[str]:
        """SNBI compliance status: 'Compliant' or 'Non-Compliant'."""
        return self._data.get("snbiStatus")

    @property
    def last_inspection(self) -> Optional[str]:
        """Date of the most recent inspection (ISO format string)."""
        return self._data.get("lastInspection")

    @property
    def coordinates(self) -> Optional[Dict[str, float]]:
        """Bridge location as ``{"lat": float, "lng": float}``."""
        return self._data.get("coordinates")

    @property
    def bridge_name(self) -> Optional[str]:
        """Human-readable bridge name."""
        return self._data.get("bid02_bridge_name")

    @property
    def year_built(self) -> Optional[int]:
        """Year the bridge was constructed."""
        return self._data.get("bw01_year_built")

    @property
    def district(self) -> Optional[str]:
        """ODOT highway district number."""
        return self._data.get("bl04_highway_district")

    def fetch_compliance_metrics(self) -> Dict[str, Any]:
        """Fetch FHWA NBIP compliance metrics for all bridges.

        Returns:
            Dict with compliance metric data from the
            ``/api/compliance-metrics/`` endpoint.
        """
        url = f"{self._base_url}/api/compliance-metrics/"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("Failed to fetch compliance metrics: %s", e)
            return {}

    def fetch_comparison(self) -> Dict[str, Any]:
        """Compare data sources for this bridge.

        Returns:
            Dict with cross-source comparison from
            ``/api/bridges/{sfn}/compare/``.
        """
        url = f"{self._base_url}/api/bridges/{self.sfn}/compare/"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("Failed to fetch comparison for %s: %s", self.sfn, e)
            return {}

    def __repr__(self) -> str:
        return (
            f"BridgeDBAsset(sfn='{self.sfn}', "
            f"condition={self.condition!r}, "
            f"status={self.snbi_status!r})"
        )


# ============================================================================
# Midas Civil API Objects
# ============================================================================

class MidasNode(BaseModel):
    """A finite element node in the Midas model.

    Attributes:
        id: Midas node ID.
        x: X coordinate.
        y: Y coordinate.
        z: Z coordinate.
    """
    id: int
    x: float
    y: float
    z: float


class MidasMaterial(BaseModel):
    """Material definition from Midas Civil.

    Attributes:
        id: Midas material ID.
        name: Material name (e.g. 'Concrete', 'Steel').
        material_type: Material category string.
        elastic_modulus: Modulus of elasticity (ksi or MPa).
        poisson_ratio: Poisson's ratio.
        thermal_coeff: Coefficient of thermal expansion.
        density: Unit weight / density.
    """
    id: int
    name: str = ""
    material_type: str = ""
    elastic_modulus: Optional[float] = None
    poisson_ratio: Optional[float] = None
    thermal_coeff: Optional[float] = None
    density: Optional[float] = None


class MidasSection(BaseModel):
    """Cross-section properties from Midas Civil.

    Attributes:
        id: Midas section ID.
        name: Section name.
        shape: Shape type string (e.g. 'Rectangle', 'I-Section').
        area: Cross-sectional area.
        iyy: Moment of inertia about the Y-Y axis.
        izz: Moment of inertia about the Z-Z axis.
    """
    id: int
    name: str = ""
    shape: str = ""
    area: Optional[float] = None
    iyy: Optional[float] = None
    izz: Optional[float] = None


class ElementType(str, Enum):
    """Midas element type designators."""
    BEAM = "BEAM"
    TRUSS = "TRUSS"
    PLATE = "PLATE"
    SOLID = "SOLID"
    TENDON = "TENDON"
    SPRING = "SPRING"
    LINK = "LINK"
    RIGID = "RIGID"


class MidasElement(BaseModel):
    """A finite element in the Midas model.

    Attributes:
        id: Midas element ID.
        element_type: Element type (BEAM, TRUSS, etc.).
        material_id: Reference to MidasMaterial.
        section_id: Reference to MidasSection.
        node_ids: List of connected node IDs (2 for beam/truss).
    """
    id: int
    element_type: ElementType = ElementType.BEAM
    material_id: Optional[int] = None
    section_id: Optional[int] = None
    node_ids: List[int] = Field(default_factory=list)

    @property
    def start_node_id(self) -> Optional[int]:
        """ID of the first (start) node."""
        return self.node_ids[0] if self.node_ids else None

    @property
    def end_node_id(self) -> Optional[int]:
        """ID of the last (end) node."""
        return self.node_ids[-1] if len(self.node_ids) > 1 else None


class MidasBoundary(BaseModel):
    """Support / boundary condition from Midas Civil.

    Attributes:
        node_id: The node this boundary applies to.
        dx: Translational restraint in X (True = fixed).
        dy: Translational restraint in Y.
        dz: Translational restraint in Z.
        rx: Rotational restraint about X.
        ry: Rotational restraint about Y.
        rz: Rotational restraint about Z.
        spring_dx: Spring stiffness in X (force/length).
        spring_dy: Spring stiffness in Y.
        spring_dz: Spring stiffness in Z.
        spring_rx: Rotational spring about X.
        spring_ry: Rotational spring about Y.
        spring_rz: Rotational spring about Z.
    """
    node_id: int
    dx: bool = False
    dy: bool = False
    dz: bool = False
    rx: bool = False
    ry: bool = False
    rz: bool = False
    spring_dx: float = 0.0
    spring_dy: float = 0.0
    spring_dz: float = 0.0
    spring_rx: float = 0.0
    spring_ry: float = 0.0
    spring_rz: float = 0.0


class LoadType(str, Enum):
    """Load classification."""
    STATIC = "STATIC"
    MOVING = "MOVING"


class MidasStaticLoad(BaseModel):
    """A static load case from Midas Civil.

    Attributes:
        id: Load case ID.
        name: Load case name.
        description: Optional description.
        load_type: Always STATIC.
    """
    id: int
    name: str = ""
    description: str = ""
    load_type: LoadType = LoadType.STATIC


class MidasMovingLoad(BaseModel):
    """A moving load case from Midas Civil.

    Attributes:
        id: Load case ID.
        name: Load case name.
        description: Optional description.
        load_type: Always MOVING.
        vehicle_load_name: Name of the vehicle load definition.
        standard_code: Design standard (e.g. 'AASHTO-LRFD').
        dynamic_load_allowance: Impact factor percentage.
    """
    id: int
    name: str = ""
    description: str = ""
    load_type: LoadType = LoadType.MOVING
    vehicle_load_name: str = ""
    standard_code: str = ""
    dynamic_load_allowance: float = 33.0


class MidasResult(BaseModel):
    """Analysis results for a single element or node.

    Attributes:
        element_id: Element this result applies to (if element result).
        node_id: Node this result applies to (if nodal result).
        load_case: Name of the load case.
        axial: Axial force.
        shear_y: Shear force in Y.
        shear_z: Shear force in Z.
        moment_y: Bending moment about Y.
        moment_z: Bending moment about Z.
        torsion: Torsional moment.
        dx: Nodal displacement in X.
        dy: Nodal displacement in Y.
        dz: Nodal displacement in Z.
        reaction_x: Reaction force in X (supports only).
        reaction_y: Reaction force in Y.
        reaction_z: Reaction force in Z.
    """
    element_id: Optional[int] = None
    node_id: Optional[int] = None
    load_case: str = ""
    axial: Optional[float] = None
    shear_y: Optional[float] = None
    shear_z: Optional[float] = None
    moment_y: Optional[float] = None
    moment_z: Optional[float] = None
    torsion: Optional[float] = None
    dx: Optional[float] = None
    dy: Optional[float] = None
    dz: Optional[float] = None
    reaction_x: Optional[float] = None
    reaction_y: Optional[float] = None
    reaction_z: Optional[float] = None


class MidasAPIConnection:
    """Low-level HTTP client for the Midas Civil REST API.

    Args:
        api_key: The MAPI-Key for authentication.
        base_url: Midas Civil API base URL.
    """

    def __init__(self, api_key: str, base_url: str = "https://api-v2.midasit.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "MAPI-Key": self.api_key,
            "Content-Type": "application/json",
        })

    def get(self, endpoint: str) -> dict:
        """Perform a GET request to the Midas API.

        Args:
            endpoint: API path (e.g. '/civil/db/node').

        Returns:
            Parsed JSON response as a dict.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        resp = self._session.get(f"{self.base_url}{endpoint}")
        resp.raise_for_status()
        return resp.json()

    def post(self, endpoint: str, data: dict) -> dict:
        """Perform a POST request to the Midas API.

        Args:
            endpoint: API path.
            data: JSON payload.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        resp = self._session.post(f"{self.base_url}{endpoint}", json=data)
        resp.raise_for_status()
        return resp.json()

    def put(self, endpoint: str, data: dict) -> dict:
        """Perform a PUT request to the Midas API.

        Args:
            endpoint: API path.
            data: JSON payload.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        resp = self._session.put(f"{self.base_url}{endpoint}", json=data)
        resp.raise_for_status()
        return resp.json()

    def delete(self, endpoint: str) -> dict:
        """Perform a DELETE request to the Midas API.

        Args:
            endpoint: API path.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        resp = self._session.delete(f"{self.base_url}{endpoint}")
        resp.raise_for_status()
        return resp.json()


def _calculate_3d_distance(node_i: MidasNode, node_j: MidasNode) -> float:
    """Calculate 3D Euclidean distance between two nodes.

    Args:
        node_i: Start node.
        node_j: End node.

    Returns:
        Distance in model units.
    """
    return math.sqrt(
        (node_j.x - node_i.x) ** 2
        + (node_j.y - node_i.y) ** 2
        + (node_j.z - node_i.z) ** 2
    )


class MidasBridge:
    """Orchestrator for a complete Midas Civil bridge model.

    Fetches and stores all structural sub-objects (nodes, elements,
    materials, sections, boundaries, loads, results) from the Midas
    Civil REST API.

    Args:
        api_key: MAPI-Key for authentication. If None, loads from
            ``~/secrets.json`` key ``MIDAS_API_KEY``.
        base_url: Midas API base URL.

    Example::

        bridge = MidasBridge("your-api-key")
        bridge.load_geometry()
        length = bridge.get_element_length(1)
        print(f"Element 1 length: {length:.2f}")
    """

    def __init__(self, api_key: Optional[str] = None,
                 base_url: str = "https://api-v2.midasit.com"):
        if api_key is None:
            secrets = _load_secrets()
            api_key = secrets.get("MIDAS_API_KEY", "")
        self.api = MidasAPIConnection(api_key, base_url)

        self.nodes: Dict[int, MidasNode] = {}
        self.materials: Dict[int, MidasMaterial] = {}
        self.sections: Dict[int, MidasSection] = {}
        self.elements: Dict[int, MidasElement] = {}
        self.boundaries: Dict[int, MidasBoundary] = {}
        self.static_loads: Dict[int, MidasStaticLoad] = {}
        self.moving_loads: Dict[int, MidasMovingLoad] = {}
        self.results: List[MidasResult] = []

    def load_geometry(self):
        """Fetch nodes, materials, sections, and elements from Midas.

        Populates ``self.nodes``, ``self.materials``, ``self.sections``,
        and ``self.elements`` dicts keyed by their Midas IDs.
        """
        self._fetch_nodes()
        self._fetch_materials()
        self._fetch_sections()
        self._fetch_elements()

    def load_boundaries(self):
        """Fetch boundary conditions from Midas."""
        self._fetch_boundaries()

    def load_static_loads(self):
        """Fetch static load cases from Midas."""
        self._fetch_static_loads()

    def load_moving_loads(self):
        """Fetch moving load cases from Midas."""
        self._fetch_moving_loads()

    def load_all(self):
        """Fetch all model data: geometry, boundaries, and loads."""
        self.load_geometry()
        self.load_boundaries()
        self.load_static_loads()
        self.load_moving_loads()

    def _fetch_nodes(self):
        """Parse node data from the Midas ``/civil/db/node`` endpoint."""
        try:
            data = self.api.get("/civil/db/node")
            node_data = data.get("NODE", data)
            for nid_str, props in node_data.items():
                nid = int(nid_str)
                self.nodes[nid] = MidasNode(
                    id=nid,
                    x=props.get("X", 0.0),
                    y=props.get("Y", 0.0),
                    z=props.get("Z", 0.0),
                )
        except Exception as e:
            logger.warning("Failed to fetch nodes: %s", e)

    def _fetch_materials(self):
        """Parse material data from ``/civil/db/matl``."""
        try:
            data = self.api.get("/civil/db/matl")
            matl_data = data.get("MATL", data)
            for mid_str, props in matl_data.items():
                mid = int(mid_str)
                self.materials[mid] = MidasMaterial(
                    id=mid,
                    name=props.get("NAME", ""),
                    material_type=props.get("TYPE", ""),
                    elastic_modulus=props.get("ELAST", None),
                    poisson_ratio=props.get("POISN", None),
                    thermal_coeff=props.get("THERMAL", None),
                    density=props.get("DENSITY", None),
                )
        except Exception as e:
            logger.warning("Failed to fetch materials: %s", e)

    def _fetch_sections(self):
        """Parse section data from ``/civil/db/sect``."""
        try:
            data = self.api.get("/civil/db/sect")
            sect_data = data.get("SECT", data)
            for sid_str, props in sect_data.items():
                sid = int(sid_str)
                self.sections[sid] = MidasSection(
                    id=sid,
                    name=props.get("NAME", ""),
                    shape=props.get("SHAPE", ""),
                    area=props.get("AREA", None),
                    iyy=props.get("IYY", None),
                    izz=props.get("IZZ", None),
                )
        except Exception as e:
            logger.warning("Failed to fetch sections: %s", e)

    def _fetch_elements(self):
        """Parse element data from ``/civil/db/elem``."""
        try:
            data = self.api.get("/civil/db/elem")
            elem_data = data.get("ELEM", data)
            for eid_str, props in elem_data.items():
                eid = int(eid_str)
                etype_str = props.get("TYPE", "BEAM")
                try:
                    etype = ElementType(etype_str)
                except ValueError:
                    etype = ElementType.BEAM

                node_ids = []
                for key in ("iNODE", "jNODE", "NODE"):
                    if key in props:
                        val = props[key]
                        if isinstance(val, list):
                            node_ids.extend(val)
                        else:
                            node_ids.append(int(val))

                self.elements[eid] = MidasElement(
                    id=eid,
                    element_type=etype,
                    material_id=props.get("MATL", None),
                    section_id=props.get("SECT", None),
                    node_ids=node_ids,
                )
        except Exception as e:
            logger.warning("Failed to fetch elements: %s", e)

    def _fetch_boundaries(self):
        """Parse boundary data from ``/civil/db/cons``."""
        try:
            data = self.api.get("/civil/db/cons")
            cons_data = data.get("CONS", data)
            for nid_str, props in cons_data.items():
                nid = int(nid_str)
                self.boundaries[nid] = MidasBoundary(
                    node_id=nid,
                    dx=bool(props.get("DX", False)),
                    dy=bool(props.get("DY", False)),
                    dz=bool(props.get("DZ", False)),
                    rx=bool(props.get("RX", False)),
                    ry=bool(props.get("RY", False)),
                    rz=bool(props.get("RZ", False)),
                )
        except Exception as e:
            logger.warning("Failed to fetch boundaries: %s", e)

    def _fetch_static_loads(self):
        """Parse static load cases from ``/civil/db/stld``."""
        try:
            data = self.api.get("/civil/db/stld")
            stld_data = data.get("STLD", data)
            for lid_str, props in stld_data.items():
                lid = int(lid_str)
                self.static_loads[lid] = MidasStaticLoad(
                    id=lid,
                    name=props.get("NAME", ""),
                    description=props.get("DESC", ""),
                )
        except Exception as e:
            logger.warning("Failed to fetch static loads: %s", e)

    def _fetch_moving_loads(self):
        """Parse moving load cases from ``/civil/db/mvld``."""
        try:
            data = self.api.get("/civil/db/mvld")
            mvld_data = data.get("MVLD", data)
            for lid_str, props in mvld_data.items():
                lid = int(lid_str)
                self.moving_loads[lid] = MidasMovingLoad(
                    id=lid,
                    name=props.get("LCNAME", ""),
                    description=props.get("DESC", ""),
                )
        except Exception as e:
            logger.warning("Failed to fetch moving loads: %s", e)

    def get_element_length(self, elem_id: int) -> float:
        """Calculate the length of a beam/truss element.

        Looks up the element's connected nodes and computes the 3D
        Euclidean distance between them.

        Args:
            elem_id: The Midas element ID.

        Returns:
            Element length in model units.

        Raises:
            KeyError: If the element or its nodes are not loaded.
        """
        elem = self.elements[elem_id]
        if elem.start_node_id is None or elem.end_node_id is None:
            raise ValueError(f"Element {elem_id} has insufficient node connectivity.")
        node_i = self.nodes[elem.start_node_id]
        node_j = self.nodes[elem.end_node_id]
        return _calculate_3d_distance(node_i, node_j)

    def get_element_material(self, elem_id: int) -> Optional[MidasMaterial]:
        """Get the material assigned to an element.

        Args:
            elem_id: The Midas element ID.

        Returns:
            The MidasMaterial object, or None if not assigned.
        """
        elem = self.elements[elem_id]
        if elem.material_id is not None:
            return self.materials.get(elem.material_id)
        return None

    def get_element_section(self, elem_id: int) -> Optional[MidasSection]:
        """Get the section assigned to an element.

        Args:
            elem_id: The Midas element ID.

        Returns:
            The MidasSection object, or None if not assigned.
        """
        elem = self.elements[elem_id]
        if elem.section_id is not None:
            return self.sections.get(elem.section_id)
        return None

    def get_supported_nodes(self) -> List[MidasNode]:
        """Get all nodes that have boundary conditions.

        Returns:
            List of MidasNode objects with supports.
        """
        return [
            self.nodes[nid]
            for nid in self.boundaries
            if nid in self.nodes
        ]

    def __repr__(self) -> str:
        return (
            f"MidasBridge(\n"
            f"  nodes={len(self.nodes)},\n"
            f"  elements={len(self.elements)},\n"
            f"  materials={len(self.materials)},\n"
            f"  sections={len(self.sections)},\n"
            f"  boundaries={len(self.boundaries)},\n"
            f"  static_loads={len(self.static_loads)},\n"
            f"  moving_loads={len(self.moving_loads)}\n"
            f")"
        )


# ============================================================================
# Ohio Legal Loads (extracted from Midas API)
# ============================================================================

OHIO_STANDARD_VEHICLES: Dict[str, Dict[str, Any]] = {
    "HL-93TRK": {"standard": "AASHTO-LRFD", "dla": 33},
    "HL-93TDM": {"standard": "AASHTO-LRFD", "dla": 33},
    "HS20-FTG": {"standard": "AASHTO-LRFD", "dla": 15},
    "OH Legal load 2F1": {"standard": "OHDOT LOAD", "dla": 33},
    "OH Legal load 3F1": {"standard": "OHDOT LOAD", "dla": 33},
    "OH Legal load 5C1": {"standard": "OHDOT LOAD", "dla": 33},
    "AASHTO Legal Type 3": {"standard": "AASHTO LEGAL/PERMIT LOAD", "dla": 33},
    "AASHTO Legal Type 3-3": {"standard": "AASHTO LEGAL/PERMIT LOAD", "dla": 33},
    "AASHTO Legal Type 3S2": {"standard": "AASHTO LEGAL/PERMIT LOAD", "dla": 33},
    "AASHTO Posting load SU4": {"standard": "AASHTO LEGAL/PERMIT LOAD", "dla": 33},
    "AASHTO Posting load SU5": {"standard": "AASHTO LEGAL/PERMIT LOAD", "dla": 33},
    "AASHTO Posting load SU6": {"standard": "AASHTO LEGAL/PERMIT LOAD", "dla": 33},
    "AASHTO Posting load SU7": {"standard": "AASHTO LEGAL/PERMIT LOAD", "dla": 33},
    "Type EV2": {"standard": "FAST ACT EV LOADS", "dla": 33},
    "Type EV3": {"standard": "FAST ACT EV LOADS", "dla": 33},
    "PL 60T": {"standard": "OHDOT PERMIT", "dla": 33},
    "PL 65T": {"standard": "OHDOT PERMIT", "dla": 33},
}


# ============================================================================
# TIMS ArcGIS REST Service Objects
# ============================================================================

# --- Base ArcGIS query helper ---

class ArcGISLayer:
    """Generic ArcGIS REST API query helper.

    Provides methods for querying any ArcGIS MapServer layer with spatial
    and attribute filters. All TIMS objects inherit from this.

    Args:
        url: Full URL to the MapServer layer (ending in ``/MapServer/N``).
        max_records: Maximum records per request (server-side limit).
    """

    def __init__(self, url: str, max_records: int = 1000):
        self._url = url.rstrip("/")
        self._max_records = max_records

    def query(
        self,
        where: str = "1=1",
        out_fields: str = "*",
        geometry: Optional[Dict[str, Any]] = None,
        geometry_type: str = "esriGeometryEnvelope",
        spatial_rel: str = "esriSpatialRelIntersects",
        return_geometry: bool = True,
        result_record_count: Optional[int] = None,
        order_by: Optional[str] = None,
    ) -> List[dict]:
        """Query features from the ArcGIS layer.

        Args:
            where: SQL-style WHERE clause.
            out_fields: Comma-separated field names or '*'.
            geometry: Spatial filter geometry dict.
            geometry_type: Type of geometry filter.
            spatial_rel: Spatial relationship for filter.
            return_geometry: Whether to include geometry in results.
            result_record_count: Limit number of results.
            order_by: ORDER BY clause (e.g. 'SFN ASC').

        Returns:
            List of feature attribute dicts (with optional 'geometry' key).
        """
        params: Dict[str, Any] = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "f": "json",
        }
        if geometry:
            params["geometry"] = json.dumps(geometry)
            params["geometryType"] = geometry_type
            params["spatialRel"] = spatial_rel
            params["inSR"] = "4326"
        if result_record_count:
            params["resultRecordCount"] = result_record_count
        if order_by:
            params["orderByFields"] = order_by

        try:
            resp = requests.get(f"{self._url}/query", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            results = []
            for f in features:
                rec = dict(f.get("attributes", {}))
                if return_geometry and "geometry" in f:
                    rec["_geometry"] = f["geometry"]
                results.append(rec)
            return results
        except Exception as e:
            logger.warning("ArcGIS query failed on %s: %s", self._url, e)
            return []

    def query_by_bbox(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        out_fields: str = "*",
        where: str = "1=1",
    ) -> List[dict]:
        """Query features within a bounding box (WGS84).

        Args:
            xmin: West longitude.
            ymin: South latitude.
            xmax: East longitude.
            ymax: North latitude.
            out_fields: Fields to return.
            where: Additional attribute filter.

        Returns:
            List of feature attribute dicts.
        """
        envelope = {
            "xmin": xmin, "ymin": ymin,
            "xmax": xmax, "ymax": ymax,
            "spatialReference": {"wkid": 4326},
        }
        return self.query(
            where=where,
            out_fields=out_fields,
            geometry=envelope,
            geometry_type="esriGeometryEnvelope",
        )

    def query_by_point(
        self,
        lon: float,
        lat: float,
        buffer_miles: float = 1.0,
        out_fields: str = "*",
        where: str = "1=1",
    ) -> List[dict]:
        """Query features near a point.

        Args:
            lon: Longitude (WGS84).
            lat: Latitude (WGS84).
            buffer_miles: Search radius in miles.
            out_fields: Fields to return.
            where: Additional attribute filter.

        Returns:
            List of feature attribute dicts.
        """
        # Approximate degrees per mile at Ohio latitudes (~40°N)
        deg_per_mile_lat = 1.0 / 69.0
        deg_per_mile_lon = 1.0 / 54.6
        dx = buffer_miles * deg_per_mile_lon
        dy = buffer_miles * deg_per_mile_lat
        return self.query_by_bbox(
            lon - dx, lat - dy, lon + dx, lat + dy,
            out_fields=out_fields, where=where,
        )


# --- TIMS Layer URL Constants ---

TIMS_BASE = "https://tims.dot.state.oh.us/ags/rest/services"

TIMS_URLS = {
    "bridge_inventory": f"{TIMS_BASE}/Assets/Bridge_Inventory/MapServer/0",
    "historic_bridge": f"{TIMS_BASE}/Assets/Historic_Bridge_Inventory/MapServer/0",
    "stone_culvert": f"{TIMS_BASE}/Assets/Stone_Culvert_Inventory/MapServer/0",
    "retaining_wall": f"{TIMS_BASE}/Assets/Retaining_Wall_Inventory/MapServer/0",
    "geotech_boreholes": f"{TIMS_BASE}/Assets/Geotech_Bore_Hole_Locations/MapServer/0",
    "rail_crossings": f"{TIMS_BASE}/Assets/Rail_Crossing_Inventory/MapServer/0",
    "rail_lines": f"{TIMS_BASE}/Assets/Rail_Lines/MapServer/0",
    "road_inventory": f"{TIMS_BASE}/Roadway_Information/Road_Inventory/MapServer/0",
    "functional_class": f"{TIMS_BASE}/ROADWAY/Functional_Class/MapServer/0",
    "nhs": f"{TIMS_BASE}/ROADWAY/NHS/MapServer/0",
    "freight_network": f"{TIMS_BASE}/ROADWAY/National_Highway_Freight_Network/MapServer/0",
    "traffic_stations": f"{TIMS_BASE}/Roadway_Information/Traffic_Count_Stations/MapServer/0",
    "scenic_rivers": f"{TIMS_BASE}/Environmental/Scenic_Rivers/MapServer/0",
    "mussel_streams": f"{TIMS_BASE}/Environmental/Mussel_Streams/MapServer/0",
    "wetlands": f"{TIMS_BASE}/Environmental/National_Wetland_Inventory/MapServer/0",
    "huc8": f"{TIMS_BASE}/Environmental/NRCS_HUC_8/MapServer/0",
    "huc12": f"{TIMS_BASE}/Environmental/NRCS_HUC_12/MapServer/0",
    "dwp_lines": f"{TIMS_BASE}/Planning_Engineering/District_Work_Plan/MapServer/0",
    "dwp_points": f"{TIMS_BASE}/Planning_Engineering/District_Work_Plan/MapServer/1",
    "current_projects_lines": f"{TIMS_BASE}/Planning_Engineering/Current_Projects/MapServer/0",
    "current_projects_points": f"{TIMS_BASE}/Planning_Engineering/Current_Projects/MapServer/1",
    "project_history": f"{TIMS_BASE}/Planning_Engineering/Project_History/MapServer/0",
    "districts": f"{TIMS_BASE}/Boundaries/ODOT_Districts/MapServer/0",
    "counties": f"{TIMS_BASE}/Boundaries/County/MapServer/0",
    "cities": f"{TIMS_BASE}/Boundaries/Cities_Villages/MapServer/0",
}

# ODOT District -> County FIPS mapping
ODOT_DISTRICT_COUNTIES: Dict[str, List[int]] = {
    "01": [3, 39, 63, 65, 125, 137, 161, 175],
    "02": [51, 69, 95, 123, 143, 147, 171, 173],
    "03": [5, 33, 43, 77, 93, 103, 139, 169],
    "04": [7, 99, 133, 151, 153, 155],
    "05": [31, 45, 59, 83, 89, 119, 127],
    "06": [41, 47, 49, 97, 101, 117, 129, 159],
    "07": [11, 21, 23, 37, 91, 107, 109, 113, 149],
    "08": [17, 25, 27, 57, 61, 135, 165],
    "09": [1, 15, 71, 79, 87, 131, 141, 145],
    "10": [9, 53, 73, 105, 111, 115, 121, 163, 167],
    "11": [13, 19, 29, 67, 75, 81, 157],
    "12": [35, 55, 85],
}


# --- TIMS Bridge ---

class TIMSBridge:
    """ODOT TIMS Bridge Inventory record.

    Fetches bridge data from the TIMS ArcGIS REST endpoint using the
    Structure File Number (SFN).

    Args:
        sfn: Structure File Number (e.g. '2102226').

    Example::

        bridge = TIMSBridge("2102226")
        print(bridge.county)        # "DEL"
        print(bridge.district)      # "06"
        print(bridge.lat, bridge.lon)
        print(bridge.condition_ratings)
        print(bridge.is_structurally_deficient)

    Raises:
        ValueError: If no bridge found with the given SFN.
    """

    _layer = ArcGISLayer(TIMS_URLS["bridge_inventory"])

    # Condition rating codes: 0-3 = structurally deficient threshold
    _SD_THRESHOLD = 4

    def __init__(self, sfn: str):
        self.sfn = sfn.strip()
        self._data: Dict[str, Any] = {}
        self._fetch()

    def _fetch(self):
        """Query TIMS for this bridge's record."""
        results = self._layer.query(
            where=f"SFN='{self.sfn}'",
            out_fields="*",
            return_geometry=True,
        )
        if not results:
            raise ValueError(f"No bridge found in TIMS with SFN '{self.sfn}'")
        self._data = results[0]

    def _get(self, key: str, default=None):
        """Case-insensitive attribute lookup."""
        val = self._data.get(key)
        return val if val is not None else default

    # --- Location ---
    @property
    def lat(self) -> Optional[float]:
        """Latitude in decimal degrees."""
        return self._get("LATITUDE_DD")

    @property
    def lon(self) -> Optional[float]:
        """Longitude in decimal degrees."""
        return self._get("LONGITUDE_DD")

    @property
    def county(self) -> Optional[str]:
        """County code (e.g. 'DEL', 'FRA')."""
        return self._get("COUNTY_CD")

    @property
    def district(self) -> Optional[str]:
        """ODOT district number (e.g. '06')."""
        return self._get("DISTRICT")

    @property
    def facility_carried(self) -> Optional[str]:
        """Road/route carried on the bridge."""
        return self._get("STR_LOC_CARRIED")

    @property
    def feature_intersected(self) -> Optional[str]:
        """Feature crossed by the bridge (stream, road, rail)."""
        return self._get("STR_LOC")

    # --- Structural ---
    @property
    def year_built(self) -> Optional[int]:
        """Year the bridge was built."""
        yr_epoch = self._get("YR_BUILT")
        if yr_epoch and isinstance(yr_epoch, (int, float)):
            try:
                # Use timedelta from Unix epoch to handle pre-1970 dates
                # (Windows doesn't support negative timestamps in utcfromtimestamp)
                epoch = datetime(1970, 1, 1)
                dt = epoch + timedelta(milliseconds=yr_epoch)
                return dt.year
            except (OverflowError, ValueError, OSError):
                return None
        return None

    @property
    def main_material(self) -> Optional[str]:
        """Main span material code."""
        return self._get("MAIN_STR_MTL_CD")

    @property
    def main_type(self) -> Optional[str]:
        """Main span design type code."""
        return self._get("MAIN_STR_TYPE_CD")

    @property
    def total_spans(self) -> Optional[int]:
        """Total number of spans."""
        return self._get("TOTAL_SPANS")

    @property
    def max_span_length(self) -> Optional[float]:
        """Maximum span length."""
        return self._get("MAX_SPAN_LEN")

    @property
    def overall_length(self) -> Optional[float]:
        """Overall structure length."""
        return self._get("OVRL_STR_LEN")

    @property
    def deck_width(self) -> Optional[float]:
        """Deck width out-to-out."""
        return self._get("DECK_WD")

    @property
    def roadway_width(self) -> Optional[float]:
        """Bridge roadway width (curb-to-curb)."""
        return self._get("BRG_RDW_WD")

    @property
    def deck_area(self) -> Optional[float]:
        """Deck area in square feet."""
        return self._get("DECK_AREA")

    @property
    def skew(self) -> Optional[int]:
        """Skew angle in degrees."""
        return self._get("SKEW_DEG")

    @property
    def lanes_on(self) -> Optional[int]:
        """Number of lanes on the bridge."""
        return self._get("LANES_ON")

    @property
    def lanes_under(self) -> Optional[int]:
        """Number of lanes under the bridge."""
        return self._get("LANES_UND")

    # --- Traffic ---
    @property
    def adt(self) -> Optional[int]:
        """Average Daily Traffic on the route."""
        return self._get("INVENT_RTE_ADT")

    @property
    def future_adt(self) -> Optional[int]:
        """Projected future ADT."""
        return self._get("FUTURE_ADT")

    # --- Condition ---
    @property
    def deck_rating(self) -> Optional[str]:
        """Deck condition summary rating (0-9, N)."""
        return self._get("DECK_SUMMARY")

    @property
    def superstructure_rating(self) -> Optional[str]:
        """Superstructure condition summary rating."""
        return self._get("SUPS_SUMMARY")

    @property
    def substructure_rating(self) -> Optional[str]:
        """Substructure condition summary rating."""
        return self._get("SUBS_SUMMARY")

    @property
    def culvert_rating(self) -> Optional[str]:
        """Culvert condition summary rating."""
        return self._get("CULVERT_SUMMARY")

    @property
    def channel_rating(self) -> Optional[str]:
        """Channel condition summary rating."""
        return self._get("CHAN_SUMMARY")

    @property
    def scour_critical(self) -> Optional[str]:
        """Scour critical rating code."""
        return self._get("SCOUR_CRIT_CD")

    @property
    def sufficiency_rating(self) -> Optional[float]:
        """Sufficiency rating (0-100)."""
        val = self._get("SUFF_RATING")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def condition_ratings(self) -> Dict[str, Optional[str]]:
        """All condition ratings as a dict."""
        return {
            "deck": self.deck_rating,
            "superstructure": self.superstructure_rating,
            "substructure": self.substructure_rating,
            "culvert": self.culvert_rating,
            "channel": self.channel_rating,
            "scour": self.scour_critical,
        }

    @property
    def is_structurally_deficient(self) -> bool:
        """Whether the bridge is structurally deficient.

        A bridge is SD if any of deck, superstructure, substructure,
        or culvert ratings are <= 4.
        """
        for rating in [self.deck_rating, self.superstructure_rating,
                       self.substructure_rating, self.culvert_rating]:
            if rating is not None:
                try:
                    if int(rating) <= self._SD_THRESHOLD:
                        return True
                except (ValueError, TypeError):
                    continue
        return False

    @property
    def is_scour_critical(self) -> bool:
        """Whether the bridge is scour-critical (codes 0-3, T, U)."""
        sc = self.scour_critical
        if sc is None:
            return False
        return sc in ("0", "1", "2", "3", "T", "U")

    # --- Load Rating ---
    @property
    def inventory_rating_factor(self) -> Optional[float]:
        """Inventory load rating factor."""
        val = self._get("RAT_INV_LOAD_FACT")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def operating_rating_factor(self) -> Optional[float]:
        """Operating load rating factor."""
        val = self._get("RAT_OPR_LOAD_FACT")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def design_load(self) -> Optional[str]:
        """Design load code."""
        return self._get("DESIGN_LOAD_CD")

    # --- Classification ---
    @property
    def owner(self) -> Optional[str]:
        """Owner code."""
        return self._get("OWNER_CD")

    @property
    def maintenance_responsibility(self) -> Optional[str]:
        """Maintenance responsibility code."""
        return self._get("MAINT_RESP_CD")

    @property
    def functional_class(self) -> Optional[str]:
        """Functional classification code."""
        return self._get("FUNC_CLAS_CD")

    @property
    def nhs_designation(self) -> Optional[str]:
        """NHS designation code."""
        return self._get("INVENT_NHS_CD")

    @property
    def bypass_detour_length(self) -> Optional[str]:
        """Bypass/detour length code."""
        return self._get("BYPASS_LEN")

    # --- Inspection ---
    @property
    def fracture_critical(self) -> bool:
        """Whether fracture-critical inspection is required."""
        return self._get("FRAC_CRIT_INSP_SW") == "Y"

    @property
    def underwater_inspection(self) -> bool:
        """Whether underwater inspection is required."""
        return self._get("DIVE_INSP_SW") == "Y"

    # --- Clearances ---
    @property
    def min_vertical_clearance(self) -> Optional[float]:
        """Minimum vertical clearance on bridge (feet)."""
        return self._get("MIN_VRT_CLR_BRG")

    @property
    def approach_roadway_width(self) -> Optional[float]:
        """Approach roadway width (feet)."""
        val = self._get("APPRH_RDW_WD")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    # --- Waterway ---
    @property
    def drainage_area(self) -> Optional[float]:
        """Drainage area (square miles)."""
        val = self._get("DRN_AREA")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def stream_velocity(self) -> Optional[float]:
        """Stream velocity (fps)."""
        val = self._get("STREAM_VELOCITY")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def waterway_adequacy(self) -> Optional[str]:
        """Waterway adequacy appraisal rating."""
        return self._get("WW_ADEQUACY_CD")

    # --- Raw access ---
    @property
    def raw(self) -> Dict[str, Any]:
        """Full raw attribute dict from TIMS."""
        return dict(self._data)

    def __repr__(self) -> str:
        yr = self.year_built or "?"
        cond = "/".join(
            str(r) if r else "?" for r in [
                self.deck_rating, self.superstructure_rating,
                self.substructure_rating,
            ]
        )
        return (
            f"TIMSBridge(sfn='{self.sfn}', "
            f"'{self.facility_carried or '?'}' over '{self.feature_intersected or '?'}', "
            f"built={yr}, D/S/S={cond}, "
            f"suff={self.sufficiency_rating})"
        )

    @classmethod
    def search_by_bbox(
        cls,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        where: str = "1=1",
    ) -> List[Dict[str, Any]]:
        """Find bridges within a bounding box.

        Args:
            xmin: West longitude.
            ymin: South latitude.
            xmax: East longitude.
            ymax: North latitude.
            where: Additional SQL filter.

        Returns:
            List of bridge attribute dicts.
        """
        return cls._layer.query_by_bbox(xmin, ymin, xmax, ymax, where=where)

    @classmethod
    def search_near(
        cls,
        lon: float,
        lat: float,
        radius_miles: float = 5.0,
        where: str = "1=1",
    ) -> List[Dict[str, Any]]:
        """Find bridges near a coordinate.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius in miles.
            where: Additional SQL filter.

        Returns:
            List of bridge attribute dicts.
        """
        return cls._layer.query_by_point(lon, lat, radius_miles, where=where)

    @classmethod
    def search_by_county(cls, county_cd: str) -> List[Dict[str, Any]]:
        """Find all bridges in a county.

        Args:
            county_cd: County code (e.g. 'DEL', 'FRA').

        Returns:
            List of bridge attribute dicts.
        """
        return cls._layer.query(where=f"COUNTY_CD='{county_cd}'")

    @classmethod
    def search_by_district(cls, district: str) -> List[Dict[str, Any]]:
        """Find all bridges in an ODOT district.

        Args:
            district: District number (e.g. '06').

        Returns:
            List of bridge attribute dicts.
        """
        return cls._layer.query(where=f"DISTRICT='{district}'")


# --- TIMS Project (District Work Plan) ---

class TIMSProject:
    """ODOT TIMS District Work Plan project record.

    Wraps the DWP Lines and Points layers for querying active and
    planned construction projects.

    Example::

        projects = TIMSProject.search_by_district("06")
        for p in projects:
            print(p["PID_NBR"], p["PROJECT_NME"])
    """

    _lines_layer = ArcGISLayer(TIMS_URLS["dwp_lines"])
    _points_layer = ArcGISLayer(TIMS_URLS["dwp_points"])

    @classmethod
    def search_by_district(cls, district: str) -> List[Dict[str, Any]]:
        """Find projects in an ODOT district.

        Args:
            district: District number (e.g. '06').

        Returns:
            List of project attribute dicts with geometry.
        """
        return cls._lines_layer.query(
            where=f"DISTRICT_NBR='{district}'",
            out_fields="*",
        )

    @classmethod
    def search_by_county(cls, county: str) -> List[Dict[str, Any]]:
        """Find projects in a county.

        Args:
            county: County name (e.g. 'DELAWARE').

        Returns:
            List of project attribute dicts.
        """
        return cls._lines_layer.query(
            where=f"COUNTY_NME_WORK_LOCATION='{county.upper()}'",
        )

    @classmethod
    def search_near(
        cls, lon: float, lat: float, radius_miles: float = 5.0,
    ) -> List[Dict[str, Any]]:
        """Find projects near a coordinate.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of project attribute dicts.
        """
        return cls._lines_layer.query_by_point(lon, lat, radius_miles)

    @classmethod
    def search_by_pid(cls, pid: str) -> List[Dict[str, Any]]:
        """Find a project by PID number.

        Args:
            pid: Project ID number.

        Returns:
            List of matching project dicts.
        """
        return cls._lines_layer.query(where=f"PID_NBR='{pid}'")


# --- TIMS Road (Functional Class, NHS, Freight) ---

class TIMSRoad:
    """ODOT TIMS road network query interface.

    Provides access to functional classification, NHS designation,
    and freight network layers.
    """

    _func_class = ArcGISLayer(TIMS_URLS["functional_class"])
    _nhs = ArcGISLayer(TIMS_URLS["nhs"])
    _freight = ArcGISLayer(TIMS_URLS["freight_network"])
    _road_inv = ArcGISLayer(TIMS_URLS["road_inventory"])

    @classmethod
    def functional_class_near(
        cls, lon: float, lat: float, radius_miles: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Get functional classification segments near a point.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of road segment dicts with FUNCTION_CLASS_CD.
        """
        return cls._func_class.query_by_point(lon, lat, radius_miles)

    @classmethod
    def nhs_routes_near(
        cls, lon: float, lat: float, radius_miles: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """Get NHS route segments near a point.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of NHS segment dicts.
        """
        return cls._nhs.query_by_point(lon, lat, radius_miles)

    @classmethod
    def freight_network_near(
        cls, lon: float, lat: float, radius_miles: float = 5.0,
    ) -> List[Dict[str, Any]]:
        """Get freight network segments near a point.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of freight network dicts.
        """
        return cls._freight.query_by_point(lon, lat, radius_miles)


# --- TIMS Environmental ---

class TIMSWaterway:
    """ODOT TIMS environmental waterway layers.

    Provides access to scenic rivers and mussel streams for
    environmental constraint checking.
    """

    _scenic = ArcGISLayer(TIMS_URLS["scenic_rivers"])
    _mussel = ArcGISLayer(TIMS_URLS["mussel_streams"])
    _wetlands = ArcGISLayer(TIMS_URLS["wetlands"])

    @classmethod
    def scenic_rivers_near(
        cls, lon: float, lat: float, radius_miles: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """Find scenic rivers near a point.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of scenic river feature dicts.
        """
        return cls._scenic.query_by_point(lon, lat, radius_miles)

    @classmethod
    def mussel_streams_near(
        cls, lon: float, lat: float, radius_miles: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """Find mussel habitat streams near a point.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of mussel stream feature dicts.
        """
        return cls._mussel.query_by_point(lon, lat, radius_miles)

    @classmethod
    def wetlands_near(
        cls, lon: float, lat: float, radius_miles: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Find NWI wetlands near a point.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of wetland feature dicts.
        """
        return cls._wetlands.query_by_point(lon, lat, radius_miles)


# ============================================================================
# USGS / NHD Hydrology Objects
# ============================================================================

class NHDFlowline:
    """National Hydrography Dataset Plus (NHDPlus HR) flowline query.

    Queries the USGS NHDPlus_HR MapServer for stream/river flowlines
    near bridge locations. No authentication required.

    Example::

        streams = NHDFlowline.near(-82.949, 40.182, radius_miles=0.5)
        for s in streams:
            print(s["GNIS_Name"], "Order:", s.get("StreamOrder"))
    """

    _url = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer"
    # Layer 3 = NetworkNHDFlowline (stream lines with StreamOrder)
    _flowline_layer = ArcGISLayer(f"{_url}/3", max_records=2000)
    # Layer 9 = NHDWaterbody (lakes, ponds, reservoirs)
    _waterbody_layer = ArcGISLayer(f"{_url}/9", max_records=2000)
    # Layer 12 = WBDHU12 (12-digit HUC watershed boundaries)
    _huc12_layer = ArcGISLayer(f"{_url}/12", max_records=2000)

    @classmethod
    def near(
        cls,
        lon: float,
        lat: float,
        radius_miles: float = 0.5,
        out_fields: str = "GNIS_Name,FType,FCode,StreamOrder,LengthKm,Permanent_Identifier",
    ) -> List[Dict[str, Any]]:
        """Find stream flowlines near a coordinate.

        Args:
            lon: Longitude (WGS84).
            lat: Latitude (WGS84).
            radius_miles: Search radius in miles.
            out_fields: Fields to return.

        Returns:
            List of flowline feature dicts.
        """
        return cls._flowline_layer.query_by_point(
            lon, lat, radius_miles, out_fields=out_fields,
        )

    @classmethod
    def waterbodies_near(
        cls,
        lon: float,
        lat: float,
        radius_miles: float = 1.0,
        out_fields: str = "GNIS_Name,FType,FCode,AreaSqKm",
    ) -> List[Dict[str, Any]]:
        """Find waterbodies (lakes, ponds) near a coordinate.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.
            out_fields: Fields to return.

        Returns:
            List of waterbody feature dicts.
        """
        return cls._waterbody_layer.query_by_point(
            lon, lat, radius_miles, out_fields=out_fields,
        )

    @classmethod
    def huc12_at(
        cls,
        lon: float,
        lat: float,
    ) -> List[Dict[str, Any]]:
        """Find the HUC-12 watershed containing a point.

        Args:
            lon: Longitude.
            lat: Latitude.

        Returns:
            List of HUC-12 boundary dicts.
        """
        return cls._huc12_layer.query_by_point(
            lon, lat, buffer_miles=0.01, out_fields="*",
        )


class USGSStreamStats:
    """USGS StreamStats API wrapper for watershed delineation.

    Delineates the drainage basin at a lat/lng point and returns
    basin characteristics (drainage area, slope, precipitation)
    and flow statistics (peak flows, mean annual flow).

    Example::

        result = USGSStreamStats.delineate(-82.949, 40.182)
        print(result["drainage_area_sqmi"])
        print(result["peak_flows"])
    """

    _base = "https://streamstats.usgs.gov/ss-delineate/v1"

    @classmethod
    def delineate(
        cls,
        lon: float,
        lat: float,
        region: str = "OH",
    ) -> Dict[str, Any]:
        """Delineate a watershed and return basin characteristics.

        Args:
            lon: Longitude (WGS84).
            lat: Latitude (WGS84).
            region: State/region code (default 'OH').

        Returns:
            Dict with keys:
                - ``drainage_area_sqmi``: Drainage area in square miles.
                - ``basin_characteristics``: Dict of parameter code -> value.
                - ``peak_flows``: Dict of recurrence interval -> flow (cfs).
                - ``watershed_geojson``: GeoJSON of the delineated basin.
                - ``raw``: Full API response.
        """
        url = f"{cls._base}/delineate/sshydro/{region}"
        params = {"lat": lat, "lon": lon}

        try:
            resp = requests.get(url, params=params, timeout=120)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("StreamStats delineation failed: %s", e)
            return {"drainage_area_sqmi": None, "basin_characteristics": {},
                    "peak_flows": {}, "watershed_geojson": None, "raw": {}}

        # Parse basin characteristics
        basin_chars = {}
        drainage_area = None
        for param in data.get("parameters", []):
            code = param.get("code", "")
            value = param.get("value")
            basin_chars[code] = value
            if code == "DRNAREA":
                drainage_area = value

        # Parse flow statistics
        peak_flows = {}
        for stat in data.get("flowStatistics", []):
            for regression in stat.get("regressionEquations", []):
                for flow in regression.get("flowStatistics", []):
                    name = flow.get("statisticGroupName", "")
                    value = flow.get("value")
                    if value is not None:
                        peak_flows[name] = value

        # Extract watershed GeoJSON
        watershed = data.get("globalwatershed")

        return {
            "drainage_area_sqmi": drainage_area,
            "basin_characteristics": basin_chars,
            "peak_flows": peak_flows,
            "watershed_geojson": watershed,
            "raw": data,
        }

    @classmethod
    def delineate_features_only(
        cls,
        lon: float,
        lat: float,
        region: str = "OH",
    ) -> Optional[dict]:
        """Quick delineation returning just the watershed boundary.

        Args:
            lon: Longitude.
            lat: Latitude.
            region: State code.

        Returns:
            GeoJSON FeatureCollection of the watershed, or None.
        """
        url = f"{cls._base}/delineate/features/{region}"
        try:
            resp = requests.get(url, params={"lat": lat, "lon": lon}, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("StreamStats feature delineation failed: %s", e)
            return None


class USGSGauge:
    """USGS Water Services stream gauge query.

    Queries active USGS stream gauges in Ohio for real-time
    discharge and gage height data.

    Example::

        gauges = USGSGauge.near(-82.949, 40.182, radius_miles=10)
        for g in gauges:
            print(g["station_nm"], g["site_no"])
    """

    _base = "https://waterservices.usgs.gov/nwis"

    @classmethod
    def near(
        cls,
        lon: float,
        lat: float,
        radius_miles: float = 10.0,
    ) -> List[Dict[str, Any]]:
        """Find active USGS stream gauges near a point.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.

        Returns:
            List of gauge site dicts with site_no, station_nm,
            dec_lat_va, dec_long_va, etc.
        """
        deg_lat = radius_miles / 69.0
        deg_lon = radius_miles / 54.6
        bbox = f"{lon - deg_lon},{lat - deg_lat},{lon + deg_lon},{lat + deg_lat}"

        try:
            resp = requests.get(
                f"{cls._base}/site/",
                params={
                    "format": "json",
                    "bBox": bbox,
                    "siteType": "ST",
                    "siteStatus": "active",
                    "hasDataTypeCd": "iv",
                    "parameterCd": "00060",
                    "siteOutput": "expanded",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            sites = data.get("value", {}).get("timeSeries", [])
            if not sites:
                # Try alternative JSON structure
                sites_list = []
                for ts in data.get("value", {}).get("queryInfo", {}).get("sites", []):
                    sites_list.append(ts)
                return sites_list
            return sites
        except Exception as e:
            logger.warning("USGS gauge query failed: %s", e)
            return []

    @classmethod
    def by_site(cls, site_no: str) -> Dict[str, Any]:
        """Get current instantaneous values for a gauge.

        Args:
            site_no: USGS site number (e.g. '03227500').

        Returns:
            Dict with discharge_cfs, gage_height_ft, datetime, site_name.
        """
        try:
            resp = requests.get(
                f"{cls._base}/iv/",
                params={
                    "format": "json",
                    "sites": site_no,
                    "parameterCd": "00060,00065",
                    "siteStatus": "active",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            result: Dict[str, Any] = {"site_no": site_no}
            for ts in data.get("value", {}).get("timeSeries", []):
                var_code = ts.get("variable", {}).get("variableCode", [{}])[0].get("value")
                values = ts.get("values", [{}])[0].get("value", [])
                if values:
                    latest = values[-1]
                    if var_code == "00060":
                        result["discharge_cfs"] = float(latest.get("value", 0))
                    elif var_code == "00065":
                        result["gage_height_ft"] = float(latest.get("value", 0))
                    result["datetime"] = latest.get("dateTime")
                site_info = ts.get("sourceInfo", {})
                result["site_name"] = site_info.get("siteName", "")
            return result
        except Exception as e:
            logger.warning("USGS gauge IV query failed for %s: %s", site_no, e)
            return {"site_no": site_no}


# ============================================================================
# SNBI Compliance Checker
# ============================================================================

# FHWA SNBI field requirements by category
# Each entry: (field_code, description, required_for)
# required_for: "all" = all bridges, "nhs" = NHS only, "sd" = SD only, etc.

SNBI_REQUIRED_FIELDS: List[Tuple[str, str, str]] = [
    # Identification
    ("BID01", "Bridge Number", "all"),
    # Location
    ("BL01", "State Code", "all"),
    ("BL02", "County Code", "all"),
    ("BL05", "Latitude", "all"),
    ("BL06", "Longitude", "all"),
    # Classification
    ("BCL01", "Owner", "all"),
    ("BCL02", "Maintenance Responsibility", "all"),
    # Geometry
    ("BG01", "NBIS Bridge Length", "all"),
    ("BG05", "Bridge Width Out-to-Out", "all"),
    ("BG06", "Bridge Width Curb-to-Curb", "all"),
    ("BG09", "Approach Roadway Width", "all"),
    # Load Rating
    ("BLR04", "Load Rating Method", "all"),
    ("BLR05", "Inventory Rating Factor", "all"),
    ("BLR06", "Operating Rating Factor", "all"),
    ("BLR07", "Legal Load Rating Factor", "all"),
    # Condition
    ("BC01", "Deck Condition", "all"),
    ("BC02", "Superstructure Condition", "all"),
    ("BC03", "Substructure Condition", "all"),
    ("BC09", "Channel Condition", "all"),
    ("BC11", "Scour Condition", "all"),
    # Appraisal
    ("BAP03", "Scour Vulnerability", "all"),
    # Work
    ("BW01", "Year Built", "all"),
    # Inspection
    ("BIE02", "Inspection Begin Date", "all"),
    ("BIE05", "Inspection Interval", "all"),
    ("BIE06", "Inspection Due Date", "all"),
    # Features (at least one)
    ("BF01", "Feature Type", "all"),
    # Highway features (for highway crossings)
    ("BH01", "Functional Classification", "highway"),
    ("BH09", "AADT", "highway"),
    ("BH03", "NHS Designation", "nhs"),
    # Posting
    ("BPS01", "Load Posting Status", "all"),
]

# FHWA NBIP 23 Performance Metrics (as Ohio is judged on)
FHWA_NBIP_METRICS: Dict[str, str] = {
    "M1": "Percent of bridge inventory with good condition rating",
    "M2": "Percent of bridge inventory with fair condition rating",
    "M3": "Percent of bridge inventory with poor condition rating",
    "M4": "Percent of NHS bridges in good condition",
    "M5": "Percent of NHS bridges in poor condition",
    "M6": "Percent of bridge deck area in good condition",
    "M7": "Percent of bridge deck area in poor condition",
    "M8": "Number of structurally deficient bridges",
    "M9": "Percent of bridges with load rating",
    "M10": "Number of posted bridges",
    "M11": "Number of bridges with unknown posting status",
    "M12": "Percent of bridges with current inspection",
    "M13": "Number of bridges with overdue inspections",
    "M14": "Number of bridges with overdue underwater inspections",
    "M15": "Number of bridges with overdue NSTM inspections",
    "M16": "Number of scour-critical bridges",
    "M17": "Percent with scour Plan of Action",
    "M18": "Number of bridges with unknown foundations",
    "M19": "Percent of bridges with complete SNBI data",
    "M20": "Percent of element-level inspection data",
    "M21": "Number of bridges needing work",
    "M22": "Data quality index",
    "M23": "Timely data submission rate",
}


class SNBIComplianceChecker:
    """FHWA SNBI compliance validation for bridge records.

    Checks a bridge data dict against SNBI field requirements and
    FHWA NBIP performance metric thresholds.

    Args:
        bridge_data: Dict of SNBI field code -> value. Can come from
            any source (TIMS, AssetWise, Django API).

    Example::

        checker = SNBIComplianceChecker({
            "BID01": "2102226",
            "BL05": 40.18,
            "BL06": -82.95,
            "BC01": "7",
            "BC02": "6",
            "BC03": "5",
            "BIE02": "20240615",
            "BIE06": "20260615",
            # ... more fields
        })
        print(checker.completeness_pct)
        for gap in checker.missing_fields:
            print(f"  MISSING: {gap}")
        print(checker.condition_classification)
        print(checker.is_inspection_current)
    """

    def __init__(self, bridge_data: Dict[str, Any]):
        self._data = bridge_data

    def _has(self, field_code: str) -> bool:
        """Check if a field is populated (not None, not empty string)."""
        val = self._data.get(field_code)
        return val is not None and str(val).strip() != ""

    @property
    def missing_fields(self) -> List[Tuple[str, str]]:
        """List of (field_code, description) for missing required fields.

        Only checks fields required for 'all' bridges.
        """
        missing = []
        for code, desc, scope in SNBI_REQUIRED_FIELDS:
            if scope == "all" and not self._has(code):
                missing.append((code, desc))
        return missing

    @property
    def missing_fields_nhs(self) -> List[Tuple[str, str]]:
        """Additional missing fields for NHS bridges."""
        missing = []
        for code, desc, scope in SNBI_REQUIRED_FIELDS:
            if scope in ("all", "nhs") and not self._has(code):
                missing.append((code, desc))
        return missing

    @property
    def completeness_pct(self) -> float:
        """Percentage of required 'all' fields that are populated."""
        all_fields = [(c, d) for c, d, s in SNBI_REQUIRED_FIELDS if s == "all"]
        if not all_fields:
            return 100.0
        populated = sum(1 for c, _ in all_fields if self._has(c))
        return round(populated / len(all_fields) * 100, 1)

    @property
    def condition_classification(self) -> str:
        """Bridge condition classification: 'Good', 'Fair', or 'Poor'.

        Based on the minimum of deck (BC01), superstructure (BC02),
        and substructure (BC03) condition ratings. Culvert (BC04)
        used if deck/super/sub are not applicable.

        - Good: lowest >= 7
        - Fair: lowest 5-6
        - Poor: lowest <= 4
        """
        ratings = []
        for code in ["BC01", "BC02", "BC03", "BC04"]:
            val = self._data.get(code)
            if val is not None:
                try:
                    ratings.append(int(val))
                except (ValueError, TypeError):
                    continue
        if not ratings:
            return "Unknown"
        lowest = min(ratings)
        if lowest >= 7:
            return "Good"
        elif lowest >= 5:
            return "Fair"
        else:
            return "Poor"

    @property
    def is_structurally_deficient(self) -> bool:
        """Whether the bridge qualifies as structurally deficient.

        SD if any of BC01, BC02, BC03, BC04 <= 4.
        """
        return self.condition_classification == "Poor"

    @property
    def is_inspection_current(self) -> bool:
        """Whether the inspection is current (due date not passed).

        Checks BIE06 (Inspection Due Date) against today.
        """
        due = self._data.get("BIE06")
        if not due:
            return False
        try:
            due_str = str(due).strip()
            due_date = datetime.strptime(due_str, "%Y%m%d").date()
            return due_date >= date.today()
        except (ValueError, TypeError):
            return False

    @property
    def is_scour_critical(self) -> bool:
        """Whether the bridge is scour-critical.

        BC11 in (0, 1, 2, 3, T, U) = scour critical.
        """
        sc = self._data.get("BC11")
        if sc is None:
            return False
        return str(sc).strip() in ("0", "1", "2", "3", "T", "U")

    @property
    def has_scour_poa(self) -> bool:
        """Whether a scour Plan of Action exists (BAP04 populated)."""
        return self._has("BAP04")

    @property
    def is_posted(self) -> bool:
        """Whether the bridge is weight-posted.

        BPS01 in ('P', 'B', 'R') indicates posting.
        """
        ps = self._data.get("BPS01")
        if ps is None:
            return False
        return str(ps).strip().upper() in ("P", "B", "R")

    @property
    def needs_load_rating(self) -> bool:
        """Whether load rating data is missing.

        Returns True if BLR04 (method) or BLR05 (inventory factor) is empty.
        """
        return not self._has("BLR04") or not self._has("BLR05")

    @property
    def compliance_summary(self) -> Dict[str, Any]:
        """Full compliance summary dict."""
        return {
            "sfn": self._data.get("BID01", "?"),
            "completeness_pct": self.completeness_pct,
            "missing_count": len(self.missing_fields),
            "missing_fields": self.missing_fields,
            "condition": self.condition_classification,
            "structurally_deficient": self.is_structurally_deficient,
            "inspection_current": self.is_inspection_current,
            "scour_critical": self.is_scour_critical,
            "has_scour_poa": self.has_scour_poa,
            "posted": self.is_posted,
            "needs_load_rating": self.needs_load_rating,
        }

    def __repr__(self) -> str:
        sfn = self._data.get("BID01", "?")
        return (
            f"SNBICompliance(sfn='{sfn}', "
            f"complete={self.completeness_pct}%, "
            f"cond={self.condition_classification}, "
            f"insp_current={self.is_inspection_current})"
        )


# ============================================================================
# Bridge Engineering Check Utilities
# ============================================================================

def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in miles.

    Args:
        lat1: Latitude of point 1 (degrees).
        lon1: Longitude of point 1 (degrees).
        lat2: Latitude of point 2 (degrees).
        lon2: Longitude of point 2 (degrees).

    Returns:
        Distance in miles.
    """
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


class BridgeEngineeringChecks:
    """High-level spatial analysis utilities for bridge engineering.

    Static methods that combine TIMS, NHD, and USGS data to perform
    common bridge engineering checks.

    Example::

        # Find bridges on a project's detour route
        conflicts = BridgeEngineeringChecks.detour_conflict_scan(
            project_bridges=["2102226", "2102374"],
            detour_bridges=["2103001", "2103002"],
        )

        # Find all streams crossing near a bridge
        streams = BridgeEngineeringChecks.streams_at_bridge("2102226")

        # Check which bridges along a route are scour-vulnerable
        scour = BridgeEngineeringChecks.scour_vulnerability_scan(
            -82.95, 40.18, radius_miles=10
        )
    """

    @staticmethod
    def bridges_near_point(
        lon: float,
        lat: float,
        radius_miles: float = 5.0,
        only_state: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find TIMS bridges near a coordinate.

        Args:
            lon: Longitude.
            lat: Latitude.
            radius_miles: Search radius.
            only_state: If True, filter to state-maintained (MAINT_RESP_CD='01').

        Returns:
            List of bridge dicts, each with computed ``distance_miles``.
        """
        where = "MAINT_RESP_CD='01'" if only_state else "1=1"
        bridges = TIMSBridge.search_near(lon, lat, radius_miles, where=where)
        for b in bridges:
            blat = b.get("LATITUDE_DD")
            blon = b.get("LONGITUDE_DD")
            if blat and blon:
                b["distance_miles"] = round(
                    _haversine_miles(lat, lon, blat, blon), 2
                )
            else:
                b["distance_miles"] = None
        bridges.sort(key=lambda x: x.get("distance_miles") or 999)
        return bridges

    @staticmethod
    def streams_at_bridge(sfn: str) -> Dict[str, Any]:
        """Find NHD streams and TIMS waterways at a bridge location.

        Args:
            sfn: Bridge SFN number.

        Returns:
            Dict with keys:
                - ``bridge``: Basic bridge info.
                - ``nhd_flowlines``: NHD streams within 0.25 miles.
                - ``scenic_rivers``: TIMS scenic rivers within 2 miles.
                - ``mussel_streams``: TIMS mussel streams within 2 miles.
                - ``tims_drainage_area``: Drainage area from TIMS (sq mi).
                - ``tims_stream_velocity``: Stream velocity from TIMS (fps).
        """
        try:
            bridge = TIMSBridge(sfn)
        except ValueError:
            return {"error": f"Bridge {sfn} not found in TIMS"}

        if not bridge.lat or not bridge.lon:
            return {"error": f"Bridge {sfn} has no coordinates"}

        nhd = NHDFlowline.near(bridge.lon, bridge.lat, radius_miles=0.25)
        scenic = TIMSWaterway.scenic_rivers_near(bridge.lon, bridge.lat)
        mussel = TIMSWaterway.mussel_streams_near(bridge.lon, bridge.lat)

        return {
            "bridge": {
                "sfn": sfn,
                "facility": bridge.facility_carried,
                "feature": bridge.feature_intersected,
                "lat": bridge.lat,
                "lon": bridge.lon,
            },
            "nhd_flowlines": nhd,
            "scenic_rivers": scenic,
            "mussel_streams": mussel,
            "tims_drainage_area": bridge.drainage_area,
            "tims_stream_velocity": bridge.stream_velocity,
        }

    @staticmethod
    def scour_vulnerability_scan(
        lon: float,
        lat: float,
        radius_miles: float = 10.0,
    ) -> List[Dict[str, Any]]:
        """Scan for scour-vulnerable bridges near a location.

        Finds bridges that are scour-critical or have high stream order
        waterways, and cross-references with USGS gauge data.

        Args:
            lon: Center longitude.
            lat: Center latitude.
            radius_miles: Search radius.

        Returns:
            List of bridge dicts with scour risk indicators, sorted
            by risk (scour-critical first, then by stream order).
        """
        bridges = TIMSBridge.search_near(
            lon, lat, radius_miles,
            where="MAINT_RESP_CD='01'",
        )

        results = []
        for b in bridges:
            sfn = b.get("SFN", "")
            blat = b.get("LATITUDE_DD")
            blon = b.get("LONGITUDE_DD")
            scour_cd = b.get("SCOUR_CRIT_CD")

            risk_entry = {
                "sfn": sfn,
                "facility": b.get("STR_LOC_CARRIED"),
                "feature": b.get("STR_LOC"),
                "scour_code": scour_cd,
                "is_scour_critical": scour_cd in ("0", "1", "2", "3", "T", "U")
                    if scour_cd else False,
                "drainage_area": b.get("DRN_AREA"),
                "stream_velocity": b.get("STREAM_VELOCITY"),
                "max_stream_order": None,
                "distance_miles": None,
            }

            if blat and blon:
                risk_entry["distance_miles"] = round(
                    _haversine_miles(lat, lon, blat, blon), 2
                )
                # Check NHD stream order at bridge location
                streams = NHDFlowline.near(blon, blat, radius_miles=0.1)
                if streams:
                    orders = [
                        s.get("StreamOrder") for s in streams
                        if s.get("StreamOrder") is not None
                    ]
                    if orders:
                        risk_entry["max_stream_order"] = max(orders)

            results.append(risk_entry)

        # Sort: scour-critical first, then by stream order descending
        results.sort(
            key=lambda x: (
                not x["is_scour_critical"],
                -(x["max_stream_order"] or 0),
            )
        )
        return results

    @staticmethod
    def detour_conflict_scan(
        project_bridges: List[str],
        detour_bridges: List[str],
    ) -> List[Dict[str, Any]]:
        """Check if detour route bridges have capacity/condition issues.

        When a project requires bridge work, traffic detours to
        alternative routes. This check finds whether the detour-route
        bridges have weight restrictions, poor condition, or other
        issues that could conflict with the detour traffic.

        Args:
            project_bridges: SFNs of bridges under construction.
            detour_bridges: SFNs of bridges on the detour route.

        Returns:
            List of conflict dicts for detour bridges with issues.
        """
        conflicts = []
        for sfn in detour_bridges:
            try:
                bridge = TIMSBridge(sfn)
            except ValueError:
                conflicts.append({
                    "sfn": sfn, "issue": "NOT_FOUND",
                    "detail": "Bridge not found in TIMS",
                })
                continue

            issues = []
            if bridge.is_structurally_deficient:
                issues.append("STRUCTURALLY_DEFICIENT")
            if bridge.is_scour_critical:
                issues.append("SCOUR_CRITICAL")
            sr = bridge.sufficiency_rating
            if sr is not None and sr < 50.0:
                issues.append(f"LOW_SUFFICIENCY({sr:.1f})")
            inv_rf = bridge.inventory_rating_factor
            if inv_rf is not None and inv_rf < 1.0:
                issues.append(f"INV_RF_BELOW_1({inv_rf:.2f})")
            rw = bridge.roadway_width
            if rw is not None and rw < 24.0:
                issues.append(f"NARROW_ROADWAY({rw:.1f}ft)")

            if issues:
                conflicts.append({
                    "sfn": sfn,
                    "facility": bridge.facility_carried,
                    "feature": bridge.feature_intersected,
                    "issues": issues,
                    "deck_rating": bridge.deck_rating,
                    "super_rating": bridge.superstructure_rating,
                    "sub_rating": bridge.substructure_rating,
                    "sufficiency": bridge.sufficiency_rating,
                    "inv_rf": bridge.inventory_rating_factor,
                })

        return conflicts

    @staticmethod
    def projects_affecting_bridges(
        lon: float,
        lat: float,
        radius_miles: float = 5.0,
    ) -> Dict[str, Any]:
        """Find construction projects and nearby bridges that may be affected.

        Args:
            lon: Center longitude.
            lat: Center latitude.
            radius_miles: Search radius.

        Returns:
            Dict with ``projects`` list and ``bridges`` list, each with
            distances to the center point.
        """
        projects = TIMSProject.search_near(lon, lat, radius_miles)
        bridges = BridgeEngineeringChecks.bridges_near_point(
            lon, lat, radius_miles, only_state=True,
        )
        return {
            "center": {"lon": lon, "lat": lat},
            "radius_miles": radius_miles,
            "projects": projects,
            "project_count": len(projects),
            "bridges": bridges,
            "bridge_count": len(bridges),
        }

    @staticmethod
    def inspection_currency_check(
        bridges_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check inspection currency across a set of bridges.

        Args:
            bridges_data: List of bridge dicts with SNBI field codes.

        Returns:
            Dict with counts of current, overdue, and unknown inspections.
        """
        current = 0
        overdue = 0
        unknown = 0
        overdue_list = []

        today = date.today()
        for b in bridges_data:
            due = b.get("BIE06") or b.get("INSP_DT")
            sfn = b.get("BID01") or b.get("SFN", "?")
            if not due:
                unknown += 1
                continue
            try:
                due_str = str(due).strip()
                if len(due_str) == 8:
                    due_date = datetime.strptime(due_str, "%Y%m%d").date()
                else:
                    due_date = datetime.utcfromtimestamp(float(due) / 1000).date()
                if due_date >= today:
                    current += 1
                else:
                    overdue += 1
                    days_over = (today - due_date).days
                    overdue_list.append({
                        "sfn": sfn,
                        "due_date": due_date.isoformat(),
                        "days_overdue": days_over,
                    })
            except (ValueError, TypeError, OSError):
                unknown += 1

        overdue_list.sort(key=lambda x: x["days_overdue"], reverse=True)

        total = current + overdue + unknown
        return {
            "total": total,
            "current": current,
            "overdue": overdue,
            "unknown": unknown,
            "currency_pct": round(current / total * 100, 1) if total else 0.0,
            "overdue_bridges": overdue_list,
        }

    @staticmethod
    def posting_analysis(
        bridges_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze posting status across a set of bridges.

        Args:
            bridges_data: List of bridge dicts.

        Returns:
            Dict with counts by posting status and list of posted bridges.
        """
        posted = []
        not_posted = 0
        unknown = 0

        for b in bridges_data:
            ps = b.get("BPS01")
            sfn = b.get("BID01") or b.get("SFN", "?")
            if ps is None or str(ps).strip() == "":
                unknown += 1
            elif str(ps).strip().upper() in ("P", "B", "R"):
                posted.append({
                    "sfn": sfn,
                    "status": str(ps).strip(),
                    "facility": b.get("STR_LOC_CARRIED") or b.get("facility_carried"),
                    "inv_rf": b.get("RAT_INV_LOAD_FACT") or b.get("BLR05"),
                })
            else:
                not_posted += 1

        total = len(posted) + not_posted + unknown
        return {
            "total": total,
            "posted_count": len(posted),
            "not_posted": not_posted,
            "unknown": unknown,
            "posting_rate_pct": round(
                len(posted) / total * 100, 1
            ) if total else 0.0,
            "posted_bridges": posted,
        }


# ============================================================================
# Benford's Law Analysis
# ============================================================================

# Expected first-digit frequencies per Benford's Law
BENFORD_EXPECTED: Dict[int, float] = {
    d: math.log10(1 + 1 / d) for d in range(1, 10)
}


def _extract_first_digit(value: Any) -> Optional[int]:
    """Extract the leading non-zero digit from a numeric value.

    Args:
        value: Any value; will be coerced to float.

    Returns:
        The first significant digit (1-9), or None if not extractable.
    """
    if value is None:
        return None
    try:
        num = abs(float(value))
        if num == 0 or not math.isfinite(num):
            return None
        s = f"{num:.10e}"  # scientific notation: "1.2345e+02"
        return int(s[0])
    except (ValueError, TypeError, IndexError):
        return None


class BenfordAnalysis:
    """Benford's Law first-digit analysis for fraud detection.

    Benford's Law states that in naturally occurring numeric datasets,
    the leading digit ``d`` appears with frequency ``log10(1 + 1/d)``.
    Digit 1 appears ~30.1% of the time, digit 9 only ~4.6%.

    Deviations from this distribution can indicate:
    - Fabricated or rounded data (inspectors inventing numbers)
    - Systematic data entry errors
    - Billing fraud (inflated quantities or costs)
    - Copy-paste duplication in reporting

    This class analyzes any collection of numeric values and flags
    statistically significant deviations using a chi-squared test.

    Args:
        values: Iterable of numeric values to analyze.
        label: Human-readable label for this dataset.

    Example::

        # Check bridge deck areas for anomalies
        deck_areas = [b.get("DECK_AREA") for b in bridge_list]
        ba = BenfordAnalysis(deck_areas, label="Deck Areas")
        print(ba)
        print(f"Chi-squared: {ba.chi_squared:.2f}")
        print(f"Suspicious:  {ba.is_suspicious}")

    References:
        - Nigrini, M.J. (2012). *Benford's Law*. Wiley.
        - AASHTO (2020). *Bridge Data Quality Best Practices*.
    """

    # Chi-squared critical values at alpha=0.05 with df=8
    _CHI2_CRITICAL_005 = 15.507
    # More lenient threshold at alpha=0.01
    _CHI2_CRITICAL_001 = 20.090

    def __init__(self, values, label: str = ""):
        self.label = label
        self._digits: List[int] = []
        self._observed: Dict[int, int] = {d: 0 for d in range(1, 10)}
        self._n = 0

        for v in values:
            d = _extract_first_digit(v)
            if d is not None and 1 <= d <= 9:
                self._digits.append(d)
                self._observed[d] += 1
                self._n += 1

    @property
    def n(self) -> int:
        """Number of valid observations."""
        return self._n

    @property
    def observed_counts(self) -> Dict[int, int]:
        """Raw count of each leading digit."""
        return dict(self._observed)

    @property
    def observed_freq(self) -> Dict[int, float]:
        """Observed frequency (proportion) of each leading digit."""
        if self._n == 0:
            return {d: 0.0 for d in range(1, 10)}
        return {d: c / self._n for d, c in self._observed.items()}

    @property
    def expected_freq(self) -> Dict[int, float]:
        """Benford's expected frequency for each leading digit."""
        return dict(BENFORD_EXPECTED)

    @property
    def expected_counts(self) -> Dict[int, float]:
        """Benford's expected counts given the sample size."""
        return {d: BENFORD_EXPECTED[d] * self._n for d in range(1, 10)}

    @property
    def deviations(self) -> Dict[int, float]:
        """Deviation (observed - expected) as percentage points for each digit."""
        obs = self.observed_freq
        return {
            d: round((obs[d] - BENFORD_EXPECTED[d]) * 100, 2)
            for d in range(1, 10)
        }

    @property
    def chi_squared(self) -> float:
        """Pearson chi-squared statistic against Benford's distribution.

        Higher values indicate greater deviation from expected. With
        df=8, values above 15.507 are significant at alpha=0.05.
        """
        if self._n == 0:
            return 0.0
        chi2 = 0.0
        for d in range(1, 10):
            expected = BENFORD_EXPECTED[d] * self._n
            observed = self._observed[d]
            if expected > 0:
                chi2 += (observed - expected) ** 2 / expected
        return chi2

    @property
    def is_suspicious(self) -> bool:
        """Whether the distribution deviates significantly (alpha=0.05).

        Returns True if chi-squared exceeds the critical value for
        8 degrees of freedom at the 5% significance level.
        Requires at least 50 observations for a meaningful test.
        """
        if self._n < 50:
            return False
        return self.chi_squared > self._CHI2_CRITICAL_005

    @property
    def is_highly_suspicious(self) -> bool:
        """Whether the deviation is significant at alpha=0.01."""
        if self._n < 50:
            return False
        return self.chi_squared > self._CHI2_CRITICAL_001

    @property
    def anomalous_digits(self) -> List[Dict[str, Any]]:
        """Digits with the largest deviations from Benford's expectation.

        Returns digits where the absolute deviation exceeds 2 percentage
        points, sorted by deviation magnitude.
        """
        results = []
        obs = self.observed_freq
        for d in range(1, 10):
            dev = (obs[d] - BENFORD_EXPECTED[d]) * 100
            if abs(dev) > 2.0:
                results.append({
                    "digit": d,
                    "observed_pct": round(obs[d] * 100, 2),
                    "expected_pct": round(BENFORD_EXPECTED[d] * 100, 2),
                    "deviation_pct": round(dev, 2),
                    "direction": "OVER" if dev > 0 else "UNDER",
                })
        results.sort(key=lambda x: abs(x["deviation_pct"]), reverse=True)
        return results

    def summary(self) -> Dict[str, Any]:
        """Full analysis summary dict.

        Returns:
            Dict with all analysis results suitable for reporting.
        """
        return {
            "label": self.label,
            "n": self._n,
            "chi_squared": round(self.chi_squared, 3),
            "critical_value_005": self._CHI2_CRITICAL_005,
            "is_suspicious": self.is_suspicious,
            "is_highly_suspicious": self.is_highly_suspicious,
            "observed_freq": {
                d: round(f * 100, 2) for d, f in self.observed_freq.items()
            },
            "expected_freq": {
                d: round(f * 100, 2) for d, f in BENFORD_EXPECTED.items()
            },
            "deviations": self.deviations,
            "anomalous_digits": self.anomalous_digits,
        }

    def comparison_table(self) -> str:
        """Format a human-readable comparison table.

        Returns:
            Multi-line string showing observed vs expected frequencies.
        """
        obs = self.observed_freq
        lines = [
            f"Benford's Analysis: {self.label}" if self.label else "Benford's Analysis",
            f"N = {self._n:,} observations",
            "",
            "Digit | Observed |  Expected | Deviation |  Count",
            "------|----------|-----------|-----------|-------",
        ]
        for d in range(1, 10):
            o_pct = obs[d] * 100
            e_pct = BENFORD_EXPECTED[d] * 100
            dev = o_pct - e_pct
            flag = " ***" if abs(dev) > 3.0 else " * " if abs(dev) > 2.0 else "   "
            lines.append(
                f"  {d}   | {o_pct:6.2f}% | {e_pct:7.2f}% | "
                f"{dev:+7.2f}pp |{self._observed[d]:6d}{flag}"
            )
        lines.append("")
        lines.append(f"Chi-squared: {self.chi_squared:.3f} "
                      f"(critical at 5%: {self._CHI2_CRITICAL_005})")
        if self.is_highly_suspicious:
            lines.append(">>> HIGHLY SUSPICIOUS - Significant at 1% level <<<")
        elif self.is_suspicious:
            lines.append(">>> SUSPICIOUS - Significant at 5% level <<<")
        else:
            lines.append("Distribution consistent with Benford's Law.")
        return "\n".join(lines)

    def __repr__(self) -> str:
        label = f"'{self.label}'" if self.label else ""
        flag = " SUSPICIOUS" if self.is_suspicious else ""
        return (
            f"BenfordAnalysis({label}, n={self._n}, "
            f"chi2={self.chi_squared:.2f}{flag})"
        )


class BenfordBridgeAuditor:
    """Apply Benford's Law across multiple bridge data fields.

    Runs Benford's analysis on common numeric fields from bridge
    inventory data (TIMS, BrR, AssetWise, or SNBI) and flags datasets
    that deviate significantly from the expected distribution.

    This is especially useful for detecting:
    - **Fabricated inspection data**: Inspectors inventing condition
      ratings or quantities rather than measuring them.
    - **Billing fraud**: Inflated quantities in construction pay items
      (deck area, concrete volume, steel weight).
    - **Duplicate records**: Copy-paste errors that create unnatural
      digit distributions.
    - **Rounded data**: Excessive preference for digits 1 or 5 suggests
      estimation rather than measurement.

    Args:
        records: List of bridge data dicts (any source).

    Example::

        bridges = TIMSBridge.search_by_district("06")
        auditor = BenfordBridgeAuditor(bridges)
        report = auditor.run_audit()
        for field_name, analysis in report.items():
            if analysis.is_suspicious:
                print(f"FLAG: {field_name}")
                print(analysis.comparison_table())
    """

    # Fields commonly worth auditing, grouped by data source.
    # Format: (field_key, human_label)
    TIMS_AUDIT_FIELDS: List[Tuple[str, str]] = [
        ("DECK_AREA", "Deck Area (sq ft)"),
        ("OVRL_STR_LEN", "Overall Length (ft)"),
        ("MAX_SPAN_LEN", "Max Span Length (ft)"),
        ("DECK_WD", "Deck Width (ft)"),
        ("BRG_RDW_WD", "Roadway Width (ft)"),
        ("APPRH_RDW_WD", "Approach Roadway Width (ft)"),
        ("INVENT_RTE_ADT", "Average Daily Traffic"),
        ("FUTURE_ADT", "Future ADT"),
        ("DRN_AREA", "Drainage Area (sq mi)"),
        ("SUFF_RATING", "Sufficiency Rating"),
        ("RAT_INV_LOAD_FACT", "Inventory Rating Factor"),
        ("RAT_OPR_LOAD_FACT", "Operating Rating Factor"),
        ("SKEW_DEG", "Skew Angle (deg)"),
        ("WEARING_SURF_THCK", "Wearing Surface Thickness"),
        ("PAINT_SURFACE_AREA", "Paint Surface Area"),
    ]

    SNBI_AUDIT_FIELDS: List[Tuple[str, str]] = [
        ("BG01", "NBIS Bridge Length"),
        ("BG02", "Total Bridge Length"),
        ("BG03", "Max Span Length"),
        ("BG05", "Width Out-to-Out"),
        ("BG06", "Width Curb-to-Curb"),
        ("BG09", "Approach Roadway Width"),
        ("BG15", "Irregular Deck Area"),
        ("BG16", "Calculated Deck Area"),
        ("BLR05", "Inventory Rating Factor"),
        ("BLR06", "Operating Rating Factor"),
        ("BLR07", "Legal Load Rating Factor"),
        ("BH09", "AADT"),
        ("BH10", "AADT Truck"),
        ("BH17", "Bypass Detour Length"),
    ]

    # Construction pay item fields (if available from project data)
    CONSTRUCTION_AUDIT_FIELDS: List[Tuple[str, str]] = [
        ("unit_price", "Unit Price ($)"),
        ("quantity", "Quantity"),
        ("total_cost", "Total Cost ($)"),
        ("change_order_amount", "Change Order Amount ($)"),
        ("bid_amount", "Bid Amount ($)"),
        ("estimate_amount", "Engineer's Estimate ($)"),
    ]

    def __init__(self, records: List[Dict[str, Any]]):
        self._records = records

    def analyze_field(self, field_key: str, label: str = "") -> BenfordAnalysis:
        """Run Benford's analysis on a single field across all records.

        Args:
            field_key: Dict key to extract from each record.
            label: Human-readable label for the field.

        Returns:
            BenfordAnalysis object with results.
        """
        values = [r.get(field_key) for r in self._records]
        return BenfordAnalysis(values, label=label or field_key)

    def run_audit(
        self,
        fields: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, BenfordAnalysis]:
        """Run Benford's analysis across multiple fields.

        Args:
            fields: List of (field_key, label) tuples. If None,
                auto-detects whether the data is TIMS or SNBI format
                and uses the appropriate field list.

        Returns:
            Dict mapping field label -> BenfordAnalysis.
        """
        if fields is None:
            fields = self._auto_detect_fields()

        results = {}
        for field_key, label in fields:
            analysis = self.analyze_field(field_key, label)
            if analysis.n >= 10:  # only include fields with data
                results[label] = analysis
        return results

    def _auto_detect_fields(self) -> List[Tuple[str, str]]:
        """Detect whether records are TIMS or SNBI format."""
        if not self._records:
            return self.TIMS_AUDIT_FIELDS
        sample = self._records[0]
        if "SFN" in sample or "DECK_AREA" in sample:
            return self.TIMS_AUDIT_FIELDS
        elif "BID01" in sample or "BG01" in sample:
            return self.SNBI_AUDIT_FIELDS
        else:
            # Try construction fields
            if any(k in sample for k in ("unit_price", "quantity", "total_cost")):
                return self.CONSTRUCTION_AUDIT_FIELDS
            return self.TIMS_AUDIT_FIELDS

    def suspicious_fields(
        self,
        fields: Optional[List[Tuple[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Return only fields that fail the Benford's test.

        Args:
            fields: Field list (auto-detected if None).

        Returns:
            List of dicts with field name, chi-squared, and
            anomalous digits for each suspicious field.
        """
        audit = self.run_audit(fields)
        flagged = []
        for label, analysis in audit.items():
            if analysis.is_suspicious:
                flagged.append({
                    "field": label,
                    "n": analysis.n,
                    "chi_squared": round(analysis.chi_squared, 3),
                    "anomalous_digits": analysis.anomalous_digits,
                })
        flagged.sort(key=lambda x: x["chi_squared"], reverse=True)
        return flagged

    def full_report(
        self,
        fields: Optional[List[Tuple[str, str]]] = None,
    ) -> str:
        """Generate a complete text audit report.

        Args:
            fields: Field list (auto-detected if None).

        Returns:
            Multi-line string report.
        """
        audit = self.run_audit(fields)
        lines = [
            "=" * 70,
            "BENFORD'S LAW AUDIT REPORT",
            f"Records analyzed: {len(self._records):,}",
            f"Fields tested:    {len(audit)}",
            "=" * 70,
        ]

        suspicious_count = 0
        for label, analysis in audit.items():
            lines.append("")
            lines.append(analysis.comparison_table())
            if analysis.is_suspicious:
                suspicious_count += 1

        lines.append("")
        lines.append("=" * 70)
        lines.append(f"SUMMARY: {suspicious_count} of {len(audit)} fields "
                      f"flagged as suspicious")
        if suspicious_count == 0:
            lines.append("No anomalies detected.")
        else:
            lines.append(
                "Flagged fields warrant further investigation. Common causes:"
            )
            lines.append("  - Fabricated or estimated data (not measured)")
            lines.append("  - Systematic rounding (preference for 5s or 0s)")
            lines.append("  - Copy-paste duplication")
            lines.append("  - Billing inflation (construction pay items)")
            lines.append("  - Data entry errors at scale")
        lines.append("=" * 70)

        return "\n".join(lines)
