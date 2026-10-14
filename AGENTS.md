# Working agreement

## Workflow

Develop and test synthetic code on the Mac. Publish code through Git; the user
pulls it on UCSF and gives the generated handoff prompt to a separate Codex.
Do not connect to UCSF from the local agent. Do not modify sibling projects.
Do not pull clinical artifacts back through Git or other channels.

## Data boundary

All UCSF records, patient identifiers, feature tables, predictions, logs, model
weights, and raw schema reports stay on authorized UCSF storage. Use only
generated synthetic fixtures here. Never paste real rows or values into issues,
prompts, documentation, terminal summaries, or Git commits. Schema discovery
reads Parquet footers only, omitting statistics and arbitrary metadata.
No real column mapping is stored here. Server-approved operational findings are in
docs/21_mac_development_handoff.md; never infer source column names from those findings.

## Research invariants

Respect both occurrence and availability time at each prediction cutoff.
Split at the patient level. No global calendar split until shifted-date semantics
are verified. Unexecuted is not a failed execution: distinguish terminal causes
and right censoring. The current MVP concerns first execution only. Reject
repeated administrations until a recurrent-event design is implemented.
Predictive associations do not identify causal treatment effects.

## Engineering

Python 3.11+, src layout, explicit configs and seeded synthetic tests.
Use `make check` and `make demo` after pipeline changes. Tests must cover
censoring, linkage, temporal availability, patient splits, and no-data Git
handoffs. Keep failures explicit; never substitute synthetic results for clinical
results. Do not log exception payloads containing private records.
No large/GPU training during Phase 0. Server agents may inspect metadata or run the
bounded aggregate-only feasibility command after institutional access, server context,
mapping semantics and source coverage are verified locally. Real cohort extraction
remains unimplemented and outside this handoff. Do not persist rows during feasibility.
Treat truncated scans as incomplete evidence: do not confirm single executions or
censoring when another qualifying dose could be outside the scan. Encounter mismatch
handling is explicit and counted; patient mismatches always reject the order.
Keep lab features disabled until an independent availability rule is reviewed.

## Handoffs

Commit source and docs only after checks pass. Use `make handoff` to produce a
prompt pinned to the actual clean commit. `scripts/publish.sh` runs checks before
ordinary (never force) push. No automated result download or clinical-data upload.
Update docs/20_research_log.md with real checks and negative findings. Future
components must be explicitly labeled as planned until runnable and tested.
