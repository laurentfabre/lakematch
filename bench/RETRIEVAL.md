# Retrieval observations — ZR-3 iteration 1

Source-compatibility note: the runtime gained a table-truncation option after these measurements. Final-source verification remains pending.

Validation candidate recall only. These results do not select the final classifier or prove the FEBRL F1/latency gates.

All methods use k=5, at most 100,000 final pairs, and a 50-million retained pre-top-k join limit.
Alternative methods rerank by unweighted gram cosine; gram top-k uses IDF weighting. Unlabelled pairs are not assumed negative.
Fitted state uses training records only. Transductive retrieval queries the complete unlabelled universe.
Disjoint retrieval queries validation records after removing identities seen on either training side; its denominator may differ.

Full-universe candidate recall:

| Corpus | Gram top-k | Learned blocker | MinHash | Field blocks | Union |
|---|---:|---:|---:|---:|---:|
| febrl4_half_all | 100.0% | 99.8% | 97.8% | 100.0% | 100.0% |
| febrl4_half_no_ssn | 100.0% | 99.0% | 97.8% | 100.0% | 100.0% |
| febrl4_half_no_ssn_dob | 100.0% | 98.2% | 97.8% | 100.0% | 100.0% |
| bpid | budget_rejected | 32.7% | 55.4% | 62.2% | budget_rejected |
| abt_buy | 99.0% | 22.1% | 62.3% | 93.1% | 94.6% |
| affiliations | 24.2% | 12.1% | 22.0% | 12.1% | 23.5% |
| amazon_google | 97.7% | 56.7% | 85.1% | 60.9% | 96.7% |
| walmart_amazon | 99.0% | 57.5% | 72.5% | 96.4% | 96.9% |
| dblp_acm | 100.0% | 99.5% | 97.5% | 100.0% | 100.0% |

A rejected method has no recall measurement under this budget. No corpus is dropped to compute an apparently complete macro score.
Union reranking at fixed k can discard a true match retained by a child. The SSN+DOB-hidden row is diagnostic only.

Detailed scope, uncertainty and work measurements:

