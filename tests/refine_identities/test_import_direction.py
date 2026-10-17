"""The layout rules (issue #13; ``docs/architecture.md``), checked.

* **Imports go one way**: the offline packages (``satsimp.build``,
  ``satsimp.tools``, ``satsimp.testing``) may import the runtime
  (``satsimp``, ``satsimp.engine``, ``satsimp.methods``), never the reverse;
  nor does the runtime import refine's reference implementation
  ``satsimp.methods.refine.reference`` (v3, measuring material; only its alias
  ``handlers_v3`` does).  A subprocess makes the offline packages unimportable
  (a meta-path finder that raises) before it imports ``satsimp``, then refines a
  few inputs in each ``SATREFINE_IDENTITIES`` mode; the results must be what
  this process gets.  Importing ``satsimp`` alone loads no method.
* **The engine imports no method** (``satsimp.engine`` never imports
  ``satsimp.methods``: a method plugs in through ``engine/hooks.py``), and
  **a method imports no other method** (``satsimp.methods.<a>`` never imports
  ``satsimp.methods.<b>``; what two methods share belongs in the engine).
* **The engine names no specific SymPy function and no matrix type** (the
  heads it needs to know about are roles in ``engine/hooks.py``, set by a
  method); ``engine/backend.py``, the ``ask`` routing that guards SymPy's own
  handlers for particular heads, is exempt.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from satsimp.engine import driver as _dispatch

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "satsimp"
ENGINE = PACKAGE / "engine"
METHODS = PACKAGE / "methods"
CORE = [p for p in sorted(ENGINE.glob("*.py")) if p.name != "backend.py"]
"""The engine's algorithm modules: everything in ``engine/`` but the ``ask`` backend."""

OFFLINE = ("satsimp.build", "satsimp.tools", "satsimp.testing")
REFERENCE = ("satsimp.methods.refine.reference",)

CASES = [   # (expression, assumptions), as source evaluated with ``from sympy import *``
    ("log(x)", "Q.negative(x)"),
    ("sqrt(x**2)", "Q.real(x)"),
    ("atan(tan(x))", "Q.gt(x, -pi/2) & Q.lt(x, pi/2)"),
    ("floor(x)", "Q.ge(x, 1) & Q.lt(x, 2)"),
    ("Piecewise((1, x > 0), (2, True))", "Q.positive(x)"),
    ("exp(log(x)*y)", "Q.positive(x)"),
    ("Abs(x*y)", "Q.negative(x) & Q.positive(y)"),
    ("im(log(x))", "Q.negative(x)"),
    ("Determinant(Transpose(X))", "True"),
    ("MatMul(X, Inverse(X))", "Q.invertible(X)"),
]

_CHILD = r'''
import importlib.abc, json, sys

OFFLINE = %(offline)r


class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name in OFFLINE or name.startswith(tuple(p + "." for p in OFFLINE)):
            raise ImportError(f"offline package imported by refine: {name}")
        return None


sys.meta_path.insert(0, Blocked())
from sympy import *
import satsimp
methods = sorted(m for m in sys.modules if m.startswith("satsimp.methods"))   # before the first use
x, y = symbols("x y")
X = MatrixSymbol("X", 3, 3)
out = [srepr(satsimp.refine(eval(e), eval(a))) for e, a in %(cases)r]
loaded = sorted(m for m in sys.modules if m.startswith(OFFLINE))
print(json.dumps({"results": out, "loaded": loaded, "refine": satsimp.refine.__module__, "methods": methods}))
'''


def _expected() -> list[str]:
    from sympy import srepr, symbols, MatrixSymbol  # noqa: F401
    import sympy
    from satsimp import refine
    names = dict(vars(sympy))
    names.update(x=symbols("x"), y=symbols("y"), X=MatrixSymbol("X", 3, 3))
    return [srepr(refine(eval(e, names), eval(a, names))) for e, a in CASES]


@pytest.mark.parametrize("mode", ["generated", "live"])
def test_refine_runs_without_the_offline_packages(mode):
    code = _CHILD % {"offline": OFFLINE + REFERENCE, "cases": CASES}
    env = dict(os.environ, SATREFINE_HANDLERS="handlers_identities", SATREFINE_IDENTITIES=mode,
               PYTHONPATH=os.pathsep.join(sys.path))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    child = json.loads(proc.stdout.strip().splitlines()[-1])
    assert child["loaded"] == []
    assert child["methods"] == []
    assert child["refine"] == "satsimp.engine.driver"
    with (_dispatch.live() if mode == "live" else _dispatch.tables()):
        expected = _expected()
    assert child["results"] == expected


