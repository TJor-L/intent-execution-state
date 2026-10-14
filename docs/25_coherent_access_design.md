# Coherent bounded access: design for server review

Status: **the coherent-manifest executor is implemented and synthetically tested; no
reviewed clinical manifest exists**. The capability review found no approved exact-key
index and found that existing patient-sharded MEDS artifacts omit identities required
by this validator. The alternative indexed-probe backend remains unimplemented. Do not
submit another prefix job as a test of coherent coverage, fabricate locators, or build
an index/full-source extract under this interface.

Workflow update: the user has moved primary development/testing to UCSF. The server
agent should review capabilities and implement/test a supported backend in the same
work cycle, then perform bounded validation within established authorization and limits.
There is no longer a review-only stop or a required return to the Mac for implementation.
This design is a starting specification; revise it using server evidence while preserving
coverage, temporal, resource and data-boundary invariants. Prefer one working backend
over implementing every possible backend before any validation.

## Problem and decision

The server obtained valid limited reports but no links between independent source
prefixes. That does not estimate linkage failure or execution prevalence. Reducing
rows can fix registry pressure; it cannot align separately sharded sources.

The next executor must start from an explicit, reviewed order seed domain and retrieve
all potentially relevant rows for those keys through a reviewed access method. There
are two candidate backends; neither is assumed to exist on UCSF:

| Backend | Required existing capability | Evidence needed before implementation |
| --- | --- | --- |
| coherent manifest | An already approved, immutable set of source files/row groups covering the seed domain across all three sources | Provenance establishing complete order, administration and observation coverage for that domain, including duplicates and late records |
| indexed probe | An existing approved index/catalog/service that locates all rows for exact typed keys within an immutable source snapshot | Key domain, snapshot lineage, complete candidate enumeration, bounded index work, bounded physical reads and explicit incomplete/error responses |

Prefer the backend supported by existing reviewed infrastructure. A hand-picked shard,
an arbitrary SQL `LIMIT`, a time-nearest join or a generic predicate over all Parquet
files is not an acceptable substitute. A backend that hides a full key scan behind an
index-like API is not bounded probing. Creating an index or coherent extract is a
separate operation with its own scope, resource estimate, authorization and review;
this design does not authorize that operation.

## Server-local coherent-manifest contract

The manifest is separate from the existing logical mapping. It contains no
inline patient/order keys; it refers to an explicit seed source. All populated
manifests, review references, locators, receipts and hashes stay on restricted UCSF
storage. Only placeholder schemas and synthetic examples may enter Git.

| Section | Required information |
| --- | --- |
| version and mode | Explicit contract version; `coherent_manifest` or `indexed_probe`; no automatic fallback |
| mapping binding | SHA-256 of the exact reviewed mapping bytes |
| seed | Explicit order-source reference; declared deterministic selection rule; reviewed identity domain and eligibility semantics; review reference |
| snapshot | Immutable generation identifier and existing provenance reference; mapping/clock/key compatibility across all sources |
| orders | Coverage of every order row with each selected order key, including duplicate identities outside the seed location |
| administrations | Coverage of every row linked by selected order keys, across actions, patients, encounters and times |
| observations | Coverage of every row linked by the selected orders' direct observation keys, including duplicate identities |
| access evidence | Reviewed provider capability/coverage evidence and existing artifact-generation references |
| limits | Explicit scan, retention, probe and resource ceilings listed below |

For a coherent manifest, each source includes a bounded explicit list of file
references and row-group ordinals, bound to the immutable generation. No recursive
glob or directory discovery is allowed in the executor. For indexed probes,
the manifest binds an approved provider identifier and its index generation; returned
locators must belong to the same snapshot and pass the same file/row-group budget.
The provider identifier selects vetted code, never executable code, shell commands or
arbitrary SQL embedded in config.

The seed domain must be specified before observing successful joins. Its selection
must be reproducible from the existing snapshot and reviewed selection rule. Selection
is not a representative population sample unless a separate sampling design establishes
that. If the declared seed selection exceeds its cap, return limited; do not quietly
redefine the population as whichever prefix happened to fit.

## Private request/response interface

The following remains the general provider protocol. The implemented coherent-manifest
path realizes its bounded read/finalize behavior directly; an indexed provider does not
yet implement this protocol:

