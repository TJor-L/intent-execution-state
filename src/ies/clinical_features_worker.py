"""Resource-limited worker for reviewed bounded clinical features."""

import hashlib
import os
import sys
from pathlib import Path

import yaml

from ies.clinical_features import ClinicalFeatureError, extract_clinical_features
from ies.clinical_protocol import parse_protocol
from ies.cohort_readiness.eligibility import load_eligibility_mapping
from ies.feasibility.worker import apply_limits


def main() -> int:
    try:
        if len(sys.argv) != 7:
            raise ClinicalFeatureError("invalid_feature_arguments")
        mapping_path, protocol_path, cohort_dir, output_dir = map(Path, sys.argv[1:5])
        mapping, mapping_digest = load_eligibility_mapping(mapping_path)
        protocol_bytes = protocol_path.read_bytes()
        protocol_digest = hashlib.sha256(protocol_bytes).hexdigest()
        if mapping_digest != sys.argv[5] or protocol_digest != os.environ.get(
            "IES_PROTOCOL_SHA256"
        ):
            raise ClinicalFeatureError("feature_inputs_changed")
        protocol = parse_protocol(yaml.safe_load(protocol_bytes))
        if protocol.status != "frozen":
            raise ClinicalFeatureError("invalid_feature_protocol")
        apply_limits(mapping.limits)
        extract_clinical_features(
            mapping,
            protocol.minimum_eligible_orders,
            protocol.minimum_execution_events,
            cohort_dir,
            output_dir,
            sys.argv[6],
            mapping_digest,
            protocol_digest,
            os.environ.get("IES_EXPECTED_COMMIT", ""),
        )
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
