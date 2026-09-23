# LF-C slot 8 — supported platform compute configuration

Declared **2026-09-23**, after slot 7 from `13bfc9e`. LF-C is **7/8**; this is
the **last currently authorized LF-C attempt**, including a failure. Commit
the implementation and plan before execution. All [original](DEPLOYMENT_PLAN.md)
time, resource, fixture, preservation, cleanup and acceptance requirements stay.

The retained diagnostic establishes that this workspace rejects manual
`compute_min_instances`/`compute_max_instances` configuration. The default
configuration on the existing stopped review app has neither field. This run
omits those two optional fields via a new explicit builder option; it keeps
Medium compute, one Python worker and independent app/storage/DAB state.
The running app must report **`compute_status.active_instances == 1`** before
HTTP acceptance proceeds. Missing or larger counts leave qualification failed;
do not assume the single-writer bound from an omitted field.

Use the exact retained project UID from the [slot-7 plan](DEPLOYMENT_RESUME_PLAN.md),
refuse any existing app/review schema, rebuild the payload from committed source,
strict-validate and deploy. The operator/runtime privilege separation and all
OAuth/TLS/authentication, revocation and restart checks are unchanged. No
historical migrations, frozen inputs or runtime behavior change.

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-deployment-singleton \
  --hypothesis 'Supported platform-default compute permits the isolated app deployment while preserving the observed one-instance bound' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_SINGLETON_PLAN.md \
  --artifact bench/lakefusion/deployment-20260923-singleton.json \
  --artifact bench/lakefusion/deployment-binding-20260923-singleton.json \
  -- .venv/bin/python tools/lakefusion_deployment_run.py --platform-default-instances
```

After this terminal result, LF-C is 8/8. Preserve the target and stopped owned
compute. Diagnose with read-only operations and continue eligible local work;
another LF-C experiment requires an explicit limit amendment. LF-DEC-005 raised
LF-B only and does not increase the LF-C cap.