```text
prepare(mapping_snapshot, source_manifest_snapshot, code_sha)
  -> private plan receipt + fixed public budget summary

open_seed(receipt, budget)
  -> bounded stream of projected order rows + seed coverage receipt

probe(source_role, typed_keys, receipt, budget)
  -> bounded stream of projected rows + coverage receipt

finalize(seed_coverage, order_coverage, administration_coverage,
         observation_coverage, budget, validation_counts)
  -> fixed aggregate report
```

Keys and row streams exist only in worker memory. Coverage receipts are private and
must carry the request identity, source/index generation, exact requested domain and
completion state. A count of returned rows or a provider `success` flag is not proof
that all requested keys were exhausted. Pagination must expose exhaustion separately
from truncation. Missing proof is incomplete coverage, never a complete empty result.

Execution sequence:

1. Check the clean expected code SHA and both pinned config snapshots before source
   access. Apply worker CPU/memory/time limits before index or data reads.
2. Read the declared order seed with all required logical columns and a seed count
   cap. Keep typed direct order and observation identities in bounded registries.
3. Confirm all order rows for the selected keys, using manifest coverage or exact-key
   order probes. A duplicate outside the initial seed location must still reject its
   order. Re-reading a seed row during this confirmation must not invent a duplicate;
   use a bounded snapshot locator or replace the seed copy with the confirmed stream.
4. Probe administrations by order identity and observations by direct observation
   identity. Request **all** matching rows before applying patient, encounter, action
   or time checks. Filtering by patient, qualifying action or horizon in the probe
   could hide mismatches, repeats, retrospective records or duplicate observations.
5. Pass complete retained streams through the existing first-execution rules. For
   incomplete coverage, retain diagnostics but suppress final eligibility. Avoid a
   second unbounded copy of retained rows; count any bounded buffering against memory.

No output includes keys, source paths, row locators, action values or source exceptions.
No patient-level extract, key cache, query spill or index is persisted by this executor.
If a provider requires any such persistence, it does not satisfy this interface and
needs a separately reviewed operation.

## Work accounting and limits

Scan and retention are different budgets. Filtering cannot reset either one. All work,
including seed reads, duplicate-confirmation probes, retries, pagination and unmatched
candidate reads, must be charged before it exceeds a limit.

| Bound | Required accounting |
| --- | --- |
| seed orders | Rows considered under the declared seed selection; a capped selection is incomplete |
| files | File-open/read attempts per source, including repeated probes; no unbounded discovery |
| row groups | Row-group read attempts per source, including repeated reads, not only distinct groups |
| projected rows scanned | Every projected row materialized before key/action/patient filtering; include nonmatches and re-reads |
| rows retained | Every matching row handed to validation per source, including invalid rows, duplicate IDs, repeats and excluded actions |
| retained keys | Shared total across seed/order, administration and observation registries; do not count a seed key twice when its confirmed order replaces it |
| probe keys/requests | Explicit keys per request and total requests; pending key batches also consume the shared retained-key budget |
| index work | Bound index pages/nodes and bytes before access; output row count is not a substitute for index work |
| bytes read | Explicit I/O ceiling for index and source reads, including retries; implementations must expose/enforce it |
| wall/CPU/memory | Existing parent timeout, worker RLIMIT_CPU/RLIMIT_AS, affinity/thread limits and Slurm allocation; no quota growth |

Parquet I/O operates at page granularity. A projected-row limit alone does not bound
decompression/I/O. The coherent-manifest backend therefore charges the full
uncompressed size recorded for each selected row group before materialization, in
addition to file/group and row limits. CPU and memory guards remain necessary. An
external query service must enforce
physical work limits and expose trustworthy accounting. A client timeout and small
result limit do not prove that server-side full scans were bounded.

Candidate starting ceilings for review: 64 seed rows, 4 file reads/source, 16 row-group
reads/source, 3,000 scanned rows/source, 1,000 retained rows/source, 10,000 shared keys,
64 keys/request, 64 requests, 64 index pages and 64 MiB total bytes read. Retained rows
cannot exceed scanned rows; seeds cannot exceed retained order rows. The byte/index
numbers are proposed ceilings, not measurements or claims about source layout.
Retain 1 CPU, 2,048 MiB and 60 seconds wall/CPU limits. If useful coverage cannot fit,
report the constraint; do not enlarge limits or create preparation artifacts silently.

For current prefix planning, worst-case registry entries equal
`number_of_sources * max_rows_per_source`: 3 * 5,000 exceeds 10,000 keys. The revised
example uses 3,000 rows/source (9,000 worst-case entries), preserving all other limits.
The public `identity_budget` reports the worst case, capacity, shortfall and whether
the row caps fit. Existing local configs remain unchanged. This arithmetic is neither
a memory guarantee nor evidence of coherent coverage. Future planning must additionally
account for pending probe keys and distinguish scanned caps from retained caps.

