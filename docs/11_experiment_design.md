# Experiment design

Current status (2026-10-19): E003 is complete with its advancement gate held; A001 does
not support the proposed pairing contrast on the retained training artifact. Test
remains sealed. The earlier E001 steps below record the progression, not work to repeat. The
Mac implementation review is documented in docs/08 and does not change the clinical
decision, frozen model scales, thresholds or dataset splits.

## E000: implemented infrastructure smoke test

Dataset: generated fictional trajectories, seed 20261014, 300 patients, two orders
per patient. Train/validation/test: 70/15/15% by patient. Model: baseline A.
Endpoint: held-out observed-data competing-risk NLL in hours; report a patient-cluster
bootstrap interval. Purpose: verify the end-to-end executable path, not test novelty.
Each run has immutable output directory, configuration, revision and artifact hashes.

## E001: bounded feasibility attempted; server-led coherent access development

The first E001 code deliverable is now a generic bounded feasibility validator,
not a clinical cohort extractor. The approved server handoff reports direct linkage
is structurally feasible, repeated administrations are common, encounter equality
cannot be assumed, and independent lab availability is not yet reviewed.

On UCSF, use a reviewed local mapping to count linkage consistency, qualifying actions,
repeats, timing violations and first-event eligibility within explicit limits. Every
truncated scan is labeled `limited`; it cannot confirm absence of another dose or
right censoring. Inspect server-local counts before authorizing any cohort extraction.
The server has now performed two bounded runs, both limited. No clinical data were
accessed by the Mac agent. Independent source prefixes contained no matching links;
this is a sampling limitation, not a linkage-failure estimate. No clinical model
result or reliable cohort follows from those reports.

The server stopped the first configuration attempt before job submission because
time normalization, execution availability and a third observation source could not
be represented truthfully (docs/23_feasibility_contract_gaps.md). Version 2 implements
these concepts but does not establish their real source semantics. Review the common
clock, direct coverage join and retrospective endpoint ascertainment on UCSF. Execution
equality needs independent evidence and a mapped retrospective-exclusion rule; lack
of evidence remains a blocker, even though the software now supports the policy.

The first v2 server mapping passed review and planning, then exposed the independent-
prefix limitation (docs/24_bounded_run_findings.md). Server capability review found no
approved exact-key index preserving the required identities. A coherent-manifest
executor is now implemented and synthetically tested with separate scanned-row,
row-group-byte, retained-row and seed-key limits plus complete selected-key coverage
declarations. After separate user authorization, the server generated a restricted
private extract and manifest from a fixed-seed uniform row-position sample with full
three-source enumeration. The resulting coherent validation completed without
truncation. It found both first executions and right censoring while retaining rejection
diagnostics; this is feasibility evidence for the declared seed domain, not a population
estimate. Do not enlarge quotas or create further persistent artifacts implicitly.

Predefine acceptable linkage completeness,
ambiguity, event coverage and sample size after discussing the source definitions.
Do not invent numerical acceptance thresholds without measuring the setting.
No baseline clinical result exists until these conditions and a cohort are reviewed.

The bounded cohort now supports a separate fixed Baseline A validation operation. It
uses training rows only for estimation, evaluates validation rows only, does not emit
test metrics, and uses no predictors. Its purpose is to validate the clinical label,
censoring and likelihood path before feature development; it cannot establish individual
discrimination or a clinical-performance claim. All models, metrics and predictions stay
in UCSF private storage.

## E002: primary method comparison, pending feasibility

**Stopped on 2026-10-16 before execution.** The authorized storage contained no
authoritative documentation establishing point-in-time availability for a richer feature
source. The fixed age-only control is insufficient for the proposed primary comparison.
No test evaluation, neural model or GPU training was performed.

## E003: scoped dual-clock workflow continuation

E003 uses only the already reviewed order and qualifying-administration sources. For each
frozen index order, a complete full-source scan retains prior events in the 24-hour window
only when both occurrence and availability are no later than the prediction cutoff. The
first artifact contains no laboratory, diagnosis, physiology or outcome-derived feature.
After history coverage and CPU controls pass, compare leakage-safe single-clock and
dual-clock sequence models under prespecified documentation-delay shifts. Keep test sealed
until architecture, tuning budget, validation rule and reporting are frozen.

