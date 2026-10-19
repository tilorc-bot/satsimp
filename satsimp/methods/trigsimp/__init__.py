"""trigsimp: trigonometric simplification as rule tables (``satsimp.trigsimp`` is :func:`trigsimp`).

Passes of the engine's driver, each with its own hooks
(:func:`satsimp.engine.hooks.installed`; refine's are not read or changed):
the normalizing pass writes ``tan``, ``cot``, ``sec`` and ``csc`` with
``sin`` and ``cos``, the simplifying pass applies the substitution rows
wherever they make a sum or product smaller under :func:`.wiring.measure`,
once with every row and once after a pass with the Pythagorean rows alone
(the quotient rows, applied to a term first, can hide a Pythagorean sum:
``tan(x)**2 - sin(x)**2*tan(x)**2``); the smaller result is kept.  The
passes are repeated on the result while it gets smaller (a Pythagorean row
can leave ``cos(x)**2*tan(x)**2``, which normalizing makes ``sin(x)**2``).
The result is returned when it is smaller than the input, else the input.
Every condition is decided through ``ask`` (:mod:`satsimp.engine.backend`).
See ``docs/trigsimp.md``.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sympy import Basic, sympify

from satsimp.engine import backend, driver, hooks

from .wiring import HEADS, NORMALIZE, PYTHAGOREAN, SIMPLIFY, measure

__all__ = ["trigsimp"]


def _ask(proposition: Any, assumptions: Any = True) -> bool | None:
    return backend.ask(proposition, assumptions)


def _run(handlers: dict, expr: Any, assumptions: Any) -> Any:
    dispatcher = SimpleNamespace(ask=_ask, handlers_dict=handlers)
    with hooks.installed(dispatcher=dispatcher, ask_whole=backend.ask_whole, eval_method=None):
        return driver.refine(expr, assumptions)  # boundary: satsimp's own driver


def trigsimp(expr: Any, assumptions: Any = True) -> Any:
    """Simplify the trigonometric functions in ``expr`` under ``assumptions``
    (a boolean of ``Q`` facts): the result equals ``expr`` wherever ``expr``
    is defined and the assumptions hold, and it is ``expr`` itself unless it is
    smaller (fewer trigonometric functions, then fewer operations)."""
    expr = sympify(expr)
    if not isinstance(expr, Basic) or not expr.has(*HEADS):
        return expr
    best, best_m = expr, measure(expr)
    while True:      # each round's result is strictly smaller: a well-founded order
        normal = _run(NORMALIZE, best, assumptions)
        out = min((_run(SIMPLIFY, normal, assumptions),
                   _run(SIMPLIFY, _run(PYTHAGOREAN, normal, assumptions), assumptions)), key=measure)
        m = measure(out)
        if not m < best_m:
            return best
        best, best_m = out, m
