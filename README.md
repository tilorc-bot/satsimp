# satrefine

SymPy's `refine(expr, assumptions)` rewritten as rule tables, answered with the
[satassume](https://github.com/tilorc-bot/satassume) SAT-based `ask` engine.

The rules live in `satrefine/identities/rules/` (one module per family, e.g.
`trig.py`); how they are wired into handlers is `satrefine/identities/wiring.py`.
See [docs/refine.md](docs/refine.md) and [docs/refine-testing.md](docs/refine-testing.md).

## Install and test

```sh
pip install -e ".[dev]"
# the refine tests expect SymPy at the commit the gates use
pip install "sympy @ git+https://github.com/tilorc-bot/sympy@6379c4da69"
python -m pytest -q -n auto tests/refine_identities --ignore=tests/refine_identities/needs
```

The test trees share module basenames, so run each of `tests/refine_identities`,
`tests/refine` and `tests/refine_v3` separately.

## satrefine: the refine layer as a yardstick

`satrefine/` is the `reasoning` project's refine layer
(https://github.com/tilorc-bot/reasoning, branch `feature/refine`, commit
`12c3845`): SymPy's `refine` dispatcher vendored in `satrefine/_upstream.py` (since
phase 3 `satrefine/identities/compat/upstream.py`)
plus 56 self-registering handlers in `satrefine/handlers/` (removed in phase 3,
see below), with the test harness and 470 tests in `tests/refine/`. Every
handler asks its predicate questions through one seam, the dispatcher's `ask`, and
`satrefine/identities/compat/backend.py` chooses who answers:

| Backend | `ask` | Use |
|---|---|---|
| `sympy` | `sympy.assumptions.ask.ask` | the reference |
| `satassume` | `satassume.sympy_api.ask` alone; out-of-scope and undecided queries are `None`, so the handler does not fire | the strict measurement of this engine |
| `combined` | satassume; SymPy only where satassume has no model (matrix or unregistered custom predicates, a relation bound no theory interprets such as a float) or raises; assumptions satassume finds inconsistent raise | the default |
| `union` | satassume first, SymPy for every `None` (the `combined` behaviour before 2026-09-25) | measurements |

Select with `SATREFINE_BACKEND=<name>` (read at import; default `combined`),
`satrefine.identities.compat.backend.set_backend(name)`, or
`with satrefine.identities.compat.backend.using(name):`.

### The three handler packages

The same 56 registry keys were implemented three times, each package
self-contained and selected with `SATREFINE_HANDLERS`. Phase 3 of the
identities work kept only v3, as the reference (`satrefine/reference/v3/`,
still selected as `handlers_v3`), and removed `handlers` and `handlers_v2`
with their own tests: the last commit that has them with all their tests is `411038c` on
`ri/refactor-retire` (`git checkout 411038c` runs them as described here;
[docs/refine.md](docs/refine.md#three-implementations)).

| Package | Tests | Written by | What it is |
|---|---|---|---|
| `satrefine/handlers/` | `tests/refine/` (469; now run under the default package, see below) | the `reasoning` project's agents, then its verifiers | the original layer, copied from github.com/tilorc-bot/reasoning `feature/refine` at `12c3845`, one module per key, 33 modules |
| `satrefine/handlers_v2/` | `tests/refine_v2/` (161) | one Fable 5.1 agent, all 56 keys in one run, no verifier pass | a blind rewrite: the agent could not read the other packages, their tests or reports; 18 modules with shared helpers, rules named in the docstrings |
| `satrefine/handlers_v3/` (now `satrefine/reference/v3/`) | `tests/refine_v3/` (1,005) | nine agents (3 Fable, 6 Opus 5.5), one family each, then nine adversarial verifiers | a blind rewrite by a parallel team: one module per family (`trig`, `hyperbolic`, `inverse`, `power_exp_log`, `complex_parts`, `integer_funcs`, `combinatorial`, `minmax_deltas`, `matrices`), a shared `_common.py`, every rule stated with its precondition; the verifiers found and fixed 12 defects |

All three plug into the same dispatcher and backend switch, so any suite
runs against any package and every tool takes `--handlers`:

```bash
SATREFINE_HANDLERS=handlers_v3 PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine_v3
SATREFINE_HANDLERS=handlers_v3 PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine   # one package, another's suite
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_scoreboard --handlers handlers_v3 --suite tests/refine_v3
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_fuzz 2 1500 --handlers handlers_v3
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_oracle --handlers handlers_v3
```

How they compare, and what to build on, is in
[docs/refine.md](docs/refine.md#three-implementations). In short: the
original inherits three unsound matrix rules from SymPy and leaves relation
errors unguarded; both rewrites refuse those rules; the parallel team's
package is the only one with zero known defects after an adversarial pass
and covers the most on the branch-cut families, at about seven times the
single agent's cost, most of it the verifier pass. `handlers` was the
default until 2026-09-25, and the corpus numbers above were measured with it.

A fourth package, `satrefine/identities/` (selected as `handlers_identities`), implements the same nine
handler families as tables: identity rows with the branch bookkeeping written out
(`log`, powers, inverse functions, complex parts) and plain conditional rows
(the other families), run by a shared engine that matches rows, decides
their conditions through `ask`, and generates conditional rules from
identities under assumption profiles, each verified numerically. It is the
default package since 2026-09-25 (`satrefine.DEFAULT_HANDLERS`;
`SATREFINE_HANDLERS=handlers_v3` selects the reference). `tests/refine/`
runs against it: cases it handles worse are strict xfails pointing at
`tests/refine_identities/needs/test_default_*.py`
([docs/refine-testing.md](docs/refine-testing.md#needs-open-requests)); the tests of the
original package's internals were removed with it in phase 3. On the 1,736-case battery
recorded from the `handlers_v3` suite it gives 0 wrong and 0 crash and
matches v3 on 1,073 of v3's 1,086 rewrites, in about a third of v3's
per-family code. How it works is in [docs/refine.md](docs/refine.md), its
verification and numbers in [docs/refine-testing.md](docs/refine-testing.md).

Its layout (issue #13): `satrefine/identities/` is what runs on every
`refine` call (`core/`: driver, termination guard, proving, matching,
rewriting, case splits; `rules/`: the families; `generated/`: the checked-in
generated tables; `compat/`: SymPy workarounds, matrix special cases, the
`ask` backend; `config.py`: the environment switches). `satrefine/build/`
(table generation), `satrefine/tools/` (satrefine's tools) and
`satrefine/testing/` (the test harness) are offline: they import
`satrefine.identities`, never the reverse, and are not distributed.

`satrefine/tools/refine_scoreboard.py` runs `tests/refine` under each backend and
compares outcomes per test: satassume in-scope gaps (pass under `sympy`, fail
under `satassume` with only in-scope queries asked), out-of-scope failures
(relations or matrix predicates were asked, so the handler could not fire),
satassume wins, combination wins (pass under `combined` only) and refine gaps
(fail everywhere). The per-test scope counts come from an observer in
`tests/refine/conftest.py` that classifies every query with `out_of_scope`.

```bash
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_scoreboard
PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_scoreboard --backends sympy,satassume --show-failures satassume
SATREFINE_BACKEND=satassume PYTHONPATH=.:/path/to/sympy .venv/bin/python -m pytest -q tests/refine
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
with its history; `#NNN` references in old commit messages point at that repo.

## License

BSD-3-Clause. The rule strings and several structural rules are copied or
adapted from SymPy (BSD); see `satrefine/LICENSE.sympy`.
