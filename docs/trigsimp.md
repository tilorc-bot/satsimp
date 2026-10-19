# trigsimp: a trigonometric simplifier as rule tables

`satsimp.trigsimp(expr, assumptions=True)` is satsimp's second method
([architecture.md](architecture.md)): it rewrites trigonometric expressions to
smaller equal ones, with every rewrite an identity row, and every condition a
row needs decided through `ask` (satassume by default), so a result can depend
on the assumptions (`Abs(cos(x))` is `cos(x)` when `-pi/2 < x < pi/2`).

This page is the design note: the scope of the first version, the API, the
soundness argument and the test plan. It is updated as the method grows.

## API

```python
from sympy import Q, cos, pi, sin, sqrt, symbols
from satsimp import trigsimp

x = symbols("x")
trigsimp(sin(x)**2 + cos(x)**2)          # 1
trigsimp(sin(x)/cos(x))                  # tan(x)
trigsimp(sqrt(1 - sin(x)**2), Q.gt(x, -pi/2) & Q.lt(x, pi/2))   # cos(x)
```

`assumptions` is a SymPy boolean of `Q` facts, as for `satsimp.refine`; the
symbols' own assumptions (`Symbol('x', positive=True)`) are not read: what is
assumed is said in `assumptions`. SymPy's `trigsimp` takes options
(`method=`, `deep=`, `recursive=`) instead; satsimp's has none, it always
works bottom-up through the whole expression.

## Scope of the first version

Circular functions (`sin`, `cos`, `tan`, `cot`, `sec`, `csc`), then the
hyperbolic ones with the same tables. Three kinds of rows:

1. **Quotients** (products): `sin(u)/cos(u) = tan(u)`, `cos(u)/sin(u) = cot(u)`,
   to any integer power (`sin(x)**3/cos(x)**3 = tan(x)**3`).
2. **Pythagorean** (sums): `sin(u)**2 = 1 - cos(u)**2`, `cos(u)**2 = 1 - sin(u)**2`,
   `cos(u)**-2 = 1 + tan(u)**2`, `sin(u)**-2 = 1 + cot(u)**2` and their
   reverses; even powers are rewritten as powers of the square
   (`-4*sin(x)**4 + 4*cos(x)**4 - 8*cos(x)**2 = -4`).
3. **Angles** (sums of products): addition formulas in both directions,
   `sin(u)*cos(u) = sin(2*u)/2`, `cos(u)**2 = (1 + cos(2*u))/2`. A
   contracting row has a product on its left side and the other product of
   the formula on its right (`sin(u)*cos(v) = sin(u + v) - cos(u)*sin(v)`),
   so that in `sin(x)*cos(y) + cos(x)*sin(y)` the second term cancels; an
   expanding row has a function of `u + v` (one term against the rest) or
   of `2*u` on its left side.

