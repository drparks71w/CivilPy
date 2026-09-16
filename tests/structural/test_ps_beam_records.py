#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""As-rated prestressed box-beam records: round trip, validation rules,
derived quantities.  Parametrised over generated patterns rather than
one fixture bridge -- every rule is exercised across a family of inputs."""

import itertools
import json

import pytest

from civilpy.structural.bim_spec import (
    CompositeRangeRecord, DeckRangeRecord, DiaphragmRangeRecord,
    MildBarRowRecord, PrestressedBoxBeamRecord, PsBeamSpanRecord,
    PsBoxSectionRecord, StirrupRangeRecord, StrandPatternRecord,
    StrandRecord, StrandRowRecord, record_from_dict, record_to_dict)


# ── builders ──────────────────────────────────────────────────────────────

def section(depth=21.0, width=48.0, name="OH-CB21-48"):
    return PsBoxSectionRecord(name=name, depth_in=depth, top_width_in=width,
                              bot_width_in=width, wall_in=5.0,
                              top_slab_in=3.0, bot_slab_in=4.5)


def grid(row_counts, spacing=2.0):
    """Rows at 2, 4, 6 ... in with ``row_counts`` positions each."""
    return tuple(StrandRowRecord(height_in=2.0 * (i + 1), positions=n,
                                 spacing_in=spacing)
                 for i, n in enumerate(row_counts))


def fill(rows, used, **strand_kw):
    """Strands in the first ``used[i]`` slots of each row."""
    return tuple(StrandRecord(row=i + 1, column=c + 1, **strand_kw)
                 for i, n in enumerate(used) for c in range(n))


def pattern(row_counts=(16, 16, 8), used=(14, 10, 2), **kw):
    rows = grid(row_counts)
    return StrandPatternRecord(rows=rows, strands=fill(rows, used), **kw)


def beam(n_spans=1, span_ft=60.0, pat=None, **kw):
    pat = pat or pattern()
    spans = tuple(PsBeamSpanRecord(length_ft=span_ft, strands=pat)
                  for _ in range(n_spans))
    return PrestressedBoxBeamRecord(name="B1", sections=(section(),),
                                    spans=spans, **kw)


# ── round trip ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n_spans,used", [(1, (14, 10, 2)), (3, (16, 0, 4)),
                                          (2, (1, 1, 1))])
def test_round_trip_through_json(n_spans, used):
    rec = beam(n_spans, pat=pattern(used=used),
               stirrups=(StirrupRangeRecord(start_ft=0.5, spacing_in=6.0,
                                            n_spaces=10),),
               composite_ranges=(CompositeRangeRecord(start_ft=0.0,
                                                      length_ft=60.0),),
               deck=(DeckRangeRecord(start_ft=0.0, length_ft=60.0,
                                     thickness_in=6.0),),
               diaphragms=(DiaphragmRangeRecord(start_ft=0.0, spacing_ft=20.0,
                                                n_spaces=3),),
               condition_factor="good")
    assert rec.validate() == []
    doc = json.loads(json.dumps(rec.to_dict()))
    back = PrestressedBoxBeamRecord.from_dict(doc)
    assert back == rec
    assert back.spans[0].strands.n_strands == sum(used)
    assert record_from_dict(StrandPatternRecord,
                            record_to_dict(rec.spans[0].strands)) \
        == rec.spans[0].strands


# ── derived quantities ────────────────────────────────────────────────────

@pytest.mark.parametrize("used", list(itertools.product((0, 3, 8), repeat=3)))
def test_row_counts_and_cg(used):
    if sum(used) == 0:
        pytest.skip("no strands is a validation failure, tested below")
    pat = pattern(row_counts=(8, 8, 8), used=used)
    assert pat.row_counts() == used
    assert pat.n_strands == sum(used)
    expected_cg = sum(n * 2.0 * (i + 1) for i, n in enumerate(used)) / sum(used)
    assert pat.cg_height_in() == pytest.approx(expected_cg)
    assert pat.total_area_in2 == pytest.approx(sum(used) * 0.153)


@pytest.mark.parametrize("positions,spacing", [(16, 2.0), (3, 4.0), (1, 2.0)])
def test_row_x_offsets_are_centred(positions, spacing):
    row = StrandRowRecord(height_in=2.0, positions=positions,
                          spacing_in=spacing)
    xs = [row.x_in(c) for c in range(1, positions + 1)]
    assert sum(xs) == pytest.approx(0.0)
    if positions > 1:
        assert xs[1] - xs[0] == pytest.approx(spacing)


def test_debonded_and_harped_flags():
    rows = grid((4,))
    strands = (StrandRecord(row=1, column=1),
               StrandRecord(row=1, column=2, debond_left_ft=3.0,
                            debond_right_ft=3.0),
               StrandRecord(row=1, column=3, harp_left_ft=20.0,
                            harp_right_ft=20.0, harp_end_left_row=1,
                            harp_end_right_row=1))
    pat = StrandPatternRecord(rows=rows, strands=strands,
                              configuration="harped_debonded")
    assert pat.validate() == []
    assert (pat.n_debonded, pat.n_harped) == (1, 1)


def test_composite_property_tristate():
    assert beam().composite is None
    assert beam(composite_ranges=(CompositeRangeRecord(
        start_ft=0, length_ft=60, composite=False),)).composite is False
    assert beam(composite_ranges=(
        CompositeRangeRecord(start_ft=0, length_ft=30, composite=False),
        CompositeRangeRecord(start_ft=30, length_ft=30),)).composite is True


# ── validation rules ──────────────────────────────────────────────────────

def _problems(rec):
    return "\n".join(rec.validate())


def test_strand_outside_grid_is_caught():
    rows = grid((4, 4))
    bad_row = StrandPatternRecord(rows=rows, strands=(
        StrandRecord(row=3, column=1),))
    bad_col = StrandPatternRecord(rows=rows, strands=(
        StrandRecord(row=2, column=5),))
    assert "beyond 2 rows" in _problems(bad_row)
    assert "beyond row 2's 4 positions" in _problems(bad_col)


def test_slot_used_twice_is_caught():
    rows = grid((4,))
    pat = StrandPatternRecord(rows=rows, strands=(
        StrandRecord(row=1, column=2), StrandRecord(row=1, column=2)))
    assert "used twice" in _problems(pat)


def test_p_and_e_rules():
    rows = grid((4,))
    with_layout = StrandPatternRecord(configuration="p_and_e", rows=rows,
                                      strands=fill(rows, (2,)), p_kips=300)
    assert "cannot carry a strand layout" in _problems(with_layout)
    no_force = StrandPatternRecord(configuration="p_and_e")
    assert "needs p_kips" in _problems(no_force)
    ok = StrandPatternRecord(configuration="p_and_e", p_kips=300.0,
                             cg_mid_in=3.0)
    assert ok.validate() == []
    assert ok.cg_height_in() == 3.0
    empty_layout = StrandPatternRecord(rows=rows)
    assert "needs at least one strand" in _problems(empty_layout)


@pytest.mark.parametrize("span_ft,debond", [(40.0, 21.0), (60.0, 30.5),
                                            (20.0, 10.1)])
def test_debond_past_midspan_is_caught(span_ft, debond):
    rows = grid((2,))
    pat = StrandPatternRecord(rows=rows, strands=(
        StrandRecord(row=1, column=1, debond_left_ft=debond),
        StrandRecord(row=1, column=2)), configuration="debonded")
    span = PsBeamSpanRecord(length_ft=span_ft, strands=pat)
    assert "exceeds half the span" in _problems(span)
    fine = PsBeamSpanRecord(length_ft=span_ft, strands=StrandPatternRecord(
        rows=rows, configuration="debonded", strands=(
            StrandRecord(row=1, column=1, debond_left_ft=span_ft / 2 - 0.5),
            StrandRecord(row=1, column=2))))
    assert fine.validate() == []


@pytest.mark.parametrize("depth,height", [(17.0, 17.0), (21.0, 24.0)])
def test_strand_row_above_section_is_caught(depth, height):
    rows = (StrandRowRecord(height_in=height, positions=4, spacing_in=2.0),)
    pat = StrandPatternRecord(rows=rows, strands=fill(rows, (2,)))
    rec = PrestressedBoxBeamRecord(
        name="B1", sections=(section(depth=depth),),
        spans=(PsBeamSpanRecord(length_ft=40.0, strands=pat),))
    assert "is above the" in _problems(rec)


def test_span_section_index_is_checked():
    rec = PrestressedBoxBeamRecord(
        name="B1", sections=(section(),),
        spans=(PsBeamSpanRecord(length_ft=40.0, strands=pattern(),
                                section=1),))
    assert "beyond 1 sections" in _problems(rec)


def test_section_geometry_rules():
    assert "two walls exceed" in _problems(PsBoxSectionRecord(
        name="x", depth_in=21, top_width_in=48, bot_width_in=48, wall_in=24))
    assert "exceed depth_in" in _problems(PsBoxSectionRecord(
        name="x", depth_in=21, top_width_in=48, bot_width_in=48,
        top_slab_in=11, bot_slab_in=10))
    assert "inside the section depth" in _problems(PsBoxSectionRecord(
        name="x", depth_in=21, top_width_in=48, bot_width_in=48, y_cg_in=21))


def test_nested_record_problems_are_prefixed():
    rec = beam(stirrups=(StirrupRangeRecord(start_ft=0.0, spacing_in=6.0,
                                            n_spaces=0),),
               continuity_bars=(MildBarRowRecord(bar="#5", count=0,
                                                 height_in=2.0, start_ft=0.0,
                                                 length_ft=10.0),))
    p = _problems(rec)
    assert "stirrups[0].n_spaces" in p
    assert "continuity_bars[0].count" in p


def test_enum_fields_reject_unknown_values():
    p = _problems(beam(condition_factor="bad"))
    assert "condition_factor" in p
    p = _problems(pattern(configuration="tendons"))
    assert "configuration" in p
