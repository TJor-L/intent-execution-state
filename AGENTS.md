# Working agreement

## Project status

The original multimodal/state project stopped on 2026-10-16 because no authoritative
point-in-time semantics were available for laboratory, diagnosis or other richer sources.
The user subsequently authorized a scoped workflow-only continuation using the already
reviewed order/administration occurrence and availability semantics. Do not add new source
roles or physiology claims. Keep test evaluation sealed until the dual-clock design and
validation decision rule are frozen; start with CPU and use at most one GPU only after
the history artifact and CPU controls pass.

E003 completed as a gated negative validation experiment at entry commit `52c49bb`:
minimum unshifted gain and paired uncertainty did not pass. Test remains sealed and
neural/GPU work is not scheduled. Local synthetic diagnostics do not overturn that
decision or authorize post-validation tuning of E003.

The synthetic clock-pairing diagnostic is runnable locally via `make pairing-demo`.
Its joint-time features and controls are experimental and generated-only; they are not
connected to the clinical model runner and do not authorize a new UCSF comparison.

On 2026-10-19 the user requested autonomous local completion up to a genuine server-data
dependency. Continue independent implementation and verification without interim handoffs.
`make pairing-stress` is a separate generated stress check. The `clock-audit` Slurm job
is a bounded, label-free descriptive audit of existing retained training histories;
it is implemented and generated-test verified. The user reported UCSF job 39325 complete
at commit `14b8d69`, including the monitor's artifact verification. Subsequent user
feedback does not support the proposed clock-pairing contrast in the retained training
histories: both event types have coincident clocks at the audit resolution, without
distinct valid pair swaps. This is a scoped artifact finding, not proof that clinical
documentation has no delays or that all single-clock workflow prediction is futile.
Do not schedule the pairing successor on these unchanged artifacts, alter reviewed
time semantics, enlarge history caps or synthesize clinical delays to obtain a contrast.
Actual mapping-policy evidence remains server-local; no restricted counts are tracked.
It does not fit models, open clinical test evaluation, rescan raw sources or authorize
a new comparison. Do not repeat this completed audit on unchanged inputs.

The user then explicitly authorized a change of research direction with the existing
data fixed: no additional/modified source data and no dependency on someone providing
new semantic explanations. W001 is the scoped successor: single-clock retained-history
counts, pooled timing and type-specific timing for the existing first-execution task.
Use only the already reviewed cohort/history artifacts and original training patients;
patient-grouped development CV leaves original validation/test untouched. The design
and fixed development screen are in docs/11 and configs/workflow_cv.yaml. This is an
exploratory information-value study, not a claimed novel architecture or an E003 rerun.
Do not claim independent confirmation after this data-informed pivot. Existing source
roles, semantic exclusions, windows, cap and cohort splits remain unchanged. No further
semantic-review request is a prerequisite for this bounded existing-artifact experiment.
The user reported W001 UCSF job 39332 complete at `9fcdc32`, with artifact verification.
Subsequent qualitative feedback failed the fixed type-specific timing support rule:
typed timing has higher mean loss than pooled timing. Counts improve mean loss over
intercepts, pooled timing over counts, and typed timing over intercepts. These directions
alone do not establish uncertainty, effect size or clinical usefulness. Preserve W001's
negative primary result; do not promote a secondary contrast to a successful primary
or retune to rescue it. The subsequent read-only review at `5836dbc` verified all four
contrasts: pooled timing versus counts and typed timing versus intercept each have a
conditional interval below zero and all folds lower. Counts versus intercept and typed
versus pooled each have an interval including zero and mixed fold directions. Conditional
intervals omit fitting and selection uncertainty; no effect magnitude is established.

W002 is an explicitly post-selection diagnostic of the same frozen W001 models, not a
new model comparison or advancement gate. It verifies the original out-of-fold losses,
adds a direct pooled-versus-intercept descriptive contrast and computes first-execution
probabilities at fixed horizons. Early-censored binary outcomes remain unknown; finite
completion bounds are not confidence intervals or proof of calibration. Original
validation/test outcomes and features stay unread. No fitting, tuning, raw source scan,
source-role expansion or GPU work is scheduled. See docs/11 for the fixed diagnostic
specification and docs/16 for the bounded server entry. The user reported W002 job 39333
complete at `1df3274`, with verified frozen replay and qualitative diagnostics. Pooled
timing versus intercept has lower NLL in all folds and a conditional interval below
zero. Execution-probability errors are mixed across horizons: pooled versus counts is
lower at 1 hour but higher at 4/12/24 hours; pooled versus intercept is lower at 1/4/12
hours but its completion bounds include zero at 24 hours. Typed versus pooled is
higher at all four horizons. These finite-sample directions are not significance tests,
effect-size claims or population rankings. All models' empirical mean risks are below
the outcome-completion range at 1 hour, above at 4 hours and inside at 12/24 hours;
inside does not establish calibration. Preserve both favorable and adverse findings.

