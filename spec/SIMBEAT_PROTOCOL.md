# SIM-3 input isolation

## What / why

`simbeat-v2` separates held-out outcomes from development at the file-access boundary. The historical `simbeat-v1` result remains `not_beaten` and retains its original access qualification. This change does not produce a new benchmark result.

BPID and Abt-Buy mix strings and labels in source records; Leipzig derives labels from a global cluster mapping. An explicit provisioning operation separates those sources before experiment execution. Development then has no reason to open a raw source or sealed outcome file. All record strings remain available for the existing transductive preprocessing.

Contents: [Boundary](#access-boundary) · [Provisioning](#provisioning) · [Execution](#experiment-execution) · [Recovery](#confirmation-and-recovery) · [Verification](#verification) · [Limits](#scope-and-limitations) · [License](#license).

---

## Access boundary

| Phase | Reads | Writes |
|---|---|---|
| Explicit provisioning | Existing nine raw source files, including outcomes | A fresh immutable input bundle, published by directory rename |
| Development manifest | Public bundle metadata and public file hashes; code, environment and embedding identities | Run manifest containing the bundle commitments |
| Preparation | Unlabeled records, unlabeled supplied pair IDs/splits, TRAIN/VALID labels | Prepared records, development pairs/features, unlabeled TEST candidates, VALID-only linkage truth |
| Fit, calibration, selection | Development features, VALID-only truth and saved VALID metrics | Models, VALID metrics and selection lock |
| Fresh confirmation | Frozen selection and models, then one sealed outcome payload per corpus | Bound release, labelled TEST pairs, predictions and confirmation |
| Confirmation resume / audit | Bound releases and saved evidence | Resume may finish confirmation from cached predictions; audit writes nothing |

Development entry points fail if the separated input bundle is absent. They never invoke provisioning or fall back to an eager corpus loader. `evaluate` uses metadata and development caches without rereading record sources. Historical mixed-label caches are read-only for execution.

```text
data/simbeat_inputs/v2/
  manifest.json
  <corpus>/
    records.json        # all record text; supplied pair IDs/splits, no labels
    development.json    # TRAIN/VALID labels or partitioned positive truth
    heldout.json        # TEST outcomes; inaccessible through public readers

data/runs/<new-run>/
  manifest.json
  selection.json
  <corpus>/
    left/  right/
    pairs/  development/
    development_truth.json   # FEBRL4 VALID only
    test_candidates/        # no label column
    heldout_release.json    # created only after selection/model checks
    test_pairs/             # created only after release
    test_truth.json         # FEBRL4 TEST only, after release
    test_predictions.json
    confirmation.json
  result.json
  report.md
```

---

## Provisioning

Provisioning is a separate dataset preparation operation, outside development and selection. It uses the legacy loaders to retain source interpretation and existing IDs, but publishes no global cluster metadata or outcome-derived notes in public records.

| Corpus | Preserved rule |
|---|---|
| BPID | SHA-1 of the complete original JSON line supplies opaque IDs and the 70/10/20 split; this includes the original label bytes in the historical hash input |
| Abt-Buy | Side-specific content IDs, supplied TRAIN/VALID/TEST splits and first-occurrence pair deduplication in that order |
| FEBRL4 | Spark left-ID hash gives 60/20/20 outer partitions; every left unit is retained, including unmatched units |
| Leipzig | Provisioning resolves cluster transitivity, expands canonical positive pairs and splits by the Spark hash of `left_id + "|" + right_id`; cluster IDs are excluded from public records |

The input manifest records raw-source and sealed-file SHA-256 commitments. Development verifies only public bytes; it does not reopen raw or sealed files to recompute those commitments. The published store cannot be overwritten by the provisioning command.

Minimal provisioning command, for a separately authorized future experiment:

```bash
cd ~/Projects/Pro/lakematch
source scripts/env.sh
python bench/simbeat_inputs.py
```

No real corpus provisioning was performed while fixing SIM3-004. Synthetic fixtures exercise the staging path.

---

## Experiment execution

A future experiment requires a fresh work directory and the explicitly provisioned default input bundle:

```bash
cd ~/Projects/Pro/lakematch
source scripts/env.sh
python bench/simbeat.py run --work-dir data/runs/simbeat-v2-new
python bench/simbeat.py audit --work-dir data/runs/simbeat-v2-new \
  --result data/runs/simbeat-v2-new/result.json
```

New run outputs stay inside their work directory. They do not replace `bench/results/simbeat.json` or `bench/SIMBEAT.md`. The default historical run directory continues to verify its completed v1 result without refitting or rescoring. No future experiment is authorized or implied by this documentation.

Candidate generation uses unlabeled records. Candidate partitions are assigned before development truth is joined. Supplied pair corpora expose pair membership without labels. TEST candidate Parquet has no `label` column; development Parquet contains only `fit`, `thr` and `valid` rows. FEBRL4 development truth contains only VALID units and links.

---

## Confirmation and recovery

Fresh confirmation first replays VALID selection, verifies the live manifest, and checks the selected serialized model hashes and feature columns. Only then may `release_labels` open the corpus's sealed outcome file. It checks the committed byte hash and payload schema, then atomically publishes a release bound to the manifest, corpus and selection digest.

A successfully committed release is reused without reopening the sealed source. A crash before the atomic commit may retry the source read; no prediction has been produced at that point. This is one durable release and one frozen prediction confirmation, not an operating-system guarantee that every byte is read only once under arbitrary process failure. Verification necessarily rereads saved evidence.

Predictions retain the atomic provenance envelope introduced for SIM3-002. V2 provenance covers the separated candidate/pair files and the bound release. Audit reconstructs labels from the release, checks them against saved TEST pairs, rejects labelled TEST candidates or TEST partitions in development, and retains all existing model, physical-plan, interval and verdict checks. V1 legacy compatibility is unchanged.

---

## Verification

```bash
cd ~/Projects/Pro/lakematch
source scripts/env.sh
python -m pytest tests/test_simbeat.py tests/test_simbeat_audit.py \
  tests/test_simbeat_resume.py tests/test_simbeat_inputs.py \
  tests/test_simbeat_isolation.py -p no:cacheprovider
cd ~/Projects/Personal
bash goals/verify_simbeat.sh 3
```

Access guards intercept actual file opens and eager loader calls during manifest creation, preparation, evaluation setup and selection. Synthetic release tests check missing or inconsistent locks, changed models, sealed-byte corruption and release reuse. Model fitting and benchmark TEST scoring are forbidden in these tests; tiny Spark sessions exercise partitioning and materialization only.

Historical result/report and all saved run artifacts are checked separately for unchanged SHA-256, size and modification time. The required phase-3 gate continues to audit the recorded v1 result; the access-guard suite establishes the new v2 boundary.

---

## Scope and limitations

- The boundary isolates access to outcomes; it does not make record preprocessing inductive. Record strings remain transductive.
- Abt-Buy and Leipzig still share entities across pair splits. Leipzig development positives can imply other relationships through transitivity. Those statistical properties are unchanged.
- Provisioning is trusted dataset preparation, and public hash commitments are not cryptographic signatures or filesystem permissions. This prevents accidental access by the harness, not deliberate access by a user who owns all files.
- The historical v1 run did parse TEST outcomes during preprocessing. Its artifacts and disclosure are preserved; the v2 implementation does not retroactively change that fact or its negative verdict.

## License

This protocol accompanies the repository's Apache-2.0 code. Existing dataset and model licenses remain applicable.
