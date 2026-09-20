# Frozen benchmark measurements

Models, thresholds, retrieval state and data were frozen before scoring. [Freeze](freeze.json); [plan](FINAL_PLAN.md).
FEBRL is closed-world linkage after global cardinality. Other rows score only supplied held-out pairs after full-universe retrieval; unknown pairs remain unknown and missing positives count as false negatives. Shared-record caveats remain in each manifest.

| Corpus / partition | Precision | Recall | F1 [95% CI] | Recall@5 | Wall s | NN F1 | Cosine F1 | Gate |
|---|---:|---:|---|---:|---:|---:|---:|---|
| febrl4_half_all / valid | 1.0000 | 0.9780 | 0.9889 [0.9821, 0.9950] | 0.9780 | 29.19 | 0.6524 | 0.9889 | diagnostic |
| febrl4_half_all / confirmation | 1.0000 | 0.9780 | 0.9889 [0.9815, 0.9950] | 0.9780 | 29.19 | 0.6524 | 0.9868 | pass |
| febrl4_half_no_ssn / valid | 1.0000 | 0.9760 | 0.9879 [0.9809, 0.9940] | 0.9780 | 27.30 | 0.6529 | 0.9889 | diagnostic |
| febrl4_half_no_ssn / confirmation | 1.0000 | 0.9740 | 0.9868 [0.9793, 0.9932] | 0.9740 | 27.30 | 0.6502 | 0.9848 | pass |
| bpid / confirmation | 0.6016 | 0.5246 | 0.5605 [0.5296, 0.5901] | 0.5461 | 89.47 | 0.5238 | 0.5241 | diagnostic |
| abt_buy / test | 0.6532 | 0.5567 | 0.6011 [0.5429, 0.6576] | 0.6207 | 20.44 | 0.4266 | 0.3977 | diagnostic |
| amazon_google / test | 0.5932 | 0.8028 | 0.6823 [0.6364, 0.7269] | 0.8853 | 17.12 | 0.4831 | 0.5148 | diagnostic |
| walmart_amazon / test | 0.8583 | 0.5677 | 0.6834 [0.6220, 0.7399] | 0.7604 | 24.60 | 0.3544 | 0.4282 | diagnostic |
| dblp_acm / test | 0.9954 | 0.9797 | 0.9875 [0.9798, 0.9943] | 0.9797 | 28.24 | 0.7941 | 0.9531 | diagnostic |
| affiliations / confirmation | 1.0000 | 0.1520 | 0.2639 [0.2459, 0.2829] | 0.1520 | 25.45 | 0.1362 | 0.2639 | diagnostic |

FEBRL wall time includes a fresh normal CLI process, imports, Spark startup, model reload, outputs and cleanup. Supplied-pair wall time includes Spark startup/cleanup and evaluation/reporting in the experiment process. Baseline timing is shared; no independent baseline latency claim.
Each sealed report includes confusion counts, paired baseline-minus-model intervals, candidate/classifier loss, and positive-link missingness, Unicode and multi-value slices. Empty slices establish no coverage. The differing-name slice is a proxy for name corruption, not an annotation of typo causes.

Live Jev requests/tokens/spend and remote compute spend for these offline runs are zero. Local hardware cost is unpriced. Earlier FEVM billing remains unreconciled, not zero.

Reference figures are historical or published, with different splits, retrieval scopes and selection protocols. They are not acceptance evidence or head-to-head comparisons:

| Corpus | Reference F1 | Provenance / limitation |
|---|---|---|
| FEBRL half-unmatched | Zingg 0.841–0.862; prototype 0.96–0.98 | Historical 2026-09-19, exposed corpus/removal outcomes |
| FEBRL original | Nearest neighbour 1.000; Zingg 0.853–0.858 | Historical; fresh selected-pipeline original diagnostic still required |
| BPID | Published best 0.788; Jev zero-shot 0.813 | EMNLP 2024 Industry / historical private split; not this disjoint confirmation |
| Abt-Buy | Magellan 0.436; Ditto 0.893 | Mudgal 2018 / Li 2021, supplied-pair tasks |
| Amazon-Google | Magellan 0.491; Ditto 0.756 | Same; original duplicates/conflicts resolved differently |
| Walmart-Amazon | Magellan 0.719; Ditto 0.868 | Same; original supplied-pair splits |
| DBLP-ACM | Magellan 0.984; Ditto 0.990 | Same; original supplied-pair splits |
| FEBRL3 | Measured Splink 0.9979; verified merge 1.0000 | Training-only, entity-disjoint validation; [clustering evidence](CLUSTERS.md) |
| historical_50k | Measured Splink 0.8580; verified merge 0.9392 | 10,082-record validation graph; not full 50k confirmation |
| Leipzig Affiliations | Web URL overlap 0.832; Soft TF-IDF with location 0.442 | Aumueller/Rahm 2009, Table 3; different dataset version and web features; [extraction and caveats](AFFILIATIONS_REFERENCE.md) |
| Synthetic scale | No accuracy reference target | [Measured bounded-work ladder](SCALE.md) |

