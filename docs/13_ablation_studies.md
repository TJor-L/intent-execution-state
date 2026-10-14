# Ablation protocol

| Intervention | What it tests | Control needed |
| --- | --- | --- |
| Remove intention objective | Additional order supervision | Same observed order inputs and parameter budget |
| Remove execution objective | Contribution of executed-care learning | Same state labels and cutoff |
| Remove joint state prediction | Transfer versus event-only benefit | Same optimization steps and comparable head capacity |
| Remove elapsed-time conditioning | Timing beyond event order | Same events and vocabulary |
| Replace conditional pathways by independent heads | Explicit factorization | Same shared encoder and supervision |
| Use ordinary event-type embeddings | Structure beyond type labels | Matched capacity and available inputs |

Run paired patient splits and seeds. Report effect sizes and intervals, not only
significance. Record changes in parameter count and compute caused by each ablation.
If removing a component changes the accessible information, label it an information
ablation and do not interpret the difference as architecture alone. None are executed
in Phase 0; the single statistical model is insufficient for this protocol.
