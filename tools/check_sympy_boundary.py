"""SymPy boundary check of the shipped package: what ruff cannot see.

ruff's TID251 (``pyproject.toml``) bans *imports* of SymPy's simplification and
assumption reasoning (``simplify``, ``trigsimp``, ``cancel``, ``factor``, ``ask``,
``refine``, ``satask``, ...).  A method call needs no import, so this check walks
the AST of ``satsimp/`` and ``satrefine/`` and flags

* reads of attributes that leave the boundary, called or not (a bound method kept
  for later is a use too): ``.cancel`` (polynomial cancellation), ``.equals``
  (numeric and simplify-based equality), ``._eval_refine`` (SymPy's own refine
  handlers, which ask SymPy's assumptions) and SymPy's old-assumption fact stores
  (``.assumptions0``, ``._assumptions0``, ``.default_assumptions``); also
  ``getattr``/``hasattr`` with one of these names as a literal;
* calls of SymPy's rewriting methods: ``.simplify()``, ``.refine()``,
  ``.trigsimp()``, ``.nsimplify()``, ``.factor()``, ``.together()``,
  ``.ratsimp()``, ``.powsimp()``, ``.radsimp()``, ``.combsimp()``,
  ``.gammasimp()``.

``.is_<fact>`` reads are not flagged (satsimp reads some; a separate change).

Not checked: the test fixtures and tools (``satsimp/testing``, ``satsimp/tools``,
``satsimp/build``), the reference handlers (``satsimp/methods/refine/reference``)
and the vendored SymPy dispatcher (``.../identities/compat/upstream.py``), which
are outside the boundary.  It mirrors satassume's ``tools/check_sympy_boundary.py``.

A site that is legitimate carries ``# boundary: <reason>`` on a line of its
statement (or of its dict item, in a table), or on a comment line right above it.
Exit status 1 lists ``file:line``.  Stdlib only.

    python tools/check_sympy_boundary.py [PATH ...]     (default: satsimp/ satrefine/)
"""
from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: attributes flagged wherever they are read
READS = {
    "cancel": "polynomial cancellation (sympy.polys)",
    "equals": "Expr.equals (numeric and simplify-based equality)",
    "_eval_refine": "SymPy's own refine handlers (they ask SymPy's assumptions)",
    "assumptions0": "a symbol's old-style assumptions",
    "_assumptions0": "a symbol's old-style assumptions",
    "default_assumptions": "a class's old-style assumptions",
}
#: methods flagged where they are called
CALLS = frozenset({
    "simplify", "refine", "trigsimp", "nsimplify", "factor", "together", "ratsimp",
    "powsimp", "radsimp", "combsimp", "gammasimp"})
EXCLUDED = ("satsimp/testing/", "satsimp/tools/", "satsimp/build/",
            "satsimp/methods/refine/reference/",
            "satsimp/methods/refine/identities/compat/upstream.py")
MARK = "boundary:"


def _marks(source: str) -> set:
    """Lines carrying a mark with a reason (a mark on a comment line counts for the next)."""
    out = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            text = tok.string.lstrip("#").strip()
            if text.startswith(MARK) and text[len(MARK):].strip():
                row, col = tok.start
                out.add(row + 1 if not tok.line[:col].strip() else row)
    return out


def _spans(tree) -> list:
    """``(first, last)`` lines of the simple statements and dict items."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.stmt) and not hasattr(n, "body"):
            out.append((n.lineno, n.end_lineno))
        elif isinstance(n, ast.Dict):
            out += [((k or v).lineno, v.end_lineno) for k, v in zip(n.keys, n.values)]
    return out


def check_source(source: str, filename: str = "<string>") -> list:
    """``[(line, what)]`` of the unmarked sites in ``source``."""
    tree = ast.parse(source, filename)
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            if n.attr in READS:
                found.append((n.lineno, f".{n.attr}: {READS[n.attr]}"))
            elif n.attr in CALLS and id(n) in called:
                found.append((n.lineno, f".{n.attr}() call: SymPy rewriting"))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id in ("getattr", "hasattr") and len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.Constant) and a.value in READS:
                found.append((n.lineno, f"{n.func.id}(x, {a.value!r}): {READS[a.value]}"))
    marks, spans = _marks(source), _spans(tree)

    def covered(line):
        a, b = min((s for s in spans if s[0] <= line <= s[1]),
                   key=lambda s: s[1] - s[0], default=(line, line))
        return any(a <= m <= b for m in marks)
    return sorted({(line, what) for line, what in found if not covered(line)})


def _excluded(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()
    return any(rel.startswith(e) or rel == e for e in EXCLUDED)


def main(argv) -> int:
    paths = [Path(p) for p in argv] or [ROOT / "satsimp", ROOT / "satrefine"]
    files = [f for p in paths for f in (sorted(p.rglob("*.py")) if p.is_dir() else [p])
             if not _excluded(f)]
    bad = 0
    for f in files:
        for line, what in check_source(f.read_text(), str(f)):
            print(f"{f}:{line}: {what} (without '# {MARK} <reason>')")
            bad += 1
    print(f"check_sympy_boundary: {len(files)} files, {bad} unmarked sites")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
