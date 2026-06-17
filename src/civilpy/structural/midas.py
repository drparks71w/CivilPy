"""
CivilPy
Copyright (C) 2019-2026 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import json
import time
import warnings
import requests
from collections import Counter
from pathlib import Path
from civilpy.general import units

analysis_results_request = {
    "Argument": {
        "TABLE_NAME": "BeamForce",
        "TABLE_TYPE": "BEAMFORCE",
        "EXPORT_PATH": Path(os.getcwd()) / "output.json",
        "UNIT": {"FORCE": "KIPS", "DIST": "FT"},
        "STYLES": {"FORMAT": "Default", "PLACE": 12},
        "COMPONENTS": [
            "Elem",
            "Load",
            "Part",
            "Axial",
            "Shear-y",
            "Shear-z",
            "Torsion",
            "Moment-y",
            "Moment-z",
        ],
        "NODE_ELEMS": {"KEYS": ["310to536"]},
        "LOAD_CASE_NAMES": ["DL(CB)", "Moving Load Case(MV:all)"],
        "PARTS": ["Part I", "Part 1/4", "Part 2/4", "Part 3/4", "Part J"],
    }
}

MIDAS_API_KEY = ""


def get_api_key(secrets_path=None):
    """
    Retrieve the API key from the secrets.json file in the civilpy directory

    Parameters
    -------
    secrets_path : the path where the secrets.json file is located

    Returns
    -------
    None - Sets a global variable for the module
    """
    global MIDAS_API_KEY

    if secrets_path is None:
        try:
            secrets_path = Path.home() / "secrets.json"
            with open(secrets_path, "r") as f:
                data = json.load(f)
                MIDAS_API_KEY = data["MIDAS_API_KEY"]

        except FileNotFoundError as e:
            print(
                f"Could not call the MIDAS API, ensure it's running and your key is correctly"
            )
            print(
                f"Stored in your secrets.json file located at the following location: {secrets_path}"
            )
            print(f"{e}")
    else:
        try:
            with open(secrets_path, "r") as f:
                data = json.load(f)
                MIDAS_API_KEY = data["MIDAS_API_KEY"]

        except FileNotFoundError as e:
            print(
                f"Could not call the MIDAS API, ensure it's running and your key is correctly"
            )
            print(
                f"Stored in your secrets.json file located at the following location: {secrets_path}"
            )
            print(f"{e}")


# function for MIDAS Open API
def midas_api(method, command, body=None):
    """
    Make a request to the MIDAS API and return the
    response as a JSON object

    Parameters
    ----------
    method: str - 'GET', 'PUT', 'POST' or 'DELETE'
    command: str - The particular method within the API you want
        to target, such as 'db/elem' for the elements you want to access
    body: dict - The body of the request you want to send to the api, usually contains
        the values you want MIDAS to update with

    Returns
    -------
    response.json - the response from the MIDAS API
    """
    if MIDAS_API_KEY:
        pass
    else:
        get_api_key()
    base_url = "https://moa-engineers.midasit.com:443/civil/"
    mapi_key = MIDAS_API_KEY

    url = base_url + command
    headers = {"Content-Type": "application/json", "MAPI-Key": mapi_key}

    try:
        if method.upper() == "POST":
            response = requests.post(url=url, headers=headers, json=body)
        elif method.upper() == "PUT":
            response = requests.put(url=url, headers=headers, json=body)
        elif method.upper() == "GET":
            response = requests.get(url=url, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url=url, headers=headers)
        else:
            response = ""
            print("Invalid method, please use one of GET, POST, PUT, or DELETE")

        return response.json()
    except NameError as not_defined:  # pragma: no cover
        print(
            """'
        Could not call the MIDAS API, ensure it\'s running and your key is correctly
        Stored in your secrets.json file located at the following location:
        """
        )
        print(f"{not_defined}")


def convert_node_units(
    from_units: str = None, to_units: str = None, in_place: bool = True
) -> None:
    """
    Converts the existing nodes from one unit system to another, for instance if you import
    a dxf file that was drawn in feet, but your midas units were set to inches,
    Parameters
    ----------
    from_units: str = The units the drawing is currently in ie 'inches' will grab them from midas if None
    to_units: str = The desired units to convert the drawing to, if None, will not run
    in_place: bool = Whether you want the function to push the data to the midas, or just return the updated values

    Returns
    -------
    None - Converts the units in the open model to the desired units
    nodes - if in_place is False
    """
    # Get the current list of nodes in midas
    nodes = midas_api("GET", "db/node")

    if to_units is None:
        print('Please specify units to convert to ("feet"/"inches")')
        return None
    if from_units is None:
        units_api_response = midas_api("GET", "db/unit")
        from_units = units_api_response["UNIT"]["1"]["DIST"].lower()

    # Go through every node and scale into the target units. One from_unit
    # equals `conversion_factor` to_units, so values multiply by the factor
    # (e.g. inch -> feet: factor = 1/12, 12 in becomes 1 ft).
    conversion_factor = (1 * units[from_units]).to(units[to_units]).magnitude
    for index_value in nodes["NODE"]:
        print(index_value, end=": ")
        for xyz_value in nodes["NODE"][index_value]:
            print(f"{xyz_value}: {nodes['NODE'][index_value][xyz_value]}", end=", ")
            nodes["NODE"][index_value][xyz_value] *= conversion_factor
            print(
                f"Updated to {xyz_value}: {nodes['NODE'][index_value][xyz_value]}",
                end=", ",
            )
        print()

    # MidasAPI expects the first key in the values to be 'Assign'
    nodes["Assign"] = nodes.pop("NODE")

    if in_place:
        # Send the updated values back to midas
        midas_api("PUT", "db/node", nodes)
    else:
        return nodes


def get_elements():
    """Retrieve all elements from the active MIDAS Civil model.

    Returns:
        dict: MIDAS API response containing element definitions keyed by
        element ID under ``"ELEM"``.
    """
    elements = midas_api("GET", "db/elem")
    return elements


def get_nodes():
    """Retrieve all nodes from the active MIDAS Civil model.

    Returns:
        dict: MIDAS API response containing node coordinates keyed by node ID
        under ``"NODE"``.
    """
    nodes = midas_api("GET", "db/node")
    return nodes


def get_materials():
    """Retrieve all material definitions from the active MIDAS Civil model.

    Returns:
        dict: MIDAS API response containing material properties keyed by
        material ID under ``"MATL"``.
    """
    materials = midas_api("GET", "db/matl")
    return materials


def get_sections():
    """Retrieve all section definitions from the active MIDAS Civil model.

    Returns:
        dict: MIDAS API response containing section properties keyed by
        section ID under ``"SECT"``.
    """
    sections = midas_api("GET", "db/sect")
    return sections


def get_static_loads():
    """Retrieve all static load case definitions from the active MIDAS Civil model.

    Returns:
        dict: MIDAS API response containing static load cases keyed by load
        case ID under ``"STLD"``.
    """
    static_loads = midas_api("GET", "db/stld")
    return static_loads


def get_units():
    """Retrieve the current unit system settings from the active MIDAS Civil model.

    Returns:
        dict: MIDAS API response containing force, length, heat, and
        temperature unit settings.
    """
    current_units = midas_api("GET", "db/unit")
    return current_units


def get_supports():
    """Retrieve all support (constraint) definitions from the active MIDAS Civil model.

    Returns:
        dict: MIDAS API response containing nodal boundary conditions keyed by
        node ID under ``"CONS"``.
    """
    support_definitions = midas_api("GET", "db/cons")
    return support_definitions


def get_elements_by_section_index(section_index: int = None):
    """
    Returns a dictionary containing all elements of the midas model that match the section index

    Parameters
    ----------
    section_index: int = The index value of the section you want to search the elements for

    Returns
    -------
    return_dict: A dictionary containing all elements of the midas model that match the section
        specified
    """
    return_dict = {"ELEM": {}}
    elements = get_elements()

    if section_index is not None:
        for key in elements["ELEM"]:
            if elements["ELEM"][key]["SECT"] == section_index:
                return_dict["ELEM"][key] = elements["ELEM"][key]
    else:
        print("You must specify a section by it's index")

    return return_dict


def get_elements_by_material_index(material_index: int = None):
    """
    Get the elements of a model by specifying a material index value
    Parameters
    ----------
    material_index: int = Index of the material you want to sort by in str format

    Returns
    -------
    return_dict: dict = The elements of a model that match the material specified
    """
    return_dict = {"ELEM": {}}
    elements = get_elements()

    if material_index is not None:
        for keys in elements["ELEM"]:
            if elements["ELEM"][keys]["MATL"] == material_index:
                return_dict["ELEM"][keys] = elements["ELEM"][keys]
    else:
        print("You must specify a material by it's index")

    return return_dict


def setup_output_directory(output_directory: str = os.getcwd()):
    """Create an ``output`` subdirectory inside *output_directory* if absent.

    Args:
        output_directory (str): Parent directory path. Defaults to the current
            working directory.

    Note:
        Prints a status message indicating whether the directory was found or
        created.
    """
    if os.path.isdir(Path(output_directory) / "output"):
        print("Output directory already exists")
    else:
        print(
            f"Directory doesn't exist, creating at {Path(output_directory) / 'output'}"
        )
        os.makedirs(Path(output_directory) / "output")


# ─────────────────────────────────────────────────────────────────────────────
# MidasCivil — object-oriented client covering the full MIDAS API surface
# ─────────────────────────────────────────────────────────────────────────────


class MidasApiError(RuntimeError):
    """Raised when the MIDAS API returns an HTTP or application error."""

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


class MidasConnectionError(MidasApiError):
    """The MIDAS API could not be reached — Civil NX is closed, the session
    dropped, or the network blipped. Transport-level and typically transient,
    so :meth:`MidasCivil.request` retries it before giving up. Subclasses
    :class:`MidasApiError` so existing ``except MidasApiError`` paths still
    catch it."""


class MidasTimeoutError(MidasConnectionError):
    """A request outran its read timeout — usually a large finite-element
    solve or model open that needs a longer ``analysis_timeout`` rather than a
    retry (re-issuing it just doubles the wait)."""


class MidasLicenseError(MidasApiError):
    """The connected Civil NX license tier rejected the operation — e.g.
    opening a model with more construction stages than a Plus license allows.
    Not retryable: skip the model rather than re-sending."""


class MidasCivil:
    """
    A connection to a running MIDAS Civil NX (or Gen NX) instance through
    the MIDAS API — the same API the MIDAS GH Rhino/Grasshopper extension
    uses, so anything sent from here lands in the connected session.

    Three lines::

        from civilpy.structural.midas import MidasCivil

        midas = MidasCivil()              # key from ~/secrets.json MIDAS_API_KEY
        nodes = midas.nodes()             # GET  /db/NODE
        midas.put_nodes({"1": {"X": 0, "Y": 0, "Z": 0}})   # PUT /db/NODE

    Coverage:

    * **Model database** — typed helpers for the common tables (nodes,
      elements, materials, sections, supports, static loads, units, groups,
      load combinations) plus generic :meth:`get_db` / :meth:`put_db` /
      :meth:`post_db` / :meth:`delete_db` that reach *every* ``/db/*`` table
      in the MIDAS API manual.
    * **Document operations** — :meth:`new`, :meth:`open`, :meth:`save`,
      :meth:`save_as`, :meth:`analyze`, :meth:`import_file`, :meth:`export_file`.
    * **Results** — :meth:`result_table` wrapping ``POST /post/TABLE``.

    Unlike the module-level functions above (kept for backwards
    compatibility), this class holds no global state, supports custom base
    URLs (regional/local API servers), applies request timeouts, and raises
    :class:`MidasApiError` instead of printing.
    """

    DEFAULT_BASE_URL = "https://moa-engineers.midasit.com:443/civil"

    #: Read timeout (s) for long operations — analysis, open, result tables —
    #: on large finite-element models (a 10k-element solve exceeds the default).
    #: Override per instance with ``analysis_timeout=`` for very large models.
    ANALYSIS_TIMEOUT = 600

    #: Default retry policy for transport (connection) failures. A dropped
    #: Civil NX session is the failure that clusters mid-batch, so one or two
    #: backoff retries recover most blips without masking a real outage.
    RECONNECT_RETRIES = 2
    RETRY_BACKOFF = 0.5

    def __init__(self, base_url=None, mapi_key=None, timeout=60,
                 secrets_path=None, analysis_timeout=None,
                 reconnect_retries=None, retry_backoff=None):
        if mapi_key is None or base_url is None:
            secrets = {}
            path = Path(secrets_path) if secrets_path else Path.home() / "secrets.json"
            try:
                with open(path, "r") as f:
                    secrets = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            mapi_key = mapi_key or secrets.get("MIDAS_API_KEY", "")
            base_url = base_url or secrets.get("MIDAS_BASE_URL", "")
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.mapi_key = mapi_key
        self.timeout = timeout
        if analysis_timeout is not None:
            self.ANALYSIS_TIMEOUT = analysis_timeout
        self.reconnect_retries = (self.RECONNECT_RETRIES
                                  if reconnect_retries is None else reconnect_retries)
        self.retry_backoff = (self.RETRY_BACKOFF
                              if retry_backoff is None else retry_backoff)
        if not self.mapi_key:
            raise MidasApiError(
                "MIDAS API key missing — copy it from Civil NX "
                "(Apps > API > Midas Settings) into ~/secrets.json as "
                '"MIDAS_API_KEY", or pass mapi_key=.'
            )

    # ── Transport ─────────────────────────────────────────────────────────────

    def request(self, method, command, body=None, timeout=None, retries=None):
        """
        Send one request to the MIDAS API and return the parsed JSON.

        ``command`` is the endpoint path, e.g. ``"/db/NODE"`` or
        ``"/doc/ANAL"``. ``timeout`` overrides the instance default for one
        call (used by :meth:`analyze`, :meth:`open`, and :meth:`result_table`
        on large models). ``retries`` overrides :attr:`reconnect_retries` for
        one call (0 disables the backoff retry).

        Error handling distinguishes three failure modes so a batch caller can
        react sensibly:

        * :class:`MidasConnectionError` — the API was unreachable (dropped
          session); retried with backoff first, then raised.
        * :class:`MidasTimeoutError` — the request outran its read timeout
          (a large solve); raised immediately, not retried.
        * :class:`MidasLicenseError` — the license tier rejected the model
          (HTTP 400, e.g. too many construction stages).

        All three subclass :class:`MidasApiError`, as does a generic HTTP or
        ``{"error": ...}`` payload failure.
        """
        url = f"{self.base_url}/{command.lstrip('/')}"
        headers = {"Content-Type": "application/json", "MAPI-Key": self.mapi_key}
        attempts = self.reconnect_retries if retries is None else retries
        response = None
        for attempt in range(attempts + 1):
            try:
                response = requests.request(
                    method.upper(), url, headers=headers,
                    json=body, timeout=timeout or self.timeout)
                break
            except requests.Timeout as exc:
                # The model is likely still solving — retrying just doubles the
                # wait, so surface it as its own error to raise analysis_timeout.
                raise MidasTimeoutError(
                    f"MIDAS {method.upper()} {command} timed out after "
                    f"{timeout or self.timeout}s — the model may still be "
                    f"solving. Raise analysis_timeout for large models."
                ) from exc
            except requests.RequestException as exc:
                # Transport failure (Civil NX closed, session dropped). This is
                # the error that cascades through a batch — retry with backoff.
                if attempt < attempts:
                    time.sleep(self.retry_backoff * (2 ** attempt))
                    continue
                raise MidasConnectionError(
                    f"Could not reach the MIDAS API at {self.base_url} — is "
                    f"Civil NX open and connected? ({exc})"
                ) from exc
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}
        if not response.ok:
            self._raise_http_error(method, command, response, data)
        if isinstance(data, dict) and "error" in data:
            raise MidasApiError(
                f"{method.upper()} {command} rejected: {data['error']}",
                response=data,
            )
        return data

    @staticmethod
    def _raise_http_error(method, command, response, data):
        """Classify a non-2xx MIDAS response and raise the matching error."""
        detail = data or (response.text[:300] if response.text else "")
        haystack = (json.dumps(data) if isinstance(data, dict) else str(data))
        haystack = f"{haystack} {response.text or ''}".lower()
        if response.status_code == 400 and (
            "construction stage" in haystack or "license" in haystack
        ):
            raise MidasLicenseError(
                f"{method.upper()} {command} rejected by the MIDAS license "
                f"tier (HTTP 400): {detail}. A model above the licensed limit "
                f"(e.g. >10 construction stages on a Plus license) cannot be "
                f"opened on this connection.",
                response=data,
            )
        raise MidasApiError(
            f"{method.upper()} {command} returned HTTP "
            f"{response.status_code}: {detail}",
            response=data,
        )

    def ping(self):
        """True when Civil NX is reachable and the key is accepted."""
        try:
            self.request("GET", "/db/UNIT")
            return True
        except MidasApiError:
            return False

    # ── Generic model database access (any /db/* table) ──────────────────────

    def get_db(self, table):
        """``GET /db/{table}`` — full contents of any model database table."""
        return self.request("GET", f"/db/{table.upper()}")

    def put_db(self, table, assign):
        """``PUT /db/{table}`` — create/update rows. ``assign`` maps id → fields."""
        return self.request("PUT", f"/db/{table.upper()}", {"Assign": assign})

    def post_db(self, table, assign):
        """``POST /db/{table}`` — create rows (errors when an id exists)."""
        return self.request("POST", f"/db/{table.upper()}", {"Assign": assign})

    def delete_db(self, table, ids=None):
        """``DELETE /db/{table}`` — remove ids (everything when ids is None)."""
        command = f"/db/{table.upper()}"
        if ids is not None:
            id_list = ",".join(str(i) for i in ids)
            command += f"/{id_list}"
        return self.request("DELETE", command)

    # ── Typed table helpers ───────────────────────────────────────────────────

    def nodes(self):
        """All nodes — ``{"NODE": {id: {X, Y, Z}}}``."""
        return self.get_db("NODE")

    def put_nodes(self, assign):
        """Create/update nodes: ``{id: {"X":, "Y":, "Z":}}``."""
        return self.put_db("NODE", assign)

    def elements(self):
        """All elements — ``{"ELEM": {id: {TYPE, MATL, SECT, NODE, ...}}}``."""
        return self.get_db("ELEM")

    def put_elements(self, assign):
        """Create/update elements: ``{id: {"TYPE": "BEAM", "MATL":, "SECT":, "NODE": [i, j]}}``."""
        return self.put_db("ELEM", assign)

    def materials(self):
        return self.get_db("MATL")

    def put_materials(self, assign):
        """Create/update materials: ``{id: {"TYPE": "STEEL"|"CONC"|"USER", "NAME":, ...}}``."""
        return self.put_db("MATL", assign)

    def sections(self):
        return self.get_db("SECT")

    def put_sections(self, assign):
        return self.put_db("SECT", assign)

    def supports(self):
        """Nodal boundary conditions — ``{"CONS": {...}}``."""
        return self.get_db("CONS")

    def put_supports(self, assign):
        """Create/update supports: ``{node_id: {"ITEMS": [{"ID": 1, "CONSTRAINT": "1110000"}]}}``."""
        return self.put_db("CONS", assign)

    def static_loads(self):
        """Static load cases — ``{"STLD": {...}}``."""
        return self.get_db("STLD")

    def put_static_loads(self, assign):
        return self.put_db("STLD", assign)

    def groups(self):
        """Structure groups — ``{"GRUP": {...}}``."""
        return self.get_db("GRUP")

    def load_combinations(self):
        """General load combinations — ``{"LCOM-GEN": {...}}``."""
        return self.get_db("LCOM-GEN")

    def units(self):
        return self.get_db("UNIT")

    def set_units(self, force="KIPS", dist="FT", heat="BTU", temper="F"):
        """Set the model unit system (defaults: kips / feet)."""
        return self.put_db("UNIT", {"1": {
            "FORCE": force, "DIST": dist, "HEAT": heat, "TEMPER": temper,
        }})

    # ── Model triage ──────────────────────────────────────────────────────────

    #: Tables read to judge whether a model can be analyzed / rated.
    TRIAGE_TABLES = ("NODE", "ELEM", "CONS", "STLD", "MVLD", "LCOM-GEN", "SECT")

    def _grab(self, table):
        """``get_db(table)`` reduced to its inner ``{id: row}`` map, or ``{}``
        when the table is empty or absent. MIDAS answers an empty/missing table
        with ``{"TABLE": {"message": ...}}``, which collapses to ``{}`` here."""
        try:
            resp = self.get_db(table)
        except MidasApiError:
            return {}
        inner = resp.get(table, resp) if isinstance(resp, dict) else {}
        if not isinstance(inner, dict) or list(inner) == ["message"]:
            return {}
        return inner

    def summarize(self):
        """Counts of the current model's structural ingredients.

        One round-trip per :attr:`TRIAGE_TABLES` entry; returns a dict with
        ``nodes``, ``elems``, ``elem_types``, ``sect_types``, ``supports``,
        ``static_loads``, ``moving_loads`` and ``combinations``. Feed it to
        :meth:`capability` to decide whether a model is worth analyzing before
        spending a long solve on it.
        """
        elem = self._grab("ELEM")
        sect = self._grab("SECT")
        return {
            "nodes": len(self._grab("NODE")),
            "elems": len(elem),
            "elem_types": dict(Counter(e.get("TYPE", "?") for e in elem.values())),
            "sect_types": dict(Counter(s.get("SECTTYPE", "?") for s in sect.values())),
            "supports": len(self._grab("CONS")),
            "static_loads": len(self._grab("STLD")),
            "moving_loads": len(self._grab("MVLD")),
            "combinations": len(self._grab("LCOM-GEN")),
        }

    def capability(self, summary=None):
        """``(can_analyze, can_rate_live_load, note)`` for the current model.

        A model needs geometry, supports, and at least one load case to solve;
        live-load rating additionally needs a moving-load case. Pass a cached
        :meth:`summarize` result as ``summary`` to avoid a second round-trip.
        """
        s = summary or self.summarize()
        if s["nodes"] == 0 or s["elems"] == 0:
            return (False, False, "empty model")
        if s["supports"] == 0:
            return (False, False, "no supports — won't solve")
        if s["static_loads"] == 0 and s["moving_loads"] == 0:
            return (False, False, "no load cases")
        if s["moving_loads"] == 0:
            return (True, False,
                    "no moving load — DL/analysis only; LL rating needs a companion model")
        if s["static_loads"] == 0:
            return (True, False, "no static load — LL/DF study only")
        return (True, True, "rateable: supports + static + moving load present")

    def can_analyze(self):
        """True when the current model has enough defined to run an analysis."""
        return self.capability()[0]

    # ── Document operations ───────────────────────────────────────────────────

    def new(self):
        """``POST /doc/NEW`` — start a blank model (discards unsaved work)."""
        return self.request("POST", "/doc/NEW", {})

    def open(self, path):
        """``POST /doc/OPEN`` — open an .mcb model file on the Civil NX machine
        (long timeout; large files take time to load)."""
        return self.request("POST", "/doc/OPEN", {"Argument": str(path)},
                            timeout=self.ANALYSIS_TIMEOUT)

    def save(self):
        """``POST /doc/SAVE`` — save the current model."""
        return self.request("POST", "/doc/SAVE", {})

    def save_as(self, path):
        """``POST /doc/SAVEAS`` — save the model to a new path."""
        return self.request("POST", "/doc/SAVEAS", {"Argument": str(path)})

    def analyze(self):
        """``POST /doc/ANAL`` — run the analysis on the current model (long
        timeout; a large finite-element solve exceeds the default request
        timeout)."""
        return self.request("POST", "/doc/ANAL", {}, timeout=self.ANALYSIS_TIMEOUT)

    def import_file(self, path):
        """``POST /doc/IMPORT`` — import a file (e.g. .mct) into the model."""
        return self.request("POST", "/doc/IMPORT", {"Argument": str(path)})

    def export_file(self, path):
        """``POST /doc/EXPORT`` — export the model to a file path."""
        return self.request("POST", "/doc/EXPORT", {"Argument": str(path)})

    # ── Results extraction ────────────────────────────────────────────────────

    def result_table(self, table_name, table_type=None, components=None,
                     node_elems=None, load_case_names=None, parts=None,
                     unit=None, styles=None, timeout=None):
        """
        ``POST /post/TABLE`` — extract an analysis results table.

        Example::

            midas.result_table(
                "BeamForce", table_type="BEAMFORCE",
                components=["Elem", "Load", "Moment-y"],
                node_elems={"KEYS": ["1to20"]},
                load_case_names=["DL(CB)"],
            )

        For element-force tables, prefer :meth:`beam_forces`, which sends the
        request shape confirmed to work against live Civil NX. ``timeout``
        overrides the request timeout for large result sets.
        """
        argument = {"TABLE_NAME": table_name}
        if table_type:
            argument["TABLE_TYPE"] = table_type
        if unit:
            argument["UNIT"] = unit
        if styles:
            argument["STYLES"] = styles
        if components:
            argument["COMPONENTS"] = list(components)
        if node_elems:
            argument["NODE_ELEMS"] = node_elems
        if load_case_names:
            argument["LOAD_CASE_NAMES"] = list(load_case_names)
        if parts:
            argument["PARTS"] = list(parts)
        return self.request("POST", "/post/TABLE", {"Argument": argument},
                            timeout=timeout or self.ANALYSIS_TIMEOUT)

    @staticmethod
    def duplicate_columns(response):
        """Column headers that appear more than once in a ``/post/TABLE``
        response. A non-empty result flags a component→column aliasing problem
        (e.g. ``Axial`` and ``Shear-z`` resolving to the same field, seen on
        some BEAMFORCE result shapes) — the values under aliased headers are
        unreliable and should be re-queried."""
        if not isinstance(response, dict):
            return []
        for value in response.values():
            if isinstance(value, dict) and "HEAD" in value:
                head = value.get("HEAD") or []
                return [c for c, n in Counter(head).items() if n > 1]
        return []

    def beam_forces(self, elem_ids, load_case_names,
                    components=("Elem", "Load", "Part", "Axial",
                                "Shear-y", "Shear-z", "Moment-y", "Moment-z"),
                    unit=None, styles=None, validate=True):
        """
        ``POST /post/TABLE`` BEAMFORCE in the request shape confirmed against
        live Civil NX: **integer** element ids in ``NODE_ELEMS["KEYS"]`` plus
        ``UNIT``, ``STYLES``, and ``PARTS`` — omitting any of those returns the
        ``"second query is wrong"`` HTTP 400. ``elem_ids`` are integer beam
        element ids; ``load_case_names`` use the result suffixes (``"…(ST)"``
        static, ``"…(MV:all)"`` moving). Returns the raw ``/post/TABLE`` JSON
        (flatten with :func:`civilpy...`/``brr.rating.parse_result_table``).

        When ``validate`` is set (default), the returned table is checked for
        duplicate column headers via :meth:`duplicate_columns` and a warning is
        issued if any are found — guarding against the component aliasing that
        produced identical Axial / Shear-z envelopes on some models.
        """
        response = self.result_table(
            "BeamForce", table_type="BEAMFORCE", components=list(components),
            node_elems={"KEYS": [int(e) for e in elem_ids]},
            load_case_names=list(load_case_names), parts=["Part I", "Part J"],
            unit=unit or {"FORCE": "KIPS", "DIST": "FT"},
            styles=styles or {"FORMAT": "Default", "PLACE": 12},
        )
        if validate:
            dups = self.duplicate_columns(response)
            if dups:
                warnings.warn(
                    f"MIDAS BEAMFORCE returned duplicate column headers {dups}; "
                    f"force components may be aliased — verify Axial vs Shear-z "
                    f"before trusting these envelopes.",
                    stacklevel=2,
                )
        return response

    def __repr__(self):
        return f"<MidasCivil {self.base_url}>"
