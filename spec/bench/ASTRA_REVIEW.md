**The cached results mostly reproduce; the strongest conclusions do not.** The principal problems are test-based model selection, exact demonstration leakage, understated stack costs, and an unsupported causal attribution to Zingg’s blocker.

All checks were read-only and offline. Pipeline reproduction used an in-memory cache-only adapter and the supplied FEBRL CSVs; no API requests or files were written. References below are relative to `mdm/bench/`.

**(a) Verdict table**

| Claim | Status | Evidence |
|---|---|---|
| Zingg FEBRL F1: Jev **0.853**, truth **0.858**, 12 rounds **0.858**, no SSN **0.843** | REPRODUCED | Exact F1: **0.853211 / 0.857796 / 0.858317 / 0.842641**. |
| Zingg Jev + deferred truth: **0.825** | REPRODUCED | **0.825270**. |
| Replacement pipeline **0.9992 / 0.9991 / 0.9966** | REPRODUCED WITH CAVEAT | **0.999199 / 0.999099 / 0.996588**; transductive evaluation includes training examples. |
| Replacement demonstrates Jev’s labelling value | OVERCLAIM | **TF-IDF top-1 alone achieves 1.0000 / 1.0000 / 0.9998**, exceeding all three learned pipelines. |
| Given-name recall **0.320 versus 0.956** | REPRODUCED | **515/1,611 versus 3,240/3,389**. |
| “Zingg’s blocking is the ceiling” | OVERCLAIM | Final links do not identify whether missing pairs were blocked or rejected by classification. |
| BPID zero-shot **0.813**, best stack **0.849** | REPRODUCED WITH CAVEAT | **0.813472 / 0.849389**; stack combination selected using TEST. VALID-selected stack: **0.830140**. |
| Amazon zero-shot **0.699**, related demos **0.796**, best stack **0.826** | REPRODUCED WITH CAVEAT | **0.699346 / 0.795539 / 0.825623**; exact demonstration leakage and TEST selection. |
| Walmart best **0.924** | REPRODUCED WITH CAVEAT | **0.923913**; TEST-selected, improvement over zero-shot not significant. |
| Abt zero-shot **0.930** | REPRODUCED | **0.930000**, higher than best stack **0.921569**. |
| Pairwise/select table C | REPRODUCED WITH CAVEAT | All three F1 rows reproduce; report subsequently crashes on an unrelated cache format. |
| Table B | REPRODUCED WITH CAVEAT | Reproduces using **v0**, not the requested **v1** command. |
| Every report/table reproduces as supplied | NOT REPRODUCED | Two report crashes; stale table A values; undocumented BPID experiments. |
| F costs **21,024 requests / 39.0M tokens / $1.64** | REPRODUCED | **39,035,991 input tokens; $1.639511622**. |
| Total spend **≈$2.04** | CANNOT VERIFY | Ledger contains only experiment F. |
| Advertised best-stack costs | NOT REPRODUCED | Independently evaluated zero-shot request omitted from cost. |
| Zingg label counts and original execution times | CANNOT VERIFY | Training artifacts and run logs absent. |
| Superiority over published Ditto/GPT/Sudowoodo results | OVERCLAIM | Different evaluation subsets/protocols; published values themselves cannot be verified offline. |

The FEBRL confusion counts independently reproduce:

| System | TP | FP | FN |
|---|---:|---:|---:|
| Zingg, Jev | 3,720 | 0 | 1,280 |
| Zingg, truth, six rounds | 3,755 | 0 | 1,245 |
| Zingg, truth, twelve rounds | 3,759 | 0 | 1,241 |
| Zingg, Jev + truth | 3,514 | 2 | 1,486 |
| Zingg, truth, no SSN | 3,644 | 5 | 1,356 |
| Pipeline, all fields | 4,992 | 0 | 8 |
| Pipeline, no SSN | 4,991 | 0 | 9 |
| Pipeline, no SSN/DOB | 4,966 | 0 | 34 |

**Numerical discrepancies and reproduction failures**

| Location | README | Current output |
|---|---|---|
| A: Amazon v1 | 0.662 | **0.705**, 1,161 test rows |
| A: Walmart v1 | 0.914 | **0.916**, 999 test rows |
| A: Abt v1 | 0.926 | **0.930**, 1,027 test rows |
| D: judgments “asked for” | 1,051 | **1,200 requested; 1,051 retained** |
| E: 900 hard labels; associated F1 and gold-size experiments | Several reported results | **No reproducing code/protocol supplied** |

