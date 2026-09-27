# Phase C checkpoint — stewardship and authorization

**In progress, 2026-09-28. LF-C has consumed 16/32 experiments under LF-DEC-008.** The local
transactional worker and APX authorization boundary pass. Slot 16 also passes the
live current-user task/retry/revocation/restart/regrant flow. Broader Apps/Lakebase
qualification and the governed two-source pilot remain open. Missing active-instance
telemetry prevents an overall deployment pass. App and warehouse are stopped;
Lakebase data is retained with a 1-CU maximum and 300-second idle suspension.

Slot 1 below remains the accepted worker checkpoint. Slot 2's source-preservation
failure is retained. The separately declared slot-3 follow-up accepts the local
APX authorization boundary with **545 tests passed**; its results and current
remaining gates follow the historical worker evidence.

The slot-1 accepted source is **`9c7d12a`**, with the plan committed before execution.
The [run manifest](../../experiments/20260922T204553Z-lf-c-workflow-f576b1/manifest.json)
records the exact command, source digest, timing and cleanup. The
[lifecycle report](workflow-20260922.json) contains migration/source hashes,
test commands and actual persisted task, operation, history and outbox receipts.

| Measurement | Observed result |
|---|---|
| Root tests | 446 passed: 347 portable checks and 99 PostgreSQL cases |
| New workflow cases | 46 portable and 44 PostgreSQL, included above |
| Existing APX app tests | 25 passed; one existing dependency deprecation warning |
| Total required tests | **471 passed, zero failures/errors/skips** |
| Database | PostgreSQL 16.15, private Unix socket, TCP disabled, fsync on |
| Lifecycle | Open → claimed → resolved/pending approval → independently approved |
| Restart | All task/operation/history/outbox content equal before/after actual server restart |
| Retry | All four original lifecycle command receipts replay exactly after restart |
| Business effect | Identity records unchanged; one approved outbox event remains pending |
| Acceptance runner duration | 23.604 seconds; outer experiment 23.775 seconds |
| Observed peak RSS | Parent 42,713,088 bytes; highest individual child 196,984,832 bytes |
| Preserved content | All 15 frozen Phase A files and four scanner input hashes match |
| Remote activity | Zero cloud, workspace or AI calls; synthetic fixtures only |
| Cleanup | Owned PostgreSQL stopped; outer process inventory found no live owned members |

The [root JUnit result](workflow-tests-20260922.xml) and
[app JUnit result](workflow-app-tests-20260922.xml) name every executed case.
These are bounded correctness fixtures, not throughput, latency, scale or
general matching-quality measurements. RSS is measured per process rather than
as a sum across all processes. No confirmation corpus was materialized.

## Slot 1 — accepted behavior

- Only a current live lease holder can renew, release or propose. Tokens rotate
  on renewal/reclaim, stale revisions conflict, and expiry during a company-lock
  wait prevents proposal. Four concurrent claimants produce one winner.
- Same-key concurrent commands return the same immutable receipt. A changed
  request, reason or context conflicts. Historical retries return their original
  result after later changes, approval and domain retirement.
- Proposal saves the resolved task, operation, decision and receipt atomically.
  Independent approval saves its decision, operation, one outbox event and
  receipt atomically. Changed company revisions produce a durable conflict and
  no outbox event. Four competing approvals enqueue once.
- Injected receipt/outbox failures roll back the whole transaction. Lost
  acknowledgements reconcile to the original committed receipt. An actual child
  process exits before commit with no persisted partial claim; a later retry
  succeeds. Actual database restart preserves receipts and state.
- Database guards reject rewrites/deletes and invalid transitions for managed
  rows. A populated schema-4 upgrade preserves legacy version-zero task/operation
  behavior. Cross-context reads and legacy reinterpretation are refused.
- Bounded inbox/history pagination binds cursors to the query context. Receipts
  use UTC even from a differently configured database session. Existing label
  and app tests remain green.

Focused development testing first exposed an extra closing parenthesis in the
new migration; it was corrected before the implementation/plan commit. All
subsequent focused and hook checks passed. This was the first bounded LF-C
acceptance attempt and it passed; the phase ledger retains one consumed slot.

## Slot 1 — remaining gates at the 2026-09-22 checkpoint

