"""Resource-limited worker for matched clinical history models."""

import os
import sys
from pathlib import Path

import pyarrow as pa

from ies.clinical_baseline import ClinicalBaselineError
from ies.clinical_history_models import load_history_model_config, run_clinical_history_models
from ies.feasibility.worker import apply_limits


class _Limits:
    memory_mb = 4096
    cpu_seconds = 1200
    cpus = 2


def main() -> int:
    try:
        if len(sys.argv) != 8:
            raise ClinicalBaselineError("invalid_history_model_arguments")
        cohort_dir, history_dir, config_path, output_dir = map(Path, sys.argv[1:5])
        config, config_digest = load_history_model_config(config_path)
        if config_digest != sys.argv[5]:
            raise ClinicalBaselineError("history_model_inputs_changed")
        apply_limits(_Limits)
        run_clinical_history_models(
            cohort_dir,
            history_dir,
            output_dir,
            config,
            config_digest,
            os.environ.get("IES_COHORT_MANIFEST_SHA256", ""),
            sys.argv[6],
            sys.argv[7],
        )
        return 0
    except (MemoryError, pa.ArrowMemoryError):
        return 72
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
