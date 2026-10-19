"""Strict input: facts only as Q facts (``satsimp.refine(..., strict=True)``,
``satsimp.trigsimp(..., strict=True)``).

By default the assumptions a symbol was declared with count: SymPy's
constructors evaluate with them before refine sees the input (for a positive
``x``, ``sqrt(x**2)`` is already ``x``), and satassume's symbol template reads
``assumptions0``, the closure SymPy's old assumption system computes from the
declaration.  An undefined function declared with assumptions
(``Function('f', real=True)``) has no template, but SymPy's constructors read its
assumptions the same way (``conjugate(f(y))`` is ``f(y)``).

:func:`check_strict` rejects such input: it raises :class:`AssumptionSymbolError`
(a ``ValueError``) naming every ``Symbol``, ``Dummy``, ``Wild`` (bound ones
included) or ``IndexedBase`` with an assumption other than ``commutative=True``,
and every applied undefined function, or ``Function`` subclass defined outside
SymPy, whose class has one.  Anything that is not a SymPy object (``True`` as the
assumptions, a number) is skipped.

Both are satassume's own (``satassume.sympy_api``, satassume#178), not a copy:
``refine(..., strict=True)`` and ``ask(..., strict=True)`` reject the same input
with the same exception class, so one ``except`` catches either.  Strict mode sees
only what survives construction (``p > 0`` is already ``S.true`` for a positive
``p``): a front end must build its input from plain symbols itself.
"""
from __future__ import annotations

from satassume.sympy_api import AssumptionSymbolError, check_strict

__all__ = ["AssumptionSymbolError", "check_strict"]