def _runtime() -> list[Path]:
    """The runtime's modules: ``satsimp/__init__.py``, the engine and the methods, without
    refine's reference implementation and its alias ``handlers_v3``."""
    paths = [PACKAGE / "__init__.py", *ENGINE.rglob("*.py"), *METHODS.rglob("*.py")]
    return sorted(p for p in paths if "reference" not in p.relative_to(METHODS.parent).parts
                  and p != METHODS / "refine" / "handlers_v3.py")


def _imports(paths, forbidden: tuple[str, ...]) -> list[str]:
    """``path:line name`` for every import (even a lazy one) in ``paths`` (files, or a
    directory searched recursively) of a module in, or equal to, one of the packages ``forbidden``."""
    if isinstance(paths, Path):
        paths = sorted(paths.rglob("*.py"))
    found = []
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:          # relative: resolve against the module's package
                    package = path.relative_to(ROOT).with_suffix("").parts[:-1]
                    parts = list(package[:len(package) - node.level + 1])
                    base = ".".join(parts + ([base] if base else []))
                names = [base] + [f"{base}.{a.name}" for a in node.names]
            for name in names:
                if name in forbidden or name.startswith(tuple(p + "." for p in forbidden)):
                    found.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}")
    return found


def test_the_offline_packages_are_not_imported_by_the_runtime():
    """No runtime module imports an offline package, even lazily."""
    found = _imports(_runtime(), OFFLINE)
    assert not found, found


def test_the_reference_is_not_imported_by_the_runtime():
    """No runtime module imports ``satsimp.methods.refine.reference`` (v3), even lazily."""
    found = _imports(_runtime(), REFERENCE)
    assert not found, found


def test_the_engine_imports_no_method():
    """No module under ``satsimp/engine`` imports ``satsimp.methods``, even lazily: a method
    plugs into the engine through ``engine/hooks.py``."""
    found = _imports(ENGINE, ("satsimp.methods",))
    assert not found, found


def _methods() -> list[str]:
    return sorted(p.name for p in METHODS.iterdir() if (p / "__init__.py").exists())


def test_a_method_imports_no_other_method():
    """No module of a method imports another method's package, even lazily (one method
    today, ``refine``: the rule is there for the next one)."""
    assert "refine" in _methods()
    found = []
    for method in _methods():
        others = tuple(f"satsimp.methods.{m}" for m in _methods() if m != method)
        found += _imports(METHODS / method, others) if others else []
    assert not found, found


def test_satsimp_does_not_import_its_methods_eagerly():
    """``satsimp/__init__.py`` imports a method only on first use (inside ``__getattr__``)."""
    tree = ast.parse((PACKAGE / "__init__.py").read_text())
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert all((n.module or "") == "__future__" for n in top if isinstance(n, ast.ImportFrom)), top
    assert not [n for n in top if isinstance(n, ast.Import)]


# ---------------------------------------------------------------------------
# the engine names no specific SymPy function and no matrix type
# ---------------------------------------------------------------------------

GENERIC = {"Function", "AppliedUndef", "UndefinedFunction"}
"""Function classes the engine may name: the generic ones (head wildcards)."""

REMAINING: dict[str, set[str]] = {}
"""Specific names the engine may still import, by module (none since step 3 of issue #13)."""


def _specific_names(path: Path) -> set[str]:
    """Names ``path`` imports from SymPy that are specific function classes
    (subclasses of ``Function``, or ``Max``/``Min``) or matrix types."""
    import importlib
    from sympy import Function
    from sympy.functions.elementary.miscellaneous import MinMaxBase
    from sympy.matrices import MatrixBase
    from sympy.matrices.expressions import MatrixExpr
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "sympy":
            module = importlib.import_module(node.module)
            for alias in node.names:
                obj = getattr(module, alias.name, None)
                if not isinstance(obj, type) or alias.name in GENERIC:
                    continue
                if issubclass(obj, (Function, MinMaxBase, MatrixBase, MatrixExpr)):
                    out.add(alias.name)
            if "matrices" in node.module:
                out.add(node.module)
        elif isinstance(node, ast.Import) and any("matrices" in a.name for a in node.names if a.name.startswith("sympy")):
            out.update(a.name for a in node.names)
    return out


def _core_names() -> dict[str, set[str]]:
    return {p.name: names for p in CORE if (names := _specific_names(p))}


def test_core_names_nothing_new():
    """No engine module names a specific function or matrix type beyond :data:`REMAINING`."""
    found = _core_names()
    extra = {m: names - REMAINING.get(m, set()) for m, names in found.items() if names - REMAINING.get(m, set())}
    assert not extra, extra


def test_core_names_no_specific_function_or_matrix():
    assert _core_names() == {}
