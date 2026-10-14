"""Internal worker; configure Linux resource ceilings before importing Arrow/NumPy."""

import os
import resource
import sys
from pathlib import Path

from ies.feasibility.contract import FeasibilityError, load_mapping_snapshot
from ies.io import write_json


def apply_limits(limits):
    if sys.platform != "linux":
        raise FeasibilityError("linux_resource_limits_required")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (limits.memory_mb * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds + 1))
    available = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, set(available[: limits.cpus]))


def main() -> int:
    try:
        path, output, expected_hash = sys.argv[1:]
        path = Path(path)
        mapping, digest = load_mapping_snapshot(path)
        if digest != expected_hash:
            raise FeasibilityError("mapping_changed")
        apply_limits(mapping.limits)
        from ies.feasibility.reader import inspect_sources

        write_json(Path(output), inspect_sources(mapping))
        return 0
    except MemoryError:
        return 72
    except FeasibilityError as error:
        return 71 if str(error) == "runtime_limit" else 70
    except Exception:
        # Suppress payloads from YAML, filesystem, Arrow and row conversion failures.
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
