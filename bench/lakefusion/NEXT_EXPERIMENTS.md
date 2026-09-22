# Approved LF-B extension — 12 total experiments

Current bound: **12 experiments; 12 consumed — extension finished**. Laurent approved “raise it to 12”
on 2026-09-22; [LF-DEC-005](../../spec/lakefusion/EXECUTION_DECISIONS.md) records
the amendment to the original frozen eight-slot limit for LF-B only. At most
four additional iterations are authorized. Existing failures/results remain
counted; LF-A, other LF phases and original campaign limits do not change.
Slot 9 failed in the acceptance harness after the fresh build/type checks; its
[diagnosis](UI_ACCEPTANCE_FOLLOWUP_PLAN.md) is retained. The reserved follow-up
passed as slot 10. The initial model run completed as slot 11 and its frozen
validation replay passed as slot 12. No LF-B experiment or follow-up remains.

| Slot | Authorized purpose | Required before starting |
|---|---|---|
| 9 | Fresh packaged APX acceptance — failed before app/browser tests because of a macOS temporary-path alias check | [Retained run](../../experiments/20260922T182532Z-lf-b-packaged-ui-d838a1/manifest.json); no product or quality pass implied |
| 10 | Reserved single diagnosed follow-up for slot 9 — passed | [Fresh-wheel acceptance](../../reports/lakefusion-ui-acceptance-20260922-final/README.md); same gates and limits, canonical-root fix |
| 11 | First LM-014 model/calibration evaluation — completed; validation selection passed | [Predeclared plan](CALIBRATION_PLAN.md), [model](calibrated-model-v1.json) and [report](calibration-20260922.json); no confirmation or automatic execution |
| 12 | Frozen validation replay — passed with exact candidate, score, band and metric agreement | [Replay report](calibration-replay-20260922.json), [plan](CALIBRATION_REPLAY_PLAN.md) and [immutable selection freeze](calibration-replay-freeze-v1.json); no fitting or threshold search |

[Final interpretation and phase disposition](../../reports/lakefusion-calibration-20260922/README.md)
close LF-B's internal worker and synthetic UI foundations. Phase C is next;
LM-014's confirmation, production approval and live integration remain open.

The reserved model slot is not permission to improvise alternatives or relax a
quality gate. If implementation cannot meet its envelope, record the failure and
park it at the bound. Confirmation stays unmaterialized in this extension;
confirmation acceptance needs a later explicit freeze and run plan.

Each iteration uses the existing experiment runner and append-only ledger.
Retain the protocol's 4 GiB local driver, 15-minute matching/training, 50
candidates per left record, two-million-pair and twenty-million-prejoin limits.
The local UI iteration needs no Spark or remote service and has a ten-minute
outer bound. Remote work, if necessary, requires an explicit per-run plan within
30-minute job/60-minute outer limits; it uses only `fevm-gdpr2`, one run at a time,
and cleans owned resources. No permanent deployment or service expansion is
included in this extension. Missing billing evidence is reported as missing.
