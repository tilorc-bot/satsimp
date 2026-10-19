"""Numeric evaluation for the trigsimp tests: values at points, and where an expression is defined.

An expression is *defined* at a point when every subexpression evaluates to a
finite number there (``docs/trigsimp.md``, "Soundness"): ``tan(x)*cos(x)`` is
not defined at ``x = pi/2`` although ``sin(x)`` is.  :func:`value` evaluates
bottom-up with mpmath at floating points, :func:`exact_value` with SymPy at
exact points (the poles and zeros of the trigonometric functions, which a
floating point never hits); both return ``None`` where the expression is not
defined.
"""
from __future__ import annotations

import random
from typing import Any

import mpmath
from sympy import (
    Add,
    Basic,
    Mul,
    Number,
    NumberSymbol,
    Pow,
    S,
    Symbol,
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
from sympy.core.numbers import ImaginaryUnit

DPS = 40
"""Working precision (decimal digits) of :func:`value`."""

_MP = {sin: mpmath.sin, cos: mpmath.cos, tan: mpmath.tan, cot: mpmath.cot,
       sec: mpmath.sec, csc: mpmath.csc, sinh: mpmath.sinh, cosh: mpmath.cosh,
       tanh: mpmath.tanh, coth: mpmath.coth, sech: mpmath.sech, csch: mpmath.csch,
       exp: mpmath.exp, log: mpmath.log}
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
