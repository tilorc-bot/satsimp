"""The engine's environment switches, in one place.

``SATREFINE_IDENTITIES``   ``generated`` (default) or ``live``: whether the driver uses the
                           generated rule tables (read on every lookup, so tests can switch it);
``SATREFINE_STRICT_LOOPS`` ``1``: a tripped termination guard raises instead of returning the
                           input unchanged (read when a guard trips).

The ``ask`` backend (``SATREFINE_BACKEND``) is chosen in :mod:`.backend`; a method's own
switches are in its package (refine's handler package: :mod:`satsimp.methods.refine.config`).
The context managers that override the two above inside a block are
:func:`.driver.live`, :func:`.driver.tables` and :func:`.guard.strict_loops`.
"""
from __future__ import annotations

import os

MODE_ENV_VAR = "SATREFINE_IDENTITIES"

STRICT_ENV_VAR = "SATREFINE_STRICT_LOOPS"


def env_mode() -> str:
    """``"generated"`` (default) or ``"live"``, from ``SATREFINE_IDENTITIES``."""
    value = os.environ.get(MODE_ENV_VAR, "generated")
    if value not in ("generated", "live"):
        raise ValueError(f"{MODE_ENV_VAR} must be 'generated' or 'live', not {value!r}")
    return value


def env_strict() -> bool:
    """Whether ``SATREFINE_STRICT_LOOPS`` asks a tripped guard to raise."""
    return os.environ.get(STRICT_ENV_VAR, "") not in ("", "0")
