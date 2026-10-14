# Statistical analysis

The implemented bootstrap resamples patient clusters with replacement, retaining all
orders within each sampled patient. For each draw calculate mean per-order NLL; the
2.5/97.5 percentiles form a 95% interval. This targets the order-weighted endpoint
while preserving patient dependence. It conditions on the trained model and split;
it does not include training or model-selection uncertainty.

For method comparisons bootstrap paired per-patient predictions from both models
using the same resampled clusters. Run multiple prespecified random seeds to quantify
optimization sensitivity, and separately report between-seed variability. Do not pool
orders as independent observations or treat seed-by-patient repetitions as new patients.

Freeze one primary comparison and endpoint. Label subgroup and ablation findings
exploratory; use prespecified multiplicity control where confirmatory claims are needed.
Assess power/precision after feasibility using realistic event and censoring rates.
Phase 0 uses 200 replicates for a fast smoke test, not a publication precision target.
