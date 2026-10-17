#!/usr/bin/env python
"""Refine's outputs under two satassume versions: dump them in each environment, then compare.

Usage::

    PYTHONHASHSEED=0 python -m satsimp.tools.refine_compare dump OUT.json [--seed 2] [--cases 1500] [--expect COMMIT]
    python -m satsimp.tools.refine_compare diff OLD.json NEW.json [--show 25]

``dump`` refines, with the default package and backend (``handlers_identities``,
``combined``) and whatever satassume is installed:

* the battery (``tests/refine_identities/battery_v3.py``, 1,736 cases recorded
  from ``tests/refine_v3``), each case classified as ``scoreboard battery``
  classifies it (same as v3, other form, miss, quiet, extra, numerically
  wrong, crash), in this process and in battery order;
* the differential's random inputs (``refine_differential``'s worker for
  ``--seed``/``--cases``, default family, in a subprocess), each recorded with
  its status (fired, unchanged, inconsistent, crash, timeout), result and
  whether the numeric check found it unsound;

and writes them with the satassume commit (or version) that answered.  Run it
once per satassume, each in a fresh process; the inputs depend only on
satsimp and SymPy, so the two dumps line up case by case.

``diff`` prints a Markdown summary for a reviewer (the satassume bump PR
quotes it): per-class counts side by side, regressions in the numbers that
must stay 0 (wrong, crash, timeout, unsound), how the classes moved, and the
first ``--show`` changed results of each part, with their inputs.  The exit
status is 0: this is a measurement.  About 1.5 minutes per dump on one core.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "handlers_identities"
BAD = {"battery": ("wrong", "crash", "timeout"), "differential": ("crash", "timeout", "unsound")}
"""Per part, the classes a satassume update should never make more frequent."""
BATTERY_CLASSES = ("same", "other", "miss", "quiet", "extra", "wrong", "crash", "timeout")
DIFF_CLASSES = ("fired", "unchanged", "inconsistent", "crash", "timeout", "unsound")
FAILED = ("crash", "timeout")
WIDTH = 160
"""Characters of an input or result kept in the listing."""


# ---------------------------------------------------------------------------
# dump
# ---------------------------------------------------------------------------

def satassume_version() -> str:
    """The commit satassume was installed from (pip's ``direct_url.json``), else its version."""
    from importlib import metadata
    try:
        dist = metadata.distribution("satassume")
    except metadata.PackageNotFoundError:
        return "not installed"
    try:
        url = json.loads(dist.read_text("direct_url.json") or "{}")
    except ValueError:
        url = {}
    return url.get("vcs_info", {}).get("commit_id") or dist.version


def dump_battery(timeout: int) -> tuple[list[dict], float]:
    """Every battery case refined and classified (``lib.battery.classify``), with the wall time."""
    from satsimp.tools.lib import battery as bat
    from satsimp.tools.lib.workers import CaseTimeout, install_case_alarm

    install_case_alarm()
    cases, _ = bat.load_battery(bat.DEFAULT)
    known_limit = bat.known_oracle_limit()
    records = []
    t0 = time.time()
    for expr, assumptions, expected, source in cases:
        signal.alarm(timeout)
        try:
            out = bat.classify(expr, assumptions, expected, source, known_limit)
        except CaseTimeout:   # raised outside classify's own handlers
            out = bat.Outcome("timeout", error=CaseTimeout())
        finally:
            signal.alarm(0)
        if isinstance(out.error, CaseTimeout):
            kind, result = "timeout", "timeout"
        elif out.error is not None:
            kind, result = "crash", f"{type(out.error).__name__}: {out.error}"
        else:
            kind, result = bat.SHORT[out.key], str(out.got)
        records.append({"source": source, "input": f"{expr} | {assumptions}", "class": kind, "result": result})
    return records, time.time() - t0


def dump_differential(seed: int, cases: int, timeout: int) -> tuple[list[dict], float]:
    """The differential worker's records for ``PACKAGE`` (a subprocess), each with its input, and the wall time."""
    from satsimp.tools.lib.grammar import generate
    from satsimp.tools.lib.workers import run_json_worker

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "worker.json")
        res = run_json_worker("satsimp.tools.refine_differential",
                              ["--worker", PACKAGE, "--seed", str(seed), "--cases", str(cases), "--out", out,
                               "--timeout", str(timeout)],
                              out, env={"SATREFINE_HANDLERS": PACKAGE}, failure="differential worker failed")
    records = []
    for r in res["records"]:
        g = generate(seed, r["case"])
        status = r.get("status", "crash")
        result = r.get("result_str") or r.get("error") or status
        records.append({"case": r["case"], "head": r["head"], "input": f"{g[1]} | {g[2]}",
                        "class": status, "result": result, "unsound": "unsound" in r})
    return records, res["seconds"]


