"""Quotients of ``sin`` and ``cos`` (``sinh`` and ``cosh``) of one argument as
``tan`` and ``cot`` (``tanh`` and ``coth``), to any integer power."""
from __future__ import annotations

from sympy import cos, cosh, cot, coth, sin, sinh, symbols, tan, tanh

u = symbols('u')

SUBSTITUTIONS = [
    (sin(u)/cos(u), tan(u), True),
    (cos(u)/sin(u), cot(u), True),
    (sinh(u)/cosh(u), tanh(u), True),
    (cosh(u)/sinh(u), coth(u), True),
]