LM-007 remains **in progress**. This is a trusted internal worker with caller-
supplied fixture identities; it does not authenticate or authorize app users.
Lakebase OAuth renewal, app-owned schema permissions, deployed migration and
real application connectivity have not been exercised. LM-008 must enforce the
domain/object/field/action matrix, denial behavior and revocation on every route,
including receipt replay and history access.

LM-009 remains **in progress**. Approval now produces a durable outbox event,
but delivery, application-time revision/policy checks, business mutation,
publication acknowledgement and audit reconciliation remain unimplemented.
LM-011 must validate full merge/split/override previews and reversals against
actual memberships, original events, subsequent edits and downstream references.
The existing APX demonstration has not gained workflow controls in this increment.

The next eligible implementation is the authenticated authorization/application
boundary, followed by integration of approved commands with business execution
and recoverable publication. Remote provisioning must use explicitly selected
Lakebase project/branch/database bindings and the authorized `fevm-gdpr2` profile.
LF-A stays 8/8 and LF-B stays 12/12; those historical limits do not reset.

## Slot 2 — authorization acceptance failure

Source **`0a588a8`** passed 492 root tests and 53 tests from a fresh APX wheel,
plus the restricted-role grant/revoke/restart/regrant lifecycle. The build and
type checks passed. The [manifest](../../experiments/20260923T113456Z-lf-c-access-27966f/manifest.json)
and [report](access-20260923.json) retain the failed result: the pinned build
restored the missing APX attribution comment in the generated API client, so
the final source hash differed. That comment was the only source change.

All 15 frozen files, five scanner inputs and dependency files were preserved;
owned PostgreSQL/process/runtime cleanup passed. The runner stopped at the
source-integrity guard before recording RSS. No local authorization acceptance
gate is closed by this attempt. Slot 2 remains consumed; commit the attribution
and execute the separately declared slot-3 plan without changing workflow or
authorization behavior, tests or budgets.

## Slot 3 — local APX authorization accepted

Accepted source **`b34535b`** includes the attribution fix and the committed
[follow-up plan](ACCESS_FOLLOWUP_PLAN.md). The
[passing manifest](../../experiments/20260923T113812Z-lf-c-access-followup-72cb65/manifest.json),
[access report](access-20260923-final.json),
[fresh-wheel report](access-http-20260923-final.json),
[root JUnit](access-tests-20260923-final.xml) and
[HTTP/app JUnit](access-http-tests-20260923-final.xml) retain the exact evidence.
Every manifest artifact, including the small process logs, is committed.

| Measurement | Observed result |
|---|---|
| Root tests | 492 passed: 365 portable checks and 127 PostgreSQL cases |
| Fresh-wheel tests | 53 passed: 45 app tests and 8 ASGI HTTP/PostgreSQL cases |
| Required total | **545 passed; zero failures, errors or skips** |
| New access coverage | 18 portable, 28 PostgreSQL, 20 transport and 8 integrated HTTP cases; included above |
| App build/types | Pinned APX 0.3.8 build, TypeScript and Python checks pass |
| Wheel runtime | Python 3.12; FastAPI 0.128.0, Starlette 0.50.0, psycopg 3.3.5; verified installed imports/source hash |
| Database | PostgreSQL 16.15, private Unix socket, TCP disabled, fsync on |
| Revocation lifecycle | Reads, history and exact retry denied after revocation; denial survives real restart |
| Regrant | Original claim receipt replays exactly, retaining its original authorization proof |
| SQL role | Supported operations run with the dedicated nonowner role; forbidden SQL cases pass |
| Duration | Runner 45.273 seconds; outer experiment 45.478 seconds |
| Observed peak RSS | Parent 43,155,456 bytes; highest individual child 350,994,432 bytes, below 4 GiB per process |
| Preserved inputs | 80 access-source hashes, all 15 frozen files, five scanner inputs and all three dependency files match |
| Cleanup | Owned databases stopped; temporary HTTP runtime removed; no live owned process-group members |
| Remote activity | Zero cloud, workspace or AI calls; confirmation corpus remains untouched |

