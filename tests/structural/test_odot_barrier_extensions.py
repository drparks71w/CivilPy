#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Tests for the Wave 8 barrier extensions: RM-4.6 end sections,
RM-4.4 transitions, RM-5.2 bikeway railing, RM-4.7 thrie-beam PCB
transitions."""

import pytest

from civilpy.structural.odot import bikeway_railing as bike
from civilpy.structural.odot.bikeway_railing import (
    BikewayRailingInput,
    layout_bikeway_railing,
)
from civilpy.structural.odot.roadway_barrier import (
    BARRIER_END_SECTIONS,
    barrier_end_section,
    layout_barrier_end_section,
    layout_barrier_transition,
)
from civilpy.structural.odot.roadway_portable_barrier import (
    THRIE_BEAM_PCB_TRANSITIONS,
    thrie_beam_pcb_transition,
    thrie_beam_transition_notes,
)


# ═════════════════════════ RM-4.6 end sections ════════════════════════════

def test_end_section_catalog():
    assert set(BARRIER_END_SECTIONS) == {"Type B", "Type B1", "Type D"}
    b = barrier_end_section("Type B")
    assert b.total_length_ft == 30.0
    assert (b.body_length_ft, b.face_transition_ft) == (16.0, 10.0)
    assert b.end_height_in == 32.0 and b.end_width_in == 32.0
    assert b.median
    d = barrier_end_section("Type D")
    assert d.total_length_ft == 14.0
    assert d.body_length_ft == 0.0
    assert d.end_width_in == 20.0 and d.end_core_width_in == 16.0
    assert not d.median


def test_end_section_stations_type_b():
    lay = layout_barrier_end_section("Type B")
    xs = [x for x, _ in lay.stations]
    # 0, 16 ft body, +10 ft transition, +32 in, +16 in
    assert xs == pytest.approx([0.0, 16.0, 26.0, 26.0 + 32.0 / 12.0, 30.0])
    first = lay.stations[0][1]
    assert max(z for _, z in first) == 42.0        # full Type B height
    end = lay.stations[-1][1]
    assert max(z for _, z in end) == 32.0
    assert max(o for o, _ in end) - min(o for o, _ in end) == 32.0
    assert any("MGS-3.1" in n for n in lay.notes)
    assert any("Item 622" in n for n in lay.notes)


def test_end_section_b1_tapers_to_42():
    lay = layout_barrier_end_section("Type B1")
    assert max(z for _, z in lay.stations[0][1]) == 57.0
    assert max(z for _, z in lay.stations[1][1]) == 42.0


def test_end_section_type_d_one_sided():
    lay = layout_barrier_end_section("Type D")
    xs = [x for x, _ in lay.stations]
    assert xs[0] == 0.0 and xs[-1] == pytest.approx(14.0)
    end = lay.stations[-1][1]
    # curb ledge on the traffic side only: exactly one 7 in ledge vertex pair
    assert sum(1 for _, z in end if z == 7.0) == 2


def test_end_section_unknown_raises():
    with pytest.raises(ValueError, match="Type B"):
        barrier_end_section("Type N")


# ═════════════════════════ RM-4.4 transitions ═════════════════════════════

def test_sign_support_transition_stations():
    lay = layout_barrier_transition("Type B", "sign support",
                                    obstruction_width_in=42.0)
    assert lay.total_length_ft == 90.0            # 40 + 10 + 40
    widths = [w for _, w in lay.stations]
    assert widths == [12.0, 42.0, 42.0, 12.0]
    assert any("5.25" in n for n in lay.notes)
    assert any("raceway" in n.lower() for n in lay.notes)


def test_pier_transition_variable_run():
    lay = layout_barrier_transition("Type B1", "pier",
                                    obstruction_length_ft=12.0)
    assert lay.obstruction_width_in == 48.0
    assert lay.total_length_ft == pytest.approx(40 + 5 + 12 + 5 + 40)


def test_transition_guards():
    with pytest.raises(ValueError, match="B/B1/C/C1"):
        layout_barrier_transition("Type N", "pier")
    with pytest.raises(ValueError, match="36.*48|foundation"):
        layout_barrier_transition("Type B", "sign support",
                                  obstruction_width_in=60.0)
    with pytest.raises(ValueError, match="kind"):
        layout_barrier_transition("Type B", "median")


# ═════════════════════════ RM-5.2 bikeway railing ═════════════════════════

def test_bikeway_constants():
    assert bike.SCD == "RM-5.2"
    assert bike.POST_SPACING_MAX_IN == 120.0
    assert bike.RAILING_HEIGHT_IN == 42.0
    assert bike.PAY_ITEM[2].endswith("WOOD FENCE")


def test_bikeway_layout_posts_and_flares():
    lay = layout_bikeway_railing(BikewayRailingInput(100.0))
    assert lay.total_length_ft == 140.0           # + two 20 ft flares
    posts = lay.post_stations_ft
    assert posts[0] == 0.0 and posts[-1] == pytest.approx(140.0)
    gaps = [b - a for a, b in zip(posts, posts[1:])]
    assert all(g <= 10.0 + 1e-9 for g in gaps)
    assert len(lay.midspan_stations_ft) == len(posts) - 1
    # mid-span stiffeners sit at bay centers
    assert lay.midspan_stations_ft[0] == pytest.approx(gaps[0] / 2.0)
    assert lay.embedment_in == 36.0
    assert lay.n_rail_pieces == 3 * 7             # 140 ft / 20 ft pieces


def test_bikeway_low_shoulder_embedment():
    lay = layout_bikeway_railing(BikewayRailingInput(
        60.0, flared_ends=False, low_shoulder=True))
    assert lay.total_length_ft == 60.0
    assert lay.embedment_in == 60.0
    with pytest.raises(ValueError):
        layout_bikeway_railing(BikewayRailingInput(0.0))


# ═════════════════════════ RM-4.7 PCB transitions ═════════════════════════

def test_thrie_beam_pairs():
    assert len(THRIE_BEAM_PCB_TRANSITIONS) == 3
    t = thrie_beam_pcb_transition('Generic 32" F-shape PCB',
                                  'Generic 32" New Jersey shape PCB')
    assert t.sheet == 1                            # order-free lookup
    t3 = thrie_beam_pcb_transition('J-J Hook 32" F-shape PCB',
                                   'Generic 32" F-shape PCB')
    assert t3.sheet == 3


def test_thrie_beam_jj_hook_nj_not_approved():
    with pytest.raises(ValueError, match="no transition"):
        thrie_beam_pcb_transition('J-J Hook 32" New Jersey shape PCB',
                                  'Generic 32" F-shape PCB')


def test_thrie_beam_notes_carry_hardware_and_limits():
    notes = " ".join(thrie_beam_transition_notes())
    assert "nested 12-gauge thrie-beam" in notes
    assert "MGS-1.1" in notes
    assert "once per mile" in notes
    assert "100 ft of unanchored PCB" in notes
    assert "Item 622" in notes
