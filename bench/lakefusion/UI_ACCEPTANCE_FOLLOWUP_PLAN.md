# LF-B reserved follow-up — canonical temporary directory

Slot 9, `20260922T182532Z-lf-b-packaged-ui-d838a1`, failed after a successful
fresh build and both type checks. The extraction containment check compared a
resolved archive-member path under `/private/var/...` with an unresolved owned
temporary root under `/var/...`. macOS aliases those locations. Even the normal
`lakematch_review/__init__.py` member was refused. Inspection found no archive
member outside the canonical root. No app test or browser ran in that experiment.

The original manifest/report remain unchanged and counted. Its extracted
directory was removed, and the outer runner verified no live owned process-group
members. LF-B now uses **9/12** runs.

Use the extension's one reserved diagnosed follow-up next, as **slot 10**. Move
the initial model/calibration run to slot 11; validation remains slot 12. This
changes only ordering within the same four authorized purposes and total cap.
No extra alternative, quality-target change or further UI retry is authorized.

Single functional change: resolve the owned temporary root once before checking
and extracting wheel members. Retain the containment guard and exact package,
source and fixture checks. Read the slot number from the bound configuration so
the new report identifies slot 10. Preserve the original v1 input binding; commit
the new [v2 binding](ui-acceptance-inputs-v2.json) before running.

Repeat [the same acceptance procedure and gates](UI_ACCEPTANCE_PLAN.md) with
fresh report/JUnit/screenshot paths and a new temporary store. The outer bound is
600 seconds, and all child/resource limits remain unchanged. No product code,
demo data, dependency version, model or quality threshold changes. Retain a
terminal failure if this reserved follow-up does not pass.
