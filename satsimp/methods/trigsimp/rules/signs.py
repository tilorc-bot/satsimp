"""The sign table: what the values of ``sin``, ``cos``, ``tan``, ``cot``,
``sinh``, ``cosh`` and ``tanh`` are, on principal windows of their argument.

A row ``(atom, fact, condition)`` states that ``fact`` holds of ``atom``
wherever ``condition`` holds of its argument ``u``: ``sin(u) > 0`` when
``0 < u < pi``.  Before trigsimp asks a question, the facts whose condition
is provable (without these facts) are added to the assumptions for each such
atom in it (:func:`satsimp.methods.trigsimp._facts`), and satassume
composes them (``1 + cos(x) >= 0``, ``2*cos(x) > 0``).  The windows are the
principal ones only: no shifts by multiples of ``2*pi``.  A condition on an
interval bounds ``u`` on both sides (so ``u`` is real); the open intervals
avoid the poles of ``tan`` and ``cot``."""
from __future__ import annotations

from sympy import Q, cos, cosh, cot, pi, sin, sinh, symbols, tan, tanh

u = symbols('u')


def _between(lo, hi, lo_open=True, hi_open=True):
    return (Q.gt(u, lo) if lo_open else Q.ge(u, lo)) & (Q.lt(u, hi) if hi_open else Q.le(u, hi))


def _bounded(f, lo, hi, strict=False):
    """``f`` real and between ``lo`` and ``hi``."""
    if strict:
        return Q.real(f) & Q.gt(f, lo) & Q.lt(f, hi)
    return Q.real(f) & Q.ge(f, lo) & Q.le(f, hi)


ROWS = [
    (sin(u), _bounded(sin(u), -1, 1), Q.real(u)),
    (sin(u), Q.positive(sin(u)), _between(0, pi)),
    (sin(u), Q.nonnegative(sin(u)), _between(0, pi, False, False)),
    (sin(u), Q.negative(sin(u)), _between(-pi, 0)),
    (sin(u), Q.nonpositive(sin(u)), _between(-pi, 0, False, False)),
    (cos(u), _bounded(cos(u), -1, 1), Q.real(u)),
    (cos(u), Q.positive(cos(u)), _between(-pi/2, pi/2)),
    (cos(u), Q.nonnegative(cos(u)), _between(-pi/2, pi/2, False, False)),
    (cos(u), Q.negative(cos(u)), _between(pi/2, 3*pi/2)),
    (cos(u), Q.nonpositive(cos(u)), _between(pi/2, 3*pi/2, False, False)),
    (tan(u), Q.real(tan(u)), _between(-pi/2, pi/2)),
    (tan(u), Q.positive(tan(u)), _between(0, pi/2)),
    (tan(u), Q.nonnegative(tan(u)), _between(0, pi/2, False, True)),
    (tan(u), Q.negative(tan(u)), _between(-pi/2, 0)),
    (tan(u), Q.nonpositive(tan(u)), _between(-pi/2, 0, True, False)),
    (cot(u), Q.positive(cot(u)), _between(0, pi/2)),
    (cot(u), Q.nonnegative(cot(u)), _between(0, pi/2, True, False)),
    (cot(u), Q.negative(cot(u)), _between(-pi/2, 0)),
    (cot(u), Q.nonpositive(cot(u)), _between(-pi/2, 0, False, True)),
    (cosh(u), Q.real(cosh(u)) & Q.ge(cosh(u), 1) & Q.positive(cosh(u)), Q.real(u)),
    (sinh(u), Q.real(sinh(u)), Q.real(u)),
    (sinh(u), Q.positive(sinh(u)), Q.positive(u)),
    (sinh(u), Q.nonnegative(sinh(u)), Q.nonnegative(u)),
    (sinh(u), Q.negative(sinh(u)), Q.negative(u)),
    (sinh(u), Q.nonpositive(sinh(u)), Q.nonpositive(u)),
    (tanh(u), _bounded(tanh(u), -1, 1, strict=True), Q.real(u)),
    (tanh(u), Q.positive(tanh(u)), Q.positive(u)),
    (tanh(u), Q.nonnegative(tanh(u)), Q.nonnegative(u)),
    (tanh(u), Q.negative(tanh(u)), Q.negative(u)),
    (tanh(u), Q.nonpositive(tanh(u)), Q.nonpositive(u)),
]

HEADS = tuple(dict.fromkeys(atom.func for atom, _, _ in ROWS))
"""The heads the table states facts about."""
