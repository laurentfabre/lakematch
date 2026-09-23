<!-- Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold. -->

# Lakematch review — APX

Workspace deployment and recovery use [the deployment runbook](../deployment/README.md).
Build with `python3 build_deploy.py` to preserve the committed dependency versions.
The completed app bundle binds the warehouse and Delta environment explicitly.

The isolated APX 0.3.8 FastAPI/React app provides an uncertainty-ordered review
queue, keyboard match/no-match/unsure decisions, mandatory reasons, immutable
model provenance, review history and evaluation statistics. Server-supplied
reviewer/time fields cannot be overwritten by a review request. Resolved labels
export as a snapshot compatible with the unchanged `lakematch train` CLI.

Laurent corrected the installed skill's legacy designation on 2026-09-20:
“It's not legacy.” The project continues with APX. Historical repository
observations remain in `../experiments/apx-prerequisites.json`; this correction
is not a claim of newly observed upstream activity. The prerequisite scaffold
passed the size check before UI development.

Run commands **from this directory**, or use an absolute app path. APX 0.3.8 has
a relative-path bug when invoked as `apx dev check app` from the parent directory.

```sh
uv sync --frozen
apx bun install --frozen-lockfile
node node_modules/typescript/bin/tsc --noEmit
.venv/bin/ty check
.venv/bin/python build_deploy.py
```

For an interactive preview, use `apx dev start --attached
--skip-credentials-validation`. APX 0.3.8's development start/check commands can
refresh router tooling and change `package.json`/`bun.lock`; inspect those changes
before committing and retain the approved pins. Use the commands above for
repeatable type checks and deployment builds. The build preserves the generated
API client's APX attribution notice.

Local mode defaults to SQLite at `data/review.sqlite`, with Genie disabled and
no Databricks client constructed. Set `LAKEMATCH_REVIEW_DATABASE` to select an
existing review database, and `LAKEMATCH_REVIEW_LOCAL_USER` to label a local
reviewer. Those local labels are a configured local identity, not workspace
authentication. Queue/evaluation ingestion is a job operation (`Store.enqueue`),
not a browser API. Empty storage shows an empty queue; no sample rows appear
implicitly. Synthetic acceptance setup is in `acceptance/README.md`.

The **Golden records** tab includes a separate, clearly labelled synthetic
company demo. Open `/#golden-records` to explore six companies and two historical
publications. Expand any field to see its source alternatives, selection rule
and approved edit; switch publications to see the earlier values. Data revision
and identity revision are shown separately. Deleted sources remain explainable.
The demo does not seed the review queue or connect to customer/workspace data.

**Do the source records agree?** shows all seven compared fields, their original
and normalized values, and the reason for review or exclusion. Try Harbor for
conflicting registration numbers, Cedar Logistics for normalized name agreement,
and Atlas Supplies SAS for a deleted CRM source. Switch publication to inspect
the earlier evidence. These are directly selected fixture pairs; no candidate
retrieval, model score or automatic merge is implied. The comparison is built
from the portable worker and packaged as a schema-2 display projection.

Its immutable JSON is packaged with the app, so a fresh checkout needs no prior
experiment output. The root Python 3.12 environment can rebuild it with
`python tools/build_golden_demo.py` (from the repository root); `--check` detects
stale generated content. The Python 3.11 app never imports the engine. Bounded
`/api/demo/golden-records` routes use the existing session dependency and expose
no mutation or configurable live-data path. The synthetic view passes local
fresh-package acceptance; production domain/field authorization and scalable
entity APIs remain open.

[Fresh-package acceptance and screenshots](../reports/lakefusion-ui-acceptance-20260922-final/README.md)
record the passing slot-10 result. The [comparison development preview](../reports/lakefusion-comparison-ui-20260922/README.md)
and [earlier provenance-only view](../reports/lakefusion-ui-20260922-final/README.md)
remain unchanged. The accepted package uses the same synthetic source data and
does not claim live workspace or customer-data qualification.

In the UI, use **R** to focus the reason, **Esc** to return to shortcuts,
**M** for match, **N** for no match and **U** for unsure. Shortcuts ignore typing
and repeated key events. Save failures remain visible; retries reuse their
request ID. Unsure reviews persist in history and stay out of training exports.
Uncertain model scores and LLM unsure decisions rank first; merge impact breaks
ties. Missing LLM labels/evaluation measurements display as unavailable.

Remote mode sets `LAKEMATCH_REVIEW_STORE=delta`, supplies
`LAKEMATCH_REVIEW_WAREHOUSE_ID` via a Databricks Apps warehouse resource, and sets
`LAKEMATCH_REVIEW_SCHEMA_NAME` to the owned catalog/schema. A deployed app rejects
SQLite. The service principal reads the queue/metadata and reads/writes labels;
the authenticated Apps proxy supplies reviewer identity. The campaign runner
requests no optional OAuth scopes and disables delegated-token forwarding in
the ZR-7 deployment. Delegated Genie remains a separate ZR-8 acceptance gate.

Delta review writes are serialized by one process. Deploy **one worker and one
instance** for a given review store; this is not a distributed lease. SQLite
also enforces unique requests/pairs and transaction locking. Queue snapshots and
statistics are bounded to 10,000 rows and fail explicitly on truncation. Optional
Lakebase is disabled. The engine never imports the app, and no app dependencies
are added to the Apache-2.0 package.

The static-scan follow-up uses insert-only Delta `MERGE` statements for queue,
review and metadata keys, protecting against sequential Statement Execution
replays after uncertain acknowledgements. Metadata retries must preserve the
original value, and reviews return the stored receipt. The single-writer rule
still applies. These changes have local regression checks; remote acceptance
remains subject to the campaign's iteration limit.

Dependencies and lockfiles belong to this subproject. FastAPI is pinned to
0.128.0 for APX route introspection. APX-derived material uses the separate
[Databricks license](APX-LICENSE.txt) and this app is intended to connect to
Databricks Services. Modified/generated files are maintained for this campaign;
upstream notices are retained.

The optional [mastering API boundary](../spec/lakefusion/ACCESS.md) adds
`/api/v1/domains/{domain_id}/tasks` and operation routes with current role,
object and field checks. The default app leaves this backend unconfigured.
An explicit Python 3.12 entrypoint can attach the PostgreSQL `WorkflowAPI` using
`create_review_app(api)`; connection credentials and approved domain contexts
come from deployment configuration. Local review identity is never a mastering
identity. Real Apps ingress, Lakebase OAuth/RLS and remote packaging remain
qualification gates; existing review routes retain the behavior described above.

After preparing the documented offline dependency cache, verify the optional
assembly from the repository root with
`.venv/bin/python tools/run_mastering_http_tests.py`. It builds and imports a
fresh APX wheel, uses the pinned FastAPI runtime and private temporary PostgreSQL
instances, and removes its owned runtime after the tests.