The first CPU comparison uses fixed eight-dimensional exponential-decay encoders and
matched convex piecewise proportional competing-risk heads. Its configuration freezes
the feature scales, ridge penalty, optimizer, four availability-delay conditions and a
paired patient-bootstrap advancement gate before the formal run. No hyperparameter search
is performed. Failure of the gate stops the experiment before test rather than permitting
post-validation threshold changes.

The formal matched CPU validation completed, and the frozen advancement gate held. The
minimum unshifted improvement and paired uncertainty requirements were not met, while the
delay-shift requirement passed. Accordingly E003 stops before test evaluation and before
any neural or GPU experiment. This controlled negative result does not establish absence
of dual-clock information in other representations, cohorts or tasks.

## Successor-design requirements (planned, not a new clinical experiment)

The current comparison is between two fixed summary encoders with different clock/scale
allocations. It does not isolate event-level documentation delay or order-conditioned
execution modeling. Generated positive controls show the current implementation can
learn an imposed occurrence-time signal; they do not establish clinical usefulness or
undo the failed E003 gate.

A successor first needs a precise estimand and a falsifiable mechanism using the already
reviewed sources. It must distinguish clock information from time-scale choice, preserve
or explicitly discard event pairing, define history truncation and perturbation refill
semantics, and include generated null and positive controls. Any new predictor content
needs its own authorized semantic review; it cannot be inferred from column names.

E003 validation has already been inspected. It cannot become a fresh confirmatory set
by renaming the experiment. A successor must state its development/tuning budget and
how it will obtain an independent evaluation or label reused validation exploratory.
Keep the current test set sealed; this local review neither opens it nor authorizes
neural/GPU training. No successor clinical run is implemented. The separate generated-only
representation diagnostic below is executable locally.

The frozen shift criterion is `NLL_dual(shift) - NLL_availability(shift) <= 0.005` at
each prespecified nonzero shift. Both models could worsen relative to zero shift while
satisfying this relative condition. Passing it does not establish absolute robustness.
The bootstrap resamples patients with all their orders and reports an order-weighted
mean loss; uncertainty is conditional on the fitted models, not a measure of variation
from retraining. Its gain margin has not been established as clinical utility.

## S001: generated clock-pairing mechanism diagnostic

Status: implemented, generated-only; separate from the ended clinical E003. Run with
`make pairing-demo` or `ies pairing-diagnostic --config configs/synthetic_pairing.yaml`.
The command generates all inputs internally and has no clinical input option.

Question: when histories have identical occurrence and availability marginals, can a
predictor preserving their within-event pairing recover a deliberately imposed signal
that marginal summaries cannot recover? This is a mechanism check, not a claim that the
signal exists in UCSF or that the representation is novel.

The initial configuration was chosen before its first full run: seeds 20261016–20261018,
800 training and 400 validation patients per seed, two index orders per patient, a 24-hour
horizon, and 200 paired patient-bootstrap replicates. Three encoders share 2/12-hour scales,
labels and the existing CPU hazard head: eight marginal features, sixteen marginal-plus-
independent-pair features, and sixteen marginal-plus-observed-pair features. Ridge is 1,
maximum iterations 100, tolerance 1e-8. There is no seed, scale or hyperparameter search.

Each index has two generated past events of the same type. Occurrence lags are 8 and 4
hours, availability lags 3 and 1 hours, with shared independent jitter of at most 0.25
hours. A patient-level latent bit swaps the pairing while preserving both marginal time
distributions and event counts. Both permutations obey occurrence before availability
before the cutoff. Event types alternate between a patient's two index orders. These
past events are not repeated outcomes of the index order; labels concern its first event.
No truncation or delay-shift experiment is included in S001.

| Scenario | Visible history | Outcome-generating rule |
| --- | --- | --- |
| pairing_signal | The latent bit controls paired timestamps | Execution rate `0.08 * exp(+/-1.2)` follows that bit |
| null | Identical histories to pairing_signal | Execution rate is 0.08, independent of the bit |
| scrambled_pairing | An independent random bit controls pairing per index | Exact same labels as pairing_signal |

Other competing-event rates are 0.04 and 0.02 per hour. The first generated competing
event supplies the label; absence before 24 hours is right censoring. Separate RNG streams
control histories, labels and scrambling. Patients never cross train/validation. These
are arbitrary simulation parameters, not estimates of clinical rates or associations.

