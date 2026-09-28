# String similarity for lakematch · 2026

*SIM-1 research and implementation candidates · reviewed 2026-09-27 · Spark 4.1.x*

## What / why

Catalogue **29 measures**, **27 distinct primary/documentation references** and
**7 papers published since 2021**, with **7 new built-in-expressible candidates** across four categories.
This extends [the earlier digest](similarity_sota.md) with explicit definitions, source provenance,
implementation contracts and a ranked shortlist. [sota_candidates.json](sota_candidates.json) is the
machine-readable counterpart; its IDs, shortlist, formulas and evidence correspond to this report.

The objective is to improve the product-title weakness identified in [METHODS](../../bench/METHODS.md)
while preserving person-name performance. Rank is an engineering hypothesis about gain per cost, not an
observed accuracy ordering. SIM-3 must compare against freshly measured Jaro-Winkler in the same run.

> Research establishes candidates. SIM-1 does not establish a Spark execution plan, Photon coverage,
> throughput, or a winner. Definition-only sources do not supply invented F1 scores.

## Contents

- [Evidence and scope](#evidence-and-scope)
- [Spark 4.1 contract](#spark-41-contract)
- [Ranked shortlist](#ranked-shortlist)
- [Measure catalogue](#measure-catalogue)
- [Implementation notes](#implementation-notes)
- [Validation and handoff](#validation-and-handoff)
- [References](#references)
- [License](#license)

---

## Evidence and scope

Search covered classical name/record matching, maintained metric definitions, recent embedding and LLM
linkage, and 2025–2026 matching research. This is a scoped review as of the date above, not an exhaustive
systematic review or a claim that a paper published in 2026 dominates every string-matching task.
Undated documentation has `year: null`; seven recent papers satisfy the date requirement without
counting access dates or counting an arXiv preprint and its proceedings version twice.

| Evidence | Checked result | Consequence for this project |
|---|---|---|
| [Bilenko 2003](#bilenko2003), Census, Table 3 | MaxF1: Levenshtein .865, Jaro .728, SoftTF-IDF .685, Jaccard .567 | Preserve per-field baselines; token methods can lose on noisy names. |
| [Jimenez 2009](#jimenez2009), 12 name datasets | F1/IAP curves favor powers above one; no precise graph-derived average quoted | Existing exponent-2 Monge–Elkan already addresses this lead. |
| [LinkTransformer 2024](#linktransformer2024), Table 1 | Multilingual company top-1: .55 edit / .69 SBERT / .83 tuned; fine-product: .54 / .79 / .84 | Retrieval evidence for aliases; not Abt-Buy pair F1. |
| [JRC 2024](#jrc2024), Table 4 | Personal-name MAP: .91355 transliterated Double Metaphone vs .95 ± .01 multilingual trained model, Latin/Cyrillic/Arabic | Script handling is a separate dependency; avoid blanket neural superiority. |
| [SimCSE 2021](#simcse2021) | BERT-base mean STS Spearman: 76.3% unsupervised / 81.6% supervised | Sentence correlation does not establish identity matching. |
| [FEDS 2025](#feds2025), Table 4 / Figure 5 | Mean LLM runtime: 179.8 s → 99.27 s for 400 pairs, similar PR curves | Cascade evidence is domain/hardware specific; pair inference is outside built-ins. |

[Zeakis 2023](#zeakis2023) evaluates 12 models on 17 entity-resolution datasets; [Sudowoodo](#sudowoodo2022)
supports contrastive representation learning as a research direction. [WDC Products](#wdc2024)
motivates checking robustness across corner-case difficulty, unseen entities and training-set size.
Neither their broader system results nor semantic-search gains prove a standalone lexical feature will win here.

### Changes in interpretation since the earlier digest

- A missing **named** built-in does not make a measure inexpressible: Jaro, OSA and alignment can be
  designed as higher-order SQL state reducers. Their feasibility is currently a design inference.
- RapidFuzz `fuzz.ratio` uses normalized **Indel**, so token-sorted Spark Levenshtein is explicitly a new
  variant. It must not be tested against RapidFuzz token-sort outputs as though they were identical.
- SoftTF-IDF may be asymmetric and exceed one through token reuse. Its selected variant explicitly
  fixes direction averaging, inner comparator, tie-breaking, threshold and clipping. [Moreau 2008](#moreau2008)
- A learned vector comparator can have a built-in **pair** expression while its encoder remains external.
- Native Spark expressions do not prove Photon support; no Spark 4.2/4.3 functions are required here.

---

## Spark 4.1 contract

Official [Spark 4.1 documentation](#spark41) supplies the primitives; the installed environment reports
PySpark **4.1.3**. Context7 queries for `apache-spark` and `pyspark` returned `ApiError`; direct official
documentation was used as fallback. No runtime plan or performance result is inferred from a docs page.

| JSON support value | Meaning of `builtin_expressible` |
|---|---|
| `direct` | True: named built-in plus arithmetic/guards. |
| `composite_design` | True: concrete outline using existing expressions; SIM-2 must prove exact execution. |
| `prepared_vectors` | True for vector comparison only; raw-string encoding is external. |
| `not_established` | False: this review has no complete built-in design; not an impossibility claim. |
| `external_inference` | False: pair-dependent model inference requires external execution. |

Use `levenshtein`, `soundex`, `substring`, `length`, `split`, `sort_array`, set/map functions,
`transform`, `aggregate`, `zip_with`, `sequence`, structs and arithmetic. Guard thresholded
Levenshtein's `-1` result. There is no named Jaro/Jaro-Winkler function in this version's reference.

Common feature semantics are project decisions:

| Concern | Required behavior |
|---|---|
| Missing values | Return existing `MISSING=-1.0` for either null/empty normalized field, including both empty. Mathematical empty-string similarity is a separate reference convention. |
| Character unit | Code points with deterministic binary comparison; no implicit grapheme or byte metric. Reuse the existing normalization stage. |
| Token representation | Specify set vs multiset, whitespace handling, ordering and duplicate policy per measure. Do not silently change a formula by deduplicating. |
| IDF | Common positive weights on both sides, frozen fitting population and unseen-token behavior; document transductive preparation. No validation/test labels in weights. |
| Arrays / ANSI | Guard empty and short inputs before `sequence`, division or indexing; `sequence(1,0)` is not empty. Accumulator fields need stable explicit types. |
| Limits | Declare character/token caps, deterministic truncation or rejection, and affected-pair counts. Never silently report an approximation as the exact measure. |
| Learned scores | Vector model/version/dimension/pooling/normalization must match; zero vectors and missing values need separate handling. |

---

## Ranked shortlist

All seven entries have new families and bare prefixes, checked against the current registry. The emitted
column uses `<prefix>_<field>`; the stored prefix contains **no underscore**, because `family_of` splits
at the first underscore. All seven are now registered as opt-in SIM-2 features; see the
[implementation contract](../SIMILARITY.md) for tested behavior and explicit resource limits.
The research feasibility/cost annotations below remain the original SIM-1 assessments.

| Rank | Measure / category | Family | Prefix | Expected value per cost (inference) |
|---|---|---|---|---|
| 1 | [Token-sorted normalized Levenshtein](#measure-token_sort_lev) / hybrid | `token_sort_lev` | `tsl` | Combines reorder tolerance with native edit cost; directly targets product titles with different word order. |
| 2 | [Boundary-padded bigram multiset Dice](#measure-padded_bigram_dice) / token | `padded_bigram_dice` | `pbd` | Cheap boundary and repeated-character evidence absent from the current gram representation; useful typo hypothesis. |
| 3 | [IDF-weighted token Jaccard](#measure-weighted_jaccard) / token | `weighted_jaccard` | `wja` | Cheap rare-model-word overlap, with a different length penalty from existing token cosine. |
| 4 | [Character trigram count cosine](#measure-qgram_count_cosine) / token | `qgram_count_cosine` | `qcc` | Adds multiplicity-sensitive character evidence at low pair cost. |
| 5 | [Symmetric clipped SoftTF-IDF with Levenshtein inner score](#measure-soft_tfidf_lev) / hybrid | `soft_tfidf_lev` | `stl` | Adds rarity to approximate token alignment, complementing existing exact-token cosine and unweighted Monge-Elkan. |
| 6 | [Normalized optimal string alignment](#measure-osa) / edit | `osa` | `osa` | Adds the transposition operation missing from the current edit baseline; expensive SQL state is justified only if typo slices improve. |
| 7 | [Normalized Indel similarity from longest common subsequence](#measure-lcs_indel) / alignment | `lcs_indel` | `lci` | Tests an alternative edit penalty with exact Indel semantics and enables later token-ratio parity work. |

Existing Levenshtein, generalized Monge–Elkan, IDF token cosine, gram Jaccard, Soundex,
numeric-token agreement, rarity and embedding cosine are controls. They are not counted as new candidates.
Ordinary Dice over the same sets is a monotone transform of Jaccard; the selected bigram Dice changes
padding and multiplicity too. Prefix-weighted Levenshtein is deferred: a prefix boost does not directly
repair a typo in the prefix, and there is insufficient measured evidence to prioritize another heuristic.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#00d4ff', 'lineColor': '#00d4ff', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'fontFamily': 'monospace'}}}%%
flowchart LR
  A["Normalized records"] --> B["Sorted tokens / gram counts / frozen IDF"]
  B --> C["Built-in pair expressions"]
  C --> D["SIM-2 reference and plan checks"]
  D --> E["SIM-3 validation selection"]
  E --> F["One TEST confirmation"]
  F --> G["Adopt only if verdict is beaten"]
```

---

## Measure catalogue

Field labels use the existing config vocabulary. `code` means identifiers, not programming source.
Each entry gives evidence separately from our feasibility/cost inference. Reference cases marked
“Derived” are hand-calculated specification examples, not an executed independent oracle.

Full formulas, expression outlines, costs and limitations for every row are in [the JSON catalogue](sota_candidates.json), keyed by the stable measure ID.

### Edit

| Measure / ID | Field types | Spark 4.1 support | Evidence / sources |
|---|---|---|---|
| <a id="measure-levenshtein"></a>**Normalized Levenshtein** (`levenshtein`) | person_name, address, organisation, title, code | Yes: `direct` | Historical Census MaxF1 .865; existing baseline. [rflev](#rflev), [bilenko2003](#bilenko2003), [spark41](#spark41) |
| <a id="measure-osa"></a>**Normalized optimal string alignment** (`osa`) | person_name, title, code | Yes: `composite_design` | Restricted transpositions; library definition, not an accuracy result. [rfosa](#rfosa), [rfdl](#rfdl), [spark41](#spark41) |
| <a id="measure-damerau"></a>**Unrestricted Damerau-Levenshtein** (`damerau`) | person_name, title, code | Yes: `composite_design` | Unrestricted edits differ from OSA; higher state cost. [rfdl](#rfdl), [rfosa](#rfosa) |
| <a id="measure-jaro"></a>**Jaro** (`jaro`) | person_name, organisation, code | Yes: `composite_design` | Historical Census MaxF1 .728; exact tie conventions matter. [rfjaro](#rfjaro), [bilenko2003](#bilenko2003), [spark41](#spark41) |
| <a id="measure-jaro_winkler"></a>**Jaro-Winkler** (`jaro_winkler`) | person_name, organisation, code | Yes: `composite_design` | No universal name-matching winner; SQL parity would remove a UDF. [rfjw](#rfjw), [christen2006](#christen2006), [spark41](#spark41) |

### Token

| Measure / ID | Field types | Spark 4.1 support | Evidence / sources |
|---|---|---|---|
| <a id="measure-token_jaccard"></a>**Token-set Jaccard** (`token_jaccard`) | address, organisation, title | Yes: `composite_design` | Historical Census MaxF1 .567; no token typo tolerance. [scipyjaccard](#scipyjaccard), [bilenko2003](#bilenko2003) |
| <a id="measure-token_dice"></a>**Token-set Dice** (`token_dice`) | address, organisation, title | Yes: `composite_design` | Same-set Dice merely rescales Jaccard (deduction). [christen2006](#christen2006) |
| <a id="measure-overlap"></a>**Token overlap coefficient** (`overlap`) | address, organisation, title | Yes: `composite_design` | Definition rewards containment; identity does not follow. [moreau2008](#moreau2008) |
| <a id="measure-weighted_jaccard"></a>**IDF-weighted token Jaccard** (`weighted_jaccard`) | address, organisation, title | Yes: `composite_design` | Weighted-set definition plus rarity rationale; proposed IDF combination. [scipyjaccard](#scipyjaccard), [splinktf](#splinktf) |
| <a id="measure-idf_cosine"></a>**IDF token-set cosine** (`idf_cosine`) | person_name, address, organisation, title | Yes: `composite_design` | Historical token-method evidence; already implemented. [cohen2003](#cohen2003), [moreau2008](#moreau2008) |
| <a id="measure-qgram_jaccard"></a>**Character q-gram set Jaccard** (`qgram_jaccard`) | address, organisation, title | Yes: `composite_design` | Established representation and set definition; already implemented. [christen2006](#christen2006), [scipyjaccard](#scipyjaccard) |
| <a id="measure-padded_bigram_dice"></a>**Boundary-padded bigram multiset Dice** (`padded_bigram_dice`) | person_name, address, organisation, title, code | Yes: `composite_design` | Proposed representation change; exact-variant gain unmeasured. [christen2006](#christen2006), [scipyjaccard](#scipyjaccard) |
| <a id="measure-qgram_count_cosine"></a>**Character trigram count cosine** (`qgram_count_cosine`) | address, organisation, title | Yes: `composite_design` | Count-vector design using cosine; gain unmeasured. [sklearncosine](#sklearncosine), [christen2006](#christen2006) |

### Hybrid

| Measure / ID | Field types | Spark 4.1 support | Evidence / sources |
|---|---|---|---|
| <a id="measure-token_sort_lev"></a>**Token-sorted normalized Levenshtein** (`token_sort_lev`) | person_name, address, organisation, title | Yes: `composite_design` | Proposed sorting plus native Levenshtein; distinct from RapidFuzz ratio. [rffuzz](#rffuzz), [rflev](#rflev) |
| <a id="measure-token_sort_indel"></a>**RapidFuzz-style token-sort Indel ratio** (`token_sort_indel`) | address, organisation, title | Yes: `composite_design` | Library-defined sorted-token ratio; no linkage F1 claim. [rffuzz](#rffuzz), [rflcs](#rflcs) |
| <a id="measure-token_set_indel"></a>**RapidFuzz-style token-set Indel ratio** (`token_set_indel`) | address, organisation, title | Yes: `composite_design` | Library definition rewards subset containment; risk for product identifiers. [rffuzz](#rffuzz), [rflcs](#rflcs) |
| <a id="measure-monge_elkan"></a>**Symmetric generalized token Monge-Elkan, exponent 2** (`monge_elkan`) | person_name, address, organisation, title, code | Yes: `composite_design` | 12-dataset exponent evidence; current symmetric variant already implemented. [jimenez2009](#jimenez2009) |
| <a id="measure-soft_tfidf_lev"></a>**Symmetric clipped SoftTF-IDF with Levenshtein inner score** (`soft_tfidf_lev`) | address, organisation, title | Yes: `composite_design` | Historical hybrid evidence; selected symmetry/inner score/clipping are new choices. [cohen2003](#cohen2003), [moreau2008](#moreau2008), [bilenko2003](#bilenko2003) |
| <a id="measure-soft_cardinality"></a>**Soft-cardinality token overlap** (`soft_cardinality`) | organisation, title | Yes: `composite_design` | SemEval MSRvid Pearson .8562; not record-linkage F1. [softcard2012](#softcard2012) |

### Phonetic

| Measure / ID | Field types | Spark 4.1 support | Evidence / sources |
|---|---|---|---|
| <a id="measure-soundex"></a>**Soundex-code equality** (`soundex`) | person_name | Yes: `direct` | Worked phonetic collision; existing feature, not identity proof. [jellyfish](#jellyfish), [spark41](#spark41) |
| <a id="measure-nysiis"></a>**NYSIIS-code equality** (`nysiis`) | person_name | Yes: `composite_design` | Library encoding definition; contextual rule parity still required. [jellyfish](#jellyfish), [christen2006](#christen2006) |
| <a id="measure-double_metaphone"></a>**Double Metaphone code overlap** (`double_metaphone`) | person_name, organisation | No established plan: `not_established` | JRC retrieval evidence depends on script and transliteration. [jrc2024](#jrc2024) |

### Alignment

| Measure / ID | Field types | Spark 4.1 support | Evidence / sources |
|---|---|---|---|
| <a id="measure-lcs_indel"></a>**Normalized Indel similarity from longest common subsequence** (`lcs_indel`) | person_name, address, organisation, title, code | Yes: `composite_design` | Defined Indel normalization; gain unmeasured. [rflcs](#rflcs), [rffuzz](#rffuzz) |
| <a id="measure-smith_waterman"></a>**Smith-Waterman local alignment** (`smith_waterman`) | address, organisation, title | Yes: `composite_design` | Primary local-alignment algorithm; no linkage benchmark inferred. [smith1981](#smith1981) |
| <a id="measure-affine_gap"></a>**Smith-Waterman local alignment with affine gaps** (`affine_gap`) | address, organisation, title | Yes: `composite_design` | Algorithm provenance; existing UDF needs scoring-parity checks. [gotoh1982](#gotoh1982), [smith1981](#smith1981) |

### Learned

| Measure / ID | Field types | Spark 4.1 support | Evidence / sources |
|---|---|---|---|
| <a id="measure-embedding_cosine"></a>**Bi-encoder embedding cosine** (`embedding_cosine`) | organisation, title | Yes: `prepared_vectors` | LinkTransformer retrieval gains; vector preparation is external. [linktransformer2024](#linktransformer2024), [zeakis2023](#zeakis2023), [sklearncosine](#sklearncosine), [wdc2024](#wdc2024) |
| <a id="measure-byte_name_distance"></a>**Learned byte-level name-vector distance** (`byte_name_distance`) | person_name, organisation | Yes: `prepared_vectors` | JRC name-retrieval results vary by script and entity type. [jrc2024](#jrc2024) |
| <a id="measure-contrastive_cosine"></a>**Contrastively trained representation cosine** (`contrastive_cosine`) | organisation, title | Yes: `prepared_vectors` | STS and ER representation evidence; task metrics differ. [simcse2021](#simcse2021), [sudowoodo2022](#sudowoodo2022), [zeakis2023](#zeakis2023) |
| <a id="measure-llm_adjudication"></a>**LLM pair adjudication / fuzzy-score cascade** (`llm_adjudication`) | person_name, address, organisation, title | No established plan: `external_inference` | Sanctions cascade runtime evidence; pair inference is external. [feds2025](#feds2025), [wdc2024](#wdc2024) |

### Shortlist definitions and expression outlines

<details><summary>1. Token-sorted normalized Levenshtein</summary>

**Definition:** L(join(sort(tokens(a)), single_space), join(sort(tokens(b)), single_space)); retain duplicate tokens.

**Expression outline:** split/filter empty tokens, sort_array and concat_ws during record preparation; use the existing normalized levenshtein expression on sorted strings.

**Cost (inference):** Token sorting plus one native edit-distance call per pair. **Limitations:** Sorting erases meaningful word order and does not solve synonyms or model-number conflicts.

Source basis: [rffuzz](#rffuzz), [rflev](#rflev). See JSON `reference_cases` for specification examples.

</details>

<details><summary>2. Boundary-padded bigram multiset Dice</summary>

**Definition:** Generate bigrams over BOS + characters + EOS. Let c_A(g),c_B(g) be counts. Score=2*sum_g min(c_A(g),c_B(g))/(sum_g c_A(g)+sum_g c_B(g)).

**Expression outline:** Use tagged character elements for collision-free BOS/EOS, sequence/transform for adjacent pairs, count maps prepared once per record, then aggregate minima over shared keys.

**Cost (inference):** O(n+m) gram generation; count preparation and map lookups add engine-dependent costs. **Limitations:** Use distinct boundary tags, not a literal character that may occur in data. Counts must not be dropped.

Source basis: [christen2006](#christen2006), [scipyjaccard](#scipyjaccard). See JSON `reference_cases` for specification examples.

</details>

<details><summary>3. IDF-weighted token Jaccard</summary>

**Definition:** Sum of shared-token positive IDF weights divided by sum of union-token weights; binary term presence, with one common weight per token on both sides.

**Expression outline:** Reuse prepared token IDF maps, union their keys, and aggregate shared/union weights. Enforce the same IDF dictionary on both sides and guard a zero total.

**Cost (inference):** O(k+l) logical weight visits after set construction; no token-pair edit calls. **Limitations:** IDF fitting population and unseen-token fallback must be frozen. Distinct from existing L2-normalized IDF cosine.

Source basis: [scipyjaccard](#scipyjaccard), [splinktf](#splinktf). See JSON `reference_cases` for specification examples.

</details>

<details><summary>4. Character trigram count cosine</summary>

**Definition:** Cosine of unpadded trigram count vectors. For a nonempty string shorter than three characters, use one tagged whole-string feature.

**Expression outline:** Build count maps during record preparation; shared-key product sum and squared-norm sums at comparison time.

**Cost (inference):** O(n+m) logical sparse-vector preparation/comparison; no per-token edit grid. **Limitations:** Repeated boilerplate may dominate; measure ablations against existing gram and token-IDF families.

Source basis: [sklearncosine](#sklearncosine), [christen2006](#christen2006). See JSON `reference_cases` for specification examples.

</details>

<details><summary>5. Symmetric clipped SoftTF-IDF with Levenshtein inner score</summary>

**Definition:** Normalize positive binary-token IDF vectors to L2. For each a choose b maximizing L(a,b), lexical tie-break; include w_A(a)*w_B(b)*L(a,b) only if L(a,b)>0.8. Average both directed sums, then clip to [0,1].

**Expression outline:** Prepare token-weight structs sorted lexically. Nested aggregate chooses the best similarity and corresponding target weight, retaining first on ties; aggregate contributions in each direction, average and least(1.0,...).

**Cost (inference):** O(k*l) native token edit calls plus weight arithmetic; reuse the existing token cap with truncation recorded. **Limitations:** Not canonical Jaro-Winkler SoftTF-IDF. Many-to-one matches can exceed one before clipping, losing information. Keep numeric disagreement separately.

Source basis: [cohen2003](#cohen2003), [moreau2008](#moreau2008), [bilenko2003](#bilenko2003). See JSON `reference_cases` for specification examples.

</details>

<details><summary>6. Normalized optimal string alignment</summary>

**Definition:** D(i,j)=min(D(i-1,j)+1,D(i,j-1)+1,D(i-1,j-1)+[a_i!=b_j],D(i-2,j-2)+1 when adjacent characters cross). Score=1-D(n,m)/max(n,m).

**Expression outline:** Nested aggregate(sequence(...)) over rows and columns. Outer struct stores the previous two rows; inner accumulator appends current-row cells. Boundary row/column are 0..length. Guard i>1 and j>1 for transpositions.

**Cost (inference):** O(n*m) cells; immutable array appends can add O(m) copying per cell. **Limitations:** OSA is not unrestricted Damerau-Levenshtein; repeated edits and overlapping transpositions differ. Cap or reject long inputs explicitly.

Source basis: [rfosa](#rfosa), [rfdl](#rfdl), [spark41](#spark41). See JSON `reference_cases` for specification examples.

</details>

<details><summary>7. Normalized Indel similarity from longest common subsequence</summary>

**Definition:** C(i,j)=C(i-1,j-1)+1 when a_i=b_j, else max(C(i-1,j),C(i,j-1)); score=2*C(n,m)/(n+m).

**Expression outline:** Nested aggregate over character positions with zero-initialized previous row and incrementally appended current row; normalize the final cell. SQL array indices offset the mathematical zero column by one.

**Cost (inference):** O(n*m) cells and O(m) logical live state, but repeated concat may add O(n*m*m) copying. **Limitations:** Subsequence is not substring. Conservative bounded inputs and plan-depth checks are required before throughput claims.

Source basis: [rflcs](#rflcs), [rffuzz](#rffuzz). See JSON `reference_cases` for specification examples.

</details>

---

## Implementation notes

For token-sort Levenshtein, normalize and tokenize once, retain duplicate tokens, and prepare sorted
strings before joining candidates. This supplies a cheap first implementation with one native edit call.
Padded gram keys should distinguish boundary tags structurally, so a literal sentinel in input cannot
collide with an artificial boundary. Count-based features need counts, not existing distinct gram arrays.

For OSA/LCS, build bounded nested reducers, not Python loops that unroll a separate expression for every
cell. Logical rolling-row space is small, but immutable array `concat` may repeatedly copy rows; report
that cost rather than assuming native C++ dynamic-programming throughput. Validate repeated characters,
adjacent transpositions and length asymmetry against an independent oracle before adding long inputs.
The OSA documentation's `CA`/`AC` result appears inconsistent with its definition; resolve it with a pinned
runtime and the recurrence, and do not blindly turn that printed example into a golden test.

For SoftTF-IDF, the chosen target's **weight** must follow the chosen target token. Do not maximize the
weight-times-similarity product while claiming to maximize similarity. Ties go to the lexical first
token; threshold is strict `>0.8`. Evaluate both directions before clipping. Include a many-to-one case
whose unbounded score exceeds one, so the test demonstrates the declared variant.

Minimal built-in example (raw normalized fields; the feature wrapper supplies the missing-value sentinel):

```sql
SELECT CASE
  WHEN a IS NULL OR b IS NULL OR length(a) = 0 OR length(b) = 0 THEN -1.0
  ELSE 1.0 - levenshtein(a, b) / CAST(greatest(length(a), length(b)) AS DOUBLE)
END AS normalized_levenshtein
FROM pairs;
```

Complete example for the first proposed family, assuming the existing normalized field contract:

```sql
WITH prepared AS (
  SELECT *,
    concat_ws(' ', sort_array(filter(split(a, ' '), t -> length(t) > 0))) AS sa,
    concat_ws(' ', sort_array(filter(split(b, ' '), t -> length(t) > 0))) AS sb
  FROM pairs
)
SELECT CASE
  WHEN a IS NULL OR b IS NULL OR length(sa) = 0 OR length(sb) = 0 THEN -1.0
  ELSE 1.0 - levenshtein(sa, sb) / CAST(greatest(length(sa), length(sb)) AS DOUBLE)
END AS tsl_example
FROM prepared;
```

These examples are specifications. SIM-2 executes the production builders in classic and Connect;
[its tests and pinned oracles](../../tests/test_sota.py) provide implementation evidence.
No public-source implementation code is copied into lakematch.

---

## Validation and handoff

```bash
cd ~/Projects/Personal
bash goals/verify_simbeat.sh 1
```

The SIM-1 verifier checks minimum counts, category coverage and shortlist shape. Additional review must
check unique IDs, valid field types, Boolean flags, all citations resolving within the catalogue, unused
family/prefix names, and Markdown/JSON agreement. The supplied verifier imports registries but does not
actually detect collisions with existing families/prefixes. A pass does not verify research claims.

SIM-2 implements only the seven new families, off by default. Required tests include published or pinned
implementation reference values, symmetry where promised, score range, repeated tokens, Unicode, numeric
conflicts, null/empty inputs and the OSA/unrestricted-Damerau counterexample. Both classic and Connect
plans must be free of Python evaluation nodes; inspect JVM UDF/custom-expression use too, since the
requirement is built-ins only. Check plan depth and bounded-input throughput before broadening limits.

SIM-3 retains the existing four corpora and protocol: fit on 80% of TRAIN, calibrate threshold on 20%,
select on VALID, then perform one TEST confirmation against freshly measured Jaro-Winkler. Report paired
bootstrap uncertainty. No corpus may lose more than .005 VALID F1 relative to Levenshtein; require the
brief's mean/Abt-Buy/TEST conditions before recording `beaten`. Otherwise `not_beaten` is a valid outcome.
New external benchmarks are research context, not extra selection datasets in this phase.

---

## References

URLs below identify distinct sources, not duplicate mirrors counted separately. Paper years are genuine
publication/version years; “undated” docs are recorded with a separate access date in JSON. Each source
is used by at least one measure. Source results are reported, not reproduced locally.

<details><summary>Source register, locators and provenance</summary>

| ID | Year / kind | Source | Checked location / qualification |
|---|---|---|---|
| <a id="cohen2003"></a>`cohen2003` | 2003 / paper | [A Comparison of String Distance Metrics for Name-Matching Tasks](https://wwcohen.github.io/postscript/ijcai-ws-2003.pdf) | Sections 2–3; Figures 1–2. Name-matching experiments; historical evidence, not a 2026 leaderboard. |
| <a id="bilenko2003"></a>`bilenko2003` | 2003 / paper | [Adaptive Name-Matching in Information Integration](https://wwcohen.github.io/postscript/intelligent-systems-2003.pdf) | Table 3: Census; Table 4: learned combinations.  |
| <a id="christen2006"></a>`christen2006` | 2006 / paper | [A Comparison of Personal Name Matching: Techniques and Practical Issues](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf) | Sections 3–5. September technical report; four name datasets, no universal winner. |
| <a id="jimenez2009"></a>`jimenez2009` | 2009 / paper | [Generalized Mongue-Elkan Method for Approximate Text String Comparison](https://www.gelbukh.com/CV/Publications/2009/Generalized%20Mongue-Elkan%20Method%20for%20Approximate%20Text%20String.pdf) | Sections 3–4; Figures 4–5. Published title spells Mongue; 12 datasets; plotted averages are not transcribed as precise numbers. |
| <a id="moreau2008"></a>`moreau2008` | 2008 / paper | [Robust Similarity Measures for Named Entities Matching](https://aclanthology.org/C08-1075.pdf) | Section 2.2, pp. 594–595. Explains SoftTF-IDF asymmetry, target-token weighting and possible scores above one. |
| <a id="softcard2012"></a>`softcard2012` | 2012 / paper | [Soft Cardinality: A Parameterized Similarity Function for Text Comparison](https://aclanthology.org/S12-1061.pdf) | Equations 1–3; Table 1.  |
| <a id="smith1981"></a>`smith1981` | 1981 / paper | [Identification of Common Molecular Subsequences](https://cs.brown.edu/courses/csci1820/spring-2022/resources/Smith_Waterman_1981.pdf) | Local-alignment recurrence. Primary paper reprint; biological sequence algorithm, not record-linkage accuracy evidence. |
| <a id="gotoh1982"></a>`gotoh1982` | 1982 / paper | [An improved algorithm for matching biological sequences](https://pubmed.ncbi.nlm.nih.gov/7166760/) | Bibliographic record and abstract; DOI 10.1016/0022-2836(82)90398-9. Algorithm provenance only; full text not inspected. |
| <a id="spark41"></a>`spark41` | undated / library-doc | [Apache Spark 4.1.0 SQL built-in functions](https://spark.apache.org/docs/4.1.0/sql-ref-functions-builtin.html) | String, collection, map and higher-order functions. Version pinned; undated documentation does not count toward recent publications. |
| <a id="rflev"></a>`rflev` | undated / library-doc | [RapidFuzz: Levenshtein](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html) | Definitions, normalization and examples. Observed documentation version 3.14.6; live page, not an immutable version pin. No linkage benchmark claim. |
| <a id="rfosa"></a>`rfosa` | undated / library-doc | [RapidFuzz: Optimal String Alignment (OSA)](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/OSA.html) | Definitions, normalization and examples. Observed documentation version 3.14.6; live page, not an immutable version pin. No linkage benchmark claim. |
| <a id="rfdl"></a>`rfdl` | undated / library-doc | [RapidFuzz: Damerau Levenshtein](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/DamerauLevenshtein.html) | Definitions, normalization and examples. Observed documentation version 3.14.6; live page, not an immutable version pin. No linkage benchmark claim. |
| <a id="rflcs"></a>`rflcs` | undated / library-doc | [RapidFuzz: Longest Common Subsequence](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/LCSseq.html) | Definitions, normalization and examples. Observed documentation version 3.14.6; live page, not an immutable version pin. No linkage benchmark claim. |
| <a id="rfjaro"></a>`rfjaro` | undated / library-doc | [RapidFuzz: Jaro](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Jaro.html) | Definitions, normalization and examples. Observed documentation version 3.14.6; live page, not an immutable version pin. No linkage benchmark claim. |
| <a id="rfjw"></a>`rfjw` | undated / library-doc | [RapidFuzz: JaroWinkler](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/JaroWinkler.html) | Definitions, normalization and examples. Observed documentation version 3.14.6; live page, not an immutable version pin. No linkage benchmark claim. |
| <a id="rffuzz"></a>`rffuzz` | undated / library-doc | [RapidFuzz: Fuzzy ratios](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) | Definitions, normalization and examples. Observed documentation version 3.14.6; live page, not an immutable version pin. No linkage benchmark claim. |
| <a id="scipyjaccard"></a>`scipyjaccard` | undated / library-doc | [SciPy: weighted Boolean Jaccard distance](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jaccard.html) | Weighted c_ij definition. Positive dimension weights; similarity is one minus distance. |
| <a id="sklearncosine"></a>`sklearncosine` | undated / library-doc | [scikit-learn: cosine_similarity](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html) | Normalized dot-product definition. Definition only; character-gram application is our design inference. |
| <a id="jellyfish"></a>`jellyfish` | undated / library-doc | [Jellyfish: string comparison and phonetic encoding functions](https://jamesturk.github.io/jellyfish/functions/) | American Soundex and NYSIIS. Worked encodings; no measured F1 advantage. |
| <a id="splinktf"></a>`splinktf` | undated / library-doc | [Splink: term-frequency adjustments](https://moj-analytical-services.github.io/splink/topic_guides/comparisons/term-frequency.html) | Problem statement; low-frequency outliers. Agreement weighting is not itself a string distance. |
| <a id="simcse2021"></a>`simcse2021` | 2021 / paper | [SimCSE: Simple Contrastive Learning of Sentence Embeddings](https://aclanthology.org/2021.emnlp-main.552/) | Abstract; STS evaluation. Semantic textual similarity correlation is not entity-match F1. |
| <a id="sudowoodo2022"></a>`sudowoodo2022` | 2022 / paper | [Sudowoodo: Contrastive Self-supervised Learning for Multi-purpose Data Integration and Preparation](https://arxiv.org/abs/2207.04122) | Abstract, arXiv v2. Year is the linked preprint year; subsequently ICDE 2023. Abstract-level evidence only. |
| <a id="zeakis2023"></a>`zeakis2023` | 2023 / paper | [Pre-trained Embeddings for Entity Resolution: An Experimental Analysis](https://www.vldb.org/pvldb/vol16/p2225-skoutas.pdf) | Abstract; experimental evaluation. 12 language models, 17 datasets; blocking and matching evaluated separately. |
| <a id="linktransformer2024"></a>`linktransformer2024` | 2024 / paper | [LinkTransformer: A Unified Package for Record Linkage with Transformer Language Models](https://aclanthology.org/2024.acl-demos.21.pdf) | Table 1, panels A–B. Top-1 retrieval accuracy, not pair classification F1. |
| <a id="jrc2024"></a>`jrc2024` | 2024 / paper | [JRC-Names-Retrieval: A Standardized Benchmark for Name Search](https://aclanthology.org/2024.lrec-main.838.pdf) | Tables 4–5; Sections 5–6. MAP and recall@k; personal and organisation names differ; transliteration is a separate dependency. |
| <a id="wdc2024"></a>`wdc2024` | 2024 / paper | [WDC Products: A Multi-Dimensional Entity Matching Benchmark](https://www.openproceedings.org/2024/conf/edbt/paper-14.pdf) | Benchmark dimensions and evaluation. Publication year 2024; preprint appeared in 2023. External validity context, not a new similarity. |
| <a id="feds2025"></a>`feds2025` | 2025 / paper | [Can LLMs Improve Sanctions Screening in the Financial System? Evidence from a Fuzzy Matching Assessment](https://www.federalreserve.gov/econres/feds/files/2025092pap.pdf) | Table 4 and Figure 5. FEDS 2025-092; 400 pairwise evaluations in the runtime table; deployment-specific timing. |

</details>

---

## License

Project-authored research and specifications follow the repository [Apache-2.0 license](../../LICENSE).
Cited publications, library documentation and implementations retain their respective rights. The
catalogue summarizes their evidence and defines original expression designs; it does not vendor code.
