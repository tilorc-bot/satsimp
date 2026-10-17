"""Offline: satsimp's tools (scoreboard, differential, fuzz, oracle, ablation, generation, gates, satassume bump).

Run as ``python -m satsimp.tools.<name>``; refine never imports this package.
What the tools share is in :mod:`satsimp.tools.lib`.
"""
from satsimp.tools.lib.select import rerun_with  # noqa: F401  (kept for callers of the old place)
