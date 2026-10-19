"""Soundness fuzz and termination of trigsimp (``docs/trigsimp.md``, "Soundness", "Test plan").

Random small trigonometric expressions (``sin``, ..., ``csc`` and, less
often, ``sinh``, ``cosh``, ``tanh``, ``sech`` of ``x``, ``y``, ``x + y``,
``2*x``, ``x - y``, ``x/2``; rational coefficients; integer powers up to 4 in
magnitude; sums of such terms, partly built to contain Pythagorean sums,
quotients and angle formulas so that the rows fire; now and then divided by
another term, squared or wrapped in ``sin``), with a fixed seed.  For each:

* the result agrees with the input at random real and complex points where
  the input is defined, relative to the largest subexpression value (a sum
  that cancels is compared against its terms), and is defined there;
* at exact points (zeros and poles of the trigonometric functions) where the
  input is defined, the result is defined and equal: no point is lost;
* the result is never larger than the input by trigsimp's measure, and
  strictly smaller when it is not the input;
* the call terminates without tripping the engine's guard (strict mode raises).

The same under assumptions on ``x`` (``0 < x < pi/2``, ``-pi/2 < x < 0``,
``0 < x < pi``, ``x`` real) at points satisfying them, with the
expressions also wrapped in what the conditional rows rewrite: ``Abs``,
square roots of squares, inverse functions of functions of ``x``, quotients
to a symbolic or fractional power.
"""
from __future__ import annotations

import random

import pytest
from sympy import (
    Abs,
    I,
    Q,
    Rational,
    S,
    acos,
    asin,
    atan,
    atan2,
    cos,
    cosh,
    cot,
    csc,
    expand,
    pi,
    sec,
    sech,
    sin,
    sinh,
    sqrt,
    symbols,
    tan,
    tanh,
)
from trigsimp_numeric import (
    SPECIAL,
    close,
    exact_close,
    exact_value,
    random_points,
    scale,
    value,
)

from satsimp import trigsimp
from satsimp.engine.guard import strict_loops
from satsimp.methods.trigsimp.wiring import measure

x, y = symbols('x y')
ARGS = [x, y, x + y, 2*x, x - y, x/2]
HEADS = [sin, cos, tan, cot, sec, csc, sin, cos, sinh, cosh, tanh, sech]
COEFFS = [1, 1, 1, -1, 2, -2, 3, Rational(1, 2), Rational(-3, 4), 5]
EXPONENTS = [1, 1, 2, 2, 3, 4, -1, -2, -3, -4]

CHUNKS = 8
PER_CHUNK = 40
SEED = 20261019


def _term(rng: random.Random):
    t = rng.choice(COEFFS)
    for _ in range(rng.randint(1, 3)):
        arg = rng.choice(ARGS[:4] if rng.random() < .8 else ARGS)
        t *= rng.choice(HEADS)(arg)**rng.choice(EXPONENTS)
    return t


def _identity_piece(rng: random.Random):
    """A sum or product a row applies to, times a coefficient and maybe a term, expanded."""
    u = rng.choice(ARGS[:4])
    pieces = [sin(u)**2 + cos(u)**2, 1 + tan(u)**2, 1 + cot(u)**2, sec(u)**2 - tan(u)**2,
              csc(u)**2 - cot(u)**2, 1 - sin(u)**2, 1 - cos(u)**2, sin(u)/cos(u), cos(u)*tan(u),
              sin(u)*cot(u), cosh(u)**2 - sinh(u)**2, 1 - tanh(u)**2, sinh(u)/cosh(u)]
    v = rng.choice(ARGS[:4])
    pieces += [sin(u)*cos(v) + cos(u)*sin(v), cos(u)*cos(v) - sin(u)*sin(v), sin(u + v) + sin(u - v),
               cos(u)**2 - sin(u)**2, 2*sin(u)*cos(u), sinh(u)*cosh(v) - cosh(u)*sinh(v),
               cosh(u + v) - cosh(u - v), 2*cosh(u)**2 - 1]
    factor = _term(rng) if rng.random() < .5 else 1
    return expand(rng.choice(COEFFS)*factor*rng.choice(pieces)**rng.choice([1, 1, 2]))


def random_expression(rng: random.Random):
    e = sum(_term(rng) if rng.random() < .5 else _identity_piece(rng) for _ in range(rng.randint(1, 4)))
    r = rng.random()
    if r < .1:
        e = e/(_term(rng) + rng.choice(COEFFS))
    elif r < .2:
        e = e**2
    elif r < .25 and e.has(x):
        e = sin(e)
    return e


def _check(e, rng: random.Random) -> list[str]:
    with strict_loops():
        r = trigsimp(e)
    problems = []
    if measure(r) > measure(e) or (r != e and not measure(r) < measure(e)):
        problems.append(f"not smaller: {e} -> {r} ({measure(e)} -> {measure(r)})")
    for point in random_points([x, y], rng, 6):
        ve = value(e, point)
        if ve is None:
            continue
        vr = value(r, point)
        if vr is None or not close(ve, vr, scale(e, point), rel=1e-25):
            problems.append(f"value: {e} -> {r} at {point}: {ve} vs {vr}")
            break
    for sx in rng.sample(SPECIAL + [I*pi/2, I*pi], 3):
        point = {x: sx, y: Rational(1, 3)}
        ve = exact_value(e, point)
        if ve is None:
            continue
        vr = exact_value(r, point)
        if vr is None or not exact_close(ve, vr):
            problems.append(f"exact point: {e} -> {r} at {point}: {ve} vs {vr}")
            break
    return problems


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_soundness_fuzz(chunk):
    rng = random.Random(SEED + chunk)
    problems = []
    for _ in range(PER_CHUNK):
        problems += _check(random_expression(rng), rng)
    assert not problems, "\n".join(problems)


