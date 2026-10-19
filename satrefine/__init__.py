"""Deprecated: satrefine is now satsimp, and refine one of its methods.

``import satrefine`` and ``satrefine.refine`` keep working for now, with a
``DeprecationWarning``: this module re-exports the top-level names it had
(``refine``, ``ask``, ``handlers_dict``, ``HANDLERS_PACKAGE``, ``DEFAULT_HANDLERS``, ``HANDLERS_ENV_VAR``,
``handlers_package``) from
:mod:`satsimp.methods.refine`.  Use ``from satsimp import refine`` instead.
Submodules (``satrefine.identities...``, ``satrefine.tools...``) are not
aliased: their new names are in the README ("Renamed from satrefine").

This alias ships in the satsimp distribution and will be removed in a later
release.
"""
from __future__ import annotations

import warnings

warnings.warn("satrefine is deprecated: it is now satsimp; use `from satsimp import refine` "
              "(refine's other names are in satsimp.methods.refine)", DeprecationWarning, stacklevel=2)

from satsimp.methods.refine import *  # noqa: E402,F401,F403
from satsimp.methods.refine import (  # noqa: E402,F401
    DEFAULT_HANDLERS,
    HANDLERS_ENV_VAR,
    HANDLERS_PACKAGE,
    __all__,
    handlers_package,
)
