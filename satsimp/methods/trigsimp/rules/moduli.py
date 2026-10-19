"""Moduli and square roots of squares, by the sign of what is inside: rule
rows, fired when their condition is provable through ``ask`` (with the sign
table's facts, :mod:`.signs`).

``sqrt(w**2) = Abs(w)``, and ``1/sqrt(w**2) = sqrt(1/w**2) = 1/Abs(w)``,
for real ``w``; ``Abs(w) = w`` for ``w >= 0`` and ``-w`` for ``w <= 0``.
Each side is defined where the other is (``1/Abs(w)`` has the pole at
``w = 0`` that ``1/sqrt(w**2)`` has)."""
from __future__ import annotations

from sympy import Abs, Q, Rational, sqrt, symbols

w = symbols('w')

RULES = [
    (sqrt(w**2), Abs(w), Q.real(w)),
    ((w**2)**Rational(-1, 2), 1/Abs(w), Q.real(w)),
    (sqrt(w**-2), 1/Abs(w), Q.real(w)),
    (Abs(w), w, Q.nonnegative(w)),
    (Abs(w), -w, Q.nonpositive(w)),
]