The primary diagnostic contrast is validation NLL of paired minus unpaired (negative
favors paired). All nine seed/scenario results, all model losses, and paired patient-
bootstrap intervals are saved. Seed means are descriptive; intervals condition on each
trained model and are not pooled across seeds. The fixed-seed regression tests require
a gain exceeding 0.05 in the deliberately strong signal case and absolute differences
below 0.05 in null/scrambled cases. These broad engineering tolerances were set before
the first full run, are not a clinical gate, and do not establish equivalence.

Interpretation boundaries: this generator deliberately makes the signal observable only
through pairing. A successful positive control demonstrates capacity to learn that
constructed mechanism. A small null difference is a check against an automatic advantage,
not proof of absence of all overfitting. No real discrimination, calibration, utility,
causal effect, population coverage or novelty is established.

Before a new real study, server-local training-history evidence would need to establish
nondegenerate and sufficiently supported reviewed time pairs by event type, including
the effect of occurrence-equals-availability policies. Equal clocks turn joint decays
into extra recency scales; that requires a corresponding single-clock basis control.
Coverage, cap selection and any perturbation/refill definition must be explicit. Existing
E003 validation is already observed, so new use would be exploratory unless an independent
evaluation design is established. The separate label-free `clock-audit` prerequisite
is now implemented and tested with generated fixtures. The user reported UCSF job 39325
complete at `14b8d69`, including artifact verification. Subsequent qualitative feedback
does not support this pairing contrast on the retained histories. It does not schedule
a model comparison, and the clinical test set remains sealed.

## S002: harmonic-basis control and fixed-model delay stress

Implemented through `make pairing-stress`, separately from S001 and E003. S001's config,
seeds and three original scenarios remain unchanged. S002 adds a fourth encoder and an
equal-clock scenario. All twelve seed/scenario combinations are reported.

The new 16-dimensional control shares the occurrence/availability marginal features
with the paired model and replaces its joint terms with availability-only harmonic
decays: `sum_i A_i(s) A_i(t)`. These extra terms equal single-clock scales with rates
`1/s + 1/t`. At equal clocks the entire control and paired feature vectors coincide;
the fitted unshifted predictions must match. This is checked analytically and in tests.
The control's common marginal block still contains both clocks; only its added basis
uses availability alone.

In the equal-clock generator, both timestamps use the same occurrence lags and shared
jitter. Execution log-rate varies with `1.2 * jitter / 0.25`; it does not depend on a
latent pairing bit. Other rates, censoring and patient splits are unchanged. This
deliberately narrow recency-signal example tests both equal-clock equivalence and
extrapolation; its rate/jitter choices are not estimated from clinical data.

Each encoder is fitted once on unshifted training data. Validation availability lags
are then reduced by 1, 4 or 8 hours; newly unavailable events are excluded, with no
refit or refill. Report both paired-minus-control NLL and each model's loss change from
its own zero-shift result. A relative win cannot conceal absolute degradation. These
are stress diagnostics, not a new advancement gate or evidence of a realistic workflow
shift distribution. Results, including adverse findings, are retained in docs/20.

## Prerequisite A001: private training-clock support audit

Implemented and generated-test verified. The user returned a completed UCSF execution
and successful monitor verification for job 39325 at `14b8d69`. Subsequent user feedback
does not support the proposed pairing contrast on this retained training artifact.
No report payload, private counts or source mapping is stored in the repository.
The Mac did not independently access UCSF artifacts. The audit reads only already-created cohort/history
artifacts, verifies their digest and QC
bindings, projects patient/order identities and split metadata across the cohort, and
materializes timestamp features only for training orders. Outcome columns are never
projected; file hashing and shared Parquet pages can touch bytes from other splits,
which does not constitute evaluation of their outcomes or feature distributions.

The private report contains per-type equal/positive-delay counts and orders with two
distinct timestamp pairs admitting a valid marginal-preserving swap. It records absent
retained histories and orders at the cap. Counts remain UCSF-only. There is no fitted
model, feature-row persistence, minimum-sample gate, power calculation or automatic
research decision. A zero swap count concerns only this specific contrast in retained
training histories; it does not prove all dual-clock information is absent. A positive
count does not establish clinical usefulness or validate a new availability assumption.

