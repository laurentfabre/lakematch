# ZR-6 iteration 5 — separate training/clustering tasks and Delta publication

Run only after the active inference experiment is terminal. This fixture uses
eight synthetic training records (28 labelled pairs), then a disjoint five-row
identity fixture. It establishes remote job capabilities, not corpus accuracy.
No change to the eight frozen benchmark models, thresholds, aliases or inputs.

Hypothesis: a GBT fitted/logged in one serverless task reloads in a second task;
the engine's verified merge resolves the expected groups; versioned Delta output
tables become visible together through a single Delta catalog commit. Test an
unchanged snapshot, additions/changes/deletions, retry reuse, historical retry
without head rewind, and a seeded write failure after the first staged table.
Require three commits, exact journal replay, stable unchanged IDs, abandoned
attempt cleanup and no visible partial publication.

The publisher supports one serialized writer through a job with
`max_concurrent_runs: 1`. It also checks the previous catalog-head sequence in
the transaction. This does not claim a distributed lease or arbitrary
concurrent-writer support. Readers resolve one committed body and pin Delta
version zero of each immutable output table; committed historical snapshots
remain available. Only uncommitted tables in the exact owned namespace are
removed on recovery.

One STANDARD job on **fevm-gdpr2**, two sequential tasks limited to 480s each,
1200s whole-job timeout, 2400s outer runner envelope including upload/deploy and
180s cancellation grace. Unique volume root/namespace, no schedules or persistent
compute. Save fit/reload IDs, three publication manifests, row counts, exact
assertions, failure diagnosis and terminal-state cleanup. Billing is unresolved,
not zero. The shared warehouse is untouched.

Both job definitions and notebooks are prepared and strict bundle validation
passes; this plan is not evidence that the adapter has executed.

## Iteration 5 result and iteration 6 revision

Run `180393856450383` timed out in training: 225s setup and 268s execution,
against the 480s task limit. Clustering was skipped. The notebook reached
MLflow model logging; automatic serving-input validation emitted a driver-local
artifact warning. This warning is retained and is not established as the timeout
cause. The model/result was not accepted. The job is terminal; the one abandoned
training scratch table was identified by owner, exact generated name and creation
time for explicit cleanup. See `experiments/cluster-fixture-timeout-diagnosis.json`.

Iteration 6 keeps the same synthetic records, model settings, assertions and
publication algorithm. Add durable progress checkpoints and the same owned-volume
`MLFLOW_DFS_TMP` setting as the existing tracking harness. The setting supports
the model's prediction staging; it does not by itself establish that MLflow's
internal serving-example validation can load a driver-local artifact.

Use 600s for training and 900s for clustering, within an 1800s whole-job timeout
and a 3000s outer deployment/capture/cleanup envelope. STANDARD compute, one active
experiment, serialized publication and explicit cleanup remain unchanged. This
is the sixth of eight allowed ZR-6 iterations. Preserve another failure; do not
increase these limits automatically.
