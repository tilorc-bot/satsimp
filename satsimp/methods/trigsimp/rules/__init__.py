"""trigsimp's rows, one module per family: ``normal`` (the normalizing pass),
``quotients`` and ``pythagorean`` (substitution rows).  A module states rows
only, in module-level tables (``RULES``: rule rows; ``SUBSTITUTIONS``:
substitution rows, :mod:`..substitute`); which handlers they serve is
:mod:`..wiring`."""
