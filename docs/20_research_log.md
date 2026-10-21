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

The fixed age-band baseline was published at clean commit
`ab97ffbb1b1b316f81721098fac4d0a986bb9c4f` and formal Slurm job 34441 completed in two
seconds. Private checks verified cohort/feature/config bindings, checksums, permissions,
training/validation patient separation, validation-row coverage and finite likelihood
and bootstrap outputs. No test metric was generated and no private result value or count
left UCSF.

The currently reviewed predictor contract is now exhausted: the bounded feature artifact
contains age at order only. Eligibility fields are selection criteria, retrospective
observation coverage is not an index-time predictor, incomplete bounded histories cannot
support history features, and laboratory/diagnosis availability semantics have not been
independently reviewed. A richer predictive model would therefore require a new private
source-and-availability review; inferring availability from field or table names would
violate the frozen temporal contract. Baseline A and A-age are pipeline controls, not an
adequate primary method comparison or clinical-performance result.

On 2026-10-16 a final bounded, read-only search of the configured authorized data storage
found no candidate data dictionary or authoritative documentation jointly defining
occurrence, recording availability and point-in-time/backfill behavior for a new feature
source. No payload, path, field name or documentation content was emitted. Because the
user has no separate semantic evidence channel and requested either autonomous resolution
or abandonment, the project stops before E002. Existing private cohort/model artifacts
are preserved on UCSF storage; nothing is deleted or transferred. Test evaluation,
multi-feature modeling, neural/GPU training and clinical-performance claims are cancelled.

The user then authorized a narrower autonomous continuation that does not require a new
semantic source: complete prediction-time histories from the already reviewed order and
qualifying-administration mappings. This does not revive laboratory, diagnosis, physiology
or causal claims. Implemented a 24-hour dual-clock history contract with full-source
inventory binding, occurrence-plus-availability masking, retrospective documentation
exclusion, duplicate rejection, explicit density/row caps and private Parquet/checksum
outputs. Generated tests cover delayed records, post-index events, source stability,
cohort alignment, private output and digest-bound Slurm submission. A data-free UCSF plan
passed; the formal history extraction has not yet run.

Formal history job 34442 stopped before a source scan because real historical rows can
contain missing or inverted time pairs. These rows are not valid predictors but should
not invalidate an otherwise frozen outcome cohort, so the extractor now excludes and
privately counts them while retaining fail-closed duplicate handling. A subsequent full
private diagnostic scan showed that materializing every eligible index-event relation
would exceed the initial 500,000-row memory bound. The fixed input contract now retains
the most recent 24 available events per index after scanning the complete source, with
exact private accounting of eligible and sequence-truncated relations. This is bounded
model-input truncation, not source-scan or outcome truncation. The corrected full-source
diagnostic completed with a verified private manifest; no scope or clinical payload was
reported.

The first resource-limited retry still failed during the complete administration-history
scan even though an unrestricted diagnostic had succeeded. Fixed-code staged diagnostics
localized the difference to memory pressure after the order-history scan, rather than an
input, semantic or runtime failure. The history path now streams patient selection from
small Arrow batches without materializing filtered batches or batch-wide row dictionaries,
stores duplicate identities as fixed-size cryptographic digests and constructs the final
Arrow artifact column-wise. The duplicate rejection rule, complete-source scan, inventory
binding and most-recent sequence truncation are unchanged. A second diagnostic completed
under the original CPU and memory limits. Private validation passed for input bindings,
checksums, restrictive permissions, the fixed schema, dual-clock lag constraints and frozen
cohort-key alignment; no test metric, clinical value, count or mapping detail was emitted.

Implemented the first matched CPU history comparison without new clinical sources or
dependencies. The availability-only and dual-clock encoders each produce eight fixed
decay features and feed the same convex piecewise proportional competing-risk head. The
configuration freezes optimization, regularization, patient-bootstrap evaluation, four
documentation-delay conditions and a three-part advancement gate. Perturbations move
availability later, remove newly unavailable events and never refit the model. Generated
tests verify matched dimensions, temporal masking, digest-bound Slurm execution,
validation-only predictions, restrictive outputs and deterministic results. A private
resource-limited diagnostic converged and passed artifact validation, but the frozen gate
held because neither the minimum unshifted gain nor its paired uncertainty condition was
met; the shift-robustness condition passed. The test partition remains sealed. This is a
negative validation finding, not evidence that dual clocks are generally uninformative.

The memory-bounded history implementation was published at clean commit
`8bc784bdd19171b9b10c0b7350635db0f406a6a3`; formal Slurm job 34444 completed under the
original CPU and memory allocation. Private post-run validation confirmed the clean
source/config/cohort bindings, checksums, restrictive permissions, fixed schema, dual-clock
constraints and cohort-key alignment. No test metric was generated.

The matched CPU comparison was published at clean commit
`d3598607ebb09379aee2105edb8ea113772aecb4`; formal Slurm job 34445 completed and reproduced
the diagnostic decision. Private checks confirmed convergence, identical feature and
parameter dimensions, common training patients, disjoint complete validation predictions,
all prespecified shifts, finite likelihoods, checksums and restrictive permissions. The
frozen gate remained held for insufficient minimum unshifted gain and paired uncertainty;
shift robustness passed. Test evaluation, architecture iteration on this validation result,
and GPU training were not performed. E003 is therefore complete as a gated negative
validation experiment, with its clinical artifacts retained only on UCSF storage.

## 2026-10-16 — Mac development resumed; generated controls and E003 review

At the user's request the Mac resumed primary implementation, with UCSF retaining all
restricted data and real validation. The entry source was
`52c49bbc37867624498ff7c0daffad9543c9df59`. This milestone consists of local working-tree
changes only; no new commit, push, server connection or clinical job was performed.

The entry version failed two generated tests because age/history readers hardcoded the
server storage root separately from the cohort verifier's test override. Cohort, age and
history readers now share a resolved artifact-directory guard. Production authorization
is unchanged; generated tests replace the root in-process only. Added rejection coverage
for outside, relative, repository and escaping directory-symlink paths. Scale and shift
configuration now rejects nonfinite numbers; empty histories cannot conceal an invalid
shift. The clinical model config and E003 thresholds were not changed. Factored the
existing gate calculation without changing its output or inequalities to test each
condition and its boundary directly.

Generated diagnostics verify an analytical censored competing-risk likelihood, event-bin
edge convention, constant-feature rate recovery, train-only normalization/fitting, paired
patient bootstrap with unequal order counts, and invariance of validation artifacts to
changes confined to generated test labels/history. A fixed-seed occurrence-signal positive
control passes using the current CPU encoder/head. Further generated counterexamples
show that the dual encoder loses event-level delay pairing and duplicates features when
clocks coincide. None of these diagnostics is evidence of clinical performance.

The source review in docs/08 and docs/11 narrows interpretation of E003: clock comparisons
also change decay scales; predictor content lacks index-order attributes and historical
order/administration links; both encoders inherit occurrence-based windowing/capping;
delay perturbations mask the retained history without refilling it. The frozen shift gate
compares models at a common shift, not either model against its unshifted performance.
Clinical coefficients, uncertainty and saturation behavior were not independently
inspected here. E003 remains a gated negative result, with test sealed and no neural/GPU
experiment scheduled. A successor requires a separate falsifiable design and an explicit
plan for already-inspected validation data; it is not implemented or running.

Validation: the initial focused set passed 28 tests. After adding gate-boundary and
test-isolation cases, final `make check` passed Ruff checks, formatting and 255 tests;
two Linux production-resource tests were skipped on macOS. The repository file boundary
check passed. `make demo` passed with unchanged synthetic NLL 2.729264271658528. This does
not claim Linux CI or new UCSF execution. Updated README, workflow, overview, architecture,
experiment status, historical schedule and server prompt to remove superseded server-primary
instructions and premature progression past E003. Existing private artifacts remain on UCSF;
no repeated clinical extraction or model run is needed for this local milestone.

## 2026-10-16 — S001 generated clock-pairing mechanism implemented and run

Continued from the local review on base commit
`52c49bbc37867624498ff7c0daffad9543c9df59`, with all changes still uncommitted. Implemented
`make pairing-demo` / `ies pairing-diagnostic`, a strict generated-only config, and three
encoders sharing the same clock scales: eight marginal features, sixteen features with
independent-pair expectations, and sixteen with observed within-event joint terms. All
reuse the same CPU hazard head. Its data-class argument now permits explicitly synthetic
model artifacts; existing clinical callers retain their original default and behavior.
The experiment has no external history/cohort input and no clinical advancement decision.

The generator changes only within-event timestamp pairing to impose a predictive signal.
Its null case preserves the histories while removing dependence of labels on pairing.
Its scrambled case preserves the exact signal-case labels and all clock marginals, while
independently reassigning the visible pairing. All generated permutations respect both
time constraints. Patient-level splits and bootstrap keep a patient's orders together.
All seeds, scenarios and models are reported without selection. The mechanism definition,
fixed configuration and interpretation boundaries are in docs/08 and docs/11.

The first full run, `artifacts/synthetic/20261016T135732Z-pairing-ff424f6a`, completed all
three preselected seeds and three scenarios. The following are **synthetic-only** mean
validation NLL differences per order, paired minus the same-dimension unpaired control:

| Generated scenario | Mean difference across three seeds |
| --- | ---: |
| Pairing signal | -0.2648343067 |
| Null | +0.0007467343 |
| Scrambled pairing | +0.0028898166 |

All three signal-case paired patient-bootstrap intervals were below zero. Null differences
were small; every null interval included zero, which is not evidence of equivalence.
Scrambling removed the observed gain; one seed had a small worsening with an interval
above zero. This negative finding is retained along with all other runs. No thresholds,
seeds, signal parameters, basis scales or E003 settings were changed in response.

The ignored output directory contains the exact config values, all fitted synthetic
models, all per-seed losses/intervals, and a manifest with dirty Git status, source file
hashes, config/lock hashes, versions and artifact checksums. Existing outputs cannot be
overwritten; failed runs record a failure type without exception payloads. These hashes
identify the executed dirty source but are not a new committed source snapshot.

Validation: 49 focused tests passed after adding the positive/null/scrambled regression
cases. Final `make check` passed lint, formatting, 276 tests and the repository boundary
check; two Linux resource tests were skipped on macOS. `make demo` passed with unchanged
synthetic NLL 2.729264271658528. No new dependency setup, server connection, clinical run,
test-set access, commit or push occurred.

This establishes only that the proposed joint features can recover the deliberately
generated pairing information. It does not establish useful signal in real histories.
With equal occurrence/availability clocks, joint terms become extra single-clock decay
scales; any real successor needs a corresponding basis control and server-local evidence
of reviewed, nondegenerate time pairs. A new clinical diagnostic/experiment remains
unimplemented and unscheduled. E003 stays closed at its failed gate, and the clinical
test partition stays sealed.

## 2026-10-19 — S002 stress controls and A001 private clock audit implemented

The user requested autonomous local work until a genuine need for UCSF data access.
Continued on base `52c49bbc37867624498ff7c0daffad9543c9df59`; the implementation and
documentation remain uncommitted. No server connection, clinical run, commit or push
occurred. E003 remains a gated negative experiment; its configuration, decision rule
and sealed test partition were not changed.

Implemented `make pairing-stress` as a separate generated-only diagnostic. It adds an
availability-basis control with the same sixteen feature dimensions: the shared
two-clock marginals plus within-availability products. When the clocks coincide,
these products exactly match the paired encoder's extra decay scales. Four scenarios
(signal, null, scrambled pairing and equal clocks) use all three existing seeds.
Each model is fitted once, then evaluated at availability delays of 0, 1, 4 and 8 hours,
without refitting or history refill. Reports include each model's deterioration from
its own unshifted loss, not only comparisons between models at the same delay.

Run `artifacts/synthetic/20261019T175100Z-pairing-7d17e45e` completed all twelve cases;
its artifact checksums were verified. Original unshifted S001 comparisons reproduced.
The following results are **synthetic-only**, descriptive means across three seeds:

| Scenario | Paired minus availability-basis NLL, unshifted | Paired NLL increase, 1h delay | 4h delay | 8h delay |
| --- | ---: | ---: | ---: | ---: |
| Pairing signal | -0.264834 | +0.411565 | +1.260665 | +1.260665 |
| Null | +0.000747 | +0.043001 | +0.277758 | +0.277758 |
| Scrambled pairing | +0.002890 | +0.027329 | +0.160410 | +0.160410 |
| Equal clocks | 0.000000 | +1.267607 | +83.151471 | +1276.416180 |

These are adverse robustness findings. Equal-clock paired/basis features and fitted
predictions coincide exactly before perturbation. Shifts move the fixed models outside
the narrow generated training support and can produce severe deterioration. The toy
pairing gain does not establish robustness, clinical utility or a reason to reopen E003.
No seeds, scales, parameters or thresholds were tuned after seeing these results.

Implemented A001, `ies clock-audit run`, with a clean-commit Slurm entry point and
`scripts/server.py plan/submit clock-audit`. This descriptive prerequisite reuses
existing private cohort/history artifacts. It verifies manifest/QC bindings, completed
history coverage, unchanged artifact digests, patient isolation, identities and time
consistency. Cohort projection reads only patient/order identity and split metadata;
only training histories are selected for aggregation. No outcomes are projected,
models fitted, validation/test features evaluated, raw sources scanned or rows saved.
Whole-file hashing and shared Parquet pages may touch nontraining bytes; this is not
a claim of physical byte isolation between partitions.

Private counts describe coincident versus delayed clocks, retained history coverage,
the sequence cap, and same-kind pairs permitting a valid marginal-preserving swap.
They are not a model gate, power calculation or population claim. Missing swaps exclude
only this retained-history contrast; positive counts do not establish useful signal or
replace reviewed timing semantics. All counts and reports stay on UCSF. The tool emits
only operational status, suppresses private exception payloads, and never exports data.

Fixed bounds are 2 CPU, 4,096 MiB and a 300-second worker, with a 5-minute-30-second
Slurm allocation; at most 20,000 cohort and 500,000 history rows, 256 MiB per Parquet
and 512 MiB declared uncompressed row-group bytes per file. Automatic artifact discovery
examines at most 1,000 direct job entries and 16 MiB of fixed-location manifests. It
requires exactly one digest-bound compatible pair and refuses to guess among candidates.
Submission persists a private receipt before monitoring the exact scheduler job ID.
Monitoring verifies successful artifacts, never retries or cancels a job, and leaves
an interrupted or timed-out job unchanged. Docs/16 contains commands using a separate
clean job checkout and the existing Python environment; no server coding agent is needed.