W001/W002's specified development analysis is complete; no further UCSF action is
needed for those questions on unchanged inputs. No common winner across the reported
metrics/horizons, clinical usefulness or new architecture contribution is established.
Do not repeat the jobs, select a favorable horizon after seeing results, recalibrate,
refit or reopen original held-out evaluation to rescue this study. Any future experiment
needs a separate question, fixed target and evaluation design. The later R001 authorization
and protocol below supply that separate design; this completion record itself does not.
Generated checks do not supply clinical evidence.

The user next authorized autonomous direction selection, implementation and research
preparation, with the user operating prepared server jobs. R001 is a separate fixed
question: compare joint-NLL versus coherent upper execution-Brier-bound selection on the
same eight-candidate PH/tree bank, using three seeded 5x3 nested patient CV runs within
original training only. See docs/11 and configs/workflow_selection.yaml. Implementation
and generated verification were completed locally. The user reported R001 job 39335
complete at `2176207`, with artifact verification and qualitative feedback. Preserve all
prior negatives; this is exploratory development, not independent confirmation, a new
score, or a claim of publishability. Keep every seed/horizon, no favorable-result search.
The fixed R001 comparison is complete; no additional server job is scheduled. No new
semantics, raw scan, GPU, data transfer or original validation/test evaluation is authorized.
The user's earlier explicit push/run/feedback instruction authorizes the
verified milestone release and pinned job handoff; it does not authorize data publication.

R001's qualitative primary comparison, upper_brier minus joint_nll, is unresolved
(completion bounds include zero) at seed 20261020, adverse (bounds above zero) at
20261021, and identical-policy predictions at 20261022. Order weighting gives the same
qualitative pattern. Horizon directions reverse between the first two seeds; no horizon
may be promoted to a new primary. Joint NLL is lower/higher/equal respectively. All
selected candidates are PH pooled/typed timing; non-selection of the shallow tree does
not prove nonlinear models ineffective. Seeds reuse patients, bounds are not confidence
intervals, and no private effect magnitudes or bootstrap endpoint values were shared.
Do not average qualitative signs or claim population significance/equivalence. Close this
selection-policy question as a negative/mixed exploratory evaluation, retain the report,
and do not retune, enlarge the bank, recalibrate or open held-out data to rescue it.
The manuscript now records the qualitative findings; numerical tables and institutional
details remain private and the draft is not submission ready. No method-superiority,
clinical-usefulness or publication-readiness claim is established.

The user then reopened direction assessment after reporting a new server-side data
format, tentatively called "omar". Its name, location, version and contents are unknown;
do not assume OMOP. At this assessment's start, origin/main had no update beyond
`28b7abe`; this is not evidence that server data did not change. F001 is implemented as
a bounded Parquet-footer-only format probe, not a clinical experiment or a conformance
validator. See docs/27 for public-source research review, fixed limits and the conditional
paired representation-fidelity direction. No new row reading, source role, semantic
assumption, held-out evaluation, full scan, GPU or old-study tuning is introduced.
Shape matches never establish populated values, actual precision, provenance or direct
event linkage. Unknown/truncated samples never establish absence. Only the explicit
authorized root or existing configured data_root is probed; no whole-server discovery.
The next genuine dependency is a server-only probe, operated by the user. The existing
explicit push/run/feedback authorization applies to this verified milestone. Preserve
all prior negative findings; P001/P002 are conditional candidates, not runnable studies
or claims of publishability. Do not use another speculative model search to fill gaps.

