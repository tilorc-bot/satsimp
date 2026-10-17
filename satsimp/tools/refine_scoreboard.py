#!/usr/bin/env python
"""Old name of ``python -m satsimp.tools.scoreboard suite`` (a test suite under each ask backend); same options.

Kept for phase 3: ``python -m satsimp.tools.refine_scoreboard [options]``
runs ``scoreboard suite [options]``.
"""
import sys

from satsimp.tools.scoreboard import main

if __name__ == "__main__":
    sys.exit(main(["suite", *sys.argv[1:]]))
