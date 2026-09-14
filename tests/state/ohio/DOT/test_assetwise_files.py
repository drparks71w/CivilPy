#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""AssetWise inspection-file dump: union of the report-mapped and
asset-level scopes, routed by content type, filed per inspection year,
Windows-safe names, orphans counted not raised. Fake client encodes the
2026-08 live findings (SFN 1801503 keeps photos only at asset level)."""

from pathlib import Path

import pytest

from civilpy.cli.batch import execute
from civilpy.state.ohio.DOT.assetwise_files import (
    dump_inspection_files, extension_for, list_inspection_files, safe_name,
    target_path,
)


class FakeClient:
    def __init__(self):
        self.downloads = []

    def get_as_id(self, sfn):
        return 555 if sfn == "1801503" else None

    def get_inspections(self, as_id):
        return [
            {"ast_id": 200, "ast_inspection_date": "2023-01-31T00:00:00"},
            {"ast_id": 100, "ast_inspection_date": "2021-01-05T00:00:00"},
        ]

    def get_report_files(self, ast_id):
        if ast_id == 100:
            return [{"af_id": 1, "af_filename": "old.jpg",
                     "af_description": "North elevation: 2021",
                     "af_date": "2021-01-06T14:35:00", "af_cover": True}]
        return [
            {"af_id": 1, "af_filename": "old.jpg", "af_date": "2021-01-06T14:35:00"},
            {"af_id": 2, "af_filename": "new.jpg", "af_description": "Deck edge spall",
             "af_date": "2023-01-31T10:00:00"},
            {"af_id": 3, "af_filename": "CUY-10-1613 Fracture Critical Member Plan.pdf",
             "af_date": "2023-02-01T00:00:00", "af_print": True},
            {"af_id": 9, "af_filename": "gone.jpg", "af_date": "2023-02-01T00:00:00"},
        ]

    def get_asset_files(self, as_id):
        return [
            {"af_id": 7, "af_content_type": "image/bitmap",
             "af_date_inserted": "2021-11-30T19:46:00", "af_deleted": False},
            {"af_id": 8, "af_content_type": "application/pdf",
             "af_date_inserted": "2022-02-02T00:00:00", "af_deleted": False},
            {"af_id": 2, "af_content_type": "image/jpeg",
             "af_date_inserted": "2023-01-31T10:00:00", "af_deleted": False},
        ]

    SERVED = {8: "CUY-0010-1613_1801503_2021 Routine Report.pdf"}

    def download_file_named(self, af_id, timeout=120):
        self.downloads.append(af_id)
        if af_id == 9:
            return None, "", ""                       # vendor-side orphan
        if af_id in (3, 8):
            return f"%PDF-{af_id}".encode(), "application/pdf", self.SERVED.get(af_id, "")
        if af_id == 7:
            return b"BM-map", "image/bitmap", ""
        return f"JPEG-{af_id}".encode(), "image/jpeg", ""

    def map_assets(self, fn, items, max_workers=10):
        for item in items:
            yield item, fn(item)


def _files(root: Path):
    return sorted(str(p.relative_to(root)).replace("\\", "/")
                  for p in root.rglob("*") if p.is_file())


def test_listing_is_union_deduped_against_earliest_report():
    items = {i["af_id"]: i for i in list_inspection_files(FakeClient(), 555)}
    assert sorted(items) == [1, 2, 3, 7, 8, 9]
    assert items[1]["ast_id"] == 100 and items[1]["caption"] == "North elevation: 2021"
    assert items[2]["ast_id"] == 200                     # report-mapped wins over asset-level
    assert items[7]["scope"] == "asset" and items[7]["report_date"] is None


def test_names_are_windows_safe_and_extensions_resolve():
    assert safe_name('Pier 2: "north" <face>? ..') == "Pier 2_ _north_ _face__"
    assert extension_for("image/jpeg", "Deck") == ".jpg"
    assert extension_for("application/pdf", "Plan.PDF") == ".pdf"
    assert extension_for("image/bitmap") == ".bmp"


def test_dump_photos_by_inspection_year(tmp_path):
    client = FakeClient()
    summary = dump_inspection_files("1801503", tmp_path, client=client)
    assert summary["as_id"] == 555
    assert summary["written"] == 3 and summary["failed"] == 1
    assert summary["skipped"] == 2                       # the two PDFs
    assert _files(tmp_path) == [
        "Inspection - 2021/2021-01-06 North elevation_ 2021.jpg",
        "Inspection - 2021/2021-11-30 assetwise_7.bmp",  # asset-level: filed by its own date
        "Inspection - 2023/2023-01-31 Deck edge spall.jpg",
    ]
    assert sorted(client.downloads) == [1, 2, 7, 9]


def test_dump_all_files_flat_and_served_names(tmp_path):
    summary = dump_inspection_files(555, tmp_path, photos_only=False, flat=True,
                                    client=FakeClient())
    assert summary["written"] == 5
    names = _files(tmp_path)
    assert "2022-02-02 CUY-0010-1613_1801503_2021 Routine Report.pdf" in names
    assert "2023-02-01 CUY-10-1613 Fracture Critical Member Plan.pdf" in names


def test_unknown_sfn_raises():
    with pytest.raises(LookupError):
        dump_inspection_files("0000000", "/tmp/nowhere", client=FakeClient())


def test_target_path_dedupes_at_write(tmp_path):
    item = {"af_id": 1, "ast_id": 1, "report_date": None, "filename": "a.jpg",
            "caption": "", "content_type": "image/jpeg", "file_date": None,
            "scope": "report", "cover": False, "in_report": False}
    assert target_path(tmp_path, item) == tmp_path / "a.jpg"


def test_cli_verb_runs_with_fake_client(tmp_path, monkeypatch, capsys):
    import civilpy.state.ohio.DOT.assetwise_client as mod
    monkeypatch.setattr(mod, "AssetWiseClient", lambda: FakeClient())
    dest = tmp_path / "out"
    assert execute(["odot", "photos", "1801503", "--folder", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "written" in out and "3" in out
    assert (dest / "Inspection - 2023").is_dir()


def test_cli_verb_without_credentials_is_a_clean_error(monkeypatch, capsys, tmp_path):
    import civilpy.state.ohio.DOT.assetwise_client as mod

    def boom():
        raise FileNotFoundError("secrets.json")
    monkeypatch.setattr(mod, "AssetWiseClient", boom)
    assert execute(["odot", "photos", "1801503", "--folder", str(tmp_path)]) == 2
    assert "secrets.json" in capsys.readouterr().out
