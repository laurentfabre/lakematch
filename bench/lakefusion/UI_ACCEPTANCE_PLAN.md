# LF-B slot 9 — fresh packaged APX golden-record acceptance

Authorized by [LF-DEC-005](../../spec/lakefusion/EXECUTION_DECISIONS.md). LF-B has
eight consumed runs and a twelve-run limit before this experiment. This is one
new run; retain any failure and use at most the already reserved diagnosed
follow-up slot. It does not reset or relabel earlier development previews.

Hypothesis: the committed APX app can be freshly built and its wheel can serve
the synthetic golden-record and comparison flows independently of the editable
app source or an existing review database.

## Inputs and preconditions

Commit this plan, the runner and [input binding](ui-acceptance-inputs-v1.json)
before starting. The binding pins app/build/browser sources, fixture/export
sources, dependency files, the schema-2 demo bundle and both publication hashes.
Verify the fifteen frozen Phase A files. Stop if a bound input differs; do not
regenerate a fixture to make verification pass. Use the existing APX 0.3.8 build.

The only data are the existing six synthetic companies, two publications,
twelve source versions per publication and twelve explicit pair comparisons.
No corpus evaluation, model fitting, threshold selection, confirmation release,
AI call, remote workspace resource or customer data is used.

## Single-run procedure and gates

1. Check the committed source/input hashes and exact existing demo export.
2. Run the pinned production build from the app directory; require original
   package/lock bytes and a nonempty deployment with every file below 10 MiB.
   Capture the wheel/build hashes. Check final TypeScript and Python types.
3. Extract only the freshly built wheel into an owned temporary directory.
   Verify its demo bytes, backend files and static UI. Force its import path and
   assert that the loaded backend originates there, not the editable source.
4. Run the app's 25 tests against that extracted package. Require zero failures,
   errors and skips. Tests verify every company/publication, field provenance,
   overrides, comparisons/source versions, deletion/history, corrupt inputs,
   session denials and the existing review lifecycle using fresh local stores.
5. Start an owned loopback server from that wheel with a new temporary SQLite
   store. Run the committed browser assertions at 1440×1100 and 390×844. Require
   source conflicts, normalized-name agreement, historical values, deleted
   source exclusion, keyboard disclosure, error recovery, no page errors or
   horizontal mobile overflow, and no review-data fetch or write. Save screenshots.
6. Recheck source/frozen hashes, remove the extracted package and temporary
   stores, and terminate all owned processes. Record terminal evidence through
   `tools/experiment.py` and its append-only ledger.

## Bounds and interpretation

Ten-minute outer runner bound; at most 420 seconds for the build (its individual
steps remain bounded to 240 seconds), 45 seconds per type check, 120 seconds for
app tests, and 130 seconds for the browser/server wrapper. The wrapper keeps its
20-second startup, 90-second browser and at most ten-second cleanup limits.
The outer bound overrides the sum of child limits. No Spark session or cloud
compute starts. Capture local wall time and main-process peak RSS; neither is
an online serving SLA or aggregate browser/build memory measurement.

A pass closes only the first synthetic APX detail-view deliverable in §5.
Empirical calibration, matching quality, live data/authorization, transactional
stewardship, deployed app acceptance and LM-010 remain open. LM-014 and LF-B
remain in progress. The screenshots and ordinary assertions acquire acceptance
status only through this newly declared, bounded run on the pinned fresh wheel.
