"""trigsimp's conditional rows and its sign table (``docs/trigsimp.md``, "Soundness", "Test plan").

* every conditional rule row (moduli, inverse functions, quotients to a
  non-integer power) is an identity at points satisfying its condition,
  random ones and exact ones (the closed endpoints of its interval among
  them), with each side defined where the other is; and it fails somewhere
  outside its condition, so the condition is not vacuous;
* every row of the sign table states a fact that holds on its condition's
  interval (random points, and exact points with the endpoints);
* **assumptions**: for each conditional row, assumptions that prove its
  condition rewrite, assumptions that refute it and none leave the input alone;
* the facts the sign table adds are what makes them provable: satassume alone
  does not decide the signs of trigonometric values.
"""
from __future__ import annotations

import random

import pytest
from sympy import (
    Abs,
    And,
    I,
    Q,
    Rational,
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
    pi,
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
    holds,
    holds_exact,
    value,
)

from satsimp import trigsimp
from satsimp.engine import backend
from satsimp.engine.guard import strict_loops
from satsimp.methods.trigsimp import _asker, wiring
from satsimp.methods.trigsimp.rules import inverses, moduli, quotients, signs

ROWS = [("moduli", row) for row in moduli.RULES] + \
       [("inverses", row) for row in inverses.RULES] + \
       [("quotients", row) for row in quotients.RULES]
IDS = [f"{family}: {row[0]} -> {row[1]}" for family, row in ROWS]

t = Symbol('t')
s = Symbol('s')
_w, _u, _a, _b = Symbol('w'), Symbol('u'), Symbol('a'), Symbol('b')
CHOICES = {
    _w: [t, sin(t), cos(t) - Rational(1, 3), sinh(t)],
    _u: [t, 2*t, t + pi/7, -t],
    _a: [s, Rational(1, 2), Rational(5, 2), s - Rational(1, 3)],
}
"""What each pattern symbol is bound to; ``b`` is bound to ``-a`` (the quotient
rows' condition ``a + b = 0``)."""

EXACT_T = SPECIAL + [-pi/3, -pi/6, 3*pi/4, -3*pi/4, 5*pi/4, I*pi/3, I, Rational(1, 3), -Rational(1, 2)]
EXACT_S = [S.Half, -Rational(3, 2), Rational(1, 3), S(2), I]


def _bindings(row):
    syms = row[0].free_symbols
    for k in range(4):
        b = {sym: CHOICES[sym][k] for sym in syms if sym in CHOICES}
        if _b in syms:
            b[_b] = -b[_a]
        yield b


def _random_point(rng: random.Random, wide: bool = False) -> dict:
    spread, imag = (7, 3) if wide else (4, 1)
    out = {}
    for sym in (t, s):
        re = rng.uniform(-spread, spread)
        out[sym] = re if rng.random() < .6 else complex(re, rng.uniform(-imag, imag))
    return out


def _bound(row, b):
    lhs, rhs, cond = (e.xreplace(b) for e in row[:3])
    return lhs, rhs, cond


def test_every_conditional_row_is_checked():
    wired = wiring.CONDITIONAL + quotients.RULES
    assert sorted(map(str, wired)) == sorted(str(row) for _, row in ROWS)
    keys = {row[0].func.__name__ for row in wiring.CONDITIONAL}
    assert keys == {"Pow", "Abs", "asin", "acos", "atan", "atan2"}
    assert keys <= set(wiring.NORMALIZE) and keys <= set(wiring.SIMPLIFY)


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_shape(family, row):
    lhs, rhs, cond = row[:3]
    assert cond is not True, "a conditional row"
    assert rhs.free_symbols <= lhs.free_symbols, "the right side binds nothing new"
    assert cond.free_symbols <= lhs.free_symbols


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_identity_on_its_condition(family, row):
    """At random points where the condition holds, both sides are defined
    or neither, and they agree."""
    rng = random.Random(f"conditional {row}")
    for b in _bindings(row):
        lhs, rhs, cond = _bound(row, b)
        checked = 0
        for _ in range(3000):
            point = _random_point(rng)
            if holds(cond, point) is not True:
                continue
            vl, vr = value(lhs, point), value(rhs, point)
            assert (vl is None) == (vr is None), (lhs, rhs, point, vl, vr)
            if vl is not None:
                assert close(vl, vr, rel=1e-30), (lhs, rhs, point, vl, vr)
                checked += 1
            if checked >= 12:
                break
        assert checked >= 12, f"{lhs}: too few points satisfy {cond}"


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_domain_at_exact_points(family, row):
    """At exact points (zeros and poles, the endpoints of the principal
    intervals) where the condition holds, both sides are defined or neither,
    and they agree."""
    checked = 0
    for b in _bindings(row):
        lhs, rhs, cond = _bound(row, b)
        for i, pt in enumerate(EXACT_T):
            at = {t: pt, s: EXACT_S[i % len(EXACT_S)]}
            if holds_exact(cond, at) is not True:
                continue
            vl, vr = exact_value(lhs, at), exact_value(rhs, at)
            assert (vl is None) == (vr is None), (lhs, rhs, at, vl, vr)
            if vl is not None:
                assert exact_close(vl, vr), (lhs, rhs, at, vl, vr)
                checked += 1
    assert checked >= 6


