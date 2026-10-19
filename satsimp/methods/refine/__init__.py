"""refine: SymPy's ``refine(expr, assumptions)`` as rule tables (``satsimp.refine`` is :data:`refine`).

The vendored dispatcher and initial handlers live in
:mod:`satsimp.methods.refine.identities.compat.upstream`; the handler package selected
with ``SATSIMP_HANDLERS`` (default ``handlers_identities``; the reference
``handlers_v3``) registers its handlers into ``handlers_dict`` when this
package is imported.  The vendored upstream handlers (``refine_abs``, ``refine_Pow``, ...)
ask SymPy's assumption system and are not exported; they stay importable from that
module for SymPy's own test suite.  The machinery the handlers run on is :mod:`satsimp.engine`.
"""
from __future__ import annotations

import importlib
import pkgutil

from .identities.compat.upstream import ask, handlers_dict, refine

__all__ = ["ask", "handlers_dict", "refine"]


from .config import DEFAULT_HANDLERS, HANDLERS_ENV_VAR, handlers_package  # noqa: E402,F401  (re-exported)

HANDLERS_PACKAGE = handlers_package()
"""Name of the handler package this process loaded (fixed at import)."""


def _load_handlers() -> None:
    """Import every public module in the selected handler package."""
    package = importlib.import_module(__name__ + "." + HANDLERS_PACKAGE)
    path = getattr(package, "__path__", None)
    if path is None:
        return
    for info in pkgutil.iter_modules(path):
        if not info.name.startswith("_"):
            importlib.import_module(f"{package.__name__}.{info.name}")


_load_handlers()
