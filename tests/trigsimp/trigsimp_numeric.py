"""Numeric evaluation for the trigsimp tests: values at points, and where an expression is defined.

An expression is *defined* at a point when every subexpression evaluates to a
finite number there (``docs/trigsimp.md``, "Soundness"): ``tan(x)*cos(x)`` is
not defined at ``x = pi/2`` although ``sin(x)`` is.  :func:`value` evaluates
bottom-up with mpmath at floating points, :func:`exact_value` with SymPy at
exact points (the poles and zeros of the trigonometric functions, which a
floating point never hits); both return ``None`` where the expression is not
defined.  :func:`holds` and :func:`holds_exact` decide a condition (a
boolean of ``Q`` facts) at a point, the same two ways.
"""
from __future__ import annotations

import random
from typing import Any

import mpmath
from sympy import (
    Abs,
    Add,
    And,
    Basic,
    Mul,
    Not,
    Number,
    NumberSymbol,
    Or,
    Pow,
    Q,
    S,
    Symbol,
    acos,
    asin,
    atan,
    atan2,
    cos,
    cosh,
    cot,
    coth,
    csc,
    csch,
    exp,
    log,
    pi,
    sec,
    sech,
    sin,
    sinh,
    tan,
    tanh,
)
from sympy.assumptions import AppliedPredicate
from sympy.core.numbers import ImaginaryUnit

DPS = 40
"""Working precision (decimal digits) of :func:`value`."""

_MP = {sin: mpmath.sin, cos: mpmath.cos, tan: mpmath.tan, cot: mpmath.cot,
       sec: mpmath.sec, csc: mpmath.csc, sinh: mpmath.sinh, cosh: mpmath.cosh,
       tanh: mpmath.tanh, coth: mpmath.coth, sech: mpmath.sech, csch: mpmath.csch,
       exp: mpmath.exp, log: mpmath.log, Abs: abs, asin: mpmath.asin, acos: mpmath.acos,
       atan: mpmath.atan}
_BAD = (S.ComplexInfinity, S.NaN, S.Infinity, S.NegativeInfinity)


def value(expr: Any, point: dict, sizes: list | None = None) -> Any:
    """``expr`` at ``point`` (symbol -> number) as an mpmath number, or ``None``
    where a subexpression is not finite (a pole, a division by zero).  The
    modulus of every subexpression's value is appended to ``sizes`` if given."""
    with mpmath.workdps(DPS):
        try:
            return _value(expr, {k: mpmath.mpmathify(v) for k, v in point.items()}, sizes)
        except (ZeroDivisionError, OverflowError, ValueError):
            return None


def _finite(v: Any) -> Any:
    if v is None or not mpmath.isfinite(v):
        return None
    return v


def _value(e: Any, point: dict, sizes: list | None) -> Any:
    v = _node(e, point, sizes)
    if sizes is not None and v is not None:
        sizes.append(abs(v))
    return v


def _node(e: Any, point: dict, sizes: list | None) -> Any:
    if isinstance(e, Symbol):
        return point[e]
    if isinstance(e, (Number, NumberSymbol, ImaginaryUnit)):
        if e in _BAD:
            return None
        return mpmath.mpmathify(complex(e)) if isinstance(e, ImaginaryUnit) else \
            mpmath.mpc(*[mpmath.mpf(str(p.evalf(DPS))) for p in e.as_real_imag()])
    args = [_value(a, point, sizes) for a in e.args]
    if any(a is None for a in args):
        return None
    if isinstance(e, Add):
        return _finite(mpmath.fsum(args))
    if isinstance(e, Mul):
        out = mpmath.mpf(1)
        for a in args:
            out *= a
        return _finite(out)
    if isinstance(e, Pow):
        base, ex = args
        if base == 0 and mpmath.re(ex) <= 0:
            return None
        return _finite(mpmath.power(base, ex))
    if e.func is atan2:          # real arguments only (SymPy's atan2 of complex numbers is not needed)
        a, b = args
        if mpmath.im(a) != 0 or mpmath.im(b) != 0 or (a == 0 and b == 0):
            return None
        return _finite(mpmath.atan2(mpmath.re(a), mpmath.re(b)))
    f = _MP.get(e.func)
    if f is not None:
        return _finite(f(args[0]))
    raise TypeError(f"no numeric evaluation for {e.func}")


def exact_value(expr: Any, point: dict) -> Any:
    """``expr`` at the exact ``point``, node by node with SymPy's evaluation,
    or ``None`` where a subexpression is infinite or undefined."""
    if not isinstance(expr, Basic) or not expr.args:
        v = point.get(expr, expr) if isinstance(expr, Symbol) else expr
        return None if v in _BAD else v
    args = [exact_value(a, point) for a in expr.args]
    if any(a is None for a in args):
        return None
    v = expr.func(*args)
    return None if v.has(*_BAD) else v


