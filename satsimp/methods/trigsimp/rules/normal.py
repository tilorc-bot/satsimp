"""``tan``, ``cot``, ``sec``, ``csc`` in terms of ``sin`` and ``cos``: the normalizing pass (Fu's TR1, TR2)."""
from __future__ import annotations

from sympy import cos, cot, csc, sec, sin, symbols, tan

u = symbols('u')

RULES = [
    (tan(u), sin(u)/cos(u), True),
    (cot(u), cos(u)/sin(u), True),
    (sec(u), 1/cos(u), True),
    (csc(u), 1/sin(u), True),
]