The reviewed retrospective-exclusion/equality semantics still require local interpretation.
The cohort remains bounded, and the retained-event cap limits what these diagnostics
can say about the full history. Do not recreate extracts, expand budgets or inspect
validation/test labels to resolve an unfavorable audit. Operational commands and resource
bounds are in docs/16.

### A001 disposition and boundaries of subsequent work

The current pairing successor is not scheduled: both event types' retained clocks
coincide at the audit resolution and the proposed distinct-pair exchange has no
observed support. History truncation and absent histories also constrain the artifact.
These are qualitative operator-provided findings, not population estimates, a new
clinical performance evaluation or a statement about uninspected validation/test data.

Keep the E003 decision, audit implementation and recorded S001/S002 results unchanged.
Do not add artificial delays to clinical histories, change mapped timing semantics,
relax retrospective exclusions, enlarge caps, rerun the same audit or fit a paired
clinical model in response to this finding. The equal-clock representation and ridge
implications can be checked locally with generated inputs; see docs/08.

Further clinical model work requires a distinct, falsifiable question. The subsequently
authorized W001 single-clock design below supplies that separate development protocol;
it is not an established methodological contribution. Its target, information set,
controls and handling of already-inspected E003 validation are specified before real
evaluation. Separately typed historical order/administration events must not be called
pending-order states without reviewed order-to-execution linkage. Recovering a genuine
dual-clock question instead requires independent reviewed availability evidence and
an explicit account of how that evidence would support different retained inputs.
Neither direction is automatically authorized to add source roles, scan more data,
open the sealed test set or start GPU work.

## W001: fixed-data single-clock workflow prediction (authorized 2026-10-19)

The user explicitly authorized changing direction, with no additional or modified
source data and no dependency on further semantic explanation. W001 uses only the
already reviewed bounded cohort and retained order/administration histories. It does
not restore dual clocks, physiology, medications-as-categories, inferred pending-order
states or an order-to-administration history linkage that these artifacts do not carry.

Question: at the existing order index, does the timing of retained prior events, and
then its association with event type, improve prediction of first execution in the
presence of the existing terminal competing events and right censoring? This is
workflow prediction under the existing cohort contract, not treatment-effect estimation.
No new time interpretations, full-source scans, extracts or changes to the history cap
are needed. All original data artifacts and split assignments remain unchanged.

The fixed design is `configs/workflow_cv.yaml`. Four CPU models use the same piecewise
competing-risk head, bin edges, optimizer and ridge. Features use availability lags with
the existing occurrence/availability eligibility constraints. Per retained event type:

| Model | Features beyond the shared time-bin intercepts | Dimensions |
| --- | --- | ---: |
| intercept | None | 0 |
| counts | Retained counts of orders and administrations | 2 |
| pooled_timing | Both counts plus four decay sums pooled across event types | 6 |
| typed_timing | Both counts plus four decay sums separately for each event type | 10 |

The decay scales are 1, 4, 12 and 24 hours throughout. Counts describe the capped
artifact, not total workload, unexecuted orders or the complete clinical history.
The information sets are nested but nominal/effective capacities differ; this is an
incremental predictive-value comparison, not a capacity-matched architectural experiment.
Same nominal ridge does not guarantee invariant regularization under reparameterization.

Evaluation is restricted to five deterministic patient folds **within the original
training partition**. Each fold's normalization and fitted model use only other folds.
All orders for one patient remain together. Original validation/test labels and histories
are not projected for analysis, and no global calendar split is inferred. Identity/split
metadata across the cohort verifies patient separation. File hashes/shared Parquet pages
may touch other-partition bytes; this is not a claim of physical byte isolation.

