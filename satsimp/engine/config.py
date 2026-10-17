"""The engine's environment switches, in one place.

``SATSIMP_IDENTITIES``     ``generated`` (default) or ``live``: whether the driver uses the
                           generated rule tables (read on every lookup, so tests can switch it);
``SATSIMP_STRICT_LOOPS``   ``1``: a tripped termination guard raises instead of returning the
                           input unchanged (read when a guard trips).

The ``ask`` backend (``SATSIMP_BACKEND``) is chosen in :mod:`.backend`; a method's own
switches are in its package (refine's handler package: :mod:`satsimp.methods.refine.config`).
The context managers that override the two above inside a block are
:func:`.driver.live`, :func:`.driver.tables` and :func:`.guard.strict_loops`.

Every switch is read with :func:`env`: ``SATSIMP_<NAME>``, else the name it had
before the rename, ``SATREFINE_<NAME>`` (deprecated: a ``DeprecationWarning`` the
first time it is used), else the default.
"""
from __future__ import annotations

import os
import warnings

PREFIX = "SATSIMP_"
OLD_PREFIX = "SATREFINE_"
"""The prefix of the variables before the rename (satrefine -> satsimp), still read as a fallback."""

MODE_ENV_VAR = PREFIX + "IDENTITIES"

STRICT_ENV_VAR = PREFIX + "STRICT_LOOPS"

_warned: set[str] = set()


def env(name: str, default: str | None = None) -> str | None:
    """``SATSIMP_<name>``, else ``SATREFINE_<name>`` (deprecated), else ``default``."""
    value = os.environ.get(PREFIX + name)
    if value is not None:
        return value
    value = os.environ.get(OLD_PREFIX + name)
    if value is None:
        return default
    if name not in _warned:
        _warned.add(name)
        warnings.warn(f"{OLD_PREFIX}{name} is deprecated: set {PREFIX}{name} instead", DeprecationWarning,
                      stacklevel=2)
    return value


def env_setdefault(name: str, default: str) -> str:
    """``os.environ.setdefault`` for a switch: ``SATSIMP_<name>`` becomes :func:`env`'s value,
    so a value set under the old name is kept, and subprocesses read it under the new one."""
    value = env(name, default)
    os.environ[PREFIX + name] = value
    return value


def env_mode() -> str:
    """``"generated"`` (default) or ``"live"``, from ``SATSIMP_IDENTITIES``."""
    value = env("IDENTITIES", "generated")
    if value not in ("generated", "live"):
        raise ValueError(f"{MODE_ENV_VAR} must be 'generated' or 'live', not {value!r}")
    return value


def env_strict() -> bool:
    """Whether ``SATSIMP_STRICT_LOOPS`` asks a tripped guard to raise."""
    return env("STRICT_LOOPS", "") not in ("", "0")
