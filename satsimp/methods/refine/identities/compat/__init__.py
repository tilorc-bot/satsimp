"""Code expected to change: SymPy workarounds, matrix special cases and the vendored refine
dispatcher (:mod:`.upstream`), which the engine reaches as ``satsimp.engine.hooks.dispatcher``.
Importing it plugs refine into the engine: the dispatcher, and the ``ask`` backend's
``ask_whole`` (:mod:`satsimp.engine.backend`)."""
from satsimp.engine import hooks as _hooks
from satsimp.engine import backend as _backend
from . import upstream as _upstream

_hooks.plug(dispatcher=_upstream, ask_whole=_backend.ask_whole)
