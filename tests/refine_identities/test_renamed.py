"""What keeps working after the rename satrefine -> satsimp: the ``satrefine`` alias and the
``SATREFINE_*`` environment variables, each with a ``DeprecationWarning``.

Each check runs in a subprocess: the alias warns when it is first imported, and the handler
package and the backend are read from the environment once per process.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from satsimp.engine import config


def _run(code: str, **env: str) -> dict:
    environ = {k: v for k, v in os.environ.items() if not k.startswith((config.PREFIX, config.OLD_PREFIX))}
    environ.update(env, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=environ, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


_ALIAS = r'''
import json, warnings
from sympy import Q, Symbol, log
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import satrefine
import satsimp
from satsimp.methods import refine as method
x = Symbol("x")
print(json.dumps({
    "warnings": [str(w.message) for w in caught if w.category is DeprecationWarning],
    "same": satrefine.refine is satsimp.refine is method.refine,
    "names": all(getattr(satrefine, n) is getattr(method, n)
                 for n in [*method.__all__, "HANDLERS_PACKAGE", "DEFAULT_HANDLERS", "HANDLERS_ENV_VAR",
                           "handlers_package"]),
    "package": satrefine.HANDLERS_PACKAGE,
    "result": str(satrefine.refine(log(x), Q.negative(x))),
}))
'''


def test_import_satrefine_warns_and_is_satsimp_refine():
    out = _run(_ALIAS)
    assert len(out["warnings"]) == 1 and "satsimp" in out["warnings"][0]
    assert out["same"] and out["names"]
    assert out["package"] == "handlers_identities"
    assert out["result"] == "log(-x) + I*pi"


_ENV = r'''
import json, warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import satsimp.methods.refine as method
    from satsimp.engine import backend, config
    mode, strict = config.env_mode(), config.env_strict()
print(json.dumps({"handlers": method.HANDLERS_PACKAGE, "backend": backend.current(), "mode": mode,
                  "strict": strict, "warnings": sorted(str(w.message).split()[0] for w in caught
                                                       if w.category is DeprecationWarning)}))
'''


def test_old_variables_are_read_with_a_warning():
    out = _run(_ENV, SATREFINE_HANDLERS="handlers_v3", SATREFINE_BACKEND="sympy",
               SATREFINE_IDENTITIES="live", SATREFINE_STRICT_LOOPS="1")
    assert (out["handlers"], out["backend"], out["mode"], out["strict"]) == ("handlers_v3", "sympy", "live", True)
    assert out["warnings"] == ["SATREFINE_BACKEND", "SATREFINE_HANDLERS", "SATREFINE_IDENTITIES",
                               "SATREFINE_STRICT_LOOPS"]


@pytest.mark.parametrize("old", [None, "handlers_v3"])
def test_new_variables_win(old):
    env = {"SATSIMP_HANDLERS": "handlers_identities", "SATSIMP_BACKEND": "satassume"}
    if old is not None:
        env.update(SATREFINE_HANDLERS=old, SATREFINE_BACKEND="sympy")
    out = _run(_ENV, **env)
    assert (out["handlers"], out["backend"]) == ("handlers_identities", "satassume")
    assert out["warnings"] == []


def test_env_setdefault_keeps_an_old_value(monkeypatch):
    monkeypatch.setenv("SATSIMP_FULL_TESTS", "")   # restored (removed) after the test
    monkeypatch.delenv("SATSIMP_FULL_TESTS")
    monkeypatch.setenv("SATREFINE_FULL_TESTS", "1")
    monkeypatch.setattr(config, "_warned", set())
    with pytest.warns(DeprecationWarning, match="SATREFINE_FULL_TESTS"):
        assert config.env_setdefault("FULL_TESTS", "0") == "1"
    assert os.environ["SATSIMP_FULL_TESTS"] == "1"
