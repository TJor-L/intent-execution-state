# Baseline registry

| ID | Model | Status / comparison purpose |
| --- | --- | --- |
| A | Piecewise exponential competing risks, intercept only | Implemented for synthetic and bounded private clinical label-pipeline validation; no individualized prediction |
| A-age | Piecewise exponential competing risks with fixed age bands and global fallback | Implemented for private feature-pipeline validation; validation-only and not a clinical claim |
| H-availability | Eight-dimensional availability-time history encoder with proportional competing-risk head | Implemented; private validation-only CPU control completed |
| H-dual | Eight-dimensional occurrence-plus-availability history encoder with the same head and budget | Implemented; frozen validation gate held, so test remains sealed |
| B | LightGBM temporal features with a censor-aware target | Planned; must not convert censored cases to negative execution labels |
| C | Single-stream time-aware type-aware Transformer | Planned; strongest direct test of whether explicit structure is needed |
| D | Single-stream marked temporal event model | Planned; controls for continuous event dynamics |
| E | Shared encoder, independent heads | Planned; isolates conditional execution/state factorization |
| P | Order-conditioned execution model | Proposed, unimplemented |

Save input vocabulary, time windows, labels, parameter count, trainable count, training
updates, tuning budget, compute and seed for every model. Match supervision as well
as input data: an auxiliary state target must also be available to the appropriate
control. Use the same patients, horizon and censoring definition across comparisons.
Compare both equal-parameter and equal-compute regimes when they answer different
questions. Do not treat improvement over A alone as methodological evidence.