def close(a: Any, b: Any, scale: Any = 1, rel: float = 1e-20) -> bool:
    """``a`` and ``b`` agree to ``rel`` relative to ``max(1, |a|, |b|, scale)``."""
    with mpmath.workdps(DPS):
        a, b = mpmath.mpmathify(complex(a) if isinstance(a, Basic) else a), \
            mpmath.mpmathify(complex(b) if isinstance(b, Basic) else b)
        return abs(a - b) <= rel*max(1, abs(a), abs(b), scale)


def exact_close(a: Any, b: Any) -> bool:
    """Two exact SymPy numbers agree numerically (to 25 digits)."""
    d = (a - b).evalf(DPS)
    return abs(complex(d)) <= 1e-25*max(1, abs(complex(a.evalf(DPS))))


def scale(expr: Any, point: dict) -> Any:
    """The largest modulus of a subexpression's value at ``point`` (at least 1):
    what a sum that cancels to a small number is compared against."""
    sizes: list = [mpmath.mpf(1)]
    value(expr, point, sizes)
    return max(sizes)


def random_points(symbols: list, rng: random.Random, n: int) -> list[dict]:
    """``n`` points: half real (in ``(-4, 4)``), half complex (imaginary part in ``(-1, 1)``)."""
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append({s: rng.uniform(-4, 4) for s in symbols})
        else:
            out.append({s: complex(rng.uniform(-4, 4), rng.uniform(-1, 1)) for s in symbols})
    return out


SPECIAL = [S.Zero, pi/6, pi/4, pi/3, pi/2, 2*pi/3, pi, 3*pi/2, -pi/2, -pi, 2*pi]
"""Exact points at which the trigonometric functions have their zeros and poles (and some regular points)."""


# deciding a condition at a point ---------------------------------------------

_SIGNS = {Q.positive: lambda v: v > 0, Q.negative: lambda v: v < 0, Q.nonnegative: lambda v: v >= 0,
          Q.nonpositive: lambda v: v <= 0, Q.zero: lambda v: v == 0, Q.nonzero: lambda v: v != 0}
_RELATIONS = {Q.gt: Q.positive, Q.ge: Q.nonnegative, Q.lt: Q.negative, Q.le: Q.nonpositive,
              Q.eq: Q.zero, Q.ne: Q.nonzero}
MARGIN = 1e-12
"""A floating value this close to a boundary (relative to the values compared) is undecided."""


def holds(cond: Any, point: dict) -> bool | None:
    """``cond`` (``And``, ``Or``, ``Not`` of ``Q.real``, ``Q.integer``, the sign
    predicates and the relations) at a floating ``point``; ``None`` when a value is
    undefined there or too close to a boundary to tell."""
    return _decide(cond, lambda e: (value(e, point), scale(e, point)))


def holds_exact(cond: Any, point: dict) -> bool | None:
    """``cond`` at an exact ``point``: an exact zero is decided exactly, every other
    value by its numerical value to 40 digits."""
    def at(e: Any) -> tuple:
        v = exact_value(e, point)
        if v is None:
            return None, 1
        if v == 0:
            return mpmath.mpf(0), 1
        with mpmath.workdps(DPS):
            return mpmath.mpmathify(complex(v.evalf(DPS))), 1
    return _decide(cond, at)


def _decide(cond: Any, at: Any) -> bool | None:
    if cond is True or cond is S.true:
        return True
    if cond is False or cond is S.false:
        return False
    if isinstance(cond, (And, Or)):
        parts = [_decide(c, at) for c in cond.args]
        if isinstance(cond, And):
            return False if False in parts else (None if None in parts else True)
        return True if True in parts else (None if None in parts else False)
    if isinstance(cond, Not):
        inner = _decide(cond.args[0], at)
        return None if inner is None else not inner
    assert isinstance(cond, AppliedPredicate), cond
    f, args = cond.function, cond.arguments
    if f in _RELATIONS:
        f, args = _RELATIONS[f], (args[0] - args[1],)
    v, size = at(args[0])
    if v is None:
        return None
    tol = MARGIN*max(1, size)
    with mpmath.workdps(DPS):
        v = mpmath.mpmathify(v)
        im = abs(mpmath.im(v))
        if f is Q.integer:
            d = abs(v - mpmath.nint(mpmath.re(v)))
            return True if d == 0 else (None if d <= tol else False)
        if f not in _SIGNS and f is not Q.real:
            raise TypeError(f"no numeric decision for {cond}")
        if im != 0:           # not real: every predicate here implies real (Q.nonzero too)
            return None if im <= tol else False
        if f is Q.real:
            return True
        r = mpmath.re(v)
        if r != 0 and abs(r) <= tol:
            return None
        return bool(_SIGNS[f](r))
