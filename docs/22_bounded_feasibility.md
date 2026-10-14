# Bounded feasibility infrastructure

This component implements docs/21_mac_development_handoff.md and the contract gaps
reported in docs/23_feasibility_contract_gaps.md. It validates a reviewed server-local
mapping using bounded projected reads. It is not a UCSF-specific cohort adapter,
label export, clinical experiment or causal model. No real source names, status
values, rows or paths belong in the tracked example.

The first server runs returned valid limited reports without links between independent
prefixes (docs/24_bounded_run_findings.md). The next step is review of the proposed
coherent-access interface in docs/25_coherent_access_design.md, not an expanded prefix
run. That new backend is not implemented; the executable described here remains v2.

## Version 2 configuration and migration

Mapping and aggregate report schemas are now version 2. Version 1 mappings are
rejected, not silently migrated. Start from `configs/feasibility.example.yaml` on the
server; preserve any earlier local mapping privately for reference. Replace the old
order `observation_end_at` mapping with a reviewed direct `observation_id` and fill the
separate observation source. Reconfirm the review flags; copying a true flag from an
older mapping is not evidence that the new semantics were checked.

All required concepts, absolute source paths, explicit bounds and review flags must
be populated in an ignored `.local.yaml`. Institutional access, mapping semantics,
qualifying actions and source coverage require separate confirmation. Direct observation
linkage and its retrospective coverage endpoint each require review. Optional terminal
fields additionally require reviewed terminal semantics. Labs must remain false.
Unknown keys are rejected. There is no automatic migration of private mappings.

`ies feasibility plan --mapping <server-local-config>` only loads/validates configuration.
It does not stat/list/read source data, create directories or submit jobs. Its output
contains resource limits and mode, not the mapping or source paths. The Slurm
`server.py plan feasibility` entry adds scheduler-config validation without accessing
data. Neither plan proves configured files/fields exist. Named-zone validation may
read the installed timezone database; it never reads clinical storage.

Planning also reports `identity_budget`: three times the per-source row cap is the
worst-case total registry size. It exposes capacity, shortfall and whether all source
row caps fit. `balanced_rows_per_source_at_key_capacity` is integer arithmetic, not
a recommendation to enlarge scans. Existing configs are never rewritten. The public
summary explicitly identifies `independent_source_prefixes` and does not claim coherent
linkage coverage, even if the key budget fits. Planning does not guarantee memory use.

## Logical fields (not UCSF field names)

| Source | Required concepts | Optional concepts |
| --- | --- | --- |
| orders | order_id, patient_id, occurred_at, available_at, direct observation_id | encounter_id; paired discontinued_at/discontinued_available_at and ended_at/ended_available_at |
| administrations | administration_id, direct order_id, patient_id, occurred_at, action | encounter_id; available_at mandatory under the default column policy; documentation_status mandatory under the equality policy |
| observations | observation_id, patient_id, ended_at, available_at | encounter_id |

Order and administration encounter mappings are supplied or omitted together. The
observation encounter mapping may be omitted independently; if supplied, an order
encounter mapping is required. Omitted comparisons are counted as unavailable.
`encounter_policy` governs administration links; `observation_encounter_policy` governs
observation links. Both default to `reject_order`; reviewed `count_only` permits a
mismatch/missing encounter but always counts it. No key is repaired or inferred.
Patient equality is mandatory for both joins regardless of encounter policies.

Identifiers and action/documentation values accept strings or integers, preserving
type: integer 1 and string "1" do not silently match. Invalid/missing identities are
counted. Duplicate orders reject that order; duplicate administrations invalidate all
referenced orders seen in the scan. Multiple orders may share one observation record.
Duplicate observation IDs reject all linked orders; no arbitrary latest/earliest row
is selected. Missing/unmatched observation links or invalid observation times reject
the order. Order end or discontinuation never substitutes for observation coverage.

