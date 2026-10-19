"""Internal bounded worker; limits precede imports of Arrow/NumPy."""

import sys
from pathlib import Path

from ies.feasibility.worker import apply_limits


class _Limits:
    memory_mb = 4096
    cpu_seconds = 1200
    cpus = 2


def main():
    try:
        if len(sys.argv) != 12:
            return 70
        from ies.feasibility.runner import verify_execution_context

        verify_execution_context()
        apply_limits(_Limits)
        from ies.clinical_selection import run_clinical_selection

        run_clinical_selection(*map(Path, sys.argv[1:6]), *sys.argv[6:12])
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
