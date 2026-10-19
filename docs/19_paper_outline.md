# R001 negative/mixed development report and manuscript draft

Status: **R001 completed; qualitative results and conclusions recorded**. Not a
submission-ready paper: clinical numerical tables and institutional details remain on
authorized UCSF storage and were not inspected by the Mac agent. The original intention/execution/physiology architecture
proposal stopped and is not being revived. Existing negative and mixed findings are
retained below; no synthetic result substitutes for clinical evidence.

Working title: **Model-selection objectives for first-execution probabilities in a
fixed clinical workflow cohort: a nested development evaluation**.

## Qualitative abstract draft

Background: model selection by the joint likelihood of time and terminal cause need
not minimize first-execution probability error at operational horizons. That distinction
is established statistical background, not our claimed methodological contribution.
Objective: compare two fixed selection policies on one shared candidate bank, and
characterize what remains unresolved when censoring obscures horizon outcomes.
Methods: original training patients, nested patient cross-validation, two small
competing-risk model families, four retained-history encodings, four equally weighted
horizons, coherent finite-sample completion bounds and generated mechanism checks.
Results: The operator-reported completed clinical comparison did not demonstrate an
advantage for conservative upper-bound selection. Across the three fixed fold seeds,
the primary finite-sample completion comparison was unresolved, adverse to upper-bound
selection, and identical between policies, respectively. Order-weighted sensitivity
preserved these directions; horizon-specific directions reversed between the first two
seeds. Generated mechanisms also included harmful selections and unresolved comparisons.
Conclusion: This fixed candidate bank provides no basis for advancing the upper-bound
selection policy. The analysis illustrates limited, data-dependent differences between
selection objectives, with substantial limits on interpretation. Completion bounds do
not establish population significance, and overlapping development folds do not provide
independent clinical confirmation. No novel scoring theory or clinical-use claim is made.
Quantitative effect magnitudes must come from the existing authorized private tables;
this qualitative abstract is not a substitute for a complete empirical manuscript.

## Introduction draft

Clinical orders can terminate through execution or competing events, and observation
may end before any terminal event. Historical workflow can predict recorded outcomes,
but improving a joint event-time likelihood does not by itself establish better
first-execution probabilities at particular time horizons. The choice of evaluation
objective therefore deserves explicit empirical treatment. Healthcare-process signal,
competing-risk probability scoring and censoring-related ranking issues are already
studied (primary-source comparison in docs/02).

This study asks a narrower, practical question within a fixed cohort: when the same
candidate models are available, does choosing by joint likelihood or by a conservative
execution-error bound change patient-held-out selections and their probability errors?
The study's possible contribution is a reproducible evaluation with explicit failure
conditions. It is not a new survival model, a new proper score or a claim that a
particular event representation generally improves clinical prediction.

## Methods draft

The eligible population is the existing bounded first-event cohort with reviewed
order/administration occurrence and availability semantics. Eligibility, competing
terminal causes, linkage and retrospective exclusions are inherited without alteration.
Inputs are capped retained histories, not complete longitudinal patient records.
No laboratory, diagnosis, physiology or new source roles enter the analysis. Original
patient splits remain fixed; only the original training partition enters this study.
Original validation was already used in E003, and test remains sealed. Selection of
this research question followed development findings, so nested CV here is not an
independent confirmation of the overall research strategy.

We compare two selection policies using eight fixed candidates: proportional-hazard
piecewise exponential and shallow likelihood-tree heads crossed with intercept, count,
pooled-recency and typed-recency inputs. Both policies use the same inner out-of-fold
candidate predictions. One minimizes equal-patient joint NLL; the other minimizes an
upper completion bound on equal-horizon execution squared error. Three prespecified
patient fold seeds each use five outer and three inner folds. Preprocessing, tree
partitions and fitting use training patients only; outer patients cannot influence
inner selection. All candidate and selected-policy outer results are retained.

