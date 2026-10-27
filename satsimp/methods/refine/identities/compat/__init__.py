"""Code expected to change: SymPy workarounds, matrix special cases and the vendored refine
dispatcher (:mod:`.upstream`), which the engine reaches as ``satsimp.engine.hooks.dispatcher``.
Importing it plugs refine into the engine: the dispatcher, and the ``ask`` backend's
``ask_whole`` and ``ask_true`` (:mod:`satsimp.engine.backend`)."""
from typing import Any

from satsimp.engine import hooks as _hooks
from satsimp.engine import backend as _backend
from . import upstream as _upstream

_ask = _upstream.ask


def _ask_true(condition: Any, assumptions: Any) -> bool:
    """:data:`satsimp.engine.hooks.ask_true` for refine: the backend's True-only
    query (:func:`satsimp.engine.backend.ask_true`), remembered per top-level
    call beside the driver's memo of ``ask``; the full ``ask`` when
    ``upstream.ask`` is patched (a test, a recording), so the patch sees
    every query."""
    ask = _upstream.ask
    if getattr(ask, "unmemoized", ask) is not _ask:
        return ask(condition, assumptions) is True
    memo = getattr(ask, "true", None)
    if memo is None:
        return _backend.ask_true(condition, assumptions)
    return memo(condition, assumptions, _backend.ask_true)


_hooks.plug(dispatcher=_upstream, ask_whole=_backend.ask_whole, ask_true=_ask_true)
