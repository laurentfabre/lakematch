# LF-B checkpoint — updated 22 September 2026

**Phase B is in progress: 2/8 experiment slots consumed.** Phase A and LM-001 are
complete at commit `96edbf8`. This increment adds portable company normalization
and bounded candidate unions, separate from the existing Spark v1 configuration
and frozen replay contracts. It does not add a classifier or deploy an app flow.

## Candidate comparison

The [predeclared comparison](CANDIDATE_PLAN.md) used 4,000 ERP anchors against
4,000 CRM records in the synthetic validation partition. The corpus, generator
and split hashes were committed before the run; confirmation remains
unmaterialized. Every ERP anchor and all 4,000 known positives are included.

| Alternative | Candidate recall | Retained pairs | Raw posting visits | Truncated anchors | Positive cap losses | Local retrieval time |
|---|---:|---:|---:|---:|---:|---:|
| Identifier + jurisdiction | 65% | 3,000 | 3,000 | 0 | 0 | 0.066 s |
| Plus normalized names | 95% | 8,552 | 10,552 | 0 | 0 | 0.080 s |
| Plus lexical tokens | 100% | 190,137 | 216,687 | 1,966 | 0 | 0.614 s |
| Plus character trigrams | 100% | 200,000 | 1,326,629 | 4,000 | 0 | 2.127 s |

These are measured local retrieval times including index construction, not
serving latency or a remote scale result. All alternatives used the same limits:
50 unique candidates per ERP after union, 2m retained pairs, 20m raw posting
visits and 120 seconds. Observed process peak memory stayed below **223 MiB**
(4 GiB gate); the peak includes earlier alternatives in the same process.

The predeclared cheapest-passing selection is **identifier + normalized name**:
95% recall at 2.138 retained pairs per anchor. It misses **all 200 combined-error
positives** (missing ID + spelling/suffix change + changed address). This limitation
must remain visible; the overall gate does not establish robustness in that
stratum. The lexical union recovers those 200 positives at approximately **22.2×**
as many retained pairs and remains within every envelope. Trigrams add no recall
on this workload and increase expansion. Subsequent scorer/calibration work must
record its chosen candidate configuration and this cost/coverage trade-off before
confirmation release. No auto-merge or product promotion is implied.

The lexical methods hit per-anchor caps, so their truncation is reported explicitly.
No known positive was lost at those caps on this validation partition. Per-stratum
and method contributions, hashes and timing are in the
[compact report](candidates-validation-v0.1.json). Raw candidate receipts remain
under ignored `data/lakefusion/candidate-validation-v0.1/` with checksums in that
report and can be reproduced from the frozen source corpus.

## Verification and limits

The [run](../../experiments/20260921T125904Z-lf-b-candidate-unions-e50a8b/manifest.json)
passed its focused contract/retrieval tests and comparison. Tests cover missing-ID
recovery, provenance, cap losses, fail-closed global budgets, duplicate keys,
feature exclusions and order independence; see [JUnit](candidate-tests-v0.1.xml).
Owned-process cleanup passed. No cloud resource or AI call ran. Historical public
corpus recall has not changed, and this synthetic experiment does not qualify
general customer data, merge precision, online latency or Spark scalability.

## Next work

LM-002/003 are complete for the declared two-source contract: the selected
candidate method now has a durable approved execution binding. Transactional
identity allocation (LM-004) is next. Survivorship and field provenance
(LM-005/006), publication and the first golden-record app view remain unimplemented.
Later remote/application gates listed in the Phase A freeze remain mandatory.

## Durable registry and exact job replay — 22 September

The second [LF-B experiment](../../experiments/20260921T221824Z-lf-b-registry-5fab9f/manifest.json)
passed **93 tests with no errors, failures or skips**, including 18 real PostgreSQL
integration cases. The [report](registry-20260922.json) and
[JUnit evidence](registry-tests-20260922.xml) retain exact results.

The optional PostgreSQL adapter persists immutable domain, mapping and execution
definitions, expected-version/revision checks, independent approval and append-only
history. Checksummed migration 0002 is additive; changed migrations, downgrades and
unattributed legacy approvals fail without partial application. Concurrent submits
and approvals have one winner; failed audit insertion rolls back the definition.
Approvals remain identical after an actual PostgreSQL process restart.

The bound job validates both input schemas, code and contract hashes, then
reproduces the preceding `identifier_name` candidate rows exactly: **8,552 pairs,
3,800/4,000 positives, 95% recall**. This preserves the original 200 combined-error
misses and does not tune or regenerate confirmation data. The separate seven-row
CRM preview accepts six legal companies and quarantines one branch. The explicit
v1 adapter preserves string identifiers and rejects incompatible old configs
without mutating them.

Observed main-process peak RSS was **89.2 MiB**. Local PostgreSQL 16.15 used a
private Unix socket with TCP disabled and fsync enabled; owned server/process
cleanup passed. psycopg 3.3.5 is an optional locked dependency. No cloud service or
AI call ran, and no existing database was used for resets. The full contract,
operator instructions and limitations are in [REGISTRY.md](../../spec/lakefusion/REGISTRY.md).

This is an internal worker/storage capability. Actors in the evidence are
synthetic fixtures; HTTP authentication, domain grants, database RLS, Lakebase
OAuth/connection tests, publication and app integration are not claimed complete.
