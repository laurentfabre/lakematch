# LF-C slot 3 — preserve source through authorization acceptance

Declared **2026-09-23**, after slot 2 consumed the second of eight LF-C
experiments. Its [manifest](../../experiments/20260923T113456Z-lf-c-access-27966f/manifest.json)
and [report](access-20260923.json) remain unchanged and failed. All 545 tests and
the restricted-role grant/revoke/restart/regrant lifecycle passed, but the final
source-integrity assertion failed: `app/build_deploy.py` restored the missing
APX attribution comment at the start of the generated `ui/lib/api.ts` file.
The comment was the only changed source; all dependency, frozen and scanner
inputs were preserved. Cleanup passed. The runner did not reach RSS recording.

Commit the build-restored attribution comment before this follow-up. The runner
now accepts explicit slot/plan arguments, fingerprints the build script and the
follow-up plan, and names changed paths when source preservation fails. Workflow,
authorization, migrations, tests and dependency pins are unchanged.

Hypothesis: the same authorization boundary passes the original acceptance
contract from a committed source tree whose generated client already has its
required attribution. This is one full follow-up, consuming **slot 3**, including
failure. Do not overwrite the slot-2 evidence or count development/hooks as a
replacement for acceptance.

All resource envelopes, required scenarios, pass conditions and remaining-gate
limitations from the [slot-2 plan](ACCESS_PLAN.md) apply unchanged: 900 seconds
overall, a fresh pinned APX build and Python 3.12 wheel, 492 root tests plus
53 app/HTTP checks with zero failures/errors/skips, the real restart lifecycle,
source/frozen/scanner/dependency preservation, observed RSS below 4 GiB per
process and owned-resource cleanup. Only small synthetic fixtures; no cloud
calls or confirmation corpus. No quality thresholds or workload changes.

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-access-followup \
  --hypothesis 'Current-grant APX workflow acceptance preserves committed source through the pinned build' \
  --timeout 900 --config bench/lakefusion/ACCESS_FOLLOWUP_PLAN.md \
  --artifact bench/lakefusion/access-20260923-final.json \
  --artifact bench/lakefusion/access-tests-20260923-final.xml \
  --artifact bench/lakefusion/access-http-20260923-final.json \
  --artifact bench/lakefusion/access-http-tests-20260923-final.xml \
  -- .venv/bin/python tools/lakefusion_access_run.py \
  --slot 3 --plan bench/lakefusion/ACCESS_FOLLOWUP_PLAN.md \
  --output bench/lakefusion/access-20260923-final.json \
  --tests-output bench/lakefusion/access-tests-20260923-final.xml \
  --http-report bench/lakefusion/access-http-20260923-final.json \
  --http-tests bench/lakefusion/access-http-tests-20260923-final.xml
```

A pass accepts the local API/policy boundary only. LM-007/008 and LF-C remain
in progress pending live Apps authentication/isolation, Lakebase bindings and
OAuth/RLS, field-projected entity/search/graph paths, business apply and durable
publication. LF-A stays 8/8 and LF-B stays 12/12.