BOUNDARIES = [
    (asin(sin(_u)), [pi/2, -pi/2]), (acos(cos(_u)), [S.Zero, pi]), (atan2(sin(_u), cos(_u)), [pi]),
    (Abs(_w), [S.Zero]), (sqrt(_w**2), [S.Zero]),
]


@pytest.mark.parametrize("lhs, ends", BOUNDARIES, ids=[str(lhs) for lhs, _ in BOUNDARIES])
def test_row_at_its_closed_endpoints(lhs, ends):
    """Each closed endpoint of a condition is inside it, and the row holds there."""
    rows = [row for _, row in ROWS if row[0] == lhs]
    assert rows
    for end in ends:
        sym = _u if _u in lhs.free_symbols else _w
        fired = 0
        for row in rows:
            at = {sym: end}
            if holds_exact(row[2].xreplace(at), {}) is not True:
                continue
            vl, vr = exact_value(row[0], at), exact_value(row[1], at)
            assert vl is not None and vr is not None and exact_close(vl, vr), (row, end)
            fired += 1
        assert fired, f"no row of {lhs} holds at {end}"


@pytest.mark.parametrize("family, row", ROWS, ids=IDS)
def test_row_fails_outside_its_condition(family, row):
    """Somewhere the condition does not hold, the identity fails: the condition is needed."""
    rng = random.Random(f"outside {row}")
    for b in _bindings(row):
        lhs, rhs, cond = _bound(row, b)
        for _ in range(3000):
            point = _random_point(rng, wide=True)
            if holds(cond, point) is not False:
                continue
            vl, vr = value(lhs, point), value(rhs, point)
            if vl is not None and (vr is None or not close(vl, vr, rel=1e-20)):
                return
    pytest.fail(f"{row[0]} -> {row[1]} holds everywhere sampled outside {row[2]}")


# the sign table ---------------------------------------------------------------

SIGN_IDS = [f"{atom}: {fact} if {cond}" for atom, fact, cond in signs.ROWS]
SIGN_EXACT = SPECIAL + [-pi/3, -pi/4, -pi/6, 3*pi/4, -3*pi/4, 5*pi/4, 4*pi/3, -2*pi/3, Rational(1, 3), S(-2), S(5),
                        I, I*pi/2, pi + I, S(1) + I]


@pytest.mark.parametrize("atom, fact, cond", signs.ROWS, ids=SIGN_IDS)
def test_sign_row_holds_on_its_interval(atom, fact, cond):
    u = signs.u
    assert atom.args == (u,) and fact.has(atom) and cond.free_symbols == {u}
    rng = random.Random(f"sign {fact} {cond}")
    checked = 0
    for _ in range(4000):
        x0 = rng.uniform(-7, 7)
        point = {u: x0 if rng.random() < .7 else complex(x0, rng.uniform(-2, 2))}
        if holds(cond, point) is not True:
            continue
        got = holds(fact, point)
        assert got is not False, (fact, point)
        checked += got is True
        if checked >= 40:
            break
    assert checked >= 40
    exact = 0
    for p in SIGN_EXACT:
        if holds_exact(cond, {u: p}) is True:
            assert holds_exact(fact, {u: p}) is True, (fact, p)
            exact += 1
    assert exact >= 2


