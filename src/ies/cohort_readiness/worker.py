"""Resource-limited vocabulary worker with sanitized process boundaries."""

import sys
from pathlib import Path

from ies.cohort_readiness.contract import CohortAuditError, load_vocabulary_mapping
from ies.feasibility.worker import apply_limits
from ies.io import write_json


def main() -> int:
    try:
        if len(sys.argv) != 4:
            raise CohortAuditError("invalid_cohort_audit_arguments")
        mapping_path, output_path, expected_digest = map(Path, sys.argv[1:])
        mapping, digest = load_vocabulary_mapping(mapping_path)
        if digest != str(expected_digest):
            raise CohortAuditError("cohort_audit_mapping_changed")
        apply_limits(mapping.limits)
        from ies.cohort_readiness.vocabulary import scan_vocabulary

        write_json(output_path, scan_vocabulary(mapping))
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