For section B, tuples below are **classical / Jev / cascade / stack; percentage sent to Jev**:

| Dataset | README, reproduced with v0 | Requested `--variant v1` |
|---|---|---|
| Amazon | .702 / .649 / .715 / .745; 24% | **.684 / .726 / .737 / .745; 18%** |
| Walmart | .830 / .852 / .877 / .870; 19% | **.831 / .874 / .908 / .910; 8%** |
| Abt | .797 / .902 / .902 / .944; 32% | **.768 / .897 / .925 / .912; 29%** |
| iTunes | .982 / .962 / .982 / 1.000; 0% | **.982 / .943 / .982 / .982; 0%** |

Fodors reproduces under both variants. The other small-set table A values reproduce.

`bench_pairs.py report` prints product results, then fails trying to read nonexistent `data/bpid/test.txt` because its cache glob is unrestricted (`bench_pairs.py:200–205`). `bench_select.py report` prints its three rows, then encounters pipeline selection caches using `id`, causing `KeyError: 'key'` (`bench_select.py:111–113`).

**(b) Findings ranked by severity**

**Critical — Exact test pairs appear among their own labelled demonstrations.**  
`bench_fewshot.py:93–112` selects nearest TRAIN examples without excluding the query pair. `bench_pairs.py:85` hashes record content without split identity.

| Cached evaluation | Test rows | Exact TRAIN-pair overlap | Own pair actually in k10 demos | Overlap with cached VALID | TRAIN-or-VALID overlap |
|---|---:|---:|---:|---:|---:|
| Amazon | 1,161 | 71 | **71** | 51 | **96** |
| Walmart | 999 | 0 | 0 | 0 | 0 |
| Abt | 1,027 | 16 | **16** | 11 | **16** |
| BPID | 800 | 0 | 0 | 0 | 0 |

Amazon’s 71 leaked demonstrations include seven positive pairs. These duplicates already exist in the raw data; quote stripping did not create them.

Removing TEST pairs appearing in TRAIN or cached VALID, while retaining the original thresholds:

| Dataset | Remaining rows / positives | Zero-shot | k10 |
|---|---:|---:|---:|
| Amazon | 1,065 / 122 | **0.713781** | **0.795181** |
| Walmart | 999 / 94 | 0.918033 | 0.917127 |
| Abt | 1,011 / 105 | **0.934673** | **0.947867** |

Thus Amazon’s gain falls from **9.62 to 8.14 F1 points**, but does not disappear. Abt’s apparent degradation also disappears.

Shared-record exposure is much broader: k10 demonstrations contain at least one exact query record for **1,127/1,161 Amazon**, **919/999 Walmart**, and **923/1,027 Abt** test rows. Both query records appear somewhere among the demonstrations for **827 / 405 / 509** rows, respectively. This evaluates mostly familiar-record matching, not unseen-entity generalization.

A supplementary near-duplicate screen—both record strings having `SequenceMatcher` similarity ≥0.95, allowing reversed orientation—found **35 / 109 / 112 additional non-exact** query/demo overlaps. This is a diagnostic definition, not proof those pairs are semantically identical.

**Critical — “Best stack” uses TEST labels to select the model.**  
`bench_stack.py:61–73` evaluates 15 combinations and chooses `max(rows_out)` by TEST F1. VALID fitting and threshold tuning do not prevent this leakage.

I instead selected the combination with highest pooled five-fold out-of-fold VALID F1, using the existing VALID threshold procedure, then refitted on VALID:

| Dataset | TEST-selected F1 | VALID-selected combination | Its TEST F1 | Observed selection uplift |
|---|---:|---|---:|---:|
| Amazon | 0.825623 | classical + zs + k10 | **0.800000** | **2.56 points** |
| Walmart | 0.923913 | classical + dec + k10 | **0.918919** | **0.50 points** |
| Abt | 0.921569 | classical + zs | **0.910000** | **1.16 points** |
| BPID | 0.849389 | classical + zs + k10 | **0.830140** | **1.92 points** |

These are observed selection uplifts, not estimates of expected bias across new datasets. Existing duplicate contamination remains in this comparison.

**Major — Stack costs omit an input actually used by the evaluated model.**  
`bench_stack.py:53–54` uses the original zero-shot probabilities plus decomposition Nouls. Lines `63–64` omit zero-shot cost on the assumption that decomposition’s holistic Score substitutes for it.

It does not: the two probability vectors differ on **747/1,764 Amazon**, **537/1,552 Walmart**, **262/1,604 Abt**, and **977/1,100 BPID** shared unique keys. Corrected costs and actual substitution results appear below.

