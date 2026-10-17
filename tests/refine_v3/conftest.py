"""Fixtures for the ``handlers_v3`` tests.

These tests target ``handlers_v3``; the module below selects it before
``satsimp`` is imported so a plain ``pytest tests/refine_v3`` works.
Setting ``SATSIMP_HANDLERS`` to another package runs this suite as a
cross-check of that package; ``SATSIMP_BACKEND`` selects the ask backend
(default ``combined``) as everywhere else.
"""
from __future__ import annotations

import os
import sys

import pytest

from satsimp.engine.config import env_setdefault   # imports no method: the handler package is chosen first

env_setdefault("HANDLERS", "handlers_v3")
if "satsimp.methods.refine" in sys.modules and \
        "satsimp.methods.refine." + os.environ["SATSIMP_HANDLERS"] not in sys.modules:
    raise RuntimeError("satsimp.methods.refine was imported before conftest selected the handler package")

from satsimp.testing.harness import query_scope_recorder  # noqa: E402


@pytest.fixture(autouse=True)
def _record_query_scope(request: pytest.FixtureRequest):
    """Count each test's queries by satassume scope category (see the harness)."""
    yield from query_scope_recorder()(request)
