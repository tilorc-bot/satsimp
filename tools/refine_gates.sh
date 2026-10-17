#!/usr/bin/env bash
# Moved to satsimp/tools/refine_gates.sh; this shim (kept for phase 3) runs it with the same arguments.
exec "$(dirname "$0")/../satsimp/tools/refine_gates.sh" "$@"