Validation: 52 focused tests passed. Final `make check` passed Ruff lint, formatting
(119 files), 307 tests and the repository file-boundary check; two Linux resource tests
were skipped on macOS. Generated tests cover clock/identity failures, train-only
projection, patient separation, input mutation, resource failures, artifact discovery,
sanitized output and mocked submission/monitoring. `make demo` passed with unchanged
synthetic NLL 2.729264271658528 in `artifacts/synthetic/20261019T175428Z-df2f4fdd`.
The full `make pairing-stress` run passed execution checks; its negative scientific
findings above remain unchanged. Slurm shell syntax and `git diff --check` passed.

A001 has not run on UCSF. The next research-dependent step needs real retained training
histories to determine whether reviewed time pairs provide the variation being studied.
That evidence cannot be inferred from synthetic fixtures. A successor clinical design
remains unimplemented and unscheduled. Publishing this verified work requires the user's
explicit commit/push instruction under AGENTS.md; a formal job requires that clean commit.

## 2026-10-19 — User authorized publication for operator-run UCSF audit

The user explicitly requested commit/push, followed by running the prepared commands
on UCSF and returning approved feedback for Mac-side fixes. Fetched `origin/main`;
it remained at `52c49bbc37867624498ff7c0daffad9543c9df59` with no divergent commits.
The reviewed publication set contains source, generated tests, fixed synthetic config
and documentation only. Existing private inputs and clinical results are not included.
The operator instructions reuse the installed environment with `uv --no-sync` and a
separate clean job checkout. Publication uses the repository's checked, ordinary-push
workflow and generates a handoff pinned to the resulting commit. A001's real UCSF run
remains pending; publication is not evidence that the audit ran or passed.

## 2026-10-19 — A001 operator-reported UCSF execution complete; private review pending

Published implementation commit `14b8d6913d059774ca7fb6f97140eef4eec63416` after
307 passing tests, two macOS-skipped Linux resource tests, repository checks and the
unchanged synthetic demo. The user then confirmed a clean detached job checkout at
that commit, successful server preflight and bounded automatic artifact discovery.
The supplied operational return reports Slurm job `39325` submitted and the monitor
returning `status: complete` with `private_review_required: true`. Under the published
monitor contract, that return requires scheduler success and artifact mode, source
commit and report-checksum verification.

This is user-provided operational evidence; no Mac connection, restricted artifact
download or independent inspection of clinical results occurred. It establishes that
the audit executed and passed its operational checks, not the presence of nondegenerate
clock pairs, adequate samples or predictive benefit. Private report review is the next
step on UCSF. Do not resubmit this completed job, reopen E003, access test outcomes or
start a successor model on the basis of execution success alone. Only locally approved
operational/research conclusions may be returned; counts, records, evidence references
and private reports remain on authorized server storage.

## 2026-10-19 — A001 feedback does not support the retained-history pairing contrast

Following job 39325 at `14b8d6913d059774ca7fb6f97140eef4eec63416`, user feedback indicates
that both event types' retained training clocks coincide at the audit resolution and
the proposed distinct valid pair-swap contrast has no support. Only this qualitative
disposition is recorded; the restricted report payload, counts, private mapping and
time-evidence references are not copied into repository files or generated fixtures.
No UCSF connection, new extraction, model fit or additional clinical job occurred.

This is a finding about the audited retained training histories, not a claim of exact
timestamp identity in every source, absence of real-world documentation delay, complete
population coverage or the behavior of uninspected validation/test histories. Missing
histories and the retained cap bound interpretation. The audit alone cannot separate
mapping-policy effects, reviewed exclusions, source behavior and history selection.
Source review confirms that the administration extractor supports a reviewed equality
policy, while order times are separately mapped logical concepts. No server mapping
contents or active evidence classifications are inferred or changed.

Disposition: do not advance the current pairing successor on unchanged artifacts.
Retain E003's frozen negative decision and S001/S002's synthetic results. Do not seek
a contrast by manufacturing clinical delays, changing semantics, relaxing retrospective
exclusions, expanding history caps or rescanning data. No replacement clinical design
or GPU work is scheduled. A separately defined single-clock workflow question remains
only a possible direction; it would need controls, an explicit information set and an
evaluation plan addressing already-inspected E003 validation. It is not evidence that
the original intent/execution/state architecture is identifiable from current features.

The Mac review also made an existing E003 limitation concrete: at exactly equal clocks,
its per-type features duplicate the two configured decay bases, whereas the other
model uses four different scales. A single total coefficient split across two identical
standardized columns has half the effective ridge penalty of a unique column at the
same nominal ridge. Added a wholly generated regression test of the implied fitted
coefficient and hazard equivalence; it does not refit clinical data or alter production
penalties, features or thresholds. The conditional algebra and interpretation are in
docs/08; docs/11 records the research disposition. Current status and operator guidance
now explicitly avoid repeating the completed audit.

Checks: 48 focused model, pairing and audit tests passed. `make check` passed Ruff lint,
formatting (119 files), 308 tests and the repository file-boundary check, with two Linux
resource tests skipped on macOS. `git diff --check` passed. Production code and the
pipeline are unchanged, so the previously verified demo and synthetic stress runs were
not repeated. Changes are local on base `14b8d69`; no commit or push occurred in this step.

## 2026-10-19 — W001 fixed-data workflow development experiment implemented

The user explicitly authorized changing research direction because the existing source
data cannot be added to or modified and further semantic explanations are unavailable.
W001 therefore reuses the reviewed cohort, first-execution/competing-event/censoring
labels and retained order/administration histories. It changes neither source semantics
nor artifacts, windows, history caps or original splits. It does not schedule the failed
pairing contrast, reopen E003 or require a server coding agent. The design is frozen in
docs/11 and `configs/workflow_cv.yaml` before any W001 clinical execution.

Implemented four fixed CPU models: time-bin intercepts alone, retained counts, counts
plus pooled timing, and counts plus type-specific timing. Five deterministic patient
folds use only original training patients; normalization and fitting exclude the held-out
fold. Original validation/test outcomes and history features are not used for analysis.
Identity metadata verifies split separation; file hashing and shared Parquet pages are
not physical byte isolation. Outputs include every model/fold and paired patient-bootstrap
contrasts conditional on the fitted folds. Those intervals omit model-fitting, shared-fold
training and design-selection uncertainty. The data-informed pivot is exploratory, not
independent confirmation. Feature capacities and effective ridge penalties differ.

The fixed primary contrast is typed minus pooled timing. Its development support flag
requires mean NLL improvement of at least 0.005, conditional interval upper bound below
zero, improvement in at least four folds and better mean NLL than the intercept control.
This is an engineering screen, not a clinical benefit threshold. Joint NLL includes all
causes; improvement alone cannot establish execution-probability calibration. Missing
nonexecution terminal causes are retained with the existing head's near-zero hazards;
fold training still requires execution events. Cause-specific calibration and independent
validation remain unimplemented. No support outcome automatically opens test or GPU work.

Implemented bounded artifact loading, digest binding, private output, clean-commit Slurm
submission, unique existing-artifact discovery and exact-job monitoring. Input bounds
match A001; computation uses the existing model-job budget of two CPU, 4,096 MiB and
1,200 worker seconds, with a 20-minute-30-second Slurm allocation. Aggregate metrics and
fold weights stay on UCSF; no prediction rows, terminal clinical metrics or automatic
downloads are produced. Workers suppress private exception payloads. Submission records
a private receipt before monitoring; interruption never cancels or resubmits a job.

Generated verification uses equal occurrence/availability clocks throughout, four
mechanisms and seeds 20261019, 20261020 and 20261021. All 12 cases completed in
`artifacts/synthetic/20261019T183526Z-workflow-60b3928c`; its manifest's artifact,
configuration and source hashes were verified against the final implementation.
Mean NLL contrasts across the three generated seeds (negative is better) were:

| Generated mechanism | Counts minus intercept | Pooled minus counts | Typed minus pooled |
| --- | ---: | ---: | ---: |
| Volume signal | -0.185160 | +0.003303 | +0.000157 |
| Pooled timing signal | 0.000000 | -0.172777 | +0.013210 |
| Type-specific timing signal | 0.000000 | +0.006560 | -0.187197 |
| Null | 0.000000 | +0.007009 | +0.000615 |

These generated checks show recovery of the intended information contrasts. Extra timing
or type-specific capacity also worsened mean performance when it carried no added signal;
the negative controls are retained. They do not establish clinical usefulness, power,
novelty, calibration or independence of all orders. A separate computational rehearsal
used 20,000 generated orders and 480,000 generated history rows, completing in about
3.28 seconds with about 320 MiB peak process RSS on the Mac. It duplicated generated
patterns with distinct synthetic identifiers to exercise input size; it is a resource
rehearsal, not performance evidence or verification of Linux address-space limits.

Final review caught and corrected the new CLI's missing private-command dispatch guard:
failed/limited worker results now yield exit code 2, and exceptions cannot take the
synthetic command's payload-bearing error path. Generated regression cases cover success,
both failure statuses and several exception types; no real data was involved.

Checks: 45 focused workflow/clinical-boundary tests passed. Final `make check` passed
Ruff lint, formatting (127 files), 353 tests and the repository file-boundary check;
two Linux resource tests were skipped on macOS. Tests cover grouped fold separation,
train-only normalization and label projection, poisoned unused held-out values,
censoring/competing causes, temporal and identity failures, incomplete/mutated inputs,
resource failures, private serialization, discovery, submission and result integrity.
`make demo` passed with unchanged synthetic NLL 2.729264271658528 in
`artifacts/synthetic/20261019T183526Z-2b94e758`. Slurm shell syntax and `git diff --check`
passed. All runs used generated data on base `14b8d69` with the working tree marked dirty;
there was no UCSF connection, new source scan, clinical W001 run or GPU use.

The remaining research-dependent step is one bounded W001 run on existing UCSF artifacts.
The user's earlier explicit publish/operator-run/feedback workflow supplies the handoff
authorization; the release contains code, generated tests and documentation only. A
clean release commit and pinned handoff identify the server entry version. Real W001
performance remains unknown and must not be inferred from these local checks.

## 2026-10-19 — W001 operator-reported UCSF execution complete; research review pending

The user reported a clean detached checkout of published commit
`9fcdc32f3200931c780e0931130a3a07fc20ddaa`, successful preflight and the fixed W001 plan.
Slurm job `39332` was submitted and the monitor returned `status: complete` with
`private_review_required: true`. Under that version's monitor contract, this requires
scheduler success, the expected source/mode/data classification, validation/test flags
remaining false, and report/model/config checksum verification.

This is operator-provided execution evidence, not independent Mac access or evidence
of predictive benefit. No research metrics or private artifacts were supplied or copied
here. All four models and five development folds ran under the fixed original-training
scope; the next step is read-only review of the existing private result. Do not resubmit
W001, change thresholds, open held-out evaluation or start GPU work based on completion.
No source scan, clinical artifact transfer or model execution occurred on the Mac.

Updated current operational status and prepared a bounded, read-only report-review
command pinned to job 39332 and its source commit. It locates the exact submission
receipt, verifies the report binding and emits only fixed qualitative conclusions;
counts, metric values, identifiers, weights, logs and private paths remain on UCSF.
No commit or push is needed for the operator to run the inline command against the
existing clean job checkout. Research conclusions remain pending authorized feedback.

Verification of the exact inline command used ten generated-only cases: supported and
unsupported flags, wrong source commit, sanitized configuration exceptions, altered
report checksum, invalid flag type, nonfinite metrics, duplicate matching receipts,
unexpected test-evaluation flag and the discovery bound. All passed; snapshots confirmed
the command wrote no artifact files. Shell syntax, `git diff --check` and the repository
file-boundary check passed. Production code is unchanged, so model tests and synthetic
training were not repeated. Status/documentation changes remain local on `9fcdc32`.

## 2026-10-19 — W001 primary hypothesis unsupported; existing secondary evidence review

The user returned the qualitative review of job 39332 at
`9fcdc32f3200931c780e0931130a3a07fc20ddaa`, with report verification confirmed. The fixed
type-specific timing development support flag is false. Mean loss is higher for typed
than pooled timing, lower for counts than intercept, lower for pooled timing than counts,
and lower for typed timing than intercept. These are operator-reported qualitative
directions; no numerical losses, intervals, fold patterns, private identifiers or other
clinical artifacts have been supplied to or inspected by the Mac.

Disposition: retain W001's negative primary result and stop advancing the typed timing
hypothesis on this evidence. The favorable secondary mean directions do not establish
stability, magnitude, calibration, clinical usefulness or a novel contribution. They do
not turn W001 into a successful primary experiment. The next step only reads the already
computed conditional intervals and fold directions for all four predefined contrasts.
No new threshold, feature, model selection claim, bootstrap, fit, held-out evaluation or
GPU job is introduced. E003 and A001's prior negative findings remain unchanged.

Replaced the long operator-pasted Python with `scripts/server.py review workflow-cv`
and `scripts/review_workflow.sh`. Review binds an exact existing job receipt and its
original source commit separately from the clean reviewer commit. It checks complete
manifest state, report/config/model checksums, original partition flags, fold identities,
finite summaries, intervals and consistency of the original support rule. It emits only
allowlisted qualitative findings. Secondary summaries are descriptive; there is no new
secondary pass rule. Zero-touching intervals include zero. The command does not submit
or query a scheduler, decode source rows or model weights, train, resample, or modify any
clinical artifacts. Bounds are 1,000 direct job entries, 16 KiB per receipt, 1 MiB per
report/config and 64 MiB for model-file hashing. Errors use fixed codes, not payloads.

Generated integration tests initially caught a JSON/YAML parser mismatch in the new
reader: JSON scientific-notation floats could become strings under YAML parsing. The
reader now parses the JSON snapshot as JSON and reuses the extracted config validator;
the original YAML training configuration and validation rules are unchanged. No clinical
job ran with this new reader, and no existing W001 result is altered by the correction.

Validation: 70 focused workflow/model-boundary/review tests passed, including 25 new
review cases; the strengthened read-only file-open check also passed. `make check`
passed Ruff lint, formatting (129 files), 378 tests and repository boundary checks, with
two Linux resource tests skipped on macOS. Tests verify qualitative boundary cases,
unchanged artifact snapshots, no row/fitting/submission access, source and digest binding,
malformed reports, discovery limits, mutations, sanitized errors and the CLI's early
read-only return. A generated shell rehearsal verified spaced paths, reuse of original
config/environment and exact review arguments. Shell syntax passed. `make demo` retained
synthetic NLL 2.729264271658528 in `artifacts/synthetic/20261019T190817Z-cc9c8168`.

Publication follows the user's explicit publish/operator-run/feedback workflow. Only
source, generated tests and operational/research documentation are included. The next
server action is one bounded read of the completed report using a separate review checkout,
not a repeat of job 39332. Actual secondary uncertainty and fold evidence remain pending.

## 2026-10-19 — W001 qualitative review complete; W002 frozen diagnostics implemented

