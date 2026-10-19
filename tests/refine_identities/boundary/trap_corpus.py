"""The trap's corpus run (``test_sympy_boundary.py``), in a process of its own.

    SATSIMP_BACKEND=strict SYMPY_TRAP_MODE=raise python trap_corpus.py ROOT [--limit N] [--timeout S]

Installs the trap (:mod:`sympy_trap`) before satsimp is imported, then refines every
battery case (``tests/refine_identities/battery_v3.py``) and the differential's random
inputs (``satsimp.tools.lib.grammar.generate``, ``--seed``, ``--diff-cases``) that pass
the strict-input check with ``satsimp.refine(expr, assumptions, strict=True)``, each
within ``--timeout`` seconds.  The last line of stdout is the JSON report: the trap's events, the counts,
the canary (a probe compiled under satsimp's directory, which must raise and record,
and a refine call under the ``combined`` backend that asks SymPy, which must raise)
and the backends that answered.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


class CaseTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise CaseTimeout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--limit", type=int, default=0, help="refine only the first N strict cases")
    ap.add_argument("--timeout", type=int, default=10, help="seconds per case")
    ap.add_argument("--seed", type=int, default=2, help="seed of the differential's random inputs")
    ap.add_argument("--diff-cases", type=int, default=500, help="differential cases (0: none)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    sys.path[:0] = [str(root), str(HERE)]

    import sympy_trap
    dirs = []
    for name in ("satsimp", "satrefine", "satassume"):
        spec = importlib.util.find_spec(name)       # locates the package without importing it
        dirs.append(os.path.dirname(spec.origin))
    # satsimp's offline packages are outside the boundary (the input generator is one)
    sympy_trap.install(dirs, [os.path.join(dirs[0], d) for d in ("tools", "testing", "build")])

    # the canary: a forbidden call from a file under satsimp's directory must raise and record
    canary = {}
    probe = compile("import sympy\nsympy.simplify(sympy.Symbol('x'))\n",
                    os.path.join(dirs[0], "_trap_canary.py"), "exec")
    try:
        exec(probe, {})
        canary["raised"] = None
    except sympy_trap.TrapError:
        canary["raised"] = "TrapError"
    canary["recorded"] = any(ev["site"].endswith("_trap_canary.py:2 <module>")
                             for ev in sympy_trap.EVENTS.values())
    # a cached SymPy method (cacheit's wrapper) that simplifies is not construction
    probe = compile("import sympy\nx = sympy.Symbol('x')\n(sympy.cos(x)**2 + sympy.sin(x)**2).as_leading_term(x)\n",
                    os.path.join(dirs[0], "_trap_canary_cached.py"), "exec")
    try:
        exec(probe, {})
        canary["cached"] = None
    except sympy_trap.TrapError:
        canary["cached"] = "TrapError"
    sympy_trap.EVENTS.clear()

    spec = importlib.util.spec_from_file_location("battery", root / "tests" / "refine_identities" / "battery_v3.py")
    battery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(battery)

    import satsimp
    from satsimp.engine import backend
    from satsimp.engine.strict import AssumptionSymbolError, check_strict
    backends: dict = {}
    backend.observers.append(lambda p, a, name, answer: backends.__setitem__(name, backends.get(name, 0) + 1))

    corpus = [(e, a, source) for e, a, _expected, source in battery.BATTERY]
    if args.diff_cases:
        from satsimp.tools.lib.grammar import generate
        for case in range(args.diff_cases):
            g = generate(args.seed, case)
            if g is not None:
                corpus.append((g[1], g[2], f"differential seed {args.seed} case {case}"))

    # the probe: under the combined backend a matrix query goes to SymPy's ask
    # (satsimp/engine/backend.py), which the trap must catch at satsimp's own site
    from sympy import MatrixSymbol, Q, Symbol as _Symbol
    X = MatrixSymbol("X", _Symbol("n"), _Symbol("n"))
    try:
        with backend.using("combined"):
            satsimp.refine(Q.invertible(X), Q.orthogonal(X))
        canary["combined"] = None
    except sympy_trap.TrapError as e:
        canary["combined"] = str(e)
    sympy_trap.EVENTS.clear()
    backends.clear()

    signal.signal(signal.SIGALRM, _alarm)
    counts = {"cases": len(corpus), "rejected": 0, "refined": 0, "changed": 0,
              "trapped": 0, "crash": 0, "timeout": 0}
    crashes, trapped = [], []
    start = time.perf_counter()
    for expr, assumptions, source in corpus:
        try:
            check_strict(expr, assumptions)
        except AssumptionSymbolError:
            counts["rejected"] += 1
            continue
        if args.limit and counts["refined"] >= args.limit:
            break
        counts["refined"] += 1
        signal.alarm(args.timeout)
        try:
            out = satsimp.refine(expr, assumptions, strict=True)
            counts["changed"] += out != expr
        except CaseTimeout:
            counts["timeout"] += 1
        except sympy_trap.TrapError as e:
            counts["trapped"] += 1
            trapped.append(f"{source}: {e}")
        except Exception as e:  # noqa: BLE001 - reported, the trap's events decide
            counts["crash"] += 1
            crashes.append(f"{source}: {type(e).__name__}: {e}"[:300])
        finally:
            signal.alarm(0)
    counts["seconds"] = round(time.perf_counter() - start, 1)
    print(json.dumps({"sympy": sympy.__version__ if (sympy := sys.modules.get("sympy")) else None,
                      "mode": sympy_trap.MODE, "backend": backend.current(), "backends": backends,
                      "canary": canary, "counts": counts, "trapped": trapped[:50],
                      "crashes": crashes[:50], "events": list(sympy_trap.EVENTS.values())}))


if __name__ == "__main__":
    main()
