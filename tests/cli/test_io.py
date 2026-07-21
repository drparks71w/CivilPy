#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ResultTable writers: csv, xlsx (with provenance), suffix dispatch."""

import csv

import pytest

from civilpy.cli.io_ import Column, CommandResult, ResultTable, write_result


def _result():
    t1 = ResultTable(
        title="Summary",
        columns=[Column("Name"), Column("Depth", "ft", ".1f")],
        rows=[("B-001", 42.5), ("B-002", None)],
    )
    t2 = ResultTable(
        title="SPT",
        columns=[Column("Depth", "ft"), Column("N")],
        rows=[(1.5, 24)],
    )
    return CommandResult(
        tables=[t1, t2],
        command="civilpy boring parse B-001.xml",
        inputs={"path": "B-001.xml"},
    )


def test_csv_single_table(tmp_path):
    result = _result()
    result.tables = result.tables[:1]
    out = tmp_path / "out.csv"
    written = write_result(result, out)
    assert written == [out]
    rows = list(csv.reader(out.open()))
    assert rows[0] == ["Name", "Depth (ft)"]
    assert rows[1] == ["B-001", "42.5"]
    assert rows[2] == ["B-002", ""]  # None → empty cell


def test_csv_multi_table_suffixes(tmp_path):
    written = write_result(_result(), tmp_path / "out.csv")
    assert sorted(p.name for p in written) == ["out_spt.csv", "out_summary.csv"]


def test_xlsx_sheets_and_provenance(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    out = tmp_path / "out.xlsx"
    write_result(_result(), out)
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["Summary", "SPT", "provenance"]
    ws = wb["Summary"]
    assert ws["B1"].value == "Depth (ft)"
    assert ws["B2"].value == 42.5  # raw number, not formatted text
    prov = {row[0].value: row[1].value for row in wb["provenance"].iter_rows(min_row=2)}
    assert prov["command"] == "civilpy boring parse B-001.xml"


def test_unknown_suffix_rejected(tmp_path):
    with pytest.raises(ValueError, match=".csv or .xlsx"):
        write_result(_result(), tmp_path / "out.pdf")
