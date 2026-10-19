"""Which handlers serve which key, for each of trigsimp's two passes.

The normalizing pass (:data:`NORMALIZE`) rewrites ``tan``, ``cot``, ``sec``
and ``csc`` (and their hyperbolic counterparts) with the rule rows of :mod:`.rules.normal`, keyed by head.  The
simplifying pass (:data:`SIMPLIFY`) serves ``Add`` and ``Mul`` with one
substitution handler (:mod:`.substitute`) over every substitution table, in
the order listed here, under :func:`measure`; the Pythagorean pre-pass
(:data:`PYTHAGOREAN`) the same way with the rows in ``sin`` and ``cos``
(``sinh`` and ``cosh``) alone (:data:`.rules.pythagorean.SINE_COSINE`).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from sympy import (
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

from .rules import angles, normal, pythagorean, quotients
from .substitute import substitution_handler

HEADS = (sin, cos, tan, cot, sec, csc, sinh, cosh, tanh, coth, sech, csch)
"""The circular and hyperbolic heads trigsimp counts and rewrites."""


@lru_cache(maxsize=65536)
def _counts(e: Any) -> tuple[int, int]:
    """Trigonometric nodes and all nodes of ``e`` (as :func:`preorder_traversal`
    visits them), remembered per subtree: a candidate shares most of its terms."""
    trig, nodes = int(isinstance(e, HEADS)), 1
    for a in (e.args if isinstance(e, Basic) else ()):
        t, n = _counts(a)
        trig, nodes = trig + t, nodes + n
    return trig, nodes


def trig_nodes(e: Any) -> int:
    """The first part of :func:`measure`, without ``count_ops``."""
    return _counts(e)[0]


def measure(e: Any) -> tuple[int, int, int]:
    """The rewrite ordering: trigonometric nodes (Fu et al.'s ``L``), then
    ``count_ops``, then all nodes (``1/cos(x)**2`` is smaller than ``1 + tan(x)**2``)."""
    trig, nodes = _counts(e)
    return trig, size(e), nodes


measure.first = trig_nodes  # type: ignore[attr-defined]


def _by_head(rows: list) -> dict:
    keys: dict = {}
    for row in rows:
        keys.setdefault(row[0].func.__name__, []).append(row)
    return {key: rule_handler(rs) for key, rs in keys.items()}


SUBSTITUTIONS = quotients.SUBSTITUTIONS + pythagorean.SUBSTITUTIONS + angles.SUBSTITUTIONS

NORMALIZE: dict = _by_head(normal.RULES)

_pythagorean = substitution_handler(pythagorean.SINE_COSINE, measure, HEADS)
PYTHAGOREAN: dict = {"Add": _pythagorean, "Mul": _pythagorean}

_substitute = substitution_handler(SUBSTITUTIONS, measure, HEADS)
SIMPLIFY: dict = {"Add": _substitute, "Mul": _substitute}
