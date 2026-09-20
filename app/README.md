<!-- Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold. -->

# Lakematch review — APX

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
uv sync
apx dev start --attached --skip-credentials-validation
apx dev check
apx build
```

Local mode defaults to SQLite at `data/review.sqlite`, with Genie disabled and
no Databricks client constructed. Set `LAKEMATCH_REVIEW_DATABASE` to select an
existing review database, and `LAKEMATCH_REVIEW_LOCAL_USER` to label a local
reviewer. Those local labels are a configured local identity, not workspace
authentication. Queue/evaluation ingestion is a job operation (`Store.enqueue`),
not a browser API. Empty storage shows an empty queue; no sample rows appear
implicitly. Synthetic acceptance setup is in `acceptance/README.md`.

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

Dependencies and lockfiles belong to this subproject. FastAPI is pinned to
0.128.0 for APX route introspection. APX-derived material uses the separate
[Databricks license](APX-LICENSE.txt) and this app is intended to connect to
Databricks Services. Modified/generated files are maintained for this campaign;
upstream notices are retained.
