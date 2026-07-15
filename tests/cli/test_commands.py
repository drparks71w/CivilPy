#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""End-to-end command runs through the batch front end."""

import json

import pytest

from civilpy.cli.batch import execute, one_shot_line
from civilpy.cli.registry import find_spec
from civilpy.cli.session import CliContext

from tests.geotechnical.test_boring import DIGGS_FIXTURE


@pytest.fixture()
def diggs_file(tmp_path):
    path = tmp_path / "B-001.xml"
    path.write_text(DIGGS_FIXTURE)
    return path


def test_odot_slab_simple(capsys):
    assert execute(["odot", "slab", "20"]) == 0
    out = capsys.readouterr().out
    assert "16.25" in out  # 20 ft simple-span deck thickness
    assert "#8" in out     # A bar


def test_odot_slab_bad_span_exits_2(capsys):
    assert execute(["odot", "slab", "99"]) == 2
    assert "not available" in capsys.readouterr().out


def test_hydro_channel_matches_doctest_values(capsys):
    assert execute([
        "hydro", "channel", "200", "--width", "10",
        "--n", "0.013", "--slope", "0.002",
    ]) == 0
    out = capsys.readouterr().out
    assert "2.316" in out  # critical depth from open_channel docstring


def test_road_vcurve_k_value(capsys):
    assert execute([
        "road", "vcurve", "--g1", "2", "--g2", "-1.5", "--length", "600",
    ]) == 0
    out = capsys.readouterr().out
    assert "171.43" in out  # K = 600 / 3.5


def test_road_hcurve_tangent(capsys):
    assert execute(["road", "hcurve", "--radius", "1000", "--delta", "35"]) == 0
    assert "315.30" in capsys.readouterr().out  # T = R tan(Δ/2)


def test_boring_parse_writes_xlsx(diggs_file, tmp_path, capsys):
    openpyxl = pytest.importorskip("openpyxl")
    out = tmp_path / "boring.xlsx"
    assert execute(["boring", "parse", str(diggs_file), "-o", str(out)]) == 0
    wb = openpyxl.load_workbook(out)
    assert "Boreholes" in wb.sheetnames and "provenance" in wb.sheetnames
    spt = wb["SPT"]
    assert spt["E2"].value == 24  # N from the fixture's 12/14/10 drive


def test_boring_parse_missing_file(capsys):
    assert execute(["boring", "parse", "does-not-exist.xml"]) == 2
    assert "no such file" in capsys.readouterr().out


def test_scour_pier_reads_boring_gradation(diggs_file, capsys):
    assert execute([
        "hydro", "scour-pier", "--velocity", "6.2", "--depth", "8",
        "--pier-width", "3", "--boring", str(diggs_file),
        "--bed-depth", "1.5",
    ]) == 0
    out = capsys.readouterr().out
    assert "0.18" in out  # D50 from the fixture gradation


def test_scour_pier_resolves_loaded_boring(diggs_file, capsys):
    ctx = CliContext(interactive=True)
    ctx.workspace.load(str(diggs_file))
    (name,) = ctx.workspace.objects
    assert execute([
        "hydro", "scour-pier", "--velocity", "6.2", "--depth", "8",
        "--pier-width", "3", "--boring", name,
    ], ctx=ctx) == 0
    assert "Local pier scour" in capsys.readouterr().out


def test_one_shot_line_skips_defaults():
    spec = find_spec("hydro", "scour-pier")
    line = one_shot_line(spec, {
        "velocity": 6.2, "depth": 8.0, "pier_width": 3.0,
        "shape": "round", "skew": 0.0, "boring": None,
        "bed_depth": 0.0, "pier_length": None,
    }, out=None)
    assert line == (
        "civilpy hydro scour-pier --velocity 6.2 --depth 8.0 --pier-width 3.0"
    )


