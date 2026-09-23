# LF-C slot 6 — correct Lakebase auto-suspension request

Declared **2026-09-23** after slot 5 failed from `10056ad`. LF-C is **5/8**.
The [original deployment plan](DEPLOYMENT_PLAN.md) retains all resource, time,
permission, fixture and acceptance limits. This attempt consumes slot 6,
including failure; commit this plan and the correction before execution.

The actual create API rejected `spec.default_endpoint_settings.no_suspension:
false` with “must be true when set”. No project, app, database or review schema
was created. A subsequent read-only get confirmed both dedicated project and app
absent. The failed report's initial cleanup string described an intended retained
target; it was **not an existence check**. Preserve the original evidence and
interpret it using this correction. The updated runner verifies actual existence
and endpoint settings in cleanup.

Correction: omit `no_suspension` entirely in both initial and default endpoint
settings; retain explicit `suspend_timeout_duration: 300s` and 0.5–1 CU limits.
The runtime, migrations, SQL permissions, fixture and HTTP acceptance are
unchanged. New report/payload/binding paths preserve all failed evidence.

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-deployment-followup \
  --hypothesis 'The corrected auto-suspension request allows the isolated Apps and Lakebase acceptance to execute' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_FOLLOWUP_PLAN.md \
  --artifact bench/lakefusion/deployment-20260923-followup.json \
  --artifact bench/lakefusion/deployment-binding-20260923-followup.json \
  -- .venv/bin/python tools/lakefusion_deployment_run.py --followup
```

No gate closes from creating resources. The same real startup, current-grant
denials and exact receipt replay after restart/regrant must pass. Billing and
the wider LM-007/008/024 qualification limits remain explicit.
