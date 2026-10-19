"""Soundness fuzz and termination of trigsimp (``docs/trigsimp.md``, "Soundness", "Test plan").

Random small trigonometric expressions (``sin``, ..., ``csc`` of ``x``,
``y``, ``x + y``, ``2*x``, ``x - y``, ``x/2``; rational coefficients; integer
powers up to 4 in magnitude; sums of such terms, partly built to contain
Pythagorean sums and quotients so that the rows fire; now and then divided by
another term, squared or wrapped in ``sin``), with a fixed seed.  For each:

* the result agrees with the input at random real and complex points where
  the input is defined, relative to the largest subexpression value (a sum
  that cancels is compared against its terms), and is defined there;
* at exact points (zeros and poles of the trigonometric functions) where the
  input is defined, the result is defined and equal: no point is lost;
* the result is never larger than the input by trigsimp's measure, and
  strictly smaller when it is not the input;
* the call terminates without tripping the engine's guard (strict mode raises).
"""
from __future__ import annotations

import random

import pytest
from sympy import Rational, cos, cot, csc, expand, sec, sin, symbols, tan
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
HEADS = [sin, cos, tan, cot, sec, csc]
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
              sin(u)*cot(u)]
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
    for sx in rng.sample(SPECIAL, 3):
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
