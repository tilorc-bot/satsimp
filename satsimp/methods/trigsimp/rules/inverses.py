"""Inverse functions of their functions on the principal ranges: rule rows,
fired when their condition is provable through ``ask``.

``asin(sin(u)) = u`` on ``[-pi/2, pi/2]``, ``acos(cos(u)) = u`` on
``[0, pi]``, ``atan(tan(u)) = u`` on ``(-pi/2, pi/2)`` and
``atan2(sin(u), cos(u)) = u`` on ``(-pi, pi]``.  The normalizing pass writes
``tan(u)`` as ``sin(u)/cos(u)`` before ``atan`` is seen, and the simplifying
pass writes it back, so ``atan`` has a row for each form.  The left sides
are defined wherever the condition holds (``tan`` has no pole inside its
interval), and so is ``u``."""
from __future__ import annotations

from sympy import Q, acos, asin, atan, atan2, cos, pi, sin, symbols, tan

u = symbols('u')

RULES = [
    (asin(sin(u)), u, Q.ge(u, -pi/2) & Q.le(u, pi/2)),
    (acos(cos(u)), u, Q.ge(u, 0) & Q.le(u, pi)),
    (atan(tan(u)), u, Q.gt(u, -pi/2) & Q.lt(u, pi/2)),
    (atan(sin(u)/cos(u)), u, Q.gt(u, -pi/2) & Q.lt(u, pi/2)),
    (atan2(sin(u), cos(u)), u, Q.gt(u, -pi) & Q.le(u, pi)),
]