The read-only verification also matched all 246 manifest source hashes and six
artifact hashes. The only runtime warning was the existing AnyIO alias
deprecation in Starlette's test client. The build emits an advisory about future
Vite configuration loading; build and type checks passed with the pinned tools.
These small synthetic correctness fixtures do not measure throughput, general
matching quality or real workspace authentication.

The [access contract](../../spec/lakefusion/ACCESS.md) now has local evidence for:

- The five-role matrix, correct domain and every participating object, plus
  refusal of partial field grants for unstructured workflow evidence.
- Stable workspace/user principals from a simulated Apps envelope; refusal of
  local review identity and request-supplied actors, roles or grants.
- Current-policy checks before command-receipt replay, serialized revocation,
  immutable grant events and original authorization proof on saved receipts.
- SQL-filtered inboxes before pagination, user/policy-bound cursors, scoped
  history, generic error responses, bounded JSON and `Cache-Control: no-store`.
- Independent approval, denied lease mutations after downgrade, concurrent
  revocation ordering, schema-5 upgrade and restricted database permissions.

## Current remaining gates

LM-007 and LM-008 remain **in progress**. Tests execute the actual APX routes
through ASGI against PostgreSQL, but simulate the trusted platform identity
envelope. Live Apps authentication, header sanitization and ingress isolation,
Lakebase OAuth renewal, project/branch/database bindings, deployed migrations,
combined app/worker packaging and per-user RLS have not been qualified. The
default review app has no mastering backend attached and refuses these routes.

Raw workflow access currently requires all domain fields. Field-projected
entity/provenance/search/graph/cache paths remain future LM-008/010/019 work.
Service-role SQL grants do not establish per-user RLS or UC inheritance. The
existing review/demo routes retain their earlier contracts; no workflow UI
controls were added or live app deployment performed in this increment.

LM-009 delivery/reconciliation and LM-011 business preview/apply are still open:
an approved operation queues an intent, but does not yet mutate or publish the
business record. The next integration checkpoint needs reproducible app/worker
assembly and selected Lakebase bindings, followed by a separately declared live
acceptance plan using `fevm-gdpr2`. Independent business-execution preparation
can continue. LF-A stays 8/8, LF-B 12/12 and LF-C now uses **3/8** slots.


## Slot 4 — isolated runtime payload accepted

Source **`6db3086`** passes the [committed runtime plan](RUNTIME_PLAN.md).
The [manifest](../../experiments/20260923T124120Z-lf-c-runtime-d511b1/manifest.json),
[runtime report](runtime-20260923.json), [matrix](runtime-matrix-20260923.json),
[root JUnit](runtime-root-tests-20260923.xml) and both
[3.11](runtime-tests-20260923/python-3.11.xml)/[3.12](runtime-tests-20260923/python-3.12.xml)
JUnit reports retain the evidence and named cases.

| Measurement | Observed result |
|---|---|
| Root suite | 492 passed |
| Fresh production payload | 111 passed on Python 3.11.14; 111 on Python 3.12.13 |
| Required total | **714 passed; zero failures/errors/skips** |
| Installation | Hash-required production requirements in empty environments; installed imports; no engine/Spark/MLflow |
| Checks | Explicit identity/resource bindings; credential renewal simulation; four-connection bound; roles, migrations and domain readiness |
| APX | Pinned build, TypeScript and Python type checks pass |
| Duration | Runner 60.840 seconds; outer experiment 60.976 seconds |
| Observed peak RSS | Parent 23,953,408 bytes; highest individual child 349,241,344 bytes |
| Preservation | 249 manifest source hashes, 93 runtime source hashes, 15 frozen files, seven scanner files and seven artifacts verified |
| Cleanup | Owned payload, isolated runtimes and private PostgreSQL removed; no live owned process-group members |
| Remote work | Zero workspace/AI calls; Apps ingress/OAuth/TLS simulated |

This accepts reproducible local assembly only. **LM-007/008 remain in progress.**
LF-DEC-007 now selects a new `lakematch-mdm-dev` project, `production` branch,
`databricks_postgres` database and `lm_control` schema. Read-only inventory found
that target/app and the isolated review schema absent; the existing Lakematch
app and campaign-tagged serverless warehouse were stopped. No remote mutation
has occurred at this checkpoint. The [slot-5 plan](DEPLOYMENT_PLAN.md) commits
finite provisioning/deployment/restart checks before execution.