Action qualification is an explicit reviewed allowlist. Other non-null actions are
excluded; missing action rejects a directly linked order. This infrastructure does
not invent refused/held/not-given causes. Non-dose actions do not need dose occurrence
times, but identity consistency checks still apply to their links.

## Reviewed time normalization

All three sources must use the same reviewed time representation and compatible
within-patient clock. `numeric_hours` accepts finite numeric hours; `timestamp_utc`
accepts timezone-aware Arrow timestamps and normalizes them to UTC hours.
`timestamp_naive` requires a `naive_time_policy` with `reviewed: true` and a private,
nonempty `evidence_reference`. The two supported policies are:

- `named_timezone`: a reviewed IANA timezone is mandatory. UTC round trips detect
  ambiguous and nonexistent local times. Ambiguity defaults to `reject`; only an
  explicit reviewed `earlier` or `later` policy may select a UTC instant. Nonexistent
  times always reject; automatic clock shifting/repair is not implemented.
- `shifted_common`: explicit declaration that naive values share a meaningful clock
  within each patient across all three sources. `timezone` must be null, and both
  ambiguity/nonexistence settings remain `reject`. Values are treated as an arbitrary
  interval clock, not civil UTC dates; civil daylight-saving rules do not apply.

Normalization happens only in memory. There is no string parsing, host-timezone
fallback, calendar split or comparison with the present date. Shifted future dates
are accepted. A named timezone must exist in the server's installed timezone database;
an unknown/missing zone fails without exposing its name. `naive_time_policy` must be
null for the other encodings. Mixed encodings or per-source timezone rules are not
implemented; do not pretend incompatible sources share a clock to pass validation.

## Execution availability and retrospective documentation

Availability must be at/after occurrence. An order must already be available at its
occurrence/index time in this MVP; delayed availability rejects it instead of silently
moving the cutoff. Order availability remains independently mapped; observed temporal
ordering alone does not establish its semantic meaning.

A dose needs occurrence and availability. Default `column` policy requires both,
with `documentation_status` and `occurrence_equality_policy` null.
`occurrence_reviewed` instead requires the availability mapping to be null, a mapped
`documentation_status`, and an `occurrence_equality_policy` containing a true review
flag and nonempty private evidence reference. Its `retrospective_exclusion` additionally
needs its own review/evidence and disjoint, nonempty `contemporaneous_values` and
`retrospective_values` lists, using the same strict integer/string typing as keys.

Only a qualifying dose in the reviewed contemporaneous class may assume equality.
A retrospective, missing or unknown documentation class rejects the **entire linked
order**, rather than dropping a dose and manufacturing censoring or a singleton.
Such doses still count toward observed repeat diagnostics. Non-dose actions do not
use the equality assumption. Classification may map to the action column only if
separate server-reviewed evidence establishes that it identifies documentation timing.
If no reliable classification/equality evidence exists, stay blocked on semantics;
the absence of an availability field is never evidence of equality.
Physiology/lab input is entirely disabled.

## Observation coverage and first execution

Followup boundary is the earlier of the linked observation `ended_at` occurrence and
the configured horizon after order creation. Observation `available_at` records when
that endpoint evidence can be ascertained; it must be present and at/after the end.
The reviewed observation source must establish continuous coverage of the relevant
order window, not merely an unrelated later encounter. This validator inspects
retrospectively ascertained coverage: an endpoint first known after the boundary is
counted in `observation_endpoint_unavailable_at_boundary_orders`, never supplied as an
index-time feature or interpreted as online knowledge at the boundary. Its availability
does not extend followup. This retrospective interpretation must be reviewed before
setting `observation_end_reviewed`; online coverage ascertainment is not implemented.

Qualifying events must occur strictly after the order. An execution or terminal event
is observable by a boundary only when occurrence <= availability <= boundary. A
late-recorded event is not retrospectively supplied as known at an earlier cutoff.

