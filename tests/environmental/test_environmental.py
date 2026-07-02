#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import unittest
from civilpy.environmental import test_environmental


class TestEnvironmentalModule(unittest.TestCase):
    def test_init(self):
        self.assertEqual(test_environmental, True)  # add assertion here


if __name__ == "__main__":
    unittest.main()
