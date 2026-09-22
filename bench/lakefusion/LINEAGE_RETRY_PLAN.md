# LF-B iteration 8 — historic retry across an implementation change

Declared after slot 6 passed 224 checks and while slot 7's Delta proof was
running. Review found that both provenance adapters replayed the current scalar
implementation before the generic publisher could resolve a committed duplicate.
Historical reads already avoid recomputation, but an exact duplicate would fail
after the scalar implementation changed or became unavailable.

Make the pre-catalog request check structural/integrity-only. Keep full scalar
replay inside the new-publication builder. Test that an existing batch retries
without invoking the current calculator and that a genuinely new batch still
requires it. Add the same check to the remote proof after its two publications.

One final LF-B experiment (slot 8/8), maximum 1,500 seconds, runs the local
acceptance runner first (at most 300 seconds, fresh report/JUnit/fixture), then
the single owned serverless proof (at most 1,150 seconds including cleanup).
Do not start while slot 7 is active. Use the same fixture sizes, table bounds,
profile, timeouts and owned-resource cleanup as LINEAGE_PLAN.md. Local and remote
reports must capture the final source hashes. Retain slots 6 and 7 unchanged.

This uses the last slot; it does not reset the phase cap. No confirmation data,
AI, candidate tuning, permanent job or application deployment is involved.
