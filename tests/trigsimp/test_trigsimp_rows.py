"""Every row of trigsimp's tables, checked numerically (``docs/trigsimp.md``, "Soundness").

A row ``(lhs, rhs, condition)`` must state an identity, and its right side
must be defined exactly where its left side is: defined wherever the left
side is (a rewrite never loses a point), and not defined where the left side
is not (a row never removes a pole: ``tan(u) -> sin(u)/cos(u)`` keeps the
pole at ``pi/2``).  Every row so far holds everywhere (condition ``True``),
so both are checked at random real and complex points and at the exact zeros
and poles of the circular and hyperbolic functions, with each pattern symbol
also a shifted or scaled argument.
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
from satsimp.methods.trigsimp.rules import angles, normal, pythagorean, quotients
from satsimp.methods.trigsimp.substitute import _candidate, _pattern

ROWS = [("normal", row) for row in normal.RULES] + \
       [("quotients", row) for row in quotients.SUBSTITUTIONS] + \
       [("pythagorean", row) for row in pythagorean.SUBSTITUTIONS] + \
       [("angles", row) for row in angles.SUBSTITUTIONS]
IDS = [f"{family}: {row[0]} -> {row[1]}" for family, row in ROWS]

t = Symbol('t')
s = Symbol('s')
ARGUMENTS = [t, 2*t, t + pi/7, -t]
"""What a pattern symbol is bound to: the row holds for every argument."""
SECOND = [s, s - pi/5, t + pi/7, 3*t]
"""What a second pattern symbol is bound to, beside :data:`ARGUMENTS` (the third pair binds both to one argument)."""


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
    syms = _symbols(row)
    for args in zip(ARGUMENTS, SECOND):
        l, r = lhs.xreplace(dict(zip(syms, args))), rhs.xreplace(dict(zip(syms, args)))
        for point in random_points([t, s], rng, 20):
            vl, vr = value(l, point), value(r, point)
            assert vl is not None and vr is not None, (l, r, point)
            assert close(vl, vr, rel=1e-30), (l, r, point, vl, vr)


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_domain(family, row):
    """At every zero and pole of sin and cos, and of sinh and cosh (at ``I``
    times those of sin and cos), and a regular point or two, the right side is
    defined exactly where the left side is, and equal there; a second pattern
    symbol is at a zero, a pole or a regular point too, or at the same point."""
    lhs, rhs, _ = row
    syms = _symbols(row)
    points = SPECIAL + [I*p for p in SPECIAL[1:]] + [p + I for p in SPECIAL[:5]] + [Rational(1, 3), -I]
    others = [S.Zero, pi/2, I*pi/2, Rational(1, 3), None]     # None: the same point as the first
    defined = 0
    for i, p in enumerate(points):
        other = others[i % len(others)]
        at = dict(zip(syms, (p, p if other is None else other)))
        vl, vr = exact_value(lhs, at), exact_value(rhs, at)
        assert (vl is None) == (vr is None), f"{lhs} -> {rhs} at {at}: {vl} vs {vr}"
        if vl is not None:
            defined += 1
            assert exact_close(vl, vr), (lhs, rhs, at, vl, vr)
    assert defined >= 4


def test_checker_finds_a_wrong_row_and_a_removed_pole():
    """The checks above can fail: a wrong identity and a row that removes a pole are caught."""
    u = symbols('u')
    point = {u: 0.7}
    assert not close(value(sin(u)**2, point), value(1 - cos(u)**2 + Rational(1, 10**25), point), rel=1e-30)
    vl, vr = exact_value(tan(u)*cos(u), {u: pi/2}), exact_value(sin(u), {u: pi/2})
    assert vl is None and vr == 1
    assert exact_value(sin(u)/cos(u), {u: pi/2}) is None and exact_value(tan(u), {u: pi/2}) is None


def test_sites_of_one_term_are_replaced_together():
    # two sites of sin(u)**2 in one term: dividing the first replacement (a sum) by
    # sin(y)**2 would put a pole at y = 0, where the term is 0
    u, x, y = symbols('u x y')
    lhs, rhs = sin(u)**2, 1 - cos(u)**2
    for term, sites in ((sin(x)**2*sin(y)**2, [({u: x}, 1), ({u: y}, 1)]),
                        (sin(x)**5*sin(y)**3, [({u: x}, 2), ({u: y}, 1)])):
        chosen = [(0, frozenset(b.items()), b, j) for b, j in sites]
        cand = _candidate([term], chosen, lhs, rhs)
        for point in ({x: 0.7, y: 0}, {x: 0.7, y: -1.3}, {x: 1j/3, y: 2 + 1j}):
            got = value(cand, point)
            assert got is not None and close(got, value(term, point))
