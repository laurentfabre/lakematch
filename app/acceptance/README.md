# APX acceptance runners

For a new local run, `local_flow.py --root data/test-runs/<new-run>/acceptance
--report-dir reports/test-runs/<new-run>` performs the complete synthetic flow.
Run it with the root Python environment, Java 17 and `SPARK_LOCAL_IP=127.0.0.1`,
inside a bounded `tools/experiment.py` invocation. It runs the app unit tests,
trains a fresh model, starts a separate Uvicorn process on a free loopback port,
exercises the browser, restarts the process and retrains from the exact exported
labels. It refuses a previously used database/output directory. The test app is
always stopped; any separately running interactive demo remains available.
Set `LAKEMATCH_CHROMIUM_EXECUTABLE` if Playwright's Chromium is not installed.
This tests the packaged FastAPI/React app; it does not restart the APX dev manager.

These runners use only the new synthetic fixture and the explicitly selected
`fevm-gdpr2` campaign. Run one experiment at a time through `tools/experiment.py`.
The runner adds the app's `app-source.json` artifact because the existing engine
source digest deliberately does not include this isolated subproject.

`fixture.py prepare` writes disjoint baseline, review and validation records.
The normal engine CLI trains the baseline; `fixture.py seed` queues its real
probabilities. `browser.mjs` reviews 20 pairs (one via keyboard) through HTTP,
checks retries, statistics/history, hidden Genie and mobile layout, and exports
the exact snapshot. `feedback.py export` writes the 19 resolved training labels;
`feedback.py audit` verifies the next normal CLI model's recorded digest.
`restart.py` stops/restarts APX and compares every provenance field unchanged.
`local_checks.py` runs APX type checks, app regression tests and the build limit.

`remote.py --profile fevm-gdpr2 --report <path>` prepares three owned Delta tables,
creates the dedicated one-instance app with the owned warehouse resource,
grants only required catalog/schema traversal and table read/write privileges,
deploys the build, reviews 20 synthetic pairs, independently reads back Delta,
and checks stop/start persistence. It always stops its app and warehouse.
No existing app or shared warehouse is modified. The outer experiment timeout
must leave room for explicit cleanup (2400 seconds work + 300 seconds reserve).

The app is a single serialized Delta writer. Multiple workers/instances writing
the same queue are unsupported. The local SQLite store additionally enforces
unique requests/pairs and serializes concurrent transactions. Snapshots are
bounded to 10,000 reviews, with explicit failure on truncation.

Observed preliminary failures are retained in `experiments/runs.jsonl`: the
first browser launch used a missing Chromium installation; the next uncovered
SQLite numeric affinity in metadata; the third checked history before its async
fetch completed. The complete corrected browser run passed. APX commands must
run from `app/` (or use an absolute app path); relative `app` arguments trigger an
APX 0.3.8 path bug. FastAPI is pinned to 0.128.0 for APX route introspection.
