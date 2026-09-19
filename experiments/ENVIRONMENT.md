# Campaign environment

Observed 2026-09-19. Profile `fevm-gdpr2` was explicitly confirmed in this conversation.
Host: `https://fevm-gdpr2.cloud.databricks.com`; workspace ID `7474658055368199`.
Only public or synthetic corpora are authorized.

Laurent subsequently instructed: “FEVM are dev workspace so do not worry about that”.
Quota/expiry discovery is therefore not a prerequisite to the bounded runs. No dollar ceiling was
provided; this does not remove timeouts, the one-active-remote-run limit, immediate cleanup, or the
eight-iteration phase limit. The official FEVM MCP is unavailable, so deployment ID, remaining
quota and expiry are unobserved. No alternative provisioning API is used.

| Capability | Observation | Status |
|---|---|---|
| CLI | 1.17.0; expired OAuth refreshed successfully | Supported |
| Identity | Current-user endpoint succeeds; Laurent has workspace admin membership | Supported |
| Catalog | `gdpr2_catalog` visible | Supported |
| Owned schema | `gdpr2_catalog.lakematch_20260919` created | Supported |
| Owned managed volume | `gdpr2_catalog.lakematch_20260919.artifacts` created | Supported; file write/read/delete passed |
| Workspace root | `/Workspace/Users/laurent.fabre@databricks.com/lakematch/20260919` created | Supported |
| Classic policies | Personal Compute `001756FAA35A6B96` permits one `i3.xlarge`, forces STANDARD; other policies also visible | Policy available; actual startup unproven |
| Classic create | First request timed out at 90 seconds; subsequent inventory empty; second request timed out at 240 seconds and inventory was again empty | Unresolved; ZR-9 parked |
| Runtime catalog | DBR 18 LTS advertises Spark 4.1.0; DBR 19 advertises Spark 4.2.0 | Metadata only |
| Serverless jobs/MLlib | Canary run `280837437066970` completed: Spark 4.2.0, Python 3.12.3, GBT save/reload and native expressions | Supported on tiny synthetic fixture |
| Pipeline API | List succeeds, no pipelines | Read supported; execution untested |
| App API | List succeeds; three unrelated active apps | Read supported; campaign deployment untested |
| Genie API | List succeeds; existing unrelated spaces visible | Read supported |
| Genie Conversation API from an app on behalf of user | Requires campaign fixture and delegated app session | Untested; no claim based on listing spaces |
| SQL warehouse | Shared starter `4aaa742e4712c3c9`, Small, serverless, auto-stop 10 minutes, STOPPED | Read supported; not assigned to this campaign |
| MLflow/UC model registration | MLflow tracking run `f4f76eee021c467bb4092c6b5fe9cf49` logged; UC model name planned: `gdpr2_catalog.lakematch_20260919.person` | Tracking supported; UC registration untested |
| Query profiles / billing | Remote run `280837437066970` retained for attribution | Billing/profile evidence unreconciled; never assumed zero cost |

No shared app, warehouse or cluster is modified. The first classic preflight envelope is one
`i3.xlarge` node, zero workers, STANDARD, 10-minute idle auto-termination, 600-second startup
deadline and explicit termination immediately after RUNNING. Resource definitions remain so a
later run can restart them. Actual restart must still be demonstrated.

Local: macOS 26.6.1 arm64, Python 3.12.13, PySpark 4.1.3, MLflow 3.16.0, PyYAML 6.0.3.
Java reports Temurin 17.0.20.1+1 (`java -version`; vendor API semver `17.0.20+101`), isolated under `.tools/jdk/`;
archive SHA-256 `196d13ba5f10414bef7f6a05a9b3f00edacb18ebacef2b99485db9e2ee18f0e8`.
Dependency versions are in `requirements-local.lock`. OSS Spark lives in `.venv`; any future
Databricks Connect environment must be separate.

Native local and Connect suites initially passed 29 tests each. The installed synthetic CLI
also completed under OS-enforced external egress denial, with 6 links and 1 quarantined row.
These are development observations; the current-source phase verifier is the acceptance authority.
Full command records, failures, digests and timings live in `runs.jsonl` and per-run manifests.

Classic request failures: `20260919T211756Z-classic-preflight-7982c4` (90s) and
`20260919T212038Z-classic-preflight-072b93` (240s). Both timed out without returning a cluster ID.
`classic-inventory-after-timeouts.json` is empty. No further identical requests will be issued.
This is an unresolved creation capability, not proof that the workspace fundamentally lacks classic compute.

Successful serverless canary: Spark 4.2.0, Python 3.12.3, MLflow 3.16.0; cache probe raised
`NOT_SUPPORTED_WITH_SERVERLESS`; Delta fallback succeeded and all scratch tables were removed.
Predictive optimization read-back is DISABLE. Shared warehouse read-back remained STOPPED.
Task setup 115s, execution 114s, notebook work 78.19s. Full output is preserved outside FEVM in
the run manifest's checksummed `serverless-canary.json` evidence. First run used Jobs' default
PERFORMANCE_OPTIMIZED, and the separate STANDARD retry succeeded. No phase parity or
Photon coverage is inferred from these canaries.

STANDARD confirmation `20260919T214533Z-serverless-standard-91d0f6` succeeded on the updated
engine: parent run `667945925462279`, setup 176s, task execution 268s, full run 445.512s,
notebook work 244.01s. MLflow run `a8f8a13d5253422c98cefecef4deff9d` contains its report.
Three expected links, equal reloaded predictions, volume round-trip and scratch cleanup passed.
The earlier STANDARD 300s attempt timed out and is retained; increasing the finite envelope
resolved that failure. These two tiny runs are not a controlled performance or cost benchmark.
`final-resource-state.json` records the final inventory. Remaining ENV gaps: classic creation,
UC model registration, pipeline execution, delegated app-to-Genie conversation, query profiles
and attributable billing. No phase beyond ZR-1 is marked complete.

The successful STANDARD canary Spark model was downloaded and archived locally under its run’s
`artifacts/model.tar.gz`; its checksum and archive provenance are recorded in the manifest.
This preserves the model outside FEVM without committing bulk artifacts.
