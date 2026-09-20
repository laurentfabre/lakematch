# ZR-6 iteration 1 — lazy adapter parity before deployment

Hypothesis: the selected persisted MinHash and binary GBT state can be expressed
as lazy Spark SQL plans with exactly the same candidate keys/ranking and numeric
probabilities (maximum absolute difference < 1e-12), preserving the existing
models and thresholds. Training, model-state export and convergence remain jobs.

First compare DQX 0.16.0 public row-rule expressions with native quality on six
seeded rows: blank/null IDs, duplicate IDs, missing values, invalid/range numeric
values, regex warning, and minimum row count. Require exact reason arrays and
row multiplicity, two valid and four quarantined rows. Prove plan construction
has no Spark actions or WorkspaceClient initialization. DQX's full engine
constructor probes workspace connectivity, so it is unsuitable inside flows.
The optional adapter uses public DQRowRule.get_check_condition instead.

Then compare MLlib and exported SQL inference on the frozen FEBRL all-field and
SSN-hidden validation records (1,000 left/500 right); no confirmation labels or
new fitting. Require exact MinHash buckets, complete ordered-candidate equality,
GBT probabilities within 1e-12, and no Python UDF node in the lazy plan. Derive
coefficients and tree nodes from the saved Spark model Parquet, retaining its
Spark version and feature order. Reject unsupported model shapes explicitly.
Static inspection found that Spark ML uses `hashUnsafeBytes2` while SQL `hash()`
uses the legacy `hashUnsafeBytes`. The adapter therefore implements standard
Murmur3 x86_32 with SQL expressions and must pass 14 byte-tail/Unicode edge cases
against the public HashingTF.indexOf API before corpus parity is measured.

Three sequential local runs, timeouts 120s/300s/300s, local[2], unchanged memory,
candidate caps and pair/join limits. External network denied. DQX is isolated in
.tools/dqx-runtime; mandatory engine dependencies remain unchanged. Exported
state is deployment preparation only. No SDP compatibility, Photon execution,
remote parity or production acceptance is claimed by a local pass.

## Iteration 1 outcome; iteration 2 declaration

DQX passed (`20260920T024144Z-dqx-parity-35d1e2`, 10.28s). The first
native-model check failed before export (`20260920T024154Z-native-ml-all-1820d0`,
12.35s), and the sweep stopped. Static inspection identified a harness bug:
`row.index` resolves the inherited tuple method, not the column called `index`.
Use `row['index']` and retain all expected/actual edge-case values in the report.
The SQL hash expression itself is unchanged. Failed reports now record failure
explicitly rather than leaving a stale `running` status.

Iteration 2 repeats only the two native checks, sequentially, 300s each (600s
aggregate plus cleanup), with unchanged validation data, models and resource
limits. DQX's completed measurement is reused. No deployment until both pass.

## Iteration 2 outcome; iteration 4 integration correction

Both native checks passed in 37.86s / 35.67s, with exact keys and candidates and
probability differences below 1e-12. Iteration 3 reached remote pipeline analysis
but the feature builder's global `require_implemented()` rejected DQX. The job
was cancelled and its automatic unchanged retry stopped. This was an integration
guard defect; no frozen model or hash-expression discrepancy was observed.

Iteration 4 wires lazy quality dispatch, accepts the implemented DQX engine at
the job gate, and removes the feature stage's check of unrelated quality/app
integrations. Job-level guards remain. Repeat the same three adapter checks
(120s/300s/300s) plus one focused feature regression (120s), then both remote
configurations under the unchanged iteration-3 envelopes if local checks pass.
Frozen matching features, models, thresholds and data remain unchanged.
