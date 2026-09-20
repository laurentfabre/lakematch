# Remaining acceptance gates — 2026-09-20

ZR-1, ZR-2, ZR-4 and ZR-5 pass on current source. The target is still incomplete.
Read-only phase results are in `experiments/acceptance-20260920.json`; final
resource state is in `experiments/final-resource-state-20260920.json`.

| Gate | Observed blocker | Required next input or evidence |
|---|---|---|
| ZR-3 | Eight iterations exhausted. Million-record candidate materialization exhausted the unchanged JVM heap after 672.80s. Actual `bench --all` passed its replay/original/clustering stages and stopped before scale. | Explicit authorization for a separately predeclared ninth iteration, or a scope decision. No automatic retry or memory increase. |
| ZR-6 | DQX/native inference and remote train/reload/Delta recovery pass. All 16 exact pipeline SQL statements remain redacted; executed per-stage operator profiles are unavailable. No attributed billing rows were returned. | Exported query-profile JSON through the documented workspace UI, and available campaign-attributed billing evidence. Missing rows do not mean zero cost. |
| ZR-7 | APX is retained after Laurent’s “It's not legacy” correction. Local UI, 20 HTTP reviews, exact training-label feedback and restart pass. Remote iteration 8 created the app but read the service principal before provisioning completed; no deployment occurred. | Explicit authorization for one additional bounded app iteration using the [prepared provisioning-wait fix](APP_NEXT_RUN.md). App/warehouse are STOPPED. Do not restart the maintenance debate or run a ninth iteration automatically. |
| ZR-8 / ENV | Actual delegated app-to-Genie Conversation API remains untested. App remote acceptance is blocked at its cap. | Complete app acceptance, then prepare and prove the ten-question delegated flow. An unused Genie scope proposal was rejected by automatic review and removed; the current app has only default identity scopes. |
| ZR-9 | Jobs API explicitly rejects classic compute on fevm-gdpr2: “Only serverless compute is supported in the workspace.” | Classic capability on the selected workspace or an explicit scope/target decision. No alternate profile was selected. |

## Scale diagnosis to carry forward

The failed tier measured 8,450,667,332 prospective joins, 20,326,239 retained
join rows and 471,655 candidate pairs before failure. Completed attempts recorded
about 2.90 GB shuffle reads and 4.17 GB writes. A small final pair count does not
bound intermediate join/plan memory. A prospective next hypothesis is to reduce
materialization and join memory within an explicitly reviewed envelope; these
observations do not establish which implementation change will solve it.
The 100k result remains valid (recall 0.95546, F1 0.97722, 342.12s), and no
million-tier quality or throughput is claimed.

No remote experiment remains active. The newly created review app is STOPPED and has no deployment ([cleanup](../experiments/app-resource-cleanup-20260920.json)). The owned warehouse is STOPPED, the
campaign pipeline is IDLE, no campaign classic cluster exists and no generated
materializer scratch table remains. The shared warehouse was left untouched.
Durable models, labels, committed Delta snapshots and evidence are preserved.