def dump(out: str, seed: int, cases: int, timeout: int, expect: str | None = None) -> None:
    from satsimp.tools.lib.select import select
    select(handlers=PACKAGE)
    os.environ.setdefault("SATREFINE_STRICT_LOOPS", "1")   # a tripped loop guard is a crash here
    import satsimp.methods.refine  # noqa: F401

    version = satassume_version()
    if expect is not None and version != expect:
        raise SystemExit(f"satassume {version} is installed, not {expect}")
    print(f"satassume {version}: battery", flush=True)
    battery, t_battery = dump_battery(timeout)
    print(f"  {len(battery)} cases, {t_battery:.0f}s; differential seed {seed}, {cases} cases", flush=True)
    differential, t_diff = dump_differential(seed, cases, timeout)
    print(f"  {len(differential)} cases, {t_diff:.0f}s", flush=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        json.dump({"satassume": version, "hash_seed": os.environ.get("PYTHONHASHSEED"),
                   "battery": {"seconds": t_battery, "records": battery},
                   "differential": {"seed": seed, "cases": cases, "seconds": t_diff, "records": differential}}, fh)


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

def _classes(record: dict, part: str) -> list[str]:
    """The classes a record counts in (a differential rewrite found unsound counts as fired and unsound)."""
    return [record["class"]] + (["unsound"] if part == "differential" and record.get("unsound") else [])


def _key(record: dict, part: str):
    return record["case"] if part == "differential" else (record["source"], record["input"])


def _cut(text: str, width: int = WIDTH) -> str:
    text = " ".join(str(text).split()).replace("`", "'")
    return text if len(text) <= width else text[:width - 3] + "..."


def _error(result: str) -> str:
    """A crash message without the file paths it may name, cut short."""
    return _cut(re.sub(r" \(/[^)]*\)?", "", result), 120)


def compare_part(old: dict, new: dict, part: str) -> dict:
    """Counts, moves and changed records of one part of two dumps.

    Records are matched by position (the battery repeats some inputs; both
    dumps refine the same list in the same order) and, as a check, by key."""
    a, b = old[part]["records"], new[part]["records"]
    if len(a) != len(b) or any(_key(x, part) != _key(y, part) for x, y in zip(a, b)):
        raise SystemExit(f"{part}: the two dumps refined different inputs (were they made from the same tree?)")
    counts = {side: Counter(c for r in recs for c in _classes(r, part)) for side, recs in (("old", a), ("new", b))}
    changed = [(x, y) for x, y in zip(a, b) if (x["class"], x["result"], x.get("unsound")) !=
               (y["class"], y["result"], y.get("unsound"))]
    moves = Counter((x["class"] + ("/unsound" if x.get("unsound") else ""),
                     y["class"] + ("/unsound" if y.get("unsound") else "")) for x, y in changed)
    return {"total": len(a), "counts": counts, "changed": changed, "moves": moves,
            "seconds": (old[part].get("seconds"), new[part].get("seconds"))}


def _table(classes, counts, old_name, new_name) -> list[str]:
    lines = [f"| | `{old_name}` | `{new_name}` |", "|---|---:|---:|"]
    for c in classes:
        o, n = counts["old"][c], counts["new"][c]
        if o or n:
            lines.append(f"| {c} | {o} | {n}{'' if o == n else f' ({n - o:+d})'} |")
    return lines


def diff(old: dict, new: dict, show: int = 25) -> str:
    """The Markdown summary of two dumps (``old`` at the pin, ``new`` at the candidate)."""
    on, nn = old["satassume"][:7], new["satassume"][:7]
    parts = {p: compare_part(old, new, p) for p in ("battery", "differential")}
    seed, ncases = new["differential"]["seed"], new["differential"]["cases"]
    lines = [(f"Refined by `{PACKAGE}` (combined backend, `PYTHONHASHSEED={new.get('hash_seed')}`), once with "
              f"satassume `{on}` and once with `{nn}`, each in a fresh process "
              f"(`python -m satsimp.tools.refine_compare`): the battery (`tests/refine_identities/battery_v3.py`, "
              f"classified against v3's results as `scoreboard battery` does) and the differential's random inputs "
              f"(seed {seed}, {ncases} cases)."), ""]
    bat, dif = parts["battery"], parts["differential"]
    lines.append(f"**{len(bat['changed'])} of {bat['total']} battery results and {len(dif['changed'])} of "
                 f"{dif['total']} differential results change.**")
    worse = [f"{part} {c} {p['counts']['old'][c]} -> {p['counts']['new'][c]}"
             for part, p in parts.items() for c in BAD[part] if p["counts"]["new"][c] > p["counts"]["old"][c]]
    if worse:
        lines += ["", "**Worse:** " + "; ".join(worse) + "."]
    for part, classes, title in (("battery", BATTERY_CLASSES, "Battery"),
                                 ("differential", DIFF_CLASSES, f"Differential, seed {seed}")):
        p = parts[part]
        lines += ["", f"### {title}", ""] + _table(classes, p["counts"], on, nn)
        so, sn = p["seconds"]
        if so is not None and sn is not None:
            lines += ["", f"Time {so:.0f}s and {sn:.0f}s (one process each; a measurement, not a benchmark)."]
        if not p["changed"]:
            continue
        lines += ["", "Changed: " + ", ".join(f"{a} -> {b} {n}" if a != b else f"{a}, other result {n}"
                                              for (a, b), n in p["moves"].most_common()) + "."]
        errors = Counter(_error(y["result"]) for x, y in p["changed"]
                         if y["class"] in FAILED and x["class"] not in FAILED)
        if errors:
            lines += ["", "New crashes and timeouts by message: " +
                      "; ".join(f"{n} x `{e}`" for e, n in errors.most_common(5)) + "."]
        # answers that moved first, then crashes and timeouts (summarised by message above)
        listed = sorted(p["changed"], key=lambda xy: xy[0]["class"] in FAILED or xy[1]["class"] in FAILED)
        n = len(listed)
        lines += ["", f"<details><summary>The changed results ({n}{f'; the first {show}' if n > show else ''})</summary>",
                  ""]
        for x, y in listed[:show]:
            where = f"`{x['source']}`" if part == "battery" else f"case {x['case']} [{x['head']}]"
            lines.append(f"- {where}: `{_cut(x['input'])}`  ")
            for name, r in ((on, x), (nn, y)):
                label = r["class"] + (", unsound" if r.get("unsound") else "")
                result = _error(r["result"]) if r["class"] in FAILED else _cut(r["result"])
                lines.append(f"  {name}: ({label})  " if r["result"] == r["class"] else f"  {name}: `{result}` ({label})  ")
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m satsimp.tools.refine_compare", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("dump", help="refine the battery and the differential inputs, write JSON")
    p.add_argument("out")
    p.add_argument("--seed", type=int, default=2)
    p.add_argument("--cases", type=int, default=1500)
    p.add_argument("--timeout", type=int, default=60, help="seconds per case (a crash, not a hang)")
    p.add_argument("--expect", metavar="COMMIT", help="fail unless satassume was installed from this commit")
    p = sub.add_parser("diff", help="the Markdown summary of two dumps")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--show", type=int, default=25, help="changed results listed per part")
    args = ap.parse_args(argv)
    if args.command == "dump":
        dump(args.out, args.seed, args.cases, args.timeout, args.expect)
    else:
        with open(args.old) as fa, open(args.new) as fb:
            sys.stdout.write(diff(json.load(fa), json.load(fb), args.show))
    return 0


if __name__ == "__main__":
    sys.exit(main())
