# Goal: bring lakematch to its specified feature level through FEVM experiments

Created: 2026-09-19. Status: in progress; ZR-3 iterations 1–7 complete, selecting MinHash as the only complete feasible retriever. Both frozen FEBRL confirmations pass; scale completes through 100k and fails at 1m with Java heap exhaustion. ZR-4 native/identity comparisons and durable CLI publication passed through iteration 7; round-default reconciliation and final acceptance remain. ZR-6 iteration 4 local integration checks pass after the first remote SDP analysis failure; corrected remote repeats are next. ZR-1/2/5 need affected evidence refreshed. Classic compute is confirmed unsupported on the selected workspace; ZR-9 parked at ENV.

Build, run, measure and improve lakematch until **ZR-1 through ZR-9 in
[the brief](spec/BRIEF.md#phases) pass with reproducible evidence**, using an explicitly selected
FE Vending Machine (FEVM) workspace for Databricks experiments. The desired feature level is the
complete brief: a portable entity-resolution engine, benchmark-selected methods, durable identities,
MLflow tracking and registration, Lakeflow pipelines, an APX arbitration app, Genie, and verified
serverless and classic execution. A prototype score or a successful deployment alone is not completion.

This file is the execution plan and authoritative progress ledger. Creating it does not launch the
campaign. Resume with `/goal /Users/laurent.fabre/Projects/Claude/lakematch/goal.md`; once execution
is requested, continue through eligible tasks and fix failed gates until the finish line is met or an
actual external dependency prevents progress.

## § 1 — Scope and authorities

- [spec/BRIEF.md](spec/BRIEF.md) defines features, decisions D01–D28, method choices and phase gates.
  This goal changes the deployment destination to **FEVM**, following the latest user instruction;
  it retains the feature requirements and local portability checks.
- [spec/bench/README.md](spec/bench/README.md) and
  [spec/bench/ASTRA_REVIEW.md](spec/bench/ASTRA_REVIEW.md) provide historical measurements and
  evaluation pitfalls. Those results are references, not evidence that this implementation passes.
- [The porting study](spec/porting/PORTING.md),
  [its review](spec/porting/PORTING_ASTRA_OPINION.md), and the research on
  [similarity](spec/research/similarity_sota.md) and
  [platform support](spec/research/platform_facts.md) inform experiments. Recheck platform claims on
  the selected runtime; the brief's final decisions take precedence over older recommendations.
- Use this repository root. Old `~/Projects/Pro/lakematch` paths, `fourth-pat` profile names, warehouse
  IDs, Free Edition quotas and commands in the research are historical, not execution settings.
- Preserve the private Apache-2.0 repository and independent PySpark implementation: no Zingg source,
  translation, JAR or adapter. Keep Zingg comparisons as recorded figures. Only public or synthetic
  corpora enter the campaign; personal lake data is outside scope.
- Mandatory engine dependencies remain `pyspark`, `mlflow` and `pyyaml`. Benchmark tools and optional
  integrations use separate extras/environments. DQX stays a lazy adapter; APX stays in `app/`.
- Use Spark SQL built-ins on the default matching path, with explicit optional UDF features and
  optional embedding precomputation. Centralize runtime differences in `lakematch.runtime`.
  SDP flows build lazy plans; labelling, training and convergence loops run in job tasks.
- Every paid feature has its existing config switch. Laptop mode is offline after dependencies,
  models and corpora are prepared, with all paid features off. Databricks defaults enable app and
  Genie as specified; other paid integrations remain off unless included in an experiment.

## § 2 — FEVM execution context

Laurent selected **`fevm-gdpr2`** for this campaign. Its configured workspace host is
`https://fevm-gdpr2.cloud.databricks.com`. Use this selection for both serverless and classic
experiments, subject to the capability checks below. Do not substitute `fevm`, another similarly
named profile, or `DEFAULT`; no further profile-selection confirmation is needed.

`fevm-gdpr2` is a GDPR-labelled workspace: **only synthetic or public corpora ever land there**
(FEBRL, BPID, the Magellan/DeepMatcher pairs, Leipzig Affiliations, Splink `historical_50k` and the
seeded synthetic scale case all qualify). No real personal data, no lake people/merchant view, nothing
from `Health/`. This is the same rule as §1, restated at the point the destination is fixed.

Classic-compute availability is the single capability ZR-9 depends on and the reason a paid workspace
matters, so it is a **blocking ENV preflight**, not a check deferred to ZR-9: confirm at ENV time that
`fevm-gdpr2` can create a policy-compatible classic cluster. If it cannot, record the missing
capability and park ZR-9 immediately (do not substitute another workspace); local and serverless work
continues meanwhile.

| Setting | Initial state / how to resolve |
|---|---|
| Serverless CLI profile and host | `fevm-gdpr2` — `https://fevm-gdpr2.cloud.databricks.com`, explicitly selected by Laurent. Authentication and capabilities remain to be verified. |
| Classic CLI profile and host | Same selected profile and host: `fevm-gdpr2`. Classic compute/policy availability is a **blocking ENV preflight** (ZR-9 depends on it); if unavailable, report the missing capability, park ZR-9, and do not choose another workspace. |
| FEVM deployment ID and expiry | Record when the chosen workspace is identified. Use the official FEVM MCP for provisioning or lifecycle changes if needed. |
| Catalog, project schema and volume | Resolve in the selected workspace; isolate campaign assets in an owned `lakematch_<campaign>` schema. Record exact names. |
| Workspace root, experiment and model names | Record the campaign paths and resource IDs before the first remote run. |
| Compute and warehouse | Select permitted, appropriately sized resources; record ownership, policies, runtime and auto-stop settings. |
| Campaign cost limits | Laurent waived quota/expiry as a prerequisite on 2026-09-19 (“FEVM are dev workspace so do not worry about that”). No dollar ceiling specified; keep finite run envelopes, one active remote experiment, eight iterations per phase and immediate cleanup. |

Load `databricks-core` and the relevant product skills before Databricks operations (per the brief's
*Skills to load, by phase*: `databricks-core` always, then the per-phase set — `databricks-dabs`,
`databricks-pipelines`, `databricks-jobs`, `databricks-mlflow-evaluation`, `databricks-unity-catalog`,
`databricks-apps`, `databricks-genie-agents`, `dataviz`). Pass `--profile fevm-gdpr2` explicitly to
every workspace CLI command; give SDK clients the same explicit profile. Use the official `fevm`
integration only when workspace provisioning or lifecycle management is needed. Do not substitute a
different workspace when a capability is absent.

Stop billed resources the instant a run ends — do not leave this to auto-stop alone: stop the SQL
warehouse (`databricks warehouses stop <id> --profile fevm-gdpr2`) and terminate any classic cluster
(`databricks clusters delete <id> --profile fevm-gdpr2`) immediately after evidence capture, and verify
they can restart for the next test.

ENV preflight must establish authentication, permissions on the project schema/volume, supported
serverless environment and **classic policy availability (blocking — see above)**, MLflow/UC access,
pipeline availability, app and Genie access — including whether the **Genie Conversation API answers
for an app on behalf of the user** on this workspace, since ZR-8 depends on it — and
query-profile/billing evidence access. Record supported, unsupported and untested capabilities
separately. Keep local OSS Spark and Databricks Connect in separate environments.
Pin Python, Java and Spark versions; start local reproduction with Python 3.12, Java 17 and Spark
4.1.3 from the brief, and record the actual FEVM runtime versions.

Local implementation and validation can proceed while a remote dependency is unresolved.

## § 3 — Feature acceptance ledger

All gates below are required. A phase may be partially implemented but remains pending until its
acceptance evidence exists. The detailed phase clauses in the brief also apply.

| ID | Acceptance gate | Status | Evidence |
|---|---|---|---|
| ENV | Explicit FEVM target(s), capability report, isolated resources and bounded run configuration are recorded. | In progress | [Environment](experiments/ENVIRONMENT.md); auth, owned schema/volume, serverless native engine and UC model checks pass; classic Jobs submission explicitly reports serverless-only workspace; delegated Genie still untested. |
| ZR-1 | Installable package, YAML config and CLI; native quality checks split valid/quarantined rows with reasons; deterministic candidates/features/matcher/decision produce links. Tests pass on local Spark and local Spark Connect, including all-paid-features-off offline execution. Implement capability-aware materialization and phase verifiers. | Revalidation pending (checkpoint passed) | [Engine evidence](bench/ENGINE.md); source `66f76bd952fb`; 71 tests pass in each mode with no skips; offline and full FEBRL4 CLI, wheel installation/private-repository check pass; `bash verify_zr.sh 1` exits 0. |
| ZR-2 | Feature families cover every configured field type. Default matching plans have no `PythonUDF`, `BatchEvalPython` or `ArrowEvalPython`; optional Jaro-Winkler and affine-gap features are gated. Ablations cover FEBRL4-half-unmatched, BPID, Leipzig Affiliations and Abt-Buy, including local embeddings for organisation/title, accuracy and preprocessing cost. | Revalidation pending (checkpoint passed) | [Ablations](bench/ABLATION.md), [feature contract](bench/FEATURES.md), [run index](bench/ablation_index.json). All seven field types and individual removals, native plans, optional UDFs and actual offline MiniLM execution verified. Source `89407f97a43b`; `bash verify_zr.sh 2` exits 0. 71 tests pass in both modes. Embeddings default off after inconclusive paired gains; confirmation remains unscored. |
| ZR-3 | Reproducible harness runs every brief corpus, compares every required method on validation and ships the documented winners. On held-out FEBRL4-half-unmatched: F1 >= 0.97 with all fields and >= 0.96 with SSN hidden; each local end-to-end run is under 60 seconds including Spark startup. Publish candidate recall, confidence intervals, baselines and cost. Include the scale evidence specified below. | [Candidates](bench/CANDIDATES.md) selects MinHash as the only complete feasible retriever; Levenshtein/GBT/IDF-only selected on validation. Both frozen normal-CLI FEBRL confirmation gates pass: F1 0.9889 in 29.19s all-field, 0.9868 in 27.30s SSN-hidden. Six other holdouts completed. Iteration 7 scale ladder completed 1k/10k/100k; 1m failed during candidate materialization with Java heap exhaustion after 672.80s. Partial join counters are preserved. Defaults, `bench --all`, original diagnostic and final compatible-source acceptance remain pending. [Benchmarks](bench/BENCHMARKS.md). | Four alternative retrievers pass offline train/log/reload CLI checks; 17 focused regression tests pass. Retrieval iteration 1/8 is documented in [METHOD_PLAN.md](bench/METHOD_PLAN.md) and [RETRIEVAL.md](bench/RETRIEVAL.md). BPID gram/union exceed the fixed join budget; the harness records rejections without raising limits. All nine corrected retrieval runs completed with 90 method/scope outcomes; classifier iteration 2 is predeclared and 98 tests pass in both classic Spark and Spark Connect; all 81 classifier fits completed, selecting Levenshtein/GBT (macro F1 0.8201); compact-feature iteration 3 completed; IDF-only token features selected by the simpler-choice rule; no confirmation scoring. |
| ZR-4 | Compare verified merge, connected components, center and star on FEBRL3 and `historical_50k`, reporting pairwise and B-cubed metrics. Demonstrate convergence, unchanged-input stable `mdm_id`, and an exactly reconciled crosswalk/merge/split log after 1% additions, changes and deletions. | In progress | [Clustering evidence](bench/CLUSTERS.md): isolated, training-only Splink baselines passed. Pairwise/B-cubed F1: FEBRL3 0.9979/0.9986; historical_50k 0.8580/0.8797. Iteration 5 passed both native corpora: verified merge selected, pairwise F1 1.0000 / 0.9392 and B-cubed F1 1.0000 / 0.9454. Iteration 6 passed both exact 1% mutation audits, unchanged-input stability and repeated-input idempotence. [Identity evidence](bench/IDENTITY.md). Iteration 7 normal CLI publication/recovery passed with three durable commits across five fresh calls. [Publication](bench/PUBLICATION.md). The read-only verifier rejects the still-unreconciled 20-round shipped default; current full-suite acceptance remains pending. |
| ZR-5 | Composite MLflow model includes classifier/pipeline, candidate and feature specs/order, config, thresholds and label-set digest, with signature, dataset lineage and evaluation. Local SQLite tracking resolves `runs:/<id>/model` without a registry. FEVM registers in UC, resolves the champion alias to an immutable version, and reloads with equivalent predictions in a fresh session. Respect the runtime model-size limit. | Revalidation pending (checkpoint passed) | [Composite models](bench/MODELS.md): offline SQLite and CLI accepted-run reload, dataset lineage/evaluation, 71 classic/Connect tests, UC `pair_model/2` and fresh-task predictions pass. FEVM run `429596527159022`; complete package 142,284 bytes; delta < 1e-12; `bash verify_zr.sh 5` exits 0. No confirmation scores used. |
| ZR-6 | Bundle validates and an actual FEVM serverless run completes. SDP holds candidates, features, scoring and links; training/clustering are tasks. DQX and native quality engines agree on seeded bad rows. Each FEBRL4 variant is within 0.01 absolute F1 of its frozen local reference. Default config and all-paid-features-off config both deploy/run; query profiles support the Photon report. | In progress | Both bundle targets validate. Offline DQX/native exact parity passed. Native-model adapter iteration 1 failed on a harness column-name collision; iteration 2 corrects the harness and repeats parity before deployment. [Plan](bench/SERVERLESS_ADAPTER_PLAN.md). |
| ZR-7 | APX confirmed still maintained and the built bundle is under the Databricks App file-size limit (checked before UI work). APX app runs locally and as a Databricks App. Uncertainty-ordered, keyboard-first review supports match/no-match/unsure; statistics and provenance persist. End-to-end review of 20 pairs writes user/time/model/reason, the next training run consumes the labels, and predictions or documented training inputs reflect them. Restart preserves the queue and labels. | Pending | — |
| ZR-8 | Versioned Genie instructions and ten reference questions are deployed over gold tables. The app uses on-behalf-of-user auth; all ten queries have the expected tables/aggregations and correct fixture results. The panel disappears when `paid_features.genie` is off. Prove the Conversation API from the deployed app. **If the Conversation API does not answer for the app on behalf of the user on this workspace (see ENV), the phase parks with that finding — it does not loop.** | Pending | — |
| ZR-9 | Bundle runs on explicitly selected FEVM classic compute with the same engine and passing suite. Each FEBRL4 variant is within 0.01 absolute F1 of local. PHOTON versus STANDARD comparison reports wall time, DBUs and operator fallbacks; prove classic materialization behavior and final cluster termination. | Parked at ENV | Classic Jobs submission explicitly rejected: “Only serverless compute is supported in the workspace.” [Finding](experiments/classic-capability.json). No cluster created. Classic capability must be enabled on this selected workspace; do not substitute profiles. |

The 60-second gate belongs to the **local FEBRL4 reproduction**, not FEVM provisioning or startup.
Record remote startup and execution time separately. Historical prototype timing is not a passing
measurement for the new code. No phase is waived or threshold lowered to obtain a green result.

## § 4 — Implementation order and experiment loop

1. Start ENV resolution and ZR-1. Seed the engine from `spec/bench/proto_spark_native.py`, correcting
   its masked-overlap approximation into the stated IDF-weighted score, explicit candidate budgets,
   cardinality policy, deterministic tie-breaks and startup-inclusive timing. Build a separate
   experiment runner and a read-only `verify_zr.sh` for phases 1–9.
2. Once ZR-1 works, run a small FEVM serverless canary to test native expressions, materialization
   and model fit/score/save/reload. This is early platform evidence, not completion of ZR-6.
3. Implement ZR-2 and the ZR-3 harness, and add ZR-5 tracking early so FEVM experiments are logged.
   Establish frozen baselines and then compare method families, prioritizing the first failed gate.
4. Implement ZR-4 identities and ZR-6 orchestration. Exercise changes, deletes, late arrivals,
   quarantine, retries and fresh-session model loading. Complete the scale ladder and ZR-3 reports.
5. Complete the APX labelling feedback loop (ZR-7), then Genie over stable gold tables (ZR-8).
   Probe their FEVM availability earlier so an access issue is discovered before UI work depends on it.
6. Complete classic/Photon measurements (ZR-9). Re-run affected integration gates on the final
   source/configuration and reconcile the evidence ledger before declaring the campaign complete.

For each iteration:

1. Read this ledger and the latest results. Pick one unmet gate and state a falsifiable hypothesis,
   the baseline, dataset/split, primary metric, changed factors and the bounded run plan.
2. Make the smallest useful implementation or configuration change. Run relevant local checks;
   use the same engine code on FEVM. Keep experiments reproducible from a saved configuration.
3. Submit the experiment, monitor through terminal state, collect outputs and perform owned-resource
   cleanup on success, failure and cancellation. A submitted run is not a completed experiment.
4. Compare against the predeclared validation criteria. Diagnose candidate loss, scoring errors,
   cardinality effects and clustering errors separately. Retain negative results and failures.
5. Promote a method/model only when its gates pass. Update the phase ledger with evidence, record
   the next hypothesis, and continue. Do not ask for routine confirmation between in-scope iterations.

A failed score calls for diagnosis and a changed experiment. Retry a transient infrastructure failure
at most twice; repeated identical failures require a different approach or a precise dependency report.
Plateaus are not success: inspect error slices or method assumptions before launching another sweep.

## § 5 — Evaluation contract

- **Corpora:** FEBRL4 original and half-unmatched (all fields, SSN hidden, and the SSN+DOB-hidden
  diagnostic); FEBRL3; BPID; Abt-Buy; Amazon-Google; Walmart-Amazon; DBLP-ACM;
  Splink `historical_50k`; Leipzig Affiliations; and a seeded synthetic 1,000,000-record scale case.
  Track source, licence, checksum, preprocessing, ground truth and split manifest for each.
- **Methods:** compare `gram_topk`, `learned_blocker`, `minhash_lsh`, `field_blocks` and `union`
  at equal candidate-pair budgets; Levenshtein/Jaro-Winkler/both; the native multi-token families
  and optional affine gap; embeddings on/off; GBT/logistic regression/random forest; supported
  cardinality policies; and all four clustering methods. Respect corpus cardinality and runtime
  compatibility. Levenshtein remains the specified default unless a recorded decision changes it.
  Jaro-Winkler stays a UDF-only optional feature (never a default path, never Photon) until Spark 4.3
  ships the built-in (`tools/spark43_watch.py` tracks the release); compare it where present, but its
  absence from the accelerated path is expected, not a gap.
- **Baselines:** always include nearest-neighbour alone and an appropriate simple thresholded
  baseline. Re-measure Splink in an isolated benchmark environment where specified. Historical
  Zingg and published figures must show their provenance and comparability caveats.
- **Splits:** choose methods, features, thresholds, label policies and defaults on validation only.
  Freeze canonical pair IDs and remove exact/reversed duplicates across splits; account explicitly
  for conflicting labels and shared records. Use entity/anchor-disjoint evaluation where truth
  permits; distinguish it from any official benchmark split rather than conflating their scores.
- **Holdout discipline:** the old prototype datasets have already informed development. Add a
  predeclared, unexposed confirmation split/seed for final acceptance. Freeze the selected model
  and decision policy before scoring it. If test feedback drives a later change, label that test
  as development evidence and create a new independently held-out confirmation set. Never cycle
  through seeds to find a passing result.
- **Metrics:** precision, recall, F1, confusion counts, candidate recall@k and pair budget; B-cubed
  for clustering; missingness/typo/Unicode/multi-valued-field error slices; startup and execution
  time, throughput, shuffle/skew, model size and resource cost. Report 95% paired bootstrap
  intervals, resampling by entity/anchor where applicable. Specify the seed and timing boundaries.
- **Defaults:** document the validation selection rule and corpus weighting before comparison.
  Prefer the cheaper/simpler choice when measured quality is indistinguishable. Do not replace
  an end-to-end acceptance gate with a proxy metric or claim superiority from incomparable splits.
- **LLM labels:** keep the provider optional and off by default; verify its contract with cached
  public judgments before live calls. Live experiments require an available provider and bounded
  usage, run outside UDFs, and record requests/tokens/cost including retries and stacked requests.
  Cached labels must not leak evaluation truth into training or demonstrations.

Scale progressively: small canary → 10,000 → 100,000 → 1,000,000 synthetic records. Measure
candidate recall and join cardinality **before** top-k, including common-token and hot-key cases;
IDF weighting or top-k alone does not bound the preceding join. Enforce explicit candidate and
resource budgets, persist intermediate state where required, and demonstrate recovery from an
interrupted run without duplicate published links or identity events. Publish measured limits;
the brief does not establish a throughput/$ target or require 10-million-record certification.

## § 6 — Evidence and verifiers

Create these artifacts as the corresponding work lands; the paths below are planned, not existing
proof of capability. New engine reports live at repo-root **`bench/`**; the historical harness and its
`cache/` stay at **`spec/bench/`** and are not moved — the new harness *reuses* `spec/bench/cache/` so
LLM reruns cost nothing. Commit the evidence spine (`experiments/runs.jsonl`, each
`manifest.json`, `experiments/ENVIRONMENT.md`, the `bench/*.md` reports); gitignore the bulk per-run
artifacts (predictions, stdout/stderr, query profiles) — see the `.gitignore` stanza below.

- `experiments/runs.jsonl`: append-only run ledger, including failures, cancellations and negative results.
- `experiments/<run-id>/manifest.json`: hypothesis, phase, exact command, source commit plus any patch
  digest, dependency versions, runtime, selected workspace/resource IDs, config, corpus/split/label
  digests, seeds, budgets, model/run IDs and timestamps. Never include tokens or credentials.
- `experiments/<run-id>/`: metrics, predictions or durable artifact references with checksums,
  stdout/stderr, query profiles, resource/cost observations and cleanup status. Preserve enough
  evidence outside the FEVM workspace to reproduce results after the deployment expires.
- `bench/BENCHMARKS.md`, `bench/METHODS.md`, `bench/ABLATION.md`, `bench/SCALE.md`,
  `bench/PHOTON.md` and `bench/PHOTON_CLASSIC.md`: reports backed by run IDs and raw measurements.
- `experiments/ENVIRONMENT.md`: selected execution context, capability results and resource inventory.
- `ZR_CLAUDE_RESUME.txt`: brief-defined resume note; reference this ledger rather than maintaining
  conflicting completion states. Include the first eligible task and any unresolved dependency.

MLflow is the model system of record; Delta is the remote data system of record. Save the complete
model contract, not only the estimator. Attribute DBUs to campaign resources and time windows;
label estimates separately from observed billing. Delayed or inaccessible billing remains missing
evidence, never zero cost; retain the run IDs needed for later reconciliation.

`bash verify_zr.sh N` must exit 0 only when phase N's checks and evidence pass for the relevant
source/configuration. It must not deploy, train, label, write tables or manufacture its evidence.
Missing implementations, skipped tests, stale/incompatible artifacts and incomplete remote runs
must produce a nonzero result. Experiment execution and evidence capture belong to the runner.
After changes, rerun the affected gates and their dependants; reuse still-applicable evidence.

## § 7 — Resource lifecycle and stop conditions

Use one active experiment initially, bounded job timeouts, and the smallest policy-compatible
compute for the dataset. Configure classic auto-termination at 10 minutes where policy permits,
and terminate owned classic compute explicitly when a run ends. Auto-stop settings supplement
explicit cleanup. Record a finite sweep size and runtime/cost ceiling before every sweep; stop
at the limit and use the findings to plan the next iteration.

**Campaign-level boundaries** (autonomous execution must not exceed these without an explicit
Laurent go-ahead): quota/spend-ceiling discovery was waived by Laurent on 2026-09-19 because this is a dev workspace;
finite run timeouts, one active remote experiment and immediate cleanup still apply. Retain a per-phase cap of **8 experiment iterations before escalating** — if a gate
is still red after eight iterations, stop sweeping, write the diagnosis and the blocking hypothesis to
the ledger, and surface it rather than continuing. Plateaus and repeated identical failures escalate
early regardless of the count.

Tag/inventory campaign resources. Stop warehouses and apps started for experiments after evidence
capture; verify they can restart for subsequent tests. Stop only resources owned by the campaign
or explicitly assigned to it. Never shut down shared compute or delete unrelated data. Disable
predictive optimization only on the campaign schema when its config switch is false. Preserve
models, labels and durable evidence before removing owned scratch data. Do not enable additional
always-on services to bypass an experimental limit.

Continue autonomous work within the selected scope and recorded limits. If credentials, workspace
choice, quota, required permissions, unavailable capabilities or a material budget/scope expansion
prevent the next step, record the exact failed check and requested input. Continue independent
eligible work; do not repeatedly run an unsupported operation or silently choose another profile.
An unavailable required feature leaves the campaign incomplete until resolved or explicitly
removed from the target by Laurent.

**Finish line:** ENV and all nine ZR phases pass, the reports link to reproducible results, the
final app-to-label-to-training-to-gold-to-Genie flow has been exercised on FEVM, both remote runtime
targets satisfy parity, and owned compute is stopped/terminated with evidence preserved. Report
the delivered feature level, quality/cost measurements and any measured limitations. Do not keep
expanding the feature target once these requirements pass.

## § 8 — Current handoff

- `fevm-gdpr2` explicitly reconfirmed in this conversation; OAuth refreshed and authenticated.
- ZR-1 now has an installable engine, config, CLI, quality quarantine, corrected IDF candidates,
  pre-join budgets, three estimators, cardinality policies, capability materialization and read-only
  phase verifier. Expanded classic and Connect suites passed the same 71 checks each with no skips;
  source `66f76bd952fb` passes `bash verify_zr.sh 1`.
- Offline synthetic CLI passed under OS-enforced external egress denial: 6 links, 1 quarantine.
  Full original FEBRL4 development smoke completed; this is not ZR-3 holdout evidence.
- Owned schema/volume: `gdpr2_catalog.lakematch_20260919` / `.artifacts`. Remote metadata lists
  classic policies, Apps, Genie and pipelines. Listing is not execution proof.
- First classic-create request timed out at 90 seconds, with empty cluster inventory afterward;
  the bounded retry also timed out at 240 seconds, and inventory was empty again. The distinct Job Compute probe then returned “Only serverless compute is supported in the workspace.” ZR-9 is parked on this confirmed capability limit; serverless/local work continues.
- The user waived quota/expiry as prerequisites (“FEVM are dev workspace so do not worry about that”).
  Resource/time bounds and eight experiment iterations per phase remain. ZR-3 retrieval comparison iteration 1 is declared in `bench/METHOD_PLAN.md`; environment and verification attempts are individually retained in the run ledger.
- At checkpoint 6f859f4, ZR-2 completed iteration 5 (unchanged integration verification repeat): all field types, individual family removals, optional UDFs and
  offline embeddings are measured on the four required corpora. Validation native-all F1: FEBRL4 1.000,
  BPID 0.757, Abt-Buy 0.639, Leipzig 0.939; these are not confirmation scores. Embeddings stay off by
  default because both paired improvement intervals include zero. Failures remain in the run ledger.
- At checkpoint 6f859f4, ZR-5 passed: models-from-code artifact, signature, label/IDF snapshots, evaluation and CLI acceptance;
  FEVM run `429596527159022` resolves champion to UC version 2 with fresh-task prediction equivalence.
- Current ZR-3 work: learned blocking, field blocks, MinHash and union are integrated with persisted fitted state and MLflow artifacts. All four offline CLI train/reload checks pass (runs `20260919T234436Z-candidate-cli-field_blocks-3d472f`, `20260919T234508Z-candidate-cli-learned_blocker-a5441d`, `20260919T234541Z-candidate-cli-minhash_lsh-d5222c`, `20260919T234615Z-candidate-cli-union-f4a635`). The earlier field-block CLI cleanup failure is retained. Runner cleanup now verifies natural process-group exit after an EPERM race.
- Independent preparation: public FEBRL3 (5,000 rows/2,000 entities) and historical_50k (50,578 rows/5,156 entities) are frozen; Splink 4.0.16 has a separate pinned environment. Cluster metrics and bootstrap checks pass. Seven targeted Spark clustering/identity tests pass after an observed cache-lineage heap failure was fixed with owned-table round boundaries. The complete classic and Connect suites each passed the same 98 tests with no skips. CLI integration remains pending. [Plan](bench/CLUSTER_PLAN.md).
- ZR-3 classifier iteration 2 completed all nine corpus configurations / 81 models with no failed runs. Seven-corpus macro validation F1 is 0.8201 for Levenshtein/GBT, 0.8008 for Levenshtein/logistic regression and 0.8003 for Levenshtein/random forest; both alternatives have negative paired intervals. Jaro-Winkler additions show no clear paired gain. The selected estimator/string stage is recorded in [METHODS.md](bench/METHODS.md) and [selection.json](bench/selection.json). No confirmation scoring or model promotion occurred.
- ZR-4 baseline preparation exposed two failures: the launcher dereferenced the isolated interpreter symlink, then a shared Splink SQL cache returned training records from a new Linker. Both failed runs are retained. The launcher now preserves the virtual environment, and validation uses a fresh DuckDB connection/API plus an endpoint audit before metrics. Count these as iterations 1 and 2. Iteration 3 passed both Splink baselines and the native FEBRL3 comparison, but historical_50k connected components failed the 30-round cap. Iteration 4 adds parent-label shortcuts and tests disconnected long paths before repeating both native corpora with unchanged budgets; see [CLUSTER_FIX_PLAN.md](bench/CLUSTER_FIX_PLAN.md). Iteration 4 passed eight regression checks but the full FEBRL3 comparison hit a broadcast-memory error during center clustering. Iteration 5 additionally truncates the validated ID-only input relation before graph processing; budgets are unchanged. Incremental identity verification is now iteration 6.
- Next eligible work: ZR-3 retrieval iteration 1 has complete measured results; its compatibility checks require a final refresh after the additive runtime truncation option. Compact-feature iteration 3 completed all nine runs with no failures. IDF-only macro F1 is 0.8145 vs all-native 0.8201; paired interval [-0.0126, +0.0014] includes zero, with weighted feature/fit/score time 3.87s vs 7.49s. Continue the predeclared retrieval/F1 iteration 4 and latency harness,
  using the [predeclared protocol](bench/PROTOCOL.md). Classic capability remains an external ENV
  dependency, now confirmed serverless-only by the Jobs API. ZR-3/4/6/7/8 remain pending and ZR-9 is parked on the confirmed serverless-only workspace restriction. See [environment](experiments/ENVIRONMENT.md),
  [engine observations](bench/ENGINE.md), and [run ledger](experiments/runs.jsonl).
- APX maintenance prerequisite: the public repository is not archived, but its last push remains 2026-04-07 and latest release is v0.3.8 from 2026-02-26. The installed CLI is 0.3.8. Active maintenance is unconfirmed; the installed APX skill labels it legacy. This does not authorize changing the brief to AppKit. A built scaffold size check remains pending. [Evidence](experiments/apx-prerequisites.json).
- Resume: `$goal /Users/laurent.fabre/Projects/Claude/lakematch/goal.md`.

The updated-engine STANDARD canary succeeded as remote run `667945925462279` (176s setup,
268s task execution); all three expected links and equivalent reloaded predictions were observed.
Final campaign resource inventory is [here](experiments/final-resource-state.json). Billing and
query-profile evidence, pipeline execution and delegated Genie remain unproven. UC registration
and fresh-task composite-model loading now pass ZR-5.

### Continuation — 2026-09-20

- Both ZR-4 identity runs passed and were independently replayed: `20260920T012627Z-identity-febrl3-7c613f` and `20260920T012807Z-identity-historical_50k-03f0a3`. Each mutation has floor(1%) additions, actual profile changes and deletions; 10 each on FEBRL3, 100 each on the 10,082-record historical validation partition. No confirmation scores.
- ZR-3 iteration 4 failed before its first fit with Java heap exhaustion in query-plan rendering (`20260920T013426Z-linkage-all-3f9753`). Iteration 5 truncates IDF-enriched input, candidate and feature relations via owned tables, with unchanged memory/pair/time limits. See [LINKAGE_PLAN.md](bench/LINKAGE_PLAN.md).
- Local publication now uses immutable Parquet attempts and a transactional SQLite commit catalog. Two pure recovery/idempotence tests pass. A normal `cluster` CLI command is implemented with an explicit immutable model and pair-metadata declaration; Spark/CLI acceptance is pending. Remote publication still needs the Delta adapter.

- ZR-3 iteration 5 completed all three linkage configurations. Field blocks and gram top-k reached validation F1 1.000 on both required FEBRL variants; field blocks reached 0.999 on the diagnostic. Six-corpus candidate/scoring iteration 6 is predeclared in [CANDIDATE_PAIRS_PLAN.md](bench/CANDIDATE_PAIRS_PLAN.md) and now running sequentially.
- ZR-4 iteration 7 normal CLI passed (`20260920T014513Z-cluster-cli-8db05b`), with independently checked equivalent crosswalks/journals, exact retry reuse and no historical rewind. Three process-recovery checks passed (`20260920T014513Z-publication-recovery-tests-22f9d1`). The verifier still rejects the below-measured shipped round bound.
- APX baseline scaffold built successfully: 169,758 bytes total, largest deployment file 169,627 bytes; saved under `app/` with separate upstream license/notice. Maintenance remains unconfirmed, so no arbitration UI or remote app deployment yet.

- ZR-3 iteration 6 completed all six supplied-pair corpora. MinHash is the only complete feasible candidate, macro validation F1 0.6942 [0.6778, 0.7098]. Gram/union exceed BPID’s 50-million retained-join limit; field/learned retrieval leaves only one labelled training class on Affiliations. No statistical-superiority claim follows from this feasibility selection. [Candidates](bench/CANDIDATES.md).
- Iteration 7 is predeclared in [FINAL_PLAN.md](bench/FINAL_PLAN.md): immutable eight-model freeze, two fresh normal-CLI FEBRL confirmations, six supplied-pair holdouts, and a progressive 1k/10k/100k/1m synthetic scale ladder. Four focused selection/protocol/event-metric tests pass. Defaults and model aliases remain unpromoted. MinHash currently uses MLlib job code, which needs explicit compatibility work before the required SDP candidate flow.

- Frozen confirmation is now scored, with no tuning: all-field FEBRL F1 0.9888776542 [0.9815, 0.9950] at 29.1933s; SSN-hidden F1 0.9868287741 [0.9793, 0.9932] at 27.3046s. Both pass the startup-inclusive CLI quality/latency gates. All misses are retrieval losses, zero false-positive links. Six supplied-pair holdouts also completed; range 0.2639 Affiliations to 0.9875 DBLP-ACM. Exact model snapshots archived under data/frozen_models with hashes in bench/frozen_artifacts.json. [Benchmark report](bench/BENCHMARKS.md).

- ZR-6 iteration 1 is predeclared in [SERVERLESS_ADAPTER_PLAN.md](bench/SERVERLESS_ADAPTER_PLAN.md). Optional lazy DQX row-rule and exported MinHash/GBT SQL adapters are prepared, not yet exercised. Both serverless bundle targets pass strict CLI validation on fevm-gdpr2; no deployment/remote compute was started. [Validation receipt](experiments/bundle-validation.json). The bundle currently covers frozen inference only; training/clustering tasks, remote publication, app/Genie behavior and Photon evidence remain pending.

- ZR-3 iteration 7 ended: million-record run `20260920T022943Z-scale-1000000-f0a3d1` failed with Java heap exhaustion while materializing candidates. It measured 8,450,667,332 prospective join rows, 20,326,239 retained join rows and 471,655 candidate pairs before failure. No million-tier recall/F1/throughput claim. Spark cleanup failed after JVM failure; the runner verified process-group termination. No budget increase or retry. [Scale](bench/SCALE.md).

- ZR-6 adapter iteration 2 passed both variants (exact keys/candidates, probabilities within 1e-12). Remote iteration 3 deployed job `489495267612522` and pipeline `887f3271-3247-4082-82a9-9b62fb89e135`; run `954247814662959` passed preparation but failed SDP feature analysis because a global feature-stage guard rejected DQX. Cancelled its automatic retry; job terminal and pipeline IDLE are verified. Iteration 4 corrects quality dispatch and the misplaced guard, then repeats local parity before redeployment. [Adapter plan](bench/SERVERLESS_ADAPTER_PLAN.md).
