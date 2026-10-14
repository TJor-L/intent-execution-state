# Next Mac development handoff

This handoff records only approved aggregate operational findings. It contains no
patient data, private path, raw schema, source column name, or restricted value.

Expected starting commit before this document was added:
`7930602fae4e19661fd1a7fede383b25a09bd304`.

## Server findings safe for development

- Candidate order and administration sources exist.
- A direct order-to-administration relationship is structurally feasible.
- Patient identity must be a required linkage consistency check.
- Encounter identity is useful for validation but must not be assumed exact.
- Repeated administrations per order are common and require explicit handling.
- A server-reviewed engineering policy can distinguish actions representing a
  dose from continuation/non-dose actions. Actual values remain server-local.
- No reliable general source for refused, held or not-given terminal causes was
  identified.
- Laboratory features do not yet have a reviewed independent availability rule.

These findings do not authorize a real cohort extraction or clinical claim.

## Development objective

Implement a generic, configuration-driven bounded feasibility adapter. It must
validate whether a reviewed server-local mapping can support a first-execution
design without embedding UCSF table names, columns, paths or status values in
tracked source.

The first server run must emit aggregate validation counts only. It must not
persist patient-level rows or silently substitute synthetic data.

## Server-local mapping contract

Define a typed logical contract requiring mappings for:

- order and administration identities;
- direct order-to-administration identity;
- patient identity on both sources;
- optional encounter identity on both sources;
- order occurrence and availability times;
- administration occurrence time and action;
- a reviewed qualifying-action allowlist;
- optional order discontinuation and end times;
- observation-end time.

Real mappings and status values belong only in an ignored server-local config.
The tracked example must contain placeholders and keep institutional access set
to false. Validation must fail closed when authorization, required concepts,
absolute paths or explicit bounds are missing.

## First-execution rules

- Join with the configured direct order key.
- Require patient-key agreement and reject mismatches.
- Count encounter mismatches separately; never silently repair them.
- Require a reviewed qualifying action and administration occurrence time.
- Reject an order from the current MVP when it has multiple qualifying
  administrations. Do not silently choose the earliest row.
- Never label an order without qualifying administration as failed execution.
- Keep documented terminal end/discontinuation distinct from right censoring.
- Right-censor when observation ends before a qualifying execution or reviewed
  terminal event.
- Preserve occurrence and availability time separately at every cutoff.
- Exclude features unavailable at the prediction cutoff.
- Keep laboratory features disabled until an explicit availability rule exists.
- Continue patient-level splits. Do not use a global calendar split until
  shifted-date behavior is verified.

## Aggregate-only feasibility output

The first server command may report only aggregate counts for:

- considered orders and administrations;
- missing required identities or times;
- matched and unmatched direct links;
- patient and encounter mismatches;
- qualifying and excluded actions;
- single and repeated qualifying administrations;
- terminal-without-execution and right-censored orders;
- temporal-ordering violations;
- configured limits reached.

It must not emit identifiers, paths, source field names, raw actions, example
rows, timestamps, predictions or exception payloads. Restricted output stays
outside the repository with restrictive permissions.

Add hard limits for files, directories, rows or keys, runtime, CPU and memory.
Planning must not read data or create output. Submission remains CPU-only and
must verify the clean expected commit. Do not add cohort extraction, GPU
training or automatic artifact download.

## Required synthetic tests

Use neutral generated names and values. Cover at least:

1. valid direct linkage with matching patient and encounter identities;
2. patient mismatch rejection;
3. explicit encounter mismatch handling;
4. missing direct order identity;
5. occurrence-before-availability rejection;
6. post-cutoff feature exclusion;
7. one qualifying administration accepted;
8. repeated qualifying administrations rejected;
9. continuation/non-dose actions excluded by configuration;
10. terminal discontinuation distinct from execution;
11. observation-end right censoring;
12. unresolved orders censored rather than labeled failure;
13. patient-level split invariants;
14. ignored local config and no-data Git handoff;
15. sanitized errors without record values or private paths.

## Documentation and acceptance

Update the README, schema, experiment-design, privacy, remote-development,
research-log and server-prompt documents to describe the implemented contract
accurately. Keep the component labeled bounded feasibility infrastructure until
it is runnable and tested; do not claim that a UCSF cohort adapter exists.

Before publishing:

```bash
make check
make demo
```

Review the diff for data leakage, commit source and docs only, run
`make handoff`, and publish through the ordinary non-force workflow. The next
UCSF handoff must be pinned to the new clean full commit SHA.

Acceptance requires that no real schema knowledge enters Git, every temporal
decision respects occurrence and availability time, repeated administrations
fail explicitly, unexecuted is never treated as failed execution, output is
bounded and aggregate-only, and both required Make targets pass.