For early-censored orders, execution indicators after censoring remain unknown. We
complete only monotone zero-to-one first-execution trajectories consistent with the
observations and use a shared trajectory when comparing predictions. Minimum and
maximum paired errors give finite-sample bounds. The primary contrast averages equally
over patients and the fixed 1/4/12/24-hour horizons. No independent-censoring assumption
is imposed for these bounds; fitted models retain their assumptions. Conditional
patient bootstrap percentiles describe endpoint variability with fitted models held
fixed and omit fitting/selection uncertainty. They are not population confidence
intervals for the full pipeline. All tuning, tie rules, resource limits and stopping
rules are recorded in docs/11 and the versioned configuration.

Generated mechanism experiments distinguish execution and competing-event signal,
nonlinearity, time-varying effects and a null. Known full outcomes permit checks of
completion bounds under administrative-only and feature-dependent censoring. Simulation
findings explain behavior under their constructed mechanisms and cannot validate the
clinical data or establish clinical performance.

## Evidence and claims ledger

| Claim or question | Evidence currently available | Allowed interpretation |
| --- | --- | --- |
| Multimodal/state representation benefit | Essential point-in-time semantics unavailable; original direction stopped | No clinical representation or physiology claim |
| Dual-clock benefit | E003 fixed validation gate failed | Preserve negative validation result; no post-validation rescue |
| Distinct clock pairing support | A001 retained-training audit lacks the necessary pairing variation | Artifact-scoped infeasibility, not a claim about all clinical documentation |
| Type-specific timing improves pooled timing | W001 primary support condition failed | Negative primary; secondary contrasts remain exploratory |
| One model is best at all horizons | W002 gives mixed comparisons and empirical probability-range diagnostics | No common winner, population calibration or effect magnitude established |
| R001 upper-bound policy improves execution error | Job 39335 complete: unresolved / adverse / identical-policy primary comparisons across fixed seeds | No demonstrated advantage; close this policy comparison, without a population significance claim |
| New score/bounds/model theory | Close prior literature exists; no such contribution established | Present the technique as a transparent evaluation tool |
| Broad clinical utility or external generalization | No independent validation, external cohort, workflow intervention or utility study | Not established; must not appear as an achieved contribution |

## Completed qualitative clinical results

The user returned the automated completion and qualitative summary for UCSF job 39335,
actual source `21762073fe9aff38dfb37d9feddc54e9205fe1fa`, bound to the W001 population
artifacts. The fixed protocol used the original training partition only; original
validation/test were not evaluated. The Mac did not access the clinical artifacts.

The primary contrast is upper-bound selection minus joint-NLL selection, averaging
patients and the four horizons equally. A negative contrast favors upper-bound selection.

| Fixed fold seed | Primary completion comparison | Order-weighted comparison | Joint NLL difference |
| --- | --- | --- | --- |
| 20261020 | Includes zero: unresolved | Includes zero | Lower |
| 20261021 | Entire reported range above zero: adverse in this sample | Above zero | Higher |
| 20261022 | Identical selected models and policy predictions | Identical predictions | Equal |

The first two seeds each differed in a single outer fold's PH pooled/typed timing
selection. All outer-fold choices were drawn from these two PH representations. With
the third seed, both policies chose PH pooled timing in every fold, yielding identical
policy predictions through the shared prediction path. That equality is an operational
identity in this fitted run, not a population equivalence test. The shallow reference
tree was never selected; this does not rank all possible nonlinear survival models.

| Fold seed | 1-hour bounds | 4-hour bounds | 12-hour bounds | 24-hour bounds |
| --- | --- | --- | --- | --- |
| 20261020 | Above zero | Below zero | Includes zero | Includes zero |
| 20261021 | Below zero | Above zero | Above zero | Above zero |
| 20261022 | Includes zero; identical predictions | Same | Same | Same |

