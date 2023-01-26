import unittest
from civilpy.structural.steel import SteelSection


class TestSteelMemberFunctions(unittest.TestCase):
    def test_general_import(self):
        test_bridge = SteelSection("W44X335") # Correct Name
        test_bridge2 = SteelSection("W44x335") # Lowercase correction
        test_bridge3 = SteelSection("W 44x335") # Space in label

        self.assertEqual(test_bridge, test_bridge2)  # Verify all three names imported identically
        self.assertEqual(test_bridge2, test_bridge3)


if __name__ == '__main__':
    unittest.main()
