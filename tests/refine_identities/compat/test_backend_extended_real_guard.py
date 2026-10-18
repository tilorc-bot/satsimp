"""The combined backend's guard on SymPy's ``Q.extended_real`` handler for powers.

SymPy calls ``sqrt(z)`` extended real for a negative ``z``; the guard
(``_extended_real_true_checked`` in ``satsimp/engine/backend.py``)
keeps a ``True`` for a power only for an integer exponent, or an extended
nonnegative base and a real exponent.  Without it, ``conjugate(a) -> a`` for
``Q.extended_real(a)`` fires on ``sqrt(z)`` when satassume leaves the query
open (a relation against a float) (issue #67).
"""
from __future__ import annotations

from sympy import Q, Symbol, conjugate, sqrt

from satsimp import refine
from satsimp.engine import backend

z = Symbol('z')


def test_conjugate_of_root_of_negative():
    with backend.using("combined"):
        assert refine(conjugate(sqrt(z)), Q.negative(z) & Q.le(z, 1.5)) == -sqrt(z)


def test_guarded_answer():
    assert backend._guarded_sympy_ask(Q.extended_real(sqrt(z)), Q.negative(z)) is None
    assert backend._guarded_sympy_ask(Q.extended_real(z**2), Q.negative(z)) is True


def test_guarded_answer_without_ask_recursive(monkeypatch):
    # SymPy as 1.14 has it (see test_backend_nonzero_guard.py's without_ask_recursive)
    from importlib import import_module
    monkeypatch.delattr(import_module("sympy.assumptions.ask"), "_ask_recursive", raising=False)
    backend._handler_ask.cache_clear()
    try:
        test_guarded_answer()
    finally:
        backend._handler_ask.cache_clear()
