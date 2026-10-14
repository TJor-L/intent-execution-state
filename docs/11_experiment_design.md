# Experiment design

## E000: implemented infrastructure smoke test

Dataset: generated fictional trajectories, seed 20261014, 300 patients, two orders
per patient. Train/validation/test: 70/15/15% by patient. Model: baseline A.
Endpoint: held-out observed-data competing-risk NLL in hours; report a patient-cluster
bootstrap interval. Purpose: verify the end-to-end executable path, not test novelty.
Each run has immutable output directory, configuration, revision and artifact hashes.

## E001: feasibility, not yet executed

On UCSF, verify direct linkage, status semantics, clock consistency, observation
coverage and eligible medication categories. Predefine acceptable linkage completeness,
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
