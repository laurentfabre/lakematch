# Lake/mdm/bench — how good is Zingg + Jev, and how to make it drastically better

*Measured 2026-09-19 on public labelled corpora. Everything here is public or synthetic data; nothing personal was sent
to Jev. Every Jev judgment is cached under `cache/`, so every table below re-renders for free.*

## Verdict

*Revised after an independent review by Codex on gpt-6-astra (`ASTRA_REVIEW.md`, 2026-09-19). Every headline number
reproduced; several conclusions did not survive and are corrected here. See "Independent verification" below.*

1. **Under default settings Zingg recovered 75 % of the true links** on FEBRL4 (5 000 × 5 000 person records),
   whether its labels came from Jev (F1 0.853) or from the ground truth (0.858; 12 rounds: 0.858). Recall was 0.32 when
   the `given_name` differed and 0.956 when it was equal. Blocking is the likeliest cause, but the final links cannot
   tell a pair never compared from a pair rejected, and no configuration sweep was run: this shows where Zingg loses
   links, not why.
2. **Nearest-neighbour candidates recover every link** (recall@5 = 1.000). On the original FEBRL4, where every record
   has a partner, "always link the nearest neighbour" scores **1.0000 / 1.0000 / 0.9998 with no Jev and no model** —
   above the learned pipeline (0.9992 / 0.9991 / 0.9966). That task cannot show the value of Jev's labels.
3. **On the task that can — half the partners removed, so 2 500 records must be rejected —** nearest neighbour alone
   falls to 0.667, Zingg reaches 0.841–0.862 (precision ≈ 1.000, recall 0.73–0.76; 0.849 with Jev labels), and the pipeline trained on **Jev
   labels only** reaches 0.964–0.994. Jev's confident labels: 2 173 kept of 2 400 asked over six runs, **0 wrong**.
4. **Jev's best role depends on how ambiguous the data is.** On clean data it is a near-perfect *labeller*. On
   ambiguous person data (BPID) it is confident on 9 % of pairs only and must be the *judge*: zero-shot **0.813**,
   validation-chosen stack **0.830** (gap not significant), published best 0.788 on a different split.
5. **Combining pays on one dataset out of four.** Stack chosen on validation: Amazon-Google 0.705 → **0.800**
   (+9.5, 95 % CI [+4.6, +14.5]); no gain on Walmart-Amazon, a loss on Abt-Buy, a probable +1.7 on BPID. An earlier
   version reported the best of 15 stacks *by test score* (0.826 / 0.924 / 0.922 / 0.849): optimistic by 0.5–2.6.
6. **Comparisons with published numbers are indicative only**: different test subsets and selection protocols.

## State of the art (published, test F1 × 100)

| Dataset | Magellan (Zingg-class) | DeepMatcher | Ditto (fine-tuned) | GPT-4 zero-shot, best of 10 prompts | GPT-4o-mini zero-shot |
|---|---|---|---|---|---|
| Abt-Buy | 43.6 | 62.8 | 89.3 | 95.8 | 91.9 |
| Amazon-Google | 49.1 | 69.3 | 75.6 | 76.4 | 72.2 |
| Walmart-Amazon | 71.9 | 67.6 | 86.8 | 89.7 | 86.6 |
| Beer / Fodors-Zagats / iTunes-Amazon | 78.8 / 100 / 91.2 | 72.7 / 100 / 88.5 | 94.4 / 100 / 97.1 | n/a | n/a |
| BPID (person identity) | rules ≈ 60.8 | n/a | 75.2 (Sudowoodo 78.8 = best) | GPT-4-turbo 68.7 | Llama3-70B 72.9 |

Sources: Mudgal et al. SIGMOD 2018; Li et al. VLDB 2021; Peeters, Steiner & Bizer EDBT 2025 (test sets downsampled to
≈ 1 250 pairs, best prompt chosen on test); BPID, EMNLP 2024 Industry. **No published accuracy benchmark of Zingg
exists**; its classifier is Magellan-class. The literature's ranked levers, which the experiments below test:
blocking recall (Sparkly, VLDB 2023: top-k TF-IDF reaches 92–100 % recall at k = 10), LLM as labelling oracle
(arXiv 2606.28823: Ditto on LLM labels ≈ Ditto on human labels), cascade on the uncertain band, select-among-
candidates instead of independent pairs (ComEM, COLING 2025: +16 F1), verified clustering instead of connected
components, and — a negative result — hand-written rules *lower* F1 for most models (Peeters: −1.4 to −2.3).

