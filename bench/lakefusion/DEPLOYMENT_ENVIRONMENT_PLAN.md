# LF-C slot 13 — explicit endpoint injection and canonical workspace origin

Declared **2026-09-28**. LF-C is **12/32**. Slot 12's retained diagnostic names
exactly `DATABRICKS_HOST=mismatch, LAKEBASE_ENDPOINT=missing`, before database
authentication. It does not print the host value or establish the precise host
spelling. All other first-stage resource comparisons passed.

Hypothesis: explicit endpoint resource injection and normalization of equivalent
spellings of the selected HTTPS origin resolve these startup checks, allowing
the unchanged live workflow/revocation/restart acceptance to proceed.

- The builder adds `LAKEBASE_ENDPOINT: valueFrom: postgres` to `app.yaml` and
  the corresponding `value_from` to the DAB configuration, as required by the
  current Apps/Lakebase deployment guide. The attached branch/database and
  expected endpoint remain unchanged; the value is supplied by the resource.
- The runtime accepts the exact selected hostname with or without `https://`
  and with at most one trailing slash. It still uses the bound HTTPS origin
  for OAuth. No other origin, HTTP URL, credentials, explicit port, path, query
  or fragment becomes valid. Three positive and nine negative regression cases
  exercise this boundary. Diagnostics continue to disclose names only.
- Build a fresh, hash-pinned payload from this committed source and verify
  retained installation data and all original frozen/scanner inputs. Old payloads
  and failed evidence stay unchanged. Runtime checks on both supported Python
  versions run through managed commit hooks before remote execution.

Use [slot-13 inputs](startup-environment-inputs-20260928.json) and fresh artifact
paths. All [slot-10 bounds and acceptance gates](DEPLOYMENT_STARTUP_PLAN.md)
remain: 2,400 seconds overall/2,100 work; 480-second offline build; one Medium
app/worker with observed singleton required; 0.5–1 CU and 300-second suspension;
bounded SQL/HTTP and the retained single fixture. Capture startup logs before
owned app/warehouse cleanup. No TLS, identity, permission, singleton or data
integrity check is bypassed. A remaining mismatch is a failed attempt, not
permission to accept an arbitrary host. Billing and broader qualification stay open.

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-environment \
  --hypothesis 'Explicit endpoint injection and equivalent selected-host spellings permit live workflow acceptance while preserving resource and identity checks' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_ENVIRONMENT_PLAN.md \
  --artifact bench/lakefusion/startup-environment-inputs-20260928.json \
  --artifact bench/lakefusion/startup-environment-20260928.json \
  -- .venv/bin/python tools/lakefusion_startup_run.py \
       --inputs bench/lakefusion/startup-environment-inputs-20260928.json
```
