#!/usr/bin/env python
"""The satassume pin in ``pyproject.toml``, and the reports of the nightly bump (``satassume-bump.yml``).

Standard library only, so the workflow's light jobs run it without installing
satsimp; run it as a file, not with ``-m`` (that would import ``satsimp``)::

    python satsimp/tools/satassume_bump.py pin [PYPROJECT|-]   # the pinned ref (a commit, or a version)
    python satsimp/tools/satassume_bump.py set REF             # pin REF instead
    python satsimp/tools/satassume_bump.py report pr|issue --old SHA --new SHA --satsimp SHA \\
        [--commits N] [--results DIR] [--compare FILE] [--failed JOB ...] [--run-url URL]

The pin is the ``satassume`` entry of ``[project] dependencies``, either
``satassume @ git+URL@COMMIT`` or ``satassume==VERSION``; ``set`` keeps its
form and rewrites only that string, found by parsing the TOML, so comments and
the other entries stay as they are.

``report`` writes the body of the bump PR (``pr``) or of the tracking issue
(``issue``) as Markdown: the commit range with a compare link, the test
results per tree and Python version, failure excerpts, and the output
comparison of ``refine_compare diff`` (``--compare``).  ``--results`` is a
directory of the test jobs' artifacts: ``tests-<python>/<tree>.xml`` (junit)
and ``<tree>.log`` (pytest's output).  The body ends with a marker naming the
satsimp and satassume commits, which the workflow reads to skip a run that
would only repeat the open PR or issue.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
REPO = os.environ.get("SATASSUME_REPO") or "https://github.com/tilorc-bot/satassume"
"""The satassume repository (the workflow's ``SATASSUME_REPO``), for compare links."""
TREES = ("tests/refine_identities", "tests/refine", "tests/refine_v3", "tests/trigsimp")
MARKER = "<!-- satassume-bump satsimp={satsimp} satassume={satassume} -->"
MARKER_RE = re.compile(r"<!-- satassume-bump (?:satsimp|satrefine)=(\w+) satassume=(\w+) -->")
"""Also reads the marker of a report written before the rename (``satrefine=``)."""
SHOW = 10
"""Failure groups (tests failing with the same message) listed in a report, at most, one excerpt each."""
EXCERPT = 600
"""Characters of one failure's text kept in an excerpt."""


# ---------------------------------------------------------------------------
# the pin
# ---------------------------------------------------------------------------

@dataclass
class Pin:
    """The satassume entry of ``pyproject.toml``: ``requirement`` as written, and either the
    git ``url`` and ``ref`` it is pinned to or the PyPI ``version`` (``ref`` is then the version)."""
    requirement: str
    ref: str
    url: str | None = None

    @property
    def form(self) -> str:
        return "git" if self.url else "pypi"

    def with_ref(self, ref: str) -> str:
        return f"satassume @ {self.url}@{ref}" if self.url else f"satassume=={ref}"


GIT = re.compile(r"satassume\s*@\s*(git\+\S+?)@([0-9A-Za-z._/-]+)\s*$")
PYPI = re.compile(r"satassume\s*==\s*([0-9A-Za-z.+!-]+)\s*$")


def find_pin(text: str) -> Pin:
    """The satassume pin of the pyproject ``text``; ValueError if there is none, or it is not pinned."""
    import tomllib
    deps = tomllib.loads(text).get("project", {}).get("dependencies", [])
    entries = [d for d in deps if re.match(r"satassume\b(?![-_.\w])", d.strip())]
    if len(entries) != 1:
        raise ValueError(f"expected one satassume entry in [project] dependencies, found {len(entries)}")
    req = entries[0]
    if m := GIT.match(req.strip()):
        return Pin(req, m.group(2), m.group(1))
    if m := PYPI.match(req.strip()):
        return Pin(req, m.group(1))
    raise ValueError(f"satassume is not pinned to a git ref or an exact version: {req!r}")


def set_pin(text: str, ref: str) -> str:
    """``text`` with the satassume pin moved to ``ref`` (same form, the rest unchanged)."""
    pin = find_pin(text)
    quoted = [q + pin.requirement + q for q in ('"', "'") if text.count(q + pin.requirement + q) == 1]
    if len(quoted) != 1:
        raise ValueError(f"cannot find {pin.requirement!r} exactly once as a string in pyproject.toml")
    out = text.replace(quoted[0], quoted[0][0] + pin.with_ref(ref) + quoted[0][0])
    assert find_pin(out).ref == ref
    return out


# ---------------------------------------------------------------------------
# test results
# ---------------------------------------------------------------------------

@dataclass
class TreeResult:
    """One tree's pytest run under one Python: its summary line, and its failures as (test id, message, text)."""
    summary: str
    failures: list[tuple[str, str, str]]


SUMMARY = re.compile(r"^=*\s*(\d+ (?:passed|failed|skipped|xfailed|xpassed|errors?|deselected|warnings?)\b.*?)\s*=*$")


def read_tree(directory: Path, tree: str) -> TreeResult | None:
    """The results of ``tree`` in a test job's artifact ``directory`` (None: it did not run)."""
    name = tree.rsplit("/", 1)[-1]
    log, junit = directory / f"{name}.log", directory / f"{name}.xml"
    if not log.exists() and not junit.exists():
        return None
    summary = ""
    if log.exists():
        lines = [m.group(1) for line in log.read_text(errors="replace").splitlines() if (m := SUMMARY.match(line))]
        summary = lines[-1] if lines else ""
    failures: list[tuple[str, str, str]] = []
    if junit.exists():
        try:
            root = ET.parse(junit).getroot()
        except ET.ParseError:
            return TreeResult(summary or "no result (unreadable junit file)", [])
        for case in root.iter("testcase"):
            for child in case:
                if child.tag in ("failure", "error"):
                    test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
                    message = child.get("message") or ""
                    failures.append((test_id, message, (child.text or message).strip()))
    return TreeResult(summary or "no summary line (pytest did not finish?)", failures)


def read_results(results: Path | None) -> dict[str, dict[str, TreeResult | None]]:
    """{python: {tree: result}} from the ``tests-<python>`` directories under ``results``."""
    out: dict[str, dict[str, TreeResult | None]] = {}
    if results is None or not results.is_dir():
        return out
    for d in sorted(results.glob("tests-*")):
        out[d.name[len("tests-"):]] = {tree: read_tree(d, tree) for tree in TREES}
    return out


def signature(message: str) -> str:
    """What groups failures: the first line of the message, without the file paths it may name."""
    line = (message.strip().splitlines() or [""])[0]
    return re.sub(r" \(/[^)]*\)", "", line)[:200]


def excerpt(text: str, limit: int = EXCERPT) -> str:
    """The end of a failure's text (where pytest puts the assertion), at most ``limit`` characters."""
    text = text.strip()
    return text if len(text) <= limit else "...\n" + text[-limit:]


def fenced(text: str) -> list[str]:
    """``text`` as a Markdown code block whose fence is longer than any run of backticks in it."""
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
    return [fence, text, fence]


def tests_section(results: dict[str, dict[str, TreeResult | None]]) -> list[str]:
    if not results:
        return ["No test results were found (the test jobs did not upload any)."]
    pythons = sorted(results)
    lines = ["| tree | " + " | ".join(f"Python {p}" for p in pythons) + " |",
             "|---|" + "---|" * len(pythons)]
    for tree in TREES:
        cells = []
        for p in pythons:
            r = results[p].get(tree)
            cells.append("did not run" if r is None else r.summary.replace("|", "\\|"))
        lines.append(f"| `{tree}` | " + " | ".join(cells) + " |")
    groups: dict[str, dict[str, tuple[str, str]]] = {}   # message -> {test id: (python, text)}
    for p in pythons:
        for tree in TREES:
            for test_id, message, text in (r.failures if (r := results[p].get(tree)) else []):
                groups.setdefault(signature(message), {}).setdefault(test_id, (p, text))
    if groups:
        tests = len({t for g in groups.values() for t in g})
        order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
        most = f" (the {SHOW} most frequent)" if len(groups) > SHOW else ""
        lines += ["", f"### Failures: {tests} tests, {len(groups)} distinct messages{most}", ""]
        for message, group in order[:SHOW]:
            (test_id, (p, text)), more = next(iter(group.items())), len(group) - 1
            message = message.replace("`", "'") or "no message"
            others = f" and {more} more" if more else ""
            lines += [f"**{len(group)} x** `{message}`: `{test_id}` (Python {p}){others}", "",
                      *fenced(excerpt(text)), ""]
    return lines


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def report(kind: str, old: str, new: str, satsimp: str, commits: int | None = None,
           results: Path | None = None, compare: Path | None = None, failed: list[str] = (),
           run_url: str | None = None, pat: bool = False, repo: str = REPO) -> str:
    """The Markdown body of the bump PR (``kind="pr"``) or of the tracking issue (``"issue"``)."""
    rng = f"[`{old[:7]}...{new[:7]}`]({repo}/compare/{old}...{new})"
    count = f" ({commits} commits)" if commits is not None else ""
    run = f"[this run]({run_url})" if run_url else "the nightly run"
    if kind == "pr":
        lines = [f"Bumps satassume from `{old[:7]}` to `{new[:7]}`, satassume `main`{count}: {rng}.",
                 "",
                 (f"Opened by the satassume bump workflow (`.github/workflows/satassume-bump.yml`, {run}), "
                  f"which ran satsimp's tests (as `.github/workflows/test.yml` runs them) against the new "
                  f"commit and compared refine's outputs at the old pin and the new commit, on satsimp "
                  f"`{satsimp[:7]}`. Merging it is a review decision: the comparison below lists the answers "
                  f"that change."),
                 "",
                 ("The branch `satassume-bump` belongs to the workflow: every passing run force-pushes it with "
                  "only the pin change, so commits pushed to it are lost. Make any fix the bump needs in a separate "
                  "PR; the next run then tests the bump on top of it.")]
    else:
        lines = [(f"The satassume bump workflow fails for satassume `main` at `{new[:7]}` "
                  f"(pin `{old[:7]}`{count}: {rng}), on satsimp `{satsimp[:7]}`: {run}."),
                 "",
                 ("The pin stays where it is until a run passes; the next passing run closes this issue and "
                  "opens the bump PR.")]
        if failed:
            lines += ["", "Failed: " + ", ".join(f"`{f}`" for f in failed) + "."]
    lines += ["", "## Tests", ""] + tests_section(read_results(results))
    lines += ["", "## Refine outputs: old pin and new commit", ""]
    if compare is not None and compare.exists():
        lines += compare.read_text().rstrip().splitlines()
    else:
        lines.append("No comparison (the compare job did not produce one).")
    if kind == "pr" and pat:
        lines += ["", "## CI on this PR", "",
                  ("Opened with the `SATASSUME_BUMP_TOKEN` secret, so `.github/workflows/test.yml` runs on this PR "
                   "as on any other; the test results above are the bump workflow's own run of the same tests.")]
    elif kind == "pr":
        lines += ["", "## CI on this PR", "",
                  ("A PR opened with the workflow's `GITHUB_TOKEN` does not start other workflows, so "
                   "`test.yml` does not run on it; the test results above, from the same tree and commits, "
                   "are the evidence. To run `test.yml` here as well, close and reopen the PR, or set the "
                   "`SATASSUME_BUMP_TOKEN` secret (a token that may push and open PRs) and the workflow "
                   "uses it instead.")]
    lines += ["", MARKER.format(satsimp=satsimp, satassume=new)]
    return "\n".join(lines) + "\n"


def marker(body: str) -> tuple[str, str] | None:
    """(satsimp commit, satassume commit) of a report's marker, or None.

    The last match: the marker ends the report, and the test output quoted
    above it may contain marker-like text."""
    found = MARKER_RE.findall(body or "")
    return found[-1] if found else None


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="satassume_bump.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pin", help="print the pinned ref")
    p.add_argument("pyproject", nargs="?", default=str(PYPROJECT), help="a pyproject.toml, or - for stdin")
    p = sub.add_parser("set", help="pin another ref (in place)")
    p.add_argument("ref")
    p.add_argument("--pyproject", default=str(PYPROJECT))
    p = sub.add_parser("marker", help="print the satsimp and satassume commits of a report read from stdin")
    p = sub.add_parser("report", help="the Markdown body of the bump PR or the tracking issue")
    p.add_argument("kind", choices=("pr", "issue"))
    p.add_argument("--old", required=True, help="the pinned satassume commit")
    p.add_argument("--new", required=True, help="the satassume commit tested")
    p.add_argument("--satsimp", "--satrefine", dest="satsimp", required=True, help="the satsimp commit tested")
    p.add_argument("--commits", type=int, help="satassume commits between the two")
    p.add_argument("--results", type=Path, help="directory holding the test jobs' tests-<python> artifacts")
    p.add_argument("--compare", type=Path, help="the summary refine_compare diff wrote")
    p.add_argument("--failed", nargs="*", default=[], help="the jobs that failed")
    p.add_argument("--run-url")
    p.add_argument("--pat", action="store_true", help="the PR is opened with a token that starts test.yml on it")
    p.add_argument("--repo", default=REPO, help="the satassume repository URL (default: $SATASSUME_REPO)")
    args = ap.parse_args(argv)
    if args.command == "pin":
        text = sys.stdin.read() if args.pyproject == "-" else Path(args.pyproject).read_text()
        print(find_pin(text).ref)
    elif args.command == "set":
        path = Path(args.pyproject)
        path.write_text(set_pin(path.read_text(), args.ref))
    elif args.command == "marker":
        m = marker(sys.stdin.read())
        print(" ".join(m) if m else "")
    else:
        sys.stdout.write(report(args.kind, args.old, args.new, args.satsimp, args.commits, args.results,
                                args.compare, args.failed, args.run_url, args.pat, args.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
