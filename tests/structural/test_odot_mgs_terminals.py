#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the MGS bridge terminal assemblies (MGS-3.1/3.2/3.3) and
the standard-run layout (MGS-2.1)."""

import pytest

from civilpy.structural.odot.guardrail import (
    BRIDGE_TERMINALS,
    MGS_DRAWINGS,
    bridge_terminal,
    layout_bridge_terminal,
    layout_mgs_run,
)


def test_terminal_catalog():
    assert set(BRIDGE_TERMINALS) == {"Type 1", "Type 2", "Type TST-2"}
    with pytest.raises(ValueError, match="Type 1"):
        bridge_terminal("Type 9")


def test_type1_post_stations():
    t = bridge_terminal("Type 1")
    assert t.n_posts == 13
    st = t.post_stations_in()
    assert st[0] == 22.75                       # 1'-10 3/4" to post 1
    # posts 1-10 at quarter spacing, 10-13 at half spacing
    assert st[9] - st[0] == pytest.approx(9 * 18.75)
    assert st[12] - st[9] == pytest.approx(3 * 37.5)
    lay = layout_bridge_terminal("Type 1")
    assert len(lay.posts) == 13
    # posts 1-6 are the long 6'-6" posts
    assert all(length == 78.0 for n, _, length, _ in lay.posts if n <= 6)
    assert all(length == 72.0 for n, _, length, _ in lay.posts if n > 6)
    joined = " ".join(lay.notes)
    assert "nested thrie beam" in joined
    assert "Item 606" in joined
    assert "curb" in joined.lower()


def test_type1_connects_to_wave3_railings():
    t = bridge_terminal("Type 1")
    assert "BR-1-13" in t.connects_to
    assert "TST-1-99" in t.connects_to
    assert "RM-4.6" in t.connects_to


def test_type2_is_trailing_end_connector():
    t = bridge_terminal("Type 2")
    assert t.n_posts == 1
    assert "one-directional" in t.notes
    assert "bearing plate" in t.connection.lower()
    lay = layout_bridge_terminal("Type 2")
    assert lay.length_in == 37.5


def test_tst2_post_groups_and_spacings():
    t = bridge_terminal("Type TST-2")
    assert t.n_posts == 10
    assert t.post_spacings_in == (37.5, 37.5, 37.5, 18.75, 18.75, 18.75,
                                  18.75, 37.5, 37.5)
    lay = layout_bridge_terminal("Type TST-2")
    posts = {n: (post, length) for n, post, length, _ in lay.posts}
    assert posts[1][0].startswith("W6x9") and posts[1][1] == 72.0
    assert posts[10][0].startswith("W6x15") and posts[10][1] == 84.0
    assert t.connects_to == ("TST-2-21",)
    assert "W-to-thrie" in lay.notes[1]


def test_registry_and_terminals_agree():
    for des, t in BRIDGE_TERMINALS.items():
        assert t.scd in MGS_DRAWINGS
        assert MGS_DRAWINGS[t.scd].category == "bridge_terminal"


def test_mgs_run_layout():
    lay = layout_mgs_run(100.0)
    assert lay.spacing.name == "standard"
    gaps = [b - a for a, b in
            zip(lay.post_stations_ft, lay.post_stations_ft[1:])]
    assert all(g == pytest.approx(6.25) for g in gaps)
    assert lay.post_stations_ft[-1] == pytest.approx(100.0)
    assert lay.n_panels == 4                    # 100 ft / 25 ft
    assert lay.rail_height_in == 31.0


def test_mgs_run_quarter_spacing_and_guards():
    lay = layout_mgs_run(25.0, spacing="quarter", panel_length_ft=12.5)
    gaps = [b - a for a, b in
            zip(lay.post_stations_ft, lay.post_stations_ft[1:])]
    assert all(g == pytest.approx(18.75 / 12.0) for g in gaps)
    with pytest.raises(ValueError, match="panel_length"):
        layout_mgs_run(100.0, panel_length_ft=20.0)
    with pytest.raises(ValueError, match="spacing"):
        layout_mgs_run(100.0, spacing="double")
    with pytest.raises(ValueError, match="length_ft"):
        layout_mgs_run(0.0)


def test_rated3_registry_notes_enriched():
    for scd in ("MGS-2.3", "MGS-2.4", "MGS-4.1", "MGS-4.2", "MGS-6.1"):
        assert MGS_DRAWINGS[scd].notes, scd
    assert "Long-Span" in MGS_DRAWINGS["MGS-2.3"].notes
    assert "Type 2 BCT" in MGS_DRAWINGS["MGS-4.2"].notes
