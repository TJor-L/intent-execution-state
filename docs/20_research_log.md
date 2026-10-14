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