All four models and all folds are reported. No hyperparameter grid, fold selection or
automatic retry is performed. Each training fold must contain execution events; absent
other terminal causes are reported and retain the existing head's near-zero-hazard
behavior rather than requiring new labels or rejecting a valid cohort. The primary
contrast is typed_timing minus pooled_timing
in observed-data NLL per order; negative is better. Secondary contrasts decompose counts
versus intercept and pooled timing versus counts, plus typed versus intercept. Original
clinical validation is already used by E003, and this pivot was informed by that work and
the training audit. These results are explicitly exploratory development CV, not a fresh
confirmatory experiment. A paired patient bootstrap retains all orders within a sampled
patient and conditions on the fitted folds. Its intervals omit refitting, fold-training
dependence and design-selection uncertainty; they are not definitive population CIs.
The joint likelihood includes all existing causes; an improvement may arise from
competing-event prediction and alone does not establish better execution-probability
calibration. Cause-specific probability calibration is not implemented in this screen
and is required before any future execution-risk or operational-use claim.

Before any W001 clinical run, the fixed descriptive support rule requires the primary
mean improvement to reach 0.005 NLL per order, its conditional interval upper bound below
zero, improvement in at least four of five folds, and a lower mean NLL than the intercept
control. This is an engineering development screen, not a clinically justified minimum
benefit. Passing only permits consideration of a separately frozen validation design;
it never opens test, starts GPU work or declares clinical advancement. Failure is retained
without changing scales/thresholds to pass. Secondary results can reveal usefulness of
simpler history summaries without supporting the event-type-specific timing hypothesis.

The generated diagnostic `make workflow-demo` uses three prespecified seeds and four
mechanisms: volume signal, pooled timing signal, type-specific timing signal and a null.
All synthetic clocks coincide, and competing events/right censoring are generated. It
checks learnability of the proposed information contrasts, not clinical performance.
The immutable manifest records configuration, source hashes, dependencies and all cases.

The private entry point is `workflow-cv`, using existing compatible cohort/history
manifests, the same input bounds as A001, and the already established model-job budget
of 2 CPU, 4,096 MiB and a 1,200-second worker (Slurm 20 minutes 30 seconds). It writes
private fold models and aggregate metrics without prediction rows; no terminal metrics,
counts or identifiers are exported. The user reported UCSF job 39332 complete at
`9fcdc32`, including monitor artifact verification. Subsequent qualitative feedback
reports that the fixed primary support rule failed, with typed timing having higher
mean loss than pooled timing. Counts versus intercept, pooled timing versus counts and
typed timing versus intercept have lower mean loss. No numerical effect size, conditional
interval or fold pattern has been supplied. Preserve this negative primary result;
the remaining review concerns already-defined secondary descriptions, not a replacement
primary endpoint or a new advancement rule. Local checks, operational evidence and
research conclusions are recorded separately in docs/20.

`scripts/server.py review workflow-cv` reads the existing report by exact job ID and
original source commit. It checks artifact hashes and consistency of the original support
flag, then reports all four predefined contrasts with qualitative mean direction,
conditional interval position relative to zero, and whether fold directions agree.
An endpoint exactly zero is classified as including zero. No fit, bootstrap, new feature,
row access or secondary pass rule is added. These conditional intervals retain all the
limitations above. Qualitative summaries cannot establish effect magnitude or clinical
utility, and favorable secondary findings do not overturn W001's primary failure.

Methodological context: [Cawley and Talbot, JMLR 2010](https://www.jmlr.org/papers/v11/cawley10a.html)
show why repeated model selection can bias performance estimates; this motivates the
fixed exploratory comparison and explicit validation-reuse limitation here.
[Agniel et al., BMJ 2018](https://www.bmj.com/content/361/bmj.k1479) demonstrate that EHR
healthcare-process variables can carry predictive information and introduce biases.
That study does not establish a medication-execution effect, transportability or novelty
for W001. The protocol above is our scoped design choice, not a claim that those papers
validate this particular predictor or these cohort semantics.

## Archived broader proposal (inactive)

Proposed primary comparison: structured model P versus type-aware model C with matched inputs,
capacity and labels. Primary endpoint: test competing-risk NLL; key secondary outcomes
are calibration and relevant state/transfer performance. Freeze the meaningful effect
threshold, seeds, splits and tuning budget before test evaluation. Use validation
for model selection, and preserve the test set for the final comparison.

Secondary experiments: training fractions 1/5/10/25/100% sampled by patient, medication
and department subgroups, synthetic delay shifts, representation transfer, and
independent-head ablations. A shift experiment uses training-fitted parameters unchanged
on a separately generated shifted test set; rerunning the full pipeline at another
delay scale alone is not a robustness test. Multi-model/shift runners remain planned.
