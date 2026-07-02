#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

from pint import UnitRegistry
import pandas as pd

try:
    from sqlalchemy import text
except ImportError:  # SQLAlchemy is an optional dependency (db extra)
    text = None

units = UnitRegistry()

def get_table_as_df(conn, schema, table):
    if text is None:
        raise ImportError(
            "SQLAlchemy is required for database functions. "
            "Install with: pip install civilpy[db]"
        )
    query = text(f"SELECT * FROM {schema}.{table}")
    result = conn.execute(query)
    df = pd.DataFrame(result.fetchall(), columns=result.keys())

    return df

class PrintColors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
