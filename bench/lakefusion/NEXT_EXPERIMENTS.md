# Proposed LF-B extension — not authorized or executed

Current bound: **8 experiments; 8 consumed**. Proposed new total: **12**, allowing
at most four additional iterations. Existing failures/results remain counted;
LF-A and the original campaign limits do not change. This file does not modify
the approved protocol or grant permission to run an experiment.

| Slot | Proposed purpose | Required before starting |
|---|---|---|
| 9 | Accept the first APX synthetic golden-record view from a fresh build: pinned historical field provenance, overrides, deleted sources and desktop/mobile navigation | Final app/source digest, fresh owned local store, browser plan and frozen demo hashes |
| 10 | First LM-014 model/calibration evaluation using the selected candidate path and approved development/validation families | Implement and review one explicit feature/model/calibrator contract; commit family manifests, negative sampling, thresholds-selection procedure and all hyperparameters before reading results |
| 11 | At most one diagnosed follow-up for a failure in slot 9 or 10 | Written diagnosis, one declared change and retained failure; no open-ended sweep |
| 12 | Frozen validation replay of the selected result and evidence review | Passing prerequisites, immutable configuration and compatible existing replay contract |

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
included in this proposal. Missing billing evidence is reported as missing.