The user returned the read-only review for original job `39332` at source
`9fcdc32f3200931c780e0931130a3a07fc20ddaa`, using reviewer
`5836dbc90bb71275ad04d009fbc2d007dca902f5`. Artifact verification passed; original
validation/test were not evaluated, and the typed-timing support flag remains false.
The approved qualitative feedback is:

| Predefined W001 contrast | Mean loss | Conditional interval | Fold directions |
| --- | --- | --- | --- |
| Counts minus intercept | Lower | Includes zero | Mixed |
| Pooled timing minus counts | Lower | Below zero | All lower |
| Typed timing minus pooled | Higher | Includes zero | Mixed |
| Typed timing minus intercept | Lower | Below zero | All lower |

Interpretation: pooled temporal summaries have consistent exploratory incremental
evidence relative to counts in this development analysis. Counts alone are not
consistently better than intercepts; type-specific timing has no supported incremental
benefit under the original rule. An interval including zero does not establish
equivalence or prove types harmful. Typed versus intercept does not isolate the value
of type-specific timing. No numeric magnitude, clinical benefit or independent
confirmation follows from the shared directions. Conditional intervals omit fitting
and data-informed selection uncertainty. Preserve W001's negative primary and E003's
negative validation result; no tuning, original validation/test evaluation or GPU work.

Implemented W002, explicitly post-selection and without an advancement gate. It binds
the original W001 receipt/SHA, models, configuration and existing cohort/history
digests; verifies patient folds, training-assignment hashes and normalization; and
reproduces all original per-fold and overall likelihood losses without fitting. All
four models remain included. It adds a direct descriptive pooled-versus-intercept NLL
contrast using the same conditional bootstrap draws, not an inferred interval from
the other comparisons or a replacement primary endpoint.

Frozen cause-specific hazards now yield first-execution cumulative incidence at fixed
1/4/12/24-hour horizons, accounting for both competing causes. Earlier right censoring
leaves the binary outcome unknown. Brier completion bounds, paired Brier differences
using a common unknown label, and fixed-bin empirical calibration ranges introduce
no additional censoring-independence assumption. They are finite-sample descriptions,
not confidence intervals, population calibration tests, effect-size claims or a new
estimator contribution. Inside a completion range is not proof of calibration;
outside alone is not statistical evidence of population miscalibration. This does not
remove assumptions from the original fitted likelihood. Detailed specification and
primary methodological references are in docs/11.

The new `workflow-diagnostics` entry reuses the bounded training-only reader, runs
under 2 CPU / 4,096 MiB / 300 worker seconds (Slurm 5:30), and writes only a private
aggregate report and manifest. No new model weights or prediction rows are persisted,
no original source is scanned, and held-out labels/features remain unread. The
`diagnose_workflow.sh` wrapper reuses the original environment/config and combines
preflight, plan, submission, monitoring and allowlisted qualitative feedback. There is
no automatic retry or result download. Exact original job/SHA and artifact mismatch
stop execution. Malformed JSON object types now fail with fixed operational errors
when the shared receipt finder is called directly by the new server entry.

Validation: 85 focused tests passed. Final `make check` passed Ruff lint/format
(135 files), 414 tests and the repository boundary check; two Linux-only resource
tests remain skipped on this Mac. Tests cover analytic probability mass and competing
risks, exact horizon ties, early censoring, exhaustive binary completion bounds, paired
label consistency, no-refit replay, fold/normalization/weight/input changes, original
interval reproduction, private permissions, suppressed exception payloads, worker
limits and serialized arguments, submission/monitor routing and sanitized receipts.
Both new shell files pass syntax checks. `make demo` retained synthetic NLL
2.729264271658528 at `artifacts/synthetic/20261019T192218Z-5da71c32`.

`make workflow-demo` completed all 12 generated cases at
`artifacts/synthetic/20261019T192200Z-workflow-e04f044b`, now including frozen W002
reports. All replays passed with no further fitting, including negative/null controls.
Source/config/dependency and all artifact hashes were independently verified. Generated
fixture creation still fits W001 models; this is separate from the no-fit diagnostic.
The generated mechanisms and W001 contrast values are unchanged. Synthetic results
are not clinical evidence or Linux resource-cap verification.

Publication follows the user's existing explicit publish/operator-run/feedback
instruction. Only source, generated tests and approved qualitative/operational docs
are included. **No real W002 job has run.** The remaining dependency is one bounded
replay of existing UCSF artifacts by the operator in a new clean checkout. No new data,
semantic explanation or server coding agent is needed. Original W001 outputs and
running/old checkouts must not be edited; test remains sealed.

## 2026-10-19 — W002 completed; mixed horizon findings close this development analysis

The operator reported diagnostic job `39333` complete at entry source
`1df32744dcbcd2aebaa89174fee1de546f4ddd2a`, binding original W001 job `39332` at
`9fcdc32f3200931c780e0931130a3a07fc20ddaa`. Preflight and the bounded plan passed.
The monitor returned a complete verified report and allowlisted qualitative diagnostics;
the summary requires successful frozen-model replay. No models were fitted, no raw
sources scanned and no original validation/test outcomes or features evaluated. The
Mac did not connect to UCSF or receive private reports, rows, weights or metric values.

The four original NLL contrasts retain the W001 qualitative findings. The new post-hoc
pooled-minus-intercept contrast has lower mean loss, a conditional interval below zero
and all five fold losses lower. This strengthens the descriptive baseline comparison,
not W001's failed primary or independent confirmation. No numerical magnitude was shared.

The returned paired execution-probability Brier completion bounds are:

| Contrast | 1 hour | 4 hours | 12 hours | 24 hours |
| --- | --- | --- | --- | --- |
| Counts minus intercept | Above zero | Below zero | Below zero | Below zero |
| Pooled minus counts | Below zero | Above zero | Above zero | Above zero |
| Pooled minus intercept | Below zero | Below zero | Below zero | Includes zero |
| Typed minus pooled | Above zero | Above zero | Above zero | Above zero |
| Typed minus intercept | Below zero | Below zero | Includes zero | Includes zero |

Each range concerns binary completions of early-censored outcomes in the current
sample, pairing the same unknown label between models. It is not a sampling interval
or a population significance statement. An interval including zero leaves the direction
unresolved by these bounds; it does not establish equality. Conversely, an interval
entirely above/below zero does not establish a useful magnitude or population ranking.

All four models' empirical mean predicted probabilities are below the event-fraction
completion range at 1 hour, above at 4 hours, and inside at 12/24 hours. This is an
overall sample description, not a calibration-bin assessment or population test.
Inside does not establish calibration. The operator did not share numerical gaps,
unknown-outcome counts, bin-level results or private source semantics; do not infer them.

Code review confirms the compared objectives differ: NLL scores joint event time/cause
and the censoring contribution, whereas horizon Brier errors score execution by a
single horizon. A local, entirely invented two-order analytic check verified opposite
rankings without fitting or clinical inputs: both events occur at time 1, with causes
1 and 2, and constant hazards A=(0.2,0.7,0.1), B=(0.5,0.1,0.4). The closed-form mean
NLL is `1 - log(lambda_1 * lambda_2)/2`; 4-hour execution probability is
`lambda_1 * (1 - exp(-4))`. A has lower NLL but higher squared probability error than
B, matching the production functions. This is a mathematical counterexample only;
it does not diagnose the mechanism behind the actual clinical rankings or establish
data error, misspecification or censoring bias. No implementation change was justified
by the supplied directions.

Disposition: the specified W001/W002 analysis is complete, with partial descriptive
temporal-information evidence and adverse/mixed horizon results. These findings do not
establish a common winner across reported objectives/horizons, a calibrated clinical
predictor, a validated architecture contribution or a successful original primary. Stop advancing type-specific
timing under this protocol. Do not pick the favorable 1-hour result as a new primary,
recalibrate, retune, open the original held-out partitions or resubmit unchanged jobs.
No further server action or missing-data request is needed to conclude these questions.
Any separate future study would need a distinct fixed target and evaluation design;
none is scheduled or implemented by this record. The original broader research aim
has not been achieved merely because this development analysis is complete.

Updated the working agreement, overview, README, fixed design, operator instructions
and server handoff template. Archived W002's execution commands and retained both
positive and negative findings. This change is documentation only; models, thresholds,
data readers, CLI behavior and diagnostic calculations are unchanged. The 36 focused
diagnostic/clinical-boundary tests passed, including analytic probability checks,
exhaustive censoring completions, no-refit replay and input/output binding. Publication
uses the existing authorized milestone workflow. `make check` passed Ruff lint/format
(135 files), 414 tests and the repository file boundary check; two Linux-only resource
tests remain skipped on macOS. `git diff --check` passed. No new full synthetic pipeline
run was needed for this documentation-only change, and no new clinical job was submitted.


## 2026-10-19 — R001 autonomous research pivot, implementation and generated evidence

The user delegated research direction, implementation, verification and preparation,
retaining responsibility only for running UCSF commands. Continued the earlier explicit
push/run/feedback workflow; no request for a server coding agent or more data/semantics.
Entry source: `34f602a87516d3ddb3b77f50a0db837e07409481`. No UCSF connection or clinical
artifact download occurred. W001/W002 remain complete with all negative/mixed findings.

Reviewed primary literature (docs/02), including SurvivalBoost, censoring-sensitive
Brier evaluation, proper survival scoring and a very recent partial-identification
preprint. General workflow signal, metric ranking disagreements and shared-outcome
paired bounds are not new contributions. Chose a narrow empirical question rather than
claiming a new scoring rule or architecture. R001's fixed protocol is in docs/11;
`configs/workflow_selection.yaml` SHA256 is
`437efcf7bbfb49f26b26a107b60d835f1c08ad875a78abd906898fc0e2909206`.
It remains a data-informed exploratory study, with no clinical or publication gate.

Implemented a shared eight-candidate PH/tree bank and two inner selection objectives,
three fixed seeds of 5x3 patient-nested CV, training-only preprocessing/splits,
equal-patient/equal-horizon primary comparison, coherent multi-horizon completion bounds,
NLL cause decomposition, order-weighting sensitivity and conditional bootstrap endpoint
percentiles. The independently implemented depth-two survival tree relaxes linear/PH
assumptions but is not state-of-the-art or capacity matched. All candidate/seed/horizon
results and negative directions are retained. No original validation/test feature or
outcome evaluation, new source, raw scan, history enlargement or GPU is introduced.

The completion implementation enumerates monotone first-execution trajectories, shared
across compared models. Exhaustive small-case checks verify its bounds; paired bounds
can be narrower than separately completed horizons. A deliberate outer-outcome mutation
test verifies that inner selection cannot use outer-fold labels. Generated artifact tests
keep deliberately invalid held-out labels/features unread, bind the original W001 job's
population manifests, detect input mutation, preserve private permissions, reject scope
changes, enforce worker limits and suppress private exception payloads. No actual records
were used in tests. The upper-bound objective is explicitly not proper probability
scoring: with all labels unknown it favors .5 irrespective of the latent event probability.

New operational path: `scripts/run_selection.sh` -> preflight/plan/Slurm/wait, bound to
original W001 job 39332 and its source. It reuses the existing Python environment and
private config. Worker 2 CPU/4 GiB/1200 seconds, same artifact byte/row bounds. Private
outputs include complete numerical report, models, exact config, checksummed manifest
and `paper_tables.md`; no prediction rows or patient IDs. Terminal returns only fixed
candidate names and qualitative comparisons. No automatic retry or source expansion.
Prepared the related-work comparison, explicit stopping rules and manuscript methods/
claims ledger. Clinical quantitative results and institutional manuscript details remain
pending and must stay on authorized UCSF storage.

Generated full benchmark completed at
`artifacts/synthetic/20261019T194338Z-selection-74420522`: 30 cases, each with three
nested-CV seeds (90 evaluations), five mechanisms, three data seeds, two censoring
regimes, 240 patients and 1–3 orders/patient. All known complete-outcome errors were inside
the recorded completion bounds. Manifest records exact source file hashes, dirty Git
state, config/dependencies, timings and output digests; metrics SHA256
`e003e5e0c9cecc6e8c11433f564a68138646f6cba76f5027b0827835fe40d4c8`.

Generated primary oracle error differences below are `upper_brier minus joint_nll`,
averaged over nine data/CV seed combinations per row. “Lower/higher/equal” counts concern
known synthetic latent outcomes only. Seeds reuse data and these are not inference tests.

| Generated mechanism | Censoring | Mean oracle difference | Lower / higher / equal | Completion range includes zero |
| --- | --- | ---: | --- | ---: |
| Execution signal | Administrative only | +0.000129 | 2 / 4 / 3 | 3/9 |
| Execution signal | Feature dependent | -0.001841 | 6 / 3 / 0 | 9/9 |
| Competing signal | Administrative only | +0.000460 | 4 / 5 / 0 | 0/9 |
| Competing signal | Feature dependent | +0.002318 | 2 / 7 / 0 | 9/9 |
| Nonlinear execution | Administrative only | +0.000014 | 4 / 5 / 0 | 0/9 |
| Nonlinear execution | Feature dependent | +0.029062 | 0 / 9 / 0 | 9/9 |
| Time-varying execution | Administrative only | 0 | 0 / 0 / 9 | 9/9 |
| Time-varying execution | Feature dependent | +0.002344 | 2 / 6 / 1 | 9/9 |
| Null | Administrative only | +0.000415 | 2 / 6 / 1 | 1/9 |
| Null | Feature dependent | +0.000243 | 3 / 6 / 0 | 9/9 |

These are material negative findings: conservative selection often worsens true error,
and all feature-dependent-censoring comparisons leave the completion contrast unresolved.
In the administrative-only time-varying cases both policies select the same candidates.
Do not describe the new criterion as an improved method. The clinical job will characterize
this comparison on the existing data, not validate a claimed simulation winner; the bank,
weights and endpoints were not revised after observing these outcomes. If the clinical
results add no useful distinction, close as a reproducible negative report rather than
expand the search. Broad theoretical/publication novelty remains unestablished.

Generated capacity profile (`scripts/profile_selection.py`): 19,999 orders, 479,976 history
events, all 480 fits, 34.86 seconds and 609.73 MiB peak RSS on this Mac; serialized report
197,586 bytes and models 155,964 bytes. This excludes production Parquet-read overhead and
does not verify Linux resource limits or guarantee clinical convergence/runtime. Existing
server limits remain hard. No clinical data or sampling inference comes from this profile.

Verification before release: full `make check` initially passed 446 tests with two
Linux-only skips; `make demo` passed at `artifacts/synthetic/20261019T194346Z-1e381999`;
`make selection-demo` completed all 30 cases. Added the explicit all-unknown improper-score
regression after reviewing the adverse generated results; final release checks are recorded
below. Shell syntax and diff whitespace checks passed. No dependencies changed.

Actual clinical R001 state: **not run**. The sole remaining external dependency is one
fixed, clean-commit UCSF job using existing artifacts. No private numerical R001 finding,
accepted manuscript, independent confirmation or deployment readiness is claimed.

