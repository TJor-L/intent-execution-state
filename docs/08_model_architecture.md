# Model architecture and implementation boundary

Current executable history comparison: matched eight-dimensional fixed history encoders
with convex piecewise proportional competing-risk heads. The availability-only control
uses four decay scales per event type. The dual-clock encoder uses two occurrence and two
availability scales per event type. Both use the same labels, parameter count, training
patients, ridge penalty and optimization budget. This is a small CPU workflow baseline,
not the planned Transformer or order-conditioned architecture.

Documentation-delay interventions shift availability later at validation time, remove
events no longer available at the cutoff and reuse the training-fitted parameters. They
do not refit on perturbed data. The frozen gate requires a minimum unshifted likelihood
gain, a paired patient-bootstrap interval below zero, and a bounded dual-minus-availability
loss difference at each shift. The shift condition is relative to the other model at the
same shift, not relative to the dual-clock model's own unshifted loss. E003 did not pass
the first two conditions; its test partition remains sealed.

## Local implementation and representation review (2026-10-16)

This review uses source code and generated fixtures only. The clinical conclusion is
the server-approved operational finding in docs/20; no clinical artifacts were inspected
on the Mac. The frozen E003 config, clinical result and advancement thresholds are unchanged.

For each event type, the encoder sums `exp(-lag / scale)` separately for each clock.
The availability control uses scales 1, 4, 12, 24 hours; the dual-clock model uses 2 and
12 hours for each clock. Consequences of the implemented representation:

- Equal feature/parameter counts do not make this a nested clock ablation. Changing
  clocks also changes the time scales. If clocks are equal, the two pairs of dual-clock
  features duplicate each other; equal nominal dimensions need not mean equal effective
  capacity or the same effect of ridge regularization.
- The feature sums discard event pairing. Two same-type events with occurrence lags
  8 and 4 hours and availability lags 3 and 1 hours encode identically after swapping
  the availability lags, although the paired delays change from (5, 3) to (7, 1).
  The stored `documentation_delay_hours` field is not used by the model.
- The predictor sees event type and lags, without index-order attributes, medication
  content, historical order-to-administration links or physiology. The extractor's
  patient alignment and outcome linkage do not supply those features to the head.
  This cannot test the proposed order-conditioned intent/execution architecture.
- Both models share a history selected using occurrence time: the preceding 24 hours,
  strictly before the index, with availability at or before the cutoff. After a complete
  source scan, the cap retains the 24 most recent occurrences, breaking ties by
  availability, kind and ID. The name "availability-only" describes the encoder,
  not a history selection process independent of occurrence time.
- Delay perturbations mask events in that already capped artifact. They do not refill
  from older qualifying events discarded by the original cap. These runs test sensitivity
  of a fixed retained history, not full reconstruction of histories under a workflow shift.

Generated checks in `tests/test_history_piecewise.py` establish an analytical likelihood
oracle including censoring and right-closed bin edges, recovery of constant-feature
maximum-likelihood rates, train-only normalization/fitting, loss of pairing information,
equal-clock feature duplication, and a fixed-seed positive control with an occurrence-only
signal. The positive control verifies that the implementation can learn that deliberately
generated signal; it says nothing about signal strength in UCSF data.

`tests/test_clinical_history_models.py` checks paired patient resampling with unequal
orders per patient, all three frozen gate boundaries, and unchanged fitted models and
validation outputs after replacing only generated test-partition labels and histories.
Finite scale/shift validation now rejects NaN/infinity even for empty histories. The path
fix shares one resolved server boundary across cohort, age and history artifacts; tests
replace it only in-process. CLI server context, Slurm checks and production storage
restrictions are not relaxed.

The head uses clipped log rates and objective-change convergence. The analytical and
generated controls are not a numerical audit of every saturation or sparse-event case,
and this review does not establish optimality of the private clinical fits. Additional
diagnostics, if needed, must remain distinct from performance-driven retuning of E003.

## A001 interpretation and equal-clock algebra (2026-10-19)

User feedback from the completed training-history audit does not support a distinct
clock-pairing contrast on the retained artifact. Only the qualitative conclusion is
recorded here; restricted counts, reports and mapping evidence remain outside Git.
Coincidence at the audit tolerance is not a claim of bitwise-identical source times,
nor does a training-only audit establish the same finding in other data partitions.

For exactly equal clocks, the unshifted E003 dual representation for each event type is
`[f_2, f_12, f_2, f_12]`. It has only two distinct basis functions per type, while the
availability control uses the different scales `[1, 4, 12, 24]`. This cannot isolate
the contribution of an independent occurrence clock. The time mask and retained-history
selection are also shared. E003's frozen negative decision remains valid as the result
of its implemented comparison; it is not a clean general test of two-clock information.

