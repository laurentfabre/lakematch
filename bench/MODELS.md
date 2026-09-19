# Composite model acceptance

ZR-5 passes `bash verify_zr.sh 5` on the current source. All checks use a synthetic fixture; its F1 is a contract test,
not a benchmark quality claim. Training and evaluation use separate record IDs.

Iteration 1 logs the pipeline, raw-pair schema, full config, candidate spec, feature
order, frozen threshold, label snapshot/digest and training-only IDF. The full
package size includes MLflow metadata and bundled code. Offline local logging
and a fresh Python/Spark process reload passed (132,097 bytes, maximum probability
difference below 1e-12). Static MLflow evaluation includes custom pairwise metrics;
the local SQLite registry remains empty. A rejected acceptance leaves the pointer intact.
Runs: `20260919T225512Z-tracking-train-6ad9eb`, `20260919T225534Z-tracking-reload-f218c1`.

Iteration 2 tests the same logger on FEVM serverless, then registers
`gdpr2_catalog.lakematch_20260919.pair_model` and resolves `@champion` to an immutable
version in a separate notebook task. Finite envelope: one active experiment, two
sequential tasks, 600 seconds per task and 1,500 seconds overall. Model staging uses
the owned UC Volume. Billing remains unreconciled. Submission is not acceptance.

The pyfunc is a **driver/job batch model**, because it needs a Spark session and
decisions across the complete candidate snapshot. It is not a row-at-a-time Spark
UDF or an online serving model. Retrieval supplies the frozen `cos`, `rank` and `gap`
features; the artifact records their candidate spec. Prediction replays normalization,
comparisons, IDF, optional local embeddings, classifier and cardinality decisions.

Final local/Connect coverage, normal CLI integration, read-only phase verification
and FEVM registration/fresh-session evidence now pass. The phase completed at
iteration 3 of the eight-iteration cap.

The normal CLI now logs every training run. `input.validation_labels` provides
record-disjoint evaluation labels; `mlflow.acceptance_f1` must be explicitly set
before a passing run can replace `model.pointer` (default `models/current.json`).
Without a validation set, logged metrics are marked `training_diagnostic` and
automatic promotion is refused. A scoring run without `input.labels` loads the
accepted `runs:/<id>/model`, or resolves the remote UC alias once.

The first CLI run (`20260919T230102Z-tracking-cli-93b4b5`) exposed positional CSV
header handling through warnings despite equivalent outputs. It is superseded:
the CSV reader now selects by header name, with a regression test for reordered
columns. A test-only missing pandas import was fixed after a failed suite;
the failure remains in the ledger. The initial standalone Spark test also
needed the worker Python pinned to 3.12 rather than the host Python 3.14.

## Observed FEVM result and final integration repeat

Iteration 2 passed as parent run `1068365812709755`; independent task runs
`933375526767449` (train) and `898101933933972` (reload) both succeeded.
The model is `gdpr2_catalog.lakematch_20260919.pair_model/1`, with MLflow run
`e8e49a55886c405dad10cf87f7e05d3d` and alias `champion`. The complete package was
137,948 bytes. Fresh-task maximum probability difference was
`4.579669976578771e-16`. Observed setup was 226 seconds for training and 2 for
reload; task execution was 312 and 54 seconds respectively. Billing is missing,
not zero. All task states are terminal, and the model/evidence was exported under
`data/remote_models/20260919T225721Z`, with checksums in the experiment report.

Iteration 3 repeats the same fixture on the final logging/config source after CLI
integration. Its remote parent run is `429596527159022`; it retains the same
600-second task and 1,500-second overall envelopes. The local repeat includes
classic/Connect tests, standalone offline fresh-process reload, and the normal CLI.
No benchmark setting or confirmation split is changed by this verification repeat.

The full FEBRL development label file includes negatives outside the candidate
set. Its first integrated run exceeded the new label-snapshot budget and failed;
the logged snapshot now contains exactly the labels consumed by classifier fitting.
Validation disjointness still checks **all original training endpoints**, including
noncandidate labels that can contribute records to IDF fitting. Raw-record and label
CSV reads both select by header name. Logging examples reuse materialized comparisons
so model logging does not rerun the expensive retrieval join.

Final iteration-3 evidence: `20260919T231539Z-tracking-train-3189a0`,
`20260919T231601Z-tracking-reload-f74e35`, `20260919T231613Z-tracking-cli-022075`,
and `20260919T230816Z-tracking-serverless-cb7cab`. Remote MLflow run
`d6ee845c458942679aa4d34bc0db3bc1` registered UC version **2** and resolved
`champion` to that immutable version. Package size: **142,284 bytes**; maximum
fresh-task probability difference: **4.579669976578771e-16**. All remote tasks
are terminal; the export/checksum manifest preserves the model outside FEVM.
The same **71 tests** pass on classic local Spark and local Spark Connect.
