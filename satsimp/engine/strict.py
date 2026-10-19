"""Strict input: facts only as Q facts (``satsimp.refine(..., strict=True)``).

By default the assumptions a symbol was declared with count: SymPy's
constructors evaluate with them before refine sees the input (for a positive
``x``, ``sqrt(x**2)`` is already ``x``), and satassume's symbol template reads
``assumptions0``, the closure SymPy's old assumption system computes from the
declaration.  An undefined function declared with assumptions
(``Function('f', real=True)``) has no template, but SymPy's constructors read its
assumptions the same way (``conjugate(f(y))`` is ``f(y)``).

:func:`check_strict` rejects such input: it raises :class:`AssumptionSymbolError`
(a ``ValueError``) naming every ``Symbol``, ``Dummy`` or ``Wild`` (bound ones
included) with an assumption other than ``commutative=True`` and every applied
undefined function whose class has one.  Anything that is not a SymPy object
(``True`` as the assumptions, a number) is skipped.

This mirrors ``satassume.sympy_api.check_strict`` and ``AssumptionSymbolError``
(satassume PR #178: same objects, same message); satsimp keeps its own copy so it
does not depend on a satassume that has them.
"""
from __future__ import annotations

from typing import Any


class AssumptionSymbolError(ValueError):
    """Strict input (:mod:`satsimp.engine.strict`): the input holds symbols or
    undefined functions declared with old-style assumptions.  ``symbols`` are
    those objects (a ``Symbol``, ``Dummy`` or ``Wild``, or the class of an
    undefined function), in a fixed order."""

    def __init__(self, symbols: Any) -> None:
        self.symbols = tuple(symbols)
        names = ", ".join(f"{s} ({_declared(s)})" for s in self.symbols)
        super().__init__(f"strict mode: state assumptions as Q facts, not on {names}")


def _declared(s: Any) -> str:
    """The non-default assumptions of ``s``, as ``k=v`` (the declared ones where
    SymPy keeps them apart from their closure)."""
    if isinstance(s, type):
        a = s.default_assumptions  # boundary: the strict check itself
    else:
        a = getattr(s, "_assumptions_orig", None) or s.assumptions0  # boundary: the strict check itself
    return ", ".join(f"{k}={v}" for k, v in sorted(a.items())
                     if not (k == "commutative" and v))


def check_strict(*exprs: Any) -> None:
    """Raise :class:`AssumptionSymbolError` if one of ``exprs`` holds a symbol
    (``Symbol``, ``Dummy``, ``Wild``, bound ones included) with an assumption
    other than ``commutative=True``, or an applied undefined function whose
    class has one; anything not a SymPy object is skipped."""
    from sympy.core.basic import Basic
    from sympy.core.function import AppliedUndef
    from sympy.core.symbol import Symbol
    bad = set()
    for e in exprs:
        if not isinstance(e, Basic):
            continue
        for a in e.atoms(Symbol, AppliedUndef):
            if isinstance(a, Symbol):
                if a.assumptions0 != {"commutative": True}:  # boundary: the strict check itself
                    bad.add(a)
            elif _declared(type(a)):
                bad.add(type(a))
    if bad:
        raise AssumptionSymbolError(sorted(bad, key=lambda s: (str(s), isinstance(s, type))))