| Corpus | Scope | Method | Recall [95% CI] | Δ recall CI vs gram | Pairs | Join rows before/after cap | Fit/save s | Retrieval s |
|---|---|---|---|---|---:|---:|---:|---:|
| febrl4_half_all | transductive | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 71355234/17252022 | 0.00 | 30.17 |
| febrl4_half_all | disjoint | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 2877187/1882862 | 0.00 | 4.27 |
| febrl4_half_all | transductive | learned_blocker | 0.998 [0.994, 1.000] | [-0.006, +0.000] | 6412 | 10133/10133 | 2.04 | 1.43 |
| febrl4_half_all | disjoint | learned_blocker | 0.998 [0.994, 1.000] | [-0.006, +0.000] | 660 | 1365/1365 | 2.04 | 0.67 |
| febrl4_half_all | transductive | minhash_lsh | 0.978 [0.964, 0.990] | [-0.036, -0.010] | 24917 | 1624475/642249 | 1.05 | 12.27 |
| febrl4_half_all | disjoint | minhash_lsh | 0.992 [0.984, 0.998] | [-0.016, -0.002] | 4985 | 67300/67300 | 1.05 | 2.34 |
| febrl4_half_all | transductive | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 3402522/758568 | 0.00 | 8.31 |
| febrl4_half_all | disjoint | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 137236/137236 | 0.00 | 2.00 |
| febrl4_half_all | transductive | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 74757756/18010590 | 0.00 | 57.23 |
| febrl4_half_all | disjoint | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 3014423/2020098 | 0.00 | 18.14 |
| febrl4_half_no_ssn | transductive | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 68247312/14716729 | 0.00 | 26.79 |
| febrl4_half_no_ssn | disjoint | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 2750591/1756266 | 0.00 | 4.32 |
| febrl4_half_no_ssn | transductive | learned_blocker | 0.990 [0.980, 0.998] | [-0.020, -0.002] | 9181 | 13535/13535 | 2.07 | 1.43 |
| febrl4_half_no_ssn | disjoint | learned_blocker | 0.990 [0.980, 0.998] | [-0.020, -0.002] | 822 | 1361/1361 | 2.07 | 0.68 |
| febrl4_half_no_ssn | transductive | minhash_lsh | 0.978 [0.964, 0.990] | [-0.036, -0.010] | 24897 | 1748507/679756 | 0.91 | 10.97 |
| febrl4_half_no_ssn | disjoint | minhash_lsh | 0.992 [0.984, 0.998] | [-0.016, -0.002] | 4983 | 71604/71604 | 0.91 | 2.12 |
| febrl4_half_no_ssn | transductive | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 3400249/756295 | 0.00 | 7.17 |
| febrl4_half_no_ssn | disjoint | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 136779/136779 | 0.00 | 1.83 |
| febrl4_half_no_ssn | transductive | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 71647561/15473024 | 0.00 | 54.17 |
| febrl4_half_no_ssn | disjoint | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 2887370/1893045 | 0.00 | 26.20 |
| febrl4_half_no_ssn_dob | transductive | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 47952034/13347192 | 0.00 | 24.37 |
| febrl4_half_no_ssn_dob | disjoint | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 1935780/1417693 | 0.00 | 4.03 |
| febrl4_half_no_ssn_dob | transductive | learned_blocker | 0.982 [0.970, 0.992] | [-0.030, -0.008] | 17295 | 25415/25415 | 1.80 | 1.51 |
| febrl4_half_no_ssn_dob | disjoint | learned_blocker | 0.982 [0.970, 0.992] | [-0.030, -0.008] | 1267 | 1786/1786 | 1.80 | 0.66 |
| febrl4_half_no_ssn_dob | transductive | minhash_lsh | 0.978 [0.964, 0.990] | [-0.036, -0.010] | 24890 | 1789888/697158 | 1.00 | 9.70 |
| febrl4_half_no_ssn_dob | disjoint | minhash_lsh | 0.990 [0.980, 0.998] | [-0.020, -0.002] | 4985 | 75300/75300 | 1.00 | 1.93 |
| febrl4_half_no_ssn_dob | transductive | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 3278634/634680 | 0.00 | 5.48 |
| febrl4_half_no_ssn_dob | disjoint | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 4997 | 131224/131224 | 0.00 | 1.63 |
| febrl4_half_no_ssn_dob | transductive | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 25000 | 51230668/13981872 | 0.00 | 48.18 |
| febrl4_half_no_ssn_dob | disjoint | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 5000 | 2067004/1548917 | 0.00 | 21.23 |
| bpid | transductive | gram_topk | budget_rejected: Pre-top-k join budget exceeded: {'join_rows_before_cap': 636719883, 'join_rows_after_cap': 83426093, 'dropped_grams': 520}; limit=50000000 | — | — | — | — | — |
| bpid | disjoint | gram_topk | 0.976 [0.966, 0.986] | [+0.000, +0.000] | 10200 | 26066367/17860209 | 0.00 | 37.15 |
| bpid | transductive | learned_blocker | 0.327 [0.297, 0.355] | reference over budget | 3554 | 4271/4271 | 2.23 | 2.81 |
| bpid | disjoint | learned_blocker | 0.327 [0.297, 0.355] | [-0.680, -0.617] | 586 | 613/613 | 2.23 | 0.91 |
| bpid | transductive | minhash_lsh | 0.554 [0.521, 0.585] | reference over budget | 49898 | 11071466/3447647 | 1.03 | 73.98 |
| bpid | disjoint | minhash_lsh | 0.677 [0.647, 0.709] | [-0.328, -0.268] | 10194 | 470719/470719 | 1.03 | 10.52 |
| bpid | transductive | field_blocks | 0.622 [0.591, 0.652] | reference over budget | 43678 | 249828/249828 | 0.00 | 6.54 |
| bpid | disjoint | field_blocks | 0.626 [0.595, 0.656] | [-0.382, -0.318] | 5409 | 11827/11827 | 0.00 | 1.27 |
| bpid | transductive | union | budget_rejected: Pre-top-k join budget exceeded: {'join_rows_before_cap': 636969711, 'join_rows_after_cap': 83675921, 'dropped_grams': 520}; limit=50000000 | — | — | — | — | — |
| bpid | disjoint | union | 0.973 [0.962, 0.983] | [-0.007, +0.002] | 10200 | 26078194/17872036 | 0.00 | 54.56 |
| abt_buy | transductive | gram_topk | 0.990 [0.975, 1.000] | [+0.000, +0.000] | 5340 | 11210168/7258449 | 0.00 | 14.33 |
| abt_buy | disjoint | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 260 | 25252/25252 | 0.00 | 1.89 |
| abt_buy | transductive | learned_blocker | 0.221 [0.167, 0.275] | [-0.824, -0.711] | 3794 | 10836/10836 | 1.52 | 1.47 |
| abt_buy | disjoint | learned_blocker | 0.167 [0.042, 0.333] | [-0.958, -0.667] | 16 | 16/16 | 1.52 | 0.52 |
| abt_buy | transductive | minhash_lsh | 0.623 [0.554, 0.686] | [-0.436, -0.304] | 5339 | 167663/167663 | 0.86 | 6.87 |
| abt_buy | disjoint | minhash_lsh | 0.667 [0.458, 0.833] | [-0.542, -0.167] | 244 | 515/515 | 0.86 | 0.86 |
| abt_buy | transductive | field_blocks | 0.931 [0.897, 0.966] | [-0.093, -0.029] | 5106 | 69603/69603 | 0.00 | 2.18 |
| abt_buy | disjoint | field_blocks | 0.958 [0.875, 1.000] | [-0.125, +0.000] | 105 | 140/140 | 0.00 | 0.52 |
| abt_buy | transductive | union | 0.946 [0.912, 0.975] | [-0.074, -0.020] | 5340 | 11279771/7328052 | 0.00 | 28.40 |
| abt_buy | disjoint | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 260 | 25392/25392 | 0.00 | 8.49 |
| affiliations | transductive | gram_topk | 0.242 [0.217, 0.270] | [+0.000, +0.000] | 11262 | 30280533/7376117 | 0.00 | 13.68 |
| affiliations | disjoint | gram_topk | 0.263 [0.236, 0.295] | [+0.000, +0.000] | 1865 | 1114758/1114758 | 0.00 | 2.74 |
| affiliations | transductive | learned_blocker | 0.121 [0.101, 0.144] | [-0.141, -0.102] | 8474 | 335556/124875 | 1.45 | 2.03 |
| affiliations | disjoint | learned_blocker | 0.201 [0.179, 0.226] | [-0.082, -0.045] | 1539 | 14808/14808 | 1.45 | 0.65 |
| affiliations | transductive | minhash_lsh | 0.220 [0.196, 0.244] | [-0.036, -0.010] | 11194 | 1336196/625913 | 0.87 | 6.38 |
| affiliations | disjoint | minhash_lsh | 0.252 [0.225, 0.279] | [-0.023, -0.002] | 1837 | 51224/51224 | 0.87 | 1.14 |
| affiliations | transductive | field_blocks | 0.121 [0.101, 0.144] | [-0.141, -0.102] | 8474 | 335556/124875 | 0.00 | 1.97 |
| affiliations | disjoint | field_blocks | 0.201 [0.179, 0.226] | [-0.082, -0.045] | 1539 | 14808/14808 | 0.00 | 0.62 |
| affiliations | transductive | union | 0.235 [0.210, 0.262] | [-0.015, +0.000] | 11262 | 30616089/7500992 | 0.00 | 23.75 |
| affiliations | disjoint | union | 0.257 [0.230, 0.287] | [-0.014, +0.001] | 1865 | 1129566/1129566 | 0.00 | 10.79 |
| amazon_google | transductive | gram_topk | 0.977 [0.954, 0.995] | [+0.000, +0.000] | 6440 | 9060270/4737716 | 0.00 | 11.69 |
| amazon_google | disjoint | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 495 | 54797/54797 | 0.00 | 1.82 |
| amazon_google | transductive | learned_blocker | 0.567 [0.500, 0.633] | [-0.477, -0.343] | 4750 | 30815/30815 | 1.47 | 1.27 |
| amazon_google | disjoint | learned_blocker | 0.579 [0.421, 0.737] | [-0.579, -0.263] | 82 | 92/92 | 1.47 | 0.67 |
| amazon_google | transductive | minhash_lsh | 0.851 [0.801, 0.900] | [-0.173, -0.083] | 6432 | 619432/282554 | 0.92 | 4.07 |
| amazon_google | disjoint | minhash_lsh | 0.895 [0.789, 0.974] | [-0.211, -0.026] | 467 | 3593/3593 | 0.92 | 0.80 |
| amazon_google | transductive | field_blocks | 0.609 [0.540, 0.673] | [-0.433, -0.304] | 6016 | 55794/55794 | 0.00 | 1.23 |
| amazon_google | disjoint | field_blocks | 0.579 [0.421, 0.737] | [-0.579, -0.263] | 217 | 329/329 | 0.00 | 0.61 |
| amazon_google | transductive | union | 0.967 [0.940, 0.991] | [-0.023, +0.000] | 6440 | 9116064/4793510 | 0.00 | 19.23 |
| amazon_google | disjoint | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 495 | 55126/55126 | 0.00 | 9.84 |
| walmart_amazon | transductive | gram_topk | 0.990 [0.974, 1.000] | [+0.000, +0.000] | 8440 | 42081348/11461898 | 0.00 | 33.57 |
| walmart_amazon | disjoint | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 775 | 566173/566173 | 0.00 | 3.10 |
| walmart_amazon | transductive | learned_blocker | 0.575 [0.505, 0.646] | [-0.487, -0.344] | 3295 | 6439/6439 | 1.70 | 1.35 |
| walmart_amazon | disjoint | learned_blocker | 0.661 [0.534, 0.780] | [-0.466, -0.220] | 109 | 152/152 | 1.70 | 0.70 |
| walmart_amazon | transductive | minhash_lsh | 0.725 [0.658, 0.789] | [-0.332, -0.201] | 8432 | 1178913/472254 | 0.90 | 10.83 |
| walmart_amazon | disjoint | minhash_lsh | 0.864 [0.763, 0.949] | [-0.237, -0.051] | 775 | 14893/14893 | 0.90 | 1.71 |
| walmart_amazon | transductive | field_blocks | 0.964 [0.937, 0.990] | [-0.052, -0.005] | 8319 | 334301/311843 | 0.00 | 3.24 |
| walmart_amazon | disjoint | field_blocks | 0.983 [0.948, 1.000] | [-0.052, +0.000] | 654 | 4591/4591 | 0.00 | 0.78 |
| walmart_amazon | transductive | union | 0.969 [0.943, 0.990] | [-0.042, -0.005] | 8440 | 42415649/11773741 | 0.00 | 51.85 |
| walmart_amazon | disjoint | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 775 | 570764/570764 | 0.00 | 12.41 |
| dblp_acm | transductive | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 12180 | 93918127/21317704 | 0.00 | 45.19 |
| dblp_acm | disjoint | gram_topk | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 1060 | 592976/592976 | 0.00 | 2.47 |
| dblp_acm | transductive | learned_blocker | 0.995 [0.989, 1.000] | [-0.011, +0.000] | 9910 | 61316/61316 | 1.76 | 2.32 |
| dblp_acm | disjoint | learned_blocker | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 344 | 567/567 | 1.76 | 0.55 |
| dblp_acm | transductive | minhash_lsh | 0.975 [0.959, 0.989] | [-0.041, -0.011] | 12129 | 2074955/547542 | 0.93 | 14.58 |
| dblp_acm | disjoint | minhash_lsh | 0.992 [0.976, 1.000] | [-0.024, +0.000] | 1046 | 13139/13139 | 0.93 | 1.30 |
| dblp_acm | transductive | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 12180 | 705372/624242 | 0.00 | 12.01 |
| dblp_acm | disjoint | field_blocks | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 1060 | 5187/5187 | 0.00 | 0.72 |
| dblp_acm | transductive | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 12180 | 94623499/21941946 | 0.00 | 74.23 |
| dblp_acm | disjoint | union | 1.000 [1.000, 1.000] | [+0.000, +0.000] | 1060 | 598163/598163 | 0.00 | 10.23 |

