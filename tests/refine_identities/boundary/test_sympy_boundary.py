"""The SymPy boundary (README, "SymPy boundary"): the static check
``tools/check_sympy_boundary.py`` and the runtime trap over a generic corpus.

The trap patches SymPy process-wide, so the corpus runs in a subprocess of its own
(``trap_corpus.py`` with ``sympy_trap.py``, both next to this file): nothing leaks
into this process or other tests, and it is xdist-safe (no shared files; the report
comes back on stdout).  ruff's import bans (``pyproject.toml``) run in CI's lint job.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CHECKER = ROOT / "tools" / "check_sympy_boundary.py"


def _checker():
    spec = importlib.util.spec_from_file_location("check_sympy_boundary", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# -- static check ----------------------------------------------------------

def test_static_check_passes_on_the_package(capsys):
    assert _checker().main([]) == 0
    assert " 0 unmarked sites" in capsys.readouterr().out


SNIPPET = (
    "def f(e, a, c):\n"
    "    e.simplify()\n"                                       # 2
    "    e.equals(a)\n"                                        # 3
    "    e._eval_refine(a)\n"                                  # 4
    "    k = e.assumptions0\n"                                 # 5
    "    g = e.cancel\n"                                       # 6: read, not called
    "    h = getattr(e, '_eval_refine', None)\n"               # 7
    "    e.together()\n"                                       # 8
    "    ok = e.is_positive and e.is_Add\n"                    # .is_<fact>: not checked
    "    ok = e.simplify\n"                                    # a rewriting method only when called
    "    ok = e.expand()\n"
    "    m = e.equals(a)  # boundary: a reason\n"
    "    # boundary: a reason\n"
    "    m = e.equals(a)\n"
    "    m = e.equals(a)  # boundary:\n"                       # 15: no reason
    "    T = {e._eval_refine: 1,  # boundary: a key\n"
    "         c._eval_refine: 2}\n"                            # 17: its own item
)


def test_static_check_flags_a_snippet():
    lines = [line for line, _ in _checker().check_source(SNIPPET)]
    assert lines == [2, 3, 4, 5, 6, 7, 8, 15, 17]


def test_static_check_fails_on_a_planted_file(tmp_path):
    planted = tmp_path / "planted.py"
    planted.write_text(SNIPPET)
    clean = tmp_path / "clean.py"
    clean.write_text("def f(e):\n    return e.expand()\n")
    out = subprocess.run([sys.executable, str(CHECKER), str(planted), str(clean)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 1, out.stdout + out.stderr
    assert f"{planted}:3: .equals" in out.stdout
    assert "clean.py" not in out.stdout
    assert "2 files, 9 unmarked sites" in out.stdout
    out = subprocess.run([sys.executable, str(CHECKER), str(clean)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr


def test_static_check_skips_what_is_outside_the_boundary():
    mod = _checker()
    assert mod._excluded(ROOT / "satsimp" / "methods" / "refine" / "identities" / "compat" / "upstream.py")
    assert mod._excluded(ROOT / "satsimp" / "methods" / "refine" / "reference" / "v3" / "trig.py")
    assert mod._excluded(ROOT / "satsimp" / "tools" / "refine_compare.py")
    assert not mod._excluded(ROOT / "satsimp" / "engine" / "driver.py")


# -- runtime trap ----------------------------------------------------------

def test_runtime_trap_corpus():
    """The battery and the differential's random inputs (seed 2), every case that
    passes the strict-input check, through ``refine(..., strict=True)`` under the
    ``strict`` backend with SymPy's simplification and assumption reasoning trapped
    (``SYMPY_TRAP_MODE=raise``): no call is reached from satsimp (or satassume)
    except SymPy's own construction and evaluation (``sympy_trap.CONSTRUCTION``,
    ``BUILDING``, ``HARMLESS``), and no fact of an assumption-carrying symbol is read
    (the corpus has none, and satsimp makes none)."""
    env = {**os.environ, "SATSIMP_BACKEND": "strict", "SYMPY_TRAP_MODE": "raise",
           "PYTHONHASHSEED": "0",
           "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")]))}
    out = subprocess.run([sys.executable, str(HERE / "trap_corpus.py"), str(ROOT)],
                         capture_output=True, text=True, timeout=600, env=env, cwd=ROOT)
    assert out.returncode == 0, out.stderr[-3000:]
    d = json.loads(out.stdout.splitlines()[-1])
    # the trap is armed: a probe from satsimp's directory raises and records, and so
    # does satsimp's own call of SymPy's ask under the combined backend
    assert d["mode"] == "raise"
    assert d["canary"]["raised"] == "TrapError" and d["canary"]["recorded"], d["canary"]
    assert "backend.py" in (d["canary"]["combined"] or ""), d["canary"]
    # the strict backend answered every query
    assert d["backend"] == "strict" and set(d["backends"]) == {"strict"}, d["backends"]
    counts = d["counts"]
    assert counts["refined"] >= 2000 and counts["changed"] >= 1000, counts
    forbidden = [e for e in d["events"] if e["kind"] == "forbidden" and not e["allowed"]]
    assert not forbidden and not d["trapped"], "SymPy reasoning reached from satsimp:\n" + "\n".join(
        [f"{e['name']} at {e['site']} (entry {e['entry']}, called by {e['caller']}, {e['count']}x)"
         for e in forbidden] + d["trapped"])
    facts = [e for e in d["events"] if e["kind"] != "forbidden"]
    assert not facts, "\n".join(f"{e['kind']} {e['name']} at {e['site']}" for e in facts)
    assert not d["crashes"], d["crashes"]
