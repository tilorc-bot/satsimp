#!/usr/bin/env python
"""Moved to ``satsimp/tools/refine_fuzz.py``: run ``python -m satsimp.tools.refine_fuzz``.

This shim (kept for phase 3) runs that file as a script with the same arguments.
Imported as a module (``tools/ask_fuzz.py`` does), it gives the fuzzer's
vocabulary, grammar and numeric check from ``satsimp.tools.lib``."""
import os
import runpy
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository root
if __name__ == "__main__":
    sys.path[0] = _ROOT                                                 # not tools/
    runpy.run_path(os.path.join(_ROOT, "satsimp", "tools", "refine_fuzz.py"), run_name="__main__")
else:
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from satsimp.tools.lib.assumptions import *  # noqa: F401,F403,E402
    from satsimp.tools.lib.grammar import *  # noqa: F401,F403,E402
    from satsimp.tools.lib.numeric import *  # noqa: F401,F403,E402
