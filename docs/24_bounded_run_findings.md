# Findings from the first version 2 bounded server run

This Git handoff contains only approved aggregate operational findings. It includes
no source path, physical table or field name, action value, identifier, patient row,
timestamp value, raw schema or private evidence reference.

## Validation performed

The authorized server tested commit
`8f8772587e7acb4958ce2ef9c6668edb7042120a`. Environment setup, server preflight,
Ruff, formatting, **167 tests**, the repository boundary check and the end-to-end
synthetic demo passed.

A version 2 server-local mapping passed data-free planning. It used three reviewed
logical sources, an explicit shifted-common time policy, retrospective documentation
exclusion, patient/encounter validation and disabled laboratory features.

## Bounded-run result

Two small CPU runs produced valid `limited` reports. The first showed that the tracked
example's per-source row allowance can exhaust the shared key allowance before all
three sources receive a useful identity budget. The second reduced rows per source
without expanding any limit; all three sources and qualifying actions were considered.

No direct order or observation links occurred within the independent bounded prefixes.
Accordingly, the validator correctly asserted no execution, terminal or censoring
eligibility. The scheduler records a nonzero exit for `limited`; the restricted report,
not scheduler success alone, is the authoritative state.

This is not evidence that linkage is absent. It shows that independent prefix traversal
of separately sharded sources is structurally uninformative for this storage layout.
Automatically enlarging quotas or selecting convenient shards would not establish
reviewed coverage.

## Next design requirement

Design a separately reviewed coherent-source or key-index/probe interface before the
next real run. The design must:

- begin from an explicit server-local seed source and reviewed identity domain;
- find corresponding rows in the other sources without treating unmatched prefixes as
  linkage failures;
- distinguish rows scanned from rows retained and bound both;
- bound files, row groups, projected rows, retained keys, wall time, CPU and memory;
- preserve mapping and source-manifest checksums across planning and execution;
- keep every identifier and row in memory or restricted server storage only;
- emit fixed aggregate counters and `limited` whenever coverage is incomplete;
- reject duplicate, patient-mismatched, repeated or retrospective execution rows under
  the existing rules;
- avoid arbitrary shard selection, hidden full-table scans and automatic quota growth;
- require a separately reviewed operation before creating any persistent key index or
  coherent restricted extract.

Planning should also expose a non-sensitive worst-case identity-budget diagnostic.
The tracked example limits should not imply that three maximum-size unique sources fit
inside a smaller shared key budget.

## Scope

Do not implement a full cohort, patient-level output, laboratory features, GPU work or
automatic result transfer. A projected full-source key scan or persistent index is a
new reviewed phase, not an implicit extension of the current bounded reader.