**Major — Blocking causation is asserted without candidate-level evidence.**  
`README.md:8–14,190–193,230–231`; `bench_febrl.py:57–61`.

The tested configurations use `labelDataSampleSize=0.1`, `numPartitions=8`, exact postcode/state matching, and fuzzy matching for other fields. There is no controlled sweep of these settings, classifier thresholds, or substantially larger label budgets. Twelve rounds increase recovered links from **3,755 to 3,759**; that alone does not establish a blocking ceiling.

Alternative explanations remain: restrictive blocking, a name-sensitive classifier, conservative acceptance thresholds, insufficient/inappropriate labels, or field configuration. Replacing the whole system changes several components simultaneously.

The strongest missing control is **top-1 TF-IDF alone: F1 1.0000 / 1.0000 / 0.9998**. FEBRL does not establish that Jev labels improve this baseline.

**Major — FEBRL is transductive, with evaluation feedback in algorithm development.**  
`bench_pipeline.py:113–170,179–180`.

- Runtime ground truth supports recall diagnostics, label auditing and scoring; I found **no direct truth-to-prediction dependency**.
- Training candidates remain in the scored universe.
- Decision threshold **0.5**, confidence **0.9**, and arbitration bands are constants—not thresholds learned from Jev-labelled validation data as the docstring claims.
- The comment that rejecting uncertain selections “cost 52 true links” explicitly documents ground-truth feedback influencing the arbitration policy.

Excluding every A-anchor represented in confident training labels yields F1 **0.999138 / 0.999033 / 0.996352**. The measured resubstitution inflation is small.

The one-best rule privileges FEBRL’s structure, but an ablation accepting **every** candidate with probability ≥0.5 produces **identical headline counts** in all three variants. It does not explain the observed gap.

**Major — Evaluation populations and labels are not cleanly controlled.**  
`bench_fewshot.py:75,88–90`; `bench_pairs.py:85,163–166`.

Evaluation membership is “whatever keys currently exist in the v1 cache.” Selection experiments append judgments to that cache, expanding earlier evaluation samples. This explains stale table A values and prevents interpreting v0→v1 changes as a controlled prompt-only comparison.

There are also conflicting labels for identical parsed pairs: across supplied splits, **18 Amazon keys, one Walmart key and 13 Abt keys** have contradictory labels. Abt’s cached VALID and TEST each include an internally contradictory duplicate pair. Identical content receives the same cached model answer but conflicting scoring targets.

**Major — Several experiments cannot be reconstructed from supplied artifacts.**

- Zingg models, training labels and logs are missing. The scoring script therefore prints zero label counts; this means **missing evidence**, not that original training used zero labels.
- Saved Zingg configs reference the original workspace.
- Original 19-second/four-minute/eight-minute timings cannot be established.
- `bench_bpid.py:185–194` implements only the τ=0.9 student experiment. The τ=0.7 count **186** can be verified, including **four incorrect labels**, but the reported **0.639** model result is undocumented. The **900 hard-label / gold 100,300,900** experiments likewise lack code specifying their protocol. Only **600 cached TRAIN pairs** exist.

**Minor — Threshold implementation changes reported answers.**  
`bench_cascade.py:82–84` uses floating-point `np.arange`; `bench_pairs.py:178–180` uses integer-derived thresholds and another tie-break.

For quantized probabilities, `0.30000000000000004` excludes values exactly equal to `0.30`. Replacing the grid with exact integer-derived hundredths, retaining first-max tie-breaking, changes zero-shot F1:

| Dataset | Current few-shot report | Exact-grid result |
|---|---:|---:|
| Amazon | 0.699346 | **0.704698** |
| Walmart | 0.918033 | **0.916201** |
| BPID | 0.813472 | **0.812903** |

Also, `p_same()` uses top-level probability, whereas cascade “Jev alone” uses `score/2` (`bench_cascade.py:119–121`). These are different decision statistics, not interchangeable baselines.

**Minor — Parsing and schema discovery are fragile.**

- `bench_pairs.py:76` removes apostrophes/backticks, including meaningful text: `8.5 ' portable` becomes `8.5 portable`; `Here 's` becomes `Here s`. It changes fields in **1,013/1,916 Abt test rows**. Its F1 effect cannot be isolated without new judgments.
- `bench_cascade.py:47` discovers feature columns from each batch’s first 50 rows. Missing/reordered schemas could silently misalign features or cause dimensional errors. **All supplied split schemas pass this check**, so no current numerical effect was demonstrated.

