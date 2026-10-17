"""The handler package and ``ask`` backend a tool runs under.

A tool run as a script sets ``SATSIMP_HANDLERS`` (``SATSIMP_BACKEND``)
before it imports :mod:`satsimp.methods.refine`.  When refine and its handler
package (or the backend) are already loaded when the tool reads its arguments,
:func:`select` runs the tool again in a fresh process with the variables set, once, and
only when what is loaded differs.
"""
from __future__ import annotations

import os
import sys


def rerun_with(handlers: str | None = None, backend: str | None = None) -> None:
    """Re-execute this process (same arguments, same pid) with the selection in the environment.

    Returns without doing anything when refine already runs the
    selected package and backend."""
    import satsimp.methods.refine as method
    from satsimp.engine import backend as _backend
    env = {}
    if handlers is not None and method.HANDLERS_PACKAGE != handlers:
        env["SATSIMP_HANDLERS"] = handlers
    if backend is not None and _backend.current() != backend:
        env["SATSIMP_BACKEND"] = backend
    if not env:
        return
    os.environ.update(env)
    main = sys.modules["__main__"]
    spec = getattr(main, "__spec__", None)
    command = ["-m", spec.name] if spec is not None else [main.__file__]
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, [sys.executable, *command, *sys.argv[1:]])


def select(handlers: str | None = None, backend: str | None = None) -> None:
    """Run this tool under ``handlers`` and ``backend`` (None: leave as is).

    If refine (:mod:`satsimp.methods.refine`) or the backend is loaded with something
    else, re-execute (see :func:`rerun_with`); then set the variables, so that
    subprocesses and a later import see them too."""
    if "satsimp.methods.refine" in sys.modules or "satsimp.engine.backend" in sys.modules:
        rerun_with(handlers=handlers, backend=backend)
    if handlers is not None:
        os.environ["SATSIMP_HANDLERS"] = handlers
    if backend is not None:
        os.environ["SATSIMP_BACKEND"] = backend


def backend_from_env(default: str = "combined") -> None:
    """Set the ``ask`` backend from ``SATSIMP_BACKEND`` (default ``combined``), as the fuzzers always did."""
    from satsimp.engine import backend, config
    backend.set_backend(config.env("BACKEND", default))
