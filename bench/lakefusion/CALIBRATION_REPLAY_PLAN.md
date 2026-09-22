# LF-B slot 12 — frozen validation replay

Prerequisite: slot 11 completed from `785b0ca`, within its declared bounds, with
one selected validation policy. The model, report and source/configuration hashes
are fixed in [the replay freeze](calibration-replay-freeze-v1.json). Commit that
freeze and the original evidence before executing. This is the last authorized
LF-B experiment; there is no remaining follow-up allocation.

Reload the inspectable JSON logistic model and Platt calibration. Recompute the
entire original validation candidate population, features, raw/calibrated scores,
conflict and one-to-one ambiguity vetoes, selected bands, calibration diagnostics,
family audit and deterministic grouped-bootstrap metrics. Use the already
selected reject boundary 0.1 and accept boundary 0.9. Do not fit, recalibrate,
search thresholds, change retrieval or materialize confirmation.

The same evaluator's `--mode replay` requires a committed freeze, exact original
report/model hashes, all original input/dependency pins and LF-B count 11. It
must match the slot-11 validation digest exactly. Four worker probability-preview
samples continue to use existing comparison/score contracts; all actual routes
remain review. An observed quality result cannot authorize automatic execution.

Run through `tools/experiment.py`, phase LF-B, kind `lf-b-calibration-replay`,
900-second outer limit, one-thread BLAS variables, measured peak RSS ≤4 GiB.
The original 120-second retrieval, 50-candidate, 2-million-pair, 20-million-posting
and 100,000-diagnostic-row limits remain. Use fresh report and bulk-score paths.
Keep terminal outcome and owned-process cleanup, including failure.

The original synthetic validation selected retrieval and bands. Replaying it
establishes reproducibility, not independent accuracy evidence. Confirmation,
real-domain qualification, registry promotion, online integration and automatic
execution remain later gates. This run starts no Spark, service, database,
remote resource or AI request.