LF-A remains 8/8, LF-B 12/12 and LF-C **4/8**. Live OAuth/TLS/role mapping,
independent user approval, ingress isolation, per-user RLS, business execution,
publication recovery and customer-style redeployment remain unqualified.


## Slot 5 — project request rejected before provisioning

Source **`10056ad`** failed after 2.349 seconds; [manifest](../../experiments/20260923T124916Z-lf-c-deployment-8a586f/manifest.json)
and [report](deployment-20260923.json) retain the attempted request. The API
rejects explicit `no_suspension: false` in endpoint defaults: that optional flag
only accepts true when set. Auto-suspension requires omitting it and supplying
`300s`. Read-only checks then confirmed the dedicated project and app absent.
No binding artifact exists because creation failed. The cleanup message in the
failed report was intent, not existence proof; no resource was retained.

All 252 source hashes and three manifest artifacts match. No SQL, fixture,
app/warehouse start or deployment occurred. LM-007/008 remain open and LF-C is
**5/8**. The [slot-6 follow-up plan](DEPLOYMENT_FOLLOWUP_PLAN.md) preserves the
same budgets and checks, corrects the optional boolean and records actual
resource existence in cleanup. Existing resources and scanner files are intact.


## Slot 6 — dedicated project created; app deployment failed

Source **`e296720`**, [manifest](../../experiments/20260923T125137Z-lf-c-deployment-followup-2eb17c/manifest.json),
[report](deployment-20260923-followup.json) and
[binding](deployment-binding-20260923-followup.json) retain this 20.911-second
failed attempt. The selected project exists with UID
`ca930294-0763-4eaa-9638-b8be2c4f98b6`, PostgreSQL 17, 0.5–1 CU and verified
300-second suspension. Payload build and strict bundle validation passed.

The app create/deploy failed. Its original stderr was overwritten by cleanup's
“app does not exist” message; the cause cannot be established from this report.
A subsequent read-only bundle plan passes with one intended app create. No app,
control schema, fixture or review schema was created and the warehouse was not
started. Workspace payload files/DAB deployment metadata and the selected
Lakebase project are retained. Storage costs remain unreconciled.

All 252 source hashes and four manifest artifacts verify. LF-C is **6/8**.
The [slot-7 resume plan](DEPLOYMENT_RESUME_PLAN.md) pins the retained project UID,
rechecks the payload hashes, preserves each command error and checks app
existence before cleanup. Live application acceptance remains open.


## Slot 7 — workspace rejects manual app instance counts

Source **`13bfc9e`**, [manifest](../../experiments/20260923T125449Z-lf-c-deployment-resume-314c30/manifest.json)
and [report](deployment-20260923-resume.json) retain the exact failed API response:
**“Manual instance count configuration is not enabled in this workspace.”**
The attempt lasted 4.813 seconds. The strict bundle plan is valid, but the live
Apps create API rejects its explicit min/max instance counts. No app, SQL
schema/fixture or warehouse start occurred. The dedicated project remains with
its verified limits and five-minute suspension; no destructive cleanup ran.

All 252 source hashes and four artifact hashes match. LF-C is **7/8**.
The [slot-8 plan](DEPLOYMENT_SINGLETON_PLAN.md) omits unsupported optional
instance fields and requires a live observed count of one before acceptance.
A missing count remains unqualified. This is the last available LF-C attempt.


## Slot 8 — stopped app provisioned; local certificate trust blocked installation

Source **`a4b9f79`**, [manifest](../../experiments/20260923T125850Z-lf-c-deployment-singleton-55310c/manifest.json),
[report](deployment-20260923-singleton.json) and
[binding](deployment-binding-20260923-singleton.json) retain this failed
55.313-second attempt. The supported default-compute configuration creates
`lakematch-mdm-dev` and its dedicated service principal, attaching the selected
Lakebase database and the campaign warehouse. The app is **STOPPED**. Its source
payload is uploaded under separate DAB state; no running deployment is qualified.

