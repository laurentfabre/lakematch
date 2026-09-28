# Optional string similarity families

*SIM-2 implementation contract · Spark 4.1 · classic and Spark Connect*

## What / why

Seven additional comparison families implement the [SIM-1 shortlist](research/sota_candidates.json).
They are **off by default**. Enable them for validation experiments; SIM-3 decides whether any
combination improves on the existing Jaro-Winkler baseline. All new preparation and pair expressions
use Spark SQL built-ins. This establishes portability, not Photon coverage or an accuracy improvement.

## Contents

- [Configuration](#configuration)
- [Families](#families)
- [Input and resource contract](#input-and-resource-contract)
- [Implementation](#implementation)
- [Verification](#verification)
- [License](#license)

---

## Configuration

Minimal opt-in:

```yaml
features:
  extra_families: [token_sort_lev]
```

All seven, with their resource limits explicitly stated:

```yaml
features:
  extra_families:
    - token_sort_lev
    - padded_bigram_dice
    - weighted_jaccard
    - qgram_count_cosine
    - soft_tfidf_lev
    - osa
    - lcs_indel
  sota_max_chars: 256
  token_cap: 30
  embeddings:
    provider: none
```

`features.exclude` takes precedence over `extra_families`, including preparation. Unknown names,
duplicate names, a scalar instead of a list, and nonpositive/noninteger limits are configuration
errors. Booleans are not integer limits. `udf_features` is not needed for these families.

---

## Families

The prefix is stored without the trailing underscore; emitted columns are `<prefix>_<field>`.
`text` below means person_name, address, organisation and title; `multi-text` means address,
organisation and title. Code comparisons operate on the normalized code field, including the
existing canonical joined representation of multi-valued codes.

| Family | Prefix | Fields | Exact implemented variant |
|---|---|---|---|
| `token_sort_lev` | `tsl` | text | Sort duplicate-preserving tokens, join with spaces, then `1 - levenshtein/max_length`. This differs from RapidFuzz token-sort Indel. |
| `padded_bigram_dice` | `pbd` | text, code | Boundary-padded bigram **multiset** Dice: twice the sum of minimum counts divided by total counts. |
| `weighted_jaccard` | `wja` | multi-text | Sum of shared IDF weights divided by union IDF weights, with binary token presence and common weights on both sides. |
| `qgram_count_cosine` | `qcc` | multi-text | Cosine of unpadded trigram **count** vectors. A shorter nonempty string is one separately tagged whole-string feature. |
| `soft_tfidf_lev` | `stl` | multi-text | L2-normalized binary-token IDF; normalized-Levenshtein best match; strict similarity `>0.8`; average both directions and clip to one. |
| `osa` | `osa` | person_name, title, code | Unit-cost optimal string alignment, normalized by maximum length. Adjacent transpositions allowed; unrestricted Damerau-Levenshtein is different. |
| `lcs_indel` | `lci` | text, code | `2 * longest_common_subsequence_length / (left_length + right_length)`, the normalized Indel similarity. |

SoftTF-IDF chooses the most similar target token, retaining the lexical first on ties, and uses
that target's weight. It does not maximize similarity times weight. Different source tokens may
reuse a target; clipping handles an averaged score above one. Numeric disagreement remains a
separate existing feature.

---

## Input and resource contract

Every new feature returns the existing `-1.0` missing sentinel when either normalized field is empty
or absent, including both empty. Comparable scores lie in `[0,1]`. Existing normalization determines
case, punctuation and token boundaries; comparison uses Unicode code points, not bytes or graphemes.

IDF preparation reuses the common dictionary computed over both input sides, including when the old
`token_idf` and `rarity` families are excluded. This is transductive unlabeled preparation; no match
labels enter the weights. Comparisons must use maps from that same prepared population. Unknown
tokens require re-preparation rather than arbitrary pair-specific weight assignment.

| Limit | Behavior |
|---|---|
| `sota_max_chars` (default 256) | OSA/LCS raise a descriptive Spark error if either nonmissing input exceeds the cap. No truncation, substitution with another metric, or missing-value fallback occurs. |
| `token_cap` (default 30) | SoftTF-IDF raises if either side has more than this many distinct weighted tokens. It does not silently truncate or renormalize a selected subset. The pre-existing Monge-Elkan family retains its own truncation behavior. |

Increasing a cap is explicit and may be costly. DP evaluates quadratic cell counts and copies growing
array rows; copying may add another factor of the shorter length. Gram-count preparation currently
scans the gram array for each unique gram (`O(n * unique_grams)`), once per record. Its comparison
uses prepared maps. No measured large-corpus throughput claim is made in SIM-2.

---

## Implementation

[features/sota.py](../src/lakematch/features/sota.py) holds the expression builders.
[features/__init__.py](../src/lakematch/features/__init__.py) connects the new registry, record preparation
and per-field comparison columns. Record enrichments are batched to keep Connect plans shallow.

OSA and LCS use nested SQL `aggregate` state machines with explicitly typed integer rows. The shorter
string supplies columns, reducing row-copy cost. SQL expressions are sent as text so the Connect
protobuf does not contain a deeply nested tree of individual Python `Column` operators. Column names
are quoted as identifiers. Python constructs the expression; it does not evaluate any input rows.

Bigram boundary elements are nulls within JSON pairs, distinct from every input character. Count-map
keys are unique by construction and do not depend on Spark's duplicate-map-key policy. Trigram short
strings carry a separate tag. Arrays preserve multiplicity until counts are computed.

---

## Verification

The pinned [reference fixture](../tests/fixtures/sota_reference.json) records RapidFuzz and SciPy versions,
source URLs and exact composition rules. It includes 26 string cases, 196 exhaustive binary-string
pairs for OSA/LCS, weighted-set cases and SoftTF-IDF tie/threshold/clipping cases. Tests require no
RapidFuzz installation. [The generator](../tests/generate_sota_reference.py) can regenerate the fixture
in a separate oracle environment; it never imports the Spark implementation.

The maintained primitives are OSA, Indel and Levenshtein from RapidFuzz; weighted Boolean Jaccard,
cosine and Bray-Curtis from SciPy. Multiset Dice equals one minus Bray-Curtis for nonnegative counts.
The custom SoftTF-IDF variant independently composes RapidFuzz token distances and Euclidean norms;
its symmetrization/clipping is a project contract, not claimed library equivalence. The actual pinned
OSA runtime gives distance one for `CA`/`AC`, resolving the inconsistent documentation example.

```bash
cd ~/Projects/Pro/lakematch
bash scripts/test.sh -p no:cacheprovider tests/test_sota.py
```

The production-path plan test prepares and materializes records before comparing every applicable
field type. It executes all seven families and rejects Python/JVM UDF evaluation in the resulting
plans. Configuration tests cover defaults, exclusions and invalid inputs; runtime tests cover cap
boundaries. Both classic and Connect run the same suite.

Required phase gate, including both complete repository suites:

```bash
cd ~/Projects/Personal
bash goals/verify_simbeat.sh 2
```

---

## License

Project code and documentation follow [Apache-2.0](../LICENSE). Test fixtures record numerical outputs
and source attribution; no external metric implementation is vendored into the production engine.
