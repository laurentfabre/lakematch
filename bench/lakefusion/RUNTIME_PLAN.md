# LF-C slot 4 — isolated workflow deployment payload

Declared **2026-09-23**, after accepted source `8b8200d`. LF-C has consumed
3/8 experiments. This local acceptance attempt consumes slot 4, including
failure. Commit implementation, fixtures, this plan and input fingerprints
before execution. Development checks and commit hooks are not acceptance.

Hypothesis: a freshly built APX/workflow deployment payload installs from its
own hash-required production requirements on Python 3.11 and 3.12, runs the
accepted HTTP/PostgreSQL workflows without repository-source imports or Spark,
and refuses unqualified identities, roles, migrations, domains and credentials.

The package uses exact unchanged portable source copies and all six historical
migrations. The ordinary engine/app dependency files and all 15 frozen Phase A
files remain unchanged. Preserve the seven scanner files fingerprinted in
[runtime-inputs-20260923.json](runtime-inputs-20260923.json).

## Bounds and required checks

- One local experiment, **900 seconds** overall. Fresh pinned APX build ≤420
  seconds; root suite ≤180; two-version payload installation/testing ≤300.
- Offline prepared dependency caches during acceptance. Empty owned environments
  first install the generated production requirements with mandatory hashes,
  then receive only the pinned pytest/httpx test harness. No root engine package,
  Spark/MLflow installation or repository `PYTHONPATH` in those runtimes.
- At least **492 root checks** and **111 app/runtime checks per Python version**;
  every required test passes with zero failures/errors/skips. Runtime tests use
  the packaged migrations, real dedicated LOGIN roles and the deployed factory.
- Verify stable principal/resource bindings, early token renewal/concurrency,
  expired/failed refresh refusal, bounded admission and owned-socket cleanup.
  Check role/schema/table/column/sequence permissions and their changes after
  startup; reject schema drift, owner/elevated roles and mixed engine installs.
  Requests preserve exact receipts across restart; current grants deny revocation.
- Small synthetic fixtures only; PostgreSQL instances use private Unix sockets,
  TCP disabled, fsync on and at most 12 configured connections. Runtime connector
  admits at most four connections. No matching corpus or confirmation data.
- Payload <10 MiB per file and <100 MiB total. Observed parent/highest-child RSS
  each <4 GiB. Record per-process observation, not an aggregate memory claim.
- Source, dependency, frozen and scanner hashes remain unchanged. Stop/remove
  every owned database, payload directory and isolated runtime. Preserve compact
  source/payload/wheel fingerprints, JUnit, timings and terminal failure/success.

The generated DAB was separately validated with `bundle validate --strict` on
`fevm-gdpr2` using a temporary copy, the selected workspace host and synthetic
resource references. The first development validation caught `valueFrom` in the
DAB API config; the corrected generator uses `value_from` there and `valueFrom`
in `app.yaml`. Final strict validation passed with no warnings. Neither that
metadata check nor this local experiment creates workspace resources or proves
the live target's permissions. Acceptance itself makes zero workspace calls.

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-runtime \
  --hypothesis 'A self-contained APX workflow payload preserves authorization and readiness across Python 3.11 and 3.12' \
  --timeout 900 --config bench/lakefusion/RUNTIME_PLAN.md \
  --artifact bench/lakefusion/runtime-20260923.json \
  --artifact bench/lakefusion/runtime-root-tests-20260923.xml \
  --artifact bench/lakefusion/runtime-matrix-20260923.json \
  --artifact bench/lakefusion/runtime-tests-20260923/python-3.11.xml \
  --artifact bench/lakefusion/runtime-tests-20260923/python-3.12.xml \
  -- .venv/bin/python tools/lakefusion_runtime_run.py
```

A pass qualifies local packaging/assembly only. Live Apps identity/header
isolation, Lakebase OAuth/TLS/role mapping, per-user RLS, scale-to-zero and remote
latency remain unproved. The user selected a new dedicated Lakebase target in
LF-DEC-007; provisioning/deployment require a separately committed finite plan.
LM-007/008 and LF-C remain in progress. LM-009/011 business execution/publication
and later entity/search/graph paths are unchanged. LF-A stays 8/8 and LF-B 12/12.
