"""Substitution rows: identities applied inside a sum, kept when the sum gets smaller.

A substitution row ``(lhs, rhs, condition)`` has a *monomial* left side: a
product of integer powers of applied functions over pattern symbols
(``sin(u)**2``, ``sin(u)/cos(u)``, ``sin(u)*cos(v)``).  It states
``lhs = rhs`` wherever ``condition`` holds, with ``rhs`` defined wherever
``lhs`` is.

:func:`substitution_handler` rewrites a sum (a product is a sum of one term):
a *site* is a term in which the left side occurs, its factors binding
distinct factors of the term with exponents of the same sign and at least as
large; it occurs there ``j`` times, the most the exponents allow
(``sin(x)**5`` holds ``sin(x)**2`` twice).  A candidate replaces the
occurrences at one site, at every site of one binding, or at every site of
the row; the replaced terms are expanded (the integer power of the right
side at the top, then the rest of the term distributed over it) and the
terms added again.  The
candidate with the smallest measure is returned when it is smaller than the
sum's; a site counts only when its row's condition is provable.
"""
from __future__ import annotations

from typing import Any, Callable, Iterator

from sympy import Add, Integer, Mul, Pow
from sympy.core.function import expand_multinomial

from satsimp.engine.match import bindings, subst
from satsimp.engine.prove import provable

MAX_SITES = 64
"""Sites considered per row and sum: a bound on the work for a long sum."""


def _pattern(lhs: Any) -> list[tuple[Any, int]]:
    """The left side as ``[(base, exponent)]``."""
    out = []
    for factor in Mul.make_args(lhs):
        base, e = factor.as_base_exp()
        if not isinstance(e, Integer):
            raise ValueError(f"substitution row with a non-integer exponent: {lhs}")
        out.append((base, int(e)))
    return out


def _powers(term: Any, heads: tuple) -> dict:
    """The factors of ``term`` that are integer powers of an application of ``heads``, as base -> exponent."""
    out: dict = {}
    for factor in Mul.make_args(term):
        base, e = factor.as_base_exp()
        if isinstance(base, heads) and isinstance(e, Integer):
            out[base] = out.get(base, 0) + int(e)
    return out


def _merge(b: dict, nb: dict) -> dict | None:
    merged = dict(b)
    for k, v in nb.items():
        if merged.setdefault(k, v) != v:
            return None
    return merged


def _sites(pattern: list, powers: dict, assumptions: Any) -> Iterator[tuple[dict, int]]:
    """``(binding, j)`` for each way the pattern's factors bind distinct factors of the term."""
    def extend(k: int, b: dict, used: dict) -> Iterator[tuple[dict, int]]:
        if k == len(pattern):
            yield b, min(powers[base] // p for base, p in used.items())
            return
        pbase, p = pattern[k]
        for base, e in powers.items():
            if base in used or e*p <= 0 or abs(e) < abs(p):
                continue
            for nb in bindings(pbase, base, assumptions):
                merged = _merge(b, nb)
                if merged is not None:
                    yield from extend(k + 1, merged, {**used, base: p})
    yield from extend(0, {}, {})


def _replaced(term: Any, lhs: Any, rhs: Any, j: int) -> Any:
    """``term`` with ``lhs**j`` replaced by ``rhs**j``: ``rhs**j`` expanded at
    the top and the rest of the term distributed over it as one factor, so
    that ``(x + 1)*sin(x)**2`` gives ``(x + 1) - (x + 1)*cos(x)**2``, whose
    terms collect with ``(x + 1)*cos(x)**2``."""
    rest = term*Pow(lhs, -j)
    return Add(*[rest*t for t in Add.make_args(expand_multinomial(Pow(rhs, j), deep=False))])


def substitution_handler(rows: list, measure: Callable[[Any], tuple], heads: tuple) -> Callable[[Any, Any], Any]:
    """A handler from substitution rows (see the module docstring); ``heads``
    are the applied functions the left sides are made of."""
    table = [(lhs, rhs, cond, _pattern(lhs)) for lhs, rhs, cond in rows]

    def handler(expr: Any, assumptions: Any) -> Any:
        terms = list(Add.make_args(expr))
        if any(t.args_cnc()[1] for t in terms):     # a noncommutative factor: left alone
            return None
        powers = [_powers(t, heads) for t in terms]
        if not any(powers):
            return None
        best, best_m = None, measure(expr)
        for lhs, rhs, cond, pattern in table:
            sites = []        # (term index, binding key, binding, j)
            for i, pw in enumerate(powers):
                if len(sites) >= MAX_SITES:
                    break
                for b, j in _sites(pattern, pw, assumptions):
                    sites.append((i, frozenset(b.items()), b, j))
                    if len(sites) >= MAX_SITES:
                        break
            if not sites:
                continue
            holds: dict = {}
            sites = [s for s in sites if _holds(holds, s[1], s[2], cond, assumptions)]
            by_binding: dict = {}
            for s in sites:
                by_binding.setdefault(s[1], []).append(s)
            choices = [[s] for s in sites] + [g for g in by_binding.values() if len(g) > 1]
            if len(by_binding) > 1:
                choices.append(sites)
            for chosen in choices:
                cand = _candidate(terms, chosen, lhs, rhs)
                if cand is None:
                    continue
                m = measure(cand)
                if m < best_m:
                    best, best_m = cand, m
        return best

    handler.rows = rows      # type: ignore[attr-defined]
    handler.kind = "substitution"  # type: ignore[attr-defined]
    return handler


def _holds(cache: dict, key: Any, b: dict, cond: Any, assumptions: Any) -> bool:
    if key not in cache:
        cache[key] = cond is True or provable(subst(cond, b), assumptions) is True
    return cache[key]


def _candidate(terms: list, chosen: list, lhs: Any, rhs: Any) -> Any:
    """The sum with the chosen sites replaced; of two sites in one term that
    share a factor, the first.  ``None`` when nothing is replaced."""
    new = list(terms)
    used: dict = {}
    for i, _, b, j in chosen:
        l, r = subst(lhs, b), subst(rhs, b)
        bases = {f.as_base_exp()[0] for f in Mul.make_args(l)}
        if used.get(i, set()) & bases:
            continue
        used.setdefault(i, set()).update(bases)
        new[i] = _replaced(new[i], l, r, j)
    return Add(*new) if used else None
