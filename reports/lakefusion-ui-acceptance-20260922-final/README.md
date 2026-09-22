# Fresh-package acceptance: synthetic golden records

**Passed on 2026-09-22, LF-B slot 10/12.** A fresh APX wheel was extracted into
an owned temporary directory and loaded independently of the editable app.
All 25 app tests and the desktop/mobile browser assertions passed. This accepts
the first synthetic golden-record detail view in goal §5.

![Source identifiers that need human review](comparison-conflict.png)

[Full desktop view](golden-desktop.png) · [Earlier values](golden-history.png) ·
[Phone view](golden-mobile.png) · [Normalized names](comparison-normalization.png)

The accepted fixture has **six companies, two publications, 96 field explanations
and twelve explicit pair comparisons**. Source versions, selected values,
approved edits, identifier conflicts and deleted sources remain explainable.
The pair memberships are predefined; no model probability or automatic merge
is produced.

Evidence:

- [Bounded experiment manifest](../../experiments/20260922T182853Z-lf-b-packaged-ui-followup-a3e01e/manifest.json)
  records source commit `938fe86`, inputs, environment, a 600-second outer limit
  and terminal process-group cleanup.
- [Acceptance report](../../bench/lakefusion/ui-acceptance-20260922-final.json)
  verifies 89 pinned input files, fresh-wheel imports and exact backend/demo
  contents, source preservation and build hashes.
- [JUnit](../../bench/lakefusion/ui-acceptance-tests-20260922-final.xml):
  **25 tests, zero failures/errors/skips** against the extracted package.
- [Browser receipt](preview.json): 1440×1100 desktop and 390×844 mobile, zero
  page errors, no horizontal mobile overflow, keyboard disclosure, history,
  conflict/normalization views and recovery after a simulated 503. No review
  queue/statistics/history fetch or review write occurred.

The fresh build and final TypeScript/Python checks pass. Its four deployment
files are below 10 MiB, largest **163,756 bytes**. The wheel contains the exact
**191,907-byte** demo JSON. The outer run took **18.70 seconds**; the main Python
process peaked at **25.4 MiB RSS**, excluding child build/browser memory. These
are local acceptance measurements, not online latency or capacity claims.

The extracted package and the browser's temporary store were removed; its
server/browser closed and the outer runner found no live owned process-group
members. All fifteen frozen Phase A files, dependency pins, historical
publication hashes and existing source/golden values are unchanged. No corpus
evaluation, fitting, threshold selection, confirmation release, AI call or
remote workspace operation occurred.

Slot 9's [failure](../../experiments/20260922T182532Z-lf-b-packaged-ui-d838a1/manifest.json)
is retained and counted. Its build/types passed, but the harness compared a
resolved `/private/var` member against an unresolved `/var` temporary-root alias
and stopped before app/browser tests. The
[one reserved follow-up](../../bench/lakefusion/UI_ACCEPTANCE_FOLLOWUP_PLAN.md)
canonicalized that root and repeated the same gates. No app or data change was
needed.

LF-B now uses **10/12** experiments. Its calibration deliverable remains open;
initial model/calibration evaluation and frozen validation occupy the two
remaining slots. Live data adapters, domain/field authorization, transactional
stewardship, deployed app acceptance and LM-010 remain separate later gates.
The detailed [comparison contract](../../spec/lakefusion/MATCH_EVIDENCE.md) and
[app instructions](../../app/README.md) describe the implementation and usage.