References and original provenance: [historical controlled benchmark](../spec/bench/README.md), [brief](../spec/BRIEF.md#benchmarks-and-known-tests).

Method selection: [candidates](CANDIDATES.md), [classifiers](CLASSIFIERS.md), [compact features](COMPACT_FEATURES.md), [clustering](CLUSTERS.md). No held-out result is used to revise a model or threshold. Validation-selected package defaults are adopted; final execution compatibility and phase acceptance are checked separately. Frozen benchmark models and thresholds are unchanged; the separate synthetic UC acceptance model is tracked in MODELS.md.

Evidence:

- `frozen-linkage-all`: [20260920T021816Z-frozen-linkage-all-ab5c4c](../experiments/20260920T021816Z-frozen-linkage-all-ab5c4c/manifest.json).
- `frozen-linkage-no_ssn`: [20260920T021850Z-frozen-linkage-no_ssn-648422](../experiments/20260920T021850Z-frozen-linkage-no_ssn-648422/manifest.json).
- `frozen-pairs-bpid`: [20260920T021921Z-frozen-pairs-bpid-8f3fe0](../experiments/20260920T021921Z-frozen-pairs-bpid-8f3fe0/manifest.json).
- `frozen-pairs-abt_buy`: [20260920T022053Z-frozen-pairs-abt_buy-91ebc9](../experiments/20260920T022053Z-frozen-pairs-abt_buy-91ebc9/manifest.json).
- `frozen-pairs-amazon_google`: [20260920T022115Z-frozen-pairs-amazon_google-f06d4e](../experiments/20260920T022115Z-frozen-pairs-amazon_google-f06d4e/manifest.json).
- `frozen-pairs-walmart_amazon`: [20260920T022135Z-frozen-pairs-walmart_amazon-134c63](../experiments/20260920T022135Z-frozen-pairs-walmart_amazon-134c63/manifest.json).
- `frozen-pairs-dblp_acm`: [20260920T022201Z-frozen-pairs-dblp_acm-7faf7e](../experiments/20260920T022201Z-frozen-pairs-dblp_acm-7faf7e/manifest.json).
- `frozen-pairs-affiliations`: [20260920T022232Z-frozen-pairs-affiliations-ae066d](../experiments/20260920T022232Z-frozen-pairs-affiliations-ae066d/manifest.json).
- `scale-1000`: [20260920T022259Z-scale-1000-723925](../experiments/20260920T022259Z-scale-1000-723925/manifest.json).
- `scale-10000`: [20260920T022322Z-scale-10000-173b75](../experiments/20260920T022322Z-scale-10000-173b75/manifest.json).
- `scale-100000`: [20260920T022359Z-scale-100000-71c0b7](../experiments/20260920T022359Z-scale-100000-71c0b7/manifest.json).
- `scale-1000000`: [20260920T022943Z-scale-1000000-f0a3d1](../experiments/20260920T022943Z-scale-1000000-f0a3d1/manifest.json).

## Original FEBRL diagnostic

Frozen selected model F1 0.988161, candidate recall 0.976600, fresh CLI wall time 35.43s. Independent nearest-neighbour-only F1 1.000000. [20260920T044150Z-original-febrl-9dd88f](../experiments/20260920T044150Z-original-febrl-9dd88f/manifest.json).
Full exposed original corpus, including historical development anchors; diagnostic only. This is not new holdout acceptance.

Incomplete or failed evidence:

- scale-1000000: failed; partial counters retained, no completed output or quality claim

## Final execution compatibility

[The eight-model replay audit](compatibility_index.json) records zero changes
in candidate metadata or probabilities and identical decisions for every frozen
corpus. The original freeze and model trees remain unchanged. Fresh normal-CLI
FEBRL times are 30.67s (all fields) and 27.31s (SSN hidden), with unchanged F1
0.9888776542 / 0.9868287741. These are replays of exposed outcomes.

[Actual campaign execution](campaign_execution.json) also completed the original
FEBRL diagnostic and both exact clustering comparisons, then returned nonzero
at the retained million-record scale failure. Eight ZR-3 iterations are exhausted;
no retry or larger resource envelope was used. Full campaign acceptance remains
blocked. The historical SSN+DOB-hidden validation diagnostic is separate in
[linkage_index.json](linkage_index.json); this entry point did not rerun it.
