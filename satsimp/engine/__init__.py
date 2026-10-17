"""The machinery every simplification method shares (``docs/architecture.md``).

The driver (:mod:`.driver`) and its termination guard (:mod:`.guard`), proving
conditions through ``ask`` (:mod:`.prove`), pattern matching (:mod:`.match`),
rewriting with identity and rule tables (:mod:`.rewrite`, :mod:`.measure`), case
splits (:mod:`.split`), families as data (:mod:`.spec`), the ``ask`` backend
(:mod:`.backend`) and the engine's environment switches (:mod:`.config`).  What a
method plugs in (its dispatcher and handler registry, SymPy workarounds, matcher
extensions, the head roles) goes through :mod:`.hooks`.  Nothing here imports a
method (``tests/refine_identities/test_import_direction.py``).
"""
