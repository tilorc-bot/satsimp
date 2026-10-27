"""``backend.ask_true``: satassume's True-only query for callers that act only
on a True (satassume #317), and ``provable(..., true_only=True)`` built on it.

A True is the same True as the full ``ask`` gives, inconsistent assumptions
still raise, and a patched ``ask`` or an observer sees the full query.  The
tests of the True-only query itself are skipped where the installed satassume
has no such modes (``backend._modes``: before #317, as at the pin).
"""
from __future__ import annotations

import pytest
from sympy import Abs, MatrixSymbol, Q, Symbol, sqrt

from satsimp import refine
from satsimp.engine import backend, hooks, prove
from satsimp.engine.prove import by_cases, provable
from satsimp.methods.refine.identities import compat
from satsimp.methods.refine.identities.compat import upstream

x, y = Symbol('x'), Symbol('y')
X = MatrixSymbol('X', 2, 2)

modes = pytest.mark.skipif(not backend._modes(), reason="satassume without true_only (before #317)")

QUERIES = [
    (Q.real(x), Q.positive(x)),             # True
    (Q.negative(x), Q.positive(x)),         # False
    (Q.positive(x), Q.real(x)),             # None
    (Q.positive(x + y), Q.positive(x) & Q.positive(y)),
    (Q.negative(x + y), Q.positive(x) & Q.positive(y)),
    (Q.nonzero(x), Q.zero(x)),
    (Q.gt(x, y), Q.gt(x, 1) & Q.lt(y, 0)),
    (Q.lt(x, y), Q.gt(x, 1) & Q.lt(y, 0)),
    (Q.invertible(X), Q.orthogonal(X)),     # no model in satassume: SymPy under combined
    (Q.singular(X), Q.orthogonal(X)),
]


@pytest.mark.parametrize("name", backend.BACKENDS)
@pytest.mark.parametrize("p,a", QUERIES)
def test_same_true(name, p, a):
    with backend.using(name):
        assert backend.ask_true(p, a) is (backend.ask(p, a) is True)


@pytest.mark.parametrize("name", ["satassume", "combined", "strict"])
def test_inconsistent_raises(name):
    """As the full ``ask`` does (``check_consistency="once"``)."""
    a = Q.positive(x) & Q.negative(x)
    with backend.using(name):
        for ask in (backend.ask, backend.ask_true):
            with pytest.raises(ValueError, match="nconsistent"):
                ask(Q.real(x + y), a)


def _spy(monkeypatch):
    import satassume.sympy_api as api
    calls = []
    real = api.ask

    def ask(*args, **kwargs):
        calls.append(kwargs)
        return real(*args, **kwargs)
    monkeypatch.setattr(api, "ask", ask)
    return calls


@modes
@pytest.mark.parametrize("name", ["satassume", "combined", "strict"])
def test_true_only_query(name, monkeypatch):
    calls = _spy(monkeypatch)
    with backend.using(name):
        assert backend.ask_true(Q.negative(x), Q.positive(x)) is False
    assert calls and all(c.get("true_only") is True and c.get("check_consistency") == "once"
                         for c in calls)


@pytest.mark.parametrize("name", ["union", "sympy"])
def test_full_query_elsewhere(name, monkeypatch):
    """``union`` keeps the full query: satassume's False stops SymPy from being asked."""
    calls = _spy(monkeypatch)
    with backend.using(name):
        backend.ask_true(Q.negative(x), Q.positive(x))
    assert not any(c.get("true_only") for c in calls)


def test_full_query_without_modes(monkeypatch):
    monkeypatch.setattr(backend, "_modes", dict)
    calls = _spy(monkeypatch)
    with backend.using("satassume"):
        assert backend.ask_true(Q.real(x), Q.positive(x)) is True
    assert calls == [{}]


@modes
def test_observers_see_true_only_answers(monkeypatch):
    """The suite's scope recorder is an observer: it must not turn the
    True-only query off (the trees would test only the full one)."""
    seen = []
    monkeypatch.setattr(backend, "observers", [lambda p, a, name, answer: seen.append(answer)])
    calls = _spy(monkeypatch)
    with backend.using("satassume"):
        assert backend.ask_true(Q.negative(x), Q.positive(x)) is False
        assert backend.ask_true(Q.real(x), Q.positive(x)) is True
    assert seen == [None, True]
    assert all(c.get("true_only") is True for c in calls)


def test_patched_ask_sees_every_query(monkeypatch):
    """A patched ``upstream.ask`` (the harness, a recording) gets the full query."""
    asked = []

    def ask(p, a=True):
        asked.append(p)
        return p == Q.real(x)
    monkeypatch.setattr(upstream, "ask", ask)
    assert compat._ask_true(Q.real(x), Q.positive(x)) is True
    assert compat._ask_true(Q.negative(x), Q.positive(x)) is False
    assert asked == [Q.real(x), Q.negative(x)]


def test_hook_plugged():
    assert hooks.base("ask_true") is compat._ask_true


def test_driver_memo(monkeypatch):
    """Within a top-level call (the driver's memo of ``ask``) a True-only
    answer is remembered, and a full answer asked first decides it."""
    from satsimp.engine.driver import _memoized
    decided = []
    real = backend.ask_true
    monkeypatch.setattr(backend, "ask_true", lambda p, a=True: decided.append(p) or real(p, a))
    monkeypatch.setattr(upstream, "ask", _memoized(compat._ask))
    a = Q.positive(x)
    assert hooks.ask_true(Q.real(x), a) is True
    assert hooks.ask_true(Q.real(x), a) is True
    assert upstream.ask(Q.negative(x), a) is False
    assert hooks.ask_true(Q.negative(x), a) is False
    assert decided == [Q.real(x)]


def test_refine_unchanged():
    for name in backend.BACKENDS:
        with backend.using(name):
            assert refine(Abs(x), Q.positive(x)) == x
            assert refine(sqrt(x**2), Q.real(x)) == Abs(x)


CONDITIONS = [
    Q.real(x) & Q.positive(x),
    Q.negative(x) | Q.real(x),
    Q.negative(x) | Q.zero(x),
    ~Q.negative(x),
    ~Q.real(x),
    Q.nonnegative(x) & ~Q.zero(x),
    by_cases(Q.negative(x), Q.real(sqrt(x))),
    Q.positive(x) & (Q.gt(x, 0) | Q.negative(x)),
]


@pytest.mark.parametrize("name", backend.BACKENDS)
@pytest.mark.parametrize("cond", CONDITIONS)
def test_provable_same_true(name, cond):
    with backend.using(name):
        full = provable(cond, Q.positive(x))
        assert (provable(cond, Q.positive(x), true_only=True) is True) is (full is True)


@modes
def test_refuted_atom_undecided():
    """The point: a refuted atom is not searched for, and comes back None
    (a ``Not`` keeps the full answer)."""
    with backend.using("satassume"):
        assert provable(Q.negative(x), Q.positive(x)) is False
        assert provable(Q.negative(x), Q.positive(x), true_only=True) is None
        assert provable(~Q.negative(x), Q.positive(x), true_only=True) is True
        assert prove._ask_atom(Q.negative(x), Q.positive(x), true_only=True) is None
