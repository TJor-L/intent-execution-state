"""Internal W001 worker; enforce Linux resource limits before Arrow and NumPy imports."""

import sys
from pathlib import Path

from ies.feasibility.worker import apply_limits


class _Limits:
    memory_mb = 4096
    cpu_seconds = 1200
    cpus = 2


def main():
    try:
        if len(sys.argv) != 9:
            return 70
        from ies.feasibility.runner import verify_execution_context

        verify_execution_context()
        apply_limits(_Limits)
        from ies.clinical_workflow import run_clinical_workflow

        run_clinical_workflow(*map(Path, sys.argv[1:5]), *sys.argv[5:9])
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