The user's subsequent instruction cancelled the new-format direction and asks for
alternatives using the previous data only. F001/P001/P002 are no longer active tasks;
do not submit the format probe or request a new resource location. Retain its code as
inactive infrastructure. Assess alternatives against the already reviewed cohort/history
and existing source semantics, without launching another experiment merely because it
can run. The initial application candidates were an analysis-definition sensitivity
study and bounded first-execution process description; the later ML-only requirement
below supersedes them as the proposed main project.
The extracted clinical cohort pools terminal-without-execution outcomes: do not infer
separate cancellation/end reasons from the generic model's extra cause slots. Scheduled
dose times, clinical urgency, medication errors and physiological outcomes are not
established by these artifacts. No server task is currently scheduled by this assessment.

The user clarified that the target must be a machine-learning methods paper and that
new tasks may use the same original data, not only the old extracted cohort. Prioritize
assessment of relation-preserving sequence learning for recurrent linked events;
one-to-many self-supervision and history compression are alternatives, not established
novel contributions. See docs/02 for the closest prior work and local go/no-go questions.
Repeated administrations and direct links are recorded operational capabilities, but
complete recurrent episodes and sufficient information for a new task are not verified.
The one-time first-execution cohort and capped histories cannot answer that question.
Do not relax their exclusions or silently reuse their test split as a new confirmation.
A separate recurrent design, coverage contract and bounded extraction are required before
clinical use. No new source semantics, clinical run, GPU work or data transfer is introduced
by this research assessment. After the user's instruction to start, M001 is implemented
as `make memory-demo`: a generated-only CPU mechanism benchmark with standard learned
utility regression, exact context allocation and small NumPy neural decoders. It does
not establish a novel method or implement a recurrent clinical extractor. The first full
run has mixed small gains versus balanced context and extra allocation overhead; null
histories lose to a history-free reference. See docs/11 and docs/20. Preserve these results;
do not turn a gain over global truncation into a paper claim or a UCSF advancement gate.
The event-context cap is not a total memory bound: scanning, metadata, model state and
allocator workspace are additional. No server experiment follows this local prototype.

The user then explicitly requested continuous autonomous research. M001 is not the main
paper method; its mixed result does not stop local research. J001, `make joint-audit-demo`,
is a generated finite-state laboratory for joint recurrent paths under common observation
end. It uses established marginal/joint/latent-class EM references and an invalid
zero-fill control; no new algorithm is claimed. The full 54-case run is complete. It
exhibits a sample/observation-dependent tradeoff: joint dependence can help in correlated
generators but overfits small or null settings. A constructive nonidentifiability witness
prevents interpreting unsupported tails as learned facts. See docs/02, docs/11 and docs/20.
Continue locally toward observation-adaptive dependence learning and compare with strong
structured shrinkage/reference methods before a server handoff. This method is planned,
not yet implemented or a publication claim. No clinical data, old-study retuning, format
probe, test opening, new extraction or GPU job follows automatically from J001.

J002 (`make joint-shrinkage-demo`) now implements a generated prefix-contrast interaction
candidate plus stronger smoothing and model-averaging references. Its 150-case grid is
complete: reveal-depth grouping sometimes improves on global shrinkage, but this candidate
loses to the tree/blend comparator in 142/150 cases. Preserve the failure and oracle-versus-
feasible distinction; do not schedule UCSF for this version. Predictable-history stopping
and future-informative stopping are separate generated stresses; the latter can invalidate
ordinary prefix-score comparisons. Continue toward joint likelihood estimation that learns
marginals and interactions together and enforces probabilities during fitting. J003 now
implements that estimator as `make joint-likelihood-demo`; all 150 fixed cases completed
with certified convex optimization, but reveal-depth grouping loses to tree/blend in
108 cases, ties 21 and wins 21. Preserve this negative strong-reference comparison;
do not retune its penalty grid or schedule a clinical run. Next local work audits the
information geometry of predictable stopping, including marginal/interaction coupling;
`make joint-information-demo` now verifies this finite generated information audit:
predictable stopping preserves reveal-depth blocks but couples marginal and interaction
scores, while future-informative stopping can bias ordinary prefix scores. The audit
uses known simulator kernels and cannot test an unknown clinical mechanism. Continue
with sequential conditional structures and strong Markov/context references locally;
no successor estimator is yet selected or claimed novel. Details and checks are in docs/11
and docs/20; no actual data or new server task has been introduced.

J004 (`make joint-context-demo`) now completes 150 fixed comparisons of ordinary
sequential context/Markov references with absorbing transitions and two-fold patient CV.
Context sharing helps some small-sample/adaptive-stopping settings, but persistent
latent-class and tree references remain stronger in others. These are stronger known
baselines, not a novel method or a server advancement gate. Preserve all regimes and
the selection cost. Continue locally toward a scalable variable-roster/longer-path
design supporting both persistent and short-memory dependence; that extension is planned,
not implemented or publication-ready. Do not keep tuning the same finite grid.

