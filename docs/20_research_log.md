# Research and engineering log

## 2026-10-14 — Phase 0 initialization

User requested actual project automation from the supplied research record.
The target directory was empty and was not a Git repository. Created an independent
repository in the specified directory; no sibling project was modified.

Workflow clarification: local Codex develops and pushes code, user pulls on UCSF and
passes a versioned prompt to the server Codex with clinical-data access. Direct local
SSH/rsync is not part of the workflow. Remote Git URL is pending from the user.

Implemented: canonical synthetic events, explicit followup/censoring, first-event
linkage validation, availability-aware history, patient partitions, piecewise
exponential competing-risk baseline, CIF and clustered bootstrap, CLI and manifests,
metadata-only audit, bounded CPU Slurm runner, Git publication checks and handoff.

Scope limits: no actual UCSF access, verified fields, clinical extraction, neural
training or clinical results. The synthetic marker is provenance, not anonymization.
Related-work primary links were checked; comprehensive novelty review remains pending.

Validation actually executed on the Mac (Python 3.11.17):

- `make check`: Ruff lint/format, **51 pytest tests**, and repository boundary check passed.
- `make demo`: completed generation, Parquet roundtrip validation, cohort, fitting,
  validation and test evaluation with 300 patients, 600 orders and 4,127 events.
- Test partition: 45 patients / 90 orders; NLL 2.7292642717 per order, patient-cluster
  bootstrap 95% interval [2.4316855015, 2.9971389141], 200 replicates. Outcome counts:
  9 censored, 68 administrations, 8 cancellations, 5 other terminal events.
  These are fictional-data smoke-test results, not clinical research findings.
- The original `generate_synthetic.py` / `validate_schema.py` entry points both ran.
- `uv build` created an sdist and wheel; verified canonical data modules and CLI in wheel.
- Bash syntax checks passed. Server submission commands were unit-tested; no actual
  UCSF connection, Slurm submission, private-data read or GPU training occurred.

An initial setup attempt failed because README had not yet been written; setup passed
after completing that file. During review, corrected an overly broad `data/` ignore
rule so the source data package is included in Git and distributions. Lint findings
were fixed before final checks. No model-selection claim follows from this smoke test.

Initial development runs recorded an uncommitted source tree. A fresh post-commit
demo and generated handoff record the actual clean commit; no self-referential SHA
is hard-coded in this log. Raw synthetic artifacts are ignored, not committed.
Next server task: bounded metadata audit after version, environment and
institutional-access checks. Remote Git URL and the actual push remain pending.

## 2026-10-14 — Git remote handoff

The user supplied `https://github.com/TJor-L/intent-execution-state.git` and authorized
the previously agreed code publication. Configured it as origin; the remote HEAD/main
query returned no existing commits. Updated the UCSF clone instructions. Publication
uses the checked `scripts/publish.sh` workflow and regenerates the handoff for the
published source commit. No UCSF access or data transfer is part of this step.

## 2026-10-14 — Bounded feasibility implementation from server handoff

Pulled `682c6baf541f50a8249b3bc5badb7d74cd73a317`, which added the approved Mac
development handoff. It reports structurally feasible direct linkage, common repeated
administrations, mandatory patient consistency, non-exact encounter identity, a locally
reviewed dose-action policy, unresolved general refused/held terminal causes and no
reviewed independent lab availability rule. No physical schema or records were shared.

Implemented a generic typed server-local mapping contract, projected/batched Parquet
reader and aggregate-only feasibility validator. It counts direct linkage, invalid
identities/times, patient/encounter consistency, qualifying/excluded actions and
first-event eligibility. Repeats reject the order rather than selecting the earliest
dose. Execution, reviewed terminal events and administrative censoring remain distinct.
Laboratory features are disabled. No real cohort adapter or patient-level export was added.

An important coverage decision: an early scan limit may hide another dose or duplicate
key. Limited scans report observed diagnostics only and do not confirm execution,
terminal or censoring eligibility. This is intentionally stricter than treating the
scanned prefix as complete followup. Complete means complete within the declared,
server-reviewed source scope, not an inference about the full database.

