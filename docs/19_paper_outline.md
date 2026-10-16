# Manuscript outline

Status: **not proceeding to a primary-method manuscript**. The required leakage-safe
feature semantics were unavailable. This outline is retained as historical planning only;
no unexecuted experiment or private result should be presented as completed evidence.

1. Abstract: concrete predictive task, validated cohort, matched comparison and effect
   estimates. Do not prefill positive findings.
2. Introduction: distinction between decisions, executed care and observations; why
   ordinary type embeddings are a strong alternative.
3. Related work: EHR representation, competing risks, point processes and workflow;
   explicitly discuss the closest method and remaining contribution.
4. Methods: availability-aware event contract, cohort, censoring, factorization,
   loss, fair baselines and conditional (not causal) interpretation.
5. Experiments: patient partitions, endpoints, seeds, resource budget, calibration,
   state prediction, transfer, ablations, workflow shifts and uncertainty.
6. Results: primary comparison first, then secondary effects and failures; distinguish
   clinical findings from synthetic mechanism checks.
7. Discussion: confounding, timing/recording bias, institutional generalization,
   feasibility failures and cases where structural modeling adds no value.
8. Reproducibility/ethics: public synthetic code, private-data constraints, approved
   disclosure and controlled-access external replication.

Tables planned: cohort flow and exclusions; source semantics; model/input/parameter
matching; primary endpoint; calibration/state outcomes; ablations; shift experiments.
Figures planned: availability-aware event timeline, architecture, CIF/calibration,
data-efficiency curves. Check the actual conference template and rules at submission;
this outline does not assert current page limits or deadlines.
