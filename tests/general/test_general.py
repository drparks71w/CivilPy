#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import pandas as pd
import pytest
from unittest.mock import MagicMock
from civilpy.general import get_table_as_df, PrintColors


class TestGetTableAsDf:
    def test_returns_dataframe(self):
        # get_table_as_df needs SQLAlchemy (the optional "db" extra).
        pytest.importorskip("sqlalchemy")
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("val1", "val2")]
        mock_result.keys.return_value = ["col1", "col2"]
        mock_conn.execute.return_value = mock_result

        df = get_table_as_df(mock_conn, "public", "test_table")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["col1", "col2"]


class TestPrintColors:
    def test_colors_defined(self):
        assert PrintColors.HEADER == "\033[95m"
        assert PrintColors.OKGREEN == "\033[92m"
        assert PrintColors.ENDC == "\033[0m"