Added explicit source/file/directory/row/key limits, worker CPU/memory/affinity limits,
parent wall-time enforcement, CPU-only Slurm submission and clean-commit verification.
Planning reads configuration only and creates no output. Submission fingerprints the
same mapping bytes used to set resource limits; changed mappings fail at execution.
Reports contain only fixed aggregate counters/status, with no records, physical names,
actions, paths, timestamps or exception payloads. Outputs stay in restricted server
storage; the worker does not spill rows or persist its private mapping.

Actual Mac validation: `make check` passed with **110 tests passing and 1 Linux-only
integration test skipped**; lint/format and publication-boundary checks passed.
`make demo` passed with the unchanged synthetic baseline NLL 2.729264271658528.
Bash syntax checks passed. Tests use generated neutral fields/actions/identities and
cover the 15 handoff categories, incomplete coverage, clean revisions, mapping changes,
private output modes and sanitized failures. The native resource-limited worker test
is scheduled to execute in Linux CI on publication; no UCSF job was submitted here.

Next server task: review/populate the ignored mapping, plan and then run one bounded
aggregate feasibility job if its prerequisites are satisfied. Interpret limited/
failed/no-report states explicitly and return only approved operational findings.
Real extraction, clinical training, physiology features and GPU work remain pending.

## 2026-10-14 — Server feasibility configuration stopped before submission

The authorized server pulled and tested
`ff14ab80d4cc07d12828f98aafece6338d841393`. Preflight, Ruff, formatting,
**111 tests**, the repository boundary check and the end-to-end synthetic demo passed.
No real feasibility Slurm job was submitted because the reviewed sources cannot be
represented truthfully by the current mapping contract.

Approved operational findings: source timestamps require an explicit policy for
timezone-naive values; execution availability has no separately reviewed timestamp;
and observation end comes from a third logical source rather than the order rows.
Temporal ordering alone was not treated as semantic proof, and occurrence-equals-
availability was not enabled to bypass missing evidence. The execution-action policy
does not invent refused, held or not-given terminal causes.

The next Mac task is documented in `docs/23_feasibility_contract_gaps.md`: add explicit
reviewed time normalization, a bounded third observation source and join, and stricter
evidence requirements for occurrence-equals-availability. Output remains aggregate-
only; real cohort persistence, labs, GPU training and automatic result transfer stay
out of scope.

## 2026-10-14 — Version 2 contract after the server's stopped configuration

Pulled `b3961d600f9baeb319b3da27fd63ed9a465ba161` with the approved contract-gap
handoff. The server had submitted no real feasibility job; no rows, source fields,
private paths or schema reports were transferred to the Mac.

Implemented version 2 mappings and aggregate reports. A required third observation
source joins through an explicit reviewed identity and checks patient consistency.
Its encounter reject/count policy is independent of the administration policy.
Missing coverage, duplicate observation identities and invalid endpoint times reject
linked orders; order termination cannot supply missing coverage. Observation registries
share the total key budget; all three readers share the same per-source traversal/row
caps and global CPU/memory/time limits. Any truncation preserves limited status and
suppresses otherwise eligible outcome claims.

Added in-memory naive timestamp normalization with a reviewed named IANA timezone or
explicit common within-patient shifted clock. No host timezone, current-date check or
calendar split is inferred. Ambiguous local times reject unless a reviewed earlier/later
policy is explicit; nonexistent local times always reject. Order occurrence and
availability remain separate required mappings. Old mappings fail rather than inherit
new semantics silently.

Execution availability stays independently mapped by default. Equality now requires
private evidence metadata and a separately reviewed mapped classification of
contemporaneous versus retrospective documentation. Retrospective/unknown qualifying
records reject the whole linked order and still contribute to repeat diagnostics.
Dropping only those rows would falsely manufacture censoring or single executions.
No refused, held or not-given outcome was invented.

Observation endpoint availability is validated separately from occurrence and counted
when it lies after the analysis boundary. The explicitly reviewed interpretation is
retrospective coverage ascertainment, not online endpoint knowledge or an index-time
feature. Availability never extends the observation window. Continuous coverage still
requires source-semantic review; a direct identity match alone cannot establish it.
An online coverage policy, mixed time encodings and real cohort persistence remain
unimplemented. These are stated limitations, not inferred source properties.

