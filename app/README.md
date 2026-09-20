# APX prerequisite scaffold

Modified for lakematch on 2026-09-20 from the APX 0.3.8 generated README.

This is the isolated FastAPI/React scaffold required by ZR-7. It contains no
arbitration flow yet. The baseline `apx build` completed: 169,758 bytes in total,
largest deployment file 169,627 bytes, below the 10 MiB per-file platform limit.
See [the prerequisite evidence](../experiments/apx-prerequisites.json).

Active upstream maintenance remains unconfirmed. The repository is not archived,
but its last push is 2026-04-07 and latest release is v0.3.8 from 2026-02-26. The
installed skill labels APX legacy. The brief requires APX, so this scaffold is
preserved while the maintenance gate remains open; no AppKit substitution or
remote deployment has occurred.

Run `apx build app` from the repository root to rebuild. Dependencies and lockfiles
belong to this subproject; the engine does not import it. The app is intended to
connect to Databricks Services. APX-derived material uses [the Databricks license](APX-LICENSE.txt),
separately from the Apache-2.0 engine. Label storage remains the brief's local
store / remote Delta design, with optional Lakebase disabled.
