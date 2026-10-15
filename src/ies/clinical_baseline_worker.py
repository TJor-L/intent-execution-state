"""Resource-limited worker for the private intercept-only clinical baseline."""

import os
import sys
from pathlib import Path

from ies.clinical_baseline import (
    ClinicalBaselineError,
    load_baseline_config,
    run_clinical_baseline,
)
from ies.feasibility.worker import apply_limits


class _Limits:
    memory_mb = 4096
    cpu_seconds = 1200
    cpus = 2


def main() -> int:
    try:
        if len(sys.argv) != 6:
            raise ClinicalBaselineError("invalid_baseline_arguments")
        cohort_dir, config_path, output_dir = map(Path, sys.argv[1:4])
        config, config_digest = load_baseline_config(config_path)
        if config_digest != sys.argv[4]:
            raise ClinicalBaselineError("baseline_inputs_changed")
        apply_limits(_Limits)
        run_clinical_baseline(
            cohort_dir,
            output_dir,
            config,
            config_digest,
            sys.argv[5],
            os.environ.get("IES_EXPECTED_COMMIT", ""),
        )
        return 0
    except MemoryError:
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
