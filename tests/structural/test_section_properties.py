"""
CivilPy
Copyright (C) 2019-2026 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from civilpy.structural.section_properties import CrossSection
from civilpy.structural.steel import W


class TestCrossSection:
    def test_basic_init(self):
        cs = CrossSection("A", (10, 2))
        assert cs.area == 20

    def test_repr(self):
        cs = CrossSection("A", (10, 2))
        result = repr(cs)
        assert "A" in result

    def test_add_second_plate(self):
        cs = CrossSection("A", (10, 2))
        cs("B", (10, 3))
        assert len(cs.labels) == 2
        assert cs.area == 50

    def test_add_plate_at_y(self):
        cs = CrossSection("A", (10, 2))
        cs("B", (8, 1), y=5.0)
        assert cs.area == 28

    def test_neutral_axis(self):
        cs = CrossSection("A", (10, 2))
        assert cs.n > 0

    def test_section_modulus(self):
        cs = CrossSection("A", (10, 4))
        assert cs.S > 0

    def test_check_negative_y_values(self):
        cs = CrossSection("A", (10, 2))
        result = cs.check_negative_y_values()
        assert isinstance(result, bool)

    def test_init_with_y(self):
        cs = CrossSection("A", (10, 4), y=2.0)
        assert cs.area == 40

    def test_else_branch_append_value(self):
        # Trigger 'else: print("Unexpected execution")' branch
        # This happens when shape=None and y=None for append_value
        # Called via __call__ with no shape and no y
        cs = CrossSection("flange", (10, 2))
        cs("web", (1, 12))  # This goes through y=None, shape=None branch in append_value
        assert len(cs.labels) == 2

    def test_shape_based_init(self):
        # Covers lines 67-73: shape provided to __init__
        w = W("W36X150")
        cs = CrossSection("A", shape=w)
        assert cs.area > 0

    def test_call_with_shape_no_y(self):
        # Covers line 93 (__call__ shape branch) and lines 131-143 (shape+y=None in append_value)
        w = W("W36X150")
        cs = CrossSection("A", (10, 2))
        cs("B", shape=w)
        assert len(cs.labels) == 2

    def test_append_value_shape_with_y(self):
        # Covers lines 120-126: __call__ passes axis=None, so hits else (weak-like) path
        w = W("W36X150")
        cs = CrossSection("A", (10, 2))
        cs("B", shape=w, y=5.0)
        assert len(cs.areas) == 2

    def test_append_value_shape_with_y_strong_direct(self):
        # Covers lines 115-119: direct call with axis='strong' and shape+y
        w = W("W36X150")
        cs = CrossSection("A", (10, 2))
        cs.shape = w  # set self.shape first
        cs.append_value(shape=w, y=5.0, axis='strong')
        assert len(cs.areas) == 2

    def test_append_value_shape_no_y_strong_direct(self):
        # Covers line 132: direct call with axis='strong' and shape, no y
        w = W("W36X150")
        cs = CrossSection("A", (10, 2))
        cs.shape = w  # set self.shape first
        cs.append_value(shape=w, axis='strong')
        assert len(cs.areas) == 2

    def test_negative_y_check_negative_values(self):
        # Covers line 167: check_negative_y_values returns True
        # and line 186: self.cb = extr_neg_y - self.n
        cs = CrossSection("A", (10, 4), y=-5.0)
        result = cs.check_negative_y_values()
        assert result is True
