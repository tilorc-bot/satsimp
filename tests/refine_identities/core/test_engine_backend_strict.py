"""The ``strict`` backend (satassume only) and the routing of Boolean nodes through the backend."""
from __future__ import annotations

import sys

import pytest
from sympy import Eq, MatrixSymbol, Piecewise, Q, symbols
import sympy.assumptions

from satsimp import refine
from satsimp.engine import backend

x, y = symbols("x y")
X = MatrixSymbol("X", 2, 2)


@pytest.fixture
def no_sympy_ask(monkeypatch):
    """SymPy's ``ask`` raises if anything calls it."""
    def trap(*args, **kwargs):
        raise AssertionError("SymPy's ask was called")
    monkeypatch.setattr(sys.modules["sympy.assumptions.ask"], "ask", trap)
    monkeypatch.setattr(sympy.assumptions, "ask", trap)


def test_strict_answers_as_satassume_routes():
    with backend.using("strict"):
        assert backend.ask(Q.positive(x + 1), Q.positive(x)) is True
        assert backend.ask(Q.positive(x), Q.real(x)) is None
        assert backend.ask(Q.symmetric(X), Q.diagonal(X)) is None      # combined asks SymPy here
        with pytest.raises(ValueError, match="nconsistent"):
            backend.ask(Q.positive(x), Q.positive(x) & Q.negative(x))
    assert backend.ask(Q.symmetric(X), Q.diagonal(X)) is True          # combined, the default


@pytest.mark.parametrize("expr, assumptions, expected", [
    (x > 0, Q.positive(x), True),
    (Eq(x, y), Q.gt(x, y), False),
    (Q.positive(x) & Q.negative(y), Q.positive(x) & Q.negative(y), True),
    (Piecewise((1, x > 0), (2, True)), Q.positive(x), 1),
])
def test_boolean_nodes_are_decided_through_the_backend(no_sympy_ask, expr, assumptions, expected):
    with backend.using("strict"):
        assert refine(expr, assumptions) == expected
