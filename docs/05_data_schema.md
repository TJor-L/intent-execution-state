# Schema discovery and data dictionary

No UCSF column name, relationship, timestamp definition, or status code has been
verified. The record reports ~155 tables, 1.4 TiB, 26.8 billion rows and 7.16 million
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
