# Provisional eight-week plan

| Week | Deliverable | Exit criterion |
| --- | --- | --- |
| 1 | Phase 0 repository, synthetic pipeline, Git handoff, metadata audit | Local checks pass; server execution separately verified |
| 2 | Direct linkage and cohort feasibility | Status/timestamp semantics reviewed; ambiguous labels quantified |
| 3 | CPU clinical statistical and LightGBM baselines | Censor-aware endpoint and patient splits locked |
| 4 | Single-stream neural baseline | Reproducible small-scale training, no leakage |
| 5 | Structured order-conditioned model | Parameter/input-matched comparison runnable |
| 6 | Clinically grounded state prediction | Measurement-time estimand and missingness handled |
| 7 | Ablations, data efficiency, workflow shifts | Prespecified comparisons complete including negative results |
| 8 | Statistical evaluation and manuscript | Claims match evidence and disclosure approval |

This schedule depends on access, semantic validation and compute availability. Extend
or stop phases when their exit criteria fail. Eight H200 GPUs are potential resources,
not an execution plan. Start neural work on one GPU only after small-model feasibility
and the CPU baselines are reviewed.