Actual local validation: `make check` passed with **165 tests passing and 2 Linux-only
worker cases skipped**, plus Ruff, formatting and repository-boundary checks.
`make demo` passed with the unchanged synthetic NLL 2.729264271658528 and patient-
bootstrap interval [2.4316855014758967, 2.9971389140500238]. New tests cover UTC/DST and
shifted clocks, missing/duplicate/inconsistent observation links, every third-source
scan/key bound, retrospective exclusion, required evidence, sanitized failures and
data-free planning. Native Linux worker cases cover both availability policies in CI.

Next server task: preserve the old private mapping, review a version 2 configuration
using the updated pinned handoff, and submit one small aggregate-only job only if all
semantics can be established. The implementation does not supply missing evidence.
If execution availability/classification or observation coverage cannot be reviewed,
return an approved operational blocker without guessing values or expanding scope.

## 2026-10-14 — First version 2 bounded feasibility runs

The authorized server pulled and tested
`8f8772587e7acb4958ce2ef9c6668edb7042120a`. Preflight, Ruff, formatting,
**167 tests**, the repository boundary check and the synthetic demo passed. A private
version 2 mapping passed data-free planning with all three logical sources and explicit
time/documentation policies. No physical mapping or private evidence entered Git.

Two small CPU jobs wrote valid `limited` reports. The first reached the shared key and
row allowances before a useful three-source diagnostic. A second run reduced rows per
source without increasing resources; it considered all three sources and qualifying
actions but found no linked identities in the independent bounded prefixes. It
correctly asserted no execution, terminal or censoring eligibility. A limited worker
uses a documented nonzero exit, so scheduler state alone is not the result.

This is a negative feasibility finding about the sampling mechanism, not evidence of
absent clinical linkage. The source layout is separately sharded, so independent prefix
sampling is structurally uninformative. Quotas were not expanded and convenient shards
were not selected. `docs/24_bounded_run_findings.md` specifies the next design: an
explicitly reviewed coherent-source or key-index/probe interface with separate scanned
and retained bounds, provenance checksums and aggregate-only output. Full cohort
extraction and an implicit full-table key scan remain out of scope.

## 2026-10-14 — Budget diagnosis and coherent-access design review

Pulled `9976b9ab688bb56d24a7ce5a3aefae6d6d9341fe`, the server's approved bounded-run
findings. Two limited runs demonstrated that independent source prefixes do not yield
useful cross-source identity coverage for this layout. This does not estimate absent
clinical linkage. Only operational documentation was returned, without clinical data.

Implemented a non-sensitive planning diagnostic for worst-case registry entries:
three per-source row caps versus the shared key allowance, including the shortfall
and whether all row caps fit. Plans explicitly identify independent-prefix sampling
and do not claim coherent linkage coverage. Reduced the tracked example from 5,000
to 3,000 rows per source, so at most 9,000 unique registry entries fit in 10,000 slots.
Other quotas and existing private configs are unchanged. Fitting keys neither fixes
source alignment nor guarantees memory use.

Completed the proposed interface design in docs/25_coherent_access_design.md. It starts
from an explicit reviewed order seed domain and requires either an existing coherent
manifest or an approved exact-key index/probe capability. It specifies completeness
receipts, separate scanned/retained work, file/row-group/probe/index/byte/resource
bounds and mapping/manifest checksum binding across plan, submission and execution.
Underlying immutable source/index provenance is required in addition to manifest
hashes. The design retains duplicate, patient mismatch, repeat, retrospective-record
and availability rules and distinguishes incomplete lookups from complete absence.

The new access executor, manifest parser, dual-checksum submission path and provider
backends are **not implemented**. They require the server's capability review first;
no known existing index or coherent extract was inferred from the handoff. The next
server prompt requests that review using already approved documentation and metadata,
not another real prefix job or new persistent preparation. Building an index, making
a coherent extract or doing a full-source key scan remains a separate reviewed phase.

Actual local validation: `make check` passed with **170 tests passing, 2 Linux-only
worker cases skipped**, Ruff/format checks and repository-boundary validation.
`make demo` passed with unchanged synthetic NLL 2.729264271658528. Budget tests include
the old shortfall, revised example, exact-capacity and very small-capacity cases,
non-mutating/data-free planning and the server planning entry point. The Linux-only
worker cases remain part of publication CI. No clinical source or UCSF job was accessed
by this Mac agent.

## 2026-10-14 — User moves primary development and testing to UCSF