The first operator database connection failed before any migration, grant,
fixture or review schema was created. No warehouse was started. All 252 source
hashes, four manifest artifacts, 15 frozen files and seven scanner inputs verify.
The project is retained at 0.5–1 CU with a 300-second idle-suspension setting;
storage persists and billing remains unreconciled.

[Read-only diagnosis](deployment-diagnosis-20260923.json) identifies a local CA
trust failure with `sslrootcert=system`. The same hostname and OAuth user connect
with **verify-full and TLS 1.3** using the installed Certifi CA bundle. Catalog
reads confirm `lm_control` absent and the app role has no elevated flags or
memberships. These operator observations do not establish live app OAuth,
permissions, singleton compute, migrations or workflow acceptance.

The prepared correction uses the already hash-pinned Certifi version directly
in both the operator and runtime; it preserves hostname/certificate validation.
The [next installation plan](DEPLOYMENT_INSTALLATION_PLAN.md) binds the recorded
project/app and refuses changed resources. Its slot-9 runner refuses execution
under the default limit of eight. **It has not been executed.**

LF-A stays **8/8**, LF-B **12/12**, LF-C is **8/8**. An explicit LF-C limit
amendment is required before another experiment. LM-007/008/024 remain in
progress; all business-execution/publication and later phase gates remain open.


Final checkpoint verification: source **`522bbe3`** passes **111 app/runtime
checks on Python 3.11 and 111 on Python 3.12** through the managed commit hooks,
with owned runtime/database cleanup. This is local regression coverage for the
CA correction, not another acceptance experiment. Read-only workspace metadata
then shows app **STOPPED**, warehouse **STOPPED** and Lakebase endpoint **IDLE**
with its 300-second suspension and 1-CU maximum. The run ledger independently
counts LF-A 8, LF-B 12 and LF-C 8. All frozen/scanner inputs remain intact.

## LF-C cap amendment — slot 9 authorized

Laurent's instruction “Increase the cap substantially” is implemented as
**32 total LF-C experiments** in
[LF-DEC-008](../../spec/lakefusion/EXECUTION_DECISIONS.md). All eight historical
attempts above remain counted; **24 attempts remain**. Historical references to
the eight-run ceiling describe the limit at that time. LF-A stays 8/8, LF-B
12/12 and original ZR limits are unchanged.

The [slot-9 installation plan](DEPLOYMENT_INSTALLATION_PLAN.md) is authorized
under the amended cap, retaining every per-run resource/time, quality, input
preservation and cleanup condition. This amendment alone consumes no slot and
changes no acceptance status.

## Slot 9 — database installed; app startup exceeded the local command timeout

Source **`8320d42`** executes the [authorized installation plan](DEPLOYMENT_INSTALLATION_PLAN.md).
The [manifest](../../experiments/20260923T142207Z-lf-c-deployment-installation-29b68f/manifest.json),
[installation report](deployment-20260923-installation.json) and
[binding](deployment-binding-20260923-installation.json) retain the failed attempt.
The outer run lasts **171.199 seconds**; this remains a failure and consumes slot 9.

- The rebuilt payload and strict DAB validation pass. Operator authentication
  uses **verify-full and TLS 1.3** with the pinned CA bundle.
- All six unchanged migrations and restricted serving-role grants are installed
  in `lm_control`. The frozen company domain, one synthetic legal-company master,
  ERP/CRM crosswalks and the operator's fixture access receipt are retained.
- `gdpr2_catalog.lakematch_mdm_dev` and its three empty review tables are created,
  with the intended scoped app grants. Existing review data is not shared.
- The **120-second local timeout** around `bundle run workflow --no-wait`
  expires while app compute is starting. No live HTTP checks run. Follow-on
  metadata shows active compute with **no source deployment**, so this is not
  app authentication, role readiness or workflow acceptance.
- The first cleanup stop is rejected because the platform will not stop an app
  that has been starting for less than 20 minutes. The warehouse stops normally.
  A separately recorded [cleanup reconciliation](deployment-cleanup-20260923-installation.json)
  observes active compute, stops only the owned app and confirms **STOPPED** in
  15.932 seconds. The original failed report is unchanged. This is cleanup of
  slot 9, not another experiment or a retroactive pass.

