# String similarity: what to use instead of Zingg's "Jaro-Winkler" and "affine gap"

*Research digest, 2026-09-19. Feeds `goals/goal_zingg_rewrite.md`. Numbers are as reported by the cited papers unless
marked (inference).*

## What Zingg actually runs (verified in source)

| Zingg name | Real measure | Consequence |
|---|---|---|
| `SJaroWinkler` "Jaro-Winkler" | `com.wcohen.ss.Jaro` — **plain Jaro**, no Winkler prefix bonus | fine on short single tokens and transpositions; weak on multi-token strings, reordering, long strings; no rarity weighting |
| `SAffineGap` "affine gap" | `com.wcohen.ss.MongeElkan` — **character-level** Smith-Waterman-style local alignment: match +5, mismatch −3, approximate match +3 for {d,t} {g,j} {l,r} {m,n} {b,p,v} {vowels}, gap open −5 / extend −1, scaled by `min(len) × 5` | good at abbreviations, truncations, containment; **no robustness to token reordering**; any string contained in a longer one scores ≈ 1.0 ("Al" vs "Alexander Smith") (inference from source); O(nm) over three matrices, ≈ 10× slower than Jaro (Cohen 2003). It is NOT the token-level Monge-Elkan (`Level2MongeElkan`), which Zingg does not use |

## Is anything better?

**"Replace Jaro with Jaro-Winkler": weak evidence.** Christen 2006 (average f-measure): given names Jaro .853 → Winkler
.891; surnames .601 → .588. Santos 2018 toponyms: +3 F1. JW over-scores short strings and shared prefixes (Splink notes
JW ≥ 0.7 admits "Rachael" for "Richard"; OpenSanctions damps it as `jw ** len`). On typo-heavy census person data
**normalised Levenshtein beat Jaro by 0.14 MaxF1** (Bilenko 2003: 0.865 vs 0.728). Spark has no Jaro/JW built-in before
4.3 (`jaro_winkler_similarity`, SPARK-57253, JW only). Keep JW as one optional feature, not as the upgrade.

**"Replace the affine gap with token/IDF measures": supported for multi-token fields.** Cohen, Ravikumar & Fienberg
2003: SoftTFIDF best overall (UVA MaxF1 0.89 vs TFIDF 0.79, Level2 JW 0.73; CoraATDV 0.85 / 0.84 / 0.76); TFIDF 1.2 s vs
JW ≈ 20 s. Caveat: token methods "perform poorly on the census-like dataset" (SoftTF-IDF 0.685 vs Levenshtein 0.865) —
so use them for addresses, company names and product titles, and per-token Levenshtein for person names. If a
Monge-Elkan-style feature is kept, make it symmetric with the m = 2 generalised mean (Jimenez et al. 2009).

**The largest measured gain is combining measures in a learned classifier**: Santos 2018, best single measure 57 F1,
gradient-boosted trees over all measures 78.9; Cohen's SVM "generally slightly outperforms" every single metric.

**Embeddings and LLMs.** They win on cross-script/transliterated names, company aliases and acronyms, product titles
and heavy OCR noise: LinkTransformer (ACL 2024) company aliases top-1 0.55 (Levenshtein) → 0.69 (off-the-shelf SBERT) →
0.83 (fine-tuned); product linkage 0.54 → 0.79 → 0.84. They do not clearly win on same-script single-token person names
with typos: with transliteration in front, Double Metaphone nearly matches a fine-tuned ByT5 (Blair & Bar, LREC-COLING
2024). LLM adjudication is ≈ 0.1–0.5 s per pair, "over four orders of magnitude slower" than fuzzy measures (Federal
Reserve FEDS 2025-092), so only as a cascade on the uncertain band (≈ 45 % faster at equal accuracy there).
Phonetic coding followed by exact comparison "should not be used" alone (Christen: f ≤ 0.5).

## What Spark SQL can express (Spark 4.1 / 4.2, Databricks)

