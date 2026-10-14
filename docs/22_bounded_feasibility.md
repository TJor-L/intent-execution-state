# Bounded feasibility infrastructure

This component implements the development request in docs/21_mac_development_handoff.md.
It validates a reviewed server-local mapping using bounded projected reads. It is
not a UCSF-specific cohort adapter, label export, clinical experiment or causal model.
There are no real source names, status values, rows or paths in its tracked example.

## Configuration and planning

Copy `configs/feasibility.example.yaml` to an ignored `.local.yaml` on the server.
All required concepts, absolute source paths, explicit bounds and review flags must
be populated. Institutional access, mapping semantics, qualifying actions and declared
source coverage require separate confirmation. Optional terminal fields additionally
require terminal semantics to be reviewed. Laboratory features must remain false.
Unknown keys are rejected rather than silently ignored.

`ies feasibility plan --mapping <server-local-config>` only loads/validates that
configuration. It does not stat/list/read input data, create directories or submit jobs.
Its output contains resource limits and mode only, not the mapping or source paths.
The Slurm `server.py plan feasibility` entry adds scheduler-config validation without
accessing data. Neither plan proves the configured files/fields exist.

## Logical fields (not UCSF field names)

| Source | Required concepts | Optional concepts |
| --- | --- | --- |
| orders | order_id, patient_id, occurred_at, available_at, observation_end_at | encounter_id; paired discontinued_at/discontinued_available_at and ended_at/ended_available_at |
| administrations | administration_id, direct order_id, patient_id, occurred_at, action | encounter_id; available_at is mandatory under the default column policy |

Both encounter mappings are supplied or omitted together. `encounter_policy` is
`reject_order` by default; reviewed `count_only` permits a mismatch/missing encounter
but always counts it. No key is repaired or inferred. Patient equality is mandatory.
Identifiers and action values accept strings or integers, preserving type: integer
1 and string "1" do not silently match. Invalid/missing required identities are counted.
Duplicate order IDs reject that order; duplicate administration IDs invalidate all
referenced orders seen within the scan. Missing direct links are reported separately.

Action qualification is an explicit reviewed allowlist. Other non-null actions are
excluded; missing action is unresolved and rejects a directly linked order. This
infrastructure does not invent refused/held/not-given causes. Non-dose actions do not
need dose occurrence times, but identity consistency checks still apply to their links.

## Time and first-execution policy

Times are either finite numeric hours on a reviewed common within-patient clock, or
timezone-aware Arrow timestamps normalized to UTC hours. No string parsing, timezone
guessing, date-based global split or rejection based on the present calendar date.
Naive timestamps are unsupported. Shifted future dates are allowed if their within-
patient intervals are meaningful; that must be verified on the server.

Availability must be at/after occurrence. An order must already be available at its
occurrence/index time in this MVP; delayed availability rejects it instead of moving
the prediction cutoff silently. A dose needs occurrence and availability. The default
`column` policy requires both. `occurrence_reviewed` is an explicit, server-reviewed
assumption of equality and requires the availability mapping to be null; do not choose
it simply to make validation pass. Physiology/lab input is entirely disabled.

Followup boundary is the earlier of observation end and the configured horizon after
order creation. Qualifying events must occur strictly after the order. An event is
observable by a boundary only when occurrence <= availability <= boundary. A late-
recorded event is not retrospectively supplied as known at an earlier cutoff.

Two or more qualifying administration rows reject the order, even if one is after
the horizon. The first row is stored only to analyze the exactly-one case; it is never
selected from a repeat series. Optional discontinuation/end fields represent terminal
events only if their meaning is reviewed; an administrative endpoint belongs in
observation_end_at instead. Available execution competes with available terminal events
by occurrence time. A tie rejects the order. The earliest terminal before any eligible
execution counts as terminal-without-execution; a later execution is not the first event.
No eligible event before the boundary is right censoring, never failed execution.

## Coverage and interpretation

File/directory/row truncation can hide duplicates or later doses. If either source is
truncated, all otherwise eligible orders become `unresolved_due_to_limits_orders`;
no execution/terminal/censoring counts are asserted for them. `single_qualifying_orders`
then means exactly one row **seen**, not proven to be exactly one in the source.
Repeated rows observed within a prefix still constitute a repeat diagnostic.

The first run may legitimately be limited; do not increase quotas automatically or
select conveniently small arbitrary shards to manufacture complete coverage. A later
run needs a server-reviewed source scope covering all relevant administrations and
followup. Even a complete bounded run is only complete relative to those declared
sources. Missing/unmatched IDs and invalid timestamps remain feasibility concerns,
not evidence of a reliable cohort. There is no matching by medication/time proximity.

## Limits and execution

Production execution requires Linux, an authorized UCSF marker, Slurm job context,
the reviewed clean full Git SHA and an unchanged mapping checksum. The mapping hash
is taken from the same bytes used to validate resource requests; private config is
not copied into an output artifact. Use `scripts/server.py submit feasibility`.

| Bound | Scope / enforcement |
| --- | --- |
| files / directories / directory entries | Explicit maximum per source, lazily traversed; symlinks fail rather than silently omit data |
| rows | Maximum converted/considered per source, batched with only mapped columns; no full-table read |
| keys | Combined order identity and administration identity registries; no join spill or persistent rows |
| batch_rows | Bounds Arrow batch conversion; underlying Parquet I/O/decompression still works at page granularity |
| runtime_seconds | Parent kills/waits for the worker on timeout; cooperative checks during traversal and analysis |
| cpu_seconds | Linux RLIMIT_CPU, in CPU seconds for the worker |
| cpus | Slurm allocation, worker CPU affinity, Arrow/BLAS thread limits |
| memory_mb | Slurm job allocation and worker RLIMIT_AS address-space ceiling; virtual memory differs from RSS |

Hard ceilings in the contract are 64 files, 256 directories, 10,000 directory entries
and 100,000 rows per source, 100,000 combined keys, 1,024 rows/batch, 900 wall/CPU
seconds, 4 CPUs and 4,096 MiB. Configured values can be smaller and must be explicit.
The example starts at 4 files/source, 5,000 rows/source, 10,000 keys, 1 CPU, 2,048 MiB
and 60 seconds. A Slurm/system kill may preempt final report creation. Absence of a
report is a failed/unresolved run, never an empty cohort. No GPU is requested.

## Output and statistics

Only fixed aggregate counters, fixed status/limit flags, format version and mode are
written. Counters cover rows considered, identity/time problems, linkage consistency,
actions, observed single/repeated orders, rejections, eligible first outcomes and
incomplete coverage. Diagnostics overlap and do not sum to a cohort denominator;
rejected_orders counts indexed distinct orders, not every invalid source row.

`complete` means declared sources exhausted within limits; `limited` means no final
eligibility claim is possible; `failed` means no valid result. For resource termination,
`counts: null` means counts are unavailable, not zero. Limited/failed commands exit
nonzero. Worker/config exceptions and process output never enter the report or console.
Directories are 0700, JSON files 0600, and worker core dumps disabled. No raw config,
identifier, field name, action, timestamp, private path, example, prediction or patient-
level split is output. All aggregate reports remain restricted pending disclosure review.

There is no train/test dataset here. The existing patient-exclusive splitter and its
invariants remain tested for future cohort use; the validator never partitions patients
or trains a model. Aggregate counts do not estimate clinical performance, event rates
for the full database, or linkage validity beyond the inspected declared scope.
