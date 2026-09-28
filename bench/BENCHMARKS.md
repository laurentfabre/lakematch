# Benchmarks (ZR-3)

*Generated 2026-09-29T00:04:09 from `bench/results/benchmarks.json` by `lakematch bench --all` (`bench/benchmarks.py`). Machine: arm64 · 16 cores · local[8]. Every row ran end to end on the laptop, one process per corpus; nothing below was typed by hand.*

## Contents

- [Results](#results)
- [Findings](#findings)
- [FEBRL4 thresholds](#febrl4-thresholds)
- [Jev as the only labeller](#jev-as-the-only-labeller)
- [Latency and scale](#latency-and-scale)
- [References](#references)
- [Method choices](#method-choices)
- [Protocol](#protocol)
- [Reproduce](#reproduce)

## Results

Gold labeller (TRAIN labels, threshold on VALID, scored once on TEST). F1 interval: 95 % bootstrap over TEST units. NN = always link the nearest neighbour.

| Corpus | kind | P | R | F1 [95 % CI] | NN baseline F1 | candidate recall@k | wall s (incl. start) | reference to beat or match |
|---|---|---|---|---|---|---|---|---|
| FEBRL4, half the partners removed | linkage | 1.000 | 0.996 | **0.998** [0.995, 1.000] | 0.679 | 1.000 @5 | 22.9 | Zingg 0.841 (perfect labels, all fields); Zingg 0.862 (perfect labels, SSN hidden); Zingg 0.849 (labels from Jev); Splink 0.9996 (measured); Splink SSN hidden 0.9881 (measured) |
| FEBRL4 original | linkage | 1.000 | 1.000 | **1.000** [1.000, 1.000] | 1.000 | 1.000 @5 | 28.1 | Zingg 0.853 (labels from Jev (6 rounds)); Zingg 0.858 (ground-truth labels (6 rounds)); Splink 0.9995 (measured) |
| FEBRL3 (dedupe) | dedupe | 0.996 | 0.999 | **0.998** [0.995, 1.000] | 0.575 | 1.000 @10 | 29.0 | Splink 0.9918 (measured); Splink on Febrl (blog figure, unverified) 0.998 |
| BPID | pairs | 0.811 | 0.846 | **0.828** [0.808, 0.845] | 0.640 | 0.976 @5 | 47.4 | Sudowoodo (best published) 0.788; Ditto 0.752; Llama3-70B zero-shot 0.729; GPT-4-turbo zero-shot 0.687; rules 0.608 |
| Abt-Buy | pairs | 0.678 | 0.768 | **0.721** [0.668, 0.769] | 0.844 | 0.961 @5 | 17.7 | Magellan (Zingg-class) 0.436; DeepMatcher 0.628; Ditto 0.893; GPT-4 zero-shot 0.958 |
| Amazon-Google | pairs | 0.594 | 0.697 | **0.641** [0.593, 0.688] | 0.693 | 0.977 @5 | 16.8 | Magellan (Zingg-class) 0.491; DeepMatcher 0.693; Ditto 0.756; GPT-4 zero-shot 0.764 |
| Walmart-Amazon | pairs | 0.850 | 0.740 | **0.791** [0.743, 0.835] | 0.613 | 0.995 @5 | 20.7 | Magellan (Zingg-class) 0.719; DeepMatcher 0.676; Ditto 0.868; GPT-4 zero-shot 0.897 |
| DBLP-ACM | pairs | 0.989 | 0.993 | **0.991** [0.985, 0.997] | 0.977 | 1.000 @5 | 21.1 | Magellan (Zingg-class) 0.984; Ditto 0.990 |
| Splink historical_50k (dedupe) | dedupe | 0.978 | 0.653 | **0.783** [0.778, 0.789] | 0.204 | 0.679 @10 | 62.9 | Splink 0.6881 (measured) |
| Leipzig Affiliations (dedupe) | dedupe | 0.847 | 0.451 | **0.588** [0.558, 0.618] | 0.162 | 0.514 @10 | 17.8 | Dedupe classifier + F-MWSP clustering (whole dataset) 0.630 |
| Synthetic 10^6 | linkage | 1.000 | 0.119 | **0.212** [0.207, 0.216] | 0.079 | 0.119 @5 | 114.9 | Splink 0.9921 (measured) |

## Findings

- **The nearest-neighbour baseline beats the trained matcher** (above its whole interval) on Abt-Buy (0.844 vs 0.721), Amazon-Google (0.693 vs 0.641). On these product sets a right record matches at most one left record and the right title is usually the closest one: the pair classifier, which sees each pair alone, loses to plain ranking. Candidate-aware features or a select-among-candidates decision are the lever (ZR-4 onwards).
- **Jev as the only labeller works where it is confident.** Its confident share is below 30 % on BPID (23 of 400), Splink historical_50k (dedupe) (102 of 400): there it must judge, not label (the 2026-09-19 finding, reproduced).
- **Scale: the default candidate step collapses at 10^6 records** (Synthetic 10^6 candidate recall 0.119). `bench/scale_probe.py` (`results/scale_probe.json`) locates it in two places:
  - gram_topk proposals (join: grams in <= 400 right records): recall **0.1178**, 1,289,714 pairs, 38.3 s
  - union(gram_topk, conjunction field_blocks) proposals: recall **0.9868**, 3,016,303 pairs, 42.9 s
  - union proposals -> top 5, ranking vocabulary gram_cap 400 (today): recall **0.5495**, 1,846,673 pairs, 14.0 s
  - union proposals -> top 5, ranking vocabulary 5 % of right records: recall **0.9867**, 1,846,673 pairs, 33.0 s
  - union proposals -> top 5, ranking vocabulary 10 % of right records: recall **0.9867**, 1,846,673 pairs, 37.0 s
  Two defects, both visible only at scale: the gram join keeps grams held by at most `gram_cap` = 400 right records, which at 500 000 records leaves almost no gram a true pair shares; and the shared ranking scores proposals over that same capped vocabulary, so most score 0 and the top-k cut is arbitrary. Conjunction blocks plus a ranking vocabulary cut relative to the corpus size restore 0.987. Changing the candidate default is a re-decision on VALIDATION data with this corpus added to `bench/methods.py` — the next goal, not done here.

## FEBRL4 thresholds

| | all ten fields | SSN hidden | bar |
|---|---|---|---|
| F1 [95 % CI] | 0.998 [0.995, 1.000] | 0.999 [0.997, 1.000] | ≥ 0.97 / ≥ 0.96 |
| wall time incl. Spark start | 22.9 s (the slower of the two runs) | | < 60 s |

Verdict: **met**. Zingg on the same task: 0.841 (all fields) / 0.862 (SSN hidden), recall 0.73–0.76 (recorded 2026-09-19).

## Jev as the only labeller

The same run with no gold label: Jev labels 400 TRAIN candidate pairs, only its confident answers (τ 0.90) train the model and pick the threshold. Tokens and dollars are the cost of labelling the sample once (answers are cached, so a re-run sends nothing); price $0.042 per million input tokens, output free.

| Corpus | asked | kept | F1 [95 % CI] | gold F1 | input tokens | $ | note |
|---|---|---|---|---|---|---|---|
| FEBRL4, half the partners removed | 400 | 371 | 0.948 [0.934, 0.961] | 0.998 | 259,065 | 0.0109 |  |
| FEBRL4 original | 400 | 354 | 0.998 [0.996, 1.000] | 1.000 | 254,118 | 0.0107 |  |
| FEBRL3 (dedupe) | 400 | 356 | 0.948 [0.934, 0.961] | 0.998 | 252,459 | 0.0106 |  |
| BPID | 400 | 23 | 0.649 [0.627, 0.670] | 0.828 | 227,278 | 0.0095 |  |
| Abt-Buy | 400 | 328 | 0.506 [0.448, 0.569] | 0.721 | 224,233 | 0.0094 |  |
| Amazon-Google | 400 | 225 | 0.343 [0.274, 0.408] | 0.641 | 188,721 | 0.0079 |  |
| Walmart-Amazon | 400 | 275 | 0.757 [0.704, 0.807] | 0.791 | 214,338 | 0.0090 |  |
| DBLP-ACM | 400 | 342 | 0.910 [0.890, 0.928] | 0.991 | 208,110 | 0.0087 |  |
| Splink historical_50k (dedupe) | 400 | 102 | 0.657 [0.650, 0.664] | 0.783 | 218,726 | 0.0092 |  |
| Leipzig Affiliations (dedupe) | 400 | 267 | 0.493 [0.462, 0.526] | 0.588 | 178,934 | 0.0075 |  |
| Synthetic 10^6 | 400 | 388 | 0.194 [0.189, 0.198] | 0.212 | 234,277 | 0.0098 |  |

Total: 2,460,259 input tokens, $0.103.

## Latency and scale

| Corpus | records | candidate pairs | wall s | records / s | peak shuffle (one stage, MB) | total shuffle MB |
|---|---|---|---|---|---|---|
| FEBRL4, half the partners removed | 7,500 | 25,000 | 22.9 | 327.5 | 182.2 | 218.6 |
| FEBRL4 original | 10,000 | 25,000 | 28.1 | 355.9 | 374.7 | 412.8 |
| FEBRL3 (dedupe) | 5,000 | 33,324 | 29.0 | 172.4 | 429.3 | 487.8 |
| BPID | 20,000 | 50,000 | 47.4 | 421.9 | 1887.8 | 2012.8 |
| Abt-Buy | 2,103 | 5,340 | 17.7 | 118.8 | 55.8 | 98.9 |
| Amazon-Google | 3,362 | 6,440 | 16.8 | 200.1 | 31.9 | 67.1 |
| Walmart-Amazon | 6,935 | 8,440 | 20.7 | 335.0 | 119.7 | 280.7 |
| DBLP-ACM | 4,681 | 12,180 | 21.1 | 221.8 | 207.9 | 348.9 |
| Splink historical_50k (dedupe) | 50,578 | 334,095 | 62.9 | 804.1 | 1266.5 | 2116.3 |
| Leipzig Affiliations (dedupe) | 2,260 | 15,470 | 17.8 | 127.0 | 26.5 | 55.2 |
| Synthetic 10^6 | 1,000,000 | 1,289,714 | 114.9 | 8,703.2 | 1185.8 | 4191.9 |

Peak shuffle is read from the Spark event log of each run. DBUs from the billing table apply on Databricks only (ZR-6).

## References

**FEBRL4, half the partners removed.**

| system | F1 | source |
|---|---|---|
| Zingg, perfect labels, all fields | 0.841 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Zingg, perfect labels, SSN hidden | 0.862 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Zingg, labels from Jev | 0.849 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Splink 5.0.0, measured here — unsupervised Fellegi-Sunter (DuckDB), pairwise over the whole corpus, p >= 0.5 | 0.9996 | bench/splink_reference.py |
| Splink, same model, SSN hidden | 0.9881 | bench/splink_reference.py |
| prototype: classifier on Jev labels, all fields / SSN hidden | 0.9748 / 0.9356 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| prototype + Jev arbitrates, all fields / SSN hidden | 0.9944 / 0.9637 | Lake/mdm/bench/README.md (recorded 2026-09-19) |

**FEBRL4 original.**

| system | F1 | source |
|---|---|---|
| Zingg, labels from Jev (6 rounds) | 0.853 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Zingg, ground-truth labels (6 rounds) | 0.858 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Splink 5.0.0, measured here — unsupervised Fellegi-Sunter (DuckDB), pairwise over the whole corpus, p >= 0.5 | 0.9995 | bench/splink_reference.py |
| nearest neighbour, always link | 1.000 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| top-k candidates + classifier on Jev labels | 0.999 | Lake/mdm/bench/README.md (recorded 2026-09-19) |

Corpus: every left record has exactly one partner: the nearest neighbour is a strong baseline.

**FEBRL3 (dedupe).**

| system | F1 | source |
|---|---|---|
| Splink 5.0.0, measured here — unsupervised Fellegi-Sunter (DuckDB), pairwise over the whole corpus, p >= 0.5 | 0.9918 | bench/splink_reference.py |
| Splink on Febrl (blog figure, unverified) | 0.998 | Splink blog, cited in the brief |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here.

Corpus: 2000 gold clusters over 5000 records, largest 6.

**BPID.**

| system | F1 | source |
|---|---|---|
| Sudowoodo (best published) | 0.788 | BPID, EMNLP 2024 Industry |
| Ditto | 0.752 | BPID, EMNLP 2024 Industry |
| Llama3-70B zero-shot | 0.729 | BPID, EMNLP 2024 Industry |
| GPT-4-turbo zero-shot | 0.687 | BPID, EMNLP 2024 Industry |
| rules | 0.608 | BPID, EMNLP 2024 Industry |
| Jev zero-shot (own 70/10/20 split) | 0.813 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| classical, 7 000 gold labels (own split) | 0.749 | Lake/mdm/bench/README.md (recorded 2026-09-19) |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here; not measured on this corpus (bench/splink_reference.py covers the person corpora with a Splink demo-style model).

**Abt-Buy.**

| system | F1 | source |
|---|---|---|
| Magellan (Zingg-class) | 0.436 | Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher) |
| DeepMatcher | 0.628 | Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher) |
| Ditto | 0.893 | Li et al., VLDB 2021 (Ditto) |
| GPT-4 zero-shot | 0.958 | Peeters, Steiner & Bizer, EDBT 2025 (GPT-4, best of 10 prompts, downsampled test) |
| classifier (scikit-learn) | 0.768 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Jev zero-shot | 0.930 | Lake/mdm/bench/README.md (recorded 2026-09-19) |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here; not measured on this corpus (bench/splink_reference.py covers the person corpora with a Splink demo-style model).

Corpus: 73 pair(s) repeated across Ditto splits, kept once.

**Amazon-Google.**

| system | F1 | source |
|---|---|---|
| Magellan (Zingg-class) | 0.491 | Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher) |
| DeepMatcher | 0.693 | Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher) |
| Ditto | 0.756 | Li et al., VLDB 2021 (Ditto) |
| GPT-4 zero-shot | 0.764 | Peeters, Steiner & Bizer, EDBT 2025 (GPT-4, best of 10 prompts, downsampled test) |
| classifier (scikit-learn) | 0.684 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Jev zero-shot | 0.705 | Lake/mdm/bench/README.md (recorded 2026-09-19) |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here; not measured on this corpus (bench/splink_reference.py covers the person corpora with a Splink demo-style model).

Corpus: 501 pair(s) repeated across Ditto splits, kept once.

**Walmart-Amazon.**

| system | F1 | source |
|---|---|---|
| Magellan (Zingg-class) | 0.719 | Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher) |
| DeepMatcher | 0.676 | Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher) |
| Ditto | 0.868 | Li et al., VLDB 2021 (Ditto) |
| GPT-4 zero-shot | 0.897 | Peeters, Steiner & Bizer, EDBT 2025 (GPT-4, best of 10 prompts, downsampled test) |
| classifier (scikit-learn) | 0.831 | Lake/mdm/bench/README.md (recorded 2026-09-19) |
| Jev zero-shot | 0.916 | Lake/mdm/bench/README.md (recorded 2026-09-19) |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here; not measured on this corpus (bench/splink_reference.py covers the person corpora with a Splink demo-style model).

Corpus: 6 pair(s) repeated across Ditto splits, kept once.

**DBLP-ACM.**

| system | F1 | source |
|---|---|---|
| Magellan (Zingg-class) | 0.984 | Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher) |
| Ditto | 0.990 | Li et al., VLDB 2021 (Ditto) |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here; not measured on this corpus (bench/splink_reference.py covers the person corpora with a Splink demo-style model).

Corpus: 260 pair(s) repeated across Ditto splits, kept once.

**Splink historical_50k (dedupe).**

| system | F1 | source |
|---|---|---|
| Splink 5.0.0, measured here — unsupervised Fellegi-Sunter (DuckDB), pairwise over the whole corpus, p >= 0.5 | 0.6881 | bench/splink_reference.py |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here.

Corpus: 5156 gold clusters over 50578 records, largest 21.

**Leipzig Affiliations (dedupe).**

| system | F1 | source |
|---|---|---|
| Dedupe classifier + F-MWSP clustering (whole dataset) | 0.630 | Lokhande et al., arXiv 1909.05460 (2019); a hand-written rule classifier (Aumueller & Rahm, ICIQ 2009) is reported higher, figure not extracted |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here; not measured on this corpus (bench/splink_reference.py covers the person corpora with a Splink demo-style model).

Corpus: 330 gold clusters over 2260 strings.

**Synthetic 10^6.**

| system | F1 | source |
|---|---|---|
| Splink 5.0.0, measured here — unsupervised Fellegi-Sunter (DuckDB), pairwise over the whole corpus, p >= 0.5 | 0.9921 | bench/splink_reference.py |

not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here.

Corpus: 10^6 generated records (500 000 per side), 250 000 true links, seed 1000000.

## Method choices

Every candidate method (candidate recall at an equal pair budget), string similarity, estimator and cardinality policy is compared on VALIDATION data in [METHODS.md](METHODS.md) (ZR-3a). The winners, which are the shipped defaults in `config.py`:

| choice | winner = default |
|---|---|
| `candidates.method` | `gram_topk` (default `gram_topk`) |
| `features.string_similarity` | `levenshtein` (default `levenshtein`) |
| `matcher.estimator` | `gbt` (default `gbt`) |
| `decision.cardinality` | `one_to_one` (default `one_to_one`) |

De-duplication across splits asserted on every corpus: **True**.

## Protocol

```text
(the same for every corpus, TEST is read once per labeller):

  linkage / dedupe   records -> entity view -> candidates (gram_topk, k = 5; k = 10 for dedupe, self pairs dropped,
                     pairs canonicalised) -> comparison vectors. Left records (the smaller id for dedupe) are split
                     by xxhash64 of their id: train 60 % / valid 20 % / test 20 % — the split of bench/methods.py, so
                     the method choices never saw TEST. Gold labeller: every TRAIN candidate labelled from the truth,
                     model fitted on TRAIN, threshold on VALID, links on TEST under the cardinality policy
                     (linkage: decision.cardinality; dedupe: unrestricted — clustering is ZR-4). Units = TEST left
                     records; a true pair the candidates missed is a false negative.
  pairs              the corpus's fixed pair splits (Ditto's for the Magellan sets, a line hash for BPID): model on
                     TRAIN, threshold on VALID, F1 on TEST pairs. Candidate recall@k = TEST matches that gram_topk
                     (k = 5) proposes when run over all records.
  Jev labeller       the same run with no gold label: Jev labels 400 TRAIN candidate pairs (xxhash order), only its
                     confident answers (tau 0.90) are kept, split 75 / 25 by left id into fit / threshold. Tokens and
                     dollars are the requests actually sent (answers are cached under data/runs/bench/jev/).
  trivial baseline   always link each left record's nearest neighbour (rank-1 candidate), scored on the same units.

F1 intervals: 95 % percentile bootstrap over TEST units (1 000 resamples, seed 0). Peak shuffle: the largest bytes
written by one stage, read from the Spark event log. De-duplication across splits is asserted per corpus.
```

## Reproduce

```bash
source scripts/env.sh
lakematch bench --all                      # every corpus, one process each (≈ the table's wall times)
python bench/benchmarks.py all --only abt_buy   # one row; the others keep their last result
python bench/splink_reference.py              # the measured Splink references
python bench/benchmarks.py render             # BENCHMARKS.md from the JSON, no Spark
```
