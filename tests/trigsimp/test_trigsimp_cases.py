"""trigsimp's results on the identities of SymPy's own tests (``docs/trigsimp.md``, "Test plan").

The cases come from ``sympy/simplify/tests/test_trigsimp.py`` and
``test_fu.py`` (the test function is named in each group).  The core
(normalizing pass, quotient and Pythagorean rows) gives:

* :data:`SIMPLIFIED`: the result, in this method's form where it differs
  from SymPy's (``cot(x)**2`` where SymPy gives ``1/tan(x)**2``);
* :data:`UNCHANGED`: the input itself, either out of the core's scope
  (angle-addition, double-angle and hyperbolic rows come with PR (c), sign
  tables, ``Abs``/``sqrt`` and principal ranges with PR (d); noncommutative
  factors and symbolic exponents are left alone) or not made smaller by any row;
* :data:`GAPS`: SymPy simplifies these and the core does not, although its
  rows would do: strict xfails, so a fix shows up.
"""
from __future__ import annotations

import pytest
from sympy import (
    Float,
    I,
    Integer,
    Piecewise,
    Q,
    Rational,
    S,
    Subs,
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
    exp,
    expand,
    log,
    pi,
    sec,
    sin,
    sinh,
    sqrt,
    symbols,
    tan,
    tanh,
)

from satsimp import trigsimp
from satsimp.engine.guard import strict_loops

x, y, a, b = symbols('x y a b')
A = Symbol('A', commutative=False)

# the expression of SymPy's test_trigsimp_issues that is defined nowhere: z and z1 are both 0
_z = cos(x)**2 + sin(x)**2 - 1
_z1 = tan(x)**2 - 1/cot(x)**2
_n = 1 + _z1/_z

