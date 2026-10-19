"""Quotients of ``sin`` and ``cos`` of one argument as ``tan`` and ``cot`` (to any integer power)."""
from __future__ import annotations

from sympy import cos, cot, sin, symbols, tan

u = symbols('u')

SUBSTITUTIONS = [
    (sin(u)/cos(u), tan(u), True),
    (cos(u)/sin(u), cot(u), True),
]
