"""A second method on the engine: :func:`satsimp.engine.hooks.installed` runs the driver
with that method's hooks for a block, and leaves refine's untouched (``docs/architecture.md``)."""
from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest
from sympy import Q, cos, log, sin, symbols

from satsimp import refine
from satsimp.engine import backend, driver, hooks
from satsimp.methods.refine.identities.compat import upstream
from satsimp.methods.refine.identities.compat.upstream import handlers_dict

x, y, n = symbols("x y n")


def _toy(asked: list | None = None) -> SimpleNamespace:
    """A method whose only rule is ``sin(u) -> cos(u)``."""
    def ask(proposition, assumptions=True):
        if asked is not None:
            asked.append(proposition)
        return backend.ask(proposition, assumptions)
    return SimpleNamespace(ask=ask, handlers_dict={"sin": lambda e, a: cos(e.args[0])})


def _run(method: SimpleNamespace, expr, assumptions=True):
    with hooks.installed(dispatcher=method, eval_method=None):
        return driver.refine(expr, assumptions)


def test_only_the_methods_handlers_run():
    assert _run(_toy(), sin(x) + log(x), Q.negative(x)) == cos(x) + log(x)   # no refine row
    assert refine((-x)**n, Q.even(n)) == x**n                                 # Pow._eval_refine
    assert _run(_toy(), (-x)**n, Q.even(n)) == (-x)**n                       # not called
    assert refine(log(x), Q.negative(x)) != log(x)


def test_refines_hooks_are_restored():
    before = {name: getattr(hooks, name) for name in hooks._defaults()}
    _run(_toy(), sin(x))
    with pytest.raises(ZeroDivisionError), hooks.installed(dispatcher=_toy()):
        1/0
    assert {name: getattr(hooks, name) for name in hooks._defaults()} == before
    assert hooks.dispatcher.handlers_dict is handlers_dict
    assert driver.generated_handlers is hooks.generated and hooks.generated


def test_unknown_hook_is_refused():
    with pytest.raises(TypeError), hooks.installed(dispatchr=_toy()):
        pass


def test_a_call_from_inside_refine_is_its_own_top_level_call():
    """A method called from a refine handler gets its own cache and budget, and
    refine's call goes on with its own ``ask`` afterwards."""
    from sympy import Function

    class Probe(Function):
        pass

    seen = []

    def probe(expr, assumptions):
        seen.append(_run(_toy(), sin(expr.args[0])))
        return expr.args[0]

    handlers_dict["Probe"] = probe
    try:
        assert refine(Probe(log(x)), Q.negative(x)) == refine(log(x), Q.negative(x))
    finally:
        del handlers_dict["Probe"]
    assert seen and all(s.func is cos for s in seen)
    assert not driver._calls and not driver._dispatchers
    assert upstream.ask is not None and not hasattr(upstream.ask, "__wrapped__")
    assert upstream.ask.__name__ != "memo_ask"                                # refine's ask restored
    assert driver.splits_left[0] == driver.MAX_SPLITS


_LOADED_INSIDE = """
from types import SimpleNamespace
from sympy import I, Q, log, pi, symbols
from satsimp.engine import driver, hooks
x = symbols("x")
toy = SimpleNamespace(ask=lambda p, a=True: None, handlers_dict={})
try:
    with hooks.installed(dispatcher=toy, eval_method=None):
        import satsimp
        satsimp.refine(log(x), Q.negative(x))
except hooks.LoadedInsideError:
    pass
else:
    raise SystemExit("no LoadedInsideError")
assert satsimp.refine(log(x), Q.negative(x)) == log(-x) + I*pi
print("ok")
"""


def test_a_method_imported_inside_a_block_is_refused_and_still_works_after():
    out = subprocess.run([sys.executable, "-c", _LOADED_INSIDE], capture_output=True, text=True)
    assert out.stdout.strip() == "ok", out.stderr
