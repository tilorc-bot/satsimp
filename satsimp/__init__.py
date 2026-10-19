"""Simplification methods as rule tables, with conditions proved by satassume's ``ask``.

``satsimp.refine(expr, assumptions)`` is SymPy's ``refine`` rewritten this way
(:mod:`satsimp.methods.refine`); ``refine(..., strict=True)`` takes facts only as Q
facts and raises :class:`AssumptionSymbolError` on symbols declared with assumptions
(:mod:`satsimp.engine.strict`).  The shared machinery is :mod:`satsimp.engine`;
each method is a package under :mod:`satsimp.methods` (``docs/architecture.md``).

A method is imported when it is first used, so importing :mod:`satsimp` loads
none of them and one method never pays for another's import.
"""
from __future__ import annotations

__all__ = ["AssumptionSymbolError", "refine"]


def __getattr__(name: str):
    if name == "refine":
        from .methods.refine import refine
        globals()["refine"] = refine   # later lookups are plain attribute reads
        return refine
    if name == "AssumptionSymbolError":   # refine(..., strict=True) raises it (satsimp.engine.strict)
        from .engine.strict import AssumptionSymbolError
        globals()[name] = AssumptionSymbolError
        return AssumptionSymbolError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
