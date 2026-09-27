# LF-C slot 15 — functional evidence with instance qualification kept open

Declared **2026-09-28**, LF-C **14/32**. Slot 14 proves successful startup of
the hash-verified Apps payload, including mandatory Lakebase readiness. The
platform omits `compute_status.active_instances`; the original runner therefore
stopped before HTTP. The deployment remains unqualified. No workflow/access
mutation has occurred.

Hypothesis: the retained, successfully started runtime can execute the bounded
task/retry/revocation/restart/regrant flow even though the independent instance
telemetry gate cannot currently pass.

## Explicit change to experiment ordering

This is a functional diagnostic, not a waiver or an overall acceptance run.
Unlike slots 10–14, it may collect workflow evidence when the active-instance
field is absent. It records that field as `null` with status `unqualified`,
never as one. An observed count other than integer one, a configured min/max
other than one, or compute size other than Medium still stops work immediately.
Only this input file enables the collection mode; the harness default still
refuses missing telemetry before HTTP. An overall pass still requires observed
singleton compute before and after restart. If workflow succeeds but telemetry
stays missing, record `workflow_status: passed` and overall `status: failed`.

No horizontal scaling or compute-size change is requested. Keep the existing
standard app and its platform defaults. Public [compute documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/compute-size)
and [horizontal scaling documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/horizontal-scaling)
describe separate opt-in scaling; they are context, not live count evidence.
Manual instance counts were rejected in slot 7. The user authorized this pilot
work and waived the FEVM spend-discovery prerequisite; finite bounds still apply.

## Preserved payload, state, flow and limits

Use [slot-15 inputs](startup-functional-inputs-20260928.json), pinning the slot-14
report and **exact nine-file payload from source `7d54837`**. Copy it to a fresh
directory without rebuilding or editing it. Verify original installation,
revision-1 access/unused workflow, frozen/scanner inputs and all uploaded/snapshot
files. Retain the direct source deployment and exact deployment-ID checks.

The [slot-10 eight-request workflow](DEPLOYMENT_STARTUP_PLAN.md) is unchanged:
real session, empty review queue, create/exact retry, revoke/read-write denial,
restart/continued denial, regrant/original receipt, and one durable task/command.
Keep 40-second HTTP limits, 2,400 seconds overall/2,100 work, one remote run,
one existing Medium app with one Python worker/four connections per instance,
Lakebase 0.5–1 CU/300-second suspension and the owned serverless 2X-Small warehouse.
Maintain the 1,350-second startup/cleanup reserve. Stop owned app and warehouse;
retain all data/receipts. Missing instance telemetry limits proof of aggregate
connection/compute usage and remains a qualification failure. Billing stays
unreconciled. Never restore access silently in cleanup or reseed after partial
workflow progress; a subsequent continuation must inspect the durable receipts.

Thirteen local harness tests pass. This run consumes slot 15 even if functional
checks pass and only the instance gate fails. LM-007/008/024 remain in progress;
second-user approval, RLS, renewal, business apply/publication and recovery remain
separate gates.

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-functional \
  --hypothesis 'The verified retained runtime passes functional workflow and revocation checks while missing instance telemetry remains an explicit qualification failure' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_FUNCTIONAL_PLAN.md \
  --artifact bench/lakefusion/startup-functional-inputs-20260928.json \
  --artifact bench/lakefusion/startup-functional-20260928.json \
  -- .venv/bin/python tools/lakefusion_startup_run.py \
       --inputs bench/lakefusion/startup-functional-inputs-20260928.json
```
