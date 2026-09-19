# Predeclared evaluation protocol

Declared 2026-09-19 before the new engine's ZR-2 ablations or ZR-3 method comparisons.
This document is a plan, not passing evidence. `goal.md` and `spec/BRIEF.md` retain authority.

The original FEBRL4 smoke runs in `ENGINE.md` are development-only. Their 80 labelled anchors,
their predictions and every historical prototype result must never be presented as an untouched
holdout. The benchmark harness must create and checksum manifests before training or selection.

For the FEBRL4 half-unmatched confirmation, reserve **seed 2026091901**. Use distinct namespaced
random streams for entity partitioning and partner removal. Assign whole truth entities to
60% training, 20% validation and 20% confirmation before removal, and retain the same entities
across all-field / SSN-hidden / SSN+DOB-hidden variants. Remove half the right-side partners
within each partition. Freeze the actual pair/record manifests, their hashes, and the exact RNG
algorithm before any evaluation. Do not score the confirmation partition until the model,
feature order, candidate spec and decision policy are frozen. A failed confirmation is retained;
the seed is never cycled to obtain a passing score. These are new unexposed split/removal outcomes
from a historically exposed corpus, not a new independent source population.

The latency acceptance must still process the full 5,000-left / 2,500-right half-unmatched
record universe, not just the held-out fifth. Restrict supervised training to its declared entity
partition and report the exact scope of confirmation scoring. Full-universe transductive retrieval
and strictly record-disjoint retrieval are distinct settings and need separate labels in reports.

Official product/citation splits and entity-disjoint evaluation must remain separate report rows.
Canonicalize each record using lossless sorted-key serialization; canonicalize pair orientation,
detect exact/reversed overlaps and conflicting labels, and record the resolution counts.
Do not strip apostrophes or concatenate multi-valued attributes irreversibly. Exclude conflicts
from primary supervised metrics and report them separately. Shared records must be reported;
where reliable identity labels permit it, construct a separate entity-disjoint split.

Select candidate methods at equal final pair budgets and separately report pre-top-k join volume,
hot-key loss and candidate recall. Candidate IDF may use unlabeled records from the target split
as an explicitly transductive retrieval statistic. Learned features, label policies and model
parameters fit training only; thresholds and method choices use validation only. Inductive and
transductive settings must not be conflated.

The default-selection primary score is macro validation F1 with equal weight per corpus
(FEBRL4, BPID, Abt-Buy, Amazon-Google, Walmart-Amazon, DBLP-ACM, Leipzig Affiliations).
Within FEBRL4, all-field and SSN-hidden half-unmatched tasks split that corpus's weight equally;
original and SSN+DOB-hidden rows are diagnostics. Clustering choices are selected separately,
weighting FEBRL3 and historical_50k equally and reporting both pairwise F1 and B-cubed.

Always include nearest-neighbour-only and a simple threshold baseline. Use 2,000 paired bootstrap
resamples (seed 2026091902), by entity/anchor where possible. Retain the simpler/lower-cost method
when the paired interval for its quality difference includes zero, subject to the fixed acceptance
thresholds. Levenshtein remains the specified default unless a separately recorded decision changes
it; UDF comparisons do not make Jaro-Winkler part of the default accelerated path.

Every sweep must declare its exact finite configurations, datasets, resource budgets and timeout
before execution. No sweep has started. Model selection may not use confirmation scores, cached
LLM judgments overlapping evaluation truth, or the previous smoke-run predictions. Optional live
labelling remains disabled; cached public judgments stay in `spec/bench/cache/`.

Timing begins before Spark session creation and ends after outputs and cleanup. Record corpus
preparation/model download separately. Remote provisioning, execution, DBUs and unreconciled
billing are separate observations; missing billing is never zero. The 60-second gate applies to
the specified local half-unmatched reproductions, not to remote startup or the original smoke.
