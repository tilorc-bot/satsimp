# Architecture: one engine, several simplification methods

satsimp is a home for simplification methods written as rule tables, with
conditions proved through [satassume](https://github.com/tilorc-bot/satassume)'s
`ask`. `refine` is the first method (`satsimp.refine`, [refine.md](refine.md));
a trig simplifier is a likely next one. This page says what is shared, what
belongs to a method, and where a new method's parts go. Dependencies point one
way: satsimp imports satassume, never the reverse.

## Layout

```
satsimp/
  __init__.py      the public API: satsimp.refine (a method is imported on first use)
  engine/          shared, online: runs on every call of every method
    driver.py        the tree walk: rebuild from refined children, dispatch on the head,
                     generated table first, then the live handler, then a fallback
    guard.py         termination guard (every top-level call terminates)
    prove.py         conditions decided through ask, by cases where a row marks it
    match.py         pattern matching (head wildcards, rest symbols, sub-products)
    rewrite.py       rule rows and identity rows as handlers (Row, rule_handler, identity_handler)
    measure.py       orderings an identity rewrite must decrease
    split.py         case splits
    spec.py          a family as data: which parts (Rules, Identities) serve which key
    hooks.py         every way a method (or offline code) plugs into the engine
    backend.py       which ask answers: sympy, satassume, combined (default), union
    config.py        the engine's environment switches
  methods/         one package per method; a method imports the engine, never another method
    refine/          refine (docs/refine.md)
      __init__.py      refine, handlers_dict, the refine_* handlers; loads the handler package
      config.py        SATSIMP_HANDLERS: which handler package refine loads
      identities/      the default handler package (handlers_identities)
        rules/           the families as rows; _tables (the table helpers), _wraps, _simple
        wiring.py        which handlers serve which handlers_dict key, family by family
        generated/       checked-in generated rule tables (written offline)
        compat/          expected to change: the vendored SymPy refine dispatcher
                         (upstream.py), SymPy workarounds, the matrix family and matcher hook
      handlers_identities/, handlers_v3.py   the names SATSIMP_HANDLERS selects
      reference/v3/    refine's reference implementation (offline: measuring only)
  build/           offline: table generation (specialize, stages, verify, render; specs.py
                   holds refine's per-family settings)
  tools/           offline: scoreboard, battery, differential, fuzz, oracle, ablation, gates,
                   satassume bump; a method's tools are prefixed with its name (refine_*)
  testing/         offline: test harness and numeric oracle
satrefine/         deprecated alias of satsimp's refine (see the README)
tests/             refine's three test trees: refine_identities, refine, refine_v3
```

## Shared and per method

**Shared (the engine, `satsimp/engine/`).** The row format (`(lhs, rhs,
condition)` rule rows and identity rows), the matcher, the condition prover,
case splits, the driver and its termination guard, families as data
(`spec.py`), the `ask` backend and the switches for generated tables and
strict loops. None of it names a specific SymPy function or matrix type: the
heads a method needs the engine to treat specially are roles in `hooks.py`
(`opaque`, `conditional`, `modulus`, `step`, ...), set by the method.

**Shared offline (`build/`, `tools/`, `testing/`).** Table generation and
numeric verification, the battery/scoreboard/differential/fuzz tooling and the
test harness. They import the runtime, never the reverse, and are not in the
distribution. Today they are written for refine (`build/specs.py` is refine's
generation settings, `build` finds families through refine's `identities`
package, the tools are `refine_*`).

**Per method (`satsimp/methods/<name>/`).** The method's rule families (rows
only), its wiring (which handlers serve which key), its generated tables, its
SymPy workarounds, its entry point and its environment switches. For refine
that is also the vendored SymPy `refine` dispatcher with its `handlers_dict`
keys and the reference implementation it is measured against.

## Rules

Checked by `tests/refine_identities/test_import_direction.py`:

- The offline packages import the runtime (`satsimp`, `satsimp.engine`,
  `satsimp.methods`), never the reverse; refine runs in a subprocess in which
  importing them raises. The runtime does not import refine's reference
  implementation either (only its alias `handlers_v3` does).
- `satsimp.engine` imports no method; a method plugs in through `engine/hooks.py`.
- A method imports no other method (`satsimp.methods.<a>` never imports
  `satsimp.methods.<b>`): what two methods share moves into the engine.
- The engine names no specific SymPy function or matrix type (`backend.py`,
  which guards SymPy's own `ask` handlers for particular heads, is exempt).
- `import satsimp` imports no method: `satsimp.refine` is resolved on first use.

## Adding a method

A method `trigsimp` would go here:

| Part | Where |
|---|---|
| entry point (`satsimp.trigsimp`) | `satsimp/methods/trigsimp/__init__.py`, exported lazily by a branch in `satsimp/__init__.py`'s `__getattr__` |
| rule families (rows only) | `satsimp/methods/trigsimp/rules/` |
| wiring (rows to handlers) | `satsimp/methods/trigsimp/wiring.py`, building `engine.spec.Family` objects |
| SymPy workarounds, special cases | inside the method's package, never in the engine |
| environment switches | `satsimp/methods/trigsimp/config.py`, read with `engine.config.env` |
| generated tables | `satsimp/methods/trigsimp/generated/`, written by a `satsimp/tools/trigsimp_specialize.py`; its generation settings next to refine's in `build/` |
| tests | `tests/trigsimp/`, run in its own process like the refine trees, and added to CI |
| tools | `satsimp/tools/trigsimp_*.py`, sharing `satsimp/tools/lib` |

Refine must not slow down or change: a method is imported only when used, and
importing one registers nothing in another.

How a second method runs on the engine: the hooks are module attributes of
`engine/hooks.py` that refine sets at load, so another method runs the driver
inside `hooks.installed(dispatcher=..., ...)`, which sets every hook for the
block (its own `ask` and `handlers_dict` on the dispatcher, its own generated
tables in `hooks.generated`, `eval_method=None` to skip SymPy's `_eval_refine`
methods; what it does not name is the hook's default) and restores refine's
after it. A driver call under another dispatcher is a top-level call of its
own (its own result cache, firing counts and split budget), even when it is
made from inside a refine call; what it does share with that call is
the generated-table mode (`SATSIMP_IDENTITIES`, `driver.live()`) and whether a
case split is exploring (no split is tried then). Inside a block, everything,
`satsimp.refine` included, runs on the block's hooks: a method does not call
another method there. Import a method before entering another's block: one
first imported inside it sets its hooks there, and `installed()` keeps what it
set for afterwards but raises `LoadedInsideError`. Refine's registries and settings are never read
or changed by it; the check is refine's output and speed: the three test
trees, the battery comparison (`python -m satsimp.tools.refine_compare`) and
`refine_gates.sh`. Still refine-shaped: `build/` (table generation and
verification) takes refine's families, so a method's generated tables need the
method as a parameter there first.