J005 (`make cardinality-demo`) implements a scalable exact count-interaction component
and 72 complete-observed one-transition comparisons. Its projected bounded candidate
has limited local benefit but large collective/subgroup failures; do not promote it or
expand its fixed strength bound after inspection. `make cardinality-limits-demo` verifies
same-bound population-oracle failures and a structural four-entity counterexample:
equal marginals/total counts can hide different subgroup dependence that this model
family cannot represent. This is a model restriction, not a data impossibility result.
Continue toward history-conditioned subgroup/latent structures with known recursive-count
and conditional-circuit methods as close references. The cardinality DP is a known
primitive; no recurrent terminal adapter, censoring result, method novelty or clinical
advancement is established by J005. No new UCSF action is scheduled.

J006 (`make history-roles-demo`) now implements generated recurrent paths with history-only
roles, terminal absorption and predictable prefix stopping, plus a three-start learned
conditional HMM. The fixed screen completed 72 fits / 288 evaluations, training at
rosters 4/8 and evaluating unchanged fits at 4/8/16/32. History roles are informative
in matching generators and transfer, but the learned HMM beats the bank in 238/288
cells. Preserve all null/misspecified controls; do not expand this bank to rescue it.
No novel method or clinical recurrent extractor is established. Keep the HMM as a
strong reference, and distinguish normalized variable-size laws from marginalization
of missing entities. `make roster-marginal-audit` implements exact count-law deletion
and verifies the known identical-history conditional-iid covariance limitation.
J007 (`make competition-demo`) now combines latent Markov dynamics with normalized
finite-roster count emissions. Its fixed 30 fits / 120 evaluations completed; combined
dependence beats both isolated components in its represented mechanism, including
unchanged-fit transfer to larger rosters. Simpler laws still favor simpler references;
preserve null degradation and incomplete outer-EM convergence. The initial full run
failed on a bounded-Newton active-set defect; the regression-tested solver correction
did not change the scientific grid. Exact conditional future sampling is implemented
for fully observed prefixes, including unknown future terminal events. These are known
building blocks, not established method novelty; correlated-emission HMMs are also prior
work. Missing recurrent entity histories remain unsupported by this learner. Continue
local inference/design research; no server-data blocker or clinical advancement yet.

J008 (`make hidden-history-audit`) now exactly marginalizes permanently unobserved
recurrent entities with a known full initial roster. A histogram filter agrees with
full labeled path probabilities and posteriors; all three fixed audits and 15 scaling
cases passed. B=8 compresses 390625 labeled history states to 495, but still has 125970
transition terms, so preserve the explicit resource limits. Deleting missing entities
changes the population law when competition is present. Lifted filtering and multiset
inference are established prior work; this is a reference implementation, not a new
method claim. It does not learn parameters from missing histories, handle unknown
initial rosters or identify an observation mechanism. Continue local learning/design
research with strong references and a defensible task; no clinical task is scheduled.

J009 (`make hidden-learning-demo`) now implements exact posterior sufficient statistics
and MAP-EM for partially unobserved histories, with the all-positive count partition
fixed in advance. All 30 fits / 180 evaluations completed; full-observation updates
reduce to J007. Proper missing-history learning helps in the represented competition
mechanisms but retains null/misspecified degradation and incompletely converged outer
EM. Expected statistics/gradients match exhaustive and finite-difference references;
inner convex gaps pass. This is a known-EM reference learner, not established novelty.
Preserve its fixed protocol and results. Continue with stronger correlated-emission
and set-process comparisons; no clinical job, original-test reopening or new source
semantics are authorized by these generated results.

J010 (`make gdpp-containment-audit`) verifies that J009's unsigned count emission is
exactly a diagonal cardinality-weighted GDPP, already covered by Sharghi et al. (2018).
All 21 static, two recurrent and four restricted-kernel covariance checks completed.
Do not promote the count emission as a new family or compare only to ordinary DPPs
to support novelty. Non-diagonal history-GDPP probabilities are implemented and verified;
a full learned GDPP comparison is not implemented.

