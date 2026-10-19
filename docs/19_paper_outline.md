# R001 empirical manuscript working draft

Status: **methods and evidence plan drafted; R001 clinical results pending**. Not a
submission-ready paper. The original intention/execution/physiology architecture
proposal stopped and is not being revived. Existing negative and mixed findings are
retained below; no synthetic result substitutes for clinical evidence.

Working title: **Model-selection objectives for first-execution probabilities in a
fixed clinical workflow cohort: a nested development evaluation**.

## Abstract plan — do not fill in a positive conclusion

Background: model selection by the joint likelihood of time and terminal cause need
not minimize first-execution probability error at operational horizons. That distinction
is established statistical background, not our claimed methodological contribution.
Objective: compare two fixed selection policies on one shared candidate bank, and
characterize what remains unresolved when censoring obscures horizon outcomes.
Methods: original training patients, nested patient cross-validation, two small
competing-risk model families, four retained-history encodings, four equally weighted
horizons, coherent finite-sample completion bounds and generated mechanism checks.
Results: **R001 pending; numerical clinical results must be inserted from authorized
UCSF private tables after completion and institutional disclosure review**.
Conclusion: **pending**. Describe negative, unresolved or mixed findings faithfully;
no “improved clinical decision making”, novel scoring theory or deployment claim.

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
| R001 policy choices differ and improve execution error | Clinical execution pending | No result or conclusion yet |
| New score/bounds/model theory | Close prior literature exists; no such contribution established | Present the technique as a transparent evaluation tool |
| Broad clinical utility or external generalization | No independent validation, external cohort, workflow intervention or utility study | Not established; must not appear as an achieved contribution |

## Results organization and private assembly

Lead with R001's fixed primary paired comparison for all seeds, including unresolved
bounds. Then show every candidate/policy, NLL components, all four horizons, fold choices,
order-weighting sensitivity and conditional endpoint percentiles. Put W001/W002 in the
motivation/development chronology, not as independent supporting replications. Generated
results get a separate section and explicit labels; do not pool their numbers with UCSF.

The real job writes `paper_tables.md` and `selection_report.json` in its private output
directory. They contain actual quantitative aggregates and are intended for authorized
UCSF manuscript work. Git carries the draft, methods and generated tests only. The Mac
agent must not request/pull these private tables or insert unshared values. Detailed
cohort flow, site governance, IRB/disclosure language and semantic evidence must be
completed by authorized institutional authors; no approval numbers are invented.

Planned presentation: candidate/policy table; paired multi-horizon results; all-horizon
sensitivity; selection choices; generated mechanism results; separate provenance and
coverage table. A negative direction is retained, not removed from the abstract after
viewing the results. Figures and final journal/conference formatting remain pending
real quantitative results and a concrete submission target.

## Discussion draft

The main limitation is the scope: one bounded cohort, selected retained histories,
limited representations and a small reference candidate bank. The tree is independently
implemented but not a state-of-the-art method, and model capacities are not matched.
Censoring bounds can be too wide to resolve policy differences. The upper-bound criterion
is not a proper probability score: with all labels unknown it favors .5 regardless of
the true event probability. Conservative upper-bound selection can therefore be harmful; the generated checks
explicitly permit adverse examples. Fold seeds reuse the same people, and conditional
bootstrap summaries do not cover adaptive direction selection or the full learning
pipeline. Independent clinical confirmation, transportability and utility remain open.

If the real comparison supplies no useful distinction, finish a reproducible negative
technical report and close this question. Do not expand models/horizons merely to find
a favorable paper result. Publication feasibility will depend on the actual magnitude,
clarity of the transferable lesson, completeness of reporting and venue assessment;
passing engineering checks is not evidence of publishability.
