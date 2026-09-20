# Proposed ZR-7 iteration 9 — not authorized

Approve one additional **ZR-7 app acceptance iteration** beyond the current cap.
This does not authorize another ZR-3 scale run or extend other phase limits.

The final allowed run created the campaign app asynchronously, then accessed its
service-principal field before it existed. The app is now provisioned and stopped.
The prepared fix waits for the principal and terminal provisioning state, and
waits through initial STARTING during cleanup. Offline lifecycle tests exercise
those observed transitions and a hard timeout.

The proposed run reuses `lakematch-review-20260919` on `fevm-gdpr2` and owned
warehouse `ec3b6df6c1cabcd4`. It uses the same 24 synthetic queue pairs and reviews
20 through HTTP. Assertions cover provenance, retry idempotence, independent
Delta readback and exact persistence across an app stop/start. It requests no
optional OAuth scope and disables delegated-token forwarding. Genie is disabled.
No unrelated app/warehouse is modified.

The app worker remains one; this workspace uses default fixed compute because
manual instance counts are unsupported. Model/fixture/memory budgets are unchanged.
Work checks a 1,800-second deadline between operations. SQL statements cancel
after 50 seconds, and the 2,700-second outer envelope reserves time to stop and
verify both owned resources. Labels, failed receipts and evidence are preserved.

Reviewable implementation:

- `app/acceptance/lifecycle.py` — bounded readiness and stop handling.
- `app/acceptance/remote.py` — full create/reuse, table/grant/deploy/test/cleanup flow.
- `app/tests/test_lifecycle.py` — observed provisioning transitions and timeout.

After authorization, fingerprint the current app, then use the existing
`tools/experiment.py` wrapper with `--phase ZR-7 --kind app-remote --timeout 2700
--workspace fevm-gdpr2` to run `app/acceptance/remote.py --profile fevm-gdpr2
--report data/app-acceptance-v1/remote-report-v9.json`. Include the app-source,
remote-report and remote HTTP snapshot artifacts. Do not overwrite v5–v8 receipts.

A successful run still needs an independent final audit before ZR-7 is marked
passed. Any remaining failure is reported with cleanup; this proposal grants
one run, not an open-ended sweep. The full campaign retains its other blockers.
