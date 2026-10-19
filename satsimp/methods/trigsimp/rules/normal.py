"""``tan``, ``cot``, ``sec``, ``csc`` in terms of ``sin`` and ``cos``, and
``tanh``, ``coth``, ``sech``, ``csch`` in terms of ``sinh`` and ``cosh``: the
normalizing pass (Fu's TR1, TR2)."""
from __future__ import annotations

from sympy import (
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
    symbols,
    tan,
    tanh,
)

u = symbols('u')

RULES = [
    (tan(u), sin(u)/cos(u), True),
    (cot(u), cos(u)/sin(u), True),
    (sec(u), 1/cos(u), True),
    (csc(u), 1/sin(u), True),
    (tanh(u), sinh(u)/cosh(u), True),
    (coth(u), cosh(u)/sinh(u), True),
    (sech(u), 1/cosh(u), True),
    (csch(u), 1/sinh(u), True),
]
