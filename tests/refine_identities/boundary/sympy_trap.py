"""Runtime trap for SymPy reasoning reached from satsimp code (``test_sympy_boundary.py``).

Copied from the SymPy boundary audit's trap (``sat-release/trap/sympy_trap.py``, a
pytest plugin for satassume and satsimp) and adapted the way satassume's
``tests/_sympy_trap.py`` (satassume PR #178) adapted it: no pytest plugin
(:func:`install` runs in the corpus subprocess, ``trap_corpus.py``, before satsimp is
imported, because it patches SymPy process-wide), an explicit allowlist, a
``BaseException`` in raise mode, and no ``direct_old`` event (``.is_<fact>`` reads by
package code are out of scope here).

Package code is every module under the directories :func:`install` is given (the
corpus passes satsimp's, satrefine's and satassume's, without satsimp's offline
packages: ``satsimp/tools``, ``satsimp/testing``, ``satsimp/build``).  Each event is attributed to the
innermost package frame (the *site*) and to the function the package called there (the
*entry*: the frame just below the site; ``None`` when the site called the trapped
function itself):

* ``forbidden``: a call of SymPy's simplification or assumption reasoning
  (:data:`FORBIDDEN_FUNCS`, wrapped in their defining modules and rebound in every
  loaded ``sympy.*`` module, so ``from sympy import simplify`` bindings, SymPy's local
  imports and method calls all reach the wrapper) or of one of
  :data:`FORBIDDEN_METHODS` on any SymPy class that defines it.  An event whose entry
  is SymPy's own construction or evaluation (:data:`CONSTRUCTION`) or whose name is a
  hook that decides nothing (:data:`HARMLESS`) is allowed, and so is one whose entry
  builds expressions (:data:`BUILDING`) when a SymPy ``eval`` made the call.  In raise mode
  (``SYMPY_TRAP_MODE=raise``, the default) any other raises :class:`TrapError`;
* ``symbol_assumption``: an old-assumption property of a symbol declared with
  assumptions returned True or False while package code was on the stack;
* ``pkg_makes_assumption_symbol``: package code made a ``Symbol``/``Dummy``/``Wild``
  with assumptions.

The last two are recorded, not raised.  Every event is recorded in :data:`EVENTS`
(with a count), also the raising ones: :class:`TrapError` is a ``BaseException`` so
that no ``except Exception`` in the package can hide it, but the record does not
depend on that.
"""
from __future__ import annotations

import importlib
import os
import sys
import threading
import types

MODE = os.environ.get("SYMPY_TRAP_MODE", "raise")

#: entries (what package code called) that are SymPy's own construction or evaluation:
#: a forbidden call below them is SymPy evaluating an expression satsimp built, not
#: satsimp's reasoning.  Keep this small, one reason per entry, and add an entry only
#: for a path the corpus reaches (satassume's list also has the arithmetic operators'
#: decorators, ``sympy.core.decorators._func`` and friends).
CONSTRUCTION = {
    # cached constructors and evaluation (Add, Mul, Pow and the functions go through cacheit)
    "sympy.core.cache.wrapper": "a cached constructor (cacheit)",
    # abs(e) is Abs(e)
    "sympy.core.expr.__abs__": "abs() builds Abs",
    # substitution rebuilds every changed node with func(*args)
    "sympy.core.basic.xreplace": "a func(*args) rebuild (xreplace)",
}
#: entry suffixes that are construction: any ``__new__`` (``Mul(...)``, ``Pow(...)``)
CONSTRUCTION_SUFFIXES = {".__new__": "a constructor"}
#: entries that are not constructors but build expressions on the way: allowed only when
#: the forbidden function's direct caller is a SymPy function class's ``eval`` (the
#: automatic evaluation of a node they built: ``exp.eval`` calls ``logcombine``,
#: ``Abs.eval`` and ``sign.eval`` call ``signsimp``)
BUILDING = {
    "sympy.core.function.expand_mul": "expansion rebuilds the terms it multiplies out",
    "sympy.core.function.count_ops": "counting reads numerator and denominator (as_numer_denom builds them)",
}
#: forbidden names that decide nothing: the driver's fallback for SymPy ``_eval_refine``
#: hooks that do not ask (satsimp/engine/driver.py; the ones that ask, Pow's, exp's and
#: Boolean's, are replaced through hooks.eval_refine and never called)
HARMLESS = {
    "Symbol._eval_refine": "returns self",
    "Predicate._eval_refine": "returns self",
}

