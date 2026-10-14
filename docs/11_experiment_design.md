# Experiment design

## E000: implemented infrastructure smoke test

Dataset: generated fictional trajectories, seed 20261014, 300 patients, two orders
per patient. Train/validation/test: 70/15/15% by patient. Model: baseline A.
Endpoint: held-out observed-data competing-risk NLL in hours; report a patient-cluster
bootstrap interval. Purpose: verify the end-to-end executable path, not test novelty.
Each run has immutable output directory, configuration, revision and artifact hashes.

## E001: feasibility, not yet executed

The first E001 code deliverable is now a generic bounded feasibility validator,
not a clinical cohort extractor. The approved server handoff reports direct linkage
is structurally feasible, repeated administrations are common, encounter equality
cannot be assumed, and independent lab availability is not yet reviewed.

On UCSF, use a reviewed local mapping to count linkage consistency, qualifying actions,
repeats, timing violations and first-event eligibility within explicit limits. Every
truncated scan is labeled `limited`; it cannot confirm absence of another dose or
right censoring. Inspect server-local counts before authorizing any cohort extraction.
No clinical run of this new validator has been performed by the Mac agent.

The server stopped the first configuration attempt before job submission because
time normalization, execution availability and a third observation source could not
be represented truthfully (docs/23_feasibility_contract_gaps.md). Version 2 implements
these concepts but does not establish their real source semantics. Review the common
clock, direct coverage join and retrospective endpoint ascertainment on UCSF. Execution
equality needs independent evidence and a mapped retrospective-exclusion rule; lack
of evidence remains a blocker, even though the software now supports the policy.

Predefine acceptable linkage completeness,
ambiguity, event coverage and sample size after discussing the source definitions.
Do not invent numerical acceptance thresholds without measuring the setting.
No baseline clinical result exists until these conditions and a cohort are reviewed.

## E002: primary method comparison, pending feasibility

Primary comparison: structured model P versus type-aware model C with matched inputs,
capacity and labels. Primary endpoint: test competing-risk NLL; key secondary outcomes
are calibration and relevant state/transfer performance. Freeze the meaningful effect
threshold, seeds, splits and tuning budget before test evaluation. Use validation
for model selection, and preserve the test set for the final comparison.

Secondary experiments: training fractions 1/5/10/25/100% sampled by patient, medication
and department subgroups, synthetic delay shifts, representation transfer, and
independent-head ablations. A shift experiment uses training-fitted parameters unchanged
on a separately generated shifted test set; rerunning the full pipeline at another
delay scale alone is not a robustness test. Multi-model/shift runners remain planned.
