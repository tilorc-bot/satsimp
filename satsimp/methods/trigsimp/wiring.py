"""Which handlers serve which key, for each of trigsimp's two passes.

The normalizing pass (:data:`NORMALIZE`) rewrites ``tan``, ``cot``, ``sec``
and ``csc`` (and their hyperbolic counterparts) with the rule rows of :mod:`.rules.normal`, keyed by head.  The
simplifying pass (:data:`SIMPLIFY`) serves ``Add`` and ``Mul`` with one
substitution handler (:mod:`.substitute`) over every substitution table, in
the order listed here, under :func:`measure`; the Pythagorean pre-pass
(:data:`PYTHAGOREAN`) the same way with the rows in ``sin`` and ``cos``
(``sinh`` and ``cosh``) alone (:data:`.rules.pythagorean.SINE_COSINE`).

The conditional rule rows of :mod:`.rules.moduli` and :mod:`.rules.inverses`
(:data:`CONDITIONAL`: keys ``Pow``, ``Abs``, ``asin``, ``acos``, ``atan``,
``atan2``) serve both passes, so a root or a modulus is resolved as soon as a
pass leaves its argument a square or of known sign (``sqrt(1 - sin(x)**2)``:
the simplifying pass makes ``sqrt(cos(x)**2)``, and its ``Pow`` row
``Abs(cos(x))``).  The conditional quotient rows (:data:`.rules.quotients.RULES`,
``sin(u)**a/cos(u)**a = tan(u)**a``) serve the simplifying pass only
(normalizing would write the ``tan`` they make back as ``sin/cos``), tried
on a product before its substitution rows (:func:`_first`); of those that
fire, the smallest result is kept (:func:`_smallest`).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from sympy import (
    Abs,
    Basic,
    cos,
    cosh,
    cot,
    coth,
    csc,
    csch,
    sec,
    sech,
    sin,
    sinh,
    tan,
    tanh,
)

from satsimp.engine.measure import size
from satsimp.engine.rewrite import rule_handler

from .rules import angles, inverses, moduli, normal, pythagorean, quotients
from .substitute import substitution_handler

HEADS = (sin, cos, tan, cot, sec, csc, sinh, cosh, tanh, coth, sech, csch)
"""The circular and hyperbolic heads trigsimp counts and rewrites."""


@lru_cache(maxsize=65536)
def _counts(e: Any) -> tuple[int, int, int]:
    """Trigonometric nodes, ``Abs`` nodes and all nodes of ``e`` (as
    :func:`preorder_traversal` visits them), remembered per subtree: a
    candidate shares most of its terms."""
    trig, mod, nodes = int(isinstance(e, HEADS)), int(isinstance(e, Abs)), 1
    for a in (e.args if isinstance(e, Basic) else ()):
        t, m, n = _counts(a)
        trig, mod, nodes = trig + t, mod + m, nodes + n
    return trig, mod, nodes


def trig_nodes(e: Any) -> int:
    """The first part of :func:`measure`, without ``count_ops``."""
    return _counts(e)[0]


def measure(e: Any) -> tuple[int, int, int, int]:
    """The rewrite ordering: trigonometric nodes (Fu et al.'s ``L``), then
    ``count_ops``, then ``Abs`` nodes (``-sin(x)`` is smaller than
    ``Abs(sin(x))``), then all nodes (``1/cos(x)**2`` is smaller than ``1 + tan(x)**2``)."""
    trig, mod, nodes = _counts(e)
    return trig, size(e), mod, nodes


measure.first = trig_nodes  # type: ignore[attr-defined]


def _by_head(rows: list) -> dict:
    keys: dict = {}
    for row in rows:
        keys.setdefault(row[0].func.__name__, []).append(row)
    return {key: rule_handler(rs) for key, rs in keys.items()}


def _first(*handlers: Any) -> Any:
    """A handler trying ``handlers`` in order: the first result that is not ``None``."""
    def handler(expr: Any, assumptions: Any) -> Any:
        for h in handlers:
            out = h(expr, assumptions)
            if out is not None:
                return out
        return None
    handler.handlers = handlers   # type: ignore[attr-defined]
    return handler


def _smallest(rows: list) -> Any:
    """A handler from rule rows: of the rows that fire, the smallest result
    under :func:`measure` (``cos(x)**y/sin(x)**y`` is ``cot(x)**y`` and
    ``tan(x)**(-y)`` for ``0 < x < pi/2``)."""
    handlers = [rule_handler([row]) for row in rows]

    def handler(expr: Any, assumptions: Any) -> Any:
        outs = [out for out in (h(expr, assumptions) for h in handlers) if out is not None]
        return min(outs, key=measure) if outs else None
    handler.rows = rows   # type: ignore[attr-defined]
    return handler


SUBSTITUTIONS = quotients.SUBSTITUTIONS + pythagorean.SUBSTITUTIONS + angles.SUBSTITUTIONS

CONDITIONAL = moduli.RULES + inverses.RULES
"""Conditional rule rows serving both passes, keyed by head."""

NORMALIZE: dict = _by_head(normal.RULES + CONDITIONAL)

_pythagorean = substitution_handler(pythagorean.SINE_COSINE, measure, HEADS)
PYTHAGOREAN: dict = {"Add": _pythagorean, "Mul": _pythagorean}

_substitute = substitution_handler(SUBSTITUTIONS, measure, HEADS)
SIMPLIFY: dict = {**_by_head(CONDITIONAL), "Add": _substitute,
                  "Mul": _first(_smallest(quotients.RULES), _substitute)}