The user identified the per-step Mac/server handoffs as inefficient and requested more
development and testing on the server. Updated the working agreement, active handoff,
README and workflow/design documents so UCSF owns the continuous implementation,
synthetic-test, bounded-real-validation and repair cycle. The Mac now supports research
discussion, code review and synthetic reproduction. The previous review-only stop and
requirement to return ordinary implementation work to the Mac are explicitly superseded.

The server may review available access capabilities and immediately implement/test a
supported backend, then perform small CPU validation within established authorization,
semantics and resource bounds. Ordinary bugs and configuration/scheduler defects are
fixed there. Handoffs are grouped at verified milestones or genuine external blockers.
The initial prompt SHA identifies entry state; later server commits/jobs use their own
verified revisions. Active job checkouts/configs remain fixed, with separate development
checkouts when necessary, and one primary writer per branch avoids competing edits.

Existing environments and successful checks are reused when unchanged. Focused tests
support development; pipeline changes still receive full checks and the synthetic demo.
Clinical data, private mappings/evidence and reports stay on UCSF. The change does not
authorize hidden full-source scans, new persistent extracts/indexes or resource growth;
if those are truly needed, the server must make the separate operation concrete.

This update changes workflow documentation, not the implementation status of coherent
access: its executor remains unimplemented. No clinical job was started by the Mac.
`make check` passed: **170 tests passed, 2 Linux-only cases skipped**, Ruff/format and
repository-boundary checks passed. No new tests or synthetic run were needed for these
documentation-only changes; the publication workflow still runs its required checks.

## 2026-10-14 — Coherent-manifest backend implemented on UCSF

Reviewed the server's existing approved patient-sharded MEDS artifacts and available
manifests. They provide coherent patient event shards but the medication conversion
does not retain the direct order-to-administration and encounter identities required
by this validator. No approved exact-key index/probe service preserving those fields
was found. This is an access-layout finding, not a clinical linkage finding. No hidden
full-source scan, persistent index, extract, cohort or GPU task was started.

Implemented schema-version-1 `coherent_manifest` access. A server-local manifest binds
the exact mapping bytes, an immutable reviewed snapshot and deterministic seed rule,
complete three-source coverage declarations, and explicit Parquet file/row-group
locators. The reader performs no recursive discovery or predicate/full-source fallback.
It separately caps files, row groups, projected rows, full uncompressed row-group
bytes, retained matching rows and seed keys. Unrelated administration/observation rows
consume scan and byte work but do not enter validation. Any incomplete bound suppresses
outcomes. Mapping and manifest digests are pinned through plan, Slurm submission and
the resource-limited worker; console and public plans omit private references and paths.

Added generated-only tests for remote-shard linkage, data-free planning, mapping/mode
rejection, row and byte truncation, unrelated-row accounting, duplicate orders outside
the initial location, changed locators, and Slurm digest/argument binding. Added only a
non-runnable placeholder manifest to Git. Actual server validation remains blocked on
a reviewed private manifest proving immutable complete locator coverage. Fabricating
that manifest or deriving it with a full-source preparation pass is outside this task.

Actual UCSF validation: `make check` passed with **182 tests passing**, Ruff/format and
repository-boundary checks. `make demo` passed with synthetic NLL
2.729264271658528. No clinical source was opened by these checks and no clinical report
or artifact was added to Git.

## 2026-10-14 — Full bounded footer inventory and provenance search

Ran three explicit footer-only Slurm audits against the reviewed v2 source roots
(jobs 34078, 34079 and 34080). All completed successfully in one to two seconds. Each
root was fully enumerated within a temporary 1,000-file/100-directory ceiling, with no
footer failures or truncation and one internally consistent schema per source. The
private reports remain outside Git. The private audit configurations were then restored
to their conservative 12-file defaults.

The combined source inventory substantially exceeds the coherent executor's 64-file
ceiling. Spark part ordinals are contiguous but differ across the three sources, exact
basenames do not overlap, and neither the source roots nor their common parent contains
an Arrow metadata file, manifest, catalog, index or provenance record. Completion
markers and similar filename suffixes do not prove a common key partitioner or complete
selected-key coverage, so no clinical access manifest was created.

Also reviewed the existing analysis code and bounded samples of already generated
patient-sharded artifacts. The code performs direct Parquet scans and temporary joins;
it does not expose an exact-key locator/index service or completeness receipt. A bounded
footer search of existing artifacts found no sampled schema preserving the exact
reviewed identity sets. A shallow catalog search likewise found no candidate control
file referencing those identity fields. Both artifact searches stopped at their entry
ceilings, so these are negative bounded findings, not proof about unvisited storage.

