"""refine's own environment switch: which handler package :mod:`satsimp.methods.refine` loads.

``SATREFINE_HANDLERS``     the handler package (read once, when the method is imported).

The engine's switches (generated tables or live rows, strict loop guard, ``ask`` backend)
are in :mod:`satsimp.engine.config` and :mod:`satsimp.engine.backend`.
"""
from __future__ import annotations

import os

HANDLERS_ENV_VAR = "SATREFINE_HANDLERS"
"""Name of the handler package to load, relative to ``satsimp.methods.refine``.

Defaults to :data:`DEFAULT_HANDLERS`.  The reference implementation of the
same registry keys, ``handlers_v3`` (:mod:`satsimp.methods.refine.reference.v3`), can be
selected instead, so it can be measured with the same dispatcher, backends
and tools.  (``handlers`` and ``handlers_v2`` were removed in phase 3.)
"""

DEFAULT_HANDLERS = "handlers_identities"
"""Handler package loaded when :data:`HANDLERS_ENV_VAR` is not set."""


def handlers_package() -> str:
    """The handler package the environment selects."""
    return os.environ.get(HANDLERS_ENV_VAR, DEFAULT_HANDLERS)
