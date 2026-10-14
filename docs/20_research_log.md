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
