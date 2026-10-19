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
specification and docs/16 for the single bounded server command. W002 clinical execution
is pending; generated checks do not supply clinical evidence.

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

Do not create Git commits or push unless the user explicitly requests it. Continue
implementation, testing and authorized UCSF jobs in the working tree; when a clean
commit is required for a formal job, report that concrete need to the user.

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