SIMPLIFIED = [
    # test_trigsimp1
    (1 - sin(x)**2, cos(x)**2),
    (1 - cos(x)**2, sin(x)**2),
    (sin(x)**2 + cos(x)**2, 1),
    (1 + tan(x)**2, 1/cos(x)**2),
    (1/cos(x)**2 - 1, tan(x)**2),
    (1/cos(x)**2 - tan(x)**2, 1),
    (1 + cot(x)**2, 1/sin(x)**2),
    (1/sin(x)**2 - 1, cot(x)**2),                       # SymPy: 1/tan(x)**2
    (1/sin(x)**2 - cot(x)**2, 1),
    (5*cos(x)**2 + 5*sin(x)**2, 5),
    (sin(x)/cos(x), tan(x)),
    (2*tan(x)*cos(x), 2*sin(x)),
    (cot(x)**3*sin(x)**3, cos(x)**3),
    (y*tan(x)**2/sin(x)**2, y/cos(x)**2),
    (cot(x)/cos(x), 1/sin(x)),
    (log(2*sin(x)**2 + 2*cos(x)**2), log(2)),
    # test_trigsimp1a (the circular ones)
    (sin(2)**2*cos(3)*exp(2)/cos(2)**2, tan(2)**2*cos(3)*exp(2)),
    (tan(2)**2*cos(3)*exp(2)*cos(2)**2, sin(2)**2*cos(3)*exp(2)),
    (cot(2)*cos(3)*exp(2)*sin(2), cos(3)*exp(2)*cos(2)),
    (tan(2)*cos(3)*exp(2)/sin(2), cos(3)*exp(2)/cos(2)),
    (cot(2)*cos(3)*exp(2)/cos(2), cos(3)*exp(2)/sin(2)),
    (cot(2)*cos(3)*exp(2)*tan(2), cos(3)*exp(2)),
    # test_trigsimp2 (SymPy needs recursive=True)
    (cos(x)**2*sin(y)**2 + cos(x)**2*cos(y)**2 + sin(x)**2, 1),
    (sin(x)**2*sin(y)**2 + sin(x)**2*cos(y)**2 + cos(x)**2, 1),
    (Subs(x, x, sin(y)**2 + cos(y)**2), Subs(x, x, 1)),
    # test_issue_4373
    (2.0*sin(x)**2 + 2.0*cos(x)**2, Float(2.0)),
    # test_trigsimp3
    (sin(x)**2/cos(x)**2, tan(x)**2),
    (sin(x)**3/cos(x)**3, tan(x)**3),
    (sin(x)**10/cos(x)**10, tan(x)**10),
    (cos(x)/sin(x), cot(x)),                            # SymPy: 1/tan(x)
    (cos(x)**2/sin(x)**2, cot(x)**2),
    (cos(x)**10/sin(x)**10, cot(x)**10),
    # test_issue_4661
    (-4*sin(x)**4 + 4*cos(x)**4 - 8*cos(x)**2, -4),
    (-2*cos(x)**2 + cos(x)**4 - sin(x)**4, -1),
    # test_issue_4494
    (sin(a)**2*sin(b)**2 + cos(a)**2*cos(b)**2*tan(a)**2 + cos(a)**2, 1),
    # test_issue_4280
    (cos(x)**2 + cos(y)**2*sin(x)**2 + sin(y)**2*sin(x)**2, 1),
    (a**2*sin(x)**2 + a**2*cos(y)**2*cos(x)**2 + a**2*cos(x)**2*sin(y)**2, a**2),
    (a**2*cos(y)**2*sin(x)**2 + a**2*sin(y)**2*sin(x)**2, a**2*sin(x)**2),
    # test_trigsimp_issues
    (sin(x)**3 + cos(x)**2*sin(x), sin(x)),
    ((sin(x)**y/cos(x)**y).subs(y, 2), tan(x)**2),
    (cos(x)**2/sin(x)**2*cos(y)**2/sin(y)**2, cot(x)**2*cot(y)**2),     # SymPy: 1/tan(x)**2/tan(y)**2
    (cos(x)/sin(x)*cos(x + y)/sin(x + y), cot(x)*cot(x + y)),           # SymPy: 1/(tan(x)*tan(x + y))
    (-sin(x)**4 - 2*sin(x)**2*cos(x)**2 - cos(x)**4, -1),
    # SymPy gives nan for these two (or the input for the first); the input is
    # defined nowhere (it divides by z, which is 0), so any result is sound
    # (docs/trigsimp.md, "Soundness"), and normalizing makes z1 the 0 it is first
    (sin(_n), sin(1)),
    (x*(_n - 1) - x*_n, -x),
    # test_trigsimp_issue_2515
    (x*cos(x)*tan(x), x*sin(x)),
    (-sin(x) + cos(x)*tan(x), 0),
    # test_trigsimp_noncommutative: a product with a noncommutative factor is
    # normalized (the trigonometric factors commute), sums with one are left alone
    (A*tan(x)*cos(x), A*sin(x)),
    (A*cot(x)**3*sin(x)**3, A*cos(x)**3),
    (y*A*tan(x)**2/sin(x)**2, y*A/cos(x)**2),
    (A*cot(x)/cos(x), A/sin(x)),
    # test_hyperbolic_simp (the circular one)
    (tan(x) - 1/cot(x), 0),
    # test_issue_2827_trigsimp_methods
    ((x + 1)/(x + sin(x)**2 + cos(x)**2), 1),
    # test_Piecewise: the trigonometric argument only
    (Piecewise((x*(x + y) - y*(x + y), expand((x + y)*y/x) < sin(x)**2 + cos(x)**2), (expand((x + y)*y/x), True)),
     Piecewise((x*(x + y) - y*(x + y), expand((x + y)*y/x) < 1), (expand((x + y)*y/x), True))),
    # test_trigsimp_old (deep=True there)
    (1 - sin(sin(x)**2 + cos(x)**2)**2, cos(1)**2),
    # test_fu.py: test_fu, test_TR2, test_TR2i, test_TR15_16_17
    (sin(50)**2 + cos(50)**2 + sin(pi/6), Rational(3, 2)),
    (sin(x)**4 - cos(y)**2 + sin(y)**2 + 2*cos(x)**2, cos(x)**4 + 2*sin(y)**2),   # fu: cos(x)**4 - 2*cos(y)**2 + 2
    (tan(tan(x) - sin(x)/cos(x)), 0),
    (sin(x)*sin(y)/cos(x), tan(x)*sin(y)),
    (1/(sin(x)/cos(x)), cot(x)),
    (1/(sin(x)*sin(y)/cos(x)), cot(x)/sin(y)),
    (1 - 1/sin(x)**2, -cot(x)**2),
    (1 - 1/cos(x)**2, -tan(x)**2),
    (1 - 1/tan(x)**2, 1 - cot(x)**2),
    # more of the same rows: sec and csc, quotients of tan, cot, sec, csc, powers of sums
    (sec(x)**2 - tan(x)**2, 1),
    (csc(x)**2 - cot(x)**2, 1),
    (sec(x)*cos(x), 1),
    (tan(x)*cot(x), 1),
    (1/sec(x), cos(x)),
    (1/csc(x)**2, sin(x)**2),
    (1/tan(x), cot(x)),
    (sec(x)/csc(x), tan(x)),
    (csc(x)/sec(x), cot(x)),
    (sin(x)/tan(x), cos(x)),
    (cos(x)/cot(x), sin(x)),
    (sin(x)**4 + 2*sin(x)**2*cos(x)**2 + cos(x)**4, 1),
    ((sin(x)**2 + cos(x)**2)**3, 1),
    (tan(x)**4 + 2*tan(x)**2 + 1, cos(x)**-4),
    (1/(1 + tan(x)**2), cos(x)**2),
    (1/(1 - cos(x)**2), sin(x)**-2),
    (sin(x)*cos(x)/(1 - sin(x)**2), tan(x)),
    (cos(x)**2*tan(x), sin(x)*cos(x)),
    (sin(x)**2*cos(x)**3 + cos(x)**5, cos(x)**3),
    (sec(x)**4 - tan(x)**4, 2*tan(x)**2 + 1),
    (tan(x)**2 - sin(x)**2*tan(x)**2, sin(x)**2),       # the Pythagorean pre-pass
    (x**2*sin(x)**2 + x**2*cos(x)**2 + x, x**2 + x),
    ((x + 1)*sin(x)**2 + (x + 1)*cos(x)**2, x + 1),    # the rest of a term is distributed as one factor
    (sin(x)**2/(x + 1) + cos(x)**2/(x + 1), 1/(x + 1)),
    (I*sin(x)**2 + I*cos(x)**2, I),
    (sin(x + y)**2 + cos(x + y)**2 + sinh(x), sinh(x) + 1),
    (sin(sin(x)**2 + cos(x)**2), sin(1)),
    ((sin(x)**2 + cos(x)**2)**x, 1),
]

