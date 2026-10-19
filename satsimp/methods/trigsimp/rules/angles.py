"""Addition and double-angle formulas of ``sin`` and ``cos`` (``sinh`` and
``cosh``), each way round (Fu's TR8, TR10, TR10i, TR11).

:data:`CONTRACT` rows replace a product of two functions by a function of the
sum or difference of their arguments, minus the other product of the formula:
in ``sin(x)*cos(y) + cos(x)*sin(y)`` the first term becomes
``sin(x + y) - cos(x)*sin(y)``, and the second cancels.  :data:`EXPAND` rows
replace a function of a sum (``u + v`` binds one term against the rest) or
of a double argument by products.  Every row is an identity of entire
functions: no row has a pole."""
from __future__ import annotations

from sympy import cos, cosh, sin, sinh, symbols

u, v = symbols('u v')

CONTRACT = [
    (sin(u)*cos(u), sin(2*u)/2, True),
    (sin(u)**2, (1 - cos(2*u))/2, True),
    (cos(u)**2, (1 + cos(2*u))/2, True),
    (sin(u)*cos(v), sin(u + v) - cos(u)*sin(v), True),
    (sin(u)*cos(v), sin(u - v) + cos(u)*sin(v), True),
    (cos(u)*cos(v), cos(u + v) + sin(u)*sin(v), True),
    (cos(u)*cos(v), cos(u - v) - sin(u)*sin(v), True),
    (sin(u)*sin(v), cos(u - v) - cos(u)*cos(v), True),
    (sin(u)*sin(v), cos(u)*cos(v) - cos(u + v), True),
    (sinh(u)*cosh(u), sinh(2*u)/2, True),
    (sinh(u)**2, (cosh(2*u) - 1)/2, True),
    (cosh(u)**2, (cosh(2*u) + 1)/2, True),
    (sinh(u)*cosh(v), sinh(u + v) - cosh(u)*sinh(v), True),
    (sinh(u)*cosh(v), sinh(u - v) + cosh(u)*sinh(v), True),
    (cosh(u)*cosh(v), cosh(u + v) - sinh(u)*sinh(v), True),
    (cosh(u)*cosh(v), cosh(u - v) + sinh(u)*sinh(v), True),
    (sinh(u)*sinh(v), cosh(u + v) - cosh(u)*cosh(v), True),
    (sinh(u)*sinh(v), cosh(u)*cosh(v) - cosh(u - v), True),
]

EXPAND = [
    (sin(u + v), sin(u)*cos(v) + cos(u)*sin(v), True),
    (cos(u + v), cos(u)*cos(v) - sin(u)*sin(v), True),
    (sin(2*u), 2*sin(u)*cos(u), True),
    (cos(2*u), cos(u)**2 - sin(u)**2, True),
    (cos(2*u), 1 - 2*sin(u)**2, True),
    (cos(2*u), 2*cos(u)**2 - 1, True),
    (sinh(u + v), sinh(u)*cosh(v) + cosh(u)*sinh(v), True),
    (cosh(u + v), cosh(u)*cosh(v) + sinh(u)*sinh(v), True),
    (sinh(2*u), 2*sinh(u)*cosh(u), True),
    (cosh(2*u), cosh(u)**2 + sinh(u)**2, True),
    (cosh(2*u), 1 + 2*sinh(u)**2, True),
    (cosh(2*u), 2*cosh(u)**2 - 1, True),
]

SUBSTITUTIONS = CONTRACT + EXPAND