# --------------------------------------------------------------------------- #
# Phase 1 batch commands: snbi, photos, report, odot bridge/tiff
# --------------------------------------------------------------------------- #
def _snbi_record():
    pytest.importorskip("pydantic")
    from tests.state.ohio.test_snbi import make_bridge

    return make_bridge().model_dump(exclude_none=True)


def test_snbi_validate_clean_submission(tmp_path, capsys):
    path = tmp_path / "submission.json"
    path.write_text(json.dumps([_snbi_record()]))
    assert execute(["snbi", "validate", str(path)]) == 0
    out = capsys.readouterr().out
    assert "SNBI validation" in out


def test_snbi_validate_bad_record_exits_1(tmp_path, capsys):
    bad = _snbi_record()
    bad["BL01"] = 99  # not a valid SNBI state code
    path = tmp_path / "submission.json"
    path.write_text(json.dumps([_snbi_record(), bad]))
    assert execute(["snbi", "validate", str(path)]) == 1
    out = capsys.readouterr().out
    assert "BL01" in out and "state code" in out


def test_snbi_validate_not_json(tmp_path, capsys):
    path = tmp_path / "submission.json"
    path.write_text("not json at all")
    assert execute(["snbi", "validate", str(path)]) == 2
    assert "not valid JSON" in capsys.readouterr().out


@pytest.fixture()
def photo_folder(tmp_path):
    """Two EXIF-tagged photos (numbered across the natural-sort boundary)
    and one with no metadata."""
    from PIL import Image
    from PIL.TiffImagePlugin import IFDRational

    folder = tmp_path / "photos"
    folder.mkdir()
    for i, name in enumerate(["IMG_2.jpg", "IMG_10.jpg"]):
        exif = Image.Exif()
        exif[306] = f"2026:06:0{i + 1} 10:30:00"  # DateTime
        exif[271], exif[272] = "Canon", "EOS R5"
        exif[0x8825] = {  # GPS IFD: 39°57'12.34"N 82°59'56.78"W
            1: "N", 2: (IFDRational(39), IFDRational(57), IFDRational(1234, 100)),
            3: "W", 4: (IFDRational(82), IFDRational(59), IFDRational(5678, 100)),
        }
        Image.new("RGB", (320, 240), (i * 100, 50, 50)).save(
            folder / name, exif=exif)
    Image.new("RGB", (320, 240)).save(folder / "no_exif.jpg")
    return folder


def test_photos_exif_reads_gps_decimal(photo_folder, capsys):
    assert execute(["photos", "exif", str(photo_folder)]) == 0
    out = capsys.readouterr().out
    assert "Canon" in out  # the cell may wrap in a narrow console
    assert "39.9534" in out and "-82.9" in out  # signed decimal degrees


def test_photos_rename_from_spreadsheet(photo_folder, capsys):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.append([str(photo_folder / "IMG_2.jpg"), "Pier 2, East Column"])
    wb.save(photo_folder / "map.xlsx")
    assert execute(["photos", "rename", str(photo_folder)]) == 0
    renamed = photo_folder / "Renamed_Photos" / "pier-2-east-column.jpg"
    assert renamed.exists()


def test_photos_resize_pads_to_frame(photo_folder, tmp_path, capsys):
    from PIL import Image

    dest = tmp_path / "resized"
    assert execute([
        "photos", "resize", str(photo_folder / "IMG_2.jpg"),
        "--width", "160", "--height", "160", "--dest", str(dest),
    ]) == 0
    with Image.open(dest / "IMG_2.jpg") as img:
        assert img.size == (160, 160)  # aspect kept, bars fill the frame


def test_photos_stamp_skips_missing_exif(photo_folder, capsys):
    assert execute(["photos", "stamp", str(photo_folder)]) == 0
    out = capsys.readouterr().out
    assert "no_exif.jpg: no EXIF timestamp" in out
    assert (photo_folder / "Stamped_Photos" / "IMG_2.jpg").exists()