**Checks that passed:** product classical and demonstration TF-IDF vectorizers fit TRAIN only. Stackers fit VALID and tune thresholds using out-of-fold VALID predictions. BPID’s **7,019/991/1,990** hash split has no canonical exact/mirrored pair overlap or exact-record cross-split overlap. Its raw-line hash remains sensitive to serialization, orientation and labels, but that vulnerability did not produce observed overlap here.

Zingg’s cluster expansion is fair for cross-source pairwise scoring (`bench_febrl.py:148–155`). The three principal runs contain only two-record clusters. Two hybrid triplets and five no-SSN triplets account for their respective **two/five false positives**. No duplicate predicted links were found.

**(c) Bootstrap results**

**20,000 paired bootstrap replicates**, seed **20260919**. Tables use resampling by identical left-record anchor, keeping compared predictions paired; ordinary pair bootstraps gave the same significance conclusions. Thresholds and fitted models remain fixed.

Intervals are conditional on the cached evaluation population. They do not correct TEST-based selection, demonstration leakage, training uncertainty, or all dependencies through shared right-side records.

| Comparison | F1 A, 95% CI | F1 B, 95% CI | B−A, 95% CI | Excludes zero? |
|---|---|---|---|---|
| Amazon zero-shot → k10 | .699 [.636,.758] | .796 [.739,.845] | **+.096 [.043,.152]** | Yes |
| Amazon zero-shot → TEST-best stack | .699 [.636,.758] | .826 [.777,.869] | **+.126 [.077,.178]** | Yes, selection caveat |
| Walmart zero-shot → advertised best stack | .918 [.872,.957] | .924 [.880,.960] | +.006 [−.022,.036] | No |
| Abt zero-shot → TEST-best stack | .930 [.890,.964] | .922 [.879,.957] | −.008 [−.044,.026] | No |
| BPID zero-shot → TEST-best stack | .813 [.783,.843] | .849 [.821,.876] | **+.036 [.015,.057]** | Nominally; selection caveat |
| Amazon pairwise → select | .711 [.632,.783] | .777 [.707,.838] | **+.065 [.018,.117]** | Yes |
| Walmart pairwise → select | .925 [.866,.971] | .927 [.873,.972] | +.003 [−.043,.051] | No |
| Abt pairwise → select | .931 [.881,.971] | .917 [.865,.959] | −.015 [−.063,.032] | No |

After selecting stack combinations on VALID:

| Dataset | Zero-shot → VALID-selected stack | Difference, 95% CI |
|---|---|---|
| Amazon | .699 → .800 | **+.101 [.052,.153]** |
| Walmart | .918 → .919 | +.001 [−.029,.032] |
| Abt | .930 → .910 | −.020 [−.056,.014] |
| BPID | .813 → .830 | **+.017 [−.003,.037]** |

**BPID’s stack advantage is no longer significant under this selection protocol.**

After removing Amazon’s exact TRAIN/VALID-overlapping test pairs, the k10 gain remains **+.0814**, CI **[+.0305,+.1339]**. This does not remove shared-record or near-duplicate exposure.

The README’s universal “≈±4 points” heuristic is unsupported; Amazon pairwise/select intervals are substantially wider.

**(d) Recomputed costs**

At **$0.042/M input tokens**, output free, the complete supplied ledger contains:

| Experiment F dataset | Requests | Input tokens | Output tokens | Jev cost |
|---|---:|---:|---:|---:|
| Amazon | 9,180 | 14,172,218 | 315,792 | $0.595233 |
| Walmart | 3,106 | 4,780,525 | 187,913 | $0.200782 |
| Abt | 3,238 | 5,553,763 | 195,899 | $0.233258 |
| BPID | 5,500 | 14,529,485 | 209,000 | $0.610238 |
| **Total logged** | **21,024** | **39,035,991** | **908,604** | **$1.639512** |

Earlier cost-table rows have no corresponding ledger entries:

| README experiment | Stated input | Cost implied by stated input | Published cost | Verification |
|---|---:|---:|---:|---|
| A small sets | ≈1.3M | ≈$0.05460 | $0.06 | Input unverified |
| A hard products | 2.96M | $0.12432 | $0.12 | Input unverified |
| C select | 2.32M | $0.09744 | $0.10 | Input unverified |
| D Zingg labels | 0.33M | $0.01386 | $0.01 | Input unverified |
| D pipeline | ≈1.43M | ≈$0.06006 | $0.06 | Input unverified |
| E BPID | 1.12M | $0.04704 | $0.05 | Input unverified |
| Overall | ≈48.5M | ≈$2.037 | ≈$2.04 | **Total unverified** |