Final pre-commit verification: `make check` passed **447 tests, 2 Linux-only skips**,
Ruff check/format passed for 145 Python files, repository boundary check passed; the
additional regression changed tests only. Production source and fixed config match the
completed full generated benchmark. No new clinical run occurred. The release publisher
will rerun required checks and generate a handoff pinned to the actual clean commit.


## 2026-10-19 — R001 job 39335 completed; close the fixed selection-policy question

The operator returned the transcript of the fixed checkout
`21762073fe9aff38dfb37d9feddc54e9205fe1fa`: preflight passed, planning reported the unchanged
three-seed, 5x3 nested patient-CV, eight-candidate, 480-fit design, and job `39335` was
submitted and completed. The automated monitor returned `status: complete` with verified
artifacts and qualitative selection feedback. This is operator-reported execution; the
Mac did not connect to UCSF or inspect/download private outputs. Original W001 job
`39332` and source `9fcdc32f3200931c780e0931130a3a07fc20ddaa` bound the existing population.
Original validation/test evaluation and raw scans remained false, with no GPU use.
Execution succeeded; R001 has no prespecified clinical advancement or publication gate,
so do not mislabel this as a failed software job or invent a new pass/fail threshold.

The fixed primary comparison is `upper_brier minus joint_nll`, equally weighting patients
and horizons. Only the allowlisted qualitative findings below were received; private
numerical effects, counts, predictions, models, logs and bootstrap endpoints stay at UCSF.

| Seed | Patient-weighted primary completion range | Order-weighted sensitivity | Joint NLL direction |
| --- | --- | --- | --- |
| 20261020 | Includes zero | Includes zero | Lower |
| 20261021 | Above zero | Above zero | Higher |
| 20261022 | Includes zero; identical policy predictions | Identical policy predictions | Equal |

At 20261020, upper-bound selection uses PH typed timing rather than PH pooled timing in
the third outer fold; the other folds match NLL selection. Its horizon ranges are above
zero at 1 hour, below zero at 4 hours, and include zero at 12/24 hours. At 20261021 the
fourth fold instead changes PH typed timing to PH pooled timing; other folds match.
Its horizon ranges are below zero at 1 hour and above zero at 4/12/24 hours. At 20261022
all folds select PH pooled timing under both policies. Because both policy paths reuse
the same fitted candidate predictions, this establishes identical predictions in that
run, rather than merely failure to distinguish different predictions. All horizon
ranges include zero and NLL is equal. No shallow-tree candidate was selected; this is
specific to the fixed bank/criteria and does not establish that nonlinear models fail.

Interpretation: no demonstrated primary advantage for upper-bound selection. The first
seed leaves the sample contrast unresolved, the second is adverse throughout its reported
completion range, and the third has no policy difference. Above-zero completion bounds
are not a population confidence statement or significance test. Seeds reuse patients;
do not treat them as independent replications or average signs to infer a pooled effect.
Do not promote favorable individual horizons or the first seed's lower NLL to a positive
primary finding. Magnitudes and private endpoint percentile summaries were not received,
so no claim about their size, clinical relevance or population calibration is possible.

Decision under the existing stopping rules: close this fixed selection-policy development
question and preserve the negative/mixed report. No new model search, tuning, recalibration,
source expansion, semantic request, repeated job or original held-out evaluation is
scheduled. Existing E003/A001/W001/W002 findings are unchanged. Prior exploratory workflow
signal is not proof of a publishable new method and is not invalidated by this comparison.
The qualitative manuscript now has results, discussion and a conclusion; the private
numerical tables are already available for authorized institutional assembly without
another fit. It remains a draft with missing numerical/institutional presentation, not a
submission-ready paper or an established publication opportunity. No automatic pivot
is justified simply to keep searching for a favorable result on the same fixed data.

Updated current status, experiment disposition, manuscript, operating guide, AGENTS and
handoff template. The latter now explicitly has **no server task** and distinguishes the
actual job source from later documentation commits, preventing accidental reruns. No
model code, frozen configuration, tests or original private job checkout changed.
Documentation-only verification and release checks are recorded below; no clinical or
synthetic experiment was rerun to create new research evidence.

Documentation verification: `tests/test_handoff.py` passed **15 tests**; `git diff --check`
and the repository file-boundary check passed. Reviewed the qualitative tables against
the supplied monitor output, checked current documents for stale R001 pending-run
instructions, and preserved the original protocol/configuration and historical log entries.
No new tests were needed for these text-only changes. The ordinary publisher will run
its required full checks and generate a clean-commit completion handoff before pushing.

## 2026-10-19 — New format lead; bounded F001 probe and conditional direction assessment

After the closure, the user explicitly requested another direction assessment and
autonomous implementation, reporting that someone updated an "omar" data format on
the server. Clarification established only that it was probably a data format, not its
actual name/version/location. Fetch and remote-branch inspection found only main at
`28b7abe30f3546bdd9491c8640f0da89588f2316`, with no incoming commits. A second fetch before
release still found no incoming code. No server update was downloaded or inspected.

Reviewed primary UCSF data documentation, OMOP CDM 5.4 conventions, Matcho et al.'s
2014 conversion-fidelity study and Liu et al.'s 2026 EHR stability study; links and
conditional decisions are in docs/27. UCSF publicly lists OMOP, but that does not identify
this user's resource. Public drug-exposure schemas accommodate prescriptions and
administrations; fields alone cannot establish either event roles or actual time precision.
Generic ETL fidelity and version-stability assessment have prior art. No publication
novelty, clinical feasibility, source availability or restored old hypothesis is claimed.

Prioritize P001, paired execution-phenotype preservation under representation conversion,
only if existing source/crosswalk/version evidence supports it. P002 is conditional on
already retained comparable snapshots. Both are planned questions, not implemented row
analyses. Reference representation is not clinical ground truth; unlinked/ambiguous units
must remain in denominators. Do not guess links, availability, precision, censoring or
data coverage. E003/A001/W001/W002/R001 remain closed, with original held-out data sealed.

Implemented F001 to resolve the narrower storage/schema dependency: footer-only sampling
of an explicitly authorized private root, or the existing configured root by default.
The shell wrapper reuses original configuration/Python and automates preflight, plan,
clean-commit submission, waiting, result binding/checksums and categorical feedback.
Independent limits: 12 files, 100 directories, 10,000 entries, 8 MiB per footer / 32 MiB
total, 2 CPU / 4 GiB / 120-second worker, 150-second Slurm allocation. Breadth-first
directory sampling prefers one file per visited directory; it is not representative.
Bad footer decodes consume the byte budget too. Missing sources reject before submission.

Unbuffered reads request only the header/trailer/footer; Arrow receives a footer-only
in-memory container so it cannot prefetch source data pages. No rows, statistics, private
field names, paths, arbitrary metadata or exception payloads appear in feedback. Public
standard field signatures are not UCSF mappings. Empty schema-shaped generated tables
can match, intentionally demonstrating why the result never establishes populated values,
OMOP conformance, provenance, linkage, real precision or research feasibility. Unknown,
unsupported/non-Parquet and truncated samples cannot establish absence. No database
backend, host-wide scan, dependency installation, clinical extraction or new fit was added.

Verification: initial focused generated tests passed; later adding the pre-submission
missing-source regression exposed a missing Path import in its test fixture, which was
fixed. Final `make check` passed **471 tests, 2 Linux-only skips**, Ruff check/format
passed for 149 Python files, and repository boundary checks passed. The new probe has
24 generated tests, including exact read ranges/no buffered prefetch, corrupt-footer
budgets, distinct-directory sampling, non-Parquet content exclusion, empty-schema
interpretation, storage isolation, context guards, private permissions, worker limits,
failure/no-retry behavior, checksum/commit tampering, and submission/monitoring.
`make demo` passed at `artifacts/synthetic/20261019T201819Z-2308740f`.
Shell syntax and diff whitespace checks passed. No dependencies changed. Linux limits
are configured and their parameters are tested; actual Slurm execution remains unverified.

Actual F001 state: **not run**. The remaining dependency is the user's server-side
metadata probe, not another training experiment. If the new asset is outside the existing
configured root, its authorized location/access entry is essential; this implementation
does not invent it or search other projects. Only fixed categorical feedback may return;
private reports remain on UCSF. Continue with evidence from that result before choosing
a clinical protocol. Publish this verified code milestone under the user's continuing
push/run/feedback instruction, without modifying an existing private job checkout.

## 2026-10-19 — User stops the format lead; assess alternatives on original data

The user explicitly abandoned the new-format direction and asked what could be studied
with the previous data alone. F001/P001/P002 are inactive; no format probe should now be
submitted and no new source location is requested. No F001 execution feedback was received.
Updated the current status and handoff instructions locally; no new job or model was run.

Re-read the actual extraction and artifact contracts. The clinical extractor writes
execution, pooled terminal-without-execution, or right censoring. It does not preserve
separate cancellation/other-terminal reasons just because the generic model accepts more
cause codes. Existing retained histories contain two event kinds and at most 24 events.
The bounded candidate domain is not a representative population census. Scheduled dose
time, urgency, illness severity, institution-wide workload and clinical harm are not
established features. Order-to-execution time cannot be labeled an avoidable delay/error.

Two candidate applications remain more grounded than another predictor search:
(1) sensitivity of a fixed execution-rate/waiting-time question to outcome coding and
analysis definitions; (2) descriptive execution/termination/censoring trajectories in the
bounded reviewed cohort. These are proposals, not new frozen experiments or claims that
a paper is feasible. Different patient/order weighting targets are different estimands,
not automatically bias. Aalen-Johansen is not assumption-free ground truth under arbitrary
dependent censoring. Preserve unknown outcomes and sample-completion bounds, and report
the censoring assumptions needed for population claims. No old held-out evaluation opens.