J011 (`make factored-history-audit`) now replaces J008 compound-edge enumeration for
the unsigned model with terminal thinning and grouped polynomial contractions.
All 72 generated correctness/scaling cases completed, agreeing with sparse filtering
through eight hidden entities and running factored-only through 24. Preserve small-case
overhead, fixed four-history/unsigned restrictions and the known full initial roster
assumption. Sparse costs above eight are combinatorial counts, not measured runtimes.
The rearrangement uses known inference primitives; method novelty and clinical utility
remain unestablished. J012 now verifies the exact backward/likelihood-gradient operator
in 54 generated cases; no large-roster model fitting is implemented. No new server
task or reopening of prior clinical studies follows.

The user's subsequent steering is to keep a machine-learning methods target while
grounding the contribution in the UCSF task, rather than prioritizing mathematical
or computational sophistication. This supersedes the historical next-step instructions
above: retain J001-J012 as generated reference tools; suspend the unimplemented J013
particle comparison. Prioritize the task/coverage assessment in docs/11, section
"2026-10-20 task-first research priority". Known initial rosters, permanently hidden
entities and capacity competition are simulator assumptions, not established clinical
facts. Do not expand their benchmarks before a concrete real-data task justifies them.
The candidate is joint prediction of documented execution events for a cutoff-defined
set of linked orders, subject to verified observation coverage. T001 now implements the
separate aggregate-only task contract and `recurrent-audit` Slurm entry; focused generated
tests pass. It retains repeated events without modifying the original first-execution
extractor. It is not a model-ready recurrent extract or a clinical modeling protocol.
Its separately declared full-source operation selects at most 32 original training
patients, runs two order passes plus one administration and one observation pass,
and verifies complete content hashes before/after. Both charged file reads and decoded
row groups have a 64 GiB total ceiling, with 2 CPU / 4 GiB / 1200-second worker bounds.
The user requested runnable server commands on 2026-10-21 after the release proposal;
proceed with this verified milestone's commit/push and pinned handoff. The user reported
T001 job 39768 submitted at release `34d6ee7`, followed by the monitor's generic failure
message. Read-only feedback then showed FAILED / exit 2 after one second and no
failure record. This narrows investigation to startup/early initialization without
establishing the cause or scan completion; no task-support finding follows.
Subsequent read-only inspection reproduced `path_validation / recurrent_invalid_output`;
the specific path predicate remains unknown. The local fix accepts the fixed authorized
root's canonical spelling, retains descendant-symlink/Git/overlap restrictions, and
checks boundaries before submission. A new `--check-storage` wrapper emits only fixed
categories without a job or row reads. It requires a release newer than `34d6ee7`
and has not yet been verified on UCSF.
The subsequent `07638fb` storage review confirmed the configured output is inside a
Git repository, with the alias-related legacy flags false. The current fix separates
old artifact discovery from an explicit external `--output-root`, without editing the
existing config or moving artifacts. New writes must remain outside every repository.
Read-only legacy cohort access is allowed only inside this project's original common
repository when Git confirms the directory is ignored and no contents are tracked;
foreign/nested repositories, redirects, input/output overlap and tracked inputs reject.
This exception adds no source role or row persistence. Test the storage check before
submitting the unchanged bounded scan; do not treat path checks as research evidence.
The user also reported GPU availability if useful; T001 remains a CPU
source/coverage audit, with GPU use considered only for a justified later modeling task.
`run_recurrent_audit.sh` defaults
to plan only; `--submit` executes the explicitly described scan after a clean release.
Do not substitute old coherent order samples or increase caps silently.
Existing capped first-execution artifacts
cannot establish full recurrent coverage. Preserve the methods-paper requirement, prior
negative findings, sealed old tests and the existing data boundary.

## Workflow

As requested on 2026-10-16, the Mac is again the primary implementation environment.
The Mac agent owns code changes, generated tests, research review and synthetic
reproduction. UCSF remains the only environment for restricted data and real validation;
the user can run prepared Slurm commands there without a server coding agent.
Git carries code and approved operational summaries at milestones or genuine blockers,
not after every check. Keep one active writer per branch, currently the Mac. Coordinate
a transfer before resuming independent server implementation on the same branch.
Do not connect to UCSF from the Mac agent, modify sibling projects or pull clinical
artifacts back through Git or other channels.

## Data boundary

