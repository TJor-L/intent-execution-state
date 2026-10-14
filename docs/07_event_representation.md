# Canonical event contract v1

All fields here are internal names, not assertions about UCSF columns.

| Field | Meaning |
| --- | --- |
| event_id | Unique event key within a generated dataset |
| patient_id / encounter_id | Linkage identities; real identities stay on UCSF |
| event_type | observation, order, administration, cancellation, other_terminal, followup_end |
| code | Fictional concept code in synthetic data |
| event_time | Occurrence in patient-relative hours |
| available_time | First availability, at or after occurrence |
| order_id | Required on orders, outcomes and followup markers; absent on observations |
| value | Finite numeric observation, null for other types |
| synthetic | Must be true for the current executable adapter |

Parquet carries exact schema/version and synthetic provenance metadata. Validation
rejects missing/duplicate identities, orphan or cross-patient/encounter/code links,
nonfinite values, outcome-before-order, multiple terminal events, unavailable outcomes
and missing followup boundaries. One followup marker is required per order.

Dataset-level UTC/calendar conversion, unit normalization, coding dictionaries,
free text, adult eligibility and recurrent dosing do not belong to this toy contract.
A future UCSF adapter must verify and map these explicitly, preserve provenance and
availability semantics, and output only inside authorized storage. A MIMIC adapter
can reuse the logical contract after controlled access and a separate mapping audit.
Neither private adapter is currently implemented.