@pytest.fixture()
def sheet_folder(tmp_path):
    from PIL import Image

    folder = tmp_path / "sheets"
    folder.mkdir()
    for i, name in enumerate(["sheet_1.tif", "sheet_2.tif", "sheet_10.tif"]):
        Image.new("RGB", (60, 40), (i * 60, 100, 150)).save(folder / name)
    return folder


def test_odot_tiff_join_and_split_roundtrip(sheet_folder, tmp_path, capsys):
    pytest.importorskip("tifftools")
    from PIL import Image

    joined = tmp_path / "planset.tiff"
    assert execute([
        "odot", "tiff-join", str(sheet_folder), "--dest", str(joined),
    ]) == 0
    with Image.open(joined) as img:
        pages = []
        for i in range(3):
            img.seek(i)
            pages.append(img.getpixel((0, 0))[0])
    assert pages == [0, 60, 120]  # natural order: sheet_2 before sheet_10

    out_dir = tmp_path / "pages"
    assert execute([
        "odot", "tiff-split", str(joined), "--dest", str(out_dir),
    ]) == 0
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "planset_p001.tif", "planset_p002.tif", "planset_p003.tif",
    ]


def test_odot_bridge_renders_tims_record(monkeypatch, capsys):
    from civilpy.state.ohio.DOT import TIMS

    monkeypatch.setattr(
        TIMS.TIMSBridge, "_fetch_bridge_data",
        lambda self: {
            "STR_LOC_CARRIED": "I-71 NB", "NLFID": "SDELIR00071**C",
            "COUNTY_CD": "DEL", "DISTRICT": "06",
            "LATITUDE_DD": 40.2092, "LONGITUDE_DD": -82.9304,
            "YR_BUILT": -347155200000,  # epoch ms for 1959
            "LANES_ON": "2", "MAIN_STR_MTL_CD": "2",
            "MAIN_STR_TYPE_CD": "01", "SUFF_RATING": "089.9",
            "DECK_SUMMARY": "6", "SUPS_SUMMARY": "6", "SUBS_SUMMARY": "6",
        },
    )
    assert execute(["odot", "bridge", "2102374"]) == 0
    out = capsys.readouterr().out
    assert "I-71 NB" in out
    assert "1959" in out                 # epoch-ms year conversion
    assert "Concrete Continuous" in out  # NBI material code 2
    assert "Slab" in out                 # NBI design type 01


def test_odot_bridge_unknown_sfn_exits_2(monkeypatch, capsys):
    from civilpy.state.ohio.DOT import TIMS

    monkeypatch.setattr(
        TIMS.TIMSBridge, "_fetch_bridge_data", lambda self: None)
    assert execute(["odot", "bridge", "0000000"]) == 2
    assert "No bridge found" in capsys.readouterr().out


def test_report_notebook_latex_filters_tagged_cells(tmp_path, capsys):
    nbformat = pytest.importorskip("nbformat")
    pytest.importorskip("nbconvert")

    nb = nbformat.v4.new_notebook()
    keep = nbformat.v4.new_code_cell("print('M_u = 245.3 kip-ft')")
    drop = nbformat.v4.new_code_cell("secret_setup = True")
    drop.metadata["tags"] = ["remove_cell"]
    nb.cells = [keep, drop]
    path = tmp_path / "calc.ipynb"
    nbformat.write(nb, str(path))

    assert execute(["report", "notebook", str(path), "--format", "latex"]) == 0
    tex = (tmp_path / "calc.tex").read_text()
    assert "secret_setup" not in tex
    assert "kip" in tex


def test_report_notebook_branding_needs_webpdf(tmp_path, capsys):
    nbformat = pytest.importorskip("nbformat")
    pytest.importorskip("nbconvert")

    nb = nbformat.v4.new_notebook()
    path = tmp_path / "calc.ipynb"
    nbformat.write(nb, str(path))
    assert execute([
        "report", "notebook", str(path),
        "--format", "latex", "--branding", "odot",
    ]) == 2
    assert "webpdf" in capsys.readouterr().out