@pytest.mark.parametrize("atom, fact, cond", signs.ROWS, ids=SIGN_IDS)
def test_sign_row_at_closed_endpoints(atom, fact, cond):
    """A closed endpoint (``Q.ge``, ``Q.le``) of a condition is inside it, and the fact holds there."""
    u = signs.u
    for c in [c for c in And.make_args(cond) if c.function in (Q.ge, Q.le)]:
        end = c.arguments[1]
        assert holds_exact(cond, {u: end}) is True
        assert holds_exact(fact, {u: end}) is True, (fact, end)


def test_sign_facts_are_what_proves_signs():
    """satassume alone does not decide these; with the sign table's facts it does."""
    x = symbols('x')
    ask = _asker({})
    for prop, assumptions in [
            (Q.positive(2*cos(x)), Q.gt(x, -pi/2) & Q.lt(x, pi/2)),
            (Q.nonnegative(1 + cos(x)), Q.real(x)),
            (Q.nonnegative(3 - 2*sin(x) + cos(x)), Q.real(x)),
            (Q.negative(sin(x) + sin(2*x)), Q.gt(x, -pi/2) & Q.lt(x, 0)),
            (Q.positive(tan(x)*cos(x)), Q.gt(x, 0) & Q.lt(x, pi/2)),
            (Q.ge(cosh(x), 1), Q.real(x)),
            (Q.negative(tanh(x) - 1), Q.real(x))]:
        assert backend.ask(prop, assumptions) is not True, prop
        assert ask(prop, assumptions) is True, (prop, assumptions)


def test_sign_facts_are_principal_and_not_recursive():
    x = symbols('x')
    ask = _asker({})
    assert ask(Q.positive(sin(x)), Q.gt(x, 2*pi) & Q.lt(x, 3*pi)) is None        # no 2*pi shifts
    assert ask(Q.positive(sin(x)), Q.gt(x, 0) & Q.lt(x, pi)) is True
    # 0 < sin(x) < pi holds, but proving it needs the table's facts about sin(x): not asked
    assert ask(Q.positive(sin(sin(x))), Q.gt(x, 0) & Q.lt(x, pi)) is None
    assert ask(Q.positive(sin(x)), True) is None


# assumptions: each conditional row ----------------------------------------------

x, y = symbols('x y')
_open = lambda lo, hi: Q.gt(x, lo) & Q.lt(x, hi)
_closed = lambda lo, hi: Q.ge(x, lo) & Q.le(x, hi)

ASSUMED = [
    # (row's left side, expression, assumptions proving the condition, result, assumptions refuting it);
    # the refuting assumptions refute the condition of the row's partner too (Abs(w) -> -w for
    # Abs(w) -> w), so nothing fires.  cos(x) is real for imaginary x: it is said of cos(x) itself
    (sqrt(_w**2), sqrt(sin(x)**2), Q.real(x), Abs(sin(x)), Q.imaginary(x)),
    ((_w**2)**Rational(-1, 2), 1/sqrt(cos(x)**2), Q.real(x), 1/Abs(cos(x)), Q.imaginary(cos(x))),
    (sqrt(_w**-2), sqrt(1/cos(x)**2), Q.real(x), 1/Abs(cos(x)), Q.imaginary(cos(x))),
    (Abs(_w), Abs(sin(x)), _open(0, pi), sin(x), Q.imaginary(x)),
    (Abs(_w), Abs(cos(x)), _closed(-pi/2, pi/2), cos(x), Q.imaginary(cos(x))),
    (Abs(_w), Abs(sin(x)), _open(-pi, 0), -sin(x), Q.imaginary(x)),
    (Abs(_w), Abs(cos(x)), _open(pi/2, 3*pi/2), -cos(x), Q.imaginary(cos(x))),
    (Abs(_w), Abs(sinh(x)), Q.nonnegative(x), sinh(x), Q.imaginary(x)),
    (asin(sin(_u)), asin(sin(x)), _closed(-pi/2, pi/2), x, _open(pi/2, pi)),
    (acos(cos(_u)), acos(cos(x)), _closed(0, pi), x, _open(-pi, 0)),
    (atan(tan(_u)), atan(tan(x)), _open(-pi/2, pi/2), x, _open(pi/2, pi)),
    # what the normalizing pass makes of atan(tan(x)); left alone, it is atan(tan(x)), smaller
    (atan(sin(_u)/cos(_u)), atan(sin(x)/cos(x)), _open(-pi/2, pi/2), x, _open(pi/2, pi), atan(tan(x))),
    (atan2(sin(_u), cos(_u)), atan2(sin(x), cos(x)), Q.gt(x, -pi) & Q.le(x, pi), x, _open(pi, 2*pi)),
    (quotients.RULES[0][0], sin(x)**y/cos(x)**y, _open(-pi/2, pi/2), tan(x)**y, _open(pi, 3*pi/2)),
    (quotients.RULES[0][0], sin(x)**Rational(5, 2)/cos(x)**Rational(5, 2), _open(0, pi/2), tan(x)**Rational(5, 2),
     _open(pi, 3*pi/2)),
    (quotients.RULES[1][0], cos(x)**y/sin(x)**y, _open(0, pi/2), cot(x)**y, Q.negative(sin(x)) & Q.negative(cos(x))),
    (quotients.RULES[1][0], sin(x)**y/cos(x)**y, _open(pi/2, pi), cot(x)**(-y), _open(pi, 3*pi/2)),
    (quotients.RULES[2][0], sinh(x)**y/cosh(x)**y, Q.real(x), tanh(x)**y,
     Q.negative(sinh(x)) & Q.negative(cosh(x))),
    (quotients.RULES[3][0], cosh(x)**y/sinh(x)**y, Q.positive(x), coth(x)**y,
     Q.negative(sinh(x)) & Q.negative(cosh(x))),
]
ASSUMED = [case if len(case) == 6 else case + (case[1],) for case in ASSUMED]
"""The sixth element: the result when the row does not fire (the input, unless something else is smaller)."""
ASSUMED_IDS = [f"{e} | {a}" for _, e, a, *_ in ASSUMED]