All UCSF records, patient identifiers, feature tables, predictions, logs, model
weights, and raw schema reports stay on authorized UCSF storage. Use only
generated synthetic fixtures on the Mac and in tracked tests. The authorized server
may inspect restricted inputs within the reviewed scope; their contents remain there.
Never paste real rows or values into issues, prompts, documentation, terminal summaries,
or Git commits. Schema discovery
reads Parquet footers only, omitting statistics and arbitrary metadata.
No real column mapping is stored here. Server-approved operational findings are in
docs/21_mac_development_handoff.md, docs/23_feasibility_contract_gaps.md and
docs/24_bounded_run_findings.md; never infer source column names from those findings.
Time/availability evidence references and
documentation classifications are server-local too, never report payloads.

## Research invariants

Respect both occurrence and availability time at each prediction cutoff.
Split at the patient level. No global calendar split until shifted-date semantics
are verified. Unexecuted is not a failed execution: distinguish terminal causes
and right censoring. The current MVP concerns first execution only. Reject
repeated administrations until a recurrent-event design is implemented.
Predictive associations do not identify causal treatment effects.

## Engineering

Python 3.11+, src layout, explicit configs and seeded synthetic tests.
During implementation run focused tests for the change. For pipeline changes, run
`make check` and `make demo` before committing/publishing the verified change. Reuse an unchanged
environment; repeat setup only when dependencies/environment require it. Tests must cover
censoring, linkage, temporal availability, patient splits, and no-data Git
handoffs. Keep failures explicit; never substitute synthetic results for clinical
results. Do not log exception payloads containing private records.
No large/GPU training during Phase 0. Server agents may inspect metadata, implement and
test an appropriate access backend, then run bounded aggregate-only feasibility after
institutional access, server context, mapping semantics, coverage and resource bounds
are verified on the server. Routine implementation, bug fixes and bounded CPU runs
inside that established scope do not require another Mac handoff. The bounded Phase 0
cohort extractor is implemented and generated-test verified; formal clinical extraction
must run only through its clean-commit Slurm entry point. Do not persist rows during
feasibility.
Treat truncated scans as incomplete evidence: do not confirm single executions or
censoring when another qualifying dose could be outside the scan. Encounter mismatch
handling is explicit and counted; patient mismatches always reject the order.
Keep lab features disabled until an independent availability rule is reviewed.
Use the version 2 mapping with a bounded third observation source. Require direct
observation linkage, patient agreement and reviewed retrospective coverage semantics;
never replace observation end with order end. Naive times need an explicit reviewed
timezone or shifted common-clock policy. Equality of execution occurrence/availability
requires evidence and a reviewed mapped retrospective-exclusion rule; retrospectively
documented or unclassified qualifying doses reject the entire linked order.
The first real bounded runs were limited and independent prefixes had no linked keys;
do not interpret that as absent linkage. Use docs/25_coherent_access_design.md as the
starting specification. The server should check available access capabilities and
continue directly into implementation/testing when evidence supports a backend. The
coherent-manifest executor is implemented and has completed a bounded real validation;
an independent exact-key indexed backend remains unimplemented. Do not repeat unchanged
prefix runs expecting coherent coverage.
Persistent index/extract creation, full-source scans and resource expansion beyond the
established scope remain separate operations: make their scope/cost concrete if needed.
Do not disguise them as bounded probing. Missing access, essential semantics or physical
access capabilities are genuine blockers; ordinary code defects are work to fix locally.

## Handoffs

On 2026-10-21 the user removed the per-release commit/push approval requirement because
the server Codex is unavailable and Git is how server code is updated. The Mac agent
is authorized to commit and ordinarily push verified project milestones and necessary
server fixes without asking again. Complete the required checks before publishing,
then provide commands pinned to the actual released commit. This standing authorization
supersedes older per-release approval requirements recorded in the research log.
Keep the Mac as the active writer; the user operates the prepared UCSF commands.

Commit source and docs only after checks pass. A handoff SHA identifies the initial
entry version, not a permanent freeze: server changes and later jobs use their own
actual clean commits. Never edit/pull a checkout or mapping used by a queued/running
job; use a separate clean job checkout if development must continue concurrently.
Use `make handoff` to produce a prompt pinned to the actual clean commit when needed.
`scripts/publish.sh` runs checks before ordinary (never force) push. No automated result
download or clinical-data upload.
Update docs/20_research_log.md with real checks and negative findings. Future
components must be explicitly labeled as planned until runnable and tested. Report a
milestone with code SHA, checks, real run state, coverage limitations and next work;
send an interim handoff only for a concrete blocker requiring user/external input.