## Corpora used

| Corpus | Why | Size used | Licence |
|---|---|---|---|
| Magellan / DeepMatcher, via `megagonlabs/ditto` `data/er_magellan` | fixed splits, comparable with published F1 | 9 datasets, 20 MB | Ditto repo Apache-2.0; upstream states none |
| FEBRL4 (`recordlinkage` package) | person records, end to end with ground truth | 5 000 + 5 000, 5 000 links | BSD-3 |
| BPID, zenodo 13932202 | closest public analogue of the `people` entity: name, e-mails, phones, addresses, dob; multi-valued, missing | 10 000 labelled pairs | Apache-2.0 |

Worth adding next (found, verified reachable, not run): OpenSanctions `sample_1000.json` (real multilingual person +
company pairs, CC-BY-NC), Leipzig *Affiliations* (organisation-name clustering, 330 clusters, CC BY 4.0 — the merchant
analogue), Splink `fake_1000` (has e-mails + cluster ids) and `historical_50k` for cluster-level metrics, the
Peeters/MatchGPT sampled test sets for exact comparability with GPT-4.

## Results

Decision thresholds are chosen on VALID and frozen on TEST; which signals enter a stack is also chosen on VALID
(section G). "Sample" = a reproducible random sample of the test split (≈ 600 pairs, 57–67 positives: a 95 % interval
on an F1 difference spans roughly ±5 to ±7 points). The Magellan splits are not clean: identical pairs sit in TRAIN
and TEST (96 on Amazon-Google, 16 on Abt-Buy) and 18 / 1 / 13 identical pairs carry contradictory labels.

### A. Jev alone, zero-shot, pairwise (`bench_pairs.py`)

| Dataset (pairs BOTH wordings judged) | generic (v0) | + identity rule (v1) | difference, 95 % CI |
|---|---|---|---|
| Beer (91 pairs, 14 pos.) | 0.933 | 0.933 | 0.0 |
| Fodors-Zagats (189, 22) | 0.952 | 0.927 | −2.6 [−9.1, 0.0] |
| iTunes-Amazon (109, 27) | 0.962 | 0.920 | −4.2 [−14.9, +5.8] |
| Walmart-Amazon (600, 57) | 0.860 | **0.926** | **+6.6 [+1.5, +12.4]** |
| Abt-Buy (603, 64) | 0.887 | 0.926 | +3.9 [−0.9, +8.9] |
| Amazon-Google (616, 67) | 0.667 | 0.662 | −0.4 [−6.5, +5.1] |

Same pairs for both wordings (`bench_audit.py`; an earlier version compared different samples). The identity rule is a
significant gain on Walmart-Amazon only. The 3-level Score and a plain Noul (v2: 0.933 / 0.952 / 0.964 on the small
sets) are equivalent; the Score keeps the review queue, so it stays. ≈ 450–640 input tokens per pair.

### B. What Jev adds to a Zingg-class matcher (`bench_cascade.py`)

| Dataset (sample) | classical alone | Jev alone | cascade (share of pairs sent to Jev) | stacked |
|---|---|---|---|---|
| Abt-Buy | 0.797 | 0.902 | 0.902 (32 %) | **0.944** |
| Amazon-Google | 0.702 | 0.649 | 0.715 (24 %) | **0.745** |
| Walmart-Amazon | 0.830 | 0.852 | **0.877** (19 %) | 0.870 |
| iTunes-Amazon / Fodors-Zagats | 0.982 / 1.000 | 0.962 / 0.952 | 0.982 / 1.000 (0 %) | 1.000 / 1.000 |

