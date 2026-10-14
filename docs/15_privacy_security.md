# Data boundary and publication rules

Real UCSF patient-level records stay on authorized UCSF infrastructure. This includes
de-identified extracts, identifiers, features, labels, predictions, notes, logs,
checkpoints and any caches derived from them. The local environment uses synthetic
records only. Do not copy sample clinical rows into prompts, comments or Markdown.

Git is the code handoff, not a data transport. `.gitignore` excludes data/artifacts,
binary tables, local configs, logs and weights. The publication check additionally
allowlists source/docs/config paths, rejects symlinks and obvious private keys, and
never prints file contents. These are guardrails, not a PHI/secret classifier: source
comments and documents still need human/agent review. Removing a committed secret
does not remove it from history; do not push such history.

The server audit reads only bounded Parquet footers, with no row values, statistics,
filenames or arbitrary embedded metadata in its report. Schema reports themselves
remain restricted until reviewed. Exceptions are sanitized. Server jobs use restrictive
umask; configure private storage ACLs according to the institution's actual rules.

No automatic results download, MIMIC download or credentials in Git. Models trained on
restricted data are not automatically publishable. Public aggregates need review for
small cells and institutional disclosure requirements; this project does not invent
those thresholds. The `IES_EXECUTION_CONTEXT` variable is an accidental-use guard,
not proof of institutional approval or a security sandbox.

The bounded feasibility command adds a strict server-local mapping contract and reads
only projected columns under explicit source limits. Real row values exist in memory
only on the server. Neither the row iterator nor the validator persists records.
The only result payload contains fixed aggregate counters, completion/limit state,
and format version. Paths, physical columns, action values, identifiers, timestamps,
example rows, predictions, per-patient splits and exception payloads are excluded.

Run output directories have mode 0700 and report files 0600; worker core dumps are
disabled. Linux address-space, CPU-time and affinity limits plus a parent timeout
complement Slurm allocation. External worker output is suppressed and errors are
reported without payloads. A resource kill can leave no report; never interpret that
as zero events or success. Full aggregate reports remain restricted because small
cells are not automatically safe to disclose. Existing metadata audit reports have
a different contract and remain server-local too.
