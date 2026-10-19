"""``satsimp/tools/satassume_bump.py`` and ``refine_compare diff``: the pin edit, the reports, the summary.

The workflow (``.github/workflows/satassume-bump.yml``) runs these end to end;
here they run on the real ``pyproject.toml`` and on small made-up results.
"""
from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")

bump = importlib.import_module("satsimp.tools.satassume_bump")
compare = importlib.import_module("satsimp.tools.refine_compare")

ROOT = Path(__file__).resolve().parents[3]
OLD, NEW, HEAD = "a" * 40, "b" * 40, "c" * 40

PYPROJECT = """\
[project]
name = "satsimp"
# satassume pinned to a commit
dependencies = [
    "satassume @ git+https://github.com/tilorc-bot/satassume@{ref}",
    "satassume-extras>=1",
    "sympy>=1.12",
]

[project.optional-dependencies]
dev = ["pytest"]
"""


def test_pin_of_the_repository():
    pin = bump.find_pin((ROOT / "pyproject.toml").read_text())
    assert pin.form == "git" and pin.url == "git+https://github.com/tilorc-bot/satassume"
    assert re.fullmatch(r"[0-9a-f]{40}", pin.ref)


def test_set_pin_changes_only_the_satassume_string():
    text = PYPROJECT.format(ref=OLD)
    out = bump.set_pin(text, NEW)
    assert bump.find_pin(out).ref == NEW
    assert out == PYPROJECT.format(ref=NEW)
    assert bump.set_pin((ROOT / "pyproject.toml").read_text(), NEW).count(NEW) == 1


def test_set_pin_keeps_a_pypi_pin_a_pypi_pin():
    text = 'dependencies = ["satassume==0.0.1", "sympy"]\n'
    text = "[project]\n" + text
    assert bump.find_pin(text).form == "pypi"
    assert bump.set_pin(text, "0.0.2") == text.replace("0.0.1", "0.0.2")


@pytest.mark.parametrize("deps", ['["sympy"]', '["satassume"]', '["satassume>=0.1"]',
                                  '["satassume @ git+https://x/satassume@a", "satassume==1"]'])
def test_unpinned_or_ambiguous_is_an_error(deps):
    with pytest.raises(ValueError):
        bump.find_pin(f"[project]\ndependencies = {deps}\n")


def test_workflow_installs_the_sympy_of_test_yml():
    def sympy(name):
        return re.findall(r"sympy @ git\+\S+@\w+", (ROOT / ".github" / "workflows" / name).read_text())
    assert set(sympy("satassume-bump.yml")) == set(sympy("test.yml")) and len(set(sympy("test.yml"))) == 1


def _pr_lookups() -> list[tuple[str, str]]:
    """(``--json`` fields, ``--jq`` filter) of every ``gh pr list`` in the workflow."""
    text = (ROOT / ".github" / "workflows" / "satassume-bump.yml").read_text()
    found = re.findall(r"gh pr list [^\n]*?--json (\S+) --jq '([^']*)'", text)
    assert len(found) == text.count("gh pr list --head \"") == 3
    return found


def test_workflow_ignores_pull_requests_from_forks():
    """``gh pr list --head B`` also lists a fork's PR from a branch named B; every lookup must drop it."""
    prs = [{"number": 7, "body": "fork <!-- satassume-bump satsimp=c satassume=b -->", "isCrossRepository": True},
           {"number": 9, "body": "ours", "isCrossRepository": False}]
    jq = shutil.which("jq")
    for fields, query in _pr_lookups():
        assert "isCrossRepository" in fields.split(",") and "select(.isCrossRepository | not)" in query
        if jq is None:
            continue
        for listed, want in ((prs, {"ours", "9"}), (prs[:1], {"", "''"})):
            out = subprocess.run([jq, "-r", query], input=json.dumps(listed), capture_output=True, text=True,
                                 check=True).stdout.split()
            assert set(out) <= want and "7" not in out and "fork" not in out, (query, listed, out)


def test_marker_is_the_last_one():
    quoted = "```\nE  assert '<!-- satassume-bump satsimp=x satassume=y -->'\n```\n"
    body = quoted + bump.MARKER.format(satsimp=HEAD, satassume=NEW)
    assert bump.marker(body) == (HEAD, NEW)


def test_marker_of_a_report_written_before_the_rename():
    assert bump.marker("<!-- satassume-bump satrefine=c satassume=b -->") == ("c", "b")


def test_excerpt_fence_outlasts_backticks_in_the_text():
    assert bump.fenced("plain") == ["```", "plain", "```"]
    assert bump.fenced("a ``` b ```` c")[0] == "`````"


JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="1"
skipped="0" tests="2"><testcase classname="tests.refine.test_a" name="test_ok" time="0.1"/>
<testcase classname="tests.refine.test_a" name="test_bad" time="0.1"><failure message="assert 1 == 2">
def test_bad():
&gt;       assert 1 == 2
E       assert 1 == 2</failure></testcase></testsuite></testsuites>"""


def _results(tmp_path: Path) -> Path:
    for python in ("3.11", "3.12"):
        d = tmp_path / "results" / f"tests-{python}"
        d.mkdir(parents=True)
        (d / "refine.xml").write_text(JUNIT)
        (d / "refine.log").write_text(".F\n=== FAILURES ===\nFAILED tests/refine/test_a.py::test_bad\n"
                                      "1 failed, 1 passed in 0.52s\n")
        (d / "refine_v3.log").write_text("1004 passed, 1 xfailed in 12.39s\n")
    return tmp_path / "results"


def test_report_issue(tmp_path):
    body = bump.report("issue", OLD, NEW, HEAD, commits=352, results=_results(tmp_path),
                       failed=["test (failure)"], run_url="https://example/run/1")
    assert f"https://github.com/tilorc-bot/satassume/compare/{OLD}...{NEW}" in body
    assert "(352 commits" in body and "`test (failure)`" in body and "[this run](https://example/run/1)" in body
    assert "| `tests/refine` | 1 failed, 1 passed in 0.52s | 1 failed, 1 passed in 0.52s |" in body
    assert "| `tests/refine_identities` | did not run | did not run |" in body
    assert "| `tests/refine_v3` | 1004 passed, 1 xfailed in 12.39s |" in body
    assert "| `tests/trigsimp` | did not run | did not run |" in body
    assert "### Failures: 1 tests, 1 distinct messages" in body   # one test, failing under both Pythons
    assert "**1 x** `assert 1 == 2`: `tests.refine.test_a::test_bad` (Python 3.11)" in body
    assert "E       assert 1 == 2" in body
    assert "No comparison" in body
    assert bump.marker(body) == (HEAD, NEW)


def test_report_pr(tmp_path):
    summary = tmp_path / "summary.md"
    summary.write_text("**0 of 3 battery results change.**\n")
    body = bump.report("pr", OLD, NEW, HEAD, results=tmp_path / "none", compare=summary)
    assert body.startswith(f"Bumps satassume from `{OLD[:7]}` to `{NEW[:7]}`")
    assert "**0 of 3 battery results change.**" in body and "No test results" in body
    assert "close and reopen the PR" in body and "force-pushes" in body
    assert "close and reopen" not in bump.report("pr", OLD, NEW, HEAD, pat=True)
    assert bump.marker("no marker") is None


def test_failures_are_grouped_by_message():
    assert bump.signature("ImportError: cannot import name 'f' from 'm' (/x/y/m.py)\nmore") == \
        "ImportError: cannot import name 'f' from 'm'"


def test_command_line_set_and_pin(tmp_path, capsys):
    path = tmp_path / "pyproject.toml"
    path.write_text(PYPROJECT.format(ref=OLD))
    assert bump.main(["set", NEW, "--pyproject", str(path)]) == 0
    assert bump.main(["pin", str(path)]) == 0
    assert capsys.readouterr().out.strip() == NEW


def _dump(satassume, battery, differential):
    return {"satassume": satassume, "hash_seed": "0",
            "battery": {"seconds": 1.0, "records": [
                {"source": f"test_trig.py::t{i}", "input": f"sin(x{i}) | Q.real(x{i})", "class": c, "result": r}
                for i, (c, r) in enumerate(battery)]},
            "differential": {"seed": 2, "cases": len(differential), "seconds": 2.0, "records": [
                {"case": i, "head": "Abs", "input": f"Abs(y{i}) | True", "class": c, "result": r, "unsound": u}
                for i, (c, r, u) in enumerate(differential)]}}


def test_compare_diff():
    old = _dump(OLD, [("same", "x"), ("quiet", "sin(x1)"), ("miss", "sin(x2)")],
                [("fired", "y0", False), ("unchanged", "Abs(y1)", False)])
    new = _dump(NEW, [("same", "x"), ("crash", "ImportError: `_registry_state`"), ("other", "y")],
                [("fired", "-y0", True), ("unchanged", "Abs(y1)", False)])
    text = compare.diff(old, new, show=1)
    assert "**2 of 3 battery results and 1 of 2 differential results change.**" in text
    assert "**Worse:** battery crash 0 -> 1; differential unsound 0 -> 1." in text
    assert "| crash | 0 | 1 (+1) |" in text and "| unsound | 0 | 1 (+1) |" in text
    assert "Changed: quiet -> crash 1, miss -> other 1." in text
    assert "The changed results (2; the first 1)" in text
    assert "ImportError: '_registry_state'" in text   # backticks would break the Markdown
    assert "`-y0` (fired, unsound)" in text
    assert compare.diff(old, old).count("<details>") == 0


def test_compare_diff_refuses_different_inputs():
    old = _dump(OLD, [("same", "x")], [])
    new = _dump(NEW, [("same", "x"), ("same", "y")], [])
    with pytest.raises(SystemExit):
        compare.diff(old, new)
