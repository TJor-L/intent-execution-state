"""Resource-limited worker for private bounded cohort extraction."""

import hashlib
import os
import sys
from pathlib import Path

import yaml

from ies.clinical_protocol import parse_protocol
from ies.cohort_readiness.eligibility import EligibilityError, load_eligibility_mapping
from ies.cohort_readiness.extract import extract_cohort
from ies.feasibility.worker import apply_limits


def main() -> int:
    try:
        if len(sys.argv) != 6:
            raise EligibilityError("invalid_extraction_arguments")
        mapping_path, protocol_path, output_dir = map(Path, sys.argv[1:4])
        mapping, mapping_digest = load_eligibility_mapping(mapping_path)
        protocol_bytes = protocol_path.read_bytes()
        protocol_digest = hashlib.sha256(protocol_bytes).hexdigest()
        if mapping_digest != sys.argv[4] or protocol_digest != sys.argv[5]:
            raise EligibilityError("extraction_inputs_changed")
        protocol = parse_protocol(yaml.safe_load(protocol_bytes))
        if protocol.status != "frozen":
            raise EligibilityError("eligibility_protocol_not_frozen")
        commit = os.environ.get("IES_EXPECTED_COMMIT", "")
        apply_limits(mapping.limits)
        extract_cohort(
            mapping,
            protocol.minimum_eligible_orders,
            protocol.minimum_execution_events,
            output_dir,
            mapping_digest,
            protocol_digest,
            commit,
        )
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
