# Company pilot generator v0.1

Implements the workload approved in LF-DEC-004. This freezes generation choices
before any candidate comparison. It is synthetic test preparation, not measured
quality or a claim that this corruption distribution represents a customer.

Seeds: generation **20260921**, split **20260922**, perturbation **20260923**,
opaque keys **20260924**, independent source order **20260925**, training-negative
sampling **20260926**. All choices use SHA-256 namespaced ranking or hash modulo,
independent of Python's random implementation. Split whole families first by
rank, using exact 60/20/20 counts, then independently rank companies for error
allocation within each partition. Both legal companies and all their source
variants remain in the same family partition.

Each family has a common synthetic brand/industry and two legal companies in
different jurisdictions. Generated identifiers are 12-digit strings (leading
zeros retained); source keys are independent 128-bit opaque digests. Names,
addresses and jurisdiction may legitimately overlap across companies. ERP is the
reference source in this initial workload; the declared CRM corruption is a
limitation to qualify before claims about symmetric customer source quality.

| Exclusive company stratum | All companies | Development | Validation | Confirmation |
|---|---:|---:|---:|---:|
| Clean | 4,000 | 2,400 | 800 | 800 |
| Spelling / suffix | 3,000 | 1,800 | 600 | 600 |
| Missing identifier | 4,000 | 2,400 | 800 | 800 |
| Wrong identifier / collision | 2,000 | 1,200 | 400 | 400 |
| Changed address | 3,000 | 1,800 | 600 | 600 |
| Multilingual name | 2,000 | 1,200 | 400 | 400 |
| Same name in another jurisdiction | 1,000 | 600 | 200 | 200 |
| Combined | 1,000 | 600 | 200 | 200 |

Spelling swaps the first two brand letters and drops the legal suffix.
Multilingual translates the industry word, including accented French values.
Wrong-identifier cases copy the sibling's identifier **and country**, producing
a real erroneous identifier/jurisdiction tuple while retaining the original
name/address. Same-name cases copy the sibling's legal name while retaining the
correct jurisdiction and identifier. Changed-address cases replace street and
postcode. Combined cases have spelling/suffix changes, a missing identifier and
changed street/postcode. These are the only intended overlapping corruptions;
all other strata are exclusive. Donor records always belong to the same family.

The matching feature allowlist is legal name, country, registration identifier,
street, city and postcode. Source record keys are opaque routing identifiers
outside the feature object. Parent keys, source identity, split, family, company
truth and corruption stratum never enter features. Each source is independently
shuffled; aligned row position is not a matching shortcut. Relationship tests
may consume parent keys separately under the relationship contract.

Candidates query **ERP left → CRM right within the same partition**. The 50 cap
applies to unique CRM candidates **after the union of retrieval methods** for
each ERP row. Record pre-cap union counts, per-method contributions and positive
losses. The existing global pair and pre-join limits also apply; do not give each
retrieval method a separate 50 allowance. Report the asymmetric workload honestly.

Training pairs include every development positive plus one sibling negative
and four distinct other-family negatives per ERP anchor, chosen by the independent
negative stream. No validation/confirmation negative sampling is supplied for
fitting. Validation metrics evaluate the complete retained candidate population
and all truth positives, including positives lost by retrieval. Calibration must
account for training sampling; precision on enriched fitting pairs cannot pass
the auto-merge gate. Final confidence uses at most one audited accepted decision
per family, selected with a separately declared fixed analysis seed before release.

`tools/prepare_company_pilot.py` writes only development/validation sources,
separate truth and development fitting pairs into a **new** directory. It emits
file hashes, source-code hash and all partition membership hashes. Confirmation
row/label generation is withheld until final configuration and analysis are
frozen. Releasing it is an explicit separate API action; this is a workflow guard,
not a claim of cryptographic blindness to synthetic data with published seeds.

Unit tests use unrelated seeds 41–46 and 250 families, including their own
confirmation partition. Production preparation materializes 32,000 source rows;
the other 8,000 remain unmaterialized. Bulk data stays ignored. Commit the code,
this contract and compact manifest before any matching-quality comparison.
