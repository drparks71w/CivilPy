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
        f"oracle+cx_oracle://{secrets['BRR_USN']}:{secrets['BRR_PASS']}@{secrets['BRR_SERVER']}:{secrets['BRR_PORT']}/?service_name={secrets['BRR_SERVICE']}"
    )

    # Create the engine
    oracle_engine = create_engine(oracle_connection_string)

    # Establish connection
    oracle_conn = oracle_engine.connect()
    print("Connection successful!")

    return oracle_conn, oracle_engine