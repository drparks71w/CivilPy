#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
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

import json
from pathlib import Path
from sqlalchemy import create_engine

def load_secrets(file_path):
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
