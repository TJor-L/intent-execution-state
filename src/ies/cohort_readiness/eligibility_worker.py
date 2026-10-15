"""Resource-limited aggregate eligibility worker."""

import hashlib
import sys
from pathlib import Path

import yaml

from ies.clinical_protocol import parse_protocol
from ies.cohort_readiness.eligibility import (
    EligibilityError,
    audit_eligibility,
    load_eligibility_mapping,
)
from ies.feasibility.worker import apply_limits
from ies.io import write_json


def main() -> int:
    try:
        if len(sys.argv) != 6:
            raise EligibilityError("invalid_eligibility_arguments")
        mapping_path = Path(sys.argv[1])
        protocol_path = Path(sys.argv[2])
        output_path = Path(sys.argv[3])
        mapping, mapping_digest = load_eligibility_mapping(mapping_path)
        protocol_bytes = protocol_path.read_bytes()
        protocol_digest = hashlib.sha256(protocol_bytes).hexdigest()
        if mapping_digest != sys.argv[4] or protocol_digest != sys.argv[5]:
            raise EligibilityError("eligibility_inputs_changed")
        protocol = parse_protocol(yaml.safe_load(protocol_bytes))
        if protocol.status != "frozen":
            raise EligibilityError("eligibility_protocol_not_frozen")
        apply_limits(mapping.limits)
        report = audit_eligibility(
            mapping,
            protocol.minimum_eligible_orders,
            protocol.minimum_execution_events,
        )
        write_json(output_path, report)
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
