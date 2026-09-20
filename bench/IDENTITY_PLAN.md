# Incremental identity verification — ZR-4 iteration 4

Run only after both native clustering comparisons pass and the macro comparison
selects a method. Use each corpus's frozen model, threshold, field-block setup
and training IDF. Do not retrain, retune, or read confirmation scores.

Use the complete validation-record partition of each corpus (report its size;
this is not a claim to mutate every record in the original 50k dataset). Sort
records by SHA-256 rank with seed 2026091901 and namespace `increment/corpus`.
Take floor(1% of validation records), at least one, for each operation. Delete
the first group; change the next disjoint group by replacing its full profile
with a different validation entity's profile while preserving the record ID;
clone the third group under new `added-...` IDs. Keep exact mutation IDs and
before/after content digests before any incremental scoring. Whole-profile
changes deliberately exercise movement between entities, rather than only typo
correction. Additions and deletions balance the record count.

Recompute the original validation graph in a fresh process and require identical
canonical identities to the stored comparison membership. Recompute the changed
graph with the same frozen model, reconcile all rows, and require exactly the
declared addition/deletion/content-change counts. Journal replay must equal the
entire new crosswalk in both directions. Repeat the changed input; require
identical identities, all journal rows unchanged and zero new cluster events.
Record merge, split, rekey, created and retired events actually observed; do not
invent event counts or silently suppress canonical-key changes.

Preserve crosswalks, the complete journal, events and mutation in sealed local
artifacts. This verifies deterministic snapshots and journal semantics; CLI and
durable publication/recovery retain their separate acceptance requirements.
Two sequential offline runs, at most 900 seconds each / 30 minutes total, with
the comparison's pair/join limits and 30-round bound. No remote/live-label spend.
