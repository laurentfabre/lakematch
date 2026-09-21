# LF-B iteration 1 — first candidate-union comparison

Prerequisite: Phase A frozen at commit `96edbf8`; generator and all data/split
hashes committed before comparison. Evaluate **validation only**, 4,000 ERP
anchors against 4,000 CRM records from 2,000 whole families. No confirmation
records are generated or read. Historical public-corpus results are unchanged.

Hypothesis: complementary normalized-name, lexical-token and character-trigram
retrieval recover positives missed by exact identifiers within the approved
candidate, pre-join, time and memory envelope. No classifier or AI call runs.

Four predeclared alternatives, each at the same limits:

1. Exact normalized identifier + jurisdiction.
2. (1) union exact accent/punctuation/legal-suffix-normalized name, across countries.
3. (2) union postings for the two least-frequent available name tokens within country.
4. (3) union postings for the three least-frequent available name character trigrams.

Top-k ranking is fixed before evaluation: 2×exact identifier/jurisdiction,
1×exact normalized name, token Jaccard, trigram Jaccard, 0.2×exact street/postcode,
0.1×same country, then opaque CRM key as a deterministic tie break. These weights
are retrieval priorities, not match probabilities or an auto-merge threshold.

**Equal bounds:** 50 unique CRM candidates per ERP **after union**, 2m retained
pairs, 20m raw posting visits (including duplicate retrieval across methods),
4 GiB measured process peak memory, 120 seconds per alternative, 600 seconds outer
experiment. Source-row bound is 20,000 per side. Whole-run cap failure is a failed
alternative, never a reason to remove anchors. Python peak RSS is measured after
each alternative; this is an observed feasibility gate, not a hard OS allocation
reservation. No Spark, SQL warehouse, cloud job or AI inference is started.

Report every anchor, total known positives, per-stratum pre/post-cap recall,
cap losses, retained pairs, posting visits, method provenance, timings and peak
RSS. Truth is used only after candidate retrieval. Synthetic truth is complete;
this does not change unknown-label semantics for historical public corpora.
Persist raw candidate receipts in ignored local artifacts and compact hashes and
metrics in the repository. Never use sampled development negatives as precision
evidence. Auto-merge quality is not measured by this experiment.

Run contract/retrieval unit tests before the comparison. Select the **cheapest
passing alternative by retained pairs**, then posting visits, then declared order.
Do not tune after looking at confirmation. Additional development follows the
eight-experiment LF-B phase cap and must record a new plan if the hypothesis or
configuration changes.
