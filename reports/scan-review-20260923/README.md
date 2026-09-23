# Scan review — 23 September 2026

The current source-only scan reports **0 errors, 25 warnings and 104 info**
across **339 files / 2,096,959 bytes**. The broad supplied scan reports 1,834
findings across 10,076 files / 584,342,811 bytes. These scopes differ: the source
scan includes current runtime source and excludes generated copies and reports.
Neither is a complete security or deployment qualification.

The scanner wrapper now includes `runtime/`, including its code, dependencies
and tests. Its regression test also checks that ignored runtime build and
environment copies stay excluded. The original supplied scan files are intact;
their fingerprints and the read-only workspace observation are in
[review.json](review.json).

## Evidence

- [Initial scoped scan](../source-scan/20260923-runtime-review/findings.md):
  1 error, 26 warnings, 104 info. The new error and one warning matched the
  literal `synthetic-credential` in a mocked SDK response. It was not a secret.
- [Final scoped scan](../source-scan/20260923-runtime-review-final/findings.md):
  0 errors, 25 warnings, 104 info. That test now generates its fixture value and
  still checks exact credential forwarding. No production authentication changed.
- [Scope and source fingerprints](../source-scan/20260923-runtime-review-final/scope.json)
  identify every copied file and current working-tree content. The baseline Git
  commit is recorded there; the uncommitted changes are captured by file hashes.
- The focused source-selection tests passed (2 cases). Managed commit hooks run
  the required source guards and both isolated Python runtime suites.

## BP-273 is not reproduced

On `fevm-gdpr2`, `databricks global-init-scripts list --output json` returned
`[]`. A direct authenticated GET of `/api/2.0/global-init-scripts` returned `{}`,
with **zero scripts**. There is currently nothing to delete or annotate.

The supplied scanner row records count 1 but does not retain its raw response.
This discrepancy could involve response-shape handling or state/run context;
its cause is not established. Current absence does not prove the exact state at
the earlier scan instant. Do not classify it as a confirmed current failure or
change workspace scripts based solely on that row.

Only metadata was read. No script content, personal OAuth token, SQL warehouse
query, resource mutation or compute start was required.

## Remaining source warnings

| Rules | Hits | Review |
|---|---:|---|
| BP-101 | 6 | Production findings include atomic registry/migration writes and the local publisher's unique batch ID, `BEGIN IMMEDIATE`, and immutable receipt replay. Test fixtures deliberately insert data or drift. `INSERT` alone does not establish a duplicate-write defect. The Delta review store already uses immutable-key `MERGE`. |
| BP-128 | 7 | The engine calls `tracking.evaluate_pairs`, which logs the input, MLflow evaluation and evaluation contract. Other hits are tests and bounded campaign/canary tools; a small `start_run` body alone is not missing logging evidence. No new MLflow experiment was run for this review. |
| BP-381 / BP-542 | 6 | These bundles do not provision custom model-serving endpoints; adding unused resources would not remediate a project defect. |
| BP-059 | 2 | `workflow.py:70` binds values with `%s` and appends a fixed lock clause. The second report hit is `tests/postgres/test_workflow.py:84`, whose table names come from a fixed tuple. It is not a second production hit at workflow line 84. |
| BP-549 / BP-555 | 2 | The Genie builder uses the actual `enable_format_assistance` field and sorts `join_specs` by ID. The grep rules do not recognize those existing implementations. |
| BP-551 | 1 | No Genie cover image; cosmetic demo improvement remains open. |
| BP-131 | 1 | The dated serverless canary uses a personal experiment path. This is a historical campaign utility; customer packaging still needs portable environment inputs. |

The builder also contains example SQL, SQL snippets, synonyms, purpose,
disambiguation and data-quality instructions. The broader report includes
heuristic matches in audit scripts, which are not definitions of Genie spaces.
This review neither changes nor qualifies the live Genie configuration.

## Online errors are unevaluated

The supplied online statistics are 46 attempted, 10 evaluated (9 pass, 1 fail),
24 unsupported predicates and 12 errors. The errors break down as **7 SqlFailed,
4 not-found and 1 HTTP error**; they are not twelve SQL failures plus five more.
The row-level failed predicate is BP-273, discussed above. Unsupported predicates
and failed requests remain unknown; they must not be counted as passing controls.
The precise SQL failure causes were not established by this metadata-only review.

LF-A remains 8/8, LF-B 12/12 and LF-C **8/8**. This maintenance review consumes
no deployment experiment and does not authorize the proposed LF-C limit increase.
The pending live installation and certificate fix keep their prior status.
