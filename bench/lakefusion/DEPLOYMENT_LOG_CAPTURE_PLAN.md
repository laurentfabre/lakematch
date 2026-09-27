# LF-C slot 11 — retain app initialization diagnostics before cleanup

Declared **2026-09-28**. LF-C has consumed **10/32** attempts. Slot 10 proves
retained database/grant verification and separate compute startup, then package
installation succeeds but the application crashes during initialization. Its
199.075-second failed attempt and successful owned-compute cleanup are retained.
No HTTP acceptance ran. Reading logs after stopping returns HTTP 503: the log
service needs active app compute. The root cause is therefore not yet known.

Execute one diagnostic follow-up using the **unchanged slot-9 payload**, the
same retained installation and the complete bounds and gates of the
[slot-10 plan](DEPLOYMENT_STARTUP_PLAN.md). This is not a payload correction or
an assumption that retry fixes the application. Its hypothesis is that capturing
logs while compute is active will identify the exact failing initialization
contract without weakening it. If startup unexpectedly succeeds, all original
single-instance and HTTP/revocation/restart gates still apply.

The only harness changes bind the configuration exactly to the recorded
installation and capture up to 150 APP log lines (40 seconds maximum) **before
cleanup** on failure. Persist at most 16,000 characters after removing
credential assignments, bearer/JWT/PAT material and URL passwords. A local
regression test checks that credential values are absent while the failure
message remains. The original failure/command diagnostics remain distinct from
log-capture or cleanup errors. Retain all failed evidence.

Use the fresh [slot-11 inputs](startup-logcapture-inputs-20260928.json), report
and payload directory. Keep the 2,400-second overall/2,100-second work envelope,
startup cleanup reserve, Medium app, one observed instance/worker, 0.5–1 CU,
300-second suspension, sequential bounded SQL and one remote experiment.
The synthetic fixture is verified, not reseeded. Stop the owned app/warehouse;
retain installed state and receipts. All 15 frozen and seven scanner files stay
unchanged. Billing and broader feature qualification remain open.

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-startup-logs \
  --hypothesis 'Capturing initialization logs before cleanup identifies the unchanged app startup failure without weakening contracts' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_LOG_CAPTURE_PLAN.md \
  --artifact bench/lakefusion/startup-logcapture-inputs-20260928.json \
  --artifact bench/lakefusion/startup-logcapture-20260928.json \
  -- .venv/bin/python tools/lakefusion_startup_run.py \
       --inputs bench/lakefusion/startup-logcapture-inputs-20260928.json
```
