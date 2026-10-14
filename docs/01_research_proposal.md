# Research proposal

## Problem and gap

Routine EHR sequences mix decisions, delivery of care, and measurements. A medication
order is a decision under observed patient state and workflow constraints. Its first
administration, discontinuation, and observation cutoff are distinct outcomes.
The research gap to verify is whether an explicit conditional execution model adds
value beyond a sufficiently capable event-type-aware sequence model.

## Approach

Start at order creation with 24 hours of information available at that time. Estimate
cause-specific event intensities and survival; use physiological prediction only after
a clinically defensible drug–measurement pair and measurement process are established.
All baselines receive identical available events and labels. Compare parameter counts,
optimization budgets, data fractions, and department/workflow shifts.

## Evidence and deliverables

The immediate evidence is engineering evidence: tests, censor-aware likelihood, and
reproducibility on fictional trajectories. Next establish direct order–administration
linkage, timestamp semantics, and observable followup. Later evaluate calibration,
likelihood, transfer, and state prediction with patient-cluster uncertainty estimates.

## Negative findings

Type embeddings may be sufficient. Apparent improvements may disappear after matching
parameters or inputs. Execution prediction may encode institutional workflow without
improving patient representation. Each outcome limits the claim and may motivate a
measurement/benchmark paper or discontinuing the architecture branch.
