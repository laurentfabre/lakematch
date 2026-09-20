# Leipzig Affiliations reference

The [official dataset page](https://dbs.uni-leipzig.de/research/projects/benchmark-datasets-for-entity-resolution)
cites David Aumueller and Erhard Rahm, **Web-based Affiliation Matching** (2009),
and *Affiliation analysis of database publications* for its Affiliations download.
It lists 2,260 affiliation strings, 32,816 matching pairs and 330 clusters.

The [cited 2009 paper](https://dbs.uni-leipzig.de/files/research/publications/2009-11/pdf/aumueller2009iciq.pdf)
describes a test database of **2,450 variants / 670 institutions with locations**
on PDF page 7. Its Table 3, PDF page 8, reports each method at the threshold
giving its highest F-measure:

| Method / Table 3 row | Precision | Recall | F1 | Threshold |
|---|---:|---:|---:|---|
| Soft TF-IDF / 1 | 0.286 | 0.272 | 0.279 | 0.7 |
| Soft TF-IDF with same location / 2 | 0.840 | 0.300 | 0.442 | 0.5 × 1 |
| Google distance-weighted overlap of 8 result URLs / 9 | 0.895 | 0.777 | 0.832 | 0.3 |

These are historical context, not a direct comparison with lakematch's held-out
supplied-pair task. Entity and cluster counts differ; the paper uses institution
and location extraction, external web-search results, and threshold selection
on its evaluation set. There is no common independently held-out partition.
No web searches for individual affiliation records were performed in this campaign.

The brief's attribution to “FAMER papers” is not supported by the inspected
[Scalable Matching and Clustering of Entities with FAMER](https://dbs.uni-leipzig.de/files/research/publications/2018-11/pdf/FAMER-2407-8454-1-SM.pdf).
Its Section 5.1/Table 3 evaluates geographic settlements, MusicBrainz and
North Carolina voters. An Affiliations FAMER F1 must not be inferred from those
results. The actual dataset citation above supplies the extracted reference.

Retrieved 2026-09-20. [Structured extraction and file hashes](affiliations_reference.json)
identify local archived source PDFs, extracted text and the dataset page under
`data/references/`. No change to benchmark models, data or thresholds follows.