No Parquet data pages, footer statistics, arbitrary metadata or row values were read.
No database write, cohort, persistent extract, index or GPU task was created. A real
coherent validation now requires either source-owner provenance proving a shared
partition/locator contract, or a separately scoped preparation job that scans tens of
GiB and hundreds of millions of footer-declared rows to create a restricted locator or
coherent extract. That preparation is intentionally not hidden inside the validator.

## 2026-10-14 — Separately authorized coherent preparation implementation

The user explicitly authorized the separately scoped full-source read. Implemented a
Slurm-only coherent preparation worker without a database dependency. It selects up to
64 valid typed order identities from 4,096 fixed-seed uniformly sampled row positions
across the stable order snapshot, fully scans the mapped
columns in all three sources, retains every matching order/administration/direct
observation row, and preserves duplicates and mismatches for the existing validator.
It does not select a clinical cohort or claim representative sampling.

The preparation has hard ceilings per source: 1,000 files, 2,000 entries, 2,000 row
groups, 500 million rows and 64 GiB, plus 33,333 retained rows per source and 100,000
shared keys. The exact Parquet
inventory (path, size and nanosecond mtime) must be unchanged before and after the scan.
Only after that check does it write three projected Parquet files, a private mapping,
coherent manifest and checksummed receipt beneath the UCSF output root with restrictive
permissions. Console output is fixed aggregate status; exception payloads are suppressed.

Generated-only tests exercise full cross-file preparation, private file permissions,
the runnable generated mapping/manifest, discovery rejection and Slurm digest/resource
binding. The synthetic full scan exposes a duplicate administration identity outside
the previously reviewed locator and correctly rejects both affected orders. `make check`
passed with **185 tests passing** and repository-boundary checks; `make demo` passed with
unchanged synthetic NLL 2.729264271658528. No real preparation job had been submitted at
the time of this entry.

## 2026-10-14 — Complete coherent UCSF feasibility run

The first authorized preparation run completed, but its stable-prefix seed contained no
linked administration rows. A data-free plan also exposed a worst-case shared-identity
budget shortfall. The server fixed both ordinary design defects rather than interpreting
the negative prefix result: retained rows were reduced to 33,333 per source so the
three-source worst case fits 100,000 shared keys, and seed selection changed to 4,096
fixed-seed uniformly sampled row positions across the full order snapshot. Selection
does not condition on successful joins or outcomes.

After 185 tests, repository-boundary checks and the unchanged synthetic demo passed,
the final preparation job 34086 completed successfully under 2 CPU, 4 GiB and ten-minute
scheduler bounds. It fully scanned the reviewed projected sources, found both linked
administration and observation rows, verified the source inventory before and after,
and wrote only restricted UCSF-local artifacts with private permissions. No database,
cohort, model or GPU task was used.

Bounded feasibility job 34087 then completed successfully from the prepared mapping and
manifest. Its report is `complete`, coherent coverage is verified, no resource or data
limit was reached, and no order remained unresolved due to limits. The declared seed
domain contains both accepted first executions and right censoring. Repeated qualifying
administrations, missing required times and temporal-ordering violations remain visible
and cause rejection as designed; no terminal-without-execution category was observed.
These are aggregate feasibility findings for a fixed small row-position domain, not
population rates, clinical efficacy evidence or a model result. All counts and reports
remain on UCSF storage.

## 2026-10-14 — Clinical cohort protocol gate started

Started the post-feasibility milestone without extracting a real cohort. Implemented a
strict versioned clinical protocol parser and data-free planner. It freezes the current
research invariants: adult inpatient scope, first execution only, direct observation
coverage, 24-hour input/followup, occurrence plus availability time, patient-level
seeded splits, no global calendar split, rejection of repeats/ties, exclusion of
continuous infusions and unresolved PRN semantics, and no laboratory features.

The tracked protocol remains `draft`. A private protocol cannot become `frozen` until
it contains reviewed evidence for adult derivation, inpatient definition and one or two
prespecified medication categories, plus minimum eligible-order and execution-event
thresholds justified before extraction. Plans expose only generic missing gates and
never medication categories or evidence references. Generated tests cover draft/frozen
states, every unresolved gate, unknown keys, invariant violations, private-value
suppression and the CLI path. No clinical source, output directory or job is touched by
planning.

