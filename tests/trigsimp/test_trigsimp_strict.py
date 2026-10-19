"""``satsimp.trigsimp(..., strict=True)``: refine's strict input
(:mod:`satsimp.engine.strict`), then the ``strict`` backend."""
from __future__ import annotations

import contextlib

import pytest
from sympy import Function, Q, Symbol, cos, pi, sin, sqrt, tan

from satsimp import AssumptionSymbolError, trigsimp
from satsimp.engine import backend

x = Symbol("x")


def test_rejects_assumption_carrying_input():
    p = Symbol("p", positive=True)
    with pytest.raises(AssumptionSymbolError) as e:
        trigsimp(sin(p)**2 + cos(p)**2, strict=True)
    assert e.value.symbols == (p,)
    assert "p (positive=True)" in str(e.value)
    with pytest.raises(AssumptionSymbolError):         # in the assumptions too
        trigsimp(sin(x)**2, Q.positive(p), strict=True)
    with pytest.raises(AssumptionSymbolError):         # before the no-trig early return
        trigsimp(p + 1, strict=True)
    with pytest.raises(AssumptionSymbolError):
        trigsimp(sin(Function("f", real=True)(x)), strict=True)
    assert trigsimp(sin(p)**2 + cos(p)**2) == 1        # default: unchanged


def test_plain_symbols_under_the_strict_backend(monkeypatch):
    used = []
    using = backend.using

    @contextlib.contextmanager
    def spy(name):
        used.append(name)
        with using(name):
            yield
    monkeypatch.setattr(backend, "using", spy)
    assert trigsimp(sin(x)**2 + cos(x)**2, strict=True) == 1
    assert trigsimp(sin(x)/cos(x), strict=True) == tan(x)
    assert trigsimp(sqrt(1 - sin(x)**2), Q.gt(x, -pi/2) & Q.lt(x, pi/2), strict=True) == cos(x)
    assert used == ["strict"] * 3
    used.clear()
    assert trigsimp(sin(x)**2 + cos(x)**2) == 1
    assert used == []