Duplicated columns also change the effective regularization. If two standardized
columns coincide and their coefficients sum to `b`, minimizing the ridge cost gives
`beta_1 = beta_2 = b/2`. With the code's penalty `lambda/2 * ||beta||^2`, their joint
cost is `lambda*b^2/4`: the unique-column model has equivalent ridge `lambda/2`.
This is an algebraic diagnosis, not a prescription to refit or retune E003. A generated
regression test verifies the coefficient and hazard equivalence using the existing
optimizer; no clinical rows, rates, model weights or fits are used.

When the occurrence and availability multisets coincide exactly, any permutation that
keeps every availability lag no larger than its paired occurrence lag must preserve
equality: the nonnegative differences sum to zero. Swapping distinct times would violate
a time constraint. The arithmetic unpaired expectation therefore cannot be treated as
a valid randomized timestamp reassignment in this case. Joint equal-clock features
instead reduce to extra single-clock decay scales, as checked by S002's basis control.

The extractor keeps mapped order times separate in code. For administration history,
an explicitly reviewed occurrence-equality policy, when active, uses occurrence as
availability after the required documentation-status exclusions. Audit output alone
does not identify which mapping or policy caused the observed coincidence, nor prove
that real-world documentation never arrives late. The reviewed mapping is not changed.
Windowing, filtering and the retained-event cap bound the audit's interpretation.

## Generated clock-pair mechanism diagnostic

`src/ies/models/paired_history.py` implements three experimental encoders for the local
synthetic diagnostic only. All share scales 2 and 12 hours for both clocks and the same
event mask. Within each event type, let `O_i(s) = exp(-occurrence_lag_i / s)` and
`A_i(t) = exp(-availability_lag_i / t)` for the retained `n` events.

| Encoder | Per-type features | Total dimensions |
| --- | --- | --- |
| marginal | Two occurrence sums and two availability sums | 8 |
| unpaired | Marginals plus `sum(O(s)) * sum(A(t)) / n` for each scale pair | 16 |
| paired | Marginals plus `sum_i O_i(s) * A_i(t)` for each scale pair | 16 |

Empty histories produce zeros. The unpaired features equal the expected joint features
under uniform within-type reassignment of availability to occurrence. The generated
histories ensure every such reassignment is temporally valid. Their equality is tested
by enumerating permutations; arbitrary real histories need not permit all permutations.
This is pairing of the two timestamps on the same event, not order-to-administration
linkage or treatment-effect modeling.

All heads reuse the same CPU competing-risk optimizer, training-only standardization,
ridge and budget. Equal nominal dimensions of the paired/unpaired comparison do not
guarantee equal rank or effective capacity. The deliberately equal-marginal generator
and null/scrambling controls establish the narrow information mechanism; they do not
establish a fair universal clinical comparison.

At equal clocks the joint term is a single-clock decay with rate `1/s + 1/t`. Thus joint
features can also expand the effective recency basis without adding clock-pair information.
A future real study must distinguish that possibility from useful nonzero documentation
delays. The current generated positive control deliberately holds both marginals fixed
when pairing changes, so its signal cannot be recovered by any marginal-only basis.

The diagnostic accepts no external history or cohort, writes explicitly synthetic
artifacts, reports all fixed seeds and includes source hashes for the dirty working tree.
It adds no mode to `clinical-history-models`, changes no frozen E003 configuration and
does not inspect clinical validation/test data. Detailed scenarios and limitations are
in docs/11; completed runs are in docs/20.

## Active W001 single-clock workflow controls

W001 reuses the existing head and availability-valid retained histories, with counts
and common recency scales 1/4/12/24 hours. The four information sets have 0/2/6/10
features: no history, two event-type counts, those counts plus pooled decays, and counts
plus type-specific decays. It introduces no new source fields, index-order attributes,
pending-order state, patient physiology, delayed-clock perturbation or linkage claim.
Parameter counts differ; improvement cannot be described as a capacity-matched effect.

Normalization and fitting happen separately within each training-patient CV fold.
The patient-level fold assignment is deterministic and independent of outcomes. Models
never consume original validation/test labels or features. Aggregate fold and overall
observed-data losses, paired conditional uncertainty and all fixed comparisons are
reported. The exact protocol, support screen and limits of post-pivot development CV
are in docs/11. No real W001 result is available at implementation time.

## Unimplemented original architecture

Original proposed encoder: a single time-aware sequence encoder with event type/code, measurement
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
This broader design is inactive after the source-semantics stop and E003's failed gate.
No neural module is silently simulated or scheduled.
