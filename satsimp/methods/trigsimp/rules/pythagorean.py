"""``sin(u)**2 + cos(u)**2 = 1`` and ``cosh(u)**2 - sinh(u)**2 = 1``, and
their forms with ``tan`` and ``cot`` (``tanh`` and ``coth``), each way round.

:data:`SINE_COSINE` are the rows in ``sin`` and ``cos`` (``sinh`` and
``cosh``) alone, which the Pythagorean pre-pass applies to the normalized
expression before any row writes a ``tan`` or ``cot`` (:mod:`..wiring`)."""
from __future__ import annotations

from sympy import cos, cosh, cot, coth, sin, sinh, symbols, tan, tanh

u = symbols('u')

SINE_COSINE = [
    (sin(u)**2, 1 - cos(u)**2, True),
    (cos(u)**2, 1 - sin(u)**2, True),
    (sinh(u)**2, cosh(u)**2 - 1, True),
    (cosh(u)**2, 1 + sinh(u)**2, True),
]

SUBSTITUTIONS = SINE_COSINE + [
    (cos(u)**-2, 1 + tan(u)**2, True),
    (sin(u)**-2, 1 + cot(u)**2, True),
    (tan(u)**2, cos(u)**-2 - 1, True),
    (cot(u)**2, sin(u)**-2 - 1, True),
    (cosh(u)**-2, 1 - tanh(u)**2, True),
    (sinh(u)**-2, coth(u)**2 - 1, True),
    (tanh(u)**2, 1 - cosh(u)**-2, True),
    (coth(u)**2, 1 + sinh(u)**-2, True),
]
