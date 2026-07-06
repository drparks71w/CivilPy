#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""G5 (pure slice) -- real per-shape SECT + per-grade MATL assignment from the
hub, replacing the single placeholder.  The moving-load tables and analyze()
are the live-Civil-NX part; the section/material payloads are pure + testable."""

import pytest

from civilpy.structural.structural_model import StructuralModel, Units
from civilpy.structural.midas_models import (
    rolled_i_section_block, hub_section_material_blocks,
)


def test_rolled_i_section_references_aisc_db_by_default():
    blk = rolled_i_section_block("W24X104", sect_id=3)
    s = blk["3"]
    assert s["SECT_NAME"] == "W24X104"
    before = s["SECT_BEFORE"]
    assert before["SHAPE"] == "H"
    assert before["DATATYPE"] == 1
    assert before["SECT_I"] == {"DB_NAME": "AISC10(US)", "SECT_NAME": "W24X104"}


def test_rolled_i_section_custom_db_name():
    blk = rolled_i_section_block("W24X104", sect_id=1, db_name="AISC14(US)")
    assert blk["1"]["SECT_BEFORE"]["SECT_I"]["DB_NAME"] == "AISC14(US)"


def test_rolled_i_section_falls_back_to_user_dimensions():
    blk = rolled_i_section_block("W24X104", sect_id=3, db_name=None)
    s = blk["3"]
    assert s["SECT_NAME"] == "W24X104"
    before = s["SECT_BEFORE"]
    assert before["SHAPE"] == "H"
    assert before["DATATYPE"] == 2
    h, b, tw, tf, b2, tf2 = before["SECT_I"]["vSIZE"]
    assert (h, b, tw, tf) == (24.1, 12.8, 0.5, 0.75)   # AISC W24x104
    assert (b2, tf2) == (b, tf)                          # symmetric rolled shape


def _two_shape_bridge():
    m = StructuralModel(units=Units(force="kips", length="ft"))
    a = m.add_node(0, 0, 0).id
    b = m.add_node(60, 0, 0).id
    c = m.add_node(120, 0, 0).id
    m.add_element(a, b, role="girder", midas_type="BEAM",
                  section="W24X131", material="Grade 50")
    m.add_element(b, c, role="girder", midas_type="BEAM",
                  section="W24X104", material="Grade 50")
    return m


class TestHubSectionMaterialBlocks:
    def setup_method(self):
        self.m = _two_shape_bridge()
        self.blocks = hub_section_material_blocks(self.m)

    def test_distinct_sections_get_distinct_ids(self):
        assert set(self.blocks["sect_by_shape"]) == {"W24X131", "W24X104"}
        assert sorted(self.blocks["sect_by_shape"].values()) == [1, 2]
        assert set(self.blocks["SECT"]) == {"1", "2"}

    def test_one_material_per_grade(self):
        assert self.blocks["matl_by_grade"] == {"Grade 50": 1}
        assert self.blocks["MATL"]["1"]["NAME"] == "Grade 50"

    def test_every_element_assigned_real_section(self):
        for elem in self.m.elements.values():
            sid, mid = self.blocks["elem_assign"][elem.id]
            assert sid in (1, 2) and mid == 1
            # the assigned SECT carries the element's own shape label
            assert self.blocks["SECT"][str(sid)]["SECT_NAME"] == elem.section

    def test_sections_reference_the_aisc_db_by_default(self):
        w131 = self.blocks["SECT"][
            str(self.blocks["sect_by_shape"]["W24X131"])]
        assert w131["SECT_BEFORE"]["SECT_I"] == {
            "DB_NAME": "AISC10(US)", "SECT_NAME": "W24X131"}

    def test_sections_carry_real_geometry_with_db_name_none(self):
        blocks = hub_section_material_blocks(self.m, db_name=None,
                                              length_unit="in")
        w131 = blocks["SECT"][str(blocks["sect_by_shape"]["W24X131"])]
        h, b, tw, tf, *_ = w131["SECT_BEFORE"]["SECT_I"]["vSIZE"]
        assert (h, b, tw, tf) == (24.5, 12.9, 0.605, 0.96)  # AISC W24x131
