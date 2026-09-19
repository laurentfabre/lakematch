# ZR-2 validation sweep, declared before scoring

Four local corpus runs, each limited to 900 seconds, sequential Spark sessions,
20 GBT iterations, depth 3, seed 0; at most 100,000 candidate pairs and 50 million
pre-top-k gram rows. No remote compute, live labels or confirmation scoring.
The four runs form one feature-selection iteration within the phase's eight-iteration cap.

The fixed configurations are `native_all`, `without_field_families`, `without_idf`,
`without_grams`, `without_monge`, `plus_jaro_winkler`, `plus_affine`, and
`embedding_on` (last only for organisation/title). Native-all includes all three
native multi-token measures. Default shipment waits for the cross-corpus selection.
All optional similarities are independent implementations, with explicit UDF gating.
The affine comparison is global affine-gap edit similarity (open 1, extend .25),
not the historical character-local containment score; this difference is explicit.

Corpora: full FEBRL4-half-unmatched universe, BPID, Leipzig Affiliations, Abt-Buy.
FEBRL labels use the predeclared seed 2026091901, namespaced SHA-256 ranking of
truth entities and removal choices. BPID uses components of the supplied pair
graph, so neither endpoint crosses splits. Leipzig uses released truth components;
all positive within-component pairs and five deterministic same-partition negatives
per anchor define its sampled-pair task. Abt-Buy retains its official pair split;
shared records are counted, and that row is not described as record-disjoint.
All exact/reversed pair overlaps are removed train-first, and all conflicting keys
are excluded. Canonical serialization preserves apostrophes and array boundaries.

Training pairs (including negative candidates) must have both endpoints in the
training partition. Full-universe validation retrieval can include partners from
any partition. The first run was canceled after review found that training
negatives had not enforced the right-endpoint partition. Its partial validation
results are invalid for method selection. The correction has an explicit
regression check, and the canceled run is retained.
No confirmation score was calculated and no split/seed was changed.

Fit IDF on training records only. Thresholds maximize validation F1 on the fixed
0.00–1.00 grid, ties selecting the higher threshold. Report these as validation
ablations with selection optimism, never held-out confirmation evidence. Use the
same 2,000 anchor/group bootstrap resamples (seed 2026091902) for paired differences.
Nearest-neighbour and tuned cosine baselines accompany FEBRL retrieval. The other
three corpora evaluate supplied labeled pairs and make no candidate-recall claim.

Embedding model: `sentence-transformers/all-MiniLM-L6-v2`, immutable revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, Apache-2.0, CPU, prepared locally.
No model download occurs during execution. Report actual record counts and seconds,
plus explicitly extrapolated seconds per 100,000 records. The provider runs once
per prepared record; the pair plan consumes persisted arrays and remains native.

Feature execution, fitting, inference and shared retrieval/IDF preparation are timed
separately. Per-variant timings reuse prepared candidates/statistics and are not
end-to-end latency measurements. Entire-corpus-run wall time includes Spark startup,
report writes and cleanup. The 60-second ZR-3 gate is not tested by this sweep.

## Frozen default and verification repeat

The corrected validation sweep found no statistically resolved embedding benefit:
Abt-Buy paired F1 change CI [-0.0460, +0.0231]; Leipzig [-0.0004, +0.0074].
Under the predeclared cheaper-choice rule, embedding `fields_of_type` defaults to
`[]`. The provider and pinned local MiniLM model remain selectable explicitly.
No similarity/estimator default is promoted from this limited ablation.

A verification repeat uses exactly the same eight explicit experiment settings,
splits and seeds after this default change. It also records the complete per-row
feature config and fixes runner cleanup bookkeeping (an EPERM signal result must
be reconciled against a process inventory, and a failed runner must exit nonzero).
No new quality-driven configuration is added. This is the third phase iteration:
initial split-flaw attempt, corrected fixed sweep, and final reproducibility check;
socket canaries and early infrastructure failures are retained separately.

## Field-family coverage completion (iteration 4)

Acceptance review requires each typed field family to be removed separately,
in addition to the joint removal of type-specific extra features already measured.
Add `without_<type>_fields` for each type present in a corpus: person_name, address,
code and date on FEBRL/BPID; number and title on Abt-Buy; organisation on Leipzig.
These configurations remove every comparison feature for that type, including
its token measures. Retrieval inputs remain fixed, so this is a classifier-feature
ablation and does not measure the effect of hiding that type from retrieval.

The resulting finite pass repeats the prior configurations and adds only these
predeclared removals. Same partitions, seeds, model parameters and 900-second
per-corpus limits; confirmation remains unscored. No threshold or default is
selected from the historical invalid attempt. This is iteration 4 of the cap of 8.
