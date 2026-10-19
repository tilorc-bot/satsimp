"""Every way a method (or offline code) plugs into the engine: plain module attributes.

The engine reads them at call time (``hooks.name``); a method sets them once, at
load, with :func:`plug` (by name) or in place on :func:`base` (a container).  Nothing in the engine names a specific
SymPy function; what it needs to know about particular heads is a role here.
The hooks are process-wide, and today one method sets them: refine, as listed
below (``docs/architecture.md``, "Adding a method").

Set by :mod:`satsimp.methods.refine.identities.compat` (its ``__init__``):

:data:`dispatcher`
    the refine dispatcher module, the vendored :mod:`satsimp.methods.refine.identities.compat.upstream`: its
    ``ask`` (every query of the engine goes through it, read at call time, so
    a test can patch it and the driver memoizes it per call) and its
    ``handlers_dict`` (the handler registry).
:data:`ask_whole`
    ``ask_whole(condition, assumptions)``: satassume's answer to a compound
    condition, or ``None`` when the backend's ``ask`` is not satassume's or
    satassume leaves the query to SymPy (out of its vocabulary, a relation no
    theory interprets) or finds the assumptions inconsistent.  satassume
    splits cases (``floor(y)`` is a Gaussian integer or infinite, although
    neither alternative holds alone); :func:`.prove.provable` asks the
    undecided alternatives of an ``Or`` a table marks (:func:`.prove.by_cases`)
    with it when none is provable on its own (issue #18).  Read at call time, as the backend is.

Set by :mod:`satsimp.methods.refine.identities.compat.sympy_fixes`:

:data:`rebuild`
    ``rebuild(func, args, assumptions)`` rebuilds a node from its refined
    children (the driver); the ``acot``/``acoth`` guard (B8).
:data:`eval_refine`
    SymPy ``_eval_refine`` method -> the copy the driver calls instead (a
    subclass overriding the method keeps its own).
:data:`eval_method`
    the name of the SymPy method the driver calls on a node before its
    handler (``"_eval_refine"``, the default; ``None``: none).

Filled by refine's generated tables (``generated/__init__.py``):

:data:`generated`
    key -> handler from the generated rule tables, tried before the
    dispatcher's handler (``driver.generated_handlers`` is this dict).

Set by :mod:`satsimp.methods.refine.identities.compat.matrix_match`:

:data:`match`
    matchers for pattern kinds the generic matcher does not know:
    ``hook(pattern, target, assumptions, binding, top)`` returns ``None`` when
    ``pattern`` is not of its kind (matching goes on with the generic forms),
    else an iterator of bindings (the only ones).
:data:`non_scalar`
    sum and product heads that are not scalar sums and products (``MatAdd``,
    ``MatMul``): the rest-symbol and sub-product forms skip them.
:data:`commutative`
    heads matched in every argument order (small arities).

Set by :func:`satsimp.methods.refine.identities.rules._simple.install`:

:data:`fallback`
    key -> handler tried by the driver after the key's handler declines.
:data:`own_args`
    keys whose handler refines the node's arguments itself (``Piecewise``).
:data:`opaque`
    the default opaque heads of identity rows (``floor``, ``im``, ``arg``):
    a candidate still holding one is not accepted (:func:`.rewrite.identity_handler`,
    :func:`.split.case_split` with ``opaque=None``).
:data:`conditional`
    the head of a conditional expression (``Piecewise``): a candidate with a
    new one is an undecided definition, not a rewrite.
:data:`modulus`
    the modulus head (``Abs``): canonical in :func:`.measure.default_measure`,
    what :func:`.split.case_split` generalizes its cases by.
:data:`step`
    the step head (``floor``) the endpoint split (:func:`.split.endpoint_split`) resolves.
:data:`two_valued`
    ``two_valued(node, assumptions)``: ``(value, u, endpoint, alternative)`` when
    the step node is ``value`` except at one closed endpoint ``u = endpoint``
    (:func:`satsimp.methods.refine.identities.rules._simple.floor_two_valued`), else ``None``.

Pushed by offline code (:mod:`satsimp.build`) through :func:`.driver.observing`:

:data:`observer`
    a stack of :class:`Observer`; the innermost one is consulted.  Its
    ``on_fire(kind, row)`` is called on each table-row firing (``kind``
    ``"rule"`` or ``"identity"``), and its ``tables(key)``, when set, gives the
    generated table the driver uses for ``key`` (``None``: none), whatever the mode.

Another method runs the engine with hooks of its own: :func:`installed` sets
every hook for a block and restores refine's (the values set at load) after
it, so refine's settings and registries are neither read nor changed by it.
A method imported inside such a block still sets its hooks outside it
(:func:`plug`, :func:`base`).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator, NamedTuple

from sympy.core import Add, Mul
from sympy.core.operations import LatticeOp


dispatcher: Any = None


def ask_whole(condition: Any, assumptions: Any) -> bool | None:
    """The default: no compound condition is asked whole."""
    return None


def rebuild(func: Any, args: Any, assumptions: Any) -> Any:
    """The default: ``func(*args)``."""
    return func(*args)


eval_refine: dict = {}
eval_method: str | None = "_eval_refine"
generated: dict = {}

match: list = []
non_scalar: tuple = ()
commutative: tuple = (Add, Mul, LatticeOp)

fallback: dict = {}
own_args: set = set()

opaque: tuple = ()
conditional: Any = None
modulus: Any = None
step: Any = None


def two_valued(node: Any, assumptions: Any) -> tuple | None:
    """The default: no step node is two-valued."""
    return None


class Observer(NamedTuple):
    """One entry of :data:`observer` (see :func:`.driver.observing`)."""
    on_fire: Callable | None
    tables: Callable | None


observer: list[Observer] = []


def _defaults() -> dict[str, Any]:
    """Every hook's value before any method sets it (new containers on each call)."""
    return {
        "dispatcher": None, "ask_whole": ask_whole_default, "rebuild": rebuild_default,
        "eval_refine": {}, "eval_method": "_eval_refine", "generated": {},
        "match": [], "non_scalar": (), "commutative": (Add, Mul, LatticeOp),
        "fallback": {}, "own_args": set(), "opaque": (), "conditional": None,
        "modulus": None, "step": None, "two_valued": two_valued_default, "observer": [],
    }


