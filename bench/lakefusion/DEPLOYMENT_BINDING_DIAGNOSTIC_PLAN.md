# LF-C slot 12 — identify missing or mismatched injected resource fields

Declared **2026-09-28**. LF-C is **11/32**. Slot 11's captured APP traceback
identifies `Binding.validate_environment` as the first failing boundary:
`Injected resources do not match the selected binding`. This occurs before
database authentication or HTTP requests. The 166.889-second failed run and
successful app/warehouse cleanup are retained; repeating that generic message
cannot identify the actual configuration difference.

Hypothesis: field-level diagnostics identify the platform binding difference
while preserving strict resource matching and keeping values out of logs.
The only runtime change names each missing/mismatched expected environment key.
No accepted values, identity rules, TLS checks, grants or schema contracts change.
A local regression supplies an unexpected credential-like value and checks that
the error names the affected keys without disclosing the value or secret field.
The managed hooks execute the fresh Python 3.11/3.12 runtime checks before running.

The [slot-12 inputs](startup-binding-diagnostic-inputs-20260928.json) request a
fresh hashed payload built from the committed diagnostic source, using the
existing frozen dependency locks and selected binding. The old payload and its
recorded hashes are still verified and preserved. Strict DAB validation, known
resource/fixture/grant checks, separate compute start, log capture and cleanup
use the [slot-10 procedure and bounds](DEPLOYMENT_STARTUP_PLAN.md). Rebuilding is
inside the same 2,100-second work and 2,400-second overall envelope; build is at
most 480 seconds using offline local caches. The same dedicated state, Medium
app, observed single instance, 0.5–1 CU and 300-second suspension apply.

Capture redacted APP logs before stopping owned compute. Do not infer a passing
binding or live acceptance from improved diagnostics. All original HTTP,
revocation/restart and receipt gates still apply if startup succeeds. No fixture
is reseeded, no secret is added to source, and no broader feature gate closes.

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-binding-diagnostic \
  --hypothesis 'Field-level startup diagnostics identify the missing or mismatched injected resource without exposing values or weakening validation' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_BINDING_DIAGNOSTIC_PLAN.md \
  --artifact bench/lakefusion/startup-binding-diagnostic-inputs-20260928.json \
  --artifact bench/lakefusion/startup-binding-diagnostic-20260928.json \
  -- .venv/bin/python tools/lakefusion_startup_run.py \
       --inputs bench/lakefusion/startup-binding-diagnostic-inputs-20260928.json
```