Bootstrap: 2,000 paired group resamples, seed 2026091902. Fit/save time is shared by both scopes.
Retrieval time includes full-universe budget validation plus validation-anchor collection; it excludes fit/save and Spark startup.
Complete run wall time includes corpus preparation, Spark startup, both scopes, state writes and Spark cleanup; archive compression follows.
The ideal recall ceiling sums min(k, labelled-positive degree) per anchor. Many-to-many tasks may have a ceiling below 1 even with perfect ranking.
Remote and live-label spend: zero (offline local runs). No confirmation/test partition has been scored.

- [20260920T001441Z-retrieval-febrl4-all-282fbe](../experiments/20260920T001441Z-retrieval-febrl4-all-282fbe/manifest.json): 155.03s. Disjoint universe: 1000 left / 500 right; 500 of 500 original validation positives remain. Training-overlap removals: [0, 0]. Ideal recall ceilings at k=5: transductive 1.000, disjoint 1.000.
- [20260920T001718Z-retrieval-febrl4-no_ssn-ec74ee](../experiments/20260920T001718Z-retrieval-febrl4-no_ssn-ec74ee/manifest.json): 153.54s. Disjoint universe: 1000 left / 500 right; 500 of 500 original validation positives remain. Training-overlap removals: [0, 0]. Ideal recall ceilings at k=5: transductive 1.000, disjoint 1.000.
- [20260920T001953Z-retrieval-febrl4-no_ssn_dob-d4d9c9](../experiments/20260920T001953Z-retrieval-febrl4-no_ssn_dob-d4d9c9/manifest.json): 135.42s. Disjoint universe: 1000 left / 500 right; 500 of 500 original validation positives remain. Training-overlap removals: [0, 0]. Ideal recall ceilings at k=5: transductive 1.000, disjoint 1.000.
- [20260920T000205Z-retrieval-bpid-a44b4e](../experiments/20260920T000205Z-retrieval-bpid-a44b4e/manifest.json): 208.99s. Disjoint universe: 2040 left / 2040 right; 899 of 899 original validation positives remain. Training-overlap removals: [0, 0]. Ideal recall ceilings at k=5: disjoint 1.000, transductive 1.000.
- [20260920T000535Z-retrieval-abt_buy-627b18](../experiments/20260920T000535Z-retrieval-abt_buy-627b18/manifest.json): 79.32s. Disjoint universe: 52 left / 53 right; 24 of 204 original validation positives remain. Training-overlap removals: [664, 636]. Ideal recall ceilings at k=5: transductive 1.000, disjoint 1.000.
- [20260920T000656Z-retrieval-affiliations-4bdce9](../experiments/20260920T000656Z-retrieval-affiliations-4bdce9/manifest.json): 83.14s. Disjoint universe: 373 left / 373 right; 2118 of 2118 original validation positives remain. Training-overlap removals: [0, 0]. Ideal recall ceilings at k=5: transductive 0.495, disjoint 0.495.
- [20260920T000820Z-retrieval-amazon_google-46f6b9](../experiments/20260920T000820Z-retrieval-amazon_google-46f6b9/manifest.json): 64.59s. Disjoint universe: 99 left / 189 right; 38 of 215 original validation positives remain. Training-overlap removals: [660, 854]. Ideal recall ceilings at k=5: transductive 1.000, disjoint 1.000.
- [20260920T000926Z-retrieval-walmart_amazon-08ad29](../experiments/20260920T000926Z-retrieval-walmart_amazon-08ad29/manifest.json): 134.37s. Disjoint universe: 155 left / 831 right; 59 of 193 original validation positives remain. Training-overlap removals: [772, 747]. Ideal recall ceilings at k=5: transductive 1.000, disjoint 1.000.
- [20260920T001142Z-retrieval-dblp_acm-ce6afb](../experiments/20260920T001142Z-retrieval-dblp_acm-ce6afb/manifest.json): 177.91s. Disjoint universe: 212 left / 183 right; 124 of 441 original validation positives remain. Training-overlap removals: [1035, 1009]. Ideal recall ceilings at k=5: transductive 1.000, disjoint 1.000.

Retained failures:

- [20260919T235548Z-retrieval-bpid-68711e](../experiments/20260919T235548Z-retrieval-bpid-68711e/manifest.json): failed.