FORBIDDEN_FUNCS = [("sympy.simplify.simplify", n) for n in (
    "simplify", "nsimplify", "logcombine", "posify", "separatevars", "besselsimp",
    "hypersimp", "nc_simplify", "kroneckersimp", "signsimp", "product_simplify",
    "sum_simplify")] + [
    ("sympy.simplify.trigsimp", "trigsimp"), ("sympy.simplify.trigsimp", "exptrigsimp"),
    ("sympy.simplify.trigsimp", "futrig"),
    ("sympy.simplify.powsimp", "powsimp"), ("sympy.simplify.powsimp", "powdenest"),
    ("sympy.simplify.radsimp", "radsimp"), ("sympy.simplify.radsimp", "rad_rationalize"),
    ("sympy.simplify.ratsimp", "ratsimp"), ("sympy.simplify.ratsimp", "ratsimpmodprime"),
    ("sympy.simplify.sqrtdenest", "sqrtdenest"),
    ("sympy.simplify.combsimp", "combsimp"), ("sympy.simplify.gammasimp", "gammasimp"),
    ("sympy.simplify.fu", "fu"),
    ("sympy.polys.polytools", "cancel"), ("sympy.polys.polytools", "factor"),
    ("sympy.polys.polytools", "gcd"), ("sympy.polys.polytools", "groebner"),
    ("sympy.polys.polytools", "nroots"), ("sympy.polys.polytools", "real_roots"),
    ("sympy.polys.rationaltools", "together"),
    ("sympy.polys.numberfields.minpoly", "minimal_polynomial"),
    ("sympy.solvers.solvers", "solve"), ("sympy.solvers.solveset", "solveset"),
    ("sympy.assumptions.ask", "ask"), ("sympy.assumptions.refine", "refine"),
    ("sympy.assumptions.satask", "satask"),
    ("sympy.assumptions.lra_satask", "lra_satask"),
]
#: methods wrapped on every SymPy class that defines them
FORBIDDEN_METHODS = ("equals", "simplify", "refine", "_eval_refine", "cancel", "factor",
                     "nsimplify", "trigsimp", "radsimp", "powsimp", "ratsimp", "combsimp",
                     "gammasimp", "together")

EVENTS: dict = {}   # (kind, name, site, entry, caller) -> {"kind", ..., "count"}
PKG: tuple = ()     # the package directories, each with a trailing separator
OUTSIDE: tuple = () # directories under them that are not package code
_HERE = os.path.abspath(__file__)
_guard = threading.local()


class TrapError(BaseException):
    pass


def allowed(name: str, entry: str | None, caller: str) -> str | None:
    """The reason a ``forbidden`` event is allowed, else None.  ``caller`` is the
    function that called the forbidden one (``module.name``)."""
    if name in HARMLESS:
        return HARMLESS[name]
    if entry is None:
        return None
    if entry in CONSTRUCTION:
        return CONSTRUCTION[entry]
    for suffix, why in CONSTRUCTION_SUFFIXES.items():
        if entry.endswith(suffix):
            return why
    if entry in BUILDING and caller.startswith("sympy.") and caller.endswith(".eval"):
        return BUILDING[entry]
    return None


def _site(start: int) -> tuple:
    """``(site, entry)`` of the innermost package frame above ``start``."""
    f = sys._getframe(start)
    below = None    # the frame just below the innermost package frame: what the package called
    while f is not None:
        fn = f.f_code.co_filename
        if fn.startswith(PKG) and not fn.startswith(OUTSIDE):
            entry = below and f"{below.f_globals.get('__name__', '?')}.{below.f_code.co_name}"
            return f"{_short(fn)}:{f.f_lineno} {f.f_code.co_name}", entry
        if fn != _HERE:
            below = f
        f = f.f_back
    return None, None


def _short(fn: str) -> str:
    for d in PKG:
        if fn.startswith(d):
            return os.path.join(os.path.basename(os.path.dirname(d)), fn[len(d):])
    return fn


def _record(kind: str, name: str, site: str, entry: str | None, **extra) -> dict:
    key = (kind, name, site, entry, extra.get("caller"))
    ev = EVENTS.get(key)
    if ev is None:
        ev = EVENTS[key] = {"kind": kind, "name": name, "site": site, "entry": entry,
                            "count": 0, **extra}
    ev["count"] += 1
    return ev


