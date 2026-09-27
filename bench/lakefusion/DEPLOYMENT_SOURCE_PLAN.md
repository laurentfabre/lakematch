# LF-C slot 14 — deploy the verified app configuration

Declared **2026-09-28**; LF-C is **13/32**. Slot 13 retained the exact uploaded
endpoint mapping in both source and snapshot, but the deployment environment
override omitted it. Host equivalence now passes. The application stopped before
database authentication; installed workflow tables and revision-1 access remain
unused. Original failed evidence stays unchanged.

Hypothesis: deploying the verified source directly, without the stale inline
environment override retained by bundle run, permits the unchanged runtime to
pass startup and proceed to the bounded workflow acceptance.

- Build a fresh payload from committed source. Keep DAB validation, resource
  deployment, isolated state and synchronization. Verify every uploaded app
  file's size and SHA-256 against the payload before starting compute.
- Start compute separately and wait for any automatic prior deployment to leave
  IN_PROGRESS, with a 120-second bound. A prior failure is not the new attempt.
- Call the named `apps deploy` API with the verified source path, SNAPSHOT mode
  and `--no-wait`. Supply no command or environment override: the uploaded
  app.yaml owns those settings. Require the returned deployment ID, await that
  exact deployment and compare all snapshot files with the declared payload.
- Recheck the restart snapshot too. Wrong deployment IDs, stale configuration
  and drifted wheels cannot satisfy acceptance. Four local tests cover credential
  redaction, stale readback and previous successful/failed deployment confusion.

All [slot-10 limits and acceptance](DEPLOYMENT_STARTUP_PLAN.md) remain: **2,400
seconds overall**, 2,100 work, one Medium app/worker, observed
`active_instances == 1`, four runtime connections, Lakebase 0.5–1 CU/300-second
suspension and the owned serverless 2X-Small warehouse. Reserve cleanup time for
each app start. Keep TLS, identity, restricted-role, data-integrity and no-store
checks. Do not reseed or reset the installed fixture. Stop owned app/warehouse;
retain database and deployment evidence. This attempt consumes slot 14 even on
failure; no required product gate closes merely because deployment succeeds.

Use [fresh slot-14 inputs](startup-source-inputs-20260928.json). Public CLI source
review: [run/app.go](https://github.com/databricks/cli/blob/v1.18.0/bundle/run/app.go)
and [appdeploy/app.go](https://github.com/databricks/cli/blob/v1.18.0/bundle/appdeploy/app.go).
The uploaded-file diagnosis is in [the slot-13 readback](startup-environment-upload-20260928.json).

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-source \
  --hypothesis 'A verified Apps source deployment without stale bundle-state environment overrides permits unchanged workflow acceptance' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_SOURCE_PLAN.md \
  --artifact bench/lakefusion/startup-source-inputs-20260928.json \
  --artifact bench/lakefusion/startup-source-20260928.json \
  -- .venv/bin/python tools/lakefusion_startup_run.py \
       --inputs bench/lakefusion/startup-source-inputs-20260928.json
```
