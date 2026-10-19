"""trigsimp's rows, one module per family: ``normal`` (the normalizing pass),
``quotients``, ``pythagorean`` and ``angles`` (substitution rows; ``quotients``
also has conditional rule rows for other powers), ``moduli`` and ``inverses``
(conditional rule rows), and ``signs`` (the sign table, facts added to the
questions trigsimp asks); each states the circular rows and their hyperbolic
counterparts where there are any.  A module states rows only, in module-level
tables (``RULES``: rule rows; ``SUBSTITUTIONS``: substitution rows,
:mod:`..substitute`; ``ROWS``: the sign table); which handlers they serve is
:mod:`..wiring`."""
