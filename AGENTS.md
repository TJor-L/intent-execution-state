# Working agreement

## Project status

The primary method project stopped on 2026-10-16 after bounded Phase 1 controls because
no authoritative point-in-time semantics were available for richer predictors. Preserve
the private UCSF artifacts, do not run test evaluation, add new feature sources, start
neural/GPU training or revive E002 without new independently reviewed semantic evidence.

## Workflow

UCSF is now the primary development and testing environment, as requested by the user.
The server agent owns the implementation -> synthetic tests -> bounded real validation
-> diagnosis -> fix loop. It may edit reusable code, add generated tests, commit and
publish verified milestones without handing every implementation decision back to the
Mac. Earlier review-only/return-to-Mac handoff restrictions are superseded.

The Mac agent handles research discussion, code review and synthetic reproduction.
Git carries code and approved operational summaries at milestones or genuine blockers,
not after every check. Keep one active writer per branch; while the server is developing,
the Mac should review rather than independently push competing implementation changes.
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
coherent/indexed executor is currently unimplemented; update its status only after it
is runnable and tested. Do not repeat unchanged prefix runs expecting coherent coverage.
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
