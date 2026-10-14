# Model architecture and implementation boundary

Current executable model: an intercept-only piecewise exponential competing-risk
baseline. It has one positive rate for each time bin and cause, no encoder and no
learned use of cohort features. Its purpose is to validate labels and likelihood.

Planned encoder: a single time-aware sequence encoder with event type/code, measurement
and elapsed-time inputs. Available history is encoded once per order. The order head
predicts intention events, an execution head conditions on the available index order,
and a state head conditions on executed history known at the prediction cutoff.

Each component needs an isolation experiment. Removing conditional pathways must
leave input coverage and parameter budget comparable. A shared encoder with independent
heads is the direct control for structural conditioning; a standard type-aware
Transformer controls for the ability to distinguish event categories implicitly.

Teacher-forcing future executions into a state head evaluated at the order index would
leak future information. Either forecast jointly and marginalize unavailable execution,
or explicitly define a later prediction time and update all comparators accordingly.
Architecture decisions are pending feasibility; no neural module is silently simulated.