The [read-only verification](deployment-verification-20260923-installation.json)
matches **252 source hashes, four artifact hashes, the committed plan, all 15
frozen files and all seven scanner inputs**. It confirms app **STOPPED**, warehouse
**STOPPED**, and Lakebase **IDLE**, with its 1-CU maximum and 300-second suspension.
Storage and installed data remain retained; billing is unreconciled. LF-A remains
8/8, LF-B 12/12, and LF-C is **9/32**, leaving **23 attempts**.

Next: commit a retained-state startup continuation before another run. Verify the
recorded project/app bindings, payload, migrations, fixture receipts and review
schema/grants without rerunning first-install bootstrap. Give cold startup its
declared readiness allowance inside the unchanged 2,400-second envelope, retain
timeout diagnostics, and reconcile a rejected startup stop explicitly. Require
observed `active_instances == 1` before HTTP acceptance; the undeployed active
compute observation omitted this field and cannot establish singleton operation.
Live OAuth/Apps identity, receipt/revocation/restart, second-user approval, RLS,
renewal, business publication and the broader pilot gates remain open.

## Slot 10 — cold startup resolved; runtime initialization failed

Source **`21a275e`**, [manifest](../../experiments/20260927T225506Z-lf-c-startup-0a0b78/manifest.json),
[report](startup-20260928.json) and [inputs](startup-inputs-20260928.json) retain
this **199.075-second failed attempt**. The run began September 28 in Europe/Paris
(September 27 UTC). **134 PostgreSQL regression tests** passed through managed
hooks before execution, including six new retained-state cases.

Live read-only PostgreSQL checks verify all six migrations, the approved domain,
master/crosswalks, original identity/access receipts and revision-1 policy, with
no prior workflow use. The three Delta tables are empty and their direct app
grants match. Strict bundle validation/deployment pass. Compute becomes ACTIVE
under the separate startup allowance, resolving the previous local timeout.
Package installation then succeeds, but `python -m lakematch_runtime` crashes
during initialization. No HTTP acceptance or task mutation ran.

The failed [deployment record](startup-deployments-20260928.json) gives only the
generic crash message. The [post-cleanup log request](startup-diagnosis-20260928.log)
returns HTTP 503; it cannot establish the exception. Both app and warehouse are
**STOPPED** in the run cleanup; [app metadata](startup-app-state-20260928.json)
confirms no active deployment. Lakebase and installed data are retained.

Before source changes, all **255 source hashes and four artifact hashes** matched
the manifest. Frozen and scanner inputs remain intact. LF-C is **10/32**; no
feature gate closes. The [slot-11 plan](DEPLOYMENT_LOG_CAPTURE_PLAN.md) retains
the exact payload and captures redacted initialization logs before cleanup.

## Slot 11 — resource-binding check identified as the first startup failure

Source **`0efd58f`**, [manifest](../../experiments/20260927T230225Z-lf-c-startup-logs-df741f/manifest.json)
and [report](startup-logcapture-20260928.json) retain this **166.889-second failed
attempt**. The unchanged package again installs, and APP logs captured before
cleanup identify `Binding.validate_environment`: injected resource settings do
not match the selected binding. The message does not identify which fields; no
database authentication or HTTP acceptance ran. No task or policy was changed.

The log redaction regression passes. All **256 source hashes and four artifact
hashes** verify before further source edits, as do all frozen/scanner inputs.
The app and warehouse are both **STOPPED**. Lakebase data and DAB state remain
retained; billing remains unreconciled. LF-C is **11/32**. The
[slot-12 plan](DEPLOYMENT_BINDING_DIAGNOSTIC_PLAN.md) adds credential-free field
names to that failure and builds a fresh payload; it changes no accepted values.

## Slot 12 — endpoint injection is absent; workspace host differs

Source **`fa52dd9`**, [manifest](../../experiments/20260927T230921Z-lf-c-binding-diagnostic-f2b50f/manifest.json)
and [report](startup-binding-diagnostic-20260928.json) retain this **227.192-second
failed attempt**. The fresh payload passes local **112 + 112 runtime checks**
and remote package installation. Before database authentication, the strict
binding check reports exactly `DATABRICKS_HOST=mismatch, LAKEBASE_ENDPOINT=missing`.
No environment values or credentials are disclosed. No HTTP request or task
mutation occurs. App and warehouse cleanup both confirm **STOPPED**.

