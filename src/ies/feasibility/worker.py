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
        if len(sys.argv) not in (4, 6):
            raise FeasibilityError("invalid_worker_arguments")
        path, output, expected_hash = sys.argv[1:4]
        path = Path(path)
        mapping, digest = load_mapping_snapshot(path)
        if digest != expected_hash:
            raise FeasibilityError("mapping_changed")
        apply_limits(mapping.limits)
        if len(sys.argv) == 6:
            from ies.feasibility.access import inspect_coherent_sources, load_access_snapshot

            access_path, expected_access_hash = Path(sys.argv[4]), sys.argv[5]
            manifest, access_hash = load_access_snapshot(access_path, mapping, digest)
            if access_hash != expected_access_hash:
                raise FeasibilityError("access_manifest_changed")
            report = inspect_coherent_sources(mapping, manifest)
        else:
            from ies.feasibility.reader import inspect_sources

            report = inspect_sources(mapping)
        write_json(Path(output), report)
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
