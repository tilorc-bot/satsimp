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
Every condition is decided through ``ask`` (:mod:`satsimp.engine.backend`),
with the facts the sign table (:mod:`.rules.signs`) proves about the
trigonometric values in the question added to the assumptions (:func:`_facts`).
See ``docs/trigsimp.md``.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sympy import And, Basic, S, sympify

from satsimp.engine import backend, driver, hooks

from .rules import signs
from .wiring import HEADS, NORMALIZE, PYTHAGOREAN, SIMPLIFY, measure

__all__ = ["trigsimp"]


def _proved(condition: Any, assumptions: Any) -> bool:
    """``condition`` provable by ``ask`` alone (no facts added: no recursion)."""
    try:
        return backend.ask(condition, assumptions) is True
    except (ValueError, TypeError, AssertionError):   # inconsistent assumptions: the question itself raises
        return False


def _atom_facts(atom: Any, assumptions: Any) -> Any:
    """The facts of the sign table about ``atom`` whose condition is provable."""
    out = []
    for pattern, fact, condition in signs.ROWS:
        if pattern.func is atom.func:
            b = {signs.u: atom.args[0]}
            if _proved(condition.xreplace(b), assumptions):
                out.append(fact.xreplace(b))
    return And(*out)


def _facts(proposition: Any, assumptions: Any, cache: dict) -> Any:
    """The sign table's facts about the trigonometric values in ``proposition``
    under ``assumptions`` (remembered in ``cache`` for one trigsimp call)."""
    if not isinstance(proposition, Basic):
        return S.true
    out = []
    for atom in proposition.atoms(*signs.HEADS):
        key = (atom, assumptions)
        try:
            facts = cache[key]
        except KeyError:
            facts = cache[key] = _atom_facts(atom, assumptions)
        except TypeError:          # unhashable assumptions
            facts = _atom_facts(atom, assumptions)
        out.append(facts)
    return And(*out)


def _asker(cache: dict) -> Any:
    """trigsimp's ``ask``: the backend's, with the sign table's facts about
    the question's trigonometric values added to the assumptions (theorems
    under them, so nothing is assumed that does not hold)."""
    def ask(proposition: Any, assumptions: Any = True) -> bool | None:
        facts = _facts(proposition, assumptions, cache)
        if facts is not S.true:
            assumptions = And(assumptions, facts)
        return backend.ask(proposition, assumptions)
    return ask


def _run(handlers: dict, expr: Any, assumptions: Any, ask: Any) -> Any:
    dispatcher = SimpleNamespace(ask=ask, handlers_dict=handlers)
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
    ask = _asker({})
    best, best_m = expr, measure(expr)
    while True:      # each round's result is strictly smaller: a well-founded order
        normal = _run(NORMALIZE, best, assumptions, ask)
        out = min((_run(SIMPLIFY, normal, assumptions, ask),
                   _run(SIMPLIFY, _run(PYTHAGOREAN, normal, assumptions, ask), assumptions, ask)), key=measure)
        m = measure(out)
        if not m < best_m:
            return best
        best, best_m = out, m