All **256 source hashes and four artifact hashes** match before further edits;
frozen/scanner inputs remain intact. LF-C is **12/32**. The
[slot-13 correction](DEPLOYMENT_ENVIRONMENT_PLAN.md) follows the current resource
guide's explicit endpoint mapping and tests equivalent selected-host spelling
without allowing other origins. The host's actual spelling remains unobserved;
the next run tests that hypothesis with every original gate retained.

## Slot 13 — host binding passes; stale deployment override omits the endpoint

Source **`d15ed59`**, [manifest](../../experiments/20260927T231709Z-lf-c-environment-e622d6/manifest.json)
and [report](startup-environment-20260928.json) retain the **174.203-second failed
attempt**. Managed hooks passed **124 runtime checks on Python 3.11 and 124 on
3.12** before execution. The runtime now accepts the workspace host; the sole
first-stage mismatch is `LAKEBASE_ENDPOINT=missing`. There was no HTTP request or
workflow/policy mutation. Both owned app and warehouse are **STOPPED**.

[Readback evidence](startup-environment-upload-20260928.json) verifies that both
the uploaded source and deployment snapshot contain the new endpoint mapping,
with identical SHA-256 `0d6d56a3aa60b7781a8427608688f9dfce204cec52072a06acd98af217ee8b1a`.
The local DAB resource state still contains the original five environment entries,
and the deployment metadata has those five entries without the new endpoint.
The public CLI v1.18.0 implementation in `bundle/run/app.go` resolves configuration
against deployment state; `bundle/appdeploy/app.go` sends that configuration as
an environment override. The correct uploaded app.yaml therefore did not govern
this launch. No arbitrary endpoint fallback is added.

All **256 source hashes, four artifacts, the declared plan, nine payload files,
15 frozen files and seven scanner inputs** matched before source changes. LF-C
is **13/32**. The [slot-14 continuation](DEPLOYMENT_SOURCE_PLAN.md) retains DAB
resource deployment and synchronization, verifies every uploaded app file, then
submits a named Apps SNAPSHOT deployment with no command/environment override.
It pins the returned deployment ID and verifies snapshot hashes before acceptance.
Four local deployment-evidence tests pass, including stale-source and wrong-ID
refusal. Database authentication, observed singleton compute and workflow HTTP
acceptance remain open; billing is unreconciled.

## Slot 14 — live application starts; instance-count qualification is unavailable

Source **`7d54837`**, [manifest](../../experiments/20260927T232404Z-lf-c-source-dd61e4/manifest.json)
and [report](startup-source-20260928.json) retain the **179.537-second attempt**.
The selected SNAPSHOT deployment **SUCCEEDED**, app **RUNNING**, compute **ACTIVE**.
Uvicorn logs show application startup complete, including the runtime's mandatory
Lakebase OAuth, verify-full TLS, identity, restricted-role, migration and approved
domain readiness checks. All **eight uploaded app files and eight snapshot files**
match the declared sizes/hashes. No stale environment override was supplied.

The overall attempt remains **failed**: `compute_status.active_instances` is
absent even after successful deployment, so the original gate stops before HTTP.
No workflow or access-policy mutation occurred. App and warehouse both stop;
installed state is preserved. All **256 source hashes, four artifact hashes,
nine payload files, 15 frozen files and seven scanner inputs** verify before
later edits. LF-C is **14/32**, with 18 attempts remaining.

The workspace previously rejected explicit counts with “Manual instance count
configuration is not enabled in this workspace.” Public documentation distinguishes
standard apps from opt-in horizontal scaling; it does not prove this app's current
instance count. Browser inspection was unavailable because the managed Chrome
profile was already in use; no browser was stopped or reconfigured.

The [slot-15 diagnostic plan](DEPLOYMENT_FUNCTIONAL_PLAN.md) explicitly separates
functional evidence collection from the still-failing instance qualification.
It reuses the exact slot-14 payload and the existing standard Medium app, records
missing telemetry as **unqualified**, and refuses any observed/configured count
other than one or any larger compute size. Missing counts still prevent an
overall pass after HTTP collection. **13 local harness tests** pass, including
refusal of observed drift and preservation of the missing-telemetry failure.
This changes the experiment's gate ordering, not the pilot's acceptance status.

