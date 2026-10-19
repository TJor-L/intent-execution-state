"""Generated-only capacity measurement; not a clinical run or a Linux limit test."""

import json
import os
import resource
import sys
import time
from pathlib import Path

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "2"

import numpy as np  # noqa: E402

from ies.selection_cv import load_config, run_selection_cv  # noqa: E402
from ies.selection_demo import generate_case  # noqa: E402

started = time.monotonic()
config, _ = load_config(Path("configs/workflow_selection.yaml"))
cohort, history, _ = generate_case(
    20261023, "time_varying", "feature_dependent_censoring", patients=10000
)
for events in history.values():
    level = len(events) // 2 - 1
    lags = np.linspace(0.1 + level, 20 + level, 24)
    events[:] = [
        dict(event_kind=i % 2, occurrence_lag_hours=float(lag), availability_lag_hours=float(lag))
        for i, lag in enumerate(lags)
    ]
report, models = run_selection_cv(cohort, history, config, data_class="synthetic")
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(
    json.dumps(
        dict(
            data_class="synthetic",
            orders=len(cohort),
            history_rows=sum(map(len, history.values())),
            fits=480,
            seconds=round(time.monotonic() - started, 2),
            peak_rss_mib=round(rss / (1024**2 if sys.platform == "darwin" else 1024), 2),
            report_bytes=len(json.dumps(report).encode()),
            model_bytes=len(json.dumps(models).encode()),
            linux_resource_limits_verified=False,
        )
    )
)
