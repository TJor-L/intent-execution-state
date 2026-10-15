# Clinical cohort protocol gate

Status: **draft contract implemented; real cohort extraction remains disabled**.

The complete coherent feasibility run establishes that direct linkage and first-event
classification are technically runnable for a fixed small seed domain. It does not
establish an adult inpatient population, a medication study domain, population event
rates or adequate sample size. Those decisions must be frozen before extraction and
must not be chosen by inspecting successful administrations.

`configs/clinical_protocol.example.yaml` fixes the engineering invariants already
supported by tests: order creation known at index, 24-hour input and followup windows,
occurrence plus availability time, direct observation coverage, patient-level seeded
splits, no global calendar split, first execution only, rejection of repeated
administrations and terminal ties, and no laboratory features.

Four server-local decisions remain deliberately unset:

1. Reviewed adult-age derivation and its evidence.
2. Reviewed inpatient definition and encounter handling.
3. One or two prespecified medication categories with reviewed eligibility, excluding
   continuous infusions and unresolved PRN/recurring semantics.
4. Minimum eligible-order and execution-event thresholds justified by a precision or
   power review before extraction, not selected after observing cohort yield.

Run the data-free planner with an ignored private copy:

```bash
uv run ies protocol-plan --protocol configs/clinical_protocol.local.yaml
```

The planner emits only readiness flags and generic missing-decision names. It never
prints medication categories or evidence references, reads clinical sources, creates
directories or submits work. `status: frozen` is rejected until every gate is filled.

After a private protocol is frozen, `cohort-vocabulary` provides the first aggregate-only
readiness step. It projects only the privately mapped PRN and frequency fields, requires
a stable complete reviewed snapshot within explicit file, row-group, row, byte, runtime,
CPU and memory limits, and writes value counts only to a restricted UCSF report. Rare
values are suppressed and no rows are persisted. A truncated or failed scan cannot be
used to approve medication eligibility. Real cohort extraction remains disabled.