Actual server validation: `make check` passed with **195 tests passing**, Ruff/format
and repository-boundary checks.

## 2026-10-15 — Aggregate-only cohort vocabulary audit implemented

The private clinical protocol was frozen before any population extraction. It fixes an
adult inpatient population, one prespecified intravenous medication domain, conservative
exclusion of continuous/recurring and unresolved PRN orders, patient-level seeded splits,
24-hour windows, no laboratories and predeclared minimum readiness thresholds. The
private categories, evidence references and thresholds remain server-local.

Implemented the first cohort-readiness operation without extracting a cohort. The
`cohort-vocabulary` worker projects only two privately mapped order fields (PRN and
frequency), requires an unchanged source inventory before and after the scan, and has
explicit file, entry, row-group, row, source-byte, distinct-value, runtime, CPU and
memory limits. It persists no rows. Its restricted report suppresses rare vocabulary
values; the public command reports only `complete`, `limited` or `failed`. Any bound,
resource failure, schema mismatch or source change prevents a complete semantic review.

The ignored UCSF mapping was generated only after the reviewed order schema had exactly
one PRN-token field and one frequency-token field. A data-free plan passed. No physical
mapping or vocabulary value entered Git or terminal summaries, and no clinical pages
had been scanned at the time of this entry. Actual UCSF validation: `make check` passed
with **204 tests passing**, including generated projected-read, suppression, limit,
mapping and CLI tests. `make demo` passed with unchanged synthetic NLL
2.729264271658528. The next step is the bounded Slurm vocabulary scan, followed by a
private semantic classification only if its report is complete.

The bounded Slurm vocabulary audit then ran as job 34325 from clean commit
`9b33f5fe551e556f5f302441954d44464a970ccb`. It completed successfully in 2 minutes
4 seconds with low memory use. The source inventory was unchanged, every declared file
and row group fit the limits, and the report is complete for the reviewed snapshot. No
rows were persisted. Private review identified explicit non-PRN and one-time frequency
semantics and also observed a continuous-delivery category, allowing a conservative
one-time/non-PRN allowlist that excludes recurring, continuous, null, rare and
unclassified values. Vocabulary values and all counts remain in the restricted UCSF
report. This establishes filter semantics only; it is not a cohort yield or execution
rate result.

Implemented the next aggregate-only readiness operation. A strict private eligibility
mapping binds the already reviewed feasibility mapping and adds exact adult-patient,
direct inpatient-encounter, therapeutic-class, route, PRN and frequency semantics.
The executor scans only fixed projections from five reviewed sources and verifies each
inventory is unchanged. It retains a deterministic bounded medication-domain subset in
memory, applies adult status at order time and encounter patient agreement, and then
reuses the existing availability-aware three-source validator for direct observations,
repeat rejection, first execution and right censoring. No rows are written.

The report distinguishes a complete population count from sound lower-bound threshold
evidence. Candidate saturation therefore cannot be mislabeled as total cohort yield;
it can only prove that predeclared minima are met within the retained domain. Generated
tests cover adult/outpatient exclusion, direct linkage, execution/censoring, Boolean
status criteria, changed mapping rejection, candidate saturation, data-free planning
and digest-bound Slurm submission. A real eligibility job had not yet been submitted at
the time of this entry. `make check` passed with **209 tests passing**, Ruff/format and
repository-boundary checks. `make demo` passed with unchanged synthetic NLL
2.729264271658528.

Private eligibility configuration exposed two fail-closed bootstrap defects. Early jobs
34360, 34372 and 34378 stopped before page scans because field discovery did not handle
CamelCase and applied final-source caps to unrelated candidate directories. Job 34379
completed the projected vocabulary scans, then correctly stopped when more than one
explicit one-time frequency label was present; the generator was fixed to retain all
strictly recognized one-time labels rather than demand a single spelling. Job 34382
completed the scans and wrote a private mapping, but final contract validation exposed
an implementation bug: a reference to the existing ignored `configs/*.local.yaml`
mapping was being rejected as though it were a clinical data path.

