#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Ohio-specific civil engineering tools.

Contains ODOT bridge-inventory access (TIMS, AssetWise), plan-set utilities,
SNBI validation models, and the :mod:`civilpy.state.ohio.DOT` subpackage.
"""

test_state_ohio = True

# ``civilpy.state.ohio.dot`` is an alias for the ``DOT`` subpackage.  It is
# registered rather than written as a dot.py module because a file named
# dot.py sitting beside the DOT/ package resolves ambiguously on
# case-insensitive filesystems -- i.e. on the Windows boxes that run Rhino
# and Civil NX, which is exactly where this import gets used.
import sys as _sys

from civilpy.state.ohio import DOT as dot  # noqa: E402,F401

_sys.modules.setdefault(__name__ + ".dot", dot)
