"""trigsimp and refine leave each other alone (``docs/trigsimp.md``, "Test plan"; ``docs/architecture.md``).

Each check runs in a fresh interpreter, so what is imported is the
check's own doing: ``import satsimp`` imports no method, trigsimp does not
import refine, and refine's results and hooks are the same before and after a
trigsimp call in the same process.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _python(code: str) -> str:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([ROOT, os.environ.get("PYTHONPATH", "")]))
    done = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], env=env, cwd=ROOT,
                          capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_trigsimp_imports_no_other_method():
    out = _python("""
        import sys
        import satsimp
        assert not [m for m in sys.modules if m.startswith("satsimp.methods")], "import satsimp loads a method"
        from sympy import cos, sin, symbols
        x = symbols("x")
        assert satsimp.trigsimp(sin(x)**2 + cos(x)**2) == 1
        print(sorted({m.split(".")[2] for m in sys.modules if m.startswith("satsimp.methods.")}))
    """)
    assert out.strip() == "['trigsimp']"


def test_refine_unchanged_by_trigsimp():
    _python("""
        from sympy import Abs, Q, cos, sin, sqrt, symbols, tan
        import satsimp
        from satsimp.engine import hooks
        x, y = symbols("x y")
        cases = [(Abs(x), Q.positive(x)), (sqrt(x**2), Q.real(x)), (sin(x)**2 + cos(x)**2, True),
                 (cos(x + y), Q.integer(y)), (tan(x)*cos(x), Q.real(x))]
        before = [satsimp.refine(e, a) for e, a in cases]
        state = {name: getattr(hooks, name) for name in hooks._defaults()}
        assert satsimp.trigsimp(sin(x)**2 + cos(x)**2 + tan(x)*cos(x)) == 1 + sin(x)
        assert {name: getattr(hooks, name) for name in hooks._defaults()} == state
        assert all(getattr(hooks, name) is value for name, value in state.items())
        assert [satsimp.refine(e, a) for e, a in cases] == before
    """)