Two or more qualifying administration rows reject the order, even if one is after
the horizon. The first row is stored only to analyze the exactly-one case; it is never
selected from a repeat series. Optional discontinuation/end fields represent terminal
events only if their meaning is reviewed; an administrative endpoint belongs in the
observation source. Available execution competes with available terminal events by
occurrence time. A tie rejects the order. The earliest terminal before any eligible
execution counts as terminal-without-execution; a later execution is not the first
event. No eligible event before the boundary is right censoring, never failed execution.

## Coverage and interpretation

File/directory/row truncation can hide duplicates or later doses. If any of the three
sources is truncated, all otherwise eligible orders become
`unresolved_due_to_limits_orders`; no execution/terminal/censoring counts are asserted
for them. `single_qualifying_orders` then means exactly one row **seen**, not proven to
be exactly one in the source. Repeats observed in a prefix remain a repeat diagnostic.

The first run may legitimately be limited; do not increase quotas automatically or
select arbitrary small shards to manufacture complete coverage. A later run needs a
server-reviewed source scope covering all relevant administrations and observation
records. Even a complete bounded run is only complete relative to those declared
sources. Missing/unmatched IDs and invalid times remain feasibility concerns, not
evidence of a reliable cohort. There is no matching by medication/time proximity.

## Limits and execution

Production execution requires Linux, an authorized UCSF marker, Slurm job context,
the reviewed clean full Git SHA and an unchanged mapping checksum. The mapping hash
is taken from the same bytes used to validate resource requests, including private
review metadata. The config is not copied into an output artifact. Use
`scripts/server.py submit feasibility`.

| Bound | Scope / enforcement |
| --- | --- |
| files / directories / directory entries | Maximum per source, lazily traversed; symlinks fail rather than silently omit data |
| rows | Maximum converted/considered per source; batched mapped columns only; no full-table read |
| keys | Combined order, administration and observation identity registries; no join spill or persistent rows |
| batch_rows | Bounds Arrow conversion; underlying Parquet I/O/decompression still works at page granularity |
| runtime_seconds | Parent kills/waits for worker on timeout; cooperative checks during traversal and analysis |
| cpu_seconds | Linux RLIMIT_CPU, in CPU seconds for the worker |
| cpus | Slurm allocation, worker CPU affinity, Arrow/BLAS thread limits |
| memory_mb | Slurm job allocation and worker RLIMIT_AS address-space ceiling; virtual memory differs from RSS |

Hard ceilings are 64 files, 256 directories, 10,000 directory entries and 100,000 rows
per source, 100,000 combined keys, 1,024 rows/batch, 900 wall/CPU seconds, 4 CPUs and
4,096 MiB. Configured values can be smaller and must be explicit. Current example defaults are
4 files/source, 3,000 rows/source, 10,000 keys across all three sources, 1 CPU,
2,048 MiB and 60 seconds. A Slurm/system kill may preempt final report creation.
Absence of a report is a failed/unresolved run, never an empty cohort. No GPU requested.

## Output and statistics

Only fixed counters, fixed status/limit flags, format version and mode are written.
Counters cover rows in each source, identity/time problems, both linkages, actions,
retrospective/unknown documentation, observed single/repeated orders, rejections,
eligible first outcomes and incomplete coverage. Diagnostics overlap and do not sum
to a cohort denominator; rejected_orders counts indexed distinct orders, not every
invalid source row. Matched observation links count orders, not unique endpoints.

`complete` means declared sources exhausted within limits; `limited` means no final
eligibility claim is possible; `failed` means no valid result. For resource termination,
`counts: null` means unavailable, not zero. Limited/failed commands exit nonzero.
Worker/config exceptions and process output never enter the report or console.
Directories are 0700, JSON files 0600, and worker core dumps disabled. No raw config,
identifier, field name, action, timestamp, private path, timezone, review evidence,
example, prediction or patient-level split is output. All aggregate reports remain
restricted pending disclosure review.

There is no train/test dataset here. The existing patient-exclusive splitter remains
tested for future cohort use; the validator never partitions patients or trains a
model. Aggregate counts do not estimate clinical performance, full-database event
rates or linkage validity beyond the inspected declared scope.
