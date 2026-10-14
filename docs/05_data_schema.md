# Schema discovery and data dictionary

No real UCSF column name, timestamp definition, or status code is available in this
repository. The approved server handoff confirms that candidate sources exist and
a direct order–administration relationship is structurally feasible; it does not
share the physical mapping. The record reports ~155 tables, 1.4 TiB, 26.8 billion rows and 7.16 million
distinct patientdurablekey values; these are user-provided estimates, not audit results.
The candidate table names below are also unverified.

| Candidate source | Logical concepts to verify |
| --- | --- |
| medicationorderfact | order identifier, patient/encounter identifiers, creation and availability time, medication, schedule/PRN, route, dose/unit, status transitions |
| medicationadministrationfact | administration identifier, direct order foreign key, patient/encounter match, actual/recorded times, given/refused/held states, dose/unit |
| labcomponentresultfact | test code, value/unit, specimen time, result time, availability time, corrections |
| hospitaladmissionfact / encounterfact / visitfact | adult eligibility, inpatient setting, admission/discharge, observation coverage |
| diagnosiseventfact | diagnosis coding and availability time; possible later feature source |

Server-only data dictionary template:

| Logical concept | Source table/column | Type | Units | Null/sentinel semantics | Availability rule | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Order identity | Unverified | Unverified | N/A | Unverified | N/A | Pending | Blocked |
| Direct order–execution link | Unverified | Unverified | N/A | Unverified | Unverified | Pending | Blocked |
| Observation end | Unverified | Unverified | hours after index | Unverified | Unverified | Pending | Blocked |

Keep the populated dictionary and audit JSON on UCSF until approved for sharing.
The audit samples footers with bounded traversal and emits no rows, file paths,
statistics or custom key/value metadata. A shared schema in sampled files does not
prove all partitions match. Footer inspection cannot resolve status semantics, date
shifting, linkage completeness, or event availability; those require a separately
reviewed server-side feasibility query.

## Implemented logical feasibility contract

`configs/feasibility.example.yaml` contains null physical-field/path placeholders.
Only the ignored server-local mapping may supply real names or action values.
The typed contract requires both sources' identities, patient keys, order occurrence
and availability, administration occurrence/action, a reviewed dose-action allowlist
and observation end. Both encounter mappings are optional together, with an explicit
reject/count policy. Optional discontinuation/end events require reviewed terminal
semantics and separate occurrence/availability mappings.

Administration availability requires a column or an explicit reviewed equality-to-
occurrence policy; it is never inferred from the lack of a column. Numeric patient-
relative hours and timezone-aware timestamps are supported. String/naive timestamps,
unreviewed labs, missing authorization and unbounded configuration fail closed.
The implementation reads only selected columns in bounded batches and emits counters,
not source-field names, rows or a populated dictionary. See docs/22_bounded_feasibility.md.
