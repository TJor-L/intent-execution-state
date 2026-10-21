# Experiment design

Current status (2026-10-19): R001 job 39335 completed at `2176207`; its fixed
selection-policy comparison is closed with unresolved/adverse/identical-policy findings
across seeds. No further server experiment is scheduled. W001/W002 retain their negative/mixed
findings. E003 is complete with its advancement gate held; A001 does
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
typed timing versus intercept have lower mean loss. The subsequent read-only review at
`5836dbc` verified that pooled timing versus counts and typed timing versus intercept
each have a conditional interval below zero and all five fold losses lower. Counts
versus intercept and typed versus pooled each have an interval including zero and mixed
fold directions. No numerical effect size has been supplied. Preserve this negative
primary result: descriptive secondary evidence is not a replacement primary endpoint
or a new advancement rule. Local checks, operational evidence and research conclusions
are recorded separately in docs/20.

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

## W002: frozen W001 probability diagnostics (post-selection, no refit)

This diagnostic was designed after inspecting W001's qualitative secondary results.
It is explicitly exploratory and cannot provide independent confirmation, a replacement
primary endpoint or a new advancement decision. E003 and W001 remain negative under
their original rules. The operator reported W002 job `39333` complete at `1df3274`,
including verified frozen replay and qualitative diagnostics. Findings and disposition
are recorded below and in docs/20. Generated verification remains separate from this
operator-reported clinical evidence.

Inputs are exactly the existing W001 cohort/history artifacts, original configuration,
fold models and report, bound by the original job receipt, source SHA and artifact
digests. Only original training outcomes/history enter prediction. The existing bounded
reader inspects identities/split membership across partitions to reject patient overlap;
it does not evaluate held-out outcomes or features. Mapping, source roles, cohort,
lookback, retained-history cap, censoring labels and fold assignment do not change.

For all four models, reproduce original patient folds, verify training-assignment
hashes and training-only feature normalization, then use saved coefficients without
fitting. Require each fold's and each model's overall likelihood loss to reproduce
the original report (relative tolerance 1e-9, absolute tolerance 1e-10). A mismatch is
an explicit failure, not a reason to refit. Original models and artifacts are read-only.

Report the four original NLL contrasts plus **pooled timing minus intercept**, directly
computed from paired out-of-fold losses. The new contrast is post hoc, not a frozen
W001 primary. Use the same 1,000 patient-cluster bootstrap draws and seed as W001;
intervals are conditional on the original fitted models, omit fitting/selection
uncertainty and do not correct for inspecting several comparisons. Lower loss alone
does not establish a useful magnitude or clinical benefit.

Compute first-execution cumulative incidence at **1, 4, 12 and 24 hours** from the
saved piecewise cause-specific hazards. In each interval of width d, with total hazard
L, surviving probability S contributes `S * (1 - exp(-L*d)) * lambda_execution/L`;
zero L contributes zero. All three competing hazards reduce survival. This is not
the survival complement obtained by ignoring competing terminal events.

At horizon h, execution by h is one; a competing terminal event by h or observation
through h without execution is zero. Right censoring strictly before h is unknown.
The existing inclusive boundary convention counts an event exactly at h; censoring
at h supplies observation through h. No new assumption about independent censoring
or known potential administrative censoring time is introduced by this diagnostic.
This does not remove assumptions from the original fitted likelihood model.

For each unknown binary outcome, evaluate both zero and one and aggregate lower/upper
squared-error bounds. For model differences, evaluate both models at the **same**
unknown label before taking bounds. Separately bounded scores must not be subtracted.
These finite-sample, order-weighted Brier completion bounds are not confidence intervals,
population risk estimates or a significance test. They may be wide. Bounds are marginal
for each horizon, not a joint trajectory band; within-patient statistical dependence
is not modeled by these descriptive ranges.

Privately report mean predicted execution probability and event-fraction completion
bounds overall and in ten fixed probability bins with edges 0, 0.1, ..., 1. Empty bins
are explicit. These are descriptive calibration checks without sampling intervals.
Being inside the outcome range does not establish calibration; being outside it does
not alone establish population miscalibration. Do not select bins, thresholds or a new
model based on these results. All four models and all five contrasts remain visible.

The bounded `workflow-diagnostics` Slurm job uses 2 CPU, 4,096 MiB, a 300-second worker
and 5 minutes 30 seconds of Slurm time. Unchanged limits: 20,000 cohort rows, 500,000
retained history rows, 256 MiB per Parquet file, 512 MiB declared decoded size per file.
No raw-source scan, prediction-row persistence, new model weights or GPU use occurs.
Only a private aggregate report and manifest are written. The monitor verifies the
report and prints allowlisted qualitative directions/range positions automatically;
numeric metrics, counts, calibration bins and models stay on UCSF. No automatic retry.

`make workflow-demo` constructs the same 12 generated W001 cases, fits those generated
fixtures, then runs W002 replay without further fitting. It now also saves
`diagnostics.json` with artifact hashes. Tests separately exercise early censoring,
analytic competing-risk probabilities and exhaustive binary completions. Generated
fixture fitting is separate from the no-refit clinical diagnostic.

