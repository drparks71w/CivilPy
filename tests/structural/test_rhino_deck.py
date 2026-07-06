#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""G6 -- deck slab, parapets, and railing generation from a girder-line model.
Authors a small girder ``.3dm`` (the reader's own fixture style), builds the
deck onto a companion file, and checks the geometry counts, the dead-load
quantities, and the tag round-trip the ``GirderDeck`` importer consumes."""

import warnings

import pytest

rhino3dm = pytest.importorskip("rhino3dm")

from civilpy.structural.rhino_gdr import GTAG
from civilpy.structural.rhino_deck import (
    build_deck, read_deck_model, parapet_dc2_klf, DEFAULT_DECK_T_IN,
)


def _tag(obj_attr, **kv):
    for k, v in kv.items():
        obj_attr.SetUserString(GTAG + k, str(v))


def _author_girders(path, *, ys=(0.0, 7.0, 14.0, 21.0, 28.0), deck_t=None):
    """A 5-girder-line frame at 7 ft spacing, 0..120 ft long, optionally with a
    document-level gdr.deck_t marker."""
    f = rhino3dm.File3dm()
    f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Feet
    for i, y in enumerate(ys, start=1):
        pl = rhino3dm.Polyline()
        for x in (0.0, 60.0, 120.0):
            pl.Add(x, y, 0.0)
        ga = rhino3dm.ObjectAttributes()
        _tag(ga, kind="girder", shape="W24X104", grade="Grade 50", line=i)
        f.Objects.AddCurve(pl.ToPolylineCurve(), ga)
        for x in (0.0, 60.0, 120.0):
            ba = rhino3dm.ObjectAttributes()
            _tag(ba, kind="support", fixity="expansion", line=i)
            f.Objects.AddPoint(rhino3dm.Point3d(x, y, 0.0), ba)
    if deck_t is not None:
        da = rhino3dm.ObjectAttributes()
        _tag(da, kind="bridge", deck_t=str(deck_t), deck_weff="84")
        f.Objects.AddPoint(rhino3dm.Point3d(0.0, -4.0, 0.0), da)
    assert f.Write(str(path), 7)


@pytest.fixture
def girders(tmp_path):
    p = tmp_path / "girders.3dm"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _author_girders(p, deck_t=8.5)
    return str(p)


class TestBuildDeck:
    def test_geometry_and_extents(self, girders, tmp_path):
        out = tmp_path / "deck.3dm"
        dm = build_deck(girders, out_path=out, overhang_ft=3.5)
        # 28 ft girder spread + 2 x 3.5 ft overhang
        assert dm.width_ft == pytest.approx(35.0)
        assert dm.length_ft == pytest.approx(120.0)
        assert dm.girder_spacing_ft == pytest.approx(7.0)
        assert dm.n_girder_lines == 5
        assert (dm.n_deck, dm.n_parapet, dm.n_railing) == (1, 2, 0)

    def test_deck_thickness_from_model(self, girders, tmp_path):
        # gdr.deck_t = 8.5 was authored, so it is used without an override
        dm = build_deck(girders, out_path=tmp_path / "d.3dm")
        assert dm.deck_t_in == pytest.approx(8.5)

    def test_deck_thickness_default_when_absent(self, tmp_path):
        p = tmp_path / "no_deck_t.3dm"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _author_girders(p, deck_t=None)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dm = build_deck(str(p), out_path=tmp_path / "d.3dm")
        assert dm.deck_t_in == pytest.approx(DEFAULT_DECK_T_IN)

    def test_deck_dc1_matches_tributary(self, girders, tmp_path):
        dm = build_deck(girders, out_path=tmp_path / "d.3dm", deck_t_in=8.5)
        # 8.5/12 ft x 7 ft spacing x 0.150 kcf
        assert dm.deck_dc1_klf_interior == pytest.approx(8.5 / 12 * 7 * 0.150)

    def test_parapet_dc2_from_catalog(self, girders, tmp_path):
        dm = build_deck(girders, out_path=tmp_path / "d.3dm",
                        parapet="BR-1 (36 in)")
        # BR-1 (36 in) gross section area 423.25 in^2 x 0.150 kcf / 144
        assert dm.parapet_dc2_klf_each == pytest.approx(423.25 / 144 * 0.150)
        # both edges carry one parapet; no railing here
        assert dm.total_dc2_klf == pytest.approx(2 * dm.parapet_dc2_klf_each)

    def test_railing_adds_geometry_and_load(self, girders, tmp_path):
        dm = build_deck(girders, out_path=tmp_path / "d.3dm",
                        parapet="BR-1 (36 in)", railing="TST-2 (three steel tube)")
        assert dm.n_railing == 2
        assert dm.railing_dc2_klf_each == pytest.approx(80.0 / 1000.0)  # 80 lb/ft
        assert dm.total_dc2_klf == pytest.approx(
            2 * (dm.parapet_dc2_klf_each + dm.railing_dc2_klf_each))

    def test_roundtrip_tags(self, girders, tmp_path):
        out = tmp_path / "deck.3dm"
        build_deck(girders, out_path=out, parapet="BR-1 (36 in)")
        rows = read_deck_model(str(out))
        kinds = sorted(r["kind"] for r in rows)
        assert kinds == ["deck", "parapet", "parapet"]
        deck = next(r for r in rows if r["kind"] == "deck")
        assert deck["attrs"]["t"] == pytest.approx(8.5)
        assert deck["attrs"]["width"] == pytest.approx(35.0)
        par = next(r for r in rows if r["kind"] == "parapet")
        assert par["attrs"]["designation"] == "BR-1 (36 in)"
        assert par["attrs"]["dc2"] == pytest.approx(423.25 / 144 * 0.150, abs=1e-4)

    def test_single_girder_line_rejected(self, tmp_path):
        p = tmp_path / "one_line.3dm"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _author_girders(p, ys=(0.0,), deck_t=8.5)
        with pytest.raises(ValueError, match="two girder lines"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                build_deck(str(p), out_path=tmp_path / "d.3dm")


def test_parapet_dc2_unknown_designation():
    with pytest.raises(KeyError, match="unknown bridge-railing"):
        parapet_dc2_klf("NOPE-99")
