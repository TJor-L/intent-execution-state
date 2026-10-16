# Provisional eight-week plan

Status: **stopped after the bounded Phase 1 controls**. Weeks 3–8 are cancelled rather
than executed with unreviewed availability semantics. No GPU training is authorized.

| Week | Deliverable | Exit criterion |
| --- | --- | --- |
| 1 | Phase 0 repository, synthetic pipeline, Git handoff, metadata audit | Local checks pass; server execution separately verified |
| 2 | Direct linkage and cohort feasibility | Status/timestamp semantics reviewed; ambiguous labels quantified |
| 3 | Cancelled: richer CPU/LightGBM baselines | Feature availability semantics unavailable |
| 4 | Cancelled: single-stream neural baseline | Leakage-safe inputs unavailable |
| 5 | Cancelled: structured order-conditioned model | Fair matched comparison cannot be constructed |
| 6 | Cancelled: state prediction | Measurement-time estimand unavailable |
| 7 | Cancelled: ablations and shifts | Prerequisite models absent |
| 8 | Negative feasibility record only | Claims limited to infrastructure and stopping rationale |

This schedule depends on access, semantic validation and compute availability. Extend
or stop phases when their exit criteria fail. Eight H200 GPUs are potential resources,
not an execution plan. Start neural work on one GPU only after small-model feasibility
and the CPU baselines are reviewed.
