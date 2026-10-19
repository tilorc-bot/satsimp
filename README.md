# satsimp

Simplification methods written as rule tables, with their conditions proved by the
[satassume](https://github.com/tilorc-bot/satassume) SAT-based `ask` engine. The
name pairs it with satassume; "simp" follows SymPy's `trigsimp`, `powsimp`,
`gammasimp`.

The first method is SymPy's `refine(expr, assumptions)`:

```python
from sympy import Q, Symbol, log
from satsimp import refine

x = Symbol("x")
refine(log(x), Q.negative(x))   # log(-x) + I*pi
```

The second is a trigonometric simplifier, `satsimp.trigsimp(expr, assumptions)`
(see [trigsimp](#trigsimp-a-trigonometric-simplifier) below). Methods share the same
machinery: the row format, the matcher, the condition prover, case splits, the
driver and its termination guard, generated tables and the offline
verification tooling. That machinery is `satsimp/engine/`; each method is a
package under `satsimp/methods/` (refine: `satsimp/methods/refine/`). refine
depends on as little of SymPy as it can and stays small and fast: a method is
imported only when it is first used, so a new method cannot slow refine down or
change its output. The layout, what is shared and how a method plugs in are in
[docs/architecture.md](docs/architecture.md).

refine's rules live in `satsimp/methods/refine/identities/rules/` (one module per
family, e.g. `trig.py`); how they are wired into handlers is
`satsimp/methods/refine/identities/wiring.py`. See [docs/refine.md](docs/refine.md)
and [docs/refine-testing.md](docs/refine-testing.md).

## Install and test

```sh
pip install -e ".[dev]"
# the refine tests expect SymPy at the commit the gates use
pip install "sympy @ git+https://github.com/tilorc-bot/sympy@6379c4da69"
PYTHONHASHSEED=0 python -m pytest -q -n auto tests/refine_identities --ignore=tests/refine_identities/needs
PYTHONHASHSEED=0 python -m pytest -q -n auto tests/refine
PYTHONHASHSEED=0 python -m pytest -q -n auto tests/refine_v3
PYTHONHASHSEED=0 python -m pytest -q -n auto tests/trigsimp
```

Each tree runs in its own pytest process: each selects a handler package that
registers into the one process-wide `handlers_dict`, so `tests/conftest.py`
refuses a session that collects more than one (a bare `pytest` included).

The test trees share module basenames, so run each of `tests/refine_identities`,
`tests/refine`, `tests/refine_v3` and `tests/trigsimp` in its own process, as CI does.

refine and trigsimp also work on PyPI's SymPy 1.14.0, which CI tests as well; there, the
tests that need the newer SymPy are strict xfails or leave out the cases that
need it (see
[docs/refine-testing.md](docs/refine-testing.md), "CI").

To depend on a commit (the old `tilorc-bot/satrefine` URL redirects here):

```sh
pip install "satsimp @ https://github.com/tilorc-bot/satsimp/archive/<commit>.zip"
```

## SymPy boundary

satsimp uses SymPy for its expressions and their automatic evaluation, and for little
else. The shipped package does not call SymPy's simplification (the `simplify` family,
`trigsimp`, `nsimplify`, `cancel`, `together`, `factor`, `gcd`), its number fields
(`minimal_polynomial`), its solvers, `Expr.equals`, or SymPy's assumption reasoning
(`ask`, `refine`, `satask` and their handlers, the `_eval_refine` hooks that ask). The one
exception is `satsimp/engine/backend.py`, which deliberately offers SymPy's `ask` as the
`sympy` backend and as the fallback of `combined` and `union`. Three guards keep the
boundary where it is:

1. **ruff TID251** (`pyproject.toml`) bans the imports, in `satsimp/` and
   `satrefine/`. Tests, tools, fixtures and the reference handlers are exempt; the
   backend marks its imports with `# noqa: TID251 (<reason>)`. CI runs
   `ruff check --select TID251 satsimp satrefine`.
2. **`tools/check_sympy_boundary.py`** (stdlib only) flags what an import ban cannot see:
   reads of `.cancel`, `.equals`, `._eval_refine` and the old-assumption stores
   (`assumptions0`, `default_assumptions`), and calls of `.simplify()`, `.refine()`,
   `.trigsimp()`, `.factor()`, `.together()` and the like. An allowed line says why with
   `# boundary: <reason>`.
3. **A runtime trap** (`tests/refine_identities/boundary/`) wraps SymPy's reasoning and
   simplification functions and methods, then refines the battery and the
   differential's random inputs with `strict=True` in a subprocess. A call reached
   from satsimp fails the test, naming the site. Calls that SymPy's constructors make
   while they evaluate an expression satsimp built are allowed: the allowlist in
   `sympy_trap.py` is short and gives a reason for each entry.

**Strict input.** `refine(expr, assumptions, strict=True)` takes facts only as Q facts.
It raises `satsimp.AssumptionSymbolError` (a `ValueError`) naming every `Symbol`,
`Dummy` or `Wild` declared with an assumption other than `commutative=True`, and every
applied undefined function whose class has one. The check covers `expr` and
`assumptions` and runs before any cache. The call then runs under the `strict`
backend, so SymPy's `ask` is never consulted. The default is unchanged.

```python
from sympy import Abs, Q, Symbol
from satsimp import refine

x, p = Symbol("x"), Symbol("p", positive=True)
refine(Abs(x), Q.positive(x), strict=True)   # x
refine(Abs(x) + p, Q.negative(x))            # p - x: the declaration counts by default
refine(Abs(x) + p, Q.negative(x), strict=True)
# AssumptionSymbolError: strict mode: state assumptions as Q facts, not on p (positive=True)
```

## trigsimp: a trigonometric simplifier

```python
from sympy import cos, sin, symbols, tan
from satsimp import trigsimp

x = symbols("x")
trigsimp(sin(x)**2 + cos(x)**2)                  # 1
trigsimp(1/cos(x)**2 - tan(x)**2)                # 1
trigsimp(sin(x)**3/cos(x)**3)                    # tan(x)**3
trigsimp(-4*sin(x)**4 + 4*cos(x)**4 - 8*cos(x)**2)   # -4
```

`trigsimp(expr, assumptions=True)` takes `assumptions` as `refine` does (a
boolean of `Q` facts; the symbols' own assumptions are not read) and has no
other options. It returns `expr` itself unless it finds a strictly smaller
equal expression, smaller meaning fewer trigonometric functions, then a smaller
`count_ops`, then fewer nodes. The result equals `expr` wherever `expr` is defined; it may be
defined at more points (`tan(x)*cos(x)` becomes `sin(x)`), never at fewer.

What it does now (the core, `satsimp/methods/trigsimp/`): a normalizing pass
writes `tan`, `cot`, `sec` and `csc` with `sin` and `cos`; a simplifying pass
applies substitution rows (quotients: `sin(u)/cos(u) = tan(u)`,
`cos(u)/sin(u) = cot(u)`, to any integer power; Pythagorean:
`sin(u)**2 + cos(u)**2 = 1` and its `tan`, `cot` forms, each way round) to
sums and products, keeping a rewrite only when it makes the expression smaller.
Each step is greedy: an identity that pays off only after a step that does not
shrink the expression is not found, and nothing is factored or cancelled.

Not there yet: angle-addition, double-angle and hyperbolic rows, the sign
tables, `Abs`/`sqrt` and inverse functions on principal ranges (rows that need
the assumptions), noncommutative sums and symbolic exponents (returned
unchanged). The design and the plan are in [docs/trigsimp.md](docs/trigsimp.md);
the tests are `tests/trigsimp/` (SymPy's own trigsimp and fu identities, a
numeric check of every row, a soundness fuzz).

## Renamed from satrefine

This project was called satrefine until the rename that split it into an
engine and methods. What changed for a consumer:

- **Distribution:** `satrefine` is now `satsimp` (`pip uninstall satrefine`
  before installing satsimp into an environment that has it: both install a
  `satrefine` module).
- **Import:** `from satsimp import refine` (`satsimp.refine(expr, assumptions)`).
  `import satrefine` and `satrefine.refine` still work and emit a
  `DeprecationWarning`: the `satrefine` module ships in the satsimp
  distribution as an alias that re-exports the names `satrefine` had at the
  top level (`refine`, `ask`, `handlers_dict`, `HANDLERS_PACKAGE`,
  `DEFAULT_HANDLERS`, `HANDLERS_ENV_VAR`, `handlers_package`). It will be
  removed in a later release. The vendored SymPy handlers (`refine_abs`,
  `refine_Pow`, ...) are no longer exported, from either module: they ask
  SymPy's assumption system. They remain in
  `satsimp.methods.refine.identities.compat.upstream`, for SymPy's own test
  suite. Submodules are not aliased:

  | Before | Now |
  |---|---|
  | `satrefine.refine` | `satsimp.refine` |
  | `satrefine.handlers_dict`, `satrefine.ask`, `satrefine.HANDLERS_PACKAGE` | `satsimp.methods.refine.<name>` |
  | `satrefine.identities.core.<module>` | `satsimp.engine.<module>` |
  | `satrefine.identities.compat.backend` | `satsimp.engine.backend` |
  | `satrefine.identities.config` | `satsimp.engine.config` (`SATSIMP_IDENTITIES`, `SATSIMP_STRICT_LOOPS`), `satsimp.methods.refine.config` (`SATSIMP_HANDLERS`) |
  | `satrefine.identities.<rest>` | `satsimp.methods.refine.identities.<rest>` |
  | `satrefine.handlers_identities`, `satrefine.handlers_v3`, `satrefine.reference.v3` | `satsimp.methods.refine.handlers_identities`, `...handlers_v3`, `...reference.v3` |
  | `satrefine.build`, `satrefine.tools`, `satrefine.testing` | `satsimp.build`, `satsimp.tools`, `satsimp.testing` |

- **Environment variables:** `SATREFINE_<NAME>` is now `SATSIMP_<NAME>`. The old
  names are still read when the new one is not set, with a `DeprecationWarning`:

  | Variable | What it selects |
  |---|---|
  | `SATSIMP_HANDLERS` (was `SATREFINE_HANDLERS`) | refine's handler package: `handlers_identities` (default) or `handlers_v3` |
  | `SATSIMP_BACKEND` (was `SATREFINE_BACKEND`) | the `ask` backend: `combined` (default), `strict`, `satassume`, `sympy`, `union` |
  | `SATSIMP_IDENTITIES` (was `SATREFINE_IDENTITIES`) | `generated` (default) or `live` rule tables |
  | `SATSIMP_STRICT_LOOPS` (was `SATREFINE_STRICT_LOOPS`) | `1`: a tripped termination guard raises |
  | `SATSIMP_FULL_TESTS`, `SATSIMP_TERMINATION_FUZZ` (were `SATREFINE_...`) | the long tests (see [docs/refine-testing.md](docs/refine-testing.md)) |

## refine: the refine layer as a yardstick

The refine method (`satsimp/methods/refine/`; the whole of `satrefine/` before the
rename) is the `reasoning` project's refine layer
(https://github.com/tilorc-bot/reasoning, branch `feature/refine`, commit
`12c3845`): SymPy's `refine` dispatcher vendored in `satrefine/_upstream.py` (since
phase 3 `satrefine/identities/compat/upstream.py`, now
`satsimp/methods/refine/identities/compat/upstream.py`)
plus 56 self-registering handlers in `satrefine/handlers/` (removed in phase 3,
see below), with the test harness and 470 tests in `tests/refine/`. Every
handler asks its predicate questions through one seam, the dispatcher's `ask`, and
`satsimp/engine/backend.py` chooses who answers:

| Backend | `ask` | Use |
|---|---|---|
| `sympy` | `sympy.assumptions.ask.ask` | the reference |
| `satassume` | `satassume.sympy_api.ask` alone; out-of-scope and undecided queries are `None`, so the handler does not fire | the strict measurement of this engine |
| `combined` | satassume; SymPy only where satassume has no model (matrix or unregistered custom predicates; a relation bound no theory interprets, such as a float, only for an engine with `uninterpreted="none"`: by default satassume reads such a relation as a free atom) or raises; assumptions satassume finds inconsistent raise | the default |
| `union` | satassume first, SymPy for every `None` (the `combined` behaviour before 2026-09-25) | measurements |
| `strict` | satassume only, routed as `combined` but `None` where `combined` would ask SymPy; inconsistent assumptions raise | satsimp without SymPy's assumption system |

Under `strict` and `satassume` satsimp never calls SymPy's `ask`; under `combined`, `union` and `sympy` it does.
Under every backend, Boolean nodes (relations, `And`/`Or`/`Not`, applied predicates)
are decided through it, not by SymPy's `Boolean._eval_refine`.

Select with `SATSIMP_BACKEND=<name>` (read at import; default `combined`),
`satsimp.engine.backend.set_backend(name)`, or
`with satsimp.engine.backend.using(name):`.

### The three handler packages

The same 56 registry keys were implemented three times, each package
self-contained and selected with `SATREFINE_HANDLERS` (now `SATSIMP_HANDLERS`). Phase 3 of the
identities work kept only v3, as the reference (`satrefine/reference/v3/`, now
`satsimp/methods/refine/reference/v3/`, still selected as `handlers_v3`), and removed `handlers` and `handlers_v2`
with their own tests: the last commit that has them with all their tests is `411038c` on
`ri/refactor-retire` (`git checkout 411038c` runs them as described here;
[docs/refine.md](docs/refine.md#three-implementations)).

| Package | Tests | Written by | What it is |
|---|---|---|---|
| `satrefine/handlers/` | `tests/refine/` (469; now run under the default package, see below) | the `reasoning` project's agents, then its verifiers | the original layer, copied from github.com/tilorc-bot/reasoning `feature/refine` at `12c3845`, one module per key, 33 modules |
| `satrefine/handlers_v2/` | `tests/refine_v2/` (161) | one Fable 5.1 agent, all 56 keys in one run, no verifier pass | a blind rewrite: the agent could not read the other packages, their tests or reports; 18 modules with shared helpers, rules named in the docstrings |
| `satrefine/handlers_v3/` (now `satsimp/methods/refine/reference/v3/`) | `tests/refine_v3/` (1,005) | nine agents (3 Fable, 6 Opus 5.5), one family each, then nine adversarial verifiers | a blind rewrite by a parallel team: one module per family (`trig`, `hyperbolic`, `inverse`, `power_exp_log`, `complex_parts`, `integer_funcs`, `combinatorial`, `minmax_deltas`, `matrices`), a shared `_common.py`, every rule stated with its precondition; the verifiers found and fixed 12 defects |

All three plug into the same dispatcher and backend switch, so any suite
runs against any package and every tool takes `--handlers`:

```bash
SATSIMP_HANDLERS=handlers_v3 PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine_v3
SATSIMP_HANDLERS=handlers_v3 PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine   # one package, another's suite
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satsimp.tools.refine_scoreboard --handlers handlers_v3 --suite tests/refine_v3
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satsimp.tools.refine_fuzz 2 1500 --handlers handlers_v3
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satsimp.tools.refine_oracle --handlers handlers_v3
```

How they compare, and what to build on, is in
[docs/refine.md](docs/refine.md#three-implementations). In short: the
original inherits three unsound matrix rules from SymPy and leaves relation
errors unguarded; both rewrites refuse those rules; the parallel team's
package is the only one with zero known defects after an adversarial pass
and covers the most on the branch-cut families, at about seven times the
single agent's cost, most of it the verifier pass. `handlers` was the
default until 2026-09-25, and the corpus numbers above were measured with it.

A fourth package, `satsimp/methods/refine/identities/` (`satrefine/identities/` before the
rename; selected as `handlers_identities`), implements the same nine
handler families as tables: identity rows with the branch bookkeeping written out
(`log`, powers, inverse functions, complex parts) and plain conditional rows
(the other families), run by a shared engine that matches rows, decides
their conditions through `ask`, and generates conditional rules from
identities under assumption profiles, each verified numerically. It is the
default package since 2026-09-25 (`satsimp.methods.refine.DEFAULT_HANDLERS`;
`SATSIMP_HANDLERS=handlers_v3` selects the reference). `tests/refine/`
runs against it: cases it handles worse are strict xfails pointing at
`tests/refine_identities/needs/test_default_*.py`
([docs/refine-testing.md](docs/refine-testing.md#needs-open-requests)); the tests of the
original package's internals were removed with it in phase 3. On the 1,736-case battery
recorded from the `handlers_v3` suite it gives 0 wrong and 0 crash and
matches v3 on 1,073 of v3's 1,086 rewrites, in about a third of v3's
per-family code. How it works is in [docs/refine.md](docs/refine.md), its
verification and numbers in [docs/refine-testing.md](docs/refine-testing.md).

Its layout (issue #13, then the split into engine and methods; see
[docs/architecture.md](docs/architecture.md)): `satsimp/engine/` is the shared
machinery that runs on every call (driver, termination guard, proving,
matching, rewriting, case splits, the `ask` backend, the engine's environment
switches); `satsimp/methods/refine/identities/` is refine's table package
(`rules/`: the families; `wiring.py`; `generated/`: the checked-in generated
tables; `compat/`: SymPy workarounds, matrix special cases, the vendored
dispatcher). `satsimp/build/` (table generation), `satsimp/tools/` (the tools)
and `satsimp/testing/` (the test harness) are offline: they import the
runtime, never the reverse, and are not distributed.

`satsimp/tools/refine_scoreboard.py` runs `tests/refine` under each backend and
compares outcomes per test: satassume in-scope gaps (pass under `sympy`, fail
under `satassume` with only in-scope queries asked), out-of-scope failures
(relations or matrix predicates were asked, so the handler could not fire),
satassume wins, combination wins (pass under `combined` only) and refine gaps
(fail everywhere). The per-test scope counts come from an observer in
`tests/refine/conftest.py` that classifies every query with `out_of_scope`.

```bash
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satsimp.tools.refine_scoreboard
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satsimp.tools.refine_scoreboard --backends sympy,satassume --show-failures satassume
SATSIMP_BACKEND=satassume PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine
```

Scoreboard on 2026-09-22 (SymPy at `ddbb536`, the `reasoning` pin):

| Backend | Passed | Failed | xfailed | Time |
|---|---|---|---|---|
| `sympy` | 462 | 7 | 4 | 118 s |
| `satassume` | 412 | 59 | 2 | 27 s |
| `combined` | 463 | 6 | 4 | 120 s |

All 59 tests that pass under `sympy` and fail under `satassume` asked
relations (`Q.eq/ne/lt/le/gt/ge`: Min/Max order rules, KroneckerDelta,
binomial/factorial at a literal, inverse-trig principal branches) or matrix
predicates (the eight matrix handlers): the out-of-scope categories, none of
them in-scope engine gaps. The six tests that fail under `sympy` and pass
under `satassume` only because the handler did not fire are SymPy's own
`ask` raising "inconsistent assumptions" on `Q.ge(x, y)` under
`Q.positive(x) & Q.negative(y)`, and returning `None` for `Max` of two
negative-infinite arguments. The one in-scope satassume win is
`refine(Abs(x - y), Q.positive(x) & Q.negative(y))`, where SymPy's `ask`
cannot decide `Q.negative(x - y)`. No test passes under `combined` only yet:
the handlers were written against the `reasoning` engine and SymPy, so
simplifications that need both engines are the work still to do.

## History

This code was developed on the `refine-identities` branch of
[tilorc-bot/satassume](https://github.com/tilorc-bot/satassume) and split out
with its history as satrefine; `#NNN` references in old commit messages point
at that repo. It was renamed satsimp, and split into `satsimp/engine/` and
`satsimp/methods/refine/`, so that refine becomes one method among others;
paths in older commit messages and in the numbers quoted in the docs are the
`satrefine/` paths of their time.

## License

BSD-3-Clause. The rule strings and several structural rules are copied or
adapted from SymPy (BSD); see `satsimp/LICENSE.sympy`.
