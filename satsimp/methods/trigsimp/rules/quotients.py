"""Quotients of ``sin`` and ``cos`` (``sinh`` and ``cosh``) of one argument as
``tan`` and ``cot`` (``tanh`` and ``coth``).

:data:`SUBSTITUTIONS` hold to any integer power, everywhere.  :data:`RULES`
are the same quotients to any other power ``a`` (``sin(x)**y/cos(x)**y``,
``sin(x)**(5/2)/cos(x)**(5/2)``): rule rows, fired when the denominator is
provably positive, since ``s**a*c**(-a) = (s/c)**a`` for ``c > 0`` (the
principal branch: ``log(s/c) = log(s) - log(c)``) and not in general
(``sin(x)**(1/2)/cos(x)**(1/2)`` at ``x = pi``).  The two exponents bind
separately and must add up to zero; an integer exponent is left to the
substitution rows.  ``cosh(u) > 0`` for real ``u`` (:mod:`.signs`)."""
from __future__ import annotations

from sympy import Q, cos, cosh, cot, coth, sin, sinh, symbols, tan, tanh

u, a, b = symbols('u a b')

SUBSTITUTIONS = [
    (sin(u)/cos(u), tan(u), True),
    (cos(u)/sin(u), cot(u), True),
    (sinh(u)/cosh(u), tanh(u), True),
    (cosh(u)/sinh(u), coth(u), True),
]

RULES = [
    (sin(u)**a*cos(u)**b, tan(u)**a, Q.zero(a + b) & Q.positive(cos(u)), Q.integer(a)),
    (cos(u)**a*sin(u)**b, cot(u)**a, Q.zero(a + b) & Q.positive(sin(u)), Q.integer(a)),
    (sinh(u)**a*cosh(u)**b, tanh(u)**a, Q.zero(a + b) & Q.positive(cosh(u)), Q.integer(a)),
    (cosh(u)**a*sinh(u)**b, coth(u)**a, Q.zero(a + b) & Q.positive(sinh(u)), Q.integer(a)),
]
