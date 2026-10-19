"""Every row of trigsimp's tables, checked numerically (``docs/trigsimp.md``, "Soundness").

A row ``(lhs, rhs, condition)`` must state an identity, and its right side
must be defined exactly where its left side is: defined wherever the left
side is (a rewrite never loses a point), and not defined where the left side
is not (a row never removes a pole: ``tan(u) -> sin(u)/cos(u)`` keeps the
pole at ``pi/2``).  Every row of the core holds everywhere (condition
``True``), so both are checked at random real and complex points and at the
exact zeros and poles of the trigonometric functions, with ``u`` also a
shifted or scaled argument.
"""
from __future__ import annotations

import random

import pytest
from sympy import I, Rational, S, Symbol, cos, pi, sin, symbols, tan
from trigsimp_numeric import (
    SPECIAL,
    close,
    exact_close,
    exact_value,
    random_points,
    value,
)

from satsimp.methods.trigsimp import wiring
from satsimp.methods.trigsimp.rules import normal, pythagorean, quotients
from satsimp.methods.trigsimp.substitute import _pattern

ROWS = [("normal", row) for row in normal.RULES] + \
       [("quotients", row) for row in quotients.SUBSTITUTIONS] + \
       [("pythagorean", row) for row in pythagorean.SUBSTITUTIONS]
IDS = [f"{family}: {row[0]} -> {row[1]}" for family, row in ROWS]

t = Symbol('t')
ARGUMENTS = [t, 2*t, t + pi/7, -t]
"""What the pattern symbol is bound to: the row holds for every argument."""


def _symbols(row):
    return sorted(row[0].free_symbols | row[1].free_symbols, key=str)


def test_every_wired_row_is_checked():
    wired = [row for family in (normal.RULES, wiring.SUBSTITUTIONS) for row in family]
    assert sorted(map(str, wired)) == sorted(str(row) for _, row in ROWS)
    assert all(row in pythagorean.SUBSTITUTIONS for row in pythagorean.SINE_COSINE)


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_shape(family, row):
    lhs, rhs, cond = row
    assert cond is True or cond == S.true, "the core's rows hold everywhere"
    assert rhs.free_symbols <= lhs.free_symbols, "the right side binds nothing new"
    if family != "normal":
        _pattern(lhs)        # a monomial of integer powers (raises otherwise)


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_identity(family, row):
    lhs, rhs, _ = row
    rng = random.Random(f"identity {lhs} {rhs}")
    (u,) = _symbols(row)
    for arg in ARGUMENTS:
        l, r = lhs.xreplace({u: arg}), rhs.xreplace({u: arg})
        for point in random_points([t], rng, 20):
            vl, vr = value(l, point), value(r, point)
            assert vl is not None and vr is not None, (l, r, point)
            assert close(vl, vr, rel=1e-30), (l, r, point, vl, vr)


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_domain(family, row):
    """At every zero and pole of sin and cos (and a regular point or two), the
    right side is defined exactly where the left side is, and equal there."""
    lhs, rhs, _ = row
    (u,) = _symbols(row)
    points = SPECIAL + [p + I for p in SPECIAL[:5]] + [Rational(1, 3), -I]
    defined = 0
    for p in points:
        vl, vr = exact_value(lhs, {u: p}), exact_value(rhs, {u: p})
        assert (vl is None) == (vr is None), f"{lhs} -> {rhs} at {u} = {p}: {vl} vs {vr}"
        if vl is not None:
            defined += 1
            assert exact_close(vl, vr), (lhs, rhs, p, vl, vr)
    assert defined >= 4


def test_checker_finds_a_wrong_row_and_a_removed_pole():
    """The checks above can fail: a wrong identity and a row that removes a pole are caught."""
    u = symbols('u')
    point = {u: 0.7}
    assert not close(value(sin(u)**2, point), value(1 - cos(u)**2 + Rational(1, 10**25), point), rel=1e-30)
    vl, vr = exact_value(tan(u)*cos(u), {u: pi/2}), exact_value(sin(u), {u: pi/2})
    assert vl is None and vr == 1
    assert exact_value(sin(u)/cos(u), {u: pi/2}) is None and exact_value(tan(u), {u: pi/2}) is None
