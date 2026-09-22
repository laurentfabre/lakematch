# LM-014 development increment — 2026-09-22

Hypothesis: a separate portable comparison service can explain company pairs,
retain source/rules/mapping versions and enforce deterministic precedence
without changing the v1 engine or treating retrieval agreement as merge approval.

Scope: immutable company rules, explicit field presence/normalization, bounded
pair evidence and local regression checks. All suggestions require stewardship;
no calibration, threshold selection, model training, corpus read, remote call or
identity/publication mutation is part of this increment. It consumes no new
experiment slot. LF-B remains at **8/8**; empirical acceptance is pending a revised
bound. Development checks are not matching-quality evidence.

Bounds: one pair per call, at most 10 pinned mappings, seven compared fields,
2,048 characters per scalar input, 64 KiB JSON per pair, four declared retrieval
methods. Run affected portable checks and required commit hooks with their
existing 120-second process limits. Keep confirmation data unmaterialized.

Check missing/null/blank/invalid values, Unicode names, identifier conflicts,
branch granularity, source self-comparison, rule precedence, reordered inputs,
input mutation, mapping/implementation drift and request limits. Record observed
results in PHASE_B.md. Calibrated bands and model explanations remain open.

## Independent APX development preview

Use the existing 13-row synthetic integration fixture and provenance transforms
to build a packaged, read-only six-company demo. Keep Python 3.12 engine imports
in the export tool; the Python 3.11 app reads bounded JSON. Routes live under
`/api/demo/`, use the existing session dependency and have no customer-data or
mutation adapter. A new engine-to-app acceptance run remains blocked by the cap.

Apply the data-app design guidance to a record explorer: company/publication
selectors, selected values first, expandable field evidence and source crosswalks,
then policy/publication references. Use the current APX Button, native select,
details/table elements and generated query hooks. Cover loading, error, empty
and historical-publication states. Retain the selected APX stack and existing
review route.

Development checks: app unit tests, APX type checks, pinned production build and
a loopback browser preview at desktop/mobile sizes. Browser preview has a
120-second bound, no review writes, no model training or acceptance-quality
measurement; stop its owned temporary server after screenshots. Record UI work
as a local preview pending a separately authorized acceptance experiment.
