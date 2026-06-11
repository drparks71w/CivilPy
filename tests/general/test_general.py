"""
CivilPy
Copyright (C) 2019-2026 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pandas as pd
from unittest.mock import MagicMock
from civilpy.general import get_table_as_df, PrintColors


class TestGetTableAsDf:
    def test_returns_dataframe(self):
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