The hyperbolic rows are the circular ones with the signs of
`cosh(u)**2 - sinh(u)**2 = 1` (Osborn's rule).

Then the rows that need the assumptions:

4. **Signs of trig values**: a table of facts (`sin(u) > 0` when
   `0 < u < pi`, `-1 <= sin(u) <= 1` when `u` is real, ...). Before a question
   is asked, the facts the table proves for the trig atoms in it are added to the
   assumptions, and satassume composes them (`1 + cos(x) >= 0`,
   `2*cos(x) > 0`). satassume alone does not decide signs of trig values.
   The table (`rules/signs.py`) has rows for `sin`, `cos`, `tan`, `cot` on
   their principal windows (`sin(u) > 0` on `(0, pi)`, `>= 0` on `[0, pi]`,
   `< 0` on `(-pi, 0)`, `<= 0` on `[-pi, 0]`; `cos(u)` on `(-pi/2, pi/2)` and
   `(pi/2, 3*pi/2)`; `tan(u)` and `cot(u)` on `(0, pi/2)` and `(-pi/2, 0)`;
   no shifts by `2*pi*n`), and for `cosh(u) >= 1`, `sinh(u)` and `tanh(u)` with
   the sign of `u` and `-1 < tanh(u) < 1`, for real `u`. A fact's condition is
   proved by `ask` without the table's facts, so nothing recurses: `sin(sin(x))
   > 0` for `0 < x < pi` is not proved, since `0 < sin(x) < pi` needs the facts
   about `sin(x)`. The facts are collected per trig atom, assumptions and call.
5. **Moduli and roots**: `sqrt(w**2) = Abs(w)` (and `1/sqrt(w**2) =
   sqrt(1/w**2) = 1/Abs(w)`) for real `w`, `Abs(w) = w` or `-w` by its sign,
   `sin(u)**a/cos(u)**a = tan(u)**a` for any non-integer `a` when
   `cos(u) > 0` (an integer `a` is the quotient rows' case),
   `cos(u)**a/sin(u)**a = cot(u)**a` when `sin(u) > 0`, and the hyperbolic
   forms (`cosh(u) > 0` follows from `u` real). The exponents bind separately
   and must add up to zero (`sin(x)**(5/2)*cos(x)**(-5/2)`); of the rows that
   fire, the smallest result is kept (`cos(x)**y/sin(x)**y` is `cot(x)**y`,
   not `tan(x)**(-y)`, for `0 < x < pi/2`).
6. **Inverse compositions on principal ranges**: `asin(sin(u)) = u` when
   `-pi/2 <= u <= pi/2`, `acos(cos(u)) = u` on `[0, pi]`, `atan(tan(u)) = u`
   on `(-pi/2, pi/2)`, `atan2(sin(u), cos(u)) = u` on `(-pi, pi]`. The
   normalizing pass writes `tan(u)` as `sin(u)/cos(u)` before `atan` sees it,
   so `atan` also has the row `atan(sin(u)/cos(u)) = u`.

Out of the first version: SymPy's `groebner` and `fu` searches (no search
beyond one rewrite at a time, see *How it runs*), shifts by multiples of
`pi/2` (refine has them; trigsimp would need its own rows, a method imports no
other method), noncommutative factors (returned unchanged), and
`exp(I*x)` forms. Kinds 5 and 6 cover the principal windows only (`Abs(sin(x))`
stays for `2*pi < x < 3*pi`), and not the inverses of `sec`, `csc`, `cot` or of
the hyperbolic functions.

## How it runs

On the shared engine ([architecture.md](architecture.md)): the driver walks
the expression bottom-up, dispatches each node to its head's handlers and
repeats until nothing fires, under the termination guard; `ask` is memoized
per call. trigsimp gives the driver its own hooks for the call (its own
`ask`, its own handler registry, no generated tables, no SymPy `_eval_refine`),
so refine's registry and outputs are untouched and refine is never imported.

1. **Normalize**: rule rows rewrite `tan`, `cot`, `sec`, `csc` into `sin`
   and `cos` (Fu's TR1, TR2). They never reintroduce what they remove, so
   this pass terminates.
2. **Simplify**: rows of kinds 1-3 are *substitution rows*: in a sum (a
   product is a sum of one term), for each way the left side matches a part of
   a term, or all such places at once, the matches are replaced by the right
   side, products are distributed and powers of sums expanded, and the
   candidate with the smallest measure is kept if it is smaller than the sum.
   The measure is (number of trig function nodes, `count_ops`, number of
   `Abs` nodes, number of nodes), compared lexicographically, as in Fu et
   al.'s algorithm (the node count breaks ties: `1/cos(x)**2` is smaller than
   `1 + tan(x)**2`; before it, an `Abs` node does: `-sin(x)` is smaller than
   `Abs(sin(x))`).
   The sites of one term are replaced together, the term divided by their
   left sides at once, so every division cancels a factor of the term.
   A product is rewritten only into a product: whether a term becomes a sum
   is decided by its sum, where a product and the sum it sits in cannot
   disagree about what is smaller (`-2*sinh(x)**2` alone is larger than
   `1 - cosh(2*x)`, inside `1/sinh(x/2) - 2*sinh(x)**2` it is not). For the
   same reason a sum is measured in the sign an odd function keeps for it
   (`sin(-e)` is `-sin(e)`): a sum can be smaller than another and larger
   negated.
   Rows of kinds 5 and 6 are rule rows: they fire when their condition is
   provable through `ask`, never through SymPy's `.is_<fact>`. The rows of
   `Abs`, roots and inverse functions serve both passes (keys `Pow`, `Abs`,
   `asin`, `acos`, `atan`, `atan2`), so a modulus is resolved as soon as a
   pass leaves its argument of known sign (`sqrt(1 - sin(x)**2)`: the
   Pythagorean row makes `sqrt(cos(x)**2)`, then `Abs(cos(x))`, then `cos(x)`
   for `-pi/2 < x < pi/2`); the quotient rows to other powers serve the
   simplifying pass only, tried on a product before its substitution rows
   (normalizing would write the `tan` they make back as `sin/cos`).
   The simplify pass runs twice on the normalized expression, once with
   every row and once after a pre-pass with the Pythagorean rows in `sin`
   and `cos` alone, and the smaller result is kept: bottom-up, the quotient
   rows rewrite a term before its sum is seen, which can hide a Pythagorean
   sum (`tan(x)**2 - sin(x)**2*tan(x)**2` is `sin(x)**2` only by the
   pre-pass).
3. Normalizing and simplifying are repeated on the result while it gets
   smaller (a Pythagorean row can leave `cos(x)**2*tan(x)**2`, which
   normalizing makes `sin(x)**2`), so a result is a fixed point of the method.
4. The result is returned if its measure is smaller than the input's, else
   the input (so `sec(x)` stays `sec(x)`).

Every substitution strictly decreases the measure, a well-founded order, so
the simplify pass terminates (and the driver's guard holds in any case);
each repetition of the passes is kept only when it is strictly smaller, so
the repetition terminates too. Each step is greedy: an identity that only
pays off after a step that does not shrink the expression is not found
(`(cos(x) - 1)*(cos(x) + 1)` stays: the product is not expanded).

## Soundness

The claim: `trigsimp(e, A)` equals `e` at every point satisfying `A` where
`e` is defined, meaning every subexpression of `e` evaluates to a finite
number. The result may be defined at more points (`tan(x)*cos(x)` becomes
`sin(x)`), never at fewer. An expression defined nowhere (it divides by
`sin(x)**2 + cos(x)**2 - 1`) is outside the claim: what comes back for it
can be finite, or contain `zoo`, as SymPy's own arithmetic makes it. SymPy's
automatic simplification of products drops a pole of the input when a
rewrite builds one (normalizing `tan(x)*cos(x)` builds
`sin(x)/cos(x)*cos(x)`, which is `sin(x)`); the claim allows that too.

It holds because every step preserves it:

- each row states an identity `lhs = rhs` on a domain (its condition), and
  `rhs` is defined wherever `lhs` is and the condition holds (rows are
  checked numerically for both, at random complex points, at points where
  the condition holds and at the poles and zeros of the trig functions in them);
- a row fires only when its condition is provable under `A` through `ask`;
  the trig facts added to a question are theorems under `A`, proved from the
  sign table, whose rows are checked the same way;
- distributing a product over a sum, and expanding an integer power of a
  sum, preserve values wherever every subexpression is finite;
- rewriting a power `t**(2*m)` as `(t**2)**m` uses only integer `m`.

No step uses SymPy's `simplify`, `trigsimp`, `cancel`, `together`,
`nsimplify` or `.equals`, nor the old assumptions (`.is_positive` and
friends): what is decided is decided by `ask`.

## Test plan

`tests/trigsimp/`, run in its own process like the refine trees, in CI on
both the SymPy fork and PyPI SymPy 1.14.0:

- **rows**: every row of every table checked numerically (identity on its
  domain, right side defined where the left side is), as refine's generated
  rows are;
- **cases**: the identities of SymPy's `test_trigsimp.py` and `test_fu.py`
  that the first version covers, with the outputs this method gives (they can
  differ in form from SymPy's: `cot(x)` where SymPy gives `1/tan(x)`), and the
  ones it does not cover as strict xfails when its rows would do (an
  in-scope gap), and as cases returned unchanged when they need rows of a
  later version (angles, hyperbolic functions, signs, moduli);
- **assumptions**: each conditional row with assumptions that prove its
  condition, assumptions that refute it, and none (no rewrite);
- **soundness fuzz**: random sums and products of trig terms, with and
  without assumptions: the result agrees with the input numerically at
  sampled points satisfying the assumptions (and at the exact zeros and
  poles of the trig functions where the input is defined), its measure is
  not larger, and no termination guard trips;
- **isolation**: refine's results and hooks are unchanged by a trigsimp call
  in the same process, trigsimp imports no other method, and `import satsimp`
  imports no method; refine's three test trees are run as before.

The core (PR b) has the first two kinds of rows, PR (c) the third and the
hyperbolic rows; none of them is conditional. PR (d) adds kinds 4-6: the
sign table, whose rows are checked numerically on their intervals (endpoints
included); the conditional rows, checked at random and exact points that
satisfy their conditions (the closed endpoints among them), and at points
outside, where each fails somewhere (the condition is needed); for each
conditional row, assumptions that prove its condition (it fires), that
refute it and none (the input stays); SymPy's cases that need these rows
(`sqrt(sin(x)**2)`, `sin(x)**y/cos(x)**y`, the inverse functions) with and
without assumptions, unchanged without unless the condition is provable from
nothing (`sin(1)**y/cos(1)**y` is `tan(1)**y`: `cos(1) > 0`); and the fuzz
under assumptions (`0 < x < pi/2`, `-pi/2 < x < 0`, `0 < x < pi`, `x`
real) at points satisfying them, with `Abs`, roots, inverse functions and
quotients to symbolic powers around its terms.
