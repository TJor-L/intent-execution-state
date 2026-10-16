"""Resource-limited worker for private dual-clock history extraction."""

import os
import sys
from pathlib import Path

import pyarrow as pa

from ies.cohort_readiness.eligibility import load_eligibility_mapping
from ies.dual_clock_history import HistoryError, extract_history, load_history_config
from ies.feasibility.worker import apply_limits


def main() -> int:
    try:
        if len(sys.argv) != 7:
            raise HistoryError("invalid_history_arguments")
        mapping_path, config_path, cohort_dir, output_dir = map(Path, sys.argv[1:5])
        mapping, mapping_digest = load_eligibility_mapping(mapping_path)
        config, config_digest = load_history_config(config_path)
        if mapping_digest != sys.argv[5] or config_digest != os.environ.get(
            "IES_HISTORY_CONFIG_SHA256"
        ):
            raise HistoryError("history_inputs_changed")
        apply_limits(mapping.limits)
        extract_history(
            mapping.feasibility,
            mapping.limits,
            cohort_dir,
            output_dir,
            config,
            config_digest,
            sys.argv[6],
            mapping_digest,
            os.environ.get("IES_EXPECTED_COMMIT", ""),
        )
        return 0
    except (MemoryError, pa.ArrowMemoryError):
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
