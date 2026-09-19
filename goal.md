# Goal: bring lakematch to its specified feature level through FEVM experiments

Created: 2026-09-19. Status: in progress; ZR-1 passed against source 87bb4c9923c7; serverless engine canary passed; STANDARD serverless canary passed; ZR-9 parked at ENV.

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
| ENV | Explicit FEVM target(s), capability report, isolated resources and bounded run configuration are recorded. | In progress | [Environment](experiments/ENVIRONMENT.md); auth and owned schema/volume work; classic-create timeout under investigation; serverless native engine/model canary passes; delegated Genie still untested. |
| ZR-1 | Installable package, YAML config and CLI; native quality checks split valid/quarantined rows with reasons; deterministic candidates/features/matcher/decision produce links. Tests pass on local Spark and local Spark Connect, including all-paid-features-off offline execution. Implement capability-aware materialization and phase verifiers. | Passed | [Engine evidence](bench/ENGINE.md); source `87bb4c9923c7`; 39 tests pass in each mode with no skips; offline and full FEBRL4 CLI, wheel installation/private-repository check pass; `bash verify_zr.sh 1` exits 0. |
| ZR-2 | Feature families cover every configured field type. Default matching plans have no `PythonUDF`, `BatchEvalPython` or `ArrowEvalPython`; optional Jaro-Winkler and affine-gap features are gated. Ablations cover FEBRL4-half-unmatched, BPID, Leipzig Affiliations and Abt-Buy, including local embeddings for organisation/title, accuracy and preprocessing cost. | Pending | — |
| ZR-3 | Reproducible harness runs every brief corpus, compares every required method on validation and ships the documented winners. On held-out FEBRL4-half-unmatched: F1 >= 0.97 with all fields and >= 0.96 with SSN hidden; each local end-to-end run is under 60 seconds including Spark startup. Publish candidate recall, confidence intervals, baselines and cost. Include the scale evidence specified below. | Pending | — |
| ZR-4 | Compare verified merge, connected components, center and star on FEBRL3 and `historical_50k`, reporting pairwise and B-cubed metrics. Demonstrate convergence, unchanged-input stable `mdm_id`, and an exactly reconciled crosswalk/merge/split log after 1% additions, changes and deletions. | Pending | — |
| ZR-5 | Composite MLflow model includes classifier/pipeline, candidate and feature specs/order, config, thresholds and label-set digest, with signature, dataset lineage and evaluation. Local SQLite tracking resolves `runs:/<id>/model` without a registry. FEVM registers in UC, resolves the champion alias to an immutable version, and reloads with equivalent predictions in a fresh session. Respect the runtime model-size limit. | Pending | — |
| ZR-6 | Bundle validates and an actual FEVM serverless run completes. SDP holds candidates, features, scoring and links; training/clustering are tasks. DQX and native quality engines agree on seeded bad rows. Each FEBRL4 variant is within 0.01 absolute F1 of its frozen local reference. Default config and all-paid-features-off config both deploy/run; query profiles support the Photon report. | Pending | — |
| ZR-7 | APX confirmed still maintained and the built bundle is under the Databricks App file-size limit (checked before UI work). APX app runs locally and as a Databricks App. Uncertainty-ordered, keyboard-first review supports match/no-match/unsure; statistics and provenance persist. End-to-end review of 20 pairs writes user/time/model/reason, the next training run consumes the labels, and predictions or documented training inputs reflect them. Restart preserves the queue and labels. | Pending | — |
| ZR-8 | Versioned Genie instructions and ten reference questions are deployed over gold tables. The app uses on-behalf-of-user auth; all ten queries have the expected tables/aggregations and correct fixture results. The panel disappears when `paid_features.genie` is off. Prove the Conversation API from the deployed app. **If the Conversation API does not answer for the app on behalf of the user on this workspace (see ENV), the phase parks with that finding — it does not loop.** | Pending | — |
| ZR-9 | Bundle runs on explicitly selected FEVM classic compute with the same engine and passing suite. Each FEBRL4 variant is within 0.01 absolute F1 of local. PHOTON versus STANDARD comparison reports wall time, DBUs and operator fallbacks; prove classic materialization behavior and final cluster termination. | Parked at ENV | Two create requests timed out (90s/240s), no cluster returned or found afterward. Resolve classic creation before ZR-9; do not substitute workspace. |

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
  phase verifier. Final classic and Connect suites passed the same 39 checks each with no skips;
  source `87bb4c9923c7` passes `bash verify_zr.sh 1`.
- Offline synthetic CLI passed under OS-enforced external egress denial: 6 links, 1 quarantine.
  Full original FEBRL4 development smoke completed; this is not ZR-3 holdout evidence.
- Owned schema/volume: `gdpr2_catalog.lakematch_20260919` / `.artifacts`. Remote metadata lists
  classic policies, Apps, Genie and pipelines. Listing is not execution proof.
- First classic-create request timed out at 90 seconds, with empty cluster inventory afterward;
  the bounded retry also timed out at 240 seconds, and inventory was empty again. ZR-9 is parked pending resolution of classic creation; serverless/local work continues.
- The user waived quota/expiry as prerequisites (“FEVM are dev workspace so do not worry about that”).
  Resource/time bounds and eight experiment iterations per phase remain. No model-selection sweep
  has started; environment and verification attempts are individually retained in the run ledger.
- Next eligible work: ZR-2 feature families and ablations, then the ZR-3 evaluation harness
  with the [predeclared protocol](bench/PROTOCOL.md); classic creation remains an external ENV dependency. ZR-2–8 remain pending and ZR-9 is parked. See [environment](experiments/ENVIRONMENT.md),
  [engine observations](bench/ENGINE.md), and [run ledger](experiments/runs.jsonl).
- Resume: `$goal /Users/laurent.fabre/Projects/Claude/lakematch/goal.md`.

The updated-engine STANDARD canary succeeded as remote run `667945925462279` (176s setup,
268s task execution); all three expected links and equivalent reloaded predictions were observed.
Final campaign resource inventory is [here](experiments/final-resource-state.json). Billing and
query-profile evidence, UC registration, pipeline execution and delegated Genie remain unproven.
