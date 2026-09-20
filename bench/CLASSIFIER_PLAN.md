# ZR-3 classifier comparison plan

Declared before this sweep. Retrieval observations and ZR-2 feature ablations are
validation evidence. Confirmation/test labels remain outside fitting, tuning,
method choice and metric computation. `PROTOCOL.md` retains the seeds, weighting,
bootstrap and simpler-choice rule.

Iteration 2 compares the full factorial of three string settings (Levenshtein,
Jaro-Winkler, both) and three estimators (GBT, logistic regression, random forest).
Use 20 iterations/trees, tree depth 3, estimator seed 0, the three native multi-token
families, embeddings off, and training-only feature IDF. GBT/Levenshtein is the
paired-bootstrap reference. Report feature construction, fit, score, logging and
complete run times separately. Jaro-Winkler requires the explicit optional UDF
switch and cannot become the default Photon path.
Retain local Spark event logs for whole-application shuffle, spills, per-task
execution memory and duration skew, including retries. These are not process RSS
or remote Photon profiles.

The nine declared corpus runs are FEBRL4-half-unmatched all-fields, SSN-hidden,
SSN+DOB-hidden diagnostic, BPID, Abt-Buy, Leipzig Affiliations, Amazon-Google,
Walmart-Amazon and DBLP-ACM. One active local experiment, 900 seconds per corpus,
135-minute total wall ceiling, zero remote/live-label spend. An infrastructure
failure stops the sequence for diagnosis. Each trial logs the composite model
with its validation-selected threshold/policy and exact consumed training labels.

For this factorial, FEBRL uses the gram-top-k reference retrieval, complete
5,000-left/2,500-right universe, and training pairs with both endpoints in the
training partition. Supplied-pair corpora retain their declared pair task;
unlabelled retrieved pairs are never presumed negative. Report mean-Levenshtein
threshold and nearest-neighbour baselines on the relevant evaluation pair set.
Nearest-neighbour on a supplied-pair dataset is conditional on those supplied
pairs, not a full-universe retrieval claim. Frozen-grid thresholds are 0.00–1.00
in steps of 0.01, with ties choosing the higher threshold.

Compare unrestricted, many-to-one and one-to-one decisions on FEBRL. On supplied
pairs, omit many-to-one if known training/validation positives give an anchor
multiple partners; omit one-to-one if either side has multiple known partners.
Unknown cardinality is not claimed proven from sampled pairs. Report these
restrictions and the conservative no-reassignment behavior of one-to-one.
All cardinality decisions use complete validation candidate sets before scoring.

Macro F1 weights the seven selection corpora equally; FEBRL all/SSN-hidden share
its weight. Diagnostic SSN+DOB-hidden does not vote. Defaults require the
predeclared paired evidence and portability requirements; this sweep alone does
not promote a model or score confirmation. A following bounded comparison must
measure all candidate configurations with the selected scoring pipeline on the
closed-world FEBRL tasks, and the final selected pipeline must satisfy latency.