UNCHANGED = [
    # nothing smaller: the input, never its normal form
    tan(x), sec(x), csc(x), cot(x), tan(x)**2, sin(x)**4, sin(x)**2 + cos(y)**2,
    cos(x)/sin(x)**7, cos(x)/sin(x)**3, sin(x)/cos(x)**3,        # test_issue_5948, test_trigsimp_issues
    sin(x)**8 + cos(x)**8, tan(x)**2 - sin(x)**2, sin(x)**2*tan(x)**2, sin(x + y)*csc(y),
    tan(1)*tan(2),                                               # test_fu
    cos(2)*(cos(3) + 1)**2/(cos(3) - 1)**2,                      # test_trigsimp_issues (SymPy: the same, factored)
    2**(x/2)*cos(pi*x/4)/2 + 2**(x - 1)/2,                       # test_trigsimp_issue_4032 (no trig identity)
    # angle addition, double angles (PR (c))
    sin(x + y) + sin(x - y), sin(x + y) - sin(x - y), cos(x + y) + cos(x - y), cos(x + y) - cos(x - y),
    tan(x + y) - tan(x)/(1 - tan(x)*tan(y)),                     # test_trigsimp1
    sin(x)*cos(y) + cos(x)*sin(y), sin(x)*cos(y) + cos(x)*sin(y) + 3,   # test_issue_4775
    sin(2)*cos(3) + sin(3)*cos(2), -sin(2)*sin(3) + cos(2)*cos(3), sin(2)*cos(3) - sin(3)*cos(2),
    sin(2)*sin(3) + cos(2)*cos(3), sin(2)*sin(3) + cos(2)*cos(3) + cos(2),          # test_issue_3210
    sin(Rational(1, 50))*sin(Rational(1, 25)) + cos(Rational(1, 50))*cos(Rational(1, 25)),   # test_issue_15129
    tan(2*x).expand(trig=True),                                  # test_trigsimp_issue_3826
    S.Half - cos(2*x)/2, sin(x)/2/(cos(x) + 1),                  # test_fu, test_TR2i
    # hyperbolic functions (PR (c))
    sinh(x + y) + sinh(x - y), cosh(x + y) - cosh(x - y), sinh(x)**2 + 1, cosh(x)**2 - sinh(x)**2,
    sinh(x)/cosh(x), 2*tanh(x)*cosh(x), 3*tanh(x)**7 - 2/coth(x)**7, cosh(pi/4),   # test_hyperbolic_simp, issue_7761
    # moduli, roots, symbolic exponents, inverse functions (PR (d))
    sqrt(sin(x)**2), cos(x) + sqrt(sin(x)**2),   # test_fu (issue 18059)
    sin(x)**y/cos(x)**y, sin(1)**y/cos(1)**y,                    # test_trigsimp_issues
    tan(x)**y, sin(x)**Rational(5, 2)/cos(x)**Rational(5, 2), sin(x)**2.0 + cos(x)**2.0,
    asin(sin(a)), acos(cos(a)), atan(tan(a)), atan2(sin(a), cos(a)),   # test_trigsimp_inverse
    # sums with a noncommutative factor (test_trigsimp_noncommutative)
    A - A*sin(x)**2, A - A*cos(x)**2, A*sin(x)**2 + A*cos(x)**2, A + A*tan(x)**2, A/cos(x)**2 - A,
    A/cos(x)**2 - A*tan(x)**2, y*A*cos(x)**2 + y*A*sin(x)**2, A*sin(x)/cos(x), A*sin(x + y) + A*sin(x - y),
]

