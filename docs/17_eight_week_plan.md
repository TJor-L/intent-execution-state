# Provisional eight-week plan

Status: **historical schedule; E003 stopped at its CPU advancement gate**. Cancelled
physiology work remains cancelled. Weeks 4–8 below are not an active execution plan:
no sequence model, test evaluation or GPU job is scheduled. Current work is Mac-led
implementation review and generated tests. Any successor design must be distinguished
from E003, with validation reuse addressed before a new clinical comparison.
The completed A001 audit also leaves the proposed clock-pairing successor without
support in the retained training histories. The user subsequently authorized W001's
fixed-data single-clock workflow pivot. Its CPU development design is in docs/11;
the following weeks remain historical and must not be resumed as automatic tasks.

| Week | Deliverable | Exit criterion |
| --- | --- | --- |
| 1 | Phase 0 repository, synthetic pipeline, Git handoff, metadata audit | Local checks pass; server execution separately verified |
| 2 | Direct linkage and cohort feasibility | Status/timestamp semantics reviewed; ambiguous labels quantified |
| 3 | Complete dual-clock order/administration history and CPU controls | Full-source coverage and availability masks verified |
| 4 | Single-clock and dual-clock workflow sequence baselines | Validation-only runs reproducible without leakage |
| 5 | Documentation-delay interventions and matched comparison | Architecture and validation decision frozen before test |
| 6 | Cancelled: state prediction | Measurement-time estimand unavailable |
| 7 | Workflow-only ablations and delay shifts | Prespecified comparisons complete, including negative results |
| 8 | Single test evaluation and reporting | Claims limited to workflow prediction and approved disclosure |

This schedule depends on access, semantic validation and compute availability. Extend
or stop phases when their exit criteria fail. Eight H200 GPUs are potential resources,
not an execution plan. Start neural work on one GPU only after small-model feasibility
and the CPU baselines are reviewed.