The contract now permits only ignored `configs/*.local.yaml` references inside the repo;
clinical sources and outputs remain prohibited there. The generated eligibility mapping
then passed the data-free plan with all five projected sources and unchanged resource
caps. No failed bootstrap produced a cohort, report or row extract, and no private field,
value or count entered Git. After the fix, `make check` passed with **210 tests** and the
synthetic demo remained unchanged. The real aggregate eligibility job remains the next
operation.

The first real aggregate eligibility job 34406 scanned until the independent CPU cap and
returned only a sanitized `limited` report. It suppressed all counts and made no
readiness claim. The scheduler incorrectly displayed success because the CLI had omitted
the new command from its non-complete exit-code branch; the restricted report remained
authoritative and correct. No rows or cohort were written.

Fixed the exit-code defect and replaced per-row Python filtering with exact Arrow batch
filters for medication criteria and retained patient, encounter, administration and
observation keys. Only matched rows are converted to Python objects; source traversal,
stability checks, caps and outcome semantics are unchanged. Added a regression test that
requires a nonzero CLI result for limited eligibility. The retry will use the same CPU,
memory, wall-time and data bounds rather than expanding resources.

After this optimization, `make check` passed with **211 tests** and `make demo` retained
the unchanged synthetic result.

Optimized retry 34407 failed quickly with a sanitized filter-type error, and the fixed-
code diagnostic jobs 34409 and 34410 localized it to the logical current-status field
without printing its physical name or values. The private configuration generator had
used Python's equality between Boolean `True` and integer `1`, violating the contract's
strict no-coercion rule. The generator now uses exact types. Private regeneration job
34411 completed in 3 minutes 26 seconds and produced a contract-valid mapping; its
data-free eligibility plan passed. The executor retains strict Arrow typing and now
includes only the generic logical role in a sanitized type error. No cohort or aggregate
eligibility result has yet been produced.

The next formal retry, job 34429, used the corrected private status types and optimized
scan. It completed all projected traversal but failed closed when the outcome validator's
shared identity-key budget was reached; no counts or threshold decision were emitted.
Fixed-code diagnostics 34430 and 34431 localized this to the generic outcome `keys`
limit. Reducing the retained domain from 30,000 to 20,000 deterministic candidates did
not remove the issue because multiple direct administration records legitimately consume
more than one identity per order.

Implemented exact batched outcome validation without increasing any source or resource
bound. Order identities remain in one batch, while a global administration-identity pass
detects duplicates across batches and pre-rejects every linked order before aggregation.
Generated tests use an artificially tiny key budget to prove equivalence and verify that
a duplicate administration identity spanning batches rejects both orders.

Private diagnostics 34434 and 34435 completed in about 90 seconds without reaching a
limit. In the deterministic 20,000-candidate domain, both predeclared readiness gates—
minimum eligible orders and minimum execution events—were met. Population counts remain
explicitly incomplete because the candidate bound was saturated; this is sufficient
lower-bound evidence to proceed, not a population prevalence estimate. No cohort rows
were persisted, and all counts remain UCSF-only. A formal pinned report still requires a
clean source commit; persistent cohort extraction has not started.

Implemented the bounded Phase 0 extraction path without expanding the validated source,
candidate, CPU, memory or runtime limits. It reuses the availability-aware eligibility
validator, emits only classified first-outcome rows, preserves terminal-without-execution
and right-censoring labels, rejects repeated or duplicate-linked administrations, and
assigns deterministic patient-exclusive train/validation/test partitions. Identifiers
are type-tagged before Parquet serialization so mixed source identifier types cannot be
silently coerced. Laboratory features remain disabled.

The extractor is Slurm-only, binds the private eligibility mapping and frozen protocol
digests to a clean source commit, prohibits output inside the repository, source trees or
outside `/scratch/tliu7`, refuses overwrite, and writes a private Parquet cohort, aggregate
QC report and checksum manifest with directory/file modes `0700`/`0600`. The manifest
explicitly labels the cohort as bounded and carries the population-count completeness
flag; candidate saturation therefore remains visible rather than becoming a population
yield claim. No database write or GPU path exists.

Generated tests cover accepted-only row persistence, cross-batch duplicate rejection,
deterministic patient-exclusive splits, checksum/config/commit binding, restrictive file
modes, no-overwrite behavior and digest-bound Slurm submission. `make check` passed with
**216 tests**, Ruff/format and repository-boundary checks. `make demo` retained synthetic
NLL 2.729264271658528. UCSF preflight and the data-free extraction plan passed against the
current private mapping and protocol. No clinical row extraction has run yet: formal
submission is correctly blocked until these verified working-tree changes are committed
and the job can be pinned to that clean commit.

