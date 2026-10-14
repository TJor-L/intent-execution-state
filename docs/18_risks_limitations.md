# Risks and go/no-go decisions

| Risk | Diagnostic | Decision |
| --- | --- | --- |
| Weak novelty / prior overlap | Targeted primary-literature comparison | Redesign before scaling |
| Unreliable direct linkage | Server-side key and consistency audit | Stop if most labels require speculative matching |
| Shifted or coarse clocks | Within-patient sequence/interval checks | Stop temporal modeling if ordering cannot be established |
| Ambiguous administration semantics | Source dictionary and workflow review | Exclude unresolved categories; do not invent state labels |
| Informative censoring | Discharge/coverage analysis and sensitivity checks | Reframe estimand or model censoring |
| Future leakage | Availability-time tests and cutoff audit | Invalidate and rerun affected experiments |
| Patient overlap | Identity-level partition checks | Invalidate affected estimates |
| Treatment confounding | Explicit predictive target and assumptions | Do not claim causal effects |
| Measurement-time bias | Model/stratify observation process | Do not call first post-treatment lab fixed-time outcome |
| Workflow/institution specificity | Department and external replication tests | Bound generalization claim |

Stop or redesign if a strong type-aware Transformer matches the structured model,
if gains disappear under parameter matching, or if execution gains do not translate
to meaningful representation/state benefits. A nonsignificant comparison with wide
uncertainty is not proof of equivalence; obtain enough precision before that conclusion.
No numerical feasibility cutoff is asserted before source semantics and sample size
are known. Freeze those thresholds before the final clinical experiments.