The approximations prevent treating the small-set rounding as a definite arithmetic error. The **254k/$0.011** FEBRL production claim is also unlogged. Its label stage requested **400**, not 365, judgments; 365 were retained. Arbitration requires additional requests.

Correcting stack accounting:

| Evaluated configuration | Advertised $/1,000 | Corrected $/1,000¹ | F1 if decomposition’s Score actually substitutes for zero-shot |
|---|---:|---:|---:|
| Amazon, all four | $0.103854 | **$0.127038** | **.821**, versus .826 |
| Walmart, classical+zs+dec | $0.031201 | **$0.056275** | **.919**, versus .924 |
| Abt, all four | $0.144075 | **$0.170829** | .922 |
| BPID, classical+zs+dec | $0.034606 | **$0.062326** | **.829**, versus .849 |

¹ Conditional on the unverified `ZS_TOKENS` constants at `bench_stack.py:33`. Abt zero-shot’s quoted **$0.027** is similarly conditional.

The HTML’s BPID projection of **$1.919** for 11,091×5 pairs becomes **$3.456** under corrected accounting (`matching-bench.html:339,360`).

GPT-4o arithmetic is internally consistent **as a hypothetical estimate**:

- Input-price ratio: **59.5238×**.
- Per 1,000 pairs using stated constants plus five output tokens: **$1.4300 / $1.5425 / $1.6425 / $1.7000**.
- Corrected GPT/stack cost ratios: **11.26× Amazon, 27.41× Walmart, 27.28× BPID**, instead of 14×/49×/49×.
- The quoted **≈$123** is `48.5M×$2.50/M + 36,500×5×$10/M = $123.075`.
- Five output tokens per request is not an equivalent-output assumption for composite decomposition requests. Repricing F’s actual logged input/output at GPT rates yields **$106.676**, versus **$98.641** with five output tokens/request. Neither is a measured GPT bill.
- One million pairs at 600 input plus five output tokens gives **$25.20 versus $1,550**, matching the approximate statement.

`jev_worker.py:40–68` counts successful returned requests and writes aggregate usage only after completion. Failed-attempt billing and interrupted batches are not fully auditable from this ledger.

**Published comparisons and proposed rewrites**

No supplied papers or published predictions permit independent verification of the literature numbers. Product results use different subsets from Ditto and the cited LLM evaluations; published best-of-ten prompts selected on TEST add another selection difference. BPID uses its own split and 800-row test subset. Full small-set comparisons are potentially population-comparable if the published splits are identical, but do not establish model equivalence with 14–27 positives.

The HTML repeats the principal overclaims, especially `matching-bench.html:126,240,319,342,377`. Its cost-provenance caveat at line 359 is more accurate than the README.

**(e) Sentences to rewrite**

| README location | Proposed wording |
|---|---|
| 8–11: “blocking is the ceiling”; “whenever” | “Under the tested configuration, Zingg recovered 75.1% of links. Recall was 32.0% when given names differed and 95.6% otherwise. Candidate-level diagnostics are needed to distinguish blocking from classification failures.” |
| 12–14: “Replacing the blocker fixes it” | “The replacement system reached F1 .9966–.9992 on this synthetic transductive task. Untrained top-1 TF-IDF alone reached .9998–1.0000.” |
| 55: thresholds always VALID/frozen TEST | “Decision thresholds use VALID, but the reported best signal combination was selected by TEST F1. Evaluation splits also contain duplicate pairs.” |
| 69, 96: superiority over published models | “These point estimates exceed some published values, but evaluation subsets and selection protocols differ; they do not establish superiority.” |
| 111–112: 1,051 asked for | “Across three variants, 1,200 judgments were requested; 1,051 confident labels were retained, with zero disagreements against ground truth.” |
| 149–151: related-demo gain | “Amazon k10 improved cached-test F1 from .699 to .796. After removing exact TRAIN/VALID-overlapping test pairs, the comparison was .714 to .795; shared-record exposure remains.” |
| 154: stacking helps everywhere | “Stacking improved Amazon’s point estimate. Walmart’s gain was small, Abt zero-shot was higher, and BPID’s VALID-selected improvement was not statistically significant.” |
| 139–140, 168, 186: measured costs and total | “The supplied ledger verifies experiment F at $1.639512. Earlier costs and the overall $2.04 estimate are not independently auditable from this bundle.” |
| 230–231: structural blocking failure | “Configuration and threshold exploration were limited; these runs do not establish a structural blocking ceiling.” |