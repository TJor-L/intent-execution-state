# Model architecture and implementation boundary

Current executable history comparison: matched eight-dimensional fixed history encoders
with convex piecewise proportional competing-risk heads. The availability-only control
uses four decay scales per event type. The dual-clock encoder uses two occurrence and two
availability scales per event type. Both use the same labels, parameter count, training
patients, ridge penalty and optimization budget. This is a small CPU workflow baseline,
not the planned Transformer or order-conditioned architecture.

Documentation-delay interventions shift availability later at validation time, remove
events no longer available at the cutoff and reuse the training-fitted parameters. They
do not refit on perturbed data. A frozen gate requires a minimum paired likelihood gain,
a paired patient-bootstrap interval below zero and no material degradation across the
prespecified shifts before test may be opened.

Future encoder: a single time-aware sequence encoder with event type/code, measurement
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
