# CODE_REVIEW

> **Fix status, 2026-09-28:** SIM3-001, SIM3-002 and SIM3-003 are resolved in the current worktree; see [Resolution and verification](#resolution-and-verification). The original review below is retained as historical evidence. SIM3-004 is resolved for new v2 execution; its historical v1 qualification remains recorded below.

## Final commit review — 2026-09-28

**Scope:** SIM-1 through SIM-3 and the SIM3-001–004 fixes, relative to baseline `610ce3ffc8afdd1c1bf71fa6761592a327f8723b`. Independent passes covered the feature implementations/reference tests and the benchmark/isolation/audit lifecycle. The primary pass checked catalogue requirements, integration, packaging and the complete regression suite. No unresolved blocker was found in this scope.

| Surface | Evidence / disposition |
|---|---|
| Research catalogue | Phase 1 verifies 29 measures, 27 sourced references and seven shortlisted families; evidence distinguishes definitions, implementation hypotheses and measured results |
| Feature correctness | Seven documented variants, independent reference fixtures, exhaustive DP cases, missing-value behavior, opt-in defaults, field eligibility, resource limits and physical-plan checks reviewed |
| Historical result and recovery | Selection/model/threshold bindings, prediction and physical-plan evidence, corruption rejection and completed-run resume reviewed; the recorded verdict remains `not_beaten` |
| TEST-label isolation | Staged public inputs, selection/model-gated release and v1/v2 audit paths reviewed; synthetic guards cover real file opens and reject invalid release evidence |
| Report accuracy | Fixed the final review finding: v2 reports now use their own `--result` and `--work-dir`, a local result link and quoted paths. A regression checks space-containing paths; historical v1 rendering remains byte-identical |
| Verification portability | The judge now lives at `scripts/verify_simbeat.sh`; the Personal goal command delegates to it. Gate corruption tests use the repository copy. Full artifact checks still require the intentionally gitignored local run cache |

Validation before commit:

- `bash scripts/verify_simbeat.sh 1`: **PASS**.
- `bash scripts/test.sh -p no:cacheprovider`: **211 passed on classic (162.66 s) and 211 passed on Spark Connect (116.83 s)**.
- `cd ~/Projects/Personal && bash goals/verify_simbeat.sh 3`: **PASS**, including the artifact audit and independent negative-verdict calculation.
- `git diff --check`: **PASS**.
- Preservation snapshot: **1,971** historical files unchanged by SHA-256, size and modification time; includes canonical result/report, model files, predictions, prepared inputs and selection.

Limits: no fresh four-corpus experiment, historical model refit or TEST rescoring was performed. Synthetic tests exercise feature execution, partitioning and release/audit behavior. Generation-time source hashes remain historical provenance even though verification and input-isolation code has since changed. Local models, datasets and run caches remain outside Git; committed result JSON supports internal-consistency review, while full artifact verification requires that local evidence. These changes do not justify SIM-4 adoption.

---

## Executive summary

- **Repository / commit reviewed:** `lakematch`, HEAD `610ce3ffc8afdd1c1bf71fa6761592a327f8723b`, including the current uncommitted SIM-3 worktree.
- **Review date:** 2026-09-27.
- **Stack detected:** Python, PySpark 4.1.3 / MLlib, NumPy, local Parquet and JSON artifacts.
- **Overall assessment:** the recorded **`not_beaten` verdict is independently confirmed**. Three medium findings affect the audit and completion gate; one low finding records a disclosed deviation from the literal TEST access rule.
- **Highest-risk area:** connecting the validation winner to the actual frozen TEST evidence.
- **Confidence in review coverage:** high for saved-result arithmetic and artifact consistency; bounded for historical execution order and fresh-run reproducibility.

### One-paragraph summary

The selected additions were padded bigram Dice and q-gram count cosine. An independent calculation from saved TEST predictions reproduced mean F1 **0.8459242718** for the chosen set and **0.8520629405** for Jaro–Winkler, with paired difference interval **[-0.0136894779, 0.0012187909]**. The first three adoption criteria pass; TEST mean non-regression fails. The present artifacts are consistent, but the built-in audit and shell judge accept several inconsistent fixtures, so their passing status alone is insufficient evidence. This review changed no benchmark code, selection, models, predictions or scores and did not rerun TEST.

Contents: [Final review](#final-commit-review--2026-09-28) · [Input isolation](#sim3-004-resolution-isolated-v2-inputs) · [Resolution](#resolution-and-verification) · [Method](#review-method) · [Hotspots](#threat-model-and-hotspot-map) · [Findings](#prioritized-findings) · [Evidence](#rejected-or-unverified-leads) · [Next steps](#suggested-next-steps).

---

## SIM3-004 resolution: isolated v2 inputs

**2026-09-28 — resolved for future execution.** [SIMBEAT_PROTOCOL.md](spec/SIMBEAT_PROTOCOL.md) documents the new boundary and its limits. The original review finding below continues to describe the historical v1 run accurately.

- Explicit provisioning in `bench/simbeat_inputs.py` separates public records, development labels and sealed TEST outcomes. It preserves original IDs/split rules and removes global gold clusters and outcome-derived notes from public records. No experiment entry point provisions automatically or falls back to an eager loader.
- The development manifest checks public bytes and reads precomputed raw/sealed commitments. Preparation partitions candidates before attaching development labels; TEST candidates have no label column. Evaluation reads metadata, development features and VALID-only linkage truth.
- `bench/simbeat_holdout.py` releases outcomes only after frozen selection, manifest and serialized-model checks. One successfully committed release is reused on resume; a crash before commit may retry the source read. New predictions remain bound to that release and the selected models. Verification rereads saved evidence without inference.
- V2 audit checks released outcomes against TEST pairs and rejects TEST rows in development caches. V1 audit compatibility remains unchanged. New results/reports are written under the new work directory, preserving canonical historical paths.

**Verification:** the complete SIM-3 suite passed **96 tests**; a subsequent focused output-preservation regression passed **1 additional test** (**97 total**). These include synthetic staging for all four corpora, actual file-open guards around development/selection, rejected release corruption, successful release reuse, v2 prediction-label audit checks and a byte-identical historical renderer check. The required `cd ~/Projects/Personal && bash goals/verify_simbeat.sh 3` command passed with `not_beaten`.

No real corpus provisioning, model fitting or historical TEST scoring was performed. All **1,971** protected result/report/run files retain their SHA-256, size and modification time. The input boundary prevents harness access to held-out outcomes; it does not eliminate entity overlap, transductive records or label relationships inferable through Leipzig development transitivity. Provisioning is trusted dataset preparation, not an OS access-control or signed-attestation mechanism.

---

## Resolution and verification

**2026-09-28 — SIM3-001 through SIM3-003 resolved.** The saved `not_beaten` verdict and all original experiment evidence are preserved.

| Finding | Change | Regression coverage |
|---|---|---|
| SIM3-001 | A shared selection replay uses the recorded shortlist, checks every greedy option and stop, and binds chosen families, variants, feature columns, models and thresholds across VALID, the lock and TEST. Fresh confirmation replays selection and checks the live manifest before loading a corpus or starting Spark. | Coordinated JW substitution; changed models, thresholds, columns and traces; incomplete corpus coverage; nonwinning selection and changed code rejected before inference |
| SIM3-002 | The default audit verifies saved model files and assembler columns, prediction file hashes, prediction IDs and labels against cached inputs, reconstructed confusion counts, and actual physical plan files. New predictions use an atomic envelope bound to the selection, manifest, models, columns and input hashes. | Changed prediction bytes, IDs, labels and probabilities; absent or rehashed UDF plans; stale envelopes; legacy orphan rejection; completed and interrupted cache resume with loaders and inference forbidden |
| SIM3-003 | Phase 3 of `~/Projects/Personal/goals/verify_simbeat.sh` requires the artifact-backed audit and retains its independent verdict calculation. | The actual shell gate rejects fabricated traces, missing locks or confirmations, TEST-based selection and wrong chosen models; the original negative result passes |

The read-only auditor is `bench/simbeat_audit.py`. `bench/simbeat.py audit` checks local evidence by default; `--json-only` is explicitly a partial internal-consistency check. Assertions do not implement audit guards, so Python optimization cannot disable them. Historical generation-time source hashes remain unchanged: updating the verifier does not change which source produced the recorded run. Completed historical runs verify and return without refitting, rescoring or rewriting results.

Legacy bare prediction arrays are accepted only alongside a matching completed confirmation and verified artifacts. An orphan legacy array is rejected before Spark starts; it cannot be attached to a new selection. New versioned envelopes can finish confirmation from cached rows without inference. These checks establish local consistency, not a signed attestation of historical execution order.

Verification performed without model fitting or new TEST predictions:

| Command / check | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_simbeat.py tests/test_simbeat_audit.py tests/test_simbeat_resume.py -p no:cacheprovider` | **64 passed** in 53.29 seconds |
| `cd ~/Projects/Personal && bash goals/verify_simbeat.sh 3` | Exit 0; artifact audit passes; `ALL CHECKS PASS — SIM-3 landed` |
| Before/after SHA-256, size and modification-time comparison | All **1,971** protected files unchanged, including result JSON, report, selection, predictions, model files and prepared data |

The original result JSON SHA-256 remains `aa623bb61e95efb50db9205487184ae996d873097dafe30b05746c10bfe91fb2`. TEST mean F1 remains **0.8459242718336286** versus **0.8520629404907134** for JW. No TEST scoring, model fitting or source-provenance relabeling was performed. The historical SIM3-004 qualification and the original bootstrap qualifications remain unchanged; no adoption is warranted by this result.

---

## Review method

- **Documents read:** SIM-3 requirements in `~/Projects/Personal/goals/goal_beat_jw.md`; the phase-3 shell judge; `README.md`; `pyproject.toml`; `bench/SIMBEAT.md`; benchmark, corpus, feature-selection and decision code; protocol tests; saved selection, metrics, plans, model directories and predictions. No repository-local `AGENTS.md` or `CLAUDE.md` was found; the supplied global instructions applied.
- **Independent passes:** two reviewers started with fresh context, covering protocol/statistics and audit/recovery. The primary reviewer separately reconstructed results without importing `simbeat` or PySpark.
- **Commands run:**

| Command | Result |
|---|---|
| `cd ~/Projects/Personal && bash goals/verify_simbeat.sh 3` | Exit 0; `ALL CHECKS PASS — SIM-3 landed`, `not_beaten` |
| `cd ~/Projects/Pro/lakematch && .venv/bin/python bench/simbeat.py audit` | Pass |
| `.venv/bin/python -m pytest tests/test_simbeat.py -q` | 5 passed |
| `.venv/bin/python /private/tmp/sim3-independent-review.py` | Independent evidence checks and calculations passed; no PySpark import |
| Pure `render_report(json.load(...))` comparison | Byte-identical to the existing Markdown report |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /private/tmp/sim3-audit-review/reproduce.py` | Corruption cases incorrectly accepted; canonical artifacts untouched |
| `LAKEMATCH_REPO=/private/tmp/sim3-audit-review/phase3-fixture bash ~/Projects/Personal/goals/verify_simbeat.sh 3` | Fabricated-trace fixture incorrectly passed |

- **Evidence independently checked:** all **21 variants / 84 model directories**, all **22 recorded source hashes**, all **9 corpus-file hashes**, all **16 physical plan files**, complete greedy options/stopping, development/test pair separation, frozen model/threshold identity, actual prediction IDs/labels against cached pairs, and every TEST confusion-count array. The bootstrap was separately implemented with batched draws and reproduced the interval to machine precision.
- **Constraints or blind spots:** no model was fitted, loaded for inference or rescored; no benchmark `run`, `prepare`, `evaluate` or `confirm` command was executed. This cannot establish cold-run numerical reproducibility, prove that historical predictions were produced by a particular model, or prove the historical number of TEST exposures. The review did not perform a general production security/dependency audit.

### Independently reconstructed TEST counts

Each tuple is `(TP, FP, FN)`. FEBRL4 units are left records; other units are supplied or blocked pairs.

| Corpus | Units | Chosen counts | JW counts | Chosen F1 | JW F1 |
|---|---:|---|---|---:|---:|
| FEBRL4 half unmatched | 986 | (507, 0, 0) | (507, 0, 0) | 1.0000000000 | 1.0000000000 |
| BPID | 1990 | (723, 152, 143) | (767, 204, 99) | 0.8305571511 | 0.8350571584 |
| Abt-Buy | 1892 | (132, 49, 71) | (134, 39, 69) | 0.6875000000 | 0.7127659574 |
| Leipzig Affiliations | 3120 | (1630, 347, 159) | (1646, 391, 143) | 0.8656399363 | 0.8604286461 |

Reviewed file SHA-256 values:

```text
bench/results/simbeat.json:
aa623bb61e95efb50db9205487184ae996d873097dafe30b05746c10bfe91fb2
data/runs/simbeat/selection.json:
46dab651e12aa5790597704a5cd8c01210dbfb4be3ec73a93dc352b2aeadeb52
```

Hashes, sizes and modification times of the result, selection lock, four prediction files and four confirmation files were unchanged during the independent calculation. Scratch evidence is at `/private/tmp/sim3-independent-evidence.json`; mutation script/output are in `/private/tmp/sim3-audit-review/`. The table, hashes and reproduction descriptions preserve the key evidence in this report. Scratch files are local and are not part of the repository.

---

## Threat model and hotspot map

| Surface | Why it matters | Key files or paths |
|---|---|---|
| Corpus ingestion and splitting | Labels must not influence selection across the TEST boundary | `bench/corpora.py`, `bench/simbeat.py:147`, `:217`, `:316` |
| Greedy selection and freeze | The confirmed model must be the VALID-selected model | `bench/simbeat.py:360`, `:443`, `:474` |
| Saved confirmation and resume | Stale or mismatched local artifacts can invalidate the conclusion | `bench/simbeat.py:378`, `data/runs/simbeat/` |
| Statistics and plans | Counts, pairing and UDF claims determine the published evidence | `bench/simbeat.py:262`, `:298`, `:427`, `:500` |
| Completion gate | A green result controls whether the phase is treated as finished | `~/Projects/Personal/goals/verify_simbeat.sh:98`, `:137` |

This is an offline research CLI over public data. The relevant failure boundary is between source data, cached intermediate files, selection metadata and published results; no remote attacker or cryptographic authenticity guarantee is assumed.

---

## Prioritized findings

Scores use the review contract's impact / likelihood / reachability / confidence / blast-radius rubric.

| Rank | ID | Severity | Category | Confidence | Score | Summary | Affected files |
|---|---|---|---|---|---:|---|---|
| 1 | SIM3-001 | Medium | Correctness | High | 41 | Audit does not bind the confirmed model to the VALID winner | `bench/simbeat.py:526` |
| 2 | SIM3-002 | Medium | Artifact integrity / recovery | High | 38 | TEST prediction provenance and plan evidence escape audit | `bench/simbeat.py:400`, `:529` |
| 3 | SIM3-003 | Medium | Verification coverage | High | 37 | Completion judge accepts fabricated selection history | `goals/verify_simbeat.sh:137` |
| 4 | SIM3-004 | Low | Protocol conformance | High | 30 | Raw TEST is parsed before selection, contrary to the literal access rule | `bench/corpora.py:121`, `bench/simbeat.py:240` |

## Detailed findings

### [Medium] SIM3-001 — Audit can confirm a different model from the VALID winner

- **Category / class:** correctness; missing cross-artifact invariants.
- **Confidence / priority score:** high; 41, from `(3, 3, 4, 5, 2)`.
- **Reachability:** `audit()` on a supplied result JSON, including historical or manually repaired artifacts.
- **Affected files:** `bench/simbeat.py:500`, `:514`, `:526`–`:534`; `tests/test_simbeat.py:17`–`:59`.
- **Evidence / validation:** a disposable copy retained the Dice+Cosine `chosen_families` and VALID `chosen` row, but changed the chosen variant and lock to JW and copied the existing JW model/confirmation into `chosen`. After recomputing the lock digest and TEST summaries, `audit()` accepted the inconsistent result and its verdict flipped from **`not_beaten` to `beaten`**. A separate copy with every VALID threshold set to `-50` and model hash set to `"wrong-model"` also passed.
- **Why this matters / failure path:** matching confirmation metadata to the lock does not prove that either refers to the model selected on VALID. A model-identity mix-up can survive audit and alter the adoption verdict.
- **Root cause:** the audit checks family selection and lock/confirmation consistency separately; it never binds the top-level variant, lock variant, selected VALID model and confirmed model into one invariant.
- **Minimal fix:** derive the canonical chosen variant from the recorded shortlist/families; require both variant fields to match it. Bind chosen and JW model hashes, thresholds and feature columns to their corresponding VALID rows; validate threshold ranges. Use the recorded manifest shortlist for historical replay.
- **Regression tests to add:** wrong chosen variant; swapped model; mismatched threshold; invalid threshold; changed selected feature columns.
- **Notes and uncertainty:** the untouched saved artifacts passed these stronger comparisons during this review. No current model-identity mismatch was found.

### [Medium] SIM3-002 — Saved TEST evidence and plan claims are not audited

- **Category / class:** artifact integrity and resumability; unbound cached evidence.
- **Confidence / priority score:** high; 38, from `(3, 2, 4, 5, 2)`.
- **Reachability:** result auditing, or confirmation resumed from an existing `test_predictions.json`.
- **Affected files:** `bench/simbeat.py:399`–`:411`, `:529`–`:539`; plan generation at `:202`–`:213`.
- **Evidence / validation:** setting all `predictions_sha256` values to `"not-a-sha256"` still passed audit. Independently setting every TEST builtin proof to `udf_free=False` with empty columns also passed. The audit does not open prediction or plan files. Resume reads bare cached predictions at line 402, then records the *current* selection digest at line 407 without a prediction-side selection/model binding.
- **Why this matters / failure path:** stale cached predictions or a mismatched plan can be labelled as evidence for the current selection and accepted because the JSON's count arithmetic remains consistent.
- **Root cause:** declarations and aggregate counts are checked, but their relationship to saved raw evidence is not validated.
- **Minimal fix:** store selection, model, threshold and input identities in a prediction envelope; verify them before cache reuse. Add an artifact-backed audit mode that checks file hashes, prediction IDs/labels, recomputed confusion counts and actual plan contents. At minimum, validate TEST plan declarations in the JSON-only audit.
- **Regression tests to add:** stale prediction envelope; wrong prediction digest; altered labels/probabilities; missing or UDF-bearing TEST plan; resumed confirmation under a different lock.
- **Notes and uncertainty:** all four actual prediction files and all sixteen actual plan files matched their published hashes and claims. This finding concerns what the audit would fail to detect, not observed corruption.

### [Medium] SIM3-003 — The supplied completion gate can pass fabricated selection history

- **Category / class:** verification coverage; incomplete acceptance gate.
- **Confidence / priority score:** high; 37, from `(2, 3, 4, 5, 2)`.
- **Reachability:** the required `bash goals/verify_simbeat.sh 3` command.
- **Affected files:** `~/Projects/Personal/goals/verify_simbeat.sh:98`–`:144`, especially `:120` and `:137`; helper-only coverage in `tests/test_simbeat.py:17`–`:59`.
- **Evidence / validation:** a temporary fixture replaced `forward_selection` with `[{"fabricated": true}]` and emptied `selection_lock`, `confirmation` and `meta`. Phase 3 still exited 0 and printed `ALL CHECKS PASS — SIM-3 landed`.
- **Why this matters / failure path:** a result may satisfy summary-row arithmetic while lacking any valid selection trace or frozen TEST evidence. The finish-line command does not distinguish that artifact from a complete experiment.
- **Root cause:** the shell gate checks required rows, a nonempty trace and the four verdict inequalities, but never executes the stronger audit.
- **Minimal fix:** invoke the strengthened audit from phase 3 and retain the separate verdict calculation. Require selection/confirmation identities and expected corpus/variant coverage. Do not add any training or TEST scoring to verification.
- **Regression tests to add:** the fabricated-trace fixture above must fail; missing lock, missing confirmation and wrong model must fail; the recorded negative result must continue to pass.
- **Notes and uncertainty:** the real trace independently reconstructed correctly: seven first additions, six second additions and five rejected third additions, across 84 fits.

### [Low] SIM3-004 — “TEST read exactly once” is implemented as one prediction confirmation

- **Category / class:** protocol conformance; disclosed requirement deviation.
- **Confidence / priority score:** high; 30, from `(1, 3, 3, 5, 1)`.
- **Reachability:** normal corpus loading and preparation, before validation selection.
- **Affected files:** `~/Projects/Personal/goals/goal_beat_jw.md:72`–`:74`; `bench/corpora.py:95`–`:105`, `:121`–`:139`; `bench/simbeat.py:223`, `:240`–`:244`, `:318`; disclosure in `bench/SIMBEAT.md:43`.
- **Evidence / validation:** loaders parse all split files, including TEST labels, and preparation persists all labelled pairs before filtering development rows. Evaluation invokes the loaders again. Thus literal raw TEST access is not isolated to confirmation.
- **Why this matters:** a strict reading of the hard access rule is not satisfied, even though the narrower prediction-confirmation discipline is implemented.
- **Root cause:** eager all-split corpus loaders also supply metadata and unlabeled record preparation.
- **Minimal fix:** separate development labels from held-out outcomes in a future harness, or obtain an explicit specification clarification that one frozen prediction confirmation is the intended rule. Preserve this historical result and disclose its scope; do not retroactively rerun or retune TEST.
- **Regression tests to add:** a TEST-label reader that raises if called during development or selection, with unlabeled transductive preprocessing handled separately.
- **Notes and uncertainty:** no TEST outcome-statistic path into VALID selection was found. This does not invalidate the independently reproduced negative arithmetic verdict.

---

## Rejected or unverified leads

| Candidate | Disposition |
|---|---|
| Wrong published F1, CI or verdict | Rejected for this snapshot: independently reconstructed from saved predictions, cached labels and source FEBRL truth |
| Missing greedy options or wrong stopping | Rejected: complete 7/6/5 option rounds, positive gains only, third round correctly rejected |
| JW title omission in the new baseline | Rejected: saved baseline columns differ only by corresponding `lev_*` / `jw_*` fields on all four corpora; historical correction is disclosed |
| Existing Monge–Elkan cap silently raised | Rejected: baseline comparisons retain 30 tokens; new measures use separate limits |
| Python UDF hidden in the builtin comparison evidence | Rejected for saved physical plans: all eight builtin projections were free of UDF markers; all eight JW projections contained them. Scope excludes pinned record embeddings and model scoring |
| Statistical significance of the difference | Not established: the paired interval includes zero. Pair resampling ignores entity dependence, as disclosed for Abt-Buy/Leipzig. FEBRL4 also conditions on fixed one-to-one assignments; it does not resample right-record competition. These qualifications do not change the point-estimate gate |
| Literal historical one-time exposure or full deterministic rerun | Not proven from mutable local artifacts; source ordering and saved identities are consistent. No new training or TEST scoring was permitted or performed |
| Stable historical replay after catalogue changes | A scratch reversal of the active shortlist caused audit to raise `KeyError`. The pure renderer is deterministic; audit reconstructs variant names from the current catalogue. Address this with the recorded-shortlist change in SIM3-001 |

## Quick wins

- Add negative audit fixtures before extending the existing five arithmetic/protocol tests.
- Add an artifact-backed verification path using the saved predictions; this requires no Spark inference.
- State the TEST-access qualification and conditional-bootstrap scope explicitly in any downstream summary.

## Suggested next steps

1. **Completed 2026-09-28:** fix SIM3-001 through SIM3-003 with corruption and resume tests, preserving the recorded selection and prediction files.
2. **Completed 2026-09-28:** isolate raw TEST outcome access for new v2 runs; retain the documented FEBRL4 bootstrap qualification.
3. Keep the current `not_beaten` result and opt-in defaults. SIM-4 adoption remains inapplicable; this review authorizes no new TEST experiment.

## Notable strengths

- The result is honestly negative and did not trigger adoption or reselection.
- Full-precision greedy selection, explicit stop conditions and paired sampling are implemented correctly.
- Source/data/model/plan identities and per-unit confusion counts made independent inspection possible.
- Corrected split hashing and JW field coverage are documented and all baselines were measured within the same experiment.
- The Markdown report is deterministically derived from the saved result.

## License

This review accompanies the repository's Apache-2.0 code; dataset and model licenses remain unchanged.
