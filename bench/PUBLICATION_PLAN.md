# ZR-4 iteration 7 — normal CLI and recovery

Hypothesis: the measured verified-merge model produces the same identities through
the normal CLI, while atomic publication prevents partial snapshots and duplicate
events across retries and process death.

Use the frozen FEBRL3 validation model and original/1% mutation from iteration 6;
no new training, thresholds or confirmation scores. Invoke the normal `cluster`
command in fresh processes for original input, incremental input, retry of the
same batch, and unchanged input under a new batch. Preserve immutable model URI
and explicitly declare the model's gram-cosine/rank-one/zero-gap pair metadata.
Independently compare the published Parquet crosswalks to iteration 6's sealed
JSON crosswalks. Replay journals, check zero new events on unchanged input, and
verify a historical batch retry cannot rewind the current publication.

Local immutable Parquet attempts are exposed through one SQLite transaction.
An independent test terminates a writer with `os._exit` after a partial output;
the prior commit must remain visible, the abandoned attempt must be cleaned on
retry, and only one next commit may be published. This is a local publication
test; the remote Delta adapter and remote recovery remain ZR-6 work.

Run the three targeted publication tests plus CLI harness sequentially after the
active ZR-3 sweep ends. Bound the harness at 600 seconds, local Spark `local[2]`,
unchanged 500,000-pair / 50-million-join / 30-round budgets. No external network,
remote compute or live labels. Run affected classic/Connect integration suites
after source reconciliation; do not claim complete ZR-4 acceptance without its
read-only verifier and current dependency evidence.
