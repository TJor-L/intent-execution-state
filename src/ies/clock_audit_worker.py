"""Internal bounded worker; set Linux limits before importing Arrow or audit code."""

import sys
from pathlib import Path

from ies.feasibility.worker import apply_limits


class _Limits:
    memory_mb = 4096
    cpu_seconds = 300
    cpus = 2


def main() -> int:
    try:
        if len(sys.argv) != 7:
            return 70
        from ies.feasibility.runner import verify_execution_context

        verify_execution_context()
        apply_limits(_Limits)
        from ies.clock_audit import audit_training_clocks

        audit_training_clocks(*map(Path, sys.argv[1:4]), *sys.argv[4:7])
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