- Built-ins: `levenshtein(a, b[, threshold])` (returns −1 past the threshold), `soundex`, array set functions
  (`array_intersect`, `array_union`, `array_except`, `arrays_overlap`, `array_distinct`, `array_size`), higher-order
  `transform` / `filter` / `aggregate` / `zip_with`, `sequence`, `regexp_*`, `split`, `translate`, `collate`
  (case/accent-insensitive equality, 4.0+); 4.2 adds `vector_cosine_similarity` and a `JOIN … NEAREST k BY` clause.
- Not built in: Jaro, Jaro-Winkler (until 4.3), Damerau-Levenshtein, any metaphone, n-gram helpers, string Jaccard /
  cosine. Databricks adds only `ai_similarity` (LLM-backed, billed, ranking-only, not a stable feature).
- Expressible with built-ins only: character q-grams (`transform(sequence(1, length(s)-q+1), i -> substring(s, i, q))`),
  Jaccard / Dice / overlap, TF-IDF cosine (explode + IDF join + group-by), symmetric token-level Monge-Elkan with a
  normalised-Levenshtein inner measure (`aggregate(transform(ta, a -> array_max(transform(tb, b -> …))))`), soft-Jaccard.
- UDF throughput (Splink issue #2875, PySpark 4.1, 100 M JW comparisons): Scala jar ≈ 48.9 M/s; rapidfuzz through a
  row or Arrow UDF ≈ 10 M/s, `mapInArrow` ≈ 12 M/s. Photon "doesn't support UDFs".

## Recommended features per field type (N = Spark-native, U = UDF on 4.1/4.2)

| Field | Features, by value per unit of compute |
|---|---|
| Person name (given / family tokens) | N exact match after lower + accent fold + `collate`, with a term-frequency/IDF feature for the matched value · N normalised `levenshtein` per token (threshold for early exit) · N swapped given/family flag, overlap coefficient, initial-vs-full match · U (N from 4.3) Jaro-Winkler per token · U Double Metaphone overlap as a weak flag (`soundex` is the native fallback). Cross-script: transliterate first or add an embedding cosine |
| Address | N standardise with `regexp_replace` + abbreviation map, then house number / unit / postcode equality flags · N IDF-weighted token cosine or Jaccard · N character 3-gram Jaccard/overlap · N symmetric token-level Monge-Elkan (m = 2) |
| Company / merchant | N legal-form stripping + exact flag + legal-form agreement flag · N TF-IDF cosine on character 2/3-grams (also the candidate generator; ING's production design) · N TF-IDF word cosine or SoftTFIDF with Levenshtein inner · N `levenshtein` on the space-stripped fingerprint + token-containment flag · U+GPU fine-tuned bi-encoder cosine (largest measured gain for aliases, highest cost) |
| Product title | N IDF-weighted token cosine · N model-number / numeric-token agreement · N character 3-gram cosine · U+GPU sentence-embedding cosine · LLM cascade on the uncertain band only |

## Not verified

Photon coverage per function (docs list only the category "String"); whether Spark 4.3.0 is released; `levenshtein`
under a collation; per-method averages in Cohen 2003 (figures only); rigorous benchmarks for Beider-Morse /
Daitch-Mokotoff / Cologne; embedding throughput per GPU.

## Sources

Cohen, Ravikumar & Fienberg 2003 (cs.cmu.edu/~wcohen/postscript/ijcai-ws-2003.pdf) · Bilenko et al. 2003
(wwcohen.github.io/postscript/intelligent-systems-2003.pdf) · Christen 2006
(users.cecs.anu.edu.au/~Peter.Christen/publications/mcd2006.pdf) · Jimenez et al. 2009 (generalised Monge-Elkan) ·
Santos et al. 2018 (IJGIS toponym matching) · LinkTransformer (aclanthology.org/2024.acl-demos.21.pdf) · Blair & Bar
(aclanthology.org/2024.lrec-main.838) · Federal Reserve FEDS 2025-092 · Zeakis et al. PVLDB 2023 · OpenSanctions
matchers (opensanctions.org/matcher) · Splink term-frequency guide and issue #2875 · ING EntityMatchingModel docs ·
Spark string/array/vector function pages · SPARK-57253 · Zingg and SecondString source.
