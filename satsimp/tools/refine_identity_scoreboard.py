#!/usr/bin/env python
"""Old name of ``python -m satsimp.tools.scoreboard battery`` (rows, code lines, battery, fuzz); same options.

Kept for phase 3: ``python -m satsimp.tools.refine_identity_scoreboard [options]``
runs ``scoreboard battery [options]``.
"""
import sys

from satsimp.tools.scoreboard import main

if __name__ == "__main__":
    sys.exit(main(["battery", *sys.argv[1:]]))
