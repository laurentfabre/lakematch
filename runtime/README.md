# Deploying the workflow runtime

This optional package assembles the accepted APX workflow routes with the
portable PostgreSQL worker. The ordinary review app and the Spark engine keep
their existing packages and dependency files. This is local deployment
preparation; live Apps authentication, Lakebase OAuth/TLS, database-role mapping
and RLS still require their own acceptance.

The alternative `lakematch-workflow-runtime` wheel contains the exact portable
worker source under `lakematch`, its Apache-2.0 license, and all six immutable
migrations. **Install it only in an isolated app environment, never alongside
the `lakematch` engine distribution.** The entrypoint rejects a mixed install.
Spark, MLflow and repository `PYTHONPATH` are unnecessary. Python 3.11 and 3.12
are the supported runtime targets; the separate Spark engine remains Python 3.12.

## Bind resources explicitly

Copy [binding.example.json](binding.example.json) and replace every fixture
resource with the selected app/workspace, Lakebase endpoint/host, branch/database
resource and PostgreSQL database name. Keep `schema: lm_control`, and supply each
approved domain's ID, version and SHA-256. The example contains synthetic,
unreachable hosts and is not a deployable workspace configuration.

The server compares this file with Apps-injected `DATABRICKS_APP_NAME`,
`DATABRICKS_HOST`, `DATABRICKS_WORKSPACE_ID`, `LAKEBASE_ENDPOINT`, `PGHOST`,
`PGDATABASE`, and `PGPORT`. `PGUSER` must equal the injected app client ID.
Missing/mismatched resources, personal-token/profile fallback and disabled TLS
are refused. Secrets remain platform-injected; none belong in the binding file.

Build from the repository root, after preparing the documented APX environment
and APX 0.3.8:

```sh
.venv/bin/python tools/build_workflow_bundle.py \
  --binding /path/to/selected-binding.json \
  --warehouse-id SELECTED_REVIEW_WAREHOUSE \
  --review-schema SELECTED_CATALOG.SELECTED_SCHEMA \
  --output /path/to/fresh-output
```

The builder performs the pinned UI build, creates the APX and workflow wheels,
exports production dependencies from the existing frozen app lock, and emits
`requirements.txt` with mandatory hashes for dependencies and both local wheels.
It also creates `app.yaml`, a separate DAB, and a checksummed payload manifest.
No project, branch, database, table, grant, app or workspace file is created.
Generated artifacts remain outside Git; rebuild them from the recorded source.

The DAB has independent state, one Medium app instance, one Python worker and
an explicitly selected review warehouse. The `postgres` resource references
the selected Autoscaling branch/database. Wheels are explicitly included in
sync and have no generated ignore file. `app.yaml` uses `valueFrom`; DAB config
uses the API's `value_from`. A bare bundle deployment leaves the app stopped.
The builder rejects files at 10 MiB or more and aggregate payloads at 100 MiB.

Validate the completed binding before deployment, using the selected profile:

```sh
cd /path/to/fresh-output
databricks bundle validate --strict --target pilot --profile SELECTED_PROFILE
```

For the current campaign, the selected profile remains `fevm-gdpr2`. The
selected Lakebase target is project `lakematch-mdm-dev`, branch `production`,
database `databricks_postgres`, schema `lm_control` (LF-DEC-007). Schema/template
validation with fixture references does not prove that live bindings exist or
have the required permissions.

## Separate installation from serving

An operator must apply the packaged migrations using `apply_migrations`, approve
the pinned domain definitions, and install initial grants through the existing
operator registry. Use `grant_workflow_role` for a dedicated, pre-created
nonowner role. It now includes read-only migration metadata so the server can
verify readiness. These are explicit operator operations; serving never runs
migrations, creates grants, changes owners or repairs schema drift.

The Apps resource API currently offers `CAN_CONNECT_AND_CREATE`. This alone
does **not** establish restricted access to `lm_control`. The runtime checks
the actual SQL identity, schema/table/column/sequence permissions, role flags
and memberships. It rejects control-schema ownership and broader privileges,
including grants inherited through PUBLIC. Reconcile the platform's actual
role mapping with this contract before live qualification; do not weaken the
check or drop an existing schema to make startup pass. Migration ownership is
deliberately separate from the serving role. Per-user RLS remains unimplemented.

Each connection checks the six migration hashes and pinned approved domains.
Checks run at startup and again before requests; role or schema drift therefore
refuses subsequent requests. No check writes to the database. Role metadata is
read in bounded catalog queries. The trusted owner can still bypass controls.

## Connection lifecycle

Only explicit app service-principal OAuth is used for the operational store.
The SDK has a 10-second HTTP timeout and 20-second retry timeout. Credentials
are cached under a lock, renewed after at most 30 minutes or 120 seconds before
expiry, and never reused after a failed refresh. Tokens are excluded from
representations and errors. This is separate from user authorization and UC
delegation; current end-user grants are still evaluated inside each transaction.

At most four owned connections can be active. Admission waits at most two
seconds; connection timeout is ten seconds, statement/lock timeouts are 15/5
seconds, and idle transactions time out at 20 seconds. Connections require TLS
with hostname/system-CA verification and close at the end of each request.
Business transactions are never automatically replayed. The client may retry
an idempotent request through the existing authorization/receipt contract.

This initial adapter uses fresh sockets to preserve the worker's ownership
contract. Connection pooling, real scale-to-zero behavior and remote latency
remain qualification work. Local PostgreSQL tests use private Unix sockets;
they simulate OAuth, TLS connection arguments and the Apps identity envelope.

## Verification

`tools/run_workflow_runtime_tests.py` installs fresh wheels, verifies that imports
resolve inside owned environments, and checks that no engine/Spark/MLflow
distribution is installed. With `--payload`, it first installs the actual
production `requirements.txt` with required hashes into empty environments,
checks dependencies/imports, then adds only the test harness. Both Python
versions execute app regressions, real ASGI/PostgreSQL workflow tests, token
renewal/admission tests and readiness/permission-drift cases. Every owned runtime
and PostgreSQL directory is removed afterwards.

The [slot-4 plan](../bench/lakefusion/RUNTIME_PLAN.md) defines bounded acceptance.
The [Phase C ledger](../bench/lakefusion/PHASE_C.md) distinguishes observed local
results from the remaining live integration gates.
