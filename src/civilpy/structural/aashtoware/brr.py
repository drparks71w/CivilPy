#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import json
from pathlib import Path
from sqlalchemy import create_engine

def load_secrets(file_path):
    """Load database credentials from a JSON secrets file.

    Args:
        file_path (str or Path): Path to a JSON file containing credential
            keys ``BRR_USN``, ``BRR_PASS``, ``BRR_SERVER``, ``BRR_PORT``,
            and ``BRR_SERVICE``.

    Returns:
        dict: Parsed JSON contents of the secrets file.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(file_path, 'r') as file:
        user_info = json.load(file)
    return user_info

# Checks the users home directory for secrets.json
file_path = Path.home() / 'secrets.json'

try:
    secrets = load_secrets(file_path)
except FileNotFoundError as e:
    print("Secrets.json not found, make sure it exists in the users home directory ~/secrets.json or C:\\users\\Username\\secrets.json")

def connect_to_brr():
    """Create an Oracle database connection to the BRR (Bridge Rating and
    Reporting) system.

    Credentials are read from ``~/secrets.json`` by the module-level
    ``load_secrets`` call. The connection uses the Oracle service-name format
    via ``oracledb`` / SQLAlchemy.

    Returns:
        tuple: ``(oracle_conn, oracle_engine)`` where *oracle_conn* is an
        active :class:`sqlalchemy.engine.Connection` and *oracle_engine* is
        the underlying :class:`sqlalchemy.engine.Engine`.

    Raises:
        KeyError: If any required key is missing from the secrets dict.
        sqlalchemy.exc.OperationalError: If the database is unreachable.
    """
    # Oracle connection string using service name instead of SID
    oracle_connection_string = (
        f"oracle+oracledb://{secrets['BRR_USN']}:{secrets['BRR_PASS']}@{secrets['BRR_SERVER']}:{secrets['BRR_PORT']}/?service_name={secrets['BRR_SERVICE']}"
    )

    # Create the engine
    oracle_engine = create_engine(oracle_connection_string)

    # Establish connection
    oracle_conn = oracle_engine.connect()
    print("Connection successful!")

    return oracle_conn, oracle_engine
