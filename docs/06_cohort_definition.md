# Cohort definition

Implementation status: the data-free protocol parser/planner is runnable and tested;
real cohort extraction remains disabled. See docs/26_clinical_cohort_protocol.md and
`configs/clinical_protocol.example.yaml` for the freeze gate.

Planned clinical cohort: adult inpatients with eligible medication orders. The actual
adult-age derivation, inpatient indicators, medication categories and source fields
remain unverified. Select one or two categories with reliable direct linkage and
simple first-dose semantics; initially exclude continuous infusions and unresolved
PRN/recurring orders. Do not select the cohort using future administration presence.

Index is order creation known at prediction time. Input window is the preceding 24h,
including the index order; an observation must have occurred and been available by
index. Followup ends at the earlier of a prespecified 24h horizon and verified
observation coverage. Cancellation/another terminal cause is an observed competing
event only when its meaning and time are known. No observed administration alone
implies neither cancellation nor failure.

The toy cohort has two orders per patient, first terminal event per order, explicit
followup end and independent administrative censoring. Labels use time since order.
All orders for one patient share one deterministic train/validation/test assignment.
This synthetic implementation does not enforce clinical adult/inpatient eligibility.

Before clinical extraction, define discharge/death handling, event ties, delayed
recording, scheduled time versus actual time, same-day precision, encounter changes,
and multiple administrations. Reject ambiguous examples with counted exclusion reasons;
do not infer labels from drug/time proximity without validating the match method.