## Slot 15 — live session and queue pass; task identity is rejected

Harness source **`ad7925e`**, retained runtime **`7d54837`**,
[manifest](../../experiments/20260927T233008Z-lf-c-functional-7dc429/manifest.json)
and [report](startup-functional-20260928.json) retain this **205.288-second failed
attempt**. Source/snapshot readbacks match, live startup succeeds, and missing
instance telemetry is explicitly **unqualified**. `GET /api/session` and the
empty isolated review queue each return **200** as the actual signed-in user.
The first workflow task POST returns **401** before dispatch. No receipt is
created and the runner never reaches access revocation; cleanup confirms app
and warehouse **STOPPED**.

The mastering parser only accepted unqualified alphanumeric IDs. Public
[Databricks template code](https://github.com/databricks/app-templates/pull/214)
illustrates a numeric `user-id@workspace-id` proxy identity; that form was
rejected. The actual header value was not captured, so this remains a testable
cause rather than an observed header diagnosis. The [slot-16 plan](DEPLOYMENT_IDENTITY_PLAN.md)
accepts this form only for the exact injected workspace and maps it to the
existing canonical principal. It refuses email addresses, other workspaces and
ambiguous values; failure logs classify the reason without printing headers.
**29 app-boundary tests** pass before the managed commit regression suite.

All **256 source hashes, four artifacts, declared plan, nine payload files,
15 frozen inputs and seven scanner inputs** verify before source changes.
LF-C is **15/32**. Receipt/revocation/restart evidence and singleton qualification
remain open, as do broader pilot gates. Billing remains unreconciled.

## Slot 16 — live task retry, revocation, restart and original receipt replay pass

Source **`a6e074a`**, [manifest](../../experiments/20260927T233626Z-lf-c-identity-05ae8f/manifest.json),
[report](startup-identity-20260928.json) and
[independent read-only verification](startup-identity-verification-20260928.json)
retain the **321.234-second run**. Before execution, managed hooks passed **54
app tests and 133 isolated runtime checks on each of Python 3.11 and 3.12**.
The live actor matches the installed operator's canonical principal.

| Live check | Observed result |
|---|---|
| Authenticated session and isolated empty review queue | Both 200 |
| Task creation and exact retry | Both 200; identical receipt |
| Revoked task read and write/retry | Both 403 with no-store |
| Revoked task read after app stop/start | 403 with no-store |
| Original command after restoring recorded grants | 200; exact original receipt |
| Durable database reconciliation | One task and one command; HTTP receipt/hash match |

**Functional workflow status is passed. Overall experiment status remains
failed solely for unavailable instance-count telemetry**, before and after
restart. The diagnostic does not turn that missing evidence into a pass. No
broader package is closed: second-human approval, ingress isolation, per-user
RLS, hour-long renewal, business apply/publication, restore/scale and customer
installation are separate qualification requirements.

Every uploaded app file, selected deployment snapshot and restart snapshot
matches the declared **eight app-file hashes**. All **256 source hashes, four
artifacts, nine payload files, 15 frozen inputs and seven scanner inputs** match
before documentation updates. The independent transaction is explicitly READ
ONLY and verifies restored original grants at **access revision 3**, immutable
access receipts at revisions **1/2/3**, the original fixture access receipt,
exactly one task/command and zero business operations/decisions/outbox records.
No record is reseeded or removed.

App and warehouse are both **STOPPED**, independently confirmed. Lakebase data
and DAB state remain retained, with **1-CU maximum and 300-second suspension**;
billing is unreconciled. LF-A stays **8/8**, LF-B **12/12**, LF-C is **16/32**
with **16 attempts remaining**. The cap is not a blocker.

**Continuation boundary:** the installed fixture has now been used. The
first-use verifier intentionally rejects its nonempty workflow and revision-3
access. Do not rerun slots 10–16 or reset the fixture to make them pass. A future
live qualification must pin these saved receipts and revisions in a committed,
receipt-aware continuation. Resolve instance observability and obtain a real
second authenticated participant for independent-approval acceptance; implement
business apply/publication under the existing package dependencies.
