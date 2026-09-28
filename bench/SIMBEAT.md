# String similarity benchmark — SIM-3

## What / why

Compare seven shortlisted Spark SQL feature families with Levenshtein and the Jaro–Winkler UDF, keeping the rest of the matching pipeline fixed. Select on VALID, then confirm the frozen choice once on TEST.

> Verdict: **`not_beaten`**. Chosen additions: **padded_bigram_dice, qgram_count_cosine**. This is a benchmark-specific result, not a universal ranking of string measures.

## Contents

- [Protocol](#protocol)
- [Validation](#validation)
- [Forward selection](#forward-selection)
- [TEST confirmation](#test-confirmation)
- [Verdict](#verdict)
- [Reproduce and audit](#reproduce-and-audit)
- [Limitations](#limitations)
- [License](#license)

---

## Protocol

| Setting | Frozen choice |
|---|---|
| Candidate generation | Existing `gram_topk`; k=5 for FEBRL4, k=11 then remove self and canonicalize for Leipzig |
| Pair corpora | BPID and Abt-Buy retain their fixed loader splits and supplied labelled pairs |
| Model | Spark MLlib GBT, 60 iterations, depth 3, seed 0; same existing non-edit families in every variant |
| Fit / calibration | 80/20 of TRAIN by hash; thresholds maximize pair F1 on calibration, grid 0.05–0.95 step 0.01 |
| Outer split | FEBRL4 left-ID hash 60/20/20; Leipzig canonical pair hash 60/20/20 |
| Selection | Greedy forward addition by strictly positive, unrounded mean VALID F1 gain; shortlist rank breaks ties |
| Confirmation | Saved chosen and JW models and thresholds, no refit; selection JSON locked before TEST scoring |
| Intervals | 1,000 percentile bootstrap replicates; pair units except FEBRL4 left-record units |
| TEST difference | Paired resampling within each corpus, then equal-weight mean of four corpus F1 differences |
| Record features | Default cached local embedding model and transductive IDF; record UDFs pinned before pair comparison |
| New-feature limits | 512 characters, 128 distinct tokens; checked on normalized inputs; no truncation |
| Existing Monge–Elkan | Original 30-token cap retained |

**Corrections to the historical `methods.py` measurements.** The old linkage fit/calibration hash was correlated with the outer hash, producing approximately 5/6 versus 1/6 within TRAIN. This run uses an independently salted inner hash for FEBRL4 and Leipzig. Leipzig now uses the documented pair hash. Canonical candidate orientation is deterministic. Jaro–Winkler now covers every field that receives Levenshtein, including Abt-Buy titles: the old JW-only Abt-Buy row contained no JW features. All three baselines are remeasured here; historical scores are not directly comparable.

FEBRL4 applies the existing greedy one-to-one decision and counts truth links missed by blocking; its evaluation units include every held-out left record, even without candidates. BPID, Abt-Buy and Leipzig use unrestricted pair classification, matching the actual ZR-3a similarity evaluation. The old harness's prose suggesting one-to-one Abt-Buy scoring did not describe that implementation. Leipzig F1 is conditional on its candidate pairs; it is not cluster F1 or full all-pairs recall.

TEST files and all record strings are parsed by the existing loaders during preprocessing. No TEST score or label-driven statistic is used for selection. TEST comparison vectors and predictions are evaluated only after the selection lock. The saved confirmation is reused on resume.

### Development split counts

| Corpus | Fit pairs / positives | Calibration pairs / positives | VALID pairs / positives |
|---|---:|---:|---:|
| febrl4_half_unmatched | 12200 / 1204 | 3125 / 303 | 4745 / 486 |
| bpid | 5667 / 2431 | 1352 / 603 | 991 / 433 |
| abt_buy | 4588 / 496 | 1128 / 118 | 1894 / 204 |
| leipzig_affiliations | 7466 / 4140 | 1850 / 1042 | 3034 / 1754 |

---

## Validation

F1 [95% percentile interval]. Means and selection use full precision in the JSON. Field eligibility follows SIM-2: a family with no applicable fields repeats the baseline (for example, OSA on Leipzig organisation fields).

| Variant | FEBRL4 | BPID | Abt-Buy | Leipzig | Mean | Pair plan UDF-free |
|---|---:|---:|---:|---:|---:|---|
| levenshtein | 1.0000 [1.0000, 1.0000] | 0.8097 [0.7825, 0.8370] | 0.6533 [0.5987, 0.7101] | 0.8699 [0.8581, 0.8809] | 0.8332 | yes |
| jaro_winkler | 1.0000 [1.0000, 1.0000] | 0.8038 [0.7765, 0.8296] | 0.6947 [0.6441, 0.7493] | 0.8673 [0.8548, 0.8781] | 0.8414 | no (JW UDF) |
| both | 1.0000 [1.0000, 1.0000] | 0.8091 [0.7818, 0.8355] | 0.6935 [0.6422, 0.7461] | 0.8686 [0.8564, 0.8796] | 0.8428 | no (JW UDF) |
| levenshtein + token_sort_lev | 1.0000 [1.0000, 1.0000] | 0.8084 [0.7806, 0.8355] | 0.6888 [0.6370, 0.7397] | 0.8679 [0.8557, 0.8789] | 0.8413 | yes |
| levenshtein + padded_bigram_dice | 1.0000 [1.0000, 1.0000] | 0.8186 [0.7893, 0.8462] | 0.6979 [0.6473, 0.7476] | 0.8699 [0.8580, 0.8806] | 0.8466 | yes |
| levenshtein + weighted_jaccard | 1.0000 [1.0000, 1.0000] | 0.8018 [0.7734, 0.8294] | 0.6845 [0.6305, 0.7366] | 0.8660 [0.8536, 0.8776] | 0.8381 | yes |
| levenshtein + qgram_count_cosine | 1.0000 [1.0000, 1.0000] | 0.7971 [0.7699, 0.8236] | 0.6948 [0.6467, 0.7464] | 0.8701 [0.8579, 0.8808] | 0.8405 | yes |
| levenshtein + soft_tfidf_lev | 1.0000 [1.0000, 1.0000] | 0.8029 [0.7750, 0.8288] | 0.6907 [0.6412, 0.7441] | 0.8669 [0.8543, 0.8783] | 0.8401 | yes |
| levenshtein + osa | 1.0000 [1.0000, 1.0000] | 0.8129 [0.7845, 0.8401] | 0.6849 [0.6341, 0.7369] | 0.8699 [0.8581, 0.8809] | 0.8419 | yes |
| levenshtein + lcs_indel | 1.0000 [1.0000, 1.0000] | 0.7977 [0.7670, 0.8238] | 0.6900 [0.6394, 0.7429] | 0.8710 [0.8588, 0.8817] | 0.8397 | yes |
| chosen | 1.0000 [1.0000, 1.0000] | 0.8204 [0.7907, 0.8478] | 0.7095 [0.6608, 0.7598] | 0.8661 [0.8531, 0.8770] | 0.8490 | yes |

<details><summary>All additional combination measurements</summary>

| Variant | FEBRL4 | BPID | Abt-Buy | Leipzig | Mean | Pair plan UDF-free |
|---|---:|---:|---:|---:|---:|---|
| levenshtein + token_sort_lev + padded_bigram_dice | 1.0000 [1.0000, 1.0000] | 0.8179 [0.7893, 0.8443] | 0.6827 [0.6315, 0.7349] | 0.8675 [0.8552, 0.8783] | 0.8420 | yes |
| levenshtein + padded_bigram_dice + weighted_jaccard | 1.0000 [1.0000, 1.0000] | 0.8159 [0.7889, 0.8425] | 0.7035 [0.6536, 0.7543] | 0.8685 [0.8562, 0.8795] | 0.8470 | yes |
| levenshtein + padded_bigram_dice + qgram_count_cosine | 1.0000 [1.0000, 1.0000] | 0.8204 [0.7907, 0.8478] | 0.7095 [0.6608, 0.7598] | 0.8661 [0.8531, 0.8770] | 0.8490 | yes |
| levenshtein + padded_bigram_dice + soft_tfidf_lev | 1.0000 [1.0000, 1.0000] | 0.8151 [0.7853, 0.8428] | 0.6791 [0.6282, 0.7343] | 0.8652 [0.8525, 0.8762] | 0.8399 | yes |
| levenshtein + padded_bigram_dice + osa | 1.0000 [1.0000, 1.0000] | 0.8147 [0.7846, 0.8416] | 0.6979 [0.6473, 0.7476] | 0.8699 [0.8580, 0.8806] | 0.8456 | yes |
| levenshtein + padded_bigram_dice + lcs_indel | 1.0000 [1.0000, 1.0000] | 0.8153 [0.7863, 0.8429] | 0.6758 [0.6223, 0.7282] | 0.8700 [0.8584, 0.8810] | 0.8403 | yes |
| levenshtein + token_sort_lev + padded_bigram_dice + qgram_count_cosine | 1.0000 [1.0000, 1.0000] | 0.8216 [0.7931, 0.8490] | 0.6791 [0.6279, 0.7328] | 0.8695 [0.8570, 0.8808] | 0.8426 | yes |
| levenshtein + padded_bigram_dice + weighted_jaccard + qgram_count_cosine | 1.0000 [1.0000, 1.0000] | 0.8191 [0.7895, 0.8477] | 0.6593 [0.6042, 0.7154] | 0.8690 [0.8564, 0.8802] | 0.8369 | yes |
| levenshtein + padded_bigram_dice + qgram_count_cosine + soft_tfidf_lev | 1.0000 [1.0000, 1.0000] | 0.8203 [0.7907, 0.8476] | 0.6796 [0.6269, 0.7337] | 0.8700 [0.8572, 0.8809] | 0.8425 | yes |
| levenshtein + padded_bigram_dice + qgram_count_cosine + osa | 1.0000 [1.0000, 1.0000] | 0.8145 [0.7859, 0.8432] | 0.7095 [0.6608, 0.7598] | 0.8661 [0.8531, 0.8770] | 0.8475 | yes |
| levenshtein + padded_bigram_dice + qgram_count_cosine + lcs_indel | 1.0000 [1.0000, 1.0000] | 0.8189 [0.7896, 0.8459] | 0.6990 [0.6485, 0.7472] | 0.8700 [0.8581, 0.8812] | 0.8470 | yes |

</details>

---

## Forward selection

Every remaining family is tested at each round. Combinations are canonicalized in shortlist order. The trace records rejected additions as well as accepted ones; this is greedy search, not exhaustive subset search.

| Round | Starting variant | Best addition result | Mean VALID gain | Accepted |
|---:|---|---|---:|---|
| 1 | levenshtein | levenshtein + padded_bigram_dice | +0.01337135 | True |
| 2 | levenshtein + padded_bigram_dice | levenshtein + padded_bigram_dice + qgram_count_cosine | +0.00241135 | True |
| 3 | levenshtein + padded_bigram_dice + qgram_count_cosine | levenshtein + padded_bigram_dice + qgram_count_cosine + osa | -0.00147739 | False |

---

## TEST confirmation

| Corpus | Chosen F1 [CI] | Jaro–Winkler F1 [CI] |
|---|---:|---:|
| febrl4_half_unmatched | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] |
| bpid | 0.8306 [0.8091, 0.8477] | 0.8351 [0.8150, 0.8524] |
| abt_buy | 0.6875 [0.6313, 0.7395] | 0.7128 [0.6626, 0.7621] |
| leipzig_affiliations | 0.8656 [0.8538, 0.8768] | 0.8604 [0.8479, 0.8726] |
| Equal-weight mean | 0.845924 | 0.852063 |

Chosen − JW mean F1: **-0.006139**, paired 95% CI **[-0.013689, +0.001219]**.

---

## Verdict

The supplied judge requires all four conditions below; statistical significance is reported through the interval but is not an additional judge condition.

| Condition | Passed |
|---|---|
| `abt_buy_not_below_jw` | True |
| `all_within_0_005_of_lev` | True |
| `test_mean_not_below_jw` | False |
| `valid_mean_improves_jw` | True |

Recomputed verdict: **`not_beaten`**. SIM-4 adoption is not applicable; the new families remain opt-in.

---

## Reproduce and audit

```bash
cd ~/Projects/Pro/lakematch
source scripts/env.sh
python bench/simbeat.py run
python bench/simbeat.py audit
python bench/simbeat.py render
cd ~/Projects/Personal
bash goals/verify_simbeat.sh 3
```

`run` needs the cached corpora and embedding model and makes no download requests. It resumes only an identical source/data/config/version manifest. For an independent complete rerun, use a fresh `--work-dir data/runs/simbeat-reproduction`; do not use repeated TEST runs to revise the choice. Results, per-unit confusion counts, thresholds, feature columns, plan hashes, input hashes, model hashes and the selection lock are in [results/simbeat.json](results/simbeat.json). Local feature Parquet, model directories, physical plan text and prediction evidence remain under `data/runs/simbeat/` (gitignored). The audit recomputes greedy choices, stopping, F1, intervals, paired TEST difference and verdict. The shell judge independently recomputes the four verdict conditions.

Spark **4.1.3**; embedding `minishlab/potion-base-32M` at `1e5a03f8eeb2c98b928fbbd846f22f816360919f`. Models use eight deterministic ID partitions sorted within each partition; numerical reproducibility across different Spark/JVM versions is not claimed.

---

## Limitations

- VALID is reused for several comparisons; its bootstrap intervals are descriptive, not corrected for selection.
- Abt-Buy and Leipzig share records across pair splits; they measure pair generalization, not unseen-entity generalization. Their pair bootstrap does not model dependence between pairs sharing an entity.
- IDF and record embeddings use all record strings, including held-out records, without outcome labels.
- Pair-plan purity excludes the precomputed embedding UDF and MLlib model scoring. It proves the string comparison path only; it is not a Photon execution claim.
- The larger DP limits cover this benchmark but OSA/LCS repeatedly copy DP row arrays and can be costly on long text (beyond the usual O(n*m) cell count).
- All four corpora carry equal weight regardless of size; conclusions depend on the fixed candidate, model and threshold protocol.

---

## License

Benchmark code follows the repository license. Dataset terms and provenance are documented in [corpora.py](corpora.py); cached data and model weights retain their original licenses.
