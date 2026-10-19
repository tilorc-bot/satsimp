"""Shared pytest configuration."""
from pathlib import Path

import pytest

TREES = ("refine", "refine_identities", "refine_v3")
"""Test trees that each need their own pytest process: each conftest selects a
handler package, which registers into the one process-wide ``handlers_dict``
(and ``refine_v3``'s modules import ``reference.v3`` families, registering them
too), so a session collecting two trees runs both against a mixed registry."""


def _trees(config: pytest.Config) -> set[str]:
    here = Path(__file__).resolve().parent
    ignored = [Path(p).resolve() for p in config.getoption("ignore") or ()]
    found = set()
    for arg in config.args:
        path = Path(arg.split("::")[0]).resolve()
        for tree in TREES:
            root = here / tree
            if (path == root or root in path.parents or path in root.parents) and \
                    not any(i == root or i in root.parents for i in ignored):
                found.add(tree)
    return found


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: long-running test, skipped unless enabled by an environment variable")
    trees = _trees(config)
    if len(trees) > 1:
        raise pytest.UsageError(
            f"these test trees must run in separate pytest processes: {', '.join(sorted(trees))}; "
            "run one tree per pytest (README.md, .github/workflows/test.yml)")
