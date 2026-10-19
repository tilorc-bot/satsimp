"""``sin(u)**2 + cos(u)**2 = 1`` and its forms with ``tan`` and ``cot``, each way round.

:data:`SINE_COSINE` are the rows in ``sin`` and ``cos`` alone, which the
Pythagorean pre-pass applies to the normalized expression before any row
writes a ``tan`` or ``cot`` (:mod:`..wiring`)."""
from __future__ import annotations

from sympy import cos, cot, sin, symbols, tan

u = symbols('u')

SINE_COSINE = [
    (sin(u)**2, 1 - cos(u)**2, True),
    (cos(u)**2, 1 - sin(u)**2, True),
]

SUBSTITUTIONS = SINE_COSINE + [
    (cos(u)**-2, 1 + tan(u)**2, True),
    (sin(u)**-2, 1 + cot(u)**2, True),
    (tan(u)**2, cos(u)**-2 - 1, True),
    (cot(u)**2, sin(u)**-2 - 1, True),
]