Generic wording (v0), 600-pair samples; NOT confirmed on the larger section-G evaluation (Abt-Buy stacked 0.944 here,
0.910 there), so read the stacked column as optimistic. Classical = per-field similarities + character-3-gram TF-IDF
cosine + model-number tokens, gradient boosting on the gold TRAIN split. Stack = logistic regression over [classical score, Jev's three probabilities, expected score], fitted
on VALID. The cascade buys most of the gain for a fifth to a third of the Jev calls.

### C. Select among candidates vs independent pairs (`bench_select.py`), same pairs, Jev v1 wording

| Dataset | pairs | pairwise F1 | select F1 | requests |
|---|---|---|---|---|
| Amazon-Google | 727 | 0.711 | **0.777** | 317 vs 727 |
| Walmart-Amazon | 563 | 0.925 | 0.927 | ≈ half |
| Abt-Buy | 646 | 0.931 | 0.917 | ≈ half |

Significant where near-duplicate candidates compete (Amazon-Google +6.5, 95 % CI [+1.8, +11.7], the review's
bootstrap), no measurable difference elsewhere ([−4.3, +5.1], [−6.3, +3.2]), and always about half the requests.

### D. The complete system end to end on FEBRL4 (`bench_febrl.py`, `bench_pipeline.py`)

| System | labels | P | R | F1 | wall time |
|---|---|---|---|---|---|
| Zingg, labels from Jev (6 rounds) | 100 | 1.000 | 0.744 | 0.853 | ≈ 4 min |
| Zingg, labels from ground truth (6 rounds) | 122 | 1.000 | 0.751 | 0.858 | ≈ 4 min |
| Zingg, Jev + ground truth on the pairs Jev deferred | 126 | 0.999 | 0.703 | 0.825 | ≈ 4 min |
| Zingg, ground truth, 12 rounds | 246 | 1.000 | 0.752 | 0.858 | ≈ 8 min |
| Zingg, ground truth, SSN hidden | 116 | 0.999 | 0.729 | 0.843 | ≈ 4 min |
| **control: nearest neighbour alone, always link** (all / no SSN / no SSN, no dob) | none | 1.000 | 1.000 | **1.0000 / 1.0000 / 0.9998** | < 5 s |
| top-k TF-IDF candidates + classifier on Jev labels | 365 kept of 400 asked, 0 human | 1.000 | 0.998 | 0.9992 | 19 s |
| same, SSN hidden | 353 of 400 | 1.000 | 0.998 | 0.9991 | 19 s |
| same, SSN and date of birth hidden | 333 of 400 | 1.000 | 0.993 | 0.9966 | 19 s |

On this task every record has a partner, so the control wins and a classifier can only lose links. The learned
pipeline is transductive (its training pairs are scored too); excluding them moves F1 by < 0.0003.

**Harder variant: half the partners removed** (`--unmatched 0.5`; 2 500 true links, 2 500 anchors to reject). The 0.5
decision threshold, τ = 0.9 and the arbitration bands are constants; "Jev overrides only when confident" was adopted
after seeing test results on the easy task.

| Fields | nearest neighbour, always link | NN + cosine cut learnt from Jev labels | classifier on Jev labels | + Jev arbitrates (0.02–0.98) | wider band (0.005–0.995) | Zingg, perfect labels | Jev tokens · cost |
|---|---|---|---|---|---|---|---|
| all ten | 0.667 | **0.9992** | 0.9748 | 0.9748 | 0.9944 | 0.841 (P 1.000, R 0.726) | 499 k · $0.021 |
| SSN hidden | 0.667 | 0.761 | 0.9356 | **0.9637** | **0.9637** | 0.862 (P 0.999, R 0.758) | 556 k · $0.023 |
| SSN + dob hidden | 0.667 | 0.919 | 0.9833 | **0.9848** | **0.9848** | not run | 349 k · $0.015 |

Jev's confident labels in these three runs: 1 122 kept of 1 200 asked, 0 wrong (2 173 of 2 400 over all six runs).
Zingg with Jev labels on this variant: 0.849 (P 1.000, R 0.738) — again as good as perfect labels; its limit is recall.

Where Zingg loses links — recall of `truth_r6` by what differs between the two records of a true link:

| Field that differs | links | recall when it differs | recall when it is equal |
|---|---|---|---|
| `given_name` | 1 611 | **0.320** | **0.956** |
| `surname` | 1 632 | 0.636 | 0.807 |
| any other field | — | 0.72–0.78 | 0.73–0.76 |

### E. BPID — ambiguous person profiles (`bench_bpid.py`; own 70/10/20 split, so indicative against the paper)

| Matcher | P | R | F1 |
|---|---|---|---|
| classical, 7 000 gold labels | 0.755 | 0.742 | 0.749 (0.780 on the full test split) |
| **Jev zero-shot** | 0.742 | 0.900 | **0.813** |
| **stack: classical score + Jev** | 0.778 | 0.905 | **0.837** |
| classical trained on Jev's confident labels (τ 0.9 → 47 labels / τ 0.7 → 186) | — | — | 0.437 / 0.639 |
| classical trained on all 900 Jev hard labels (77 % accurate) | 0.694 | 0.533 | 0.603 |
| reference: classical on 100 / 300 / 900 gold labels | — | — | 0.641 / 0.685 / 0.728 |

Jev is confident (τ 0.9) on 9 % of BPID pairs, and then 100 % right; at τ 0.8, 22 % and 98.9 %. Distilling it into a
feature-based student does not work on this kind of data: keep Jev in the decision.

### F. Few-shot, decomposition and full stacking (`bench_fewshot.py`, `bench_stack.py`)

Price: **$0.042 per million input tokens, output free** (`jev-1.13.0`, docs.typesafe.ai/models, 2026-09-19). Tokens are
measured (`cache/usage.jsonl`). Larger evaluation sets than in A–C (≈ 1 000 test pairs, ≈ 100–350 matches).

| Dataset | zero-shot | 6 random demos | 10 related demos | decomposition, stacked | **best stack** (signals) | $ / 1 000 pairs, best |
|---|---|---|---|---|---|---|
| Amazon-Google | 0.705 | 0.746 | **0.796** | 0.738 | **0.826** (classical + zs + dec + k10) | 0.104 |
| Walmart-Amazon | 0.916 | n/a | 0.917 | 0.905 | **0.924** (classical + zs + dec) | 0.031 |
| Abt-Buy | 0.930 | n/a | 0.917 | 0.878 | 0.922 (all four) — zero-shot alone is as good | 0.027–0.144 |
| BPID (people) | 0.813 | 0.810 | 0.789 (k20: 0.811) | **0.841** | **0.849** (classical + zs + dec) | 0.035 |

- **Related (nearest-neighbour) demonstrations** from the train split add +9.1 F1 on Amazon-Google (95 % CI
  [+4.1, +14.0]). LEAK: 71 of its 1 161 test pairs also sit verbatim in TRAIN and met their own labelled copy among
  the demos; without them and 25 VALID overlaps the gain is **+7.5 [+2.7, +12.6]**, still significant, and Abt-Buy's
  apparent loss becomes +1.3 [−2.6, +5.3] (`bench_audit.py`). Most test pairs also share a *record* with their demos
  (1 127 / 1 161): this measures matching among familiar records, as fine-tuned baselines do. Random demonstrations
  add half as much; 20 are no better than 6.
- **Decomposition** (attribute-level Nouls in the same request as the holistic Score, stacked) is the lever for
  people: BPID 0.813 → 0.841 for +25 % tokens. It does not help products.
- Stacking the classical score with Jev's answers looked like a universal win when read on test; chosen on validation it pays on Amazon-Google only (section G).
- Tokens per pair: zero-shot ≈ 450–660, decomposition ≈ 700–820, 10 related demos ≈ 1 800–3 000.

### G. Honest model selection and confidence intervals (`bench_stats.py`)

`bench_stack.py` prints every signal combination with its TEST F1; reading off the maximum is selection on test. Here
the combination is chosen by 5-fold cross-validated F1 on VALID only, then scored once on TEST. Intervals: paired
bootstrap over the test pairs, 2 000 resamples.

| Dataset | stack chosen on VALID | classifier | Jev zero-shot | stack | stack − zero-shot, 95 % CI | best-by-TEST (optimism) |
|---|---|---|---|---|---|---|
| Amazon-Google | classical + zs + k10 | 0.684 | 0.705 | **0.800** | +9.5 [+4.6, +14.5] | 0.826 (+2.6) |
| Walmart-Amazon | classical + dec + k10 | 0.831 | **0.916** | 0.919 | +0.3 [−3.0, +3.8] | 0.924 (+0.5) |
| Abt-Buy | classical + zs | 0.768 | **0.930** | 0.910 | −2.0 [−5.7, +1.5] | 0.922 (+1.2) |
| BPID | classical + zs + k10 | 0.734 | 0.813 | **0.830** | +1.7 [−0.3, +3.8] | 0.849 (+1.9) |

Significant: Jev zero-shot over the classifier on Walmart-Amazon (+8.7 [+3.5, +14.3]), Abt-Buy (+16.2 [+9.3, +23.6])
and BPID (+8.0 [+4.1, +11.9]), not on Amazon-Google (+1.6 [−5.4, +8.7]); ten related demonstrations on Amazon-Google
(+9.6 [+4.5, +14.7]). Not significant: every other prompt-side difference, including BPID decomposition (+2.8, read on
test) and demonstrations on BPID (−2.4 [−4.9, 0.0]).

### Cost of every experiment

| Experiment | Jev requests | input tokens | cost |
|---|---|---|---|
| A. zero-shot, small sets (3 variants) | 2 330 | ≈ 1.3 M | $0.06 |
| A. zero-shot, hard product sets (v0 + v1) | 5 400 | 2.96 M | $0.12 |
| C. select vs pairwise | 3 391 | 2.32 M | $0.10 |
| D. Zingg + Jev labels, toy febrl and FEBRL4 | ≈ 700 | 0.33 M | $0.01 |
| D. top-k pipeline, three variants | ≈ 1 900 | ≈ 1.43 M | $0.06 |
| E. BPID zero-shot | 1 700 | 1.12 M | $0.05 |
| F. few-shot + decomposition, four datasets | 21 024 | 39.0 M | $1.64 |
| **Total** | **≈ 36 500** | **≈ 48.5 M** | **≈ $2.04** |

Only row F is auditable from a ledger (`cache/usage.jsonl`, 39 035 991 tokens, $1.6395 — confirmed by the review); the
other rows come from totals printed at run time and the "≈" rows are partly estimated, so $2.04 is an estimate. The
later control runs (harder FEBRL4 variants) added ≈ 1.4 M tokens, $0.06. A stack that uses both the zero-shot answer
and the attribute answers pays two requests (e.g. BPID 660 + 824 = 1 484 tokens a pair), which an earlier version
under-counted. In production terms: linking the 10 000 FEBRL4 records cost **$0.011** (400 Jev labels asked, 365 kept, 254 k tokens); judging 1 000
ambiguous person pairs with the best BPID stack costs **$0.035**.

### Against GPT-4o

GPT-4o list price as supplied by Laurent (2026-09-19, not re-verified): $2.50 / M input, $10.00 / M output. Jev: $0.042 / M
input, output free — **59.5 × on input tokens**. GPT-4o cost per pair is estimated as Jev's measured zero-shot input
tokens + 5 output tokens (forced yes/no); F1 is GPT-4o zero-shot from Peeters et al. (EDBT 2025), downsampled test sets.

| Dataset | Jev zero-shot | Jev pick (chosen on validation) | GPT-4o zero-shot (published) | Jev best $ / 1 000 | GPT-4o $ / 1 000 (est.) | ratio |
|---|---|---|---|---|---|---|
| Amazon-Google | 0.699 | **0.800** | 0.736 | 0.098 | 1.43 | 15 × |
| Walmart-Amazon | 0.918 | **0.918** (zero-shot is the pick) | 0.867 | 0.025 | 1.54 | 62 × |
| Abt-Buy | 0.930 | 0.930 | **0.940** | 0.027 | 1.64 | 61 × |
| BPID (people) | 0.813 | **0.830** | n/a (GPT-4-turbo 0.687) | 0.153 | 1.70 | 11 × |

Every experiment here: $2.04 with Jev, ≈ $123 at GPT-4o prices. One million zero-shot product pairs: ≈ $25 vs ≈ $1 550.

## Independent verification (Codex, gpt-6-astra)

Run in a read-only sandbox, offline, on an isolated copy (code + caches + public data only). Full text: `ASTRA_REVIEW.md`.

| Finding | Severity | Action |
|---|---|---|
| Every headline number reproduces from the caches | confirmed | — |
| Nearest neighbour alone beats the learned pipeline on FEBRL4 (1.0000 / 1.0000 / 0.9998) | critical | control added; harder half-unmatched task built and run |
| Test pairs among their own demonstrations (71 Amazon-Google, 16 Abt-Buy) | critical | `bench_audit.py`: gain +7.5 [+2.7, +12.6] without them |
| "Best stack" chosen by TEST F1 | critical | `bench_stats.py`, corrected before the review landed and confirmed by it |
| "Blocking is the ceiling" asserted, not shown | major | reworded; no sweep run |
| Stacks using zero-shot + attribute answers priced as one request | major | token counts corrected; no pick affected |
| Different samples in table A; two report crashes; float threshold grid; "1 051 asked"; unsaved BPID experiments | minor | all fixed (`bench_bpid_students.py` reproduces the BPID figures exactly) |
| Only experiment F is ledger-auditable; GPT-4o figures are arithmetic, not a bill | minor | stated |

Not acted on: `parse()` strips apostrophes from 1 013 Abt-Buy test rows; measuring the effect needs new judgments.

## What to change in the MDM (ranked by measured effect)

1. **Generate candidates by nearest neighbour and measure their recall first:** top-k character-n-gram TF-IDF over
   the concatenated match fields (k = 5–10) kept every FEBRL4 link, where default Zingg recovered 75 %. Then **use
   Jev's confident labels to learn when to say no** (0.667 → 0.94–0.999 on the half-unmatched task, no human label). Zingg cannot take external candidate pairs, so for `people` this means the
   matcher of `bench_pipeline.py` replaces Zingg's `train`/`match`, or Zingg is kept as a second opinion only.
2. **Stack only where validation says it pays** (similarity features → gradient boosting → [its score + Jev's
   answers] → logistic regression): +10 on Amazon-Google, a probable +1.7 on people, nothing on the electronics sets,
   where plain zero-shot Jev is the pick. Where cost matters, send Jev only the band the classifier is unsure about
   (19–32 % of pairs on the product sets, 1–11 % on FEBRL4).
3. **Let Jev label first when the data is clean, and judge when it is ambiguous.** Tell them apart with one number:
   the share of pairs on which Jev is confident at τ = 0.9 (FEBRL4: ≈ 90 %; BPID: 9 %).
4. **Ask Jev to select among an anchor's top-4 candidates** rather than judging pairs one by one wherever
   near-duplicates compete (merchants, product-like strings): half the cost, up to +6.6 F1.
5. **Override only on confidence.** Jev replaces the classifier's decision when it is sure (a pick, or a firm
   "none") and otherwise the classifier stands — dropping a link whenever Jev hesitated cost 52 true links.