These horizon reversals are secondary descriptive findings. They do not authorize
selecting a favorable horizon or seed as a new primary result. Repeated seeds reuse
the same patients and are not independent cohorts. Completion bounds quantify admissible
unobserved labels for the fitted sample; they are not confidence intervals, and no
population significance claim follows from bounds above zero. The qualitative feedback
does not identify effect magnitude or supply private bootstrap endpoint percentiles.
Signs cannot be averaged to reconstruct an overall numerical contrast.

### Generated evidence, separately labeled

The generated 30-case benchmark completed all latent-outcome containment checks, but
correct calculation did not imply that the new selection policy was better. In every
feature-dependent-censoring case/seed comparison, the primary completion range included
zero. In the nonlinear execution scenario under that regime, all fixed seed combinations
had worse known latent outcome error for upper-bound selection. Administrative-only
time-varying scenarios produced identical policy choices. These counterexamples are
retained with the full generated summary in docs/20; they are not pooled with clinical
results or used to supply a clinical effect estimate.

### Private numerical assembly and remaining manuscript work

The completed job produced `paper_tables.md` and `selection_report.json` in its private
output directory. They include actual quantitative aggregates for every candidate,
policy, fold seed and horizon, plus the paired primary comparison, cause-specific NLL,
order-weighting sensitivity and conditional endpoint percentiles. They can be used by
authorized institutional authors without another model fit. Git carries qualitative
findings, code, methods and generated tests; the Mac must not pull those private files.

A submission-ready manuscript would still require actual effect estimates from those
existing tables, a complete cohort/exclusion description, appropriate presentation of
uncertainty, institutional author/governance information, and any required disclosure
review. No approval numbers, numerical effects or unseen plots are invented. Detailed
figures and venue formatting are unfinished. These gaps do not justify another data
scan, a search for a positive model, or reopening original held-out evaluation. The
present deliverable is a reproducible negative/mixed development report with a
qualitative manuscript draft, not a completed submission or an acceptance claim.

## Discussion draft

The main limitation is the scope: one bounded cohort, selected retained histories,
limited representations and a small reference candidate bank. The tree is independently
implemented but not a state-of-the-art method, and model capacities are not matched.
Censoring bounds can be too wide to resolve policy differences. The upper-bound criterion
is not a proper probability score: with all labels unknown it favors .5 regardless of
the true event probability. Conservative upper-bound selection can therefore be harmful;
the generated checks include adverse examples. Fold seeds reuse the same people, and conditional
bootstrap summaries do not cover adaptive direction selection or the full learning
pipeline. Independent clinical confirmation, transportability and utility remain open.

The real comparison now supports closing this selection-policy question under the
predefined stopping rules. It supplies no demonstrated primary advantage for the
upper-bound policy. Its adverse/unresolved/identical pattern does not erase W001's
exploratory workflow information or prove that all prediction from these data is futile.
It does remove a basis for presenting this rule as a superior method. No additional
model-bank search, recalibration, seed/horizon selection or server experiment is scheduled.

The remaining defensible contribution is the documented scope, reproducible comparison
and limits of the proposed choice rule. Existing close literature and the restricted
single-cohort development design constrain novelty and generalization. This is insufficient
to claim a strong new-method paper; it does not establish that a carefully reported
negative evaluation could never be published. Publication feasibility remains unestablished
without full numerical reporting and a specific editorial assessment. The appropriate
current outcome is an honest negative/mixed report, not another automatic direction change.

## Conclusion draft

Within the fixed candidate bank and bounded original-training cohort, replacing joint-NLL
selection with coherent upper execution-error-bound selection did not demonstrate a
primary benefit. One fold seed left the comparison unresolved, another favored NLL
selection throughout the sample completion range, and the third produced identical
policy predictions. These descriptive findings support closing this experiment while
preserving all results and keeping original held-out evaluation sealed. They do not
establish population superiority, equivalence, clinical utility or new methodological novelty.