## Checksums, planning and execution

Planning reads only explicit mapping and manifest bytes, validates declarations and
does not stat/open clinical sources, build an index, hash clinical files or create
output. Load each input once; compute its SHA-256 from the same bytes that were parsed.
The in-memory private plan receipt binds code SHA, mapping SHA-256 and manifest SHA-256,
plus the declared source/index generation. The public summary exposes only fixed mode,
review/readiness status and resource/budget diagnostics; no private receipt fields.

An explicit reviewed submission step must persist that small receipt outside Git with
0600 permissions and pin its digests in the job. Submission rejects differences from
the reviewed plan rather than silently replanning. The worker verifies both byte hashes
and code SHA before access, then uses the parsed snapshots rather than reopening mutable
config. Queued changes fail. No fallback to the old prefix reader is allowed.

The manifest hash alone does **not** prove that referenced data/index files are unchanged.
Existing immutable-generation provenance must bind contents, membership and completeness.
Validate bounded locators against that generation before and after access. A provider
generation change, unverifiable snapshot or checksum mismatch is failed/unresolved.
File size and mtime alone are insufficient. Do not create new full-file hashes or scan
all keys just to populate a manifest: obtaining absent provenance is a separately
reviewed preparation phase. Such a requirement must be returned as a blocker.

## Report semantics and validation reuse

Proposed public counters have fixed names: seed rows, files read, row groups read,
projected rows scanned and rows retained per logical source; total probe requests,
index pages/bytes and peak registry entries; requested-key counts with complete versus
incomplete coverage; and existing validation counters. No per-key output is allowed.

- `complete`: the declared seed selection and every selected-key source lookup have
  verifiable coverage, with no exceeded budget. This is completeness for the declared
  domain, not population representativeness or clinical validity.
- `limited`: any seed/probe/scan/retention/resource limit or incomplete enumeration.
  Assert no execution, terminal or censoring eligibility for this run. Unmatched
  incomplete probes are counted as unresolved lookup coverage, not linkage failure.
- `failed`: invalid config, changed provenance, provider/reader failure or invalid
  coverage receipt. Resource termination may have unavailable counts (`null`).

An empty lookup is evidence of absence only when exact-key coverage is complete.
Qualifying-dose absence never becomes failed execution. Keep patient mismatch and
duplicate rejection, independent encounter policies, repeat rejection even outside
the horizon, retrospective/unknown documentation rejection, separate availability
checks, reviewed terminal causes and lab exclusion. These rules are not relaxed to
improve yield. No synthetic replacement for failed clinical lookup is permitted.

## Implementation acceptance and remaining validation

Synthetic shards deliberately place linked records outside independent prefixes. The
implemented coherent-manifest backend covers the applicable requirements below; the
indexed-probe-specific cases remain requirements for any future probe backend:

1. Both coherent-manifest and indexed-probe contracts reject missing/unknown coverage;
   implement only the backend actually supported by reviewed infrastructure.
2. Seeded lookup finds remote-shard matches while independent prefixes do not; complete
   empty probes differ from truncated or unsupported probes.
3. Duplicate orders outside the seed, duplicate observations, patient mismatches,
   repeated late administrations and retrospective records remain visible and reject.
4. Nonmatches consume scanned budget without consuming retained-row budget; duplicate
   rows consume retained budget. Every retry and page/group read consumes work budget.
5. Each bound can independently force limited; no outcomes survive any incomplete
   coverage, and unknown counts are not invented as zeros.
6. Config/manifest changes between plan, submit and worker fail before source access;
   source/index generation changes fail even if manifest bytes are unchanged.
7. Planning creates no output and reads no clinical source; reports/console/errors
   contain no private values, paths, keys or provenance references.
8. Linux native resource guards and the existing synthetic pipeline remain passing.

Start with existing approved documentation, catalogs and prior restricted findings,
then continue implementation and testing on the server once a backend is supported.
Do not stop just to ask the Mac to implement an ordinary code change. Publish a verified
implementation/validation milestone with coverage limitations. If neither backend can
provide the required access, complete independent code/tests and propose the concrete
separate preparation scope and cost estimate. Do not hide an unreviewed persistent
index/extract or full-source scan inside the bounded executor.