Method context: [Kvamme and Borgan, JMLR 2023](https://www.jmlr.org/papers/v24/19-1030.html)
explain problems with censoring weights when censoring depends on predictors and study
an administrative-censoring alternative. We neither assume that setting here nor use
their estimator. [Gerds, Andersen and Kattan, Statistics in Medicine 2014](https://onlinelibrary.wiley.com/doi/abs/10.1002/sim.6152)
address calibration for competing-risk predictions with censored observations. W002's
elementary finite binary-completion ranges are not their calibration estimator, a
validated clinical evaluation method or a claim of methodological novelty.

### Completed W002 findings and disposition

The direct pooled-versus-intercept NLL contrast is lower in all five folds with its
conditional interval below zero. Original NLL contrasts retain the W001 directions.
The execution-probability diagnostics show the following paired Brier completion-bound
positions (lower squared error is preferable):

| Contrast | 1 hour | 4 hours | 12 hours | 24 hours |
| --- | --- | --- | --- | --- |
| Counts minus intercept | Above zero | Below zero | Below zero | Below zero |
| Pooled minus counts | Below zero | Above zero | Above zero | Above zero |
| Pooled minus intercept | Below zero | Below zero | Below zero | Includes zero |
| Typed minus pooled | Above zero | Above zero | Above zero | Above zero |
| Typed minus intercept | Below zero | Below zero | Includes zero | Includes zero |

All four models' empirical mean predictions are below the event-fraction completion
range at 1 hour, above at 4 hours and inside at 12/24 hours. These are overall sample
descriptions, not calibrated-bin validation, population tests or proof that either
later horizon is calibrated. Completion-bound directions omit sampling uncertainty;
no numerical effect magnitude has been shared. In particular, typed versus pooled
being above zero at all four horizons is not a claim of statistical significance.

The observed likelihood and horizon rankings need not agree: the implemented NLL
scores the event time and terminal cause (or censoring contribution), whereas this
Brier diagnostic scores execution by one fixed horizon. Code review and a separate
closed-form generated counterexample verified that opposite rankings are possible
without a computational defect. This does not identify the cause of the actual UCSF
differences or prove model misspecification, censoring bias or a data error.

The specified W001/W002 development analysis is complete. Retain the limited temporal
information finding and the adverse horizon-specific results together; do not claim
uniform improvement, clinical utility, a novel architecture or a positive primary.
No additional job, recalibration, tuning, GPU run or original held-out evaluation is
scheduled. Do not select 1 hour as a new confirmatory target after seeing these results.
A future study would need its own distinct question and fixed evaluation design;
this record does not define or implement that study. Current data cannot establish
the original intent/execution/state or clock-pairing claims, and the present model
comparisons do not supply evidence sufficient to advance those claims.

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

## R001: nested model-selection objective benchmark (new fixed-data question)

Authorized by the user's request to autonomously choose direction, implement, and prepare
experiments while the user operates UCSF. This protocol is fixed before R001 clinical
execution, after seeing W001/W002 qualitative results. It is **data-informed exploratory
development**, not independent confirmation or a rescue of E003/W001. See docs/02 for
close existing work; no new architecture, score, identification theorem or causal claim.
Clinical run state: operator-reported job 39335 complete at
`21762073fe9aff38dfb37d9feddc54e9205fe1fa`, with automated artifact verification.
The executable configuration is `configs/workflow_selection.yaml`; the protocol below
is unchanged. Completed findings and disposition follow the original stopping rules.

### Question and scope

On the identical fixed candidate bank, how does choosing by joint observed-data NLL
compare with choosing by a conservative upper bound on first-execution probability
error? The target is a comparison of selection policies, not whether typed timing wins.

Use exactly the existing reviewed cohort/history manifests bound to W001 job 39332,
source `9fcdc32f3200931c780e0931130a3a07fc20ddaa`. Reuse only original training patients,
existing three terminal causes/right censoring, source roles, exclusions, patient splits,
24-hour lookback and 24-event cap. Do not scan raw sources, change dates/semantics, add
patients, enlarge history, impute clinical delays or request new source explanations.
Original validation was previously used by E003 and is not fresh evidence. Original
validation/test outcomes and history features are not read by R001; test stays sealed.
Patient/split identities are inspected solely to reject overlapping original partitions.
Coverage remains the selected bounded cohort and retained histories, not all UCSF orders.

### Candidate bank and fitting

Eight candidates, in this deterministic tie order: `ph_intercept`, `tree_intercept`,
`ph_counts`, `tree_counts`, `ph_pooled_timing`, `tree_pooled_timing`, `ph_typed_timing`,
`tree_typed_timing`. Representations have 0/2/6/10 dimensions, preserving W001's count
and exponential recency encoding at scales 1/4/12/24 hours. Event occurrence and availability
are both respected; observed coincident clocks are not made artificially distinct.
All models use bins 0/1/2/4/8/12/24 hours and all three terminal causes.

PH: existing standardized log-linear piecewise exponential head; bin intercepts and
cause-specific shared-over-time feature coefficients, ridge 1, maximum 100 Newton steps,
relative objective tolerance 1e-8. Training means/scales use training rows only. Any
nonconvergence fails the run; no silent model substitution.

Tree: independent axis-aligned likelihood partition, depth at most 2, minimum 25 unique
training patients per child, candidate cuts at training feature quantiles .25/.5/.75.
Each leaf has separate cause/bin rates `(events + .5)/(exposure hours + 1)`; choose the
split improving observed smoothed-leaf likelihood most, with fixed feature/cut tie order.
This is a small nonlinear/non-PH reference, not a best-in-class survival forest. No tuning
of depth, cuts, smoothing or ridge. Both families fit order-weighted likelihood; selection
and primary evaluation are patient-weighted. The families/representations are not capacity
matched, so their differences cannot isolate a type-specific architectural contribution.

### Nesting and selection

Three fixed fold seeds: 20261020, 20261021, 20261022. Patient assignments use an independent
`R001:` hash namespace and balanced ranks. For each seed, five outer folds; each outer
training subset has three inner patient folds. Each patient's orders remain together.
The outer fold's outcomes/features never enter inner fitting, scaling, cut selection
or model selection. Feature encoding itself uses only fixed transforms of each order's
pre-cutoff history. Require at least 30 original training patients; this is a computational
minimum, not a statistical power or sufficiency claim.

Fit all eight candidates per inner fold. Assemble inner out-of-fold predictions and select:

- `joint_nll`: smallest equal-patient average observed joint cause/time NLL.
- `upper_brier`: smallest equal-patient average upper completion bound on squared
  first-execution probability errors, equally weighted over 1/4/12/24 hours.

Equal patient weight means average orders within each patient, then average patients.
Ties within 1e-12 choose the first candidate in the fixed order. Refit all eight candidates
on the whole outer training subset; each policy uses its selected candidate's outer
predictions. This yields 480 fits total, including independent outer candidate reporting.
Every seed, outer fold choice, candidate and horizon is retained; no best seed is selected.
Repeated seeds overlap in patients and are not independent replications or a larger sample.

### Coherent completion scoring and uncertainty

Let `Y(h)` be first execution by horizon h. Observed first execution supplies a monotone
zero-to-one trajectory; a competing first terminal cause supplies zeros at all horizons.
Censoring supplies known zeros through its time and unknown values afterward. Enumerate
only monotone binary trajectories matching these facts: H+1 patterns for H horizons,
including all zeros. Use the **same** completion for both compared models. For each order,
minimize/maximize the equal-horizon squared-error difference over admissible trajectories,
then average with patient weights. With no cross-order restrictions, this is the exact
finite-sample range for the recorded observations and frozen predictions. Exhaustive
small examples and generated latent outcomes verify it. It is an elementary completion
calculation, not a novel partial-identification method.

Primary contrast: `upper_brier` minus `joint_nll`, equal patients and horizons. Negative
favors `upper_brier`. Report both endpoints, even when they straddle zero. Also report
order-weighted sensitivity, each horizon, each outer fold, joint NLL and its three
cause-specific components. All eight standalone candidates receive the same descriptive
metrics. Calibration bins remain order-weighted descriptions, not proof of calibration.

Patient-bootstrap endpoint percentiles use 1,000 draws per seed, **conditional on the
fitted, overlapping out-of-fold models**. They omit refitting, selection and the adaptive
research-direction uncertainty. Do not call them full-pipeline population confidence
intervals or infer statistical significance from completion bounds. Bounds themselves
need no censoring-independence assumption; fitted likelihood models still retain their
model and censoring assumptions. This does not solve identification of population risks
under arbitrary dependent censoring or establish transportability/clinical usefulness.
The worst-completion objective is not a proper probability score: if all labels are
unknown, its squared-error optimum is .5 regardless of the latent event probability.
It is a deliberately conservative selection policy under evaluation, not an endorsed
probability-learning rule. Generated adverse examples must remain in the report.

### Generated verification, resource budget and outputs

`make selection-demo`: five fixed mechanisms (execution-only, competing-only, nonlinear
execution, time-varying execution effects, null), three data seeds 20261023/24/25, two
censoring regimes (administrative-only, feature-dependent), 240 generated patients per
case, 1–3 orders each. All 30 cases use all three CV seeds. Complete latent outcomes are
available only in this generator; replay verifies their errors are inside completion
bounds. Compare both favorable and adverse oracle directions; do not choose a successful
scenario after seeing results. `scripts/profile_selection.py` measures the default 480-fit
pipeline near the row/history caps, using only generated inputs. Neither establishes
clinical performance or verifies Linux resource enforcement on a Mac.

Server entry: `workflow-selection`, `scripts/run_selection.sh`. Two CPU, 4 GiB, worker
wall/CPU cap 1,200 seconds, Slurm 20:30; at most 20,000 cohort rows and 500,000 history rows,
existing 256 MiB file and 512 MiB declared Parquet decode limits. Reuse the environment;
no GPU, new dependency, new persistent source extract or automatic retry/resource increase.

Private outputs: manifest, exact config, numerical `selection_report.json`, outer fold
`models.json`, and `paper_tables.md` containing every candidate/policy/seed/horizon and
paired primary results. No per-order prediction rows or patient IDs are persisted.
Patient-set hashes remain private audit material. Original W001 models/metrics are not
selection inputs; its manifest fixes population provenance. Terminal feedback is an
allowlisted qualitative selection/direction summary, never metric magnitudes or counts.

### Decision and stopping rules

The run has no clinical advancement or paper-acceptance gate. Preserve all prior negatives.
Identical choices mean no observed policy-selection effect for this candidate bank.
Different choices with unresolved bounds mean the observed data do not resolve the
contrast under this evaluation; do not declare equivalence or superiority. Favorable,
adverse or mixed directions all remain in the report, without changing horizons,
weights, candidate bank, thresholds, or initiating a larger search. Failed/limited jobs
are incomplete evidence; fix implementation defects locally, not by silently relaxing
resource/data bounds. No raw data change or server coding agent is required.

After the one real run, assess whether its private effect magnitudes and complete pattern
support a useful, limited empirical paper. If not, finish the reproducible negative report
and close this question; do not spend additional UCSF runs trying to manufacture a win.
No original held-out evaluation is authorized by R001. Manuscript readiness remains
unestablished; a positive direction alone does not justify a publication claim.


### R001 completed findings and disposition (2026-10-19)

The user returned the completed monitor summary for UCSF job 39335 at source
`21762073fe9aff38dfb37d9feddc54e9205fe1fa`, bound to original W001 job 39332.
Preflight and planning reported the frozen three-seed, 5x3 patient CV, eight-candidate,
480-fit design within 2 CPU/4 GiB/1200 seconds. The monitor reported complete with verified
artifacts and `private_review_required: true`. This is operator-reported execution and
an automated summary; the Mac did not inspect private artifacts. Original validation/test
remain unevaluated, no raw scan or GPU was used, and no numerical metrics were shared.

All directions are for `upper_brier minus joint_nll` (negative favors upper_brier).

| Fold seed | Primary patient-weighted completion bounds | Order-weighted sensitivity | 1h / 4h / 12h / 24h bounds | Joint NLL direction |
| --- | --- | --- | --- | --- |
| 20261020 | Includes zero | Includes zero | Above / below / includes / includes zero | Lower |
| 20261021 | Above zero | Above zero | Below / above / above / above zero | Higher |
| 20261022 | Includes zero; identical policy predictions | Same | Includes zero at every horizon; identical predictions | Equal |

At seed 20261020 the policies differ only in the third outer fold: NLL selection chooses
PH pooled timing and upper-bound selection chooses PH typed timing. At 20261021 they
differ only in the fourth fold, with these choices reversed. At 20261022 both choose
PH pooled timing in every outer fold; the shared candidate prediction path therefore
gives identical policy predictions, rather than merely an unresolved comparison between
different models. All selected candidates are PH pooled or typed timing. Non-selection
of this fixed shallow tree does not establish that nonlinear models generally fail.

The first seed does not resolve the primary finite-sample contrast. The second's entire
reported completion range favors NLL selection in this sample. The third has no policy
difference. There is no demonstrated primary advantage for upper-bound selection, and
the first two seeds' horizon reversals cannot be turned into a new favorable endpoint.
These are overlapping development splits, not three independent studies; bounds are
not confidence intervals, and signs cannot be averaged to recover an unreported overall
contrast. No population significance, statistical equivalence, effect size, calibration
or clinical utility follows. Private bootstrap endpoint values were not returned.

Disposition: the fixed comparison is complete. Preserve the negative/mixed report and
close development of the upper-bound selection policy on these artifacts. Do not change
weights/horizons, expand the model bank, recalibrate, choose a favorable seed, or open
original held-out evaluation to obtain a win. W001's secondary workflow signal is not
erased by this result, but it does not supply a new method contribution. The qualitative
manuscript now states these results; authorized numerical manuscript assembly can use the
already-produced private tables without another fit. Publication readiness remains
unestablished. No additional server task, new data or semantic review is requested.

## M001: generated relation-memory prototype (2026-10-19)

Status: implemented as a **local synthetic mechanism benchmark**, separate from every
clinical experiment above. Run `make memory-demo`. It accepts a strict generated config
only; there is no cohort/history/mapping input or server entry. No original held-out
patients, new source semantics, recurrent clinical extraction or GPU training are involved.
This is not a frozen clinical protocol or a claim that a novel algorithm has been found.

### Target and simulator

One cutoff per generated patient; 4 or 12 already-known orders. Histories contain repeated
linked events, and the target is each order's next recurrence or terminal event within
four abstract discrete steps. These steps are not clinical hours. The simulator conditions
on all orders surviving to the cutoff; it does not model an entire clinical order lifecycle.
Future orders are not target candidates. No causal, adherence, dosing or harm claim.

Four fixed mechanisms: heterogeneous renewal intervals, switching fast/slow intervals,
a patient-wide shared burst process, and a constant memoryless null. There are 48 history
steps, with distinct generated birth times. Distinct orders may have simultaneous events;
no arbitrary within-timestamp chronology enters the predictor. A separate random generator
sets patient observation end independently of the event process. Complete latent outcomes
exist only for synthetic oracle evaluation and are never used to train either learner.
Neither clocks nor the generator are inferred from UCSF values.

The predictive distribution has nine categories: no recurrence/terminal event by step 4,
four recurrence bins, and four terminal bins. An early-censored observation permits every
later category of both causes plus the no-event category. Its loss is minus the log of
the total permitted probability. This observed-data likelihood uses the simulator's
independent observation rule; it does not solve arbitrary informative observation.

### Algorithm being assessed

All policies can inspect the same visible prefix, with occurrence strictly before and
availability no later than the cutoff. Order identifiers are grouping keys only.
Each order offers retention depths 0 through 6; an action retains its most recent events.
The common small tanh MLP decoder is trained with all depths on the decoder-training
patients. Inputs comprise retained lags/masks/statistics, known order age and four shared
prefix counters. No latent simulator state, future time or outcome is an input.

On separate allocator-training patients, compute each depth's observed loss improvement
relative to depth zero using the frozen decoder. A ridge regressor predicts that improvement
from past-only descriptors and their quadratic terms. Multiple-choice knapsack then chooses
depths to maximize the sum of predicted improvements, subject to the patient's event-slot
budget. All outcomes stay out of the allocation interface during evaluation. This is
standard regression plus discrete allocation, **not established methodological novelty**.
It is a cheap probe of whether adaptive allocation offers anything worth developing.

Canonical grouping uses observed birth times and history lags, never identifier spelling.
Orders with identical observable signatures must receive equal allocations; a budget may
be underfilled to preserve that symmetry. The DP is exact for its estimated additive
utility under this constraint. It is not an oracle for unknown predictive risk or a model
of the joint dependence among future order events. Correlated orders are evaluated with
patient aggregation, not independent-order confidence intervals.

### Controls and leakage protection

Eight policies are reported, with the same generated patient groups:

1. Globally most recent event context.
2. Balanced per-order context, taking a round from each order before the next round.
3. Static depth utilities learned on the allocator-training group, without personalization.
4. Prefix-dependent learned utilities plus the same exact allocation solver.
5. Up to six recent events for every order (reference outside the shared slot budget).
6. Per-order whole-history summary (reference with six additional summary numbers per order).
7. Direct prediction from the allocator's own descriptors and shared counters, without
   event selection. This checks whether the selector's side information already suffices.
8. A history-free constant distribution fitted on the decoder-training group, especially
   important for the memoryless null.

The reference decoders use the same small MLP family, fixed epochs and optimizer settings;
their input dimensions/parameter counts differ and are reported. They are not TGN,
Transformer or state-of-the-art reproductions. The first four policies share the exact
decoder. No fitting or policy selection uses evaluation patients. An evaluation-only
prediction-assignment permutation within each patient tests whether order-specific
alignment matters; it is an ablation, not another model fit or clinical perturbation.

### Fixed local run and reporting

Config `configs/synthetic_memory.yaml`: three seeds, four mechanisms, two order counts,
two budgets (4 and 12), giving 24 fitted cases / 48 budget comparisons. Each case has
128 decoder-training, 96 allocator-training and 192 evaluation patients. Fixed 16 hidden
units, 100 full-batch Adam steps, learning rate 0.02 and ridge 0.01. Patient sets are
disjoint within a case; repeated budget comparisons reuse fitted models/evaluation
patients, and seeded mechanism comparisons are not independent clinical replications.

Report patient-mean observed NLL, simulation-only complete NLL and execution Brier score,
retained event slots, all paired learned-versus-control contrasts, and the assignment
ablation. The 200-replicate patient bootstrap conditions on fitted models and policies;
it omits fitting/selection uncertainty and does not establish population superiority.
Keep all seeds, mechanisms and budgets. There is no automatic server-advancement rule.

**The event-slot budget is not total memory.** This offline implementation scans and
materializes the prefix. The roster, four shared counters, 44 allocator descriptor
numbers per order, model parameters and DP workspace are extra. It reports scan counts,
array sizes and separate selection/decoder timings; it does not measure full peak RAM.
Training enumerates retention depths. A shorter retained context therefore cannot be
reported as end-to-end speed or storage savings. The descriptor-direct and summary
references are necessary controls for this possible accounting failure.

Artifacts are explicitly synthetic: config, models, metrics, resource observations and a
manifest containing source/config/lock hashes, dirty Git provenance and completion status.
Existing run directories are never overwritten; failed runs retain failure status without
exception payloads. Run focused tests plus `make check` and `make demo` after changes.

### Research decision boundary

A gain only over global truncation does not justify a methods paper. If balanced context,
simple summaries or descriptor-direct prediction remove the advantage, preserve that
negative finding and redesign locally before proposing UCSF work. Even favorable synthetic
results would still need a distinct contribution relative to temporal graph memory and
sequence compression, strong matched-input baselines, a reviewed recurrent coverage
contract and independent evaluation design. No new clinical run follows automatically.

### First full generated findings

The initial complete run was `artifacts/synthetic/20261019T204214Z-memory-d6eb4bda`
on dirty base `bbbb662`. All 24 cases / 48 budget comparisons completed. The following
are equally weighted summaries of the twelve seed/order-count/budget combinations per
mechanism, **not independent replications, significance tests or clinical effect sizes**.
Differences are learned allocation minus the named reference in patient-mean observed
NLL; negative favors the learned allocation. Individual cases and conditional intervals
remain in the synthetic artifact.

| Generated mechanism | Mean difference vs recent | Mean difference vs balanced | Cases lower than balanced | Mean difference vs per-order summary | Mean difference vs history-free |
| --- | ---: | ---: | ---: | ---: | ---: |
| Renewal | -0.01117 | -0.00513 | 9 / 12 | +0.00350 | -0.01849 |
| Switching | -0.00366 | -0.00164 | 7 / 12 | -0.01006 | +0.00368 |
| Shared burst | -0.00213 | -0.00212 | 8 / 12 | -0.01339 | -0.03573 |
| Memoryless null | -0.00087 | -0.00056 | 6 / 12 | -0.00989 | +0.01594 |

For renewal, prediction-assignment permutation raises NLL by 0.04086 on average; for the
null it changes NLL by only 0.00128. These are checks against deliberately specified
synthetic mechanisms, not discoveries about clinical link information. The history-free
reference beats learned allocation in all twelve null cases. A higher-dimensional direct
descriptor MLP performs poorly here; that does not establish superiority over a well-tuned
descriptor learner, and the simple whole-history summary already removes the renewal
advantage on average. The limited small-MLP comparison is insufficient for a methods claim.

In the initial run, summed selection-plus-decoder time over the grid was 4.360 seconds
for learned allocation versus 0.488 seconds for balanced allocation (about 8.9x). These
are local implementation timings, excluding common prefix encoding and training, not
hardware-independent complexity or a total-memory measurement. The utility regressor adds
315 parameters and uses 44 descriptor numbers per order; the common decoder has 537
parameters, versus 345 for the summary decoder. Fixed prefix-state costs remain extra.

Disposition: the prototype demonstrates that the mechanics are runnable, but does not
support the current allocation design as a new publishable method or an efficiency gain.
Do not send this candidate to UCSF solely on these results. A further local method stage
must address utility-estimation stability, the descriptor/storage cost and the nearest
temporal-memory algorithms, and include stronger matched-input comparisons. The broader
original-data recurrent-learning question remains unresolved; this run cannot settle it.

After clarifying per-patient versus total materialized array accounting and tightening
joint simulation/allocation work limits, the final implementation reran at
`artifacts/synthetic/20261019T204448Z-memory-c1ffc4d9`. Metrics, model parameters and
config reproduced byte-for-byte; artifact and current source hashes were verified.
Resource timings are measured anew and are not expected to be bitwise identical.

## J001 — finite joint-path and observation audit (generated references only)

Status: implemented locally after the user's instruction to continue autonomous research.
This is research infrastructure, not a selected new paper method or a clinical gate.
Run `make joint-audit-demo` with `configs/synthetic_joint.yaml`. No clinical path/config
argument is accepted. It does not use M001's decoder, tune the closed allocation method,
or alter existing clinical jobs. All times and rates are artificial dimensionless values.

The fixed initial grid has three seeds, 256/1024 generated patients, three dependence
mechanisms, three observation laws and four reference estimators: 54 fitted cases.
Each patient has two anonymous entities and three future bins. Each bin can contain no
event, a recurrence, or an absorbing terminal event; post-terminal cells are padding,
not observation loss. There are 15 valid paths per entity and 225 joint states. Recurrence
is allowed repeatedly; ties across entities are joint-bin events, never arbitrarily sorted.
No claim about real timestamp precision or actual clinical simultaneity follows.

Independent, synchronized and opposed latent-rate mechanisms have **exactly the same
per-entity path marginals**, and different joint path laws. Fixed low/high recurrence
probabilities are 0.08/0.50 per bin and terminal probability 0.08. This construction is a
mechanism test, not evidence that UCSF has this dependence. Observation ends for both
entities together: always bin 3; bins 1/2/3 with probabilities 0.5/0.3/0.2; or bins 1/2
with probabilities 0.5/0.5. Observation is independent of the future in this initial grid.
The latent RNG is separate from the observation RNG. Changing censoring does not regenerate
the underlying sample. No future path or its length is passed to a fitter.
This audit estimates unconditional path laws for a fixed two-entity roster; it has no
history encoder or patient covariates. Conditional forecasting and variable rosters remain
future work and must not be described as implemented by this finite reference laboratory.

Reference estimators, using the same observed-prefix sufficient statistics:

- Saturated per-entity path likelihood, factored into an independent joint forecast.
- Saturated joint observed-prefix likelihood, standard multinomial missing-data EM.
- Two-class product-multinomial EM, a standard shared-latent reference. Two fixed random
  starts are compared by observed training NLL only. This family deliberately matches
  the correlated generators; its advantage would not establish robust generalization.
- Zero-filled empirical paths, an explicitly invalid negative control for treating an
  unobserved future as no recurrence. It is not a legitimate clinical baseline.

Fixed EM iterations are 300, with positive symmetric pseudocount regularization. No
evaluation-selected hyperparameters or model restarts. Raw parameter counts differ:
224 for a saturated joint law, 28 for independent marginals, 57 nominal parameters for
the two-component product mixture (latent-class parameters need not be identifiable).
All fit times are reported; no efficiency claim is defined. Complete latent outcomes
are absent from the fit API. Evaluation integrates over the **known simulator law**,
reporting exact latent joint KL, observed-prefix KL, probability that both entities recur
at least twice, and marginal mean-count error. These are conditional risks of each fitted
forecast, not clinical estimates, confidence intervals or independent replications.

The observation audit provides a concrete counterexample: two joint laws have identical
prefixes through bin 2 and identical final-bin marginals, but final-bin joint recurrence
probabilities 0.5 and 0.0. With no bin-3 observations, both induce exactly the same observed
data. The nested observation operator has rank 49 on a 225-state space; a positive chance
of full observation gives rank 225. Positivity is an identification condition, not a
finite-sample adequacy guarantee. A fitted tail in the rank-deficient case is extrapolation.

Artifacts contain config, exact audit, all case metrics, generated fitted distributions,
runtime measurements, source/config/lock hashes and dirty Git provenance. They stay in
ignored `artifacts/synthetic`; no clinical weights or records are involved. Existing
directory reuse and source/config changes during a run fail explicitly. The next method
stage must beat appropriate references and address dependence misspecification; this audit
alone never authorizes a server run or establishes publishability.

### J001 first full results (no parameter changes after inspection)

Run `artifacts/synthetic/20261019T205703Z-joint-2d4b13f4` completed the full 54-case grid.
Below are mean exact simulator joint KL risks across the three fitted seeds. Seeds are
not three independent clinical studies; these are descriptive generated results.

| Patients / observation | Mechanism | Independent paths | Joint latent class | Saturated joint |
| --- | --- | ---: | ---: | ---: |
| 256 / full | independent | 0.06624 | 0.17057 | 0.96946 |
| 256 / short | synchronized | 0.42147 | 0.51887 | 1.53226 |
| 256 / short | opposed | 0.33476 | 0.39850 | 1.59691 |
| 1024 / full | independent | 0.01322 | 0.04250 | 0.23872 |
| 1024 / full | synchronized | 0.12832 | 0.03311 | 0.27740 |
| 1024 / full | opposed | 0.13122 | 0.02518 | 0.21962 |
| 1024 / short | independent | 0.06872 | 0.16107 | 0.88217 |
| 1024 / short | synchronized | 0.19513 | 0.12189 | 0.90907 |
| 1024 / short | opposed | 0.17634 | 0.10240 | 0.79461 |

All other cells and all four methods remain in the artifact. The table intentionally
includes adverse/null and favorable cases. Saturated joint estimation performs poorly
with this sample size and weak fixed prior; it is not a sufficiently strong sole baseline.
The latent-class family matches the generator, so its favorable correlated cases do not
establish superiority under misspecification. Priors differ structurally across model
families; no comparison at matched effective complexity has been performed.

In no-tail-support cases the full distribution is not identified: ranks are 49 versus
225, and the explicit witness has identical observed law with final joint probabilities
0.5 versus 0.0. Numerical latent scores in those cells are simulator-only assessments of
extrapolations, not recovery guarantees. Known marginal mean counts can be correct while
the joint law is wrong. Zero-filling strongly degrades short-window latent risk and is
retained only as an error control.

All fitted reference algorithms together took about 1.91 seconds in the initial run
(excluding setup, output and audit); this tiny enumerated setting cannot support a
scalability claim. Source and artifact hashes were verified. There was no hyperparameter
search, server execution or clinical interpretation. Next research question: can an
observation-adaptive dependency estimator preserve useful dependence while avoiding
unjustified complexity in the small-sample/null cases? Strong hierarchical shrinkage and
model-averaging references are needed; simply adding a mixture gate is not presumed novel.

## J002 — prefix interaction shrinkage (local candidate, fixed initial experiment)

The candidate and fixed experiment were specified before inspecting its full-grid results.
Run `make joint-shrinkage-demo`, config `configs/synthetic_shrinkage.yaml`. Reuse J001's
two entities, three bins, 15 valid paths per entity and 225 joint states. This is still
an unconditional finite laboratory, not a variable-roster neural model or clinical adapter.
The scientific question is whether separating interaction complexity by observable depth
improves the dependence/bias tradeoff versus global shrinkage and stronger smoothers.

### Candidate construction and limited analytic statement

Split generated patients into an independent pilot half and estimation half. The pilot
fits two per-entity observed-prefix marginal laws `a` and `b`; all candidate adaptations
share the product reference `p0 = a b`. Each strictly positive marginal defines a weighted
orthonormal basis on its prefix tree. There are 2 contrasts first revealed at bin 1,
4 at bin 2 and 8 at bin 3. A depth-d contrast has zero conditional mean given any shorter
prefix under its reference marginal. Products of the two entities' contrasts give 196
interaction coefficients, revealed in blocks of sizes 4, 32 and 160.

At the independent reference, for common observation `C` independent of the path, the
observed-data Fisher information for this interaction basis is diagonal, with entry
`P(C >= max(d1,d2))`. This follows by conditioning each contrast on the observed prefix
and using weighted orthonormality. It is a direct finite calculation, verified numerically;
no new general statistical theorem or optimality result is claimed. In particular, using
the product of the two observation probabilities would be wrong for a shared window.

The estimator uses sample covariance of the two contrasts among patients observed through
their reveal depth. Centering avoids spurious interactions from imperfect pilot marginal
means under independent paths. A plug-in variance estimate gives a positive-part block
factor `max(0, 1 - summed_variance / squared_coefficient_norm)`. Blocks with fewer than
three observations remain zero. Global shrinkage uses a single block as an ablation;
the unshrunk covariance estimate is another ablation. A single final contraction toward
`p0` enforces a minimum density ratio 0.01. It preserves both reference marginals and zero
unsupported coefficient blocks, but can suppress useful interactions when a rare cell
would otherwise become negative. All factors and this contraction are reported.

The variance approximation and shrinkage are heuristic; there is no finite-sample
improvement guarantee. Conditional on a fixed pilot basis, covariance estimation is
appropriate for independent observation; history-dependent stopping can select a biased
complete-prefix sample. The pilot marginals are estimates, not truth or known calibration.
Preserving them does not prove calibration. Without later observed subjects, the baseline
tail remains an extrapolation, even though its extra interaction coefficients are zero.

### Comparators, mechanisms and evaluation

Eight methods: independent pilot; spectral global/reveal/unshrunk; cross-validated
Dirichlet-tree/global-blend reference; oracle-marginal spectral diagnostic; all-patient
independent and two-class latent models. The oracle diagnostic receives the simulator's
true marginals and is explicitly infeasible; it can isolate pilot error but cannot support
the deployable candidate's claim. The all-patient references use the same total patient
budget and can pool it more efficiently. Candidate and tree/blend share the pilot half.

The Dirichlet-tree reference learns conditional transitions at each observed prefix,
shrunk toward `p0` by total strength 1, 10 or 100. Independent/joint blend weights are
0, 0.25, 0.5, 0.75 or 1. Two-fold observed-prefix NLL CV within the estimation half selects
among the fixed 15 pairs, then refits on that half. This is ordinary model selection,
not a new algorithm; exact synthetic evaluation risk never enters selection.

The full fixed grid uses three new seeds, total patient counts 256/1024, five mechanisms
and five observation policies: **150 cases**. Mechanisms include J001's independent,
synchronized and opposed mixture laws, plus alternating within-bin dependence across
time and reciprocal lagged dependence. These last two stress the simple latent-class
assumption; their exact path probabilities are computed, not estimated from test samples.
Policies are full, independent short, no tail support, adaptive past and informative future.

Adaptive-past stopping uses recurrence information already observed at each bin; its
stopping probability is constant within each observed-prefix equivalence class. The
ordinary joint prefix likelihood is ignorable under this known generated mechanism, but
the complete-prefix covariance estimator is not generally unbiased. Informative-future
stopping also depends on unobserved outcomes and is deliberately outside both assumptions.
No stopping kernel is passed to any fit. Kernels and full laws are evaluation-only.

Metrics distinguish latent joint KL; true observation-channel KL after applying the
known simulated stopping kernel; and excess ordinary-prefix log score versus the true
latent law. Under informative stopping, the last quantity is not a KL divergence and
can be negative even for a wrong latent forecast. A separate exact two-path counterexample
checks this. Also report joint repeated-event probability error, all choices, contraction,
support counts, fit runtimes and all fitted generated distributions. No best-cell search,
clinical significance test, clinical advancement rule or claim of publication readiness.

### J002 first full results and next estimator design

Full run `artifacts/synthetic/20261019T210442Z-shrinkage-667c0c5e` completed 150 cases
without changing parameters after inspection. At 1024 total patients under independent
short observation, mean latent joint KL across all five mechanisms/three seeds was:

| Method | Mean exact simulator joint KL |
| --- | ---: |
| All-patient independent reference | 0.1619 |
| All-patient latent-class reference | 0.1542 |
| Shared-pilot tree/blend CV reference | 0.1845 |
| Pilot independent | 0.2469 |
| Global spectral shrinkage | 0.2475 |
| Reveal-depth spectral shrinkage | 0.2317 |
| Unshrunk spectral coefficients with positivity contraction | 0.2494 |
| Oracle-marginal reveal-depth diagnostic (infeasible) | 0.0640 |

Depth grouping improves on global grouping in 13/15 of these cases, but loses to the
tree/blend reference in all 15. At 256 patients under the same observation law, reveal
shrinkage is worse than the pilot baseline on average (0.5730 versus 0.5563) and beats it
in only 2/15 cases. Across the entire 150-case stress grid it beats the tree/blend in only
8 cases, with mean excess KL 0.04275. These descriptive counts are not hypothesis tests;
scenarios and seeds are deliberately reused in paired comparisons.

No-tail-support scores remain assessments of extrapolation. Informative-future policies
remain assumption-violation stresses; e.g. the ordinary prefix score rewards the fitted
latent-class reference over the true latent law in 9/30 such cases. The correctly applied
known observation-channel KL is a separate evaluation quantity. The exact counterexample
in the tests establishes the distinction independently of these fitted results.

The maximum marginal-preservation error is 4.45e-16, and no coefficient without empirical
reveal support is nonzero. Positivity contraction is active in 75/150 cases, with mean
factor 0.64465 and minimum 0.00209. This can nearly erase an otherwise useful correction.
The oracle-marginal diagnostic indicates that pilot estimation contributes substantially
to the gap, but it also changes the basis and variance; it is not an isolated causal
decomposition or evidence available to a deployable learner. The tree reference can
update the joint law's marginals from the estimation half, unlike the constrained candidate.

Disposition: retain the observation-depth basis/information calculation and negative
benchmark, but do not advance this split-pilot, globally contracted estimator to UCSF.
No novel-method superiority or publishability is established. This is a local algorithm
failure, not a decision to stop the broader research question or evidence that the original
clinical data lack useful dependence.

The next estimator design is **planned**: optimize one complete probability law using
observed-prefix likelihood, learning marginals and interactions together, with nonnegative
normalized probabilities enforced during optimization. A convex finite-state formulation
can penalize groups of linear interaction coefficients, plus a small positive reference
barrier, on the probability simplex. This avoids the pilot-only marginal constraint and
post-fit global contraction; it does not by itself establish a new method.

For a likelihood normalized by the total number of patients, the null score variance of
a reveal-depth block scales as `G_depth/n`, while its curvature scales as `G_depth`.
Thus a score-based group penalty would scale like `sqrt(block_size * G_depth / n)`;
using an inverse-observation penalty directly would count information loss twice. The
resulting parameter threshold still grows as observation decreases. This calculation
assumes an independent common window and a fixed reference. Predictable stopping needs
its own information analysis, and future-informative stopping remains nonidentified
without extra assumptions. Solver verification and a separate fixed comparison are
required before reporting performance for this planned estimator.

## J003 — joint convex prefix likelihood (fixed experiment before full-grid inspection)

The planned J002 successor is now implemented as `make joint-likelihood-demo`, using
`configs/synthetic_likelihood.yaml`. It keeps the same 225-state laboratory, five laws
and five stopping policies, with new seeds 20261026/27/28 and sample sizes 256/1024:
150 cases. It is neither a variable-roster model nor a clinical experiment.

For positive simplex probabilities `p`, minimize observed-prefix negative log likelihood
plus `KL(reference || p)/n` plus smooth group penalties on linear interaction coefficients
`Z_g.T (p-reference)`. Each group norm is `sqrt(norm_squared + 0.001^2)-0.001`.
The reference is a product of per-entity path laws fitted on the training patients;
it is fixed during optimization, but the fitted distribution's marginals are free.
There is no post-fit positivity contraction. Global grouping pools all 196 contrasts;
reveal grouping separates the 4/32/160 blocks. Weights are
`sqrt(sum_j G_reveal(j) / n)` within each group. The independent-window score calculation
motivates these weights; empirical references and predictable stopping do not inherit
a proved statistical guarantee.

Two-fold patient CV selects the independent reference or strengths 0.25, 1, 4 by ordinary
observed-prefix NLL. All marginal/reference fitting occurs separately inside each fit
fold. The selected model is refitted on all patients. A stronger all-patient Dirichlet-tree
and independent-blend comparator uses the same folds, fold-local references, strengths
1/10/100 and weights 0/0.25/0.5/0.75/1. Additional comparisons are all-patient independent,
two-class latent, and zero-interaction-penalty likelihood (the positive reference term
remains). No oracle marginal or simulator kernel enters fitting or selection.

The damped equality-constrained Newton solver enforces positivity and normalization.
For convex differentiable objective `f`, `gradient.p - min(gradient)` bounds objective
suboptimality on the simplex. Every fitted candidate must certify gap at most 1e-7;
iteration or line-search failure stops the experiment explicitly. This is an optimization
certificate, not a statistical error or generalization bound. Focused tests check exact
derivatives, convexity, analytic full-observation solution, agreement with censored EM,
entity-exchange equivariance of the fixed fit, and CV isolation. Seedwise equivariance
of random CV allocation is not claimed.

Report all cases, the three distinct J002 risk quantities, joint repeat probability,
selected strengths, fold sizes, solver gaps and runtimes. No-tail cells assess extrapolation;
future-informative cells violate the likelihood assumption. Compare against the strong
tree and latent references, not only the failed J002 candidate. No parameter retuning
after inspection of this full grid, clinical advancement rule or publication claim.

### J003 results and disposition

Run `artifacts/synthetic/20261019T211257Z-likelihood-cbefb2e1` completed all 150 cases;
source/config/output hashes verified. All 1800 CV Newton fits and all selected final
fits met the fixed 1e-7 optimization gap. This rules out failure to solve these fixed
objectives as an explanation, but does not validate their statistical design.

| 1024 patients; mean latent KL across five laws and three seeds | Full observation | Independent short window |
| --- | ---: | ---: |
| All-patient independent | 0.10763 | 0.15737 |
| All-patient latent class | 0.05423 | 0.16210 |
| Global interaction penalty CV | 0.10197 | 0.16230 |
| Reveal-depth penalty CV | 0.08607 | 0.15177 |
| Zero interaction penalty; positive reference term retained | 0.27321 | 0.94042 |
| All-patient tree/blend CV | 0.04202 | 0.11498 |

Across 150 cells, reveal-depth beats global grouping in 32, ties in 103 and loses in 15;
mean KL difference is -0.00194. Against tree/blend it wins 21, ties 21 and loses 108,
with mean excess KL 0.03065. These counts include assumption-violation and unsupported-tail
stresses and are descriptive, not pooled inferential evidence. At 256 patients with
independent short windows, its mean KL is 0.37103 versus independent 0.34846 and tree
0.33314. At 1024 patients under adaptive-past stopping it is 0.19676 versus independent
0.19271 and tree 0.14899. Thus the average favorable large-sample comparison with the
independent baseline does not establish a useful general estimator.

Global/reveal CV selects the independent model in 128/104 of 150 cells respectively;
reveal selects strength 1 in 44 and 0.25 in 2, never 4. Do not retrospectively broaden
the penalty grid to rescue these results. Total fitting times across the grid were
20.49/25.45 seconds for global/reveal CV, 16.99 for tree/blend, 3.46 for latent class and
1.13 for independent. These are tiny finite-state computations, not a scaling benchmark.

Disposition: J003 does not earn a server experiment or main-method status. Preserve its
certified solver and adverse comparison. The next local step is an **information audit**,
not another immediate penalty sweep: test whether predictable stopping preserves separation
of reveal depths while coupling marginal and interaction scores within a depth. Under
independent common stopping, the full contrast information is diagonal. Under predictable
history stopping, martingale differences suggest block separation by reveal time, but
within-block information can be anisotropic and nuisance-marginal coupling can reduce
effective interaction information. Future-informative stopping need not even give a
zero-mean ordinary-prefix score. These are finite calculations to verify, not claimed
new general theorems or an implemented successor estimator.

### Exact predictable-stopping information audit (implemented)

`make joint-information-demo` enumerates all states under five fixed known simulator
kernels, without sampling or fitting. Run
`artifacts/synthetic/20261019T211628Z-information-ebb50612` completed and hashes verified.
The audit uses all 224 centered orthonormal scores at the product reference: 28 marginal
and 196 interaction scores, with total reveal-depth dimensions 8/40/176. It compares
ordinary prefix scores to the correct observed-channel scores. An additional unequal-
marginal basis test prevents relying on exchangeability of this one reference.

For a local submodel `p_theta = q (1 + Z theta)`, ordinary scores are
`E_q[Z | observed prefix]`, whereas known-channel scores are
`E_q[Z | C, observed prefix]`. They coincide when `P(C=c | full path)` is constant
within each observed prefix cell. This is a check on a **specified simulator kernel**,
not a test of CAR from coarsened patient records. True channel scores have zero mean
and information bounded by the complete-data identity matrix; finite differences and
eigenvalue tests check both statements for every policy.

At the product reference, a contrast first revealed at depth d has conditional mean
zero given depth d-1. Products of two entity contrasts have this property at the later
reveal depth: if both are new, conditional independence under q makes their product
mean zero. Under predictable stopping, `1(C>=d)` is determined before depth d is
observed. Consequently the stopped score is `1(C>=d) Z_d`, and cross-depth second
moments vanish by conditioning on the earlier history. Within a depth the matrix is
`E_q[1(C>=d) Z_d Z_d.T]`; it need not be diagonal or separate marginal and interaction
directions. This is a finite martingale calculation, not a new general theorem.

The exact audit verifies this distinction. With independent short windows, information
is diagonal with entries 1/0.5/0.2 at the three depths and no nuisance coupling. With
adaptive-past stopping, cross-depth entries remain below 2e-16, but the largest marginal-
interaction entry is 0.22705. Projecting marginal nuisance scores out by the generalized
Schur complement reduces interaction information trace from 47.92443 to 46.33436;
all 196 interaction directions remain identified in this specified example. No-tail
observation has full score rank 48 and interaction rank 36, consistent with 49 observed
probability cells minus normalization. Regularization cannot add those missing directions.

Under future-informative stopping, the ordinary score has mean magnitude up to 0.06148
and cross-depth second moment up to 0.12782. Its second moment is not called the Fisher
information for the true observed experiment. Using the **known simulated** channel
restores a zero-mean score; this is not a proposed solution when a clinical channel is
unknown. The audit emits no efficient-information claim for the misspecified ordinary
score and does not infer a clinical stopping mechanism.

Next implementation is planned: compare sequential conditional transition structures,
sharing simple marginal dynamics across contexts and allowing interaction complexity
where observations support it. First add strong finite Markov/context references before
calling such a construction new. This will separate generic factorization/shrinkage gains
from any benefit attributable to observation adaptation. No architecture, clinical
protocol, data-access request or publication claim has been selected by this audit.

## J004 — sequential context reference audit (fixed protocol before full-grid results)

The next experiment tests strong established conditional models before proposing another
regularizer. Enumerate the same two-entity, three-bin valid paths. Factorize their law
into normalized transitions at each future bin, retaining absorbing terminal constraints.
Compare independent per-entity transitions and joint pair transitions. Contexts retain
zero, one or two previous bins (two is the full available history here), plus current
alive status and bin index. Separate models per bin do not assume stationary transitions.
These are ordinary finite context/Markov models, not a new algorithm or a variable-roster
architecture. Outcome probabilities use symmetric Dirichlet smoothing with total strength
1, 10 or 100 over valid next outcomes, never simulator probabilities or fitted latent truth.

Only patients observed through a transition contribute to its counts. Two-fold generated
patient CV selects among nine independent candidates, nine joint candidates, or all 18;
all predictions are refitted on the same full training sample. CV uses observed-prefix
NLL only. The full-list selector reuses the two sublists' losses, avoiding duplicate fits.
All-patient latent-class, independent path EM, and J003's strong tree/blend CV are references.
This isolates conditional sharing, memory and joint modeling, not a claimed novel gate.

Use new seeds 20261029/30/31, sample sizes 256/1024, all five J002 mechanisms and all five
observation policies: 150 fixed cases. Report exact simulator risks, selections, nominal
transition dimensions and runtimes. No-tail scores remain extrapolation assessments.
Predictable stopping can still alter the best approximation in a misspecified restricted
context family; ignorability alone does not prove full-law risk optimality. Informative-
future stopping remains outside the ordinary likelihood assumption. No new data, private
server task, model-selection significance test or publication gate is introduced.

### J004 fixed results and implications

Run `artifacts/synthetic/20261019T211915Z-context-2e036c9d` completed all 150 cases;
source/config/artifact hashes verified. The structural context references are competitive
in some regimes, but neither their global selector nor a single family dominates.

| Mean latent KL over five laws/three seeds | All-context CV | Independent-context CV | Joint-context CV | Tree/blend CV |
| --- | ---: | ---: | ---: | ---: |
| 256 / full | 0.15740 | 0.15740 | 0.16550 | 0.14422 |
| 256 / independent short | 0.24061 | 0.23052 | 0.28157 | 0.29553 |
| 256 / adaptive past | 0.23392 | 0.22787 | 0.25032 | 0.34605 |
| 1024 / full | 0.04685 | 0.10608 | 0.05918 | 0.04352 |
| 1024 / independent short | 0.12288 | 0.13836 | 0.14254 | 0.09943 |
| 1024 / adaptive past | 0.12382 | 0.14884 | 0.14495 | 0.14306 |

All unsupported-tail and future-informative cells remain in the artifacts. Across the
complete stress grid, all-context CV beats tree/blend in 73/150 cases, loses in 77 and
has mean KL difference -0.01424. This aggregate includes extrapolation/assumption-violation
stresses; do not turn it into a general performance claim. It beats path-independent EM
in 122/150 cells, but that establishes a stronger standard comparator, not method novelty.

For 1024 patients under independent short windows, context CV is better than tree/blend
in the alternating-dependence mean (0.06455 versus 0.08522), worse in synchronized
(0.17643 versus 0.10232) and opposed (0.17497 versus 0.11960), and slightly worse in
lagged dependence (0.13997 versus 0.13481). The joint-only context selector is better
in the lagged case (0.11015), showing finite-sample selection cost. The latent-class
reference remains stronger in the persistent synchronized/opposed mechanisms. A short
Markov context and a persistent latent class encode different kinds of dependence;
this is a reason to retain both as comparators, not to choose favorable scenarios.

The all-context selector chooses an independent structure in 97/150 cells and a joint
structure in 53; no full-history joint or strength-100 model is selected. The three
selectors share fits and together take 10.67 seconds across 150 cells, versus tree/blend
16.47 and latent class 3.39. No variable-roster or large-horizon scaling claim follows.
Focused tests verify equality of the full joint context model with a matching-prior
Dirichlet tree, absorbing support, normalization, entity exchange, patient CV isolation,
deterministic artifacts, and exclusion of unknown tails from transition counts.

Disposition: retain sequential context models as strong baselines. Do not present their
ordinary CV as a new ML method or repeat these same cells with a tuned candidate list.
The next local design must address the actual scalability gap: variable entity counts
and longer paths, while representing both persistent and short-memory dependence and
preserving coherent prefix probabilities. Literature review and a bounded generated
design for that extension remain planned. The finite 225-state enumerator is a test
oracle, not a proposed clinical architecture. No new UCSF job is justified by J004 alone.

## J005 — projected cardinality interaction mechanism (initial design)

Instead of another finite-path penalty sweep, test a transition layer whose cost is
polynomial in the number of currently eligible entities. This initial layer conditions
on a risk set; recurrence/terminal sequencing and a persistent-state learner are not
yet implemented. Do not call a binary transition test a complete recurrent model.

Given independent reference probabilities p_i, let M be the count of simultaneous binary
events, mu=sum p_i and V=sum p_i(1-p_i). Fix a bounded feature
`g(m)=exp(-(m-mu)^2/(2*(V+1)))`. Define `a_i=Cov_0(g(M),Y_i)/Var_0(Y_i)` and
`U=g(M)-E_0 g(M)-sum_i a_i(Y_i-p_i)`. Its mean and all marginal-score covariances
vanish under the reference. Standardize by its reference standard deviation when positive.
The exponential tilt `p_beta(y) proportional p_0(y) exp(beta U(y))` is normalized exactly.
It is generally **not** exactly marginal-preserving for beta away from zero; this local
orthogonality is not calibration or a finite-sample improvement guarantee. Estimated
references also need their own error analysis.

The constant cancels in normalization, leaving count potential beta*g(m) and per-entity
log-odds offsets -beta*a_i (with the same standardization). A log-space polynomial dynamic
program computes the partition function and count probabilities; reverse differentiation
gives all entity marginals in quadratic time. Backward sampling draws an exact set given
the sampled count. Quadratic centered interactions and the unprojected bounded feature
are controls. The projection, exponential family and cardinality DP are known ingredients.

First validate enumeration equality on small sets, gradients, sampling, permutation
equivariance, orthogonality and positive/negative association, including sizes up to 128.
No fitting-performance claim will precede those checks. A bounded scalar likelihood fit
may then test the layer at a fixed reference; it must report optimization residuals and
distinguish true-reference mechanism tests from feasible learned-reference experiments.
This design does not identify unseen tails or unknown future-dependent censoring and
does not itself establish a new ML contribution.

### J005 first fixed transition comparison

After the exact engine tests, run 72 generated transition cases: seeds 20261101/02/03,
risk-set sizes 4/16/64, training subjects 128/512 and four mechanisms. They are independent
heterogeneous Bernoulli events, a shared log-odds shift mixture, an opposed subgroup shift
mixture, and a soft capacity count law. The opposed mixture deliberately lies outside a
single shared-cardinality tilt. This is a complete-observed **one-transition** mechanism
experiment, not evidence of handling actual clinical censoring or whole future paths.
Each roster size is fitted independently in this first benchmark; computational support
for varying K is not evidence of learned transfer to unseen roster sizes.

All feasible methods use the same subjects: empirical independent Bernoulli; projected
bounded tilt; unprojected bounded tilt; centered quadratic tilt; empirical count smoothing
with prior mass 10 around the independent count law; and two-product Bernoulli mixture
EM with fixed two starts and 100 iterations. Tilt reference probabilities use Jeffreys
smoothed per-entity training frequencies, strengths constrained to [-2,2] and ridge 0.01.
An explicitly infeasible oracle-marginal projected tilt isolates reference-estimation
effects and cannot support the feasible method's claim. No method sees the generating
parameters except that marked oracle diagnostic.

Use a fresh common sample of 4096 complete generated sets per fitted case for joint
log-density-ratio comparisons, reporting Monte Carlo standard errors rather than calling
the scores exact risks. Also report exact count-distribution KL, marginal-probability MSE,
and exact cross-entropy for count-potential models (their expectations depend only on
true marginals and the true count distribution). Record all models, convergence gaps,
boundary solutions and fitting time. The held-out sample is generated and separate from
fitting; no clinical split or previous experiment is opened. Do not retune the fixed grid
after inspection or claim novelty for the known references and computational primitives.

### J005 results and exact representation limit

Run `artifacts/synthetic/20261019T212816Z-cardinality-bf0a7894` completed all 72 fixed
cases. Source/config/artifact hashes were verified before the later diagnostic source
addition. Every scalar fit met its convex-gap tolerance (maximum below 3e-10).

| Mean estimated joint KL; three seeds and two training sizes | Projected bounded | Independent | Empirical count | Two-product mixture |
| --- | ---: | ---: | ---: | ---: |
| 4 entities / independent | 0.01218 | 0.01052 | 0.02050 | 0.01955 |
| 4 entities / shared shift | 0.01390 | 0.06783 | 0.01675 | 0.02058 |
| 16 entities / shared shift | 0.10181 | 0.78312 | 0.07012 | 0.08553 |
| 64 entities / shared shift | 2.25379 | 4.86424 | 0.41522 | 0.30541 |
| 64 entities / opposed shift | 4.82777 | 4.83678 | 4.87672 | 0.29118 |
| 64 entities / soft capacity | 0.74035 | 1.67844 | 0.19713 | 1.89954 |

All other cells, Monte Carlo errors, exact count KL, marginal errors and exact model
cross-entropies remain in the artifact. Comparisons between two count-potential models
can use exact cross-entropy differences, avoiding Monte Carlo ranking noise. Projection
beats the unprojected bounded control in 43/72 cells, with mean exact difference only
-0.00104. It beats empirical count smoothing in 41 cells but loses badly enough elsewhere
to have mean excess cross-entropy 0.19231. Its mean paired Monte Carlo NLL difference
versus the product mixture is +0.40138. These are descriptive stress results, not pooled
statistical evidence. The infeasible oracle-marginal variant is better in 71/72 cases;
that does not remove the large shared/opposed failures or demonstrate deployable benefit.

Projected bounded fits reach a strength boundary in 18/72 cells. Do not expand the bound
after seeing these results. Instead, `make cardinality-limits-demo` computes exact
population optima at true marginals within the **same [-2,2] family**, removing the
training sample and ridge penalty only for an explicitly infeasible diagnostic. Its
12-case run is `artifacts/synthetic/20261019T213103Z-cardinality-limits-d88d5d1f`.
For shared shifts at 64/128 entities, even these population oracles have count KL
1.92560/6.94979. Count KL is a lower bound on full joint KL. For capacity at 64/128,
the corresponding count KL is 0.57672/0.87464. Computation scales; this particular
statistical family does not adequately represent these mechanisms.

For any tilt strength bounded by B, the log density ratio to its reference is bounded
in magnitude by `B * (max U - min U)`, since the log normalizer lies between the minimum
and maximum tilted feature values. The extrema are computed without enumeration: for
each total count, select the largest or smallest linear offsets. Tests verify the bound
and extrema against full enumeration. This finite bound helps explain why a single
bounded contrast can miss increasingly separated collective modes; it is not a new
general theorem or a universal asymptotic statement about all roster sequences.

A stronger structural witness does not depend on the strength bound. In four binary
entities, distribution P puts half its mass on 1100 and half on 0011. Distribution Q
puts half on 1010 and half on 0101. Both have marginal probabilities 1/2 and total
count identically two, but the first pair jointly occurs with probability 1/2 versus
zero. Every density `r(y) proportional exp(fields.y + g(sum y))` has equal cross-entropy
under P and Q, regardless of fields or count potential. Within count two there are six
possible sets; Jensen's inequality gives cross-entropy at least log(6), whereas either
truth has entropy log(2). The family therefore has irreducible joint KL at least log(3),
attained in the limit by the uniform distribution over those six sets. Tests verify the
construction and attaining limit. This is a **model restriction**, not nonidentifiability
from complete observed sets: the two laws can be distinguished from the actual sets.

Disposition: keep the tested exact cardinality engine as a computational component,
but do not advance the single-total-count candidate as the paper method or a server
experiment. A successor must represent **which subsets interact**, using only their
observed histories and respecting anonymous-entity permutation symmetry. Learned
history-conditioned groups, richer latent mixtures and recursive count structures are
possible next designs, with the existing recursive-cardinality/conditional-circuit
literature as necessary references. None is implemented or selected by these results.
Do not call this complete-observed one-transition benchmark a long-path/censoring result.

### J006 fixed generated history-role and roster-transfer screen (before results)

J005's total-count family cannot distinguish interacting subsets. J006 first tests
whether history-based roles supply useful information in coherent recurrent paths.
This is a reference laboratory, not a novel model claim: conditional circuits, latent
Markov models and finite mixture aggregation are established. No clinical adapter.

Each generated subject has 4 or 8 anonymous entities in training (balanced by subject),
a supplied two-bit initial history, eight forecast bins, recurrent binary events,
independent history-dependent competing termination, and absorbing inactive states.
Only the last two observed event bits route an entity. Terminal and event probabilities
factor as P(terminal set | past) P(event set | past, survivors); this is a statistical
factorization, not a physical ordering claim. Censoring is complete or a predictable
history-dependent stop after at least two transitions. Unobserved tails are absent,
not zero events. Evaluation uses fresh complete subjects at 4/8/16/32 entities without
refitting; 16/32 were absent in training. No new entities enter during a path.

Six mechanisms: independent; fresh common shocks; fresh shocks with roles determined
by history parity; persistent shocks with those roles; persistent unobserved entity
roles (misspecified negative control); and history-role soft capacity (negative local
association outside the shock bank). True shock amplitude is 0.55, between bank values
0.3/0.7. Persistent state correlation is 0.85. Soft capacity uses the already tested
count DP with potential -4*(signed count - reference mean)^2/max(K,1). History rates
and terminal rates are fixed generated constants. These are not clinical assumptions.

Models use the same training subjects: independent four-history probabilities; a
shared-role bank; all eight history sign partitions (global sign symmetry removed),
two amplitudes and fresh/persistent shocks, plus independence; and a stronger learned
two-state conditional Bernoulli HMM with unconstrained per-history state probabilities.
The HMM has three fixed starts and 60 MAP-EM iterations. Bank components share fitted
marginals; weights are fitted to whole-subject prefix likelihood by 200 MAP-EM updates
with total pseudocount one. This is a population mixture over complete path laws,
not independent re-selection using future transitions or a Bayesian parameter posterior.
Positive mixture weights give coherent prefixes and the usual -log(weight) component
log-loss bound. These facts are standard and not novelty claims.

Fixed seeds 20261104/05/06; training subjects 128/512; both stop policies; six mechanisms;
512 independent evaluation subjects per roster size. Report subject-paired NLL differences
with Monte Carlo standard errors, per-at-risk-entity loss, all seeds/settings and runtimes.
These errors condition on fitted models and omit training/selection uncertainty. The
primary information check is full-role versus shared-role bank; the learned HMM prevents
mistaking hard-coded roles for a new method. No clinical advancement rule, grid expansion,
post-result favorable-case selection, or paper-readiness assertion follows this screen.

J006 fixed-screen result: `artifacts/synthetic/20261019T213741Z-history-roles-59277c83`
completed 72 fits and 288 evaluation cells. Source/config/output hashes were verified
before adding the separate roster-marginal diagnostic. All three seeds, both sample
sizes and stopping policies remain in the report. In both history-role mechanisms,
the largest fitted mixture weight identifies the generated parity partition in all
12 fitting settings per mechanism; fresh versus persistent dynamics is also recovered
in those largest-weight components. This describes the deliberately limited generated
family, not general subgroup recovery or a clinical property.

At the unseen size 32, mean subject NLL differences (full-role bank minus reference),
averaged over the fixed seeds/sample sizes/stopping policies, are:

| Generated mechanism | Independent | Shared-role bank | Learned HMM |
| --- | ---: | ---: | ---: |
| Independent | +0.20748 | +0.17731 | -0.03906 |
| Shared fresh shock | -5.93412 | +0.13497 | +0.53733 |
| History fresh roles | -5.94217 | -5.95562 | +0.66003 |
| History persistent roles | -8.26609 | -8.21444 | +0.79144 |
| Hidden persistent roles | +0.08563 | +0.03255 | +0.38896 |
| History capacity | +0.08084 | +0.03265 | -0.15605 |

History roles have usable information and transfer in the matching mechanisms. But
the learned HMM has lower mean loss in 238/288 cells, with average bank excess 0.13843;
this is not a competitive new-method result. The bank also worsens the independent
control, does not recover hidden entity roles, and does not learn the capacity law.
Do not tune its amplitude grid or promote a favorable subgroup as a new primary result.
Keep the learned HMM as a strong reference. Total fit times were approximately 2.77 s
(full bank), 0.66 s (shared bank), and 17.33 s (three-start HMM), excluding generation
and evaluation. They are measurements on this Mac, not hardware-independent complexity
claims. EM objective traces are monotone to rounding; no global HMM optimum is claimed.

### Exact roster marginal diagnostic following J006

`make roster-marginal-audit` sums omitted binary variables out of one fixed count law:
for omitted log polynomial coefficients B_l and original potential g,
g_keep(r) = log(sum_l exp(B_l + g(r+l))). This standard exact operation retains
unequal entity fields and composes under successive deletions. It does not rerun a
size-dependent potential with the number of observed entities. The full original
population's fields and potential must be known; unknown omitted histories are not
silently supplied or identified by this calculation.

Run `artifacts/synthetic/20261019T214017Z-roster-marginal-5f014301` verified six generated
population sizes 4/8/16/32/64/128. Keeping two entities from a capacity-constrained
population gives a different law from an actual two-entity population; TV differences
range from 0.06804 to 0.13754. Exact enumeration and sequential-deletion tests verify
the operation. This is an observation-versus-population distinction, not a requirement
that every interacting population be infinitely projective.

For entities with identical histories, any shared-latent conditional-iid event model
has pair covariance Var(p_latent) >= 0 (with independent termination, multiply by
survival probability squared). More states or a richer shared latent distribution
alone cannot reproduce negative within-history covariance. Different histories may
have opposite loadings and negative covariance; the restriction is specifically for
identical conditional features. Capacity laws have negative same-history covariance.
Their correlation rho obeys rho >= -1/(K-1); preserving rho < 0 while extending to n
entities requires n <= 1-1/rho. This follows from the variance of the event count and
is only a necessary extension condition, not a new theorem or a sufficient criterion.
The audit also verifies whole-entity marginal consistency for the recurrent HMM by
exhaustive path summation. Future work needs both joint local competition and coherent
observation likelihood; a new learner and its novelty argument remain planned.

### J007 fixed combined dependence screen (specified before results)

Following J006, test a two-state conditional HMM whose state emission is a finite-roster
signed count law, rather than conditionally independent Bernoulli responses:
P(y|h,z) proportional to exp(sum_h b[z,h]*Y_h + theta[z]*phi_s(Y,n)),
phi_s = (sum_h s_h*(Y_h-n_h/2))^2 / max(sum_h n_h,1), theta in [-8,0].
Here Y_h/n_h are event/survivor counts with history h; s is one of eight sign partitions
up to global reversal. Negative theta represents local competition while state-specific
b permits common positive or opposed shocks. Roles depend only on observed past bits.
This is a combination of established HMM and cardinality/population-coupling methods,
not a novel distribution or optimization claim. Existing broader tractable models must
remain part of the novelty assessment.

For training rosters up to eight, enumerate the four *group counts*, not 2^K individual
patterns, including their binomial multiplicities. Conditional emission M-steps are
convex five-parameter problems solved by bounded Newton updates with a checked box
optimality gap. The HMM remains nonconvex: 20 fixed EM updates, initialized from the
three-start J006 HMM, for all eight partitions. Each state has its own competition
strength. Select the highest penalized training likelihood over the fixed discrete
structure; preserve null overfitting. A one-state count reference profiles the same
partitions. Priors: Beta(1.5,1.5) on sigmoid fields, quadratic theta penalty 0.05*theta^2,
and Dirichlet(1.5) initial/transition priors. Field bounds [-8,8]. At larger evaluation
rosters, use exact cardinality DP; parameters and roles are unchanged.

Generated comparison: seeds 20261107/08/09; 256 training subjects balanced between
rosters 4/8; complete or predictable prefix stopping; eight future bins and absorbing
termination. Five mechanisms: independent, history-fresh shocks, signed history capacity,
persistent parity shocks plus global competition, and hidden-entity persistent roles.
The first/second/fifth follow the existing J006 generator. The capacity law uses fields
logit(BASE[h]), theta=-4 and parity signs; combined dependence uses fields
logit(BASE[h])+0.8*latent_state*PARITY[h], theta=-4, all-positive capacity signs,
and latent correlation 0.85. The simulator and observation RNGs remain separated.
Both capacity laws use the fixed phi above; they deliberately probe the represented
mechanism, while hidden roles remain a misspecified control. Evaluate 256 fresh complete
subjects at rosters 4/8/16/32 using identical evaluation paths for all methods/policies.

Report all 30 fits / 120 evaluation settings, paired subject-NLL differences against
independent, learned Bernoulli HMM and one-state count model, Monte Carlo errors,
convergence/boundary diagnostics and runtime. These errors condition on fitted models;
no population or significance claim. No tuning after reading results, automatic clinical
advance, original test reopening, real-data access or publishability assertion. Partial
entity outcomes are not yet a training input: only known whole rosters and observed
patient prefixes are supported. Exact one-transition deletion is a separate operation;
missing histories or recurrent entity-wise dropout require a new design.

### J007 completed generated results and solver correction

Initial run `artifacts/synthetic/20261019T214813Z-competition-b41f1107` failed explicitly
on the final hidden-persistent/adaptive setting. At theta=0, a coupled Newton direction
could point out of the feasible box even though its gradient pointed inward. Feasible
step length then stayed zero. The correction re-solves the local Newton system after
activating outward-pointing boundary coordinates; a fixed generated regression verifies
the case. Bounds, priors, seeds, partitions, iteration budgets and gap tolerance stayed
unchanged. The failed artifact remains; the full fixed benchmark was rerun.

Run `artifacts/synthetic/20261019T215056Z-competition-e3237311` completed all 30 fits and
120 evaluations. Source/config/output hashes were verified before adding the conditional
forecast sampler. At unseen roster size 32, combined minus reference subject NLL, averaged
over three seeds and the two stopping policies, is:

| Generated mechanism | Independent | Product-emission HMM | One-state count |
| --- | ---: | ---: | ---: |
| Combined dependence | -12.835285 | -1.576402 | -11.423882 |
| Signed capacity | -1.907741 | -1.852041 | +0.112424 |
| History-fresh shocks | -6.594508 | +0.046553 | -6.611075 |
| Hidden persistent roles | -0.167084 | +0.051898 | -0.170290 |
| Independent | +0.383853 | +0.031478 | +0.379780 |

In the deliberately represented combined law, both isolated-component references lose
in all 24 evaluation cells. The fitted partition is all-positive in all six fits, with
theta approximately -3.70 to -4.74. Signed-capacity fits select the specified parity
partition in all six settings, but the simpler count-only model wins 23/24 cells.
Null and pure-shock controls preserve the added-model-cost failure. Across all 120 cells,
the combined model beats the product HMM in 65 and loses in 55; averaging over these
arbitrary mechanisms is not a population claim. No selected theta hits its -8 bound.

All inner convex mean-Q box gaps are <=2e-7 (maximum 1.9997355e-7). Outer EM is neither
globally certified nor always converged: the selected capacity fits still improve by
0.00509–0.03193 in their last iteration; the combined fits improve by at most 0.000002.
The fixed 20-update budget was not increased after inspection. Runtime: 6.22 s for the
product HMM, 6.14 s for count-only, 25.98 additional s for combined fitting after its
HMM warm start (about 32.20 s including that start). Generation/evaluation are excluded.
Paired Monte Carlo errors condition on fitted models and omit training/selection uncertainty.

`competition.forecast` now samples conditional future trajectories from a fully observed
roster prefix using only its filtered latent posterior. Future termination and recurrence
are sampled jointly; terminated entities stay inactive. Tests compare its one-step joint
law with independent exhaustive enumeration and check absorption, seeding and resource
bounds. This is Monte Carlo forecasting, not an exact-query solver or a missing-history
clinical adapter. The positive mechanism result supports more research, not novelty,
clinical usefulness, SOTA performance or a publication claim. Correlated-emission HMMs
and finite-population count models are established prior work (docs/02).

### J008 exact missing-history inference diagnostic (fixed before implementation)

A separate algorithmic correctness screen, not a refit or an attempt to improve J007's
results. Fix the full roster and its initial history. A known subset is observed for
its whole prefix; up to eight other entities' subsequent events, termination and
histories are unobserved. Initial histories and the number of missing entities must be
known. No reappearing labeled identities, unknown roster, hidden initial history,
informative observation selection or clinical extraction is covered.

For each omitted entity, the sufficient dynamic state is one of four two-bit histories
or absorbed/dead. Exact labeled filtering has 2*5^B latent configurations. Symmetry
permits a histogram state (n0,n1,n2,n3,ndead) and the common two-state latent variable,
with 2*choose(B+4,4) states. For each group, enumerate counts of no-event, recurrence
and termination, including their multinomial multiplicities. Combine these with observed
outcomes, use the full-survivor-roster count normalizer, then sum into next histograms.
This is exact aggregation of a known finite-state model, not a claimed new theorem.

Verify against exhaustive full labeled recurrent paths for one observed/two omitted
entities over three bins; check whole-prefix normalization, exact full-observation
reduction, zero-competition marginal consistency, terminal absorption, permutation,
conditional next-observation probabilities, model/input/resource validation. An explicit
incorrect control deletes omitted entities and changes population size. Fixed model
checks: independent/no-competition, history-dependent signed competition, and latent
plus competition, without fitting or post-result tuning. Record all path probabilities
and total-variation differences. Separately measure filter state/term counts and runtime
for B=0/1/2/4/8 at observed roster 1/4/16 and eight steps using fixed generated prefixes.
Unknown entity histories are summed out, never filled using simulator truth. The first
version is exact inference only; learning from partially observed entities is not yet
implemented. Missingness assumptions and novelty remain separate research obligations.

### J008 completed exactness and resource findings

`make hidden-history-audit` completed at
`artifacts/synthetic/20261019T220351Z-hidden-history-e07e31ab`, with source/output hashes
verified. All three fixed models agree with exhaustive labeled three-entity path sums
to maximum absolute probability error 2.23e-16. The tests also compare the full posterior
over hidden histograms and common latent state, not only a scalar likelihood. Conditional
next-observation probabilities normalize, full observation reduces to J007, and the
zero-competition model agrees with exact whole-entity deletion.

For the three-bin observed-path distribution, incorrectly changing the population size
instead of marginalizing has total variation 0.0550154 (signed competition) and 0.0135058
(combined dependence), versus numerical zero in the independent control. These are
known-model correctness differences, not learned predictive gains or clinical effects.

The exact aggregation follows because, conditional on current history and common state,
entity labels do not affect the law. Every labeled configuration with the same history
histogram therefore has the same probabilities of reaching each next histogram together
with the specified observed outcomes. Summing multinomially many assignments is exact;
it does not require filling hidden histories with their true simulated values or assuming
that hidden histories are independent. Absorbed entities occupy the fifth histogram bin.
At each step, the full surviving population enters the count normalizer before summation.

For B missing entities, the stored history states number choose(B+4,4), but the transition
terms number choose(B+12,12). The latter follows from the generating function: each of
four live history groups contributes three outcome counts, and the already-dead count
contributes one. State compression does not remove high-degree transition cost. At B=8,
495 history states replace 390625 labeled states (both have two common latent states),
but 125970 transition terms remain. The cached plan uses 5043750 bytes; this excludes
temporary working arrays and is not a peak-memory bound. Cold plan construction took
0.910 s; eight-step filtering took 0.719–0.737 s at observed sizes 1/4/16 on this Mac.
The implementation explicitly caps B at eight and total population at 128.

The first audit's plan timer could include an existing B=2 cache entry. The final run
clears the cache before each timed construction, and checks source stability before
marking completion. The probability results did not change. The general aggregation
and filtering ideas have close prior art (docs/02); retain this as a verified reference.
No missing-data learner, unknown-roster estimator, reappearing-identity algorithm,
clinical input adapter or publication-ready contribution is implemented by this audit.

### J009 missing-history learning screen (fixed before implementation/results)

Implement exact smoothing and MAP-EM for J007's fixed all-positive count partition,
using J008's histogram transitions. This is a strong reference learner built from
known EM/lifted-inference ideas, not a claimed new algorithm. Expected full-roster
emission statistics, terminal counts and latent transitions must come from the posterior
conditioned only on observed paths and supplied initial histories. Missing realized
outcomes and latent simulator states cannot enter fitting. Certify each convex emission
M-step with the existing 2e-7 mean-Q box gap; retain nonconvex/fixed-iteration limitations.
Validate smoothing and Fisher score identities against enumeration/finite differences,
plus monotone observed-data MAP objectives and full-observation reduction.

Fixed screen: seeds 20261111/12/13, 128 training subjects balanced between actual rosters
4/8, eight bins, either all entities observed or two permanently hidden after known
initial histories. Evaluate 128 new subjects at actual rosters 4/8/16, for both complete
and two-hidden inputs, reusing unchanged fitted models. Independent simulation seeds
separate training/evaluation; the hidden-subset choice is fixed by entity permutation
and independent of outcomes. This is controlled synthetic masking, not a claim about
clinical missingness. No original clinical validation/test is used.

Five generated laws: independent, fresh history-role shocks, global count competition,
common persistent state plus global count competition, and persistent hidden-entity roles.
Independent/competition/combined use J008's fixed numeric model factory (competition
uses the first state's fields in both states and all-positive signs); fresh/hidden-role
controls use J006's generator. The capacity and combined laws deliberately belong to
the candidate's family; hidden entity roles do not. No generated truth parameters enter
initialization. Known initial two-bit histories are supplied for the full roster.

References: three-start product-emission HMM; correctly marginalized one-state count
model; correctly marginalized two-state count model; and an explicitly naive two-state
control trained as if omitted entities did not exist, then deployed on the supplied
actual roster. For no missing training entities, correct and naive fits should agree.
The naive control is not presented as a strong missing-data method. All count fits use
the same fixed partition, bounds, priors and 20 EM updates, initialized from observed
reference fits. Terminal probabilities are learned too. Report all 30 fitting settings
and 180 evaluation cells, paired subject losses/Monte Carlo errors, fit diagnostics and
runtime. Errors condition on fitted models, not training/selection uncertainty. Preserve
null/misspecified losses, incomplete convergence and any solver failure. No grid tuning,
clinical advancement or novelty conclusion follows automatically.

### J009 completed generated learning results

Run `artifacts/synthetic/20261019T220942Z-hidden-learning-182f31f0` completed all 30
fitting settings / 180 evaluation cells. Source/config/output hashes were verified.
The new sparse forward-backward calculation produces posterior expected count-emission
features, survivor contexts, latent transitions and terminal/exposure counts. These
drive exact convex emission M-steps and ordinary MAP probability updates. Expected
statistics match exhaustive labeled histories; Fisher score identities match observed
likelihood finite differences. No hidden realized future outcomes enter this design.

At unseen roster size 16, after training with two hidden entities, mean subject-NLL
differences (combined minus reference) over the three fixed seeds are:

| Law | Evaluation hidden | Product HMM | Correct count-only | Naive deleted training |
| --- | ---: | ---: | ---: | ---: |
| Independent | 0 | +0.035448 | +0.177065 | +0.007328 |
| Independent | 2 | +0.034227 | +0.152326 | +0.006488 |
| History-fresh shock | 0 | +0.061137 | -1.839726 | +0.009746 |
| History-fresh shock | 2 | +0.051965 | -1.473102 | +0.004838 |
| Global capacity | 0 | -1.698916 | +0.160148 | -0.427967 |
| Global capacity | 2 | -1.105696 | +0.101263 | -0.243861 |
| Combined | 0 | -1.657722 | -1.126155 | -0.346249 |
| Combined | 2 | -1.135480 | -0.853635 | -0.230105 |
| Hidden persistent roles | 0 | +0.099332 | -0.088500 | +0.028672 |
| Hidden persistent roles | 2 | +0.064247 | -0.089123 | +0.018502 |

All settings remain in the artifact, including training without missing entities and
evaluation at sizes 4/8. With no missing training entities, combined and naive fits'
mean losses agree in all 90 evaluations (largest absolute difference 2.67e-15), as
expected from identical objectives/initializations. With two hidden training entities,
correct combined learning beats naive learning in all 18 global-capacity cells and
16/18 combined cells, but loses all 18 independent cells and 16/18 hidden-role cells.
Against the correctly marginalized one-state count reference, it wins 16/18 combined
cells but only 3/18 global-capacity cells. The simpler product HMM is stronger in most
independent, fresh-shock and hidden-role controls. Preserve those complexity costs.

Inner convex gaps are <=2e-7 (combined maximum 1.96807e-7; count-only 1.99095e-7).
Observed-data MAP objectives increase to rounding; the smallest count-only increment
is -9.1e-13. Fixed 20-step outer EM is not generally converged: combined last increments
range 0.00000343–0.0742538, and count-only reaches 0.0301437. No iteration budget was
increased after seeing results. Estimated theta ranges are [-5.89219,0] (combined) and
[-4.86417,0] (count-only), with no lower-bound saturation.

Total fitting time across 30 settings: product HMM 3.805 s; shared design construction
2.169 s; combined EM 16.967 additional s; count-only EM 15.265 additional s; naive
combined 1.814 additional s. The latter three use observed-reference initialization;
these are not independent end-to-end timings, and exclude generation/evaluation.
All comparisons are generated conditional-law checks, not population significance,
identification from real data, a new EM theorem or an advancement gate. The capability
now supports learning with partial histories; correlated-emission/set-process references
remain necessary before claiming a methods-paper contribution.

### J010 prior-family containment audit (specified before implementation)

The closest-reference search found Sharghi et al. (ECCV 2018) generalized DPPs:
P(S) proportional to pi[|S|] det(L_S), with cardinality-weighted elementary symmetric
polynomial normalization and a sequential extension. For J009's all-positive partition,
choose diagonal L_ii=exp(b[h_i]) and log pi[k]=theta*(k-K/2)^2/max(K,1). This is exactly
the current count emission, not merely an approximation. Its identical emissions imply
identical conditional recurrent prefix laws and hidden-history marginal likelihoods
when terminal/latent transitions are held fixed. Therefore an ordinary-DPP-only fitting
comparison would not test the closest known family and cannot support architecture novelty.

First implement and verify this containment, together with a non-diagonal history-shared
GDPP probability reference. Use L=diag(exp(b[h]))+U R R' U', with U the four-history
membership matrix, and cardinality weights as above. Compute selected minors with the
matrix determinant lemma and normalizers with the repeated diagonal eigenvalues plus
a <=4-dimensional block. This is an algebraic reduction of a known family, not a new
DPP normalization theorem or a claim about all DPPs. No fitting comparison is promoted
before this reference and the scope of prior overlap are correct.

Fixed generated audit: seeds 20261114/15/16; sizes 0/1/4/8/16/64/128 for diagonal
count/GDPP equivalence, with direct subset enumeration at sizes <=8 and dense-kernel
checks for non-diagonal history kernels. Verify complete recurrent scores, prefix
normalization, unknown terminal events and two-hidden-entity likelihoods. Include a
precise ordinary-DPP covariance diagnostic: an explicitly permutation-invariant real
marginal kernel has off-diagonal magnitude at most 1/K and hence covariance >=-1/K^2.
Do not extend this restriction to arbitrary kernels, mixtures with non-invariant
components, k-DPPs, cardinality-weighted GDPPs or all repulsive models. A fixed-cardinality
uniform law supplies the counterexample to such overgeneralization. This audit trains
no new model, uses no clinical inputs, and does not claim the broader GDPP has been
fit or compared with J009. A full GDPP learner remains a separate implementation task.

J010 completed at `artifacts/synthetic/20261020T162051Z-gdpp-containment-26de8e7f`:
21 static cases, two recurrent cases and four covariance counterexamples. Maximum
diagonal count/GDPP log-probability error was 2.85e-14; the non-diagonal grouped
reduction agreed with dense kernels to 8.53e-14. Both recurrent laws normalized over
3375 full paths, with two-hidden-entity marginal error <=4.17e-17. Source/output hashes
were verified before further source changes. This confirms prior containment, not a
new method or a learned non-diagonal GDPP comparison.

### J011 factored exact hidden-history filtering (specified before implementation)

The unsigned J009 model permits a more focused computational question. Can exact
filtering avoid enumerating the J008 `choose(B+12,12)` compound transition terms?
Retain the identical probability law, initial full-roster requirement, four two-bit
histories, two shared latent states and independent terminal probabilities. No new
clinical model, learning experiment or missingness-identification claim is introduced.

Proposed factorization: first thin the four history counts independently for terminal
events, then divide by the survivor-context count-tilt normalizer. For each surviving
total and previous-last-bit group size, contract the two binomial-convolution matrices
with the survivor posterior; finally apply the cardinality tilt, which depends only
on the next histogram's total number of events and the observed events. Using product
Bernoulli probabilities instead of unnormalized odds keeps the contractions scaled.
Compute count-tilt expectations for all survivor contexts by a layered polynomial
recurrence, extending the observed entities' Poisson-binomial coefficients. Carry
observed labeled-outcome and terminal log probabilities outside the contraction.

The intended implementation uses O((B+1)^4) dense working arrays and O(B^5) contractions
for fixed history dimension and observed-roster bound, plus layered normalizer work
O(choose(B+4,4)*(B+K_observed)). These are proposed algebraic operation counts, not yet
measured runtime/peak-memory claims. Binomial transforms, variable elimination and
lifted filtering are established techniques; a model-specific rearrangement alone
does not establish a publishable new inference method.

Fixed generated validation: models independent, unsigned capacity and combined,
seeds 20261117/18/19, observed roster four, horizon eight. Compare the full likelihood,
per-step posterior and next-state law with unchanged sparse J008 at hidden counts
0/1/2/4/8; run factored-only normalization checks at 12/16/24. Generate complete paths
once per setting but pass only observed paths and initial hidden histories to filtering.
Measure cold plan construction and filtering separately, retaining all timings and
errors. Sparse reference above eight is deliberately not allocated; extrapolated term
counts are not runtime measurements. Check complete-observation/independent reductions,
absorption, unknown future terminal events, permutation and extreme allowed parameters.
No tuning, fitting or score-superiority claim follows. A backward/learning operator,
non-diagonal GDPP version and clinical recurrent extractor remain separate work.

J011 completed at `artifacts/synthetic/20261020T162510Z-factored-history-a60c0ea3`.
All 72 fixed cases passed. In the 45 sparse-reference cases, maximum full log-likelihood
error was 3.56e-15, increment error 1.78e-15, posterior error 3.89e-16 and next-state
error 2.36e-16. Fully absorbed observed-roster checks, which sum over subsequent hidden
outcomes, had maximum conditional log-likelihood error 4.45e-16.

| Hidden entities | Histogram states | Sparse compound terms | Factored preparation / filtering, median seconds | Sparse preparation / filtering, median seconds |
| --- | ---: | ---: | ---: | ---: |
| 0 | 1 | 1 | 0.000435 / 0.001579 | 0.000030 / 0.001521 |
| 1 | 5 | 13 | 0.000189 / 0.001242 | 0.000132 / 0.001725 |
| 2 | 15 | 91 | 0.000276 / 0.001718 | 0.000724 / 0.002260 |
| 4 | 70 | 1820 | 0.000448 / 0.003189 | 0.012325 / 0.010117 |
| 8 | 495 | 125970 | 0.001159 / 0.009332 | 0.887681 / 0.722802 |
| 12 | 1820 | 2704156 | 0.002467 / 0.022175 | not allocated |
| 16 | 4845 | 30421755 | 0.004713 / 0.045655 | not allocated |
| 24 | 20475 | 1251677700 | 0.013957 / 0.201548 | not allocated |

Medians pool the nine fixed mechanism/seed settings at each size. These are single-run
local CPU observations, not a broad hardware benchmark. At B=8 the ratio of median
filter times is about 77; zero-missing filtering is slightly slower. B=24 factored
filtering completed without allocating the 1.25 billion compound terms; that number
is a combinatorial count, not an observed sparse runtime or memory requirement. One
dense two-latent array at B=24 occupies 6250000 bytes; several arrays, cached plans,
normalizer layers and retained posteriors coexist, so this is not peak memory.

Exactness argument: write the normalized unsigned count law as a product Bernoulli
law times exp(phi(total events)) divided by its product-law expectation. Conditional
on each old histogram, independent terminal outcomes give four binomial thinning
operators. After thinning, the normalizing expectation depends only on surviving
history counts and observed survivors. Within the even-last-bit group, the event-count
polynomial is a product of two binomial polynomials, and likewise within the odd group.
Those two counts uniquely specify the next four-history histogram. Thus summing the
survivor posterior with the two polynomial matrices enumerates exactly the same
labeled assignments and multiplicities as J008, without materializing its compound
edges. The final total-event tilt and observed labeled-outcome probabilities restore
the original conditional law. Shared latent-state transitions are unchanged.

This is an implemented computational improvement over the existing sparse reference,
not evidence of a new distribution, a general GDPP solver or superiority to all exact
inference algorithms. Four fixed histories and unsigned cardinality are essential to
the present factorization. Backward inference, learning at larger hidden populations
and comparison against optimized variable-elimination/particle references are the next
local questions. Clinical roster/coverage assumptions are still unverified.

### J012 factored backward inference and likelihood derivatives (before implementation)

Extend J011 without changing its probability law or inspecting any clinical inputs.
Transpose each thinning/convolution contraction for backward messages. Differentiate
the normalized count-tilt expectation and convolution factors analytically, including
observed Bernoulli terms, independent terminal logits, initial logits and transition
row logits. Keep full initial histories known, unsigned count potential, four history
types, at most 24 hidden and 128 total entities, horizon eight. This supplies exact
observed-likelihood gradients for future learning, not a new backpropagation theorem.

First verify forward/transpose inner products on supported histograms, posterior
normalization and sparse J009 sufficient-statistic equivalence for hidden counts
0/1/2/4 (total roster <=8). Validate every model-parameter derivative against centered
finite differences on small cases, with terminal/state logits perturbed in their
unconstrained coordinates. Include empty/variable prefixes, absorption, parameter
limits and entity permutation. At hidden counts 8/16/24, check fixed directional
derivatives against J011 forward filtering. Do not expand the old sparse reference
allocation limits to create a timing baseline.

Fixed audit: seeds 20261120/21/22; independent, unsigned-capacity and combined models;
four observed entities, horizon eight; hidden counts 0/2/4/8/16/24. Time preparation,
forward filtering and forward/backward-gradient computation separately. Directions
are fixed before outcomes, with zero theta perturbation in the independent model.
Use centered epsilon 1e-5 and record raw absolute/relative derivative errors; tolerance
2e-6 + 2e-6*abs(reference). The 27 settings within J009's supported size also compare
exact parameter gradients and latent expected counts to sparse inference.
No optimization or prediction-performance claim follows from this derivative audit.
Parameter fitting and stronger inference baselines remain separate fixed experiments.

J012 completed all 54 fixed cases at
`artifacts/synthetic/20261020T163839Z-factored-gradient-71b6137e`.
Maximum directional finite-difference error was 3.92e-10 and smoothed normalization
error 1.34e-15. In the 27 sparse-reference cases, emission-gradient error was at most
1.46e-14, terminal-logit error 1.16e-14 and latent-count error 4.45e-15. At hidden
counts 0/2/4/8/16/24, median full forward/backward-gradient seconds were
0.002876/0.005846/0.012054/0.036437/0.186676/0.846819, respectively. Preparation,
forward-only times and every case are retained. Source/output hashes were verified
before the next implementation. This establishes a runnable gradient computation,
not a fitted large-hidden-population model or a new differentiation result.

### J013 conditioned particle filtering reference (specified, subsequently suspended)

Status after the user's 2026-10-20 task-first steering: not implemented or run.
Keep this specification as historical work; it is not the next active experiment.
Resume only if a supported data task makes this computational comparison necessary.

Compare the exact factored filter with a standard sequential importance/resampling
reference using the identical model and observations. Propose the shared latent state
and hidden terminal events from their prior transitions, then sample hidden recurrent
events conditional on the observed events using the exact count-law polynomial.
Weight by the observed terminal probability and the ratio of conditional-hidden to
full-roster count normalizers, including observed Bernoulli factors. This is adapted
for hidden recurrences only; it is not the fully adapted proposal for all latent
variables. Use systematic resampling at every step. Do not use brute-force matching
of generated observations as the main particle reference.

Implement vectorized per-particle polynomial recurrences and backward sampling, with
no dense histogram enumeration. Verify the conditional distribution/weights against
small exact enumeration, non-reactivation, empty/full observation reductions and
seeded repeatability. Monte Carlo checks do not prove unbiasedness; use the standard
importance-weight factorization, and do not call mean log-likelihood unbiased.

Fixed generated comparison: the three J011 model settings, seeds 20261123/24/25,
four observed entities, horizon eight and hidden counts 8/16/24. For each of the 27
paths, run particle counts 32/128/512/2048 with eight fixed independent replicate
seeds. Compare each run to the exact J011 likelihood and final histogram/latent
posterior; retain log-likelihood error, posterior total variation, hidden alive-count
mean error, latent-state probability error, ESS and runtime. Exact preparation and
filtering are separate. Particle counts and repetitions are not tuned after results.
No formal accuracy threshold, new likelihood model, training experiment or publication
gate follows. Approximation cost/accuracy and exact-filter limitations all stay visible.

### 2026-10-20 task-first research priority

The user retains the machine-learning methods-paper objective and asks that real UCSF
data needs drive the method, rather than continued mathematical or runtime extensions.
This instruction supersedes the historical next-step plans in J001-J013. Keep their
generated references and negative results, finish verification of completed code, and
pause J013 implementation. No new clinical experiment is selected by this change.

**Candidate question, not a frozen clinical protocol:** given the histories available
at a prediction cutoff for a defined set of the same patient's linked orders, does
modeling their dependence improve prediction of subsequent documented qualifying
administration events over modeling each order separately? The set must be defined
using information available at the cutoff. Do not select orders because they eventually
receive doses, complete follow-up or remain active. This target concerns recorded events
under the reviewed action and retrospective-documentation rules, not dose appropriateness,
clinical need, missed scheduled doses, resource competition or causal effects.

The code and approved operational findings support different levels of evidence:

| Existing evidence | Permitted implication | Remaining task requirement |
| --- | --- | --- |
| Reviewed direct order/administration linkage; repeated administrations recorded | A linked recurrent-event task is worth assessing | Complete retained event paths for a defined selection, including mismatches and retrospective exclusions |
| Patient identities and reviewed within-patient common clock | Within-patient grouping is a candidate | A cutoff-defined set and compatible independent observation coverage; no unverified cross-patient calendar alignment |
| Separate directly linked observation source | Order end need not substitute for observation end | Determine whether its existing reviewed coverage can support common windows across the selected orders |
| Existing one-time first-execution cohort and histories capped at 24 events / 24 hours | Reproduce prior studies and describe retained histories | These artifacts cannot certify recurrent coverage or a complete concurrent roster |
| J008-J012 known-roster, permanently hidden-entity simulations | Check the implemented probability calculations | Neither that missingness mechanism nor an actual capacity constraint has been established in UCSF data |

Local next work is to specify the smallest recurrent cohort/coverage contract using
only the already reviewed sources, then implement generated fixtures and checks for
that contract. Dynamic order entry, terminal outcomes and observation end must remain
distinct. When observation ends, unobserved future events are unknown, not zeros.
The old extractor's repeated-administration exclusion stays unchanged. A complete
selected-order extract does not imply a complete patient-wide roster.

Before selecting a modeling experiment, a bounded server-side training-only feasibility
check will be needed to establish whether the required linked paths and common observation
windows can actually be formed. Its implementation, physical access plan and resource
bounds are not yet prepared. Do not create an extra audit of capped histories as a proxy
for this requirement, or repeat independent source prefixes. Any new full-source pass
would need its actual cost and scope specified separately. No new source mapping,
format conversion, lab semantics or clinical adjudication is assumed.

If the task is supported, the methodological comparison should isolate the benefit of
cross-order information: a marginal recurrent-event reference, a parameter-matched shared
model without cross-order context, and an appropriate established joint sequence/set
reference. Match information, compute and selection budgets; use patient splits and
predeclare one main predictive target/score after coverage is known but before outcome
comparisons. Evaluate uncertainty on that target and inspect dependence on set size and
observation length as prespecified secondary analyses. Mechanism simulations then test
the specific claimed benefit and failure modes. Runtime becomes an engineering constraint
unless it is demonstrably the task's bottleneck.

A real-data improvement alone would not establish a methods contribution. The paper
would need a reusable method addressing a demonstrated failure of appropriate references,
with ablations and limits, and broader reproducibility evidence appropriate to the claim.
Conversely, the existing synthetic inference improvement is not evidence that this UCSF
task needs hidden-entity marginalization. If the task or the reference failure is absent,
preserve that finding and reassess within the same sources rather than adding complexity.
All earlier clinical negatives and sealed tests remain unchanged.

### T001 recurrent task support audit (specified before implementation)

Purpose: establish whether the reviewed sources can form linked recurrent histories
and joint observation windows for a fixed subset of original training patients.
This is a data-task audit, with no fitting, prediction comparison or paper pass rule.
The first-execution extractor is not modified. No schedule, drug identity, dose,
diagnosis, laboratory or new terminal-cause semantics are needed.

Use only identities/splits from the existing verified cohort to select up to 32
original training patients by a fixed salted identity hash. This is an exploratory
subset of the previous selected population, not a new representative adult inpatient
cohort. For those patients retrieve all mapped orders, independently of subsequent
administrations. Confirm all rows for their selected order keys in a second order
pass, including rows with a different patient. Retrieve all linked administration
rows before action/patient/time filtering and all directly linked observation rows.
Selected-patient order completeness requires full declared-source coverage; an old
64-order coherent sample or capped history artifact cannot provide it.

Per patient, anchor at the first 64 distinct valid order-availability times. This
bounded anchor domain is fixed before outcomes; it is not an early-success sample.
At each anchor include orders occurring within the previous 24 hours and already
available, excluding only terminals already known at that cutoff. Do not add future
orders or remove orders using future observation length, future administrations or
future terminal status. These are recent known orders, not a claim of all clinically
active medication orders. An oversized roster is unresolved, never silently shortened.
Malformed/ambiguous order creation prevents certifying that patient's roster.

Retain every valid repeated qualifying administration. Reuse the reviewed action,
clock, encounter and retrospective-documentation policies. Duplicate identities,
patient mismatches, unknown documentation classes, invalid temporal order and
execution/terminal ties invalidate affected paths; they do not become negative labels.
Retrospective data-quality exclusions are reported separately and are not a prospective
eligibility claim. Rejection of one member invalidates the joint window; never improve
coverage by dropping that member. Simultaneous distinct administration identities
remain tied events rather than an invented ordering.

For a diagnostic four-hour horizon, joint ascertainment ends at the earliest linked
observation end across the cutoff-defined roster. Keep this endpoint out of input
features. Each order also has its own reviewed terminal endpoint, distinct from
observation end. A completed terminal path can have a known count despite another
order's censoring; a joint fixed-horizon count vector is known only when every member
is resolved. Preserve observed prefix counts and mark remaining counts unknown.
Occurrence before a boundary with availability after it cannot silently supply a zero;
flag the affected window as unresolved under this audited target. The four-hour horizon
is a support diagnostic, not a selected prediction endpoint for a future paper.

Report private aggregate structural/support counts, including repeated paths, roster
sizes, candidate versus invalid/partial/fully ascertained windows, identity exclusions,
and physical-read/retention limits. No row, patient identifier, feature table or model
is persisted. A complete run can show lack of support in this selected domain, not
population absence or statistical sufficiency. No automatic model run follows.

Physical access is a separately declared full-source operation: two order passes,
one administration pass and one observation pass, with all scans/bytes and retained
rows charged. Enforce source stability, explicit limits and a clean-commit Slurm entry
before real execution. The in-memory contract, raw-source adapter, private worker,
Slurm planner/submitter and categorical result review are now implemented, with 44
focused generated tests passing. The adapter runs all four declared passes and
compares complete file-content hashes before/after; the in-memory completeness flag
alone is not a coverage proof. Logical charged file reads (including both hash passes)
and full decoded row-group bytes each have a 64 GiB total ceiling. Selected retention
is capped at 20,000 order rows, 200,000 administration rows and 20,000 observation rows.
Worker limits are 2 CPUs, 4096 MiB and 1200 seconds, with a 22-minute Slurm allocation.
These ceilings are not measured UCSF costs. An oversized or changed source stops the
job, with no partial support claim, automatic retry or automatic budget expansion.
No row artifact or model-ready recurrent cohort is produced, and no real job has run.
