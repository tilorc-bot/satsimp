"""Strict input: ``satsimp.refine(expr, assumptions, strict=True)`` takes facts only as
Q facts (:mod:`satsimp.engine.strict`) and runs under the ``strict`` backend."""
from __future__ import annotations

import warnings

import pytest
from sympy import Abs, Dummy, Function, Integral, Q, Symbol, Wild, exp, sin, sqrt

import satsimp
from satsimp import AssumptionSymbolError, refine
from satsimp.engine import backend, driver
from satsimp.engine.strict import check_strict

x = Symbol("x")


def test_exported():
    assert issubclass(AssumptionSymbolError, ValueError)
    assert "AssumptionSymbolError" in satsimp.__all__
    from satsimp.engine import strict
    assert satsimp.AssumptionSymbolError is strict.AssumptionSymbolError


def test_plain_symbols_with_q_facts():
    assert refine(Abs(x), Q.positive(x), strict=True) == x
    assert refine(sqrt(x**2), Q.real(x), strict=True) == Abs(x)
    assert refine(Abs(x), True, strict=True) == Abs(x)
    assert refine(Abs(Symbol("c", commutative=True)), Q.real(x), strict=True) == Abs(Symbol("c"))
    check_strict(True, False, None, 3, Q.real(x))


def test_rejects_symbol_assumptions():
    p = Symbol("p", positive=True)
    assert refine(Abs(x) + p, Q.negative(x)) == p - x      # default: the declaration counts
    with pytest.raises(AssumptionSymbolError) as e:
        refine(Abs(x) + p, Q.negative(x), strict=True)
    assert e.value.symbols == (p,)
    assert "p (positive=True)" in str(e.value)
    with pytest.raises(AssumptionSymbolError):              # in the assumptions too
        refine(Abs(x), Q.negative(x) & Q.real(p), strict=True)


@pytest.mark.parametrize("s", [Dummy("d", integer=True), Wild("w", real=True),
                               Symbol("z", positive=False), Symbol("A", commutative=False)])
def test_rejects_any_non_default_assumption(s):
    with pytest.raises(AssumptionSymbolError) as e:
        refine(sin(s), Q.real(x), strict=True)
    assert e.value.symbols == (s,)


def test_nested_and_bound():
    p, n = Symbol("p", positive=True), Dummy("n", integer=True)
    with pytest.raises(AssumptionSymbolError) as e:
        refine(exp(x + sin(p)), Q.real(x) & (Q.positive(x) | Q.zero(sin(p) + n)), strict=True)
    assert set(e.value.symbols) == {p, n}
    with pytest.raises(AssumptionSymbolError) as e:         # a bound symbol counts too
        refine(Integral(n, (n, 0, x)), Q.positive(x), strict=True)
    assert e.value.symbols == (n,)


def test_undefined_function_assumptions():
    f, g = Function("f", real=True), Function("g")
    with pytest.raises(AssumptionSymbolError) as e:
        refine(Abs(f(x)), True, strict=True)
    assert e.value.symbols == (f,)
    assert "real=True" in str(e.value)       # SymPy keeps only the closure of a class's assumptions
    assert refine(Abs(g(x)), Q.positive(g(x)), strict=True) == g(x)


def test_checked_before_any_work(monkeypatch):
    """The check comes first: no cache, no backend switch, no refinement before it."""
    p = Symbol("p", positive=True)
    assert refine(Abs(p*x), Q.real(x)) == p*Abs(x)            # the same input refined (and cached) before
    calls = []
    monkeypatch.setattr(driver, "_refine", lambda *a: calls.append(a))
    monkeypatch.setattr(backend, "using", lambda name: calls.append(name))
    with pytest.raises(AssumptionSymbolError):
        refine(Abs(p*x), Q.real(x), strict=True)
    assert calls == []


def test_runs_under_the_strict_backend():
    seen = []

    def observe(proposition, assumptions, name, answer):
        seen.append(name)
    before = backend.current()
    backend.observers.append(observe)
    try:
        with backend.using("combined"):
            assert refine(Abs(x)*Abs(sin(x)), Q.positive(x) & Q.real(sin(x)), strict=True) != Abs(x)*Abs(sin(x))
            assert backend.current() == "combined"           # restored after the call
            with pytest.raises(AssumptionSymbolError):
                refine(Abs(Symbol("p", positive=True)), strict=True)
            assert backend.current() == "combined"
    finally:
        backend.observers.remove(observe)
    assert seen and set(seen) == {"strict"}
    assert backend.current() == before


def test_satrefine_alias():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import satrefine
    assert satrefine.refine(Abs(x), Q.positive(x), strict=True) == x
    with pytest.raises(AssumptionSymbolError):
        satrefine.refine(Abs(Symbol("p", positive=True)), strict=True)


def test_a_strict_call_inside_a_refine_call_shares_nothing_with_it():
    """``strict=True`` from a handler is its own top-level call: it neither reuses
    the outer call's (SymPy-backed) answers nor leaves its own for the outer call."""
    from sympy import Function, MatrixSymbol, S, Tuple
    from satsimp.methods.refine.identities.compat.upstream import handlers_dict

    class Probe(Function):
        pass

    X = MatrixSymbol("X", 3, 3)
    q, a = Q.invertible(X), Q.orthogonal(X)
    handlers_dict["Probe"] = lambda e, assumptions: satsimp.refine(q, assumptions, strict=True)
    try:
        assert satsimp.refine(q, a) is S.true                              # combined: SymPy decides it
        assert satsimp.refine(q, a, strict=True) == q                      # strict: satassume alone
        assert tuple(satsimp.refine(Tuple(q, Probe(X)), a)) == (S.true, q)
        assert tuple(satsimp.refine(Tuple(Probe(X), q), a)) == (q, S.true)
    finally:
        del handlers_dict["Probe"]