def _run(e, assumptions=True):
    with strict_loops():
        return trigsimp(e, assumptions)


def test_every_conditional_row_has_assumption_cases():
    assert {str(row[0]) for _, row in ROWS} == {str(lhs) for lhs, *_ in ASSUMED}


@pytest.mark.parametrize("lhs, expr, proving, expected, refuting, alone", ASSUMED, ids=ASSUMED_IDS)
def test_assumptions_proving_the_condition(lhs, expr, proving, expected, refuting, alone):
    assert _run(expr, proving) == expected


@pytest.mark.parametrize("lhs, expr, proving, expected, refuting, alone", ASSUMED, ids=ASSUMED_IDS)
def test_assumptions_refuting_the_condition(lhs, expr, proving, expected, refuting, alone):
    assert _run(expr, refuting) == alone


@pytest.mark.parametrize("lhs, expr, proving, expected, refuting, alone", ASSUMED, ids=ASSUMED_IDS)
def test_no_assumptions(lhs, expr, proving, expected, refuting, alone):
    assert _run(expr) == alone


def test_condition_provable_from_nothing():
    # cos(1) > 0 and sin(1) > 0 need no assumptions
    assert _run(sin(1)**y/cos(1)**y) == tan(1)**y
    assert _run(cos(2)**y/sin(2)**y) == cot(2)**y


def test_rows_compose_with_the_substitution_rows():
    # a Pythagorean row leaves a square under the root, the Pow and Abs rows take it
    assert _run(sqrt(1 - sin(x)**2), _open(-pi/2, pi/2)) == cos(x)
    assert _run(sqrt(1 - sin(x)**2), Q.real(x)) == Abs(cos(x))
    assert _run(1/sqrt(1 - cos(x)**2), _open(0, pi)) == 1/sin(x)
    assert _run(sqrt(1 + tan(x)**2), _open(-pi/2, pi/2)) == 1/cos(x)
    assert _run(sqrt(cosh(x)**2 - 1), Q.positive(x)) == sinh(x)
    assert _run(Abs(1 + cos(x)), Q.real(x)) == 1 + cos(x)
    assert _run(Abs(sin(x)**2 + cos(x)**2 - 2), Q.real(y)) == 1
    assert _run(atan(tan(x)) + sin(x)**2 + cos(x)**2, _open(-pi/2, pi/2)) == x + 1
    assert _run(acos(cos(x))*tan(x)*cos(x), _closed(0, pi)) == x*sin(x)
    assert _run(asin(sin(2*x)), _open(0, pi/4)) == 2*x
    assert _run(asin(sin(2*x)), _open(0, pi/2)) == asin(sin(2*x))
    assert _run(sqrt(sin(x)**2), Q.gt(x, 2*pi) & Q.lt(x, 3*pi)) == Abs(sin(x))     # principal windows only