ask_whole_default, rebuild_default, two_valued_default = ask_whole, rebuild, two_valued


_outside: list[dict] = []
"""The hooks each active :func:`installed` block restores after it, outermost
first: ``_outside[0]`` is what holds outside every block."""


def base(name: str) -> Any:
    """Hook ``name`` as it is outside every :func:`installed` block: the container a
    method fills at load (in place), whether or not it is imported inside one."""
    return _outside[0][name] if _outside else globals()[name]


def plug(**values: Any) -> None:
    """Set hooks (by name) at load: outside every :func:`installed` block, so a
    method imported inside one sets them for afterwards, and the block goes on
    with its own."""
    unknown = set(values) - set(_defaults())
    if unknown:
        raise TypeError(f"unknown hooks: {sorted(unknown)}")
    (_outside[0] if _outside else globals()).update(values)


def block() -> Any:
    """A token of the innermost active :func:`installed` block (``None`` outside every block)."""
    return _outside[-1] if _outside else None


@contextmanager
def installed(**values: Any) -> Iterator[None]:
    """Run the block with these hooks (by name), every other hook at its
    default, and restore the hooks as they were after it: how a method other
    than refine runs the engine (``docs/architecture.md``).

    A method plugs in at load through :func:`plug` and :func:`base`, which
    set the hooks outside every block: a method first imported inside one
    (refine, there) leaves the block's hooks alone and works after it.  A hook
    rebound directly inside the block (``hooks.name = ...``) would be lost:
    :class:`RuntimeError`."""
    fresh = _defaults()
    unknown = set(values) - set(fresh)
    if unknown:
        raise TypeError(f"unknown hooks: {sorted(unknown)}")
    fresh.update(values)
    module = globals()
    saved = {name: module[name] for name in fresh}
    _outside.append(saved)
    module.update(fresh)
    try:
        yield
    finally:
        rebound = sorted(name for name in fresh if module[name] is not fresh[name])
        _outside.pop()
        module.update(saved)
    if rebound:
        raise RuntimeError(f"hooks {rebound} were rebound inside an installed() block; "
                           "a method sets its hooks with hooks.plug() and hooks.base()")
