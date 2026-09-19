# Typed comparison contract

`lakematch.entity.prepare` preserves raw date/number values and normalized array
boundaries. A scalar normalized text view supplies candidate retrieval. Typed
features never parse the punctuation-stripped view, so negative signs and decimal
points survive. Dates use an explicit Spark `date_format` (default ISO date).
Invalid typed values have an `invalid` flag and comparison value -1.

All default comparisons are Spark SQL expressions, including accent-insensitive
equality, initials/overlap for names, numeric-token overlap for addresses/titles,
legal-form/acronym comparisons for organisations, code prefix/suffix/length,
date parts/day distance, and finite numeric relative/sign comparisons. Exact
equality uses the full normalized value. Other string work is bounded by
`max_chars` (512), `max_tokens` (64) and Levenshtein's edit threshold (64).
Values beyond these bounds may lose discriminating information; these are
declared computational limits, not lossless comparison guarantees.

`exclude_field_types` removes every classifier comparison for selected types;
it supports field-family ablations while leaving candidate retrieval fixed.
`field_families: false` instead removes only the extra type-specific comparisons,
retaining the base string and selected multi-token features for each field.

Native optional families are IDF token cosine, character-trigram Jaccard, and
symmetric token Monge-Elkan (average of the two directed quadratic means).
Fit `feature_stats.fit_idf` on training records, save that vocabulary with the
model, then `attach_idf` to both sides. Document frequency uses binary token
presence, counts empty documents in N, and gives unseen tokens df=0. Scoring
does not refit IDF. In a flow, consume prepared vocabulary/embedding arrays;
fitting, actions and provider invocation belong in job tasks.

Jaro-Winkler and global affine-gap edit similarity are independent optional UDF
implementations, available only with `udf_features: true`. Photon-classic configs
reject those options. The global affine score is not the historical local
alignment/containment score. Missing strings return -1, while observed ordinary
similarities range from 0 to 1. Embedding cosine ranges from -1 to 1 and includes
a separate missing flag.

Arrays use `multiple: true` and JSON or Parquet input, preserving value boundaries
for best-value and set-overlap comparisons. Multi-valued dates/numbers require
explicit upstream scalar extraction; ambiguous date formats are not guessed.

Embeddings remain off by default after the validation ablation. To select them:

```yaml
features:
  embeddings:
    fields_of_type: [organisation, title]
    provider: local
    model: data/models/all-MiniLM-L6-v2
```

Install the `embeddings` extra and run `tools/prepare_sources.py --model` during
online preparation. Engine execution loads only a local, pinned snapshot with
`trust_remote_code=False` and `local_files_only=True`. Driver batches write
record vectors to a Spark-visible JSONL path (local path or UC Volume); matching
uses native array expressions. Explicit `local` fails when unavailable; `auto`
warns and emits stable missing-value columns. Provider timing and hashes are
recorded separately. The default empty `fields_of_type` creates no extra columns.