def test_fuzz_exercises_the_rows():
    """Most generated expressions are rewritten: the fuzz tests the rows, not the identity map."""
    rng = random.Random(SEED)
    exprs = [random_expression(rng) for _ in range(60)]
    changed = sum(trigsimp(e) != e for e in exprs)
    assert changed >= 30


def test_idempotent_on_its_results():
    """A result is a fixed point: each call repeats its passes until they make nothing smaller."""
    rng = random.Random(SEED + 100)
    for _ in range(40):
        r = trigsimp(random_expression(rng))
        assert trigsimp(r) == r


# with assumptions ----------------------------------------------------------------

ASSUMPTIONS = [
    # (assumptions, how a random x satisfying them is drawn, exact x satisfying them)
    (Q.gt(x, 0) & Q.lt(x, pi/2), lambda rng: rng.uniform(1e-6, 1.5707), [pi/6, pi/4, pi/3]),
    (Q.gt(x, -pi/2) & Q.lt(x, 0), lambda rng: rng.uniform(-1.5707, -1e-6), [-pi/6, -pi/4, -pi/3]),
    (Q.gt(x, 0) & Q.lt(x, pi), lambda rng: rng.uniform(1e-6, 3.1415), [pi/6, pi/2, 2*pi/3, 3*pi/4]),
    (Q.real(x), lambda rng: rng.uniform(-6, 6), SPECIAL),
]
A_CHUNKS = 8
A_PER_CHUNK = 25
X_ARGS = [x, 2*x, x/2, -x, x + pi/2]


def _wrapped(rng: random.Random):
    """What a conditional row rewrites, with a function of ``x`` inside."""
    u = rng.choice(X_ARGS)
    f = rng.choice([sin, cos, tan, sinh, cosh])
    inner = rng.choice([f(u), f(u) + rng.choice(COEFFS), rng.choice(COEFFS)*f(u)*rng.choice([sin, cos])(u),
                        1 - sin(u)**2, 1 - cos(u)**2, 1 + tan(u)**2, cosh(u)**2 - 1])
    p = rng.choice([y, S.Half, Rational(5, 2), -Rational(1, 3), y + 1])
    return rng.choice([Abs(inner), sqrt(inner**2), sqrt(inner), 1/sqrt(inner), asin(sin(u)), acos(cos(u)),
                       atan(tan(u)), atan2(sin(u), cos(u)), sin(u)**p/cos(u)**p, cos(u)**p/sin(u)**p,
                       sinh(u)**p/cosh(u)**p, tan(u)**p, Abs(sin(u))*Abs(cos(u))])


def random_assumed_expression(rng: random.Random):
    e = sum(_wrapped(rng) if rng.random() < .6 else
            (_term(rng) if rng.random() < .5 else _identity_piece(rng)) for _ in range(rng.randint(1, 3)))
    if rng.random() < .15:
        e = _wrapped(rng)*e
    return e


def _check_assumed(e, assumptions, draw, exact, rng: random.Random) -> list[str]:
    with strict_loops():
        r = trigsimp(e, assumptions)
    problems = []
    if measure(r) > measure(e) or (r != e and not measure(r) < measure(e)):
        problems.append(f"not smaller: {e} -> {r} under {assumptions}")
    for i in range(6):
        point = {x: draw(rng), y: rng.uniform(-3, 3) if i % 2 == 0 else complex(rng.uniform(-3, 3), rng.uniform(-1, 1))}
        ve = value(e, point)
        if ve is None:
            continue
        vr = value(r, point)
        if vr is None or not close(ve, vr, scale(e, point), rel=1e-25):
            problems.append(f"value: {e} -> {r} under {assumptions} at {point}: {ve} vs {vr}")
            break
    for sx in rng.sample(exact, min(3, len(exact))):
        point = {x: sx, y: Rational(1, 3)}
        ve = exact_value(e, point)
        if ve is None:
            continue
        vr = exact_value(r, point)
        if vr is None or not exact_close(ve, vr):
            problems.append(f"exact point: {e} -> {r} under {assumptions} at {point}: {ve} vs {vr}")
            break
    return problems


@pytest.mark.parametrize("chunk", range(A_CHUNKS))
def test_soundness_fuzz_with_assumptions(chunk):
    rng = random.Random(SEED + 1000 + chunk)
    problems = []
    for k in range(A_PER_CHUNK):
        assumptions, draw, exact = ASSUMPTIONS[(chunk + k) % len(ASSUMPTIONS)]
        problems += _check_assumed(random_assumed_expression(rng), assumptions, draw, exact, rng)
    assert not problems, "\n".join(problems)


def test_fuzz_with_assumptions_exercises_the_conditional_rows():
    """Most wrapped expressions are rewritten under assumptions, and fewer without."""
    rng = random.Random(SEED + 2000)
    exprs = [(_wrapped(rng), ASSUMPTIONS[i % len(ASSUMPTIONS)][0]) for i in range(60)]
    assumed = sum(trigsimp(e, a) != e for e, a in exprs)
    bare = sum(trigsimp(e) != e for e, _ in exprs)
    assert assumed >= 30 and assumed > bare + 10, (assumed, bare)
