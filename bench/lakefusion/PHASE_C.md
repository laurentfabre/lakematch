# Phase C checkpoint — stewardship worker

**In progress, 2026-09-22. LF-C has consumed 1/8 experiments.** The local
transactional worker foundation passes. Lakebase deployment, authenticated
application workflows and the governed two-source pilot remain open.

The accepted source is **`9c7d12a`**, with the plan committed before execution.
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

## Accepted behavior

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

## Remaining gates

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
