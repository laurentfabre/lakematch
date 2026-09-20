# ZR-6 iteration 3 — triggered frozen inference on FEVM

Prerequisite: both local SQL/MLlib parity checks and DQX/native quality parity
pass. Hypothesis: the same frozen SQL MinHash/GBT state executes in a triggered
serverless SDP pipeline and each FEBRL confirmation F1 differs from its frozen
local reference by at most 0.01. Three bad-ID rows per side must be quarantined.
No fitting, threshold selection, resplitting or alias promotion.

Two sequential configurations on **fevm-gdpr2**: `serverless` uses DQX and
`serverless_native` uses native quality with every paid flag off. Both targets
intentionally share one bundle state/root and one pipeline: deploy the second
only after the first is terminal and IDLE. Stop the sweep on a failed run.
App/Genie flags alone do not establish those integrations or full ZR-6.

Each STANDARD job has 420s preparation, 900s pipeline and 420s audit task limits,
plus an 1800s whole-job limit. The runner allows 300s deployment, 180s transfer,
120s per metadata call and 180s cancellation/stop windows, under a 3000s outer
experiment timeout per target (6000s total). Triggered pipeline, no schedule,
no continuous mode. Only campaign-owned pipeline is stopped; the shared SQL
warehouse is untouched. Billing remains unreconciled, not zero.

Save exact bundle/source/input hashes, resource IDs, job states/task outputs,
pipeline event records, exported volume artifacts and terminal/IDLE cleanup.
The audit validates full-universe candidates and frozen confirmation F1.
Query profiles, training/clustering jobs, durable Delta identity publication,
app and Genie remain required follow-up evidence.
