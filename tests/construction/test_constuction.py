#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import unittest
from civilpy.construction import test_construction


class TestConstructionModule(unittest.TestCase):
    def test_init(self):
        self.assertEqual(test_construction, True)  # add assertion here


if __name__ == "__main__":
    unittest.main()