GAPS = [
    # test_trigsimp_issues: (cos(3) - 1)*(cos(3) + 1) is -sin(3)**2, after expanding the product
    (cos(2)*(cos(3) + 1)**2*(cos(3) - 1)**2, cos(2)*sin(3)**4, "a product of sums is not expanded"),
    # test_fu.py, test_TR14
    ((cos(x) - 1)*(cos(x) + 1), -sin(x)**2, "a product of sums is not expanded"),
    ((sin(x) - 1)*(sin(x) + 1), -cos(x)**2, "a product of sums is not expanded"),
    # test_issue_4661 (simplify there): numerator cos(x)**2 + 1, denominator sin(x)**2 - 2
    ((sin(x)**6 + 4*sin(x)**4*cos(x)**2 + 5*sin(x)**2*cos(x)**4 + 2*cos(x)**6)/(-sin(x)**2 - 2*cos(x)**2), -1,
     "a common factor of numerator and denominator is not cancelled"),
    # 2*cos(2*x)**4*(cos(2*x)**2 - 1)**2: the first step (a Pythagorean row at one term) does not shrink the sum
    (2*cos(2*x)**8 - 4*cos(2*x)**6 + 2*cos(2*x)**4, 2*sin(2*x)**4*cos(2*x)**4, "greedy: no smaller first step"),
]


def _run(e, assumptions=True):
    with strict_loops():       # a tripped termination guard raises instead of returning the input
        return trigsimp(e, assumptions)


@pytest.mark.parametrize("expr, expected", SIMPLIFIED, ids=[str(e)[:60] for e, _ in SIMPLIFIED])
def test_simplified(expr, expected):
    assert _run(expr) == expected


@pytest.mark.parametrize("expr", UNCHANGED, ids=[str(e)[:60] for e in UNCHANGED])
def test_unchanged(expr):
    assert _run(expr) == expr


@pytest.mark.parametrize("expr, expected", [pytest.param(e, r, marks=pytest.mark.xfail(strict=True, reason=why))
                                              for e, r, why in GAPS], ids=[str(e)[:60] for e, _, _ in GAPS])
def test_gap(expr, expected):
    assert _run(expr) == expected


def test_float_argument():
    # test_trigsimp1 and test_trigsimp_noncommutative: evaluated before trigsimp sees them
    assert _run(cos(0.12345)**2 + sin(0.12345)**2) == 1.0
    assert _run(A*cos(0.12345)**2 + A*sin(0.12345)**2) == 1.0*A


def test_not_basic():
    assert _run(1) == 1 and isinstance(_run(1), Integer)     # test_trigsimp_issues: trigsimp(1).is_Integer
    assert _run(x + 1) == x + 1
    assert _run([sin(x)]) == [sin(x)]


def test_assumptions_are_accepted():
    # the core's rows hold everywhere: assumptions do not change a result
    for expr, expected in SIMPLIFIED[:12]:
        assert _run(expr, Q.positive(x) & Q.real(y)) == expected
    assert _run(sin(x)**2 + cos(x)**2, Q.gt(x, 0) & Q.lt(x, pi)) == 1
    assert _run(sec(x), Q.positive(x)) == sec(x)


def test_domain_may_grow():
    # docs/trigsimp.md, "Soundness": the result may be defined at more points
    # (tan(x)*cos(x) is not defined at pi/2, sin(x) is), never at fewer
    assert _run(tan(x)*cos(x)) == sin(x)
    assert _run(cot(x)*sin(x)) == cos(x)
