# ZR-7 — APX review feedback, iteration 1

Declared 2026-09-20 after Laurent corrected the installed skill: “It's not legacy.”
APX 0.3.8 remains selected. The prerequisite scaffold was built before UI work:
largest deployment file 169,627 bytes, below the 10 MiB limit. Preserve the
original `experiments/apx-prerequisites.json` as historical evidence.

Hypothesis: the existing APX FastAPI/React scaffold can persist an uncertainty
queue and review provenance locally and in Delta, and an explicit resolved-label
snapshot can feed the unchanged normal `lakematch train` CLI.

Baseline: no review endpoints or UI; no app label store. Use a new small seeded
synthetic fixture, never benchmark confirmation records. Changed factors are the
isolated app and its acceptance harness; frozen models and engine code stay fixed.

Acceptance:

- Queue orders by distance to the model threshold, with LLM unsure and merge
  impact as explicit ordering factors. Keyboard match/no-match/unsure, reason,
  immutable model identity, server-supplied user/time, and visible save failures.
- Twenty pairs reviewed through HTTP; retry is idempotent, conflicting reviews
  are rejected, invalid pair/model/decision/reason cannot be stored. Restart
  retains queue and label records. Unsure labels never enter training.
- Statistics report label/queue/quarantine counts, available human/LLM agreement,
  and recorded evaluation precision/recall by model. Missing LLM/evaluation data
  is displayed as unavailable, never invented.
- Local APX startup, generated OpenAPI client, type checks, production build and
  browser interactions pass. Recheck every deployment file against 10 MiB.
- An isolated training run consumes the exact exported labels; its MLflow label
  digest matches the resolved snapshot and differs from the baseline input.
- Deploy the same app on `fevm-gdpr2` with the owned SQL warehouse resource.
  Repeat durable HTTP/restart checks against Delta. Capture and stop the app and
  owned warehouse at experiment end, including failures. No shared compute.

Bounds: one experiment at a time; local checks/feedback <= 900 seconds each;
remote app experiment <= 2400 seconds including deployment/HTTP checks and
cleanup; SQL statement timeout 50 seconds with cancellation. At most eight ZR-7
iterations. Each failure is retained. No scope or budget change to ZR-3/4.

ZR-8 follows app capability acceptance and retains its own delegated-user proof.
Optional Lakebase remains off. No app dependencies enter the Apache-2.0 engine.

## Recorded progress

The local acceptance development includes retained failed attempts: missing
Chromium executable, SQLite numeric metadata conversion, and a history-loading
race in the browser harness. Corrected browser run
`20260920T105503Z-app-browser-217ea8` passes 20 HTTP reviews, keyboard-first review,
provenance, idempotent retries, statistics/history and mobile layout. Restart run
`20260920T105714Z-app-restart-81f874` proves an exact snapshot after stopping and
starting APX. The feedback run `20260920T105553Z-app-feedback-2ab14d` consumes all
19 resolved labels with the exact expected digest, excluding one unsure review.
The final checks run `20260920T105826Z-app-local-checks-bffb8d` passes six regression
checks, both type checkers and the build (largest file 143,106 bytes).

The first remote app attempt is the next iteration (5), with the same 24-pair
fixture and 20-review protocol. App name `lakematch-review-20260919`; the owned
warehouse is `ec3b6df6c1cabcd4`. Three owned Delta tables store the queue, labels
and evaluation metadata. One worker/instance, no scaling. App and warehouse are
stopped in `finally`; durable labels and failures are preserved.

Remote iteration 5 (`20260920T105900Z-app-remote-47e95f`) failed before creating a
resource: this CLI version forbids a positional app name alongside `--json`.
The cleanup lookup independently confirmed that the app did not exist; the
warehouse was never started. Retain the failed receipt. Iteration 6 supplies the
name only in the structured JSON request; the app, fixture and assertions are
unchanged. No absent-resource failure is reported as a successful app stop.

Iteration 6 (`20260920T105954Z-app-remote-426746`) failed before resource creation:
the workspace rejects explicitly requesting the default `iam.current-user:read`
app scope. Current official Apps authorization documentation distinguishes the
automatically assigned identity scopes from the configurable supported scopes;
it also maps deprecated `dashboards.genie` to current `genie`. Iteration 7 requests
only the documented `genie` scope, retaining platform-supplied identity defaults.
Source: https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth
The UI/Delta fixture, assertions and bounds are unchanged. App absence and no
warehouse start were recorded; no active resource remains from iteration 6.

Before iteration 7 executed, automatic approval review rejected requesting the
persistent Genie OAuth scope while the ZR-7 app has Genie disabled. No remote
command from that request ran. The safer ZR-7 deployment removes all explicit
user API scopes and disables token forwarding: review provenance uses only
platform-supplied identity headers. Genie scope/delegation is deferred to ZR-8.

Iteration 7 (`20260920T110137Z-app-remote-1adbbb`) failed before resource creation:
“Manual instance count configuration is not enabled in this workspace.” This
workspace uses the default fixed app compute. Iteration 8 removes the unsupported
manual min/max instance fields and retains one Uvicorn worker. No optional OAuth
scopes/token forwarding are requested. This is the final ZR-7 iteration under the
existing cap; any remaining failure will be diagnosed and surfaced, not retried.

Iteration 8 (`20260920T110232Z-app-remote-d1963b`) created the app asynchronously,
then failed on the not-yet-populated service-principal field. Initial stop was
rejected during STARTING. The separate cleanup receipt later verifies STOPPED
with the principal present, warehouse STOPPED and pipeline IDLE. No app deployment
or Delta review tables/labels were created. The eight-iteration cap is reached.
The bounded provisioning/cleanup wait is prepared and locally tested; the
[one-run proposal](APP_NEXT_RUN.md) requires explicit authorization.