Primary-source checks: [Kaplan-Meier methods yielded misleading results in competing risk scenarios](https://pubmed.ncbi.nlm.nih.gov/16980152/)
already compares alternative first-event analyses; generic competing-risk correction is
not novelty. [Medication Administration Discrepancies Persist Despite Electronic Ordering](https://pmc.ncbi.nlm.nih.gov/articles/PMC2213483/)
uses scheduled administration times and chart review, which our current artifacts do
not supply. [Lillelund et al., UAI 2026](https://proceedings.mlr.press/v337/lillelund26a.html)
studies dependent-censoring evaluation, so another censoring-sensitive score is not an
unoccupied methodological direction. This targeted review supports assessing an applied
measurement question first, with a realistic possibility of only a technical report.

No executable code/config changes were made in this turn. These are local documentation
updates; no new commit/push or server instruction is required to answer the direction
question. Documentation whitespace and repository-boundary checks are recorded with the
working-tree verification, without rerunning clinical or synthetic experiments.

## 2026-10-19 — User requires a machine-learning methods paper; broaden beyond old artifacts

The user clarified that new tasks/models may use the same original data and explicitly
requires a machine-learning methods paper. The preceding applied-analysis candidates no
longer serve as the main project. Corrected the earlier overly narrow framing: the old
one-time first-execution cohort and capped histories are not the entire original dataset.
Re-read the approved operational handoff and eligibility implementation. Direct linkage
and repeated administrations support assessing recurrent linked-event tasks; they do not
verify complete courses or new clinical labels. No private field names or counts recorded.

Reviewed primary papers on survival pretraining, temporal relational learning, object-centric
process prediction and tokenization efficiency. The sources, reading depth and limitations
are in docs/02. Ordinary contrastive learning, a graph plus Transformer, and next-event
prediction are not unoccupied contributions. Prioritize a local assessment of relation-
preserving recurrent-event learning, potentially with learned memory allocation; retain
one-to-many self-supervision and relation-preserving compression as conditional alternatives.
No new algorithm, recurrent extractor or generated benchmark is implemented in this step.
No novelty, performance gain or publishability is established by this proposal.

Updated current-status documentation and the working agreement. Preserve the old negatives,
sealed held-out data and cancelled format route. No server command, raw scan, clinical
training, data transfer, dependency change, commit or push occurred. This is documentation
and literature work only. `git diff --check` and the repository file-boundary check passed;
model tests were not rerun. New clinical work first needs a distinct design and bounded access
plan; a recurrent task cannot silently relax the existing first-event runner's exclusions.

## 2026-10-19 — M001 local implementation, full generated comparison and mixed findings

The user said to start. Implemented a generated-only relation-context allocation prototype:
`memory_data.py`, `memory_models.py`, `memory_benchmark.py`, explicit synthetic config,
CLI `ies memory-demo`, and Make target `memory-demo`. Reused the existing NumPy environment;
no dependency installation, Torch/GPU use or clinical runner changes. The new exact-name
synthetic config is included in the repository allowlist; local configs and model/data
artifacts remain excluded. No commit or push occurred; working base remains `bbbb662`.

The simulator provides recurrent linked histories with renewal, switching, shared-burst
and memoryless-null mechanisms, independent observation end and post-cutoff terminal events.
The target is next recurrence/termination for known orders, not the entire future sequence.
The small MLP handles censored categorical outcomes through allowed-probability mass.
Decoder training, utility learning and evaluation use disjoint generated patients. Full
latent outcomes are used for synthetic scoring only. All event visibility respects both
clocks. IDs cannot act as learned identity features; equal observable histories receive
symmetric allocations, potentially underfilling the budget.

The candidate learns depth-specific expected loss improvements via ridge regression and
uses exact multiple-choice knapsack for an additive utility. Neither component is claimed
as new. Compared with recent, balanced, static-utility, all-recent-depth, whole-history
summary, descriptor-direct and history-free controls. The descriptor-direct control checks
whether auxiliary prefix information already does the predictive work. Resource accounting
separates event slots from descriptors, roster/counters, parameters, scan cost and arrays;
this is offline context selection, not a bounded-RAM streaming implementation. TGN/SALoM
primary-source checks added to docs/02; these strong methods are not yet reproduced here.

Initial focused testing exposed an unquoted YAML `null` scenario interpreted as a null
value; quoted it and retained strict config validation. Analytic likelihood gradients
matched numerical derivatives. The first full `make check` passed 498 tests and 2 skips
but the file-boundary step correctly rejected the newly added config until its exact
generated filename was added to the allowlist. No broad whitelist exception was made.

Full generated run `artifacts/synthetic/20261019T204214Z-memory-d6eb4bda` completed 24
fitted cases / 48 budget comparisons (three seeds, four mechanisms, two order counts,
two budgets). No favorable-case selection or hyperparameter changes followed the results.
Mean observed-NLL improvements versus balanced context were small and inconsistent:
renewal -0.00513 (9/12 cases lower), switching -0.00164 (7/12), shared -0.00212 (8/12),
null -0.00056 (6/12). The history-free reference beat learned allocation in every null
case. The simple summary removed the renewal advantage on average. Prediction-assignment
permutation worsened the deliberately relational renewal case much more than the null;
this is a simulator check, not evidence of clinical signal. Full numerical interpretation
and limits are in docs/11; conditional bootstrap intervals omit fitting/selection uncertainty.

Initial aggregate selection-plus-decoder time was 4.360 seconds for learned allocation
versus 0.488 seconds for balanced allocation. This excludes common encoding and training
and is hardware/implementation specific. The regressor adds 315 parameters and 44 prefix
descriptor numbers per order; retained-event limits cannot be called total-memory savings.
No stable method superiority, efficiency benefit or publication readiness is established.
Keep this implementation as a mechanism benchmark; do not schedule a UCSF run to rescue
this prototype. A distinct local algorithmic contribution and stronger comparisons remain
necessary before a new clinical study. The original data's broader usefulness is unresolved.

Final accounting distinguishes per-patient array maxima from the total materialized
evaluation arrays and rejects combined simulation/DP work expansion. Reran the complete
grid at `artifacts/synthetic/20261019T204448Z-memory-c1ffc4d9`; metrics, fitted parameters
and config reproduced byte-for-byte. Verified every artifact hash and current source hash.
No clinical data, private schema, trained clinical weights or external dataset was read.

Final verification: **30 new memory tests**; focused memory/handoff checks passed 45 tests.
`make check` passed **501 tests, 2 Linux-only skips**, Ruff check/format for 153 Python files,
and the repository file-boundary check. `make demo` passed at
`artifacts/synthetic/20261019T204417Z-67bbf708`. Tests cover censored mass/gradients,
repeated-event retention, mismatched links, both clocks, row/ID/time-shift invariance,
exact allocation versus brute force, identical-history ties, zero budget, patient splits,
oracle isolation, strict combined resource bounds, source tampering, deterministic outputs,
failure status and no-data handoffs. No new server task is pending.

## 2026-10-19 — autonomous continuation and J001 exact joint-observation laboratory

The user explicitly requested continuous automatic research rather than another pause
after an unsuccessful prototype. Started an active autonomous research goal; M001 remains
closed as the main-method candidate. No new permission/direction question was asked.
Reviewed additional primary sources for future-teacher contrastive learning, partial-label
conformal prediction, censored joint scoring, point-process diffusion, ambient diffusion
and missing-data latent-class estimation. Reading depths and concrete overlaps are in
docs/02. Generic future supervision, joint censored energy scoring and diffusion are not
claimed as inventions. No literature absence claim is used as evidence of novelty.

Implemented `joint_observation.py`, `joint_demo.py`, `configs/synthetic_joint.yaml`, CLI
`joint-audit-demo`, Make target, and exact-name synthetic config allowlist. Reused NumPy;
no dependency change, GPU, external data or clinical artifact. The laboratory enumerates
225 valid two-entity recurrent/absorbing-terminal paths. Three mechanisms have equal
marginal path laws but different joint dependence. Observation is a common independent
prefix window; latent and observation RNGs are separate. Fitters accept prefix sufficient
statistics only. Exact population evaluation uses the simulator law, not latent training
labels. All four estimators are known references or an explicitly invalid zero-fill control.

The first 54-case grid completed at
`artifacts/synthetic/20261019T205703Z-joint-2d4b13f4`. At 1024 patients under short observation,
latent-class joint KL is 0.12189 versus 0.19513 for independent paths in the synchronized
mechanism, and 0.10240 versus 0.17634 in the opposed mechanism. It is worse under the null:
0.16107 versus 0.06872. At 256 patients with short observation it is also worse in both
correlated mechanisms. These are three-seed means of exact synthetic conditional risks,
not evidence of an ML contribution or clinical benefit. No settings were retuned.
Saturated joint estimation substantially overfits; its weak fixed prior and unequal
effective complexity make it insufficient as the only comparator. The latent-class family
matches the generated dependency, requiring future misspecification controls.

The observation operator has rank 49 without final-bin observation and 225 with positive
full-window support. Constructed two laws with identical observed prefixes and final-bin
marginals, but joint final recurrence probabilities 0.5 and 0.0. This verifies the local
nonidentifiability statement directly; a learned extrapolation does not cure lost support.
The exact marginal differences across mechanisms are below 6e-17. Source and all artifact
hashes were verified. Aggregate reference fitting was about 1.91 seconds, not a scaling result.

Verification: **20 new focused tests passed**. `make check` passed **521 tests, 2 Linux-only
skips**, Ruff check/format for 156 Python files, and repository file-boundary checking.
`make demo` passed at `artifacts/synthetic/20261019T205723Z-8a19ad56`. Tests cover absorbing
termination, repeated events, equivalent observed prefixes, exact nonidentifiability,
normalization, the full-observation EM closed form, independent censor RNGs, exclusion of
latent outcomes from fitting, information contraction, deterministic generated artifacts,
config/input/resource rejection, no overwrite and sanitized failure manifests.

Research remains active. Next local work: observation-adaptive dependence learning,
nearest hierarchical shrinkage/model-averaging comparisons, misspecified dependence and
dependent-observation stress tests. Those methods/stresses are planned, not implemented.
No genuine server-data dependency has been reached; no server job is requested. No commit
or push occurred; base SHA remains `bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`, with changes
in the working tree. Old negative findings, test sealing and the cancelled format task
remain unchanged. Do not mistake completion of this reference audit for completion of
the autonomous methods-research goal.

## 2026-10-19 — J002 prefix-adapted interaction candidate and adverse strong-baseline result

Continued the active goal automatically. Revalidated the worktree and J001 artifacts;
the previous goal turn was substantive progress, not a wait/blocker. Searched primary
literature on adaptive copula smoothing, censored wavelet estimation and context-tree
weighting. Closest precedents and reading depths are in docs/02. Corrected the CTW
reference's author attribution after opening the primary PDF: Vellambi and Hutter.
Generic adaptive shrinkage and censored wavelets are not claimed as new contributions.

Implemented `joint_shrinkage.py`, `joint_stress.py`, `joint_shrinkage_demo.py`, explicit
synthetic config, CLI/Make target and exact config allowlist. The candidate constructs
weighted prefix-tree contrasts and groups cross-entity interactions by the later reveal
depth. Verified the common-window information matrix: diagonal entries use observation
probability at the maximum depth, not the product of per-entity probabilities. This is
a finite direct calculation, not a claimed novel theorem or a borrowed asymptotic result.

The estimator uses independent pilot marginal estimates, centered covariance from the
remaining observed prefixes, plug-in variance shrinkage, and a single positivity
contraction. It preserves pilot marginals and leaves unsupported interaction coefficients
zero. Added global/unshrunk ablations, a standard Dirichlet-tree/global-blend reference
selected by fixed two-fold observed-likelihood CV, all-patient independent/latent-class
references, and an explicitly infeasible oracle-marginal diagnostic. The oracle is not
included as evidence of deployable performance.

Added two dependence mechanisms outside the original two-class generator, plus predictable
history-dependent and future-informative stopping. Exact evaluation distinguishes full-law
KL, observation-channel KL, and ordinary-prefix score excess. A constructed counterexample
shows the latter can reward a wrong latent forecast when stopping depends on unseen
outcomes; no score is mislabeled as a KL in that case. No observation kernel or true path
law enters the feasible fitting/selection APIs.

The first fixed 150-case run completed at
`artifacts/synthetic/20261019T210442Z-shrinkage-667c0c5e`. At 1024 patients with independent
short windows, depth grouping improved mean KL over global grouping (0.2317 vs 0.2475;
13/15 cases lower), but was worse than the tree/blend comparator in all 15 cases (its
mean 0.1845). All-patient independent/latent-class references were 0.1619/0.1542. The
candidate loses to tree/blend in 142/150 grid cases; mean excess KL is 0.04275. At 256
patients with short windows it also worsens the pilot baseline on average. Preserve all
cases, including null, small-sample and unsupported-tail results; no settings were retuned.

Marginal error remained below 4.45e-16 and unsupported nonzero coefficients were zero.
Positivity contraction was active in 75 cases; mean factor 0.64465, minimum 0.00209.
The infeasible oracle-marginal diagnostic was much better, suggesting pilot estimation
and its locked marginals are material limitations, though this ablation changes multiple
quantities. These findings motivate a joint likelihood estimator with constraints enforced
during fitting, rather than post-fit contraction. That estimator is planned in docs/11,
not implemented. The present candidate will not be sent to UCSF on these results.

Focused joint tests: **36 passed**, including **16 new J002 cases**. `make check` passed
**537 tests, 2 Linux-only skips**, Ruff check/format for 160 Python files and repository
boundary checking. `make demo` passed at `artifacts/synthetic/20261019T210504Z-4ade4a8f`.
Verified current source and all run artifact hashes. No repeated full run, dependency
change, clinical data access, test opening, server job, commit or push. Work remains on
base `bbbb662` with the Mac as sole writer. Research stays active; the next action is
local estimator/solver work, not a permission request or a server-data blocker.

## 2026-10-19 — J003 certified joint likelihood, exact information audit, J004 strong contexts

Continued the active autonomous research goal without another approval request. Implemented
`joint_likelihood.py` and its generated runner/config/CLI/Make entry. The strictly convex
simplex objective jointly adjusts marginals and interactions, uses grouped linear-contrast
penalties, and avoids J002's fixed-pilot marginals and post-fit positivity contraction.
The damped Newton solver reports a simplex dual gap; failure to certify the fixed tolerance
stops fitting. Two-fold observed-prefix CV fits all reference nuisances inside each fit
fold. Upgraded the tree/blend comparator to all-patient fitting with the same fold isolation.

Recorded the fixed protocol before full-grid inspection. Run
`artifacts/synthetic/20261019T211257Z-likelihood-cbefb2e1` completed 150 cells. All 1800
CV solver calls and selected final fits met gap <=1e-7. Reveal grouping has mean KL
0.15177 at 1024 patients under independent short windows, versus global 0.16230,
independent 0.15737 and tree/blend 0.11498. Across the stress grid it loses to tree in
108 cells, ties 21 and wins 21; mean excess KL 0.03065. At 256 patients/short windows
it also loses to independent on average. This is an adverse strong-baseline result,
not a numerical failure. No grid broadening, clinical advancement or novelty claim.
An initial ad hoc summary script incorrectly assumed JSON key order and failed after
printing valid comparison summaries; fixed the read-only analysis, without rerunning
or changing the experiment. Source/config/output hashes verified before later source work.

Reviewed primary sources on multinomial log-linear group lasso, constrained penalized
copula density estimation and censored multistate spline likelihood. Their known ideas
are not claimed as our contributions. References/reading depth are in docs/02.

Implemented `joint_information.py` and `make joint-information-demo` for an exact
simulator-kernel audit, including 28 marginal and 196 interaction score directions.
Run `artifacts/synthetic/20261019T211628Z-information-ebb50612` completed all five policies.
Under predictable stopping, different reveal depths remain orthogonal but marginal and
interaction scores within a depth couple (largest entry 0.22705); nuisance projection
reduces interaction information trace by 1.59007. Under future-informative stopping,
ordinary prefix scores have nonzero mean (max 0.06148), whereas correct known-channel
scores remain centered. No-tail full score rank is 48, interaction rank 36. None of
this supplies a test of an unknown clinical stopping mechanism. Standard MAR likelihood
and stopping-time precedents are attributed; no new general theorem claimed.

Rather than another penalty sweep, implemented stronger sequential context references
in `joint_context.py` with normalized absorbing transitions, independent/joint entity
structures, zero/one/full history and symmetric Dirichlet smoothing. The shared two-fold
CV selects independent, joint and combined lists without latent-label or kernel access.
Fixed J004's 150-cell protocol before inspecting the full run. Run
`artifacts/synthetic/20261019T211915Z-context-2e036c9d` completed and hashes verified.
At 256 patients under independent short observation, all-context mean KL is 0.24061
versus tree/blend 0.29553; under adaptive-past stopping 0.23392 versus 0.34605. At 1024
patients/short observation it is worse (0.12288 versus 0.09943). Persistent latent-class
mechanisms remain adverse, while short-memory mechanisms benefit in some cells. Across
all stresses it beats tree in 73 cells and loses 77; do not pool these into a significance
claim. All-context selection picks independent models in 97 cells and joint in 53.
Standard context models are retained as stronger baselines, not marketed as a new method.

Verification after all implementation: **577 tests passed, 2 Linux-only skips**; Ruff
check/format passed for 168 Python files; repository boundary check passed. The 40 new
focused tests include convex derivatives/solutions/gaps, fold isolation, correct observed
score derivatives and information contraction, nuisance coupling, unknown-tail exclusion,
context/tree equality, absorbing support, exchangeability and reproducible generated
artifacts. `make demo` passed at `artifacts/synthetic/20261019T211955Z-9a20eea2`.
Earlier J003 and information-only check counts were 553 and 565 respectively. No clinical
inputs, dependencies, GPU, old-study reopening, new server job, commit or push occurred.
Base remains `bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`; worktree changes remain uncommitted.

Research remains active. The next design must support varying numbers of linked entities
and longer paths, capturing both persistent latent and short-memory dependence while
preserving coherent prefix probabilities. Review closest scalable methods and specify
a bounded generated experiment before implementing it. Do not keep tuning the same
finite grid or call local benchmark completion a viable methods paper. No genuine
server-data dependency has yet prevented the next local research step.

## 2026-10-19 — J005 exact scalable interaction engine and a structural rejection

Revalidated the current worktree and active goal. The preceding J003/J004 turn was
progress: implemented models, completed fixed comparisons, and changed the next action.
No stale process or server wait was assumed. Reviewed primary work on set-valued point
processes, Markov-modulated events, dynamic latent graphs, structured missingness,
exchangeable circuits, exact cardinality inference and centered autologistic models.
Also checked, but did not adopt, generic doubly robust censoring losses. Nearest
overlaps and reading depths are recorded in docs/02; known components are not claimed
as inventions or independently novel contributions.

Implemented `cardinality.py`, a log-space polynomial DP with reverse derivatives for
all entity marginals and exact backward set sampling. It handles 0–128 eligible entities
without enumerating 2^K sets. Added a bounded count contrast after removing constant and
single-entity projections under a fixed product reference, an unprojected bounded control,
and a centered quadratic control. The projected score is locally orthogonal to marginal
scores; nonzero tilts do not exactly preserve marginals or establish calibration.
The scalar bounded likelihood optimizer certifies a convex gap and labels boundary fits.
This is a one-transition component; no long-path or terminal/censoring adapter was added.

The fixed first comparison (`make cardinality-demo`) uses 72 cases across three seeds,
sizes 4/16/64, training subjects 128/512 and independent/shared-shift/opposed-shift/
capacity mechanisms. Each size is fitted independently; this is not learned transfer
to new roster sizes. Feasible methods use the same subjects; an oracle-marginal variant
is explicitly infeasible. Added strong empirical count smoothing and a two-product
mixture, keeping fixed restarts/iterations. A fresh common generated evaluation sample
gives joint KL estimates with Monte Carlo errors; count-model cross-entropy differences
are also computed exactly from true marginals/count probabilities. No true model or
evaluation sample enters feasible fitting.

Run `artifacts/synthetic/20261019T212816Z-cardinality-bf0a7894` completed all 72 cases;
source/config/output hashes verified before diagnostic-source additions. The candidate
helps some small shared-shift/capacity settings, but fails the strong-reference comparison
at larger sizes. At 64 entities, mean estimated joint KL is 2.25379 on shared shifts
versus empirical count 0.41522 and mixture 0.30541; on opposed shifts it is 4.82777 versus
mixture 0.29118. Projection versus its unprojected control has mean exact cross-entropy
difference only -0.00104. Empirical count wins fewer individual cells than the candidate,
yet has better average exact risk because of large adverse cases (candidate excess
0.19231). Preserve this heterogeneity; a win count alone would be misleading. The
candidate reaches a strength boundary in 18/72 cells; no bound or setting was expanded.
All scalar convex gaps are below 3e-10. Full generated distributions and diagnostics
remain in local ignored artifacts.

Implemented `cardinality_limits.py` and `make cardinality-limits-demo` to distinguish
finite-sample fitting from family limitations. Run
`artifacts/synthetic/20261019T213103Z-cardinality-limits-d88d5d1f` completed 12 exact
population-oracle cases at the unchanged strength bound, and its source/output hashes
were verified. With true marginals and no estimation noise/ridge, shared-shift count KL
is still 1.92560 at 64 entities and 6.94979 at 128; count KL lower-bounds full joint KL.
The bounded density-ratio argument and exact feature extrema are tested.

Constructed a stronger four-entity witness: uniform mass on 1100/0011 versus 1010/0101.
Both have marginals 1/2 and count two, but their first-pair event probabilities differ
by 1/2. Any linear-entity-plus-total-count energy has equal cross-entropy under both
laws and irreducible KL at least log(3), attained by the limiting uniform count-two law.
This is a model expressiveness restriction, not lack of information in fully observed
sets. It justifies replacing the single-global-count structure rather than more tuning.
The exact engine remains useful as a component for future subgroup/recursive models.

Verification: **21 focused tests**, including enumeration, normalizer derivatives,
orthogonality, failure of exact marginal preservation, both association signs, exact
sampling, permutation equivariance, 128-entity workspace, convex scalar optima, oracle
labels, EM monotonicity, tiny-tail log stability, representation witness, deterministic
artifacts, input/resource rejection and sanitized failures. `make check` passed
**598 tests, 2 Linux-only skips**, Ruff check/format for 172 Python files and repository
boundary checking. `make demo` passed at
`artifacts/synthetic/20261019T213103Z-b3ae6d54`. No dependencies, GPU, clinical artifacts,
old study changes, server jobs, commits or pushes. Base SHA remains
`bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`; all new work is uncommitted.

Research remains active. Next work must represent which history-defined subsets interact,
not just how many events occur. Investigate conditional subgroup/latent structures with
explicit permutation symmetry and coherent sequential probabilities, accounting for the
close recursive-cardinality and conditional-circuit precedents before a new claim.
Those successor structures and a full recurrent adapter are planned, not implemented.
No genuine server-data dependency has yet blocked this next local research step.

## 2026-10-19 — J006 recurrent roles, actual roster transfer, and a population/observation distinction

The preceding J005 turn was substantive progress, not a server blocker: its fixed
comparison and exact representation witness changed the next design. Continued the
active autonomous goal without a permission request. Read conditional-SPN definitions,
gating and autoregressive construction; variable-size set circuits; neural energy-process
consistency; and primary finite-exchangeability references. Reading depths and overlaps
are in docs/02. Standard HMMs, finite mixtures, exact marginalization and elementary
covariance restrictions are not presented as new methods.

Recorded J006's fixed protocol in docs/11 before the full run. Implemented
`history_roles.py` with generated eight-step recurrent paths, terminal absorption and
observed-prefix censoring, four history contexts, a 33-component role bank, a five-component
shared-role control and a learned two-state conditional Bernoulli HMM. Each entity's role
uses its own last two observed event bits; no identities, hidden simulation roles or future
outcomes enter routing. Terminal and event-set factorization is a joint probability model,
not a claim about clinical ordering. Prefix tails are marginalized, not zero-filled.
The bank is a population mixture of complete path laws, with whole-subject likelihood
weight fitting. HMM MAP-EM uses three fixed starts; neither global optimality nor a
Bayesian parameter posterior is claimed. Both models are reference learners.

`make history-roles-demo` completed at
`artifacts/synthetic/20261019T213741Z-history-roles-59277c83`: 72 fits and 288 evaluation
cells across three fixed seeds, two training sizes, two stopping policies and six
mechanisms. Training rosters are 4/8; the same parameters are evaluated at 4/8/16/32,
so 16/32 are genuine unseen-size tests here. Outcomes and stopping RNGs are separate
per generated subject, allowing matched complete/adaptive prefixes. Source/config/output
hashes were verified before the subsequent roster-audit source additions.

The largest-weight component recovers the specified parity partition and fresh versus
persistent dynamics in all 12 settings for each of the two history-role mechanisms.
At size 32, full-role minus shared-role NLL averages -5.95562 (fresh) and -8.21444
(persistent) per generated subject. This supplies a positive information-value result
and cross-size transfer in those deliberately matching generators. It is not general
role recovery, clinical evidence or a novel-method result. The learned HMM is stronger:
it wins 238/288 cells; mean bank excess NLL is 0.13843. At size 32, bank minus HMM is
+0.66003/+0.79144 in the two history mechanisms. Independent, hidden-role and capacity
controls remain in the report; the bank does not solve them. Preserve the fixed grid
and these results rather than adding amplitudes to rescue it. Total fitting seconds:
2.768 full bank, 0.663 shared bank, 17.329 three-start HMM, excluding simulation/evaluation.
All EM objective traces are nondecreasing to numerical rounding.

Implemented a separate `roster_marginal.py` diagnostic and `make roster-marginal-audit`.
For a known full count law with entity fields, summing omitted variables changes the
count potential by a log convolution with their elementary-symmetric coefficients.
This standard exact operation works for unequal fields, arbitrary kept ordering and
successive deletion; it is not the same as rerunning a size-dependent model on a smaller
actual population. No unknown omitted clinical histories are assumed available.
Run `artifacts/synthetic/20261019T214017Z-roster-marginal-5f014301` completed six exact
population sizes and verified source/output hashes. Marginalizing to two entities versus
actually changing population to two yields TV differences 0.06804–0.13754 in these
fixed generated capacity laws.

The accompanying restriction is precise: identical-history conditional-iid emissions
under a shared latent variable have nonnegative pair covariance. Opposite history roles
can be negatively correlated; the restriction is not about all pairs or all HMMs.
A same-history capacity law has negative covariance and cannot keep that correlation
while extending to arbitrary population size: count variance requires n <= 1-1/rho.
This is an elementary necessary condition, not a new theorem or sufficient extension
test. Infinite projectivity is not imposed on genuinely interacting finite populations.
Tests also verify full recurrent-path marginalization after removing an entire entity.

Verification: 25 new focused tests (19 recurrent-role, six roster-marginal), including
exhaustive latent-state posteriors, normalized transitions and coherent prefixes,
terminal support, no future routing, missing-tail handling, entity permutation, coupled
stopping, weight bounds, EM monotonicity, unchanged-fit roster transfer, population
marginals and sanitized artifact failures. `make check`: **623 passed, 2 Linux-only
skips**, Ruff check/format for 177 Python files and repository boundary check passed.
`make demo`: `artifacts/synthetic/20261019T214112Z-d796b50f`; `git diff --check` passed.
Earlier check before the separate marginal audit was 617 passed / 2 skipped. No new
dependencies, GPU, clinical artifacts, UCSF jobs, commits or pushes. Base SHA remains
`bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`; all new work is uncommitted.

Research remains active, with no repeated blocker or need for server input. The next
local question is a learned joint finite-roster transition supporting both common shocks
and local competition, with an explicit distinction between actual roster changes and
unobserved entities. Keep the learned HMM and exact cardinality/conditional-circuit
models as strong references, check closest latent count/DPP/maximum-entropy precedents,
and require a separate contribution before advancing to a clinical experiment. The
successor learner and any real recurrent-data adapter remain planned, not implemented.

## 2026-10-19 — J007 combined dependence, explicit solver failure, and conditional forecasting

Continued the active autonomous research goal locally. Recorded the fixed J007 protocol
before running its 30 fits / 120 evaluations. Read primary population-coupling,
partially-observed set, Markov DPP, collective-graphical-model and finite-state-projection
references; subsequently inspected Prentice et al.'s HMM with learned Chow-Liu emissions.
These precedents rule out claiming generic correlated-emission HMMs, cardinality
normalization, negative dependence, population aggregation or discarded-mass bounds as
new contributions. Reading depths and links are recorded in docs/02.

Implemented `competition.py` and `make competition-demo`: two-state history-conditioned
count emissions, exact group-count multiplicities for small-roster fitting, bounded
convex emission M-steps, fixed 20-update HMM EM and unchanged-parameter large-roster DP.
Three references isolate independent, latent-only and count-only mechanisms. Generated
termination and stopping remain distinct; no clinical data adapter was added.

Initial full run `artifacts/synthetic/20261019T214813Z-competition-b41f1107` explicitly
failed when a cross-coupled Newton step at theta=0 pointed outside its box and produced
repeated zero-length steps. Added an active-set correction and a generated regression
for the exact failing configuration, then reran the entire unchanged protocol. No
scientific hyperparameter or selection rule changed. The failed artifact is retained.

Completed run `artifacts/synthetic/20261019T215056Z-competition-e3237311` verified all
source/config/output hashes before the subsequent forecasting addition. Combined-law
cases beat both isolated components in all 24 settings, including unseen roster 32;
mean combined-minus-HMM NLL there is -1.576402 per generated subject. The signed-capacity
law favors the simpler count-only model in 23/24 cells; null/pure-shock controls retain
added-complexity degradation. All inner mean-Q convex gaps are <=2e-7, while some outer
EM traces remain improving at the fixed budget. Detailed results and actual timings
(including the HMM warm-start cost) are in docs/11. This is a positive represented-
mechanism check, not proof of novelty, clinical effectiveness or publication readiness.

Added `competition.forecast`: conditional Monte Carlo future paths given a fully
observed prefix, integrating unknown future terminal events and preserving absorption.
Refactored generic log-space two-state forward/backward inference and retained existing
reference-model behavior. Sixteen focused tests cover exact normalizers, gradients,
Hessians, certified box updates, EM monotonicity, exhaustive transition normalization,
HMM reduction, unchanged-fit roster transfer, filtering/forecasting, bounds and sanitized
failures. `make check`: **639 passed, 2 Linux-only skips**, Ruff check/format 180 files,
repository boundary check passed. `make demo` completed at
`artifacts/synthetic/20261019T215600Z-f5ca2b82`. No dependencies, GPU, clinical artifacts,
UCSF jobs, commits or pushes; base SHA remains
`bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`. Research remains active, not blocked.

## 2026-10-19 — J008 exact hidden-history filtering with explicit population assumptions

After J007, continued local work rather than asking the user to pick another direction.
Fixed J008's correctness/resource protocol in docs/11 before implementation. Added
`hidden_history.py`, `hidden_history_audit.py`, CLI and `make hidden-history-audit`.
For a known original roster and known initial histories, up to eight permanently
unobserved entities are represented by counts in four history states plus absorption.
Each transition sums all possible hidden no-event, recurrence and termination counts,
with multinomial multiplicities and the full-survivor population normalizer. It does
not use hidden simulated event truth, fill events with zero, or change population size.
The common latent posterior is filtered jointly with the hidden-history histogram.

Read the primary finite-exchangeability inference introduction and IJCAI 2018 lifted
filtering representation/prediction construction. Exact multiset filtering, state
aggregation and handling symmetry are existing ideas; our implementation is a concrete
reference, not an established new algorithm. Prior correlated-emission HMMs also remain
strong references. Do not turn a known-model correctness advantage into a novelty claim.

Final audit `artifacts/synthetic/20261019T220351Z-hidden-history-e07e31ab` completed all
three fixed distribution checks and 15 scaling cases. Source/output hashes verified.
Maximum absolute difference from full labeled recurrent-path summation is 2.23e-16.
Tests additionally compare the entire hidden-histogram/common-state posterior, including
terminal outcomes. Incorrect population deletion differs by TV 0.0550154 for signed
competition and 0.0135058 for combined dependence, while the independent control agrees.
All are generated known-model calculations, not fitted performance or clinical evidence.

For eight missing entities, 495 histogram states replace 390625 labeled histories,
with two common latent states in either representation. However, 125970 transition
terms remain: the count is choose(B+12,12), versus choose(B+4,4) history states.
Cached arrays use about 5.04 MB (not peak working memory). Cold construction took
0.910 s; eight-step filters at observed sizes 1/4/16 took 0.719–0.737 s. Keep the bounded
implementation and high-degree cost explicit. The first provisional audit
`20261019T220254Z-hidden-history-e9893262` had an already-cached B=2 timing; instrumentation
was corrected to cold construction, then rerun with a source-stability check. Probability
results stayed unchanged. Intermediate run `20261019T220327Z-hidden-history-0ef67188`
preceded the final source-stability guard.

Ten new focused tests cover exhaustive path sums/posteriors, normalized next observations,
full-observation and no-competition reductions, prefix consistency, permutations,
absorption, exact state/term counts, bounds, generated-only tags, artifact hashes,
no overwrite, source drift and sanitized failures. The first full check correctly
failed its pre-existing source-stability guard because timing instrumentation was edited
while that check was running (647 passed, one failed, two skipped). After stopping source
edits and finishing the audit instrumentation, reran the checks on unchanged source:
**649 passed, 2 Linux-only skips**, Ruff check/format 183 files and repository boundary
check passed. `make demo` completed at
`artifacts/synthetic/20261019T220419Z-546d1d2e`; `git diff --check` passed before this log
update and is repeated for the documentation finish.

All changes remain uncommitted on base
`bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`. No new dependencies, clinical access, held-out
clinical evaluation, GPU, server jobs, commits or pushes. Autonomous research remains
active with substantive progress and no blocker streak. Exact inference is now available
as a reference for the next local question: learning and computational control under
partial observation, against correlated-emission and lifted/particle alternatives.
Unknown initial roster/history, reappearing identities, observation-mechanism learning
and a clinical recurrent extractor remain unimplemented. A distinct method contribution
and a justified real-data task are still required before a UCSF experiment.

## 2026-10-19 — J009 learning with unobserved recurrent histories

The previous J008 goal turn was progress, not a wait or blocker. Revalidated the current
worktree and active goal, then continued into learning without another user request.
Read primary coupled-HMM, aggregate-HMM and particle-EM sources; reading depths are in
docs/02. Generic EM, smoothing, Fisher identities and lifted inference are known methods.
Fixed J009's simulation and comparison protocol in docs/11 before implementation/results.

Refactored the small-roster count normalizer into `CountDesign` with sufficient-statistic
objectives, preserving `GroupDesign` behavior. Added `hidden_learning.py`: generated
missing-subject inputs, bounded reusable sparse transitions, exact forward-backward
posteriors, expected emission/context/terminal/latent-transition statistics, and MAP-EM
with certified convex emission updates. Fully observed training reproduces the existing
count-HMM updates. Hidden future event truth never enters the design. The missing count
and original initial histories are supplied; these are not inferred from absent data.
Training is bounded to 512 subjects, actual roster eight, hidden count four and 500000
transition terms. No unknown-roster or informative-observation model is implemented.

Added the fixed configuration, CLI and `make hidden-learning-demo`. Run
`artifacts/synthetic/20261019T220942Z-hidden-learning-182f31f0` completed all 30 fitting
settings / 180 evaluation cells; source/config/output hashes verified. At unseen roster
16 with two hidden training and two hidden evaluation entities, combined-minus-reference
NLL is -1.135480 versus product HMM, -0.853635 versus correct count-only, and -0.230105
versus naive deletion, averaged over the three fixed seeds in the combined generator.
These represented-mechanism gains are accompanied by null and misspecified losses;
complete tables and all cases are retained. Correct versus naive complete-training
fits agree in all 90 evaluations to maximum mean-loss difference 2.67e-15.

With missing training, correct combined learning beats naive in 18/18 global-capacity
and 16/18 combined cases, but loses in 18/18 independent and 16/18 hidden-role cases.
Count-only is stronger in 15/18 pure-capacity cases. Product HMM is generally better
in independent/fresh-shock/hidden-role controls. Inner gaps pass <=2e-7; outer EM is
fixed-budget and sometimes still improving (largest final combined increment 0.0742538).
Do not increase iterations or alter priors to rescue inspected cases. Total time measured
inside fits is 3.805 s product HMM, 2.169 s design, 16.967 s additional combined EM,
15.265 s additional count-only EM and 1.814 s additional naive combined fitting. These
exclude simulation/evaluation and share reference initialization; no end-to-end speed
or global-optimum claim. No publication or clinical claim follows from this benchmark.

Ten new focused tests verify exact smoothing statistics against all labeled histories,
Fisher gradients against observed-likelihood finite differences, variable/empty prefixes,
EM ascent and certificates, original no-missing update equivalence, permutation invariance,
masking without hidden-outcome leakage, class/support/bounds, CLI/artifact hashes and
sanitized failures. Combined focused suite: 36 tests passed. `make check`: **659 passed,
2 Linux-only skips**, Ruff check/format 186 files and repository boundary check passed.
`make demo` completed at `artifacts/synthetic/20261019T221843Z-0f84f515`; `git diff --check`
passed. No source edits occurred while the full benchmark/checks were active.

All code remains uncommitted on base `bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`.
No dependency changes, GPU, clinical access, original test evaluation, UCSF jobs,
commits or pushes. Research remains active; there is no current external blocker.
The next local comparison must include stronger correlated-output/set-process models,
not merely the product-emission HMM or an invalid deletion control. Re-inspected the
AISTATS 2024 dynamic Bernoulli/DPP formulation and evaluation discussion: it explicitly
models within-set inhibition beyond shared hidden-state conditioning. A concrete DPP
reference, its fitting and comparability to the discrete fixed-roster task remain
planned. The clinical recurrent extractor and a distinct methods contribution remain
unimplemented/unestablished, respectively.

## 2026-10-20 — J010 containment completed; J011 exact filtering factorization

The user asked to continue after the status checkpoint. Read the working agreement
and existing source/tests; reused the unchanged environment. No server connection,
Git pull, commit or push was performed. The goal tool still reported its stored
paused state; the explicit user continuation authorized this working-tree research.
No attempt was made to claim the open research objective complete or to set a
different goal status through an unsupported resume operation.

Completed J010's already specified GDPP reference and containment audit. Read Sharghi
et al.'s 2018 primary definitions and sequential extension: J009's unsigned count law
is a diagonal cardinality-weighted GDPP. Added the dense positive-definite reference,
history-shared non-diagonal determinant/spectrum reductions, derivatives of selected
minors, recurrent scoring and a normalized-emission adapter for the existing hidden
filter. Callback shape/range checks are not a proof of normalization; probability
normalization is independently checked. No broader GDPP fitting algorithm was added.

`make gdpp-containment-audit` completed at
`artifacts/synthetic/20261020T162051Z-gdpp-containment-26de8e7f`, with 21 static,
two recurrent and four covariance cases. Diagonal log-probability error <=2.85e-14;
non-diagonal reduction error <=8.53e-14; exact two-hidden-entity marginal error
<=4.17e-17. Source/output hashes verified before the subsequent source additions.
The covariance restriction is explicitly for permutation-invariant real ordinary-DPP
marginal kernels; a fixed-cardinality GDPP counterexample prevents overgeneralizing it.
Sixteen tests cover independent dense/enumerated references, count-law identity,
minor gradients, full-path sums, hidden posteriors, terminal events, prefixes, bounds,
generated-only inputs, artifact hashes, source drift and sanitized failures. The first
focused run had one erroneous test expectation: a correctly shaped zero-log-probability
callback was expected to fail a shape check. Corrected the invalid-shape fixture;
probability algorithms and scientific protocol were unchanged.

After confirming the prior-family overlap, specified J011 in docs/11 before coding:
retain the same unsigned law, replace compound transition enumeration with independent
terminal thinning, survivor-normalizer division, grouped binomial-polynomial matrix
contractions and final event-count weighting. Added `factored_history.py`, the fixed
audit, CLI and Make target. The prepared filter supports 0..24 hidden entities and up
to 128 total entities, with exactly four two-bit history types and known initial roster.
Layered normalizer coefficients and contractions avoid the sparse compound-edge table.
No observation-mechanism inference, unknown population, signed-law/general-GDPP
extension, backward operator or new learner is implemented.

`make factored-history-audit` completed all 72 fixed cases at
`artifacts/synthetic/20261020T162510Z-factored-history-a60c0ea3`; source/output hashes
verified. All 45 comparisons within the sparse limit agree: maximum log-likelihood
error 3.56e-15, per-step posterior error 3.89e-16. At eight hidden entities, the median
eight-step filtering time across nine mechanism/seed cells is 0.009332 s versus
0.722802 s sparse, with preparation separately 0.001159 s versus 0.887681 s. At 24,
factored filtering takes median 0.201548 s plus 0.013957 s preparation. The corresponding
1,251,677,700 sparse compound terms were not allocated; no sparse timing at that size
was measured. At zero hidden entities, factored filtering is slightly slower. Full
timings, all cells and limitations are retained in docs/11 and the generated artifact.
Logical array bytes are not peak-memory measurements.

Seventeen factored-filter tests cover sparse agreement at all supported reference sizes,
layered normalizers against the earlier count DP, prefix/absorption/permutation,
complete-observation and independent-deletion limits, 24-hidden-entity behavior,
extreme allowed parameters, resource/input boundaries, provenance and failure paths.
Combined focused suite: 53 passed. `make check`: **692 passed, 2 Linux-only skips**;
Ruff check/format 192 files and repository boundary check passed. `make demo` completed
at `artifacts/synthetic/20261020T162541Z-505ac2ca`. No source files were edited during
either audit or the full checks. Documentation updates followed completed checks.

All changes remain uncommitted on base
`bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`. No new dependencies, GPU, clinical inputs,
original held-out evaluation, UCSF jobs, commits or pushes. This continuation made
substantive progress and has no external blocker streak. It establishes a reproducible
computational improvement over our sparse reference, not a new distribution or a
publication-ready contribution. Re-read lifted-filtering compound-action construction
and recursive-cardinality prior work; generic lifting and polynomial inference are
known. Next local work concerns the transpose/backward operator, learning efficiency
and comparisons against stronger computational references. A defensible real-data
roster/coverage design remains necessary before a UCSF experiment.

## 2026-10-20 — J012 verification and return to a data-driven task

J012 implements the transpose/backward operator and exact observed-likelihood
derivatives for J011's unchanged unsigned law. Its fixed 54-case generated audit
completed at `artifacts/synthetic/20261020T163839Z-factored-gradient-71b6137e`.
Source/output bindings were verified at completion. Maximum directional derivative
error was 3.92e-10; the 27 supported sparse comparisons agreed to 1.46e-14 for
emission gradients. Full results and separate preparation/forward/gradient timings
are in docs/11. No large-roster optimizer or fitted prediction comparison was added.
Twelve new tests cover sparse smoothing/gradient agreement, transpose identities,
finite differences, empty/absorbed/permuted inputs, limits and artifact failure paths;
the earlier focused combined suite passed 39 tests.

After the user's pause/explanation and subsequent continuation, the latest steering
asks for less emphasis on mathematical/algorithmic sophistication and greater grounding
in the actual UCSF task. The machine-learning methods-paper objective remains. Updated
AGENTS, README, overview and docs/11 to make this the active priority. J013 remains
specified but unimplemented and is now suspended. The J001-J012 reference tools and
their failures stay available; their speed/correctness results do not establish that
UCSF requires permanently hidden-entity inference or has a capacity-competition mechanism.

Re-read approved access/semantic findings and inspected the logical cohort/history
schemas and label-free clock-audit reader. Direct links and repeated administrations
motivate assessing recurrent joint prediction, but the selected first-execution
cohort and capped histories cannot certify complete recurrent observation windows or
patient-wide rosters. Recorded a provisional cutoff-defined, linked-order prediction
question and evidence/requirement table in docs/11. A new clinical protocol, recurrent
extractor and bounded training-only feasibility job are still unimplemented; no server
task was issued. The next implementation must address that task/coverage contract
before extending inference benchmarks.

Closed the pending integration verification using the unchanged environment:
`make check` passed **704 tests, 2 Linux-only skips**, Ruff check/format 195 files
and repository boundary check. `make demo` completed at
`artifacts/synthetic/20261020T171117Z-0a5abba2`; `git diff --check` passed.
No source was edited during these checks. This turn changed research/status documents,
not model behavior. All work remains uncommitted on base
`bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`; no UCSF access, original-test evaluation,
new source semantics, dependency changes, commits or pushes.

## 2026-10-20 — T001 recurrent task contract and server audit prepared

The user instructed us to start the data-driven direction. Specified T001 in docs/11
before implementation. It assesses whether the existing reviewed order/administration/
observation sources support recurrent histories and common follow-up for a cutoff-defined
set of recent known orders. There is no model fitting, new architecture, performance
claim or revival of closed clinical comparisons. The four-hour horizon is a fixed support
diagnostic, not a selected future prediction-paper endpoint.

Added `recurrent_task.py` with independent repeated-event handling, cutoff-only roster/
history construction, explicit terminal versus observation endpoints and unknown censored
count tails. Invalid members invalidate their joint windows rather than being removed
to improve apparent coverage. Future retrospective/unknown documentation records preserve
whole-path quality exclusions. Late-available target events cannot silently become zero.
The old first-execution validator still rejects repeated administrations, as independently
checked in the new tests.

Added a full-source access adapter, clean-Slurm runner, `recurrent-audit` server job and
`scripts/run_recurrent_audit.sh`. The fixed patient selector projects only identities/splits
from the existing bound cohort, verifies patient separation, and selects at most 32 old
training patients. Full-source scans select orders by patient, confirm all selected order
keys in a second pass, and retain all directly linked administration/observation rows
before semantic filtering. Full content hashes and source inventories are compared
before/after. Missing order identities, wrong-patient duplicate orders, cross-file links,
physical-read limits and decoded-byte limits remain explicit. Key checks are within the
selected domain, not a global source-identity uniqueness proof.

This is explicitly a new full-source operation, not bounded prefix probing or reuse of
the old capped histories. Both charged file reads and decoded row-group bytes have a
64 GiB total ceiling; worker resources are 2 CPUs / 4096 MiB / 1200 seconds with a
22-minute Slurm allocation. Retention caps are 20,000 order rows, 200,000 administration
rows and 20,000 observation rows. No cap expands automatically. File-hash work is included
in the declared budget. These are ceilings, not measured UCSF source sizes or runtime.
An oversized source may stop before useful support evidence is obtained.

The wrapper reuses the original server environment/config and discovers only the exact
previous eligibility-mapping bytes bound to the cohort; it does not guess columns or
ask for new source semantics. Default action is plan-only; explicit `--submit` runs the
described operation and monitors it. Reports contain private aggregates only; shareable
feedback is an allowlisted categorical summary, with no support-to-model advancement
rule. No patient records, histories, predictions or models are persisted by this audit.

All 44 new generated tests passed, including real toy Parquet scans, restricted-output
worker lifecycle, metadata-only planning, patient-split/label-projection checks,
censoring, late availability, known versus future terminals, malformed linkage,
truncated scans, content mutation with restored size/mtime, source inventory changes,
dictionary identities, mixed integer widths, mapping bindings and sanitized failures.
After a first full pass, code review identified a possible dictionary-encoded identity
compatibility issue; added bounded dictionary decoding and exact integer-range handling
with a regression test, then repeated required integration checks.

Final `make check`: **748 passed, 2 Linux-only skips**, Ruff check/format 203 files and
repository boundary check passed. `make demo` completed at
`artifacts/synthetic/20261020T204138Z-ac7eab94`. `make recurrent-task-demo` completed
five deterministic generated scenarios, saved with source/output hashes at
`artifacts/synthetic/20261020T204138Z-recurrent-task-8da11cba`. They distinguish complete,
partially observed, terminal, late-available and wrong-patient cases; these are contract
checks, not clinical results. Shell syntax and `git diff --check` passed. Source was
unchanged during the final checks and generated audit.

All work remains uncommitted on base `bbbb66250dcbf30cd7d38cc8096bc64bdc65951d`.
No UCSF connection, data transfer, real job, held-out evaluation, dependencies, GPU,
commit or push. A concrete external dependency is now reached: run the prepared T001
audit on UCSF to establish actual task support. A clean release is needed first;
AGENTS.md requires an explicit user instruction before committing/pushing. Do not fill
this evidence gap with more synthetic algorithm comparisons.

## 2026-10-21 — T001 release and runnable server handoff preparation

Following the concrete release proposal, the user requested runnable server commands
and reported that a GPU can be used if needed. Proceeding with the verified local
milestone release is necessary to provide a clean, fetchable T001 entry. T001 remains
a CPU source/coverage audit; no GPU computation, modeling or old-test opening is added.
The reportable real-data task support remains unknown until the user runs the job.

Fetched origin/main and confirmed no divergence from base `bbbb662`. Verified that all
source hashes still match the completed generated T001 artifact
`artifacts/synthetic/20261020T204138Z-recurrent-task-8da11cba`, with its output hashes intact.
The unchanged implementation retains the completed 748-pass / 2-skip full check and
successful `make demo`. Only handoff/status documentation changed for this release;
the required publication script reruns checks and generates the handoff pinned to the
actual clean commit before ordinary push. No clinical records or generated result
artifacts are included in the publication set. The release includes the previously
verified generated research references as well as the independent T001 audit.

## 2026-10-21 — T001 job 39768 failed; cause not yet established

Release `34d6ee75affda8e93c2eaedc121c58dc045536d5` was pushed and the user
reported successful server preflight/planning and submission of job 39768. The monitor
then returned `recurrent_audit_job_failed_no_automatic_retry`. This reports a scheduler
failure, not a negative research finding or verified source coverage. No successful
task report, reason, elapsed time or resource evidence has yet been supplied.

Local inspection confirms that the monitor emits the same message for different
terminal scheduler states. The runner can persist a fixed status/limit in `failure.json`,
but generic worker exceptions are intentionally suppressed and may leave only
`failed` with a null limit. Prepare read-only inspection of scheduler accounting and
the exact job/commit-bound failure record, emitting allowlisted categories only. Do not
resubmit, enlarge resources, read clinical rows or request private logs to infer a cause.

The prepared read-only snippet passed seven generated checks: absent record, recognized
limit, generic failure, rejection of arbitrary payloads, symlink rejection, duplicate
receipt rejection and commit mismatch rejection. `git diff --check` passed. These are
diagnostic-tool checks only; no clinical job was rerun, no pipeline changed, and no new
commit or push was made. Scheduler accounting and the existing failure record remain
the next server-only evidence needed.

### Follow-up: early exit without a failure record

User-provided accounting shows job 39768 and its batch step FAILED with exit `2:0`
after one second; no MaxRSS value was supplied. The receipt-bound read-only check
reported `failure_record: absent`. This suggests startup/early initialization but
does not establish memory exhaustion, a scan limit, successful scan coverage or any
negative task-support finding. It also does not exclude storage failures preventing
failure-record creation. The old runner suppresses pre-output exceptions to one generic
stderr sentence, making their causes unrecoverable from that sentence alone.

Added allowlisted error codes/categories to the runner's exception handler, including
errors before output creation; no arbitrary exception payload/class name is emitted.
Resource exit codes, storage restrictions, source access and research protocol are
unchanged. No root-cause fix is claimed. Six new generated regressions check exact
category output and rejection of private payloads. `make check` passed **754 tests,
2 skips**, Ruff check/format and repository boundary check. `make demo` completed at
`artifacts/synthetic/20261021T152352Z-bdb12c0c` (generated only).

Prepared a read-only snippet for the existing server checkout: locate the exact prior
receipt; classify bounded stderr without exporting log text; verify current clean
revision; rediscover the exact prior mapping; and run existing output-boundary checks.
This checks current startup metadata, not the historical compute-node environment or
exported bindings, and never invokes a worker, creates output or reads clinical rows.
Six generated cases passed, including private-payload suppression, receipt mismatch,
symlink and dirty-revision rejection; input files were unchanged. Pending that server
evidence, no retry, limit increase, commit or push was made.

### Follow-up: output-boundary rejection reproduced

The user's read-only response for job 39768 reported a present stderr file containing
the runner's generic error, no detected Python import error, and failure at
`path_validation` with code `recurrent_invalid_output`. Configuration, clean revision,
artifact discovery and mapping loading passed in that inspection. This reproduces a
current path rejection; the old combined condition does not identify its specific
predicate or prove that all historical compute-node state was the same.

Local inspection found a concrete compatibility defect: prior cohort validation used
the resolved authorized storage root, while output validation required a literal
`/scratch/tliu7` prefix and rejected even the fixed root's own symlink ancestors.
Generated fixtures reproduce rejection of a legitimate aliased root and its canonical
spelling. This is a possible cause, not yet established as job 39768's exact cause.
The replacement accepts only the fixed authorized root and its canonical spelling;
arbitrary aliases, symlinks below that root, escapes, Git repository storage (including
worktree .git files), and source/cohort overlap remain rejected. Neither server paths
nor configuration are changed automatically.

Added the same metadata-only path checks to plan/submit before command submission or
run-directory creation. Distinct fixed errors now report which boundary failed. Added
`bash scripts/run_recurrent_audit.sh --check-storage` for a read-only, categorical review
of current paths and all legacy rejection conditions. This avoids further long inline
diagnostics after release. It does not submit, run a worker, open clinical rows, create
an artifact directory, reconstruct historical scheduler state or change resource caps.
The original protocol, negative findings and held-out evaluation remain unchanged.

Verification: 39 focused runner/storage checks passed, including 22 new filesystem/CLI
cases. `make check` passed **776 tests, 2 skips**, Ruff check/format (204 files), and the
repository boundary check. `make demo` completed at
`artifacts/synthetic/20261021T153117Z-a9569c10`. Shell syntax and `git diff --check` passed.
All fixtures/results here are generated. These changes remain in the working tree on
`34d6ee7`; no commit, push, server configuration change or clinical retry has occurred.
The next release needs the explicit commit/push instruction required by AGENTS.md;
after release, use the short storage review before considering a new full-source job.

### Standing publication authorization and path-fix release

The user explicitly removed the per-release commit/push approval requirement: server
Codex is unavailable, and publishing Mac changes is necessary to update server code.
Updated AGENTS.md to authorize ordinary commit/push of verified milestones and necessary
server fixes without another approval. This supersedes the earlier approval requirement
above; the data boundary, required checks and single-writer workflow remain in force.

Preparing this path-fix release on the existing 776-pass / 2-skip check and completed
synthetic demo. The publication script reruns checks and generates a handoff pinned to
the actual clean commit before ordinary push. The initial server action for this release
is the metadata-only `--check-storage` review, not automatic resubmission of job 39768.
No claim is made yet about which legacy path predicate triggered the real failure or
about real recurrent-task support.

### Confirmed repository-contained output; separate read and write roots

The user ran the `07638fb` metadata-only storage review. It returned `blocked` with
`recurrent_storage_inside_repository`; `output_inside_git_repository` was true and
every other legacy rejection flag was false. This establishes a current output-root
repository-boundary problem, not an alias failure or a scientific negative. No job was
submitted and no raw source was scanned by that review. Whether the old cohort itself
is also repository-contained was not disclosed by those flags.

Added an explicit `--output-root` to the recurrent wrapper, passed to the server as
`--recurrent-output-root` for this job only. Original configured storage remains the
read/discovery root; only new job directories/logs/receipts/results use the new root.
Both plan and submit validate the new destination outside all Git repositories and
disjoint from configured raw storage, old artifacts and mapped input sources. The
wrapper sets umask 077. No server config mutation, relocation, copying or deletion is
performed. The prepared destination is `/scratch/tliu7/intent-execution-state-private`;
its existence/layout and validation remain server-side facts, not assumed successes.

For compatibility with already-created artifacts, a narrow read-only input exception
checks the current checkout's actual Git common repository. Only ignored directories
with no indexed descendants may supply the existing cohort; foreign/nested repositories,
tracked or unignored inputs, and redirects fail. This inspects current Git metadata,
not historical Git objects, and does not authorize or claim publication of any data.
New writes inside a repository remain forbidden, including ignored directories.
The prior mapping/cohort hashes, patient selection, scan/retention/resource limits,
sealed old evaluation and output data restrictions are unchanged.

Generated tests use actual temporary Git repositories and detached worktrees to check
legacy inputs without modifying their bytes; they reject tracked/unignored/foreign/
nested inputs and verify external destination disjointness. CLI tests retain old-root
artifact discovery while forwarding the separate write root. A simulated scheduler
test exercises the real server submission path, verifying that only the new root gets
a receipt and that invalid destinations fail before submission. No real UCSF action
was performed by the Mac.

Validation completed: **53 focused checks**, then `make check` **790 passed, 2 skips**,
Ruff check/format (204 files) and repository boundary check. `make demo` completed at
`artifacts/synthetic/20261021T161957Z-9748a470`. Shell syntax and `git diff --check` passed.
Initial new tests needed a test-block placement correction; all final focused and full
checks passed without changing the clinical protocol. All test repositories and bytes
are generated fixtures. Publishing under the standing user authorization; the release
script rechecks and pins the actual commit. The server command checks the explicit new
root first and submits only if that check passes. No server outcome is claimed yet.

### Legacy-input rejection after the external-output fix

The user ran the `784d33b` storage review with the external write root. It still returned
`recurrent_storage_inside_repository`, but all legacy flags were false, including the
new output's Git-ancestor flag. In that version this localizes the remaining rejection
to `_legacy_input_allowed`: either Git context lookup failed or the cohort's enclosing
repository markers did not exactly equal the inferred original checkout. No job was
submitted, no raw source was scanned and no recurrent-task evidence was produced.

A generated regression reproduced a real defect in the old check: same-project
`original/handoff/old-worktree/private/cohort` has both its own `.git` file and the main
repository's `.git` ancestor, so the single-directory comparison rejects it. The first
regression failed on the released implementation before the fix. This layout is
consistent with the handoff convention, but it is not proof of the private cohort's
actual location or the historical Git environment on UCSF.

Replaced the directory-name heuristic with resolved Git common-directory identity.
Every enclosing checkout must belong to the running checkout's Git family. Ignore and
index checks run independently in every enclosing checkout; same-family worktrees do
not exempt an outer tracked file or an unignored outer path. Foreign or independently
nested repositories still fail. External new-write restrictions are unchanged.
Distinct fixed categories now separate Git lookup/timeout failures, foreign repository
identity, ignore failures and tracked/unverifiable index status. Storage review emits
separate cohort-input, new-output and overlap checks, never private paths or exception
payloads; overlap is not evaluated if either path check failed.

Generated tests cover the real nested Git/worktree layout, unchanged input bytes,
both inner and outer index tracking, independent inner/outer ignore rules, foreign
repositories and sanitized Git failures/timeouts. Initial category assertions were
updated for the new explicit errors; the outer-ignore regression uses Git's anchored
common exclude to model different ignore outcomes in the enclosing checkouts.
All 60 focused storage/runner checks passed. No server artifacts or config were changed.

Final verification: `make check` **797 passed, 2 skips**, Ruff check/format (204 files)
and repository boundary check passed. `make demo` completed at
`artifacts/synthetic/20261021T162538Z-1f1fe9ed`; `git diff --check` passed. Publishing
the verified fix under the standing authorization, with a clean-commit handoff. No real
retry, source scan or claimed task-support result follows from the local tests. The
prepared server sequence retains the external write root and stops before submission
if any of the independent storage checks fail.

### Git failure localized to the legacy input; diagnostic-only next step

The user ran the `8ff2c72` storage review. Cohort input returned
`recurrent_legacy_input_git_unavailable`, new output passed, and overlap was not checked.
All legacy rejection booleans were false. No submission or raw scan occurred. This
does not establish that nested worktrees caused the remaining failure: common-directory
lookup, ignore query and some process errors still shared this generic code.

Added fixed `git_failure` diagnostics with the operation, checkout role, reason category
and exit code. Git stderr is inspected only in server process memory (an 8192-character
prefix for classification); it is never emitted, persisted or attached to exceptions.
No claim is made that PIPE capture itself caps stderr size. Git subprocesses retain
30-second timeouts, force C-locale classification and disable optional Git locks. Normal
ignore/index status codes retain their previous meaning; failed Git operations remain
blocking. No ownership bypass, safe.directory change, index modification, ignore-rule
change, source semantics change or artifact relocation was introduced.

Generated tests identify each failed Git operation at active, owning and ancestor
checkout roles without emitting a private sentinel. A real generated Git index/gitlink
fixture produces and classifies the ancestor check-ignore submodule error; it remains
blocked. This is a test case, not a claim that UCSF has that condition. Timeout and
nonzero-exit tests use the new subprocess runner and preserve sanitized feedback.
All 66 focused storage/runner checks passed. The next server command is diagnostic only,
without an automatic subsequent submission; further action depends on its actual result.

Final checks: `make check` **803 passed, 2 skips**, Ruff check/format (204 files),
repository boundary check and `git diff --check` passed. `make demo` completed at
`artifacts/synthetic/20261021T163217Z-3bf4c524`. These are generated checks only.
Publishing this diagnostic-only milestone under the standing authorization; the next
UCSF action remains the read-only storage review, not a claimed root-cause correction
or a new clinical experiment. No real paths/logs/data were accessed by the Mac.

### Remove the read-only cohort's unnecessary Git metadata dependency

The user questioned the repeated Git blockers and proposed deleting/recloning. Fetch
and worktree creation have succeeded; the latest reported failure is still the old
input Git gate at `8ff2c72`. There is no feedback from the `e0b9183` diagnostic and no
established repository corruption or specific Git subprocess cause. Preserve the
original checkout, private configuration and old artifacts; deletion is not needed.

Removed the common-directory/ignore/index gate on read-only cohort paths. That was an
implementation restriction, not a requirement to determine whether pinned existing
clinical inputs are valid. The server still confines the cohort to the original
configured artifact root, verifies authorized storage and rejects redirects. Submission
now additionally pins the canonical cohort location by SHA256; parent and worker reject
missing or changed location pins before reading mapping inputs. Existing manifest,
Parquet, mapping and source stability hashes, patient split rules and no-row persistence
remain. Clean pinned code verification and the prohibition on all new repository writes
remain. This change does not authorize tracking data, audit historical Git contents,
modify server Git configuration, relocate data, or expand T001 scan scope/resources.

Generated tests cover original and nested worktrees, malformed input Git metadata and
an ancestor gitlink with no input Git subprocess calls, unchanged input bytes and no
review output writes. Tests retain rejection of repository outputs, escapes, symlinks
and overlap. Added parent/worker path-swap rejection and configured artifact-root
rejection, alongside existing content-binding and split tests. Removed obsolete tests
whose only contract was the superseded Git gate. Focused storage/runner/access tests
passed; `make check` passed with **796 tests, 2 skips**, Ruff check/format (204 files)
and repository boundary check. The subsequent artifact-root assertion passed in the
23 runner tests. `make demo` completed at
`artifacts/synthetic/20261021T164119Z-f25eae0f`; `git diff --check` passed.

Publish under the standing authorization. Prepared server sequence first checks storage
then explicitly submits the unchanged 2-CPU/4-GiB T001 scan, stopping on any failed check.
No real scan has been rerun by the Mac; support, coverage and publication feasibility
remain unestablished. Input Git queries are no longer a blocker requiring diagnosis.