def _wrap(name: str, fn):
    def wrapper(*a, **k):
        if getattr(_guard, "busy", False):
            return fn(*a, **k)      # nested in a call already recorded
        site, entry = _site(2)
        if site is None:
            return fn(*a, **k)
        f = sys._getframe(1)
        caller = f"{f.f_globals.get('__name__', '?')}.{f.f_code.co_name}"
        why = allowed(name, entry, caller)
        _record("forbidden", name, site, entry, caller=caller, allowed=why)
        if why is None and MODE == "raise":
            raise TrapError(f"{name} reached from {site} (entry {entry}, called by {caller})")
        _guard.busy = True          # nested reasoning belongs to this call
        try:
            return fn(*a, **k)
        finally:
            _guard.busy = False
    wrapper.__wrapped__ = fn
    wrapper.__name__ = getattr(fn, "__name__", name)
    wrapper.__doc__ = getattr(fn, "__doc__", None)
    return wrapper


def _subclasses(c) -> set:
    out, todo = {c}, [c]
    while todo:
        for s in todo.pop().__subclasses__():
            if s not in out:
                out.add(s)
                todo.append(s)
    return out


def _declared(sym) -> dict:
    a = getattr(sym, "_assumptions_orig", None)
    if a is None:
        a = sym.assumptions0
    return {k: v for k, v in a.items() if v is not None and k != "commutative"}


def install(pkg_dirs, outside=()) -> None:
    """Patch SymPy; ``pkg_dirs`` are the directories of the package code, ``outside``
    directories under them that are not (offline tools, test fixtures)."""
    global PKG, OUTSIDE
    PKG = tuple(os.path.join(os.path.abspath(d), "") for d in pkg_dirs)
    OUTSIDE = tuple(os.path.join(os.path.abspath(d), "") for d in outside)
    # the wrappers add frames: keep the package's own RecursionError guards
    # from firing earlier than they would untrapped
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4000))
    import sympy
    from sympy.core.assumptions import _assume_defined, as_property
    from sympy.core.basic import Basic
    from sympy.core.symbol import Symbol

    wrapped = {}
    for mod, attr in FORBIDDEN_FUNCS:
        try:
            m = importlib.import_module(mod)
        except ImportError:         # not in this SymPy version
            continue
        fn = getattr(m, attr, None)
        if fn is None:
            continue
        wrapped[id(fn)] = w = _wrap(f"{mod.rsplit('.', 1)[-1]}.{attr}", fn)
        setattr(m, attr, w)
    # rebind already-imported names (from x import f) in every loaded sympy module
    for name, m in list(sys.modules.items()):
        if name.startswith("sympy") and m is not None:
            for k, v in list(vars(m).items()):
                if id(v) in wrapped:
                    setattr(m, k, wrapped[id(v)])
    for c in _subclasses(Basic):
        if c.__module__.startswith("sympy"):
            for meth in FORBIDDEN_METHODS:
                fn = c.__dict__.get(meth)
                if isinstance(fn, types.FunctionType):
                    setattr(c, meth, _wrap(f"{c.__name__}.{meth}", fn))

    def wrap_prop(pname, prop):
        fget = prop.fget

        def getit(self):
            v = fget(self)
            if v is not None and not getattr(_guard, "busy", False) and isinstance(self, Symbol):
                _guard.busy = True
                try:
                    if _declared(self):
                        site, entry = _site(2)
                        if site is not None:
                            _record("symbol_assumption", pname, site, entry,
                                    symbol_assumptions=sorted(_declared(self)))
                finally:
                    _guard.busy = False
            return v
        return property(getit, prop.fset, prop.fdel)

    facts = {as_property(k) for k in _assume_defined} - {"is_commutative"}
    for c in _subclasses(Symbol) | set(Symbol.__mro__):
        for pname in facts:
            p = c.__dict__.get(pname)
            if isinstance(p, property):
                setattr(c, pname, wrap_prop(pname, p))

    # assumption-carrying symbols made by package code (Dummy('t', positive=True) etc.):
    # Symbol, Dummy and Wild all pass their assumptions through Symbol._sanitize
    orig_sanitize = Symbol.__dict__["_sanitize"].__func__

    def sanitize(assumptions, obj=None):
        if {k for k, v in assumptions.items() if v is not None} - {"commutative"}:
            site, entry = _site(2)
            if site is not None:
                _record("pkg_makes_assumption_symbol", getattr(obj, "__name__", "Symbol"),
                        site, entry, assumptions=sorted(assumptions))
        return orig_sanitize(assumptions, obj)
    Symbol._sanitize = staticmethod(sanitize)
    sympy.core.cache.clear_cache()
