# Feasibility contract gaps found on the server

This Git handoff contains only approved operational findings. It contains no private
path, physical source name, field name, action value, identifier, patient row,
timestamp value or raw schema.

## Tested baseline

The authorized server tested commit
`ff14ab80d4cc07d12828f98aafece6338d841393`. Server preflight, Ruff, formatting,
111 tests, the repository boundary check and the end-to-end synthetic demo passed.

No real feasibility job was submitted because the server-local mapping could not be
reviewed truthfully under the current contract.

## Gaps discovered

1. The reviewed source exposes timezone-naive timestamps. The contract accepts
   timezone-aware Arrow timestamps or numeric hours only and has no explicit reviewed
   timezone/normalization policy.
2. The execution source does not expose a separately reviewed availability timestamp.
   Occurrence-equals-availability cannot be selected merely to make validation pass.
3. Observation end comes from a separate encounter/admission source rather than the
   order rows. The validator accepts only order and execution sources and cannot make
   the necessary bounded third-source join.
4. Order occurrence and availability remain separate logical concepts; observed
   temporal ordering is not sufficient semantic evidence.
5. The reviewed action policy identifies qualifying executions but does not supply
   general refused, held or not-given terminal causes.

## Required implementation

### Explicit time normalization

- Extend the server-local contract with an explicit reviewed policy for timezone-naive
  timestamps.
- Require a named timezone or an explicit declaration that values use a reviewed
  common shifted clock; never guess.
- Normalize only in memory and preserve occurrence and availability separately.
- Fail closed for nonexistent or ambiguous local times unless the reviewed policy
  explicitly defines their handling.
- Do not compare with the present calendar date or enable a global calendar split.

### Separate observation source

- Add a third logical source for observation coverage.
- Map its identity, patient identity, optional encounter identity, observation-end
  occurrence and availability.
- Join bounded order rows to observation rows through a reviewed direct identity;
  require patient agreement and an explicit encounter-mismatch policy.
- Do not substitute order end or discontinuation for observation end.
- Apply the file, directory, entry, row, key, wall-time, CPU and memory limits to the
  third source.
- Truncation of any source must retain `limited` status.

### Execution availability

- Keep independent execution availability mandatory by default.
- Retain occurrence-equals-availability only as an explicit reviewed policy carrying
  evidence metadata.
- When equality is used, require a reviewed exclusion policy for retrospectively
  documented actions.
- Never infer availability from the absence of a separate field.

### Terminal outcomes

- Keep qualifying execution distinct from terminal nonexecution and right censoring.
- Do not invent refused, held or not-given labels when no reviewed source exists.
- Optional generic terminal end/discontinuation still requires separate occurrence
  and availability mappings plus reviewed semantics.

## Tests to add

- timezone-naive input rejected without an explicit policy;
- reviewed timezone conversion and UTC normalization;
- ambiguous and nonexistent local-time handling;
- shifted within-patient clock accepted without calendar splitting;
- valid third-source observation linkage;
- observation patient mismatch rejection;
- encounter mismatch under both policies;
- missing or unmatched observation coverage;
- third-source truncation forcing `limited`;
- independent execution availability;
- reviewed occurrence-equality policy;
- retrospective execution exclusion under the equality policy;
- sanitized failures without physical fields, values or paths;
- data-free planning that creates no output.

## Scope

Continue to emit aggregate counts only. Do not add patient-level output, real cohort
persistence, laboratory features, GPU training or automatic result transfer. Run
`make check` and `make demo`, update the research log, publish through the ordinary
Git workflow and generate a new handoff pinned to the clean commit.

