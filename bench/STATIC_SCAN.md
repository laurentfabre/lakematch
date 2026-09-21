# Static scan remediation — 20 September 2026

The supplied scan in `reports/findings.md` and `reports/findings.json` is
preserved. It reported **0 errors, 294 warnings and 1,390 informational findings
across 9,104 files**. Most repeated warnings came from independently preserved
copies of engine source inside logged model artifacts.

The focused offline rerun in `reports/source-scan/` reports **0 errors, 15
warnings and 68 informational findings across 208 files**. This is a different,
source-only scope, so the reduction is not a count of repaired defects. No
findings were suppressed. The retained source warnings are explained below.

## Changes made

| Finding | Action and evidence |
|---|---|
| BP-101, remote review writes | Queue, review and metadata inserts now use insert-only Delta `MERGE` keyed by their immutable IDs. Sequential statement retries cannot append the same key again. Reviews read back the saved receipt, preserving its timestamp. The single-process/single-instance constraint remains; this does not add distributed uniqueness. |
| BP-101, acceptance metadata | Both local and remote fixture setup use an immutable metadata API: repeating a key/value is a no-op; changing its value is rejected. SQLite uses unique indexes, transactions and `ON CONFLICT DO NOTHING`. |
| BP-435, resource tags | Both jobs and the pipeline now declare project, development environment, field-engineering business unit and campaign tags. Both serverless bundle targets pass strict validation. Tags are prepared locally; resources were not redeployed. |
| BP-306, ownership | Added `.github/CODEOWNERS` with repository owner `@laurentfabre`. This establishes ownership, **not enforced PR approval**. GitHub branch protection/rulesets must separately require reviews, and a sole author cannot approve their own PR. No remote repository policy was changed. |
| BP-327, commit checks | Added `.pre-commit-config.yaml` and installed the equivalent repository-local hook. It runs staged-source syntax/regression checks and affected fast app/publication/guard tests. The existing managed Databricks hook invokes it before managed checks; its secret scanning and `core.hooksPath` were preserved. Full Spark/phase acceptance checks retain their separate requirements. |
| BP-538, regression guard | Added `.vibe-doctor/forbidden_patterns.json` plus an executable checker and regression tests. Reintroducing remote append SQL fails the check; valid SQLite publication SQL is allowed. |
| Artifact duplication | `mlruns/` and the whole `data/` tree were **already ignored**, with no tracked files in the four reported generated directories. Added `tools/scan_source.py` to scan a temporary snapshot selected using Git's ignore rules and explicit source roots. It keeps recursive coverage of real app and engine code. Model artifacts were not edited or removed. |

## Retained warnings and their disposition

| Finding | Assessment |
|---|---|
| BP-556 (1 warning) | **Pending acceptance evidence.** No campaign Genie space/delegated app flow has been accepted. An actual natural-language question must be compared with direct SQL once that work is eligible. No placeholder “passed” smoke artifact or extra remote experiment was created. Existing ZR-7/8 blockers still apply. |
| BP-381 / BP-542 (4 warnings) | **Not applicable to the current batch architecture.** Neither bundle deploys a model-serving endpoint. The engine scores with Spark/MLlib; adding an unused endpoint would create unrelated infrastructure. |
| BP-101, `src/lakematch/publication.py` (1 warning) | **False positive.** SQLite `BEGIN IMMEDIATE`, a unique batch ID, an input/model digest, duplicate lookup and atomic commit protect the insert. Four recovery/idempotency tests pass, including interruption, process death, historical retry without rewinding, and four concurrent duplicate publishers producing exactly one build and commit. The engine source was left unchanged. |
| BP-101, guard test fixture (1 warning) | **Intentional negative example.** `tests/test_source_hygiene.py` contains append SQL as text to prove the regression guard rejects it; the SQL is not executed. |
| BP-128 (7 warnings) | **Delegated logging / test fixtures.** Engine and benchmark scopes resume a previously logged composite run and call `tracking.evaluate_pairs`, which logs the evaluation dataset, metrics and contract. The related tracking tests exercise that behavior. `tracking_canary.py` likewise delegates to the same tracking implementation. The small scopes are not empty runs. |
| BP-131, original serverless canary (1 warning) | **Historical, limited-purpose fixture.** This early canary saves/reloads its Spark model and logs its report and link count. Complete composite-model registration and fresh-task reload are established separately by the later ZR-5 evidence. Its sealed historical purpose was retained. |

The historical `spec/bench/bench_febrl.py` INSERT flag in the original scan belongs
to the preserved comparison harness, outside this new-engine source scan.

## Validation and limits

- **13 app tests passed**, including immutable metadata retries and recovery of
  an original receipt after a simulated committed write with a lost acknowledgement.
- **4 publication recovery/idempotency tests** and **2 regression-guard tests passed**.
- APX Python and TypeScript checks passed; `git diff --check` passed.
- `databricks bundle validate --strict --target serverless --profile fevm-gdpr2`
  and the equivalent `serverless_native` validation both passed.
- The changed Delta SQL has not been run remotely. Local regression tests do not
  establish Databricks App or Delta acceptance. No deployment, warehouse startup,
  model retraining, Genie query, or ninth campaign experiment was performed.

Re-run locally:

```sh
python3 tools/check_changes.py --all
python3 tools/scan_source.py
```

Install the repository hook on another checkout with `python3 tools/install_hooks.py`.
It refuses to overwrite an existing different local hook. `.pre-commit-config.yaml`
also supports users of the pre-commit framework; this checkout does not need that
additional dependency. The direct Git hook checks staged text; its affected unit
tests execute in the local checkout, so keep the source under test aligned with
the staged changes when committing.

The [live scan review](LIVE_SCAN.md) records the supplied online results and the
21 September read-only metadata follow-up. A static presence check cannot prove
review enforcement, a deployed endpoint, or a working Genie conversation.

The subsequent [redeployment audit](REDEPLOYMENT.md) includes actual app and
Genie smoke results and a separate source scan that includes the new deployment
and Genie files. The no-deployment statement above describes this initial
static-scan follow-up, before that additional work was requested.