The verified extraction implementation was committed and published as
`067ded4ba04e5ed13b3293d95b4985d8205ac0c7`. Formal Slurm job 34436 ran from that clean
revision and completed successfully in 1 minute 29 seconds with low memory use and no
resource limit. The private bounded Phase 0 cohort, aggregate QC report and checksum
manifest were written only to the configured UCSF output storage; no database was
modified and no GPU was used.

Server-local post-run validation confirmed the pinned source/configuration digests,
artifact checksums, restrictive directory/file permissions, exact Parquet schema,
non-null required fields, unique order identities, deterministic patient-exclusive
partitions and consistent duration/outcome/cause encoding. Both frozen readiness gates
remain met. Population counts remain explicitly incomplete because the deterministic
candidate cap was saturated, so this artifact is a completed bounded research cohort,
not a complete UCSF population census. No clinical row, identifier, mapping, count or
artifact was copied into Git or reported outside UCSF.

Implemented the next fixed Baseline A operation for the bounded cohort. The CPU-only
worker verifies the cohort manifest and checksum, reads only train/validation rows,
fits the existing smoothed piecewise-exponential competing-risk baseline on training
patients, and evaluates only the validation partition with a seeded patient-cluster
bootstrap. Test metrics are not produced. The output model, validation metrics,
row-level validation losses and digest-bound manifest remain private under UCSF storage
with restrictive permissions. This is a label/likelihood pipeline validation without
features or an individual predictive claim, not the planned feature model.

Generated tests cover deterministic output, patient separation, zero-duration rejection,
changed-cohort rejection, private file modes, restricted-clinical classification and
digest-bound CPU-only Slurm submission. The formal clinical baseline has not run; its
source must first pass the full checks and be committed so Slurm can pin a clean revision.

The Baseline A implementation was published at its clean milestone and formal Slurm job
34438 completed successfully in two seconds. Private post-run validation confirmed all
artifact checksums and permissions, finite validation likelihood and bootstrap bounds,
exact agreement between the training-patient manifest and cohort training partition,
and no overlap between training patients and validation predictions. No test metric was
generated, and no metric value, count, prediction or identifier left UCSF. This validates
the bounded label/likelihood path only; it is not evidence of individual discrimination.

Implemented the first reviewed pre-index feature contract. It contains only integer age
at order, derived from the already reviewed birth-date/adult rule and order occurrence
time. Feature extraction regenerates and exactly aligns the bounded cohort under the same
mapping, protocol and source limits, then binds its private Parquet output to the cohort,
mapping, protocol and clean source digests. Laboratory values, outcomes, retrospective
coverage, absolute calendar features and incomplete event histories are not features.
Generated tests cover exact cohort alignment, adult feature completeness, private modes
and digest-bound CPU-only Slurm submission. The data-free UCSF plan passed; the formal
feature extraction has not yet run.

The first formal feature job 34439 stopped before source scans because the worker checked
an attribute not exposed by the already strict parsed protocol object. Its sanitized
failure artifact contained no clinical content. The scheduler initially displayed
success because the CLI's private-command status branch omitted the newer cohort,
baseline and feature commands. Removed the redundant attribute access, corrected exit
status handling for all private commands, and added generated regressions requiring a
nonzero result for every failed private operation. No feature artifact was produced by
the failed job and no resource scope was changed.

The corrected formal feature job 34440 completed in 1 minute 33 seconds with low memory
use. Private post-run checks verified the source/config/cohort bindings, checksums,
permissions, exact feature schema, non-null adult ages and one-to-one patient/order
alignment with every bounded cohort row. No feature values or counts left UCSF.

Implemented a fixed age-band piecewise competing-risk baseline with a global fallback
for age bands absent from training. The boundaries are fixed in source before validation;
estimation uses training patients only and evaluation remains validation-only with the
same seeded patient bootstrap. It reads the verified cohort and feature manifests,
refuses misalignment or changed artifacts and writes only private UCSF outputs. This is
a feature-pipeline control, not a causal or clinical-performance claim. Formal execution
has not yet run.