6. **Add a domain identity rule only where entities have versions or variants** (products, editions, merchants with
   branches); leave it out for people.
7. Not tested here, next in the literature's order: verified-merge or centre clustering instead of connected
   components once clusters exceed two records (FEBRL3, Splink `historical_50k`, MusicBrainz 20K are the corpora).

## Reproduce

```bash
source ../zingg_env.sh
python3 bench_pairs.py run Structured_Beer --variant v0 && python3 bench_pairs.py report      # system Python (typesafe_sdk)
$ZINGG_VENV/bin/python bench_cascade.py --variant v1
python3 bench_select.py run Structured_Amazon-Google --anchors 250 && python3 bench_select.py report
$ZINGG_VENV/bin/python bench_febrl.py prepare && $ZINGG_VENV/bin/python bench_febrl.py run --labeller jev --rounds 6
$ZINGG_VENV/bin/python bench_pipeline.py --k 5 --labels 400 --drop soc_sec_id
python3 bench_bpid.py ask && $ZINGG_VENV/bin/python bench_bpid.py report
```

Cost of everything: ≈ 36 500 Jev requests, ≈ 48.5 M input tokens, ≈ $2.04 (see the cost table).

## Caveats

- Test *samples* of ≈ 600 pairs carry ≈ ±4 F1 points of noise; the small full test sets hold 14–27 positives.
- Published LLM numbers use the best of 10 prompts chosen on the test set and downsampled test sets; BPID has no
  official split. Comparisons with the literature are indicative.
- FEBRL4 is synthetic and one-to-one; real contact data has clusters larger than two, which these runs do not test.
- The classical matcher here is mine (scikit-learn), stronger than the published Magellan numbers; it stands in for
  Zingg's classifier, not for Zingg's blocking.
- Zingg was run with default settings and 6–12 active-learning rounds, with no sweep of `labelDataSampleSize`,
  `numPartitions`, field match types or thresholds. An expert might configure it better; these runs do not establish
  a structural ceiling.
