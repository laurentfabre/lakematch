# Initial engine evidence (ZR-1)

This is implementation verification, not benchmark acceptance or method selection. No ZR-2–9
gate is claimed. The historical benchmark remains unchanged under `spec/bench/`.

The independent candidate implementation uses binary term vectors weighted by
`idf(g) = 1 + log((N_left + N_right + 1)/(df_left(g) + df_right(g) + 1))`.
Grams exceeding the per-side document-frequency cap are removed from the numerator and both
norms. Side-only retained grams still contribute to the relevant norm. This is a transductive
retrieval statistic, not a supervised feature fit. Future inductive evaluations must distinguish it.

Before the exploded join, its exact projected row count is `sum_g df_left(g) * df_right(g)`.
The job checks that value against `max_join_rows`; top-k and a separate final `max_pairs` check
do not replace that check. Hot keys, capped norms and weighted scores have independent numerical
tests. A scalar guard also protects the lazy plan, but declarative deployments must run the
job-time budget preflight before publishing that plan.

All ties use record IDs. `many_to_one` takes each anchor's best above-threshold partner;
`one_to_one` then retains each partner's best anchor. Losing anchors are rejected rather than
reassigned. This conservative policy is not an optimal bipartite assignment. `unrestricted`
keeps every distinct above-threshold pair. These are hypotheses awaiting validation comparisons.

`quality.apply_and_split` quarantines all duplicate-ID occurrences, missing IDs and configured
error violations. Warnings remain on valid rows. Dataset minimum-row checks and row-level
required/regex/range checks are native expressions. Empty datasets remain empty; dataset-level
failure reporting on an empty dataset needs a separate job diagnostic in a later iteration.

Default ZR-1 features are normalized Levenshtein, equality, soundex agreement and a missingness
indicator for each configured field, plus candidate score/rank/gap. Soundex is an initial generic
feature, not a claimed suitable feature for every field type. Type-specific families, token
features and optional embeddings remain ZR-2. Future method names are accepted by config and
fail explicitly if execution is not implemented.

| Evidence | Run |
|---|---|
| Initial classic suite: 29 passed | `20260919T211515Z-tests-classic-436a1b` |
| Initial Connect suite: same 29 passed | `20260919T211625Z-tests-connect-2683b4` |
| Offline synthetic CLI: external egress denied, 6 links, 1 quarantine, 12.21s process wall | `20260919T212127Z-offline-run-130500` |
| Full original FEBRL4 CLI, 5000×5000 records; development labels only | `20260919T212205Z-febrl4-run-395d22` |

The first unrestricted process failed because the Codex sandbox denied localhost Java sockets.
Offline-policy failures are retained: an overbroad local-endpoint rule initially allowed external
egress, unsupported literal IP syntax failed compilation, and overly strict inbound restrictions
blocked Java. The successful policy denies external outbound traffic; Spark binds to loopback.
An external TCP probe must fail with an OS permission error before the engine starts.

The FEBRL4 smoke labels contain closed-world truth for the first 80 sorted development anchors.
The run is neither held out nor half-unmatched. Its timing is not evidence for the ZR-3 60-second
held-out thresholds. Corpus preparation, file hashes and provenance are recorded separately.

`verify_zr.sh` reads evidence without executing experiments. Missing, failed, skipped, modified or
stale evidence must fail. ZR-2–9 fail explicitly while their acceptance implementations are absent.

Final ZR-1 acceptance on source `b207875989358f2aef9ad91936ee1bdd5c96cf1752ad4be9086188a4da56f5fe`:

| Check | Result | Run ID |
|---|---|---|
| Wheel build, isolated install, private repository | Passed | `20260919T212733Z-package-build-ed4b8c` |
| Classic local suite | 38 passed, 0 skipped | `20260919T212735Z-tests-classic-917be5` |
| Local Spark Connect suite | Same 38 passed, 0 skipped | `20260919T212756Z-tests-connect-df8d35` |
| Offline synthetic CLI | 6 links, 1 quarantine; 11.89s process wall | `20260919T212815Z-offline-run-78e12c` |
| Original FEBRL4 CLI | 5000 links, 25000 candidates; 69.96s process wall | `20260919T212827Z-febrl4-run-717037` |

FEBRL4 projected shared-gram join: 143,495,923 rows before pruning, 34,286,606 after dropping
115 hot grams, below the configured 50,000,000-row ceiling. This demonstrates why top-k is not
a pre-join resource bound. No held-out precision/recall or half-unmatched timing is claimed here.
The read-only verifier returned exit 0 after all five checks completed.

The final evidence fingerprint now enumerates every relevant file and excludes remote-only launcher
files from ZR-1. It was reverified after that verifier change on source
`2055cefa2db87683c5c0fccaddd3b26e1bb6d67b8b5a64c76788d53a4774cb0e`:
`20260919T213356Z-package-build-fcd7cb`, `20260919T213357Z-tests-classic-1bf7cb`,
`20260919T213418Z-tests-connect-c16f95`, `20260919T213437Z-offline-run-3bfee5`,
`20260919T213449Z-febrl4-run-95499e`. Results remained 38/38 in both modes, 6 offline links,
1 quarantine and 5000 original FEBRL4 links. FEBRL4 process wall time was 69.18s.

Early serverless canary `20260919T213142Z-serverless-canary-fe69f9` completed successfully
(remote run `280837437066970`, task `606308276009425`). Actual runtime: Spark 4.2.0,
Python 3.12.3, MLflow 3.16.0. All 3 expected synthetic links were produced; cache was explicitly
unsupported and all materializations used owned Delta tables. Save/reload predictions were equal
within 1e-12. MLflow run `f4f76eee021c467bb4092c6b5fe9cf49` contains the canary report.
Setup was 115s and task execution 114s (in-notebook measured work 78.19s).

A read-back verified no scratch tables remained, the shared warehouse remained STOPPED, and
predictive optimization was DISABLE on the campaign schema. This is early platform evidence,
not ZR-5/6 parity, UC registration or fresh-session model acceptance. Billing is unreconciled.
Jobs chose PERFORMANCE_OPTIMIZED when the launcher omitted a performance target; the launcher
now explicitly requests STANDARD. The first run is retained with that configuration discrepancy.

Follow-up review added an empty-record regression: separators between entirely missing fields must
not become candidate grams. The candidate text is now trimmed before gram generation. Both Spark
modes passed the resulting 39-test suite. The verifier then caught a runner race: a JVM shutdown
hook wrote to stderr after its checksum was recorded. The runner now waits for the entire owned
process group to exit before sealing log artifacts; current-source acceptance is being refreshed.

The first explicit STANDARD canary (`954441146199150`, local experiment
`20260919T213718Z-serverless-standard-cbc3bc`) timed out: 145s setup, 169s execution,
315.1s run duration. It produced no success result, and the post-timeout scratch inventory was empty.
A single changed retry allows a 600s task and 900s total run envelope, while keeping STANDARD.

Current accepted ZR-1 source is `87bb4c9923c70edbb147dd0dd73f29faadc627f7c15a8ebfd8c6362e52645a0c`.
The log-sealing race is fixed and `verify_zr.sh 1` returns 0. Final records:
`20260919T214526Z-package-build-b6c9cf`, `20260919T214527Z-tests-classic-24f16b`,
`20260919T214550Z-tests-connect-acfc1b`, `20260919T214609Z-offline-run-f07b13`,
`20260919T214622Z-febrl4-run-5ab497`. Both suites passed all 39 checks with no skips;
offline output remained 6 links/1 quarantine; full original FEBRL4 produced 5000 links in
70.66s process wall including startup, shutdown and verified process-group cleanup.
The later evaluation protocol is predeclared in [PROTOCOL.md](PROTOCOL.md); its comparisons
and confirmation scoring have not started.

The updated engine also passed the STANDARD retry, remote run `667945925462279`, experiment
`20260919T214533Z-serverless-standard-91d0f6`: 176s setup, 268s execution, 244.01s notebook work,
three expected links, equal reloaded predictions and scratch cleanup. MLflow run:
`a8f8a13d5253422c98cefecef4deff9d`. The final inventory contains no campaign clusters or tables;
the shared warehouse is STOPPED. Billing remains unreconciled. The startup and execution figures
are individual observations, not a paired performance/DBU comparison.
# Expanded-engine revalidation (2026-09-20 local date)

Source `1d9451e2f33e052816efc6421fd0433006d84046308d89b10ca5df3369dcc0f6`
passes the read-only ZR-1 verifier after the typed-feature additions. Classic and
Connect run the same **65 tests**, with zero skips. Wheel/private-repository,
OS-denied-egress synthetic execution and full original FEBRL4 smoke pass.
The original FEBRL process wall time is **71.21 seconds**; it remains development
smoke evidence and does not satisfy the separate ZR-3 held-out latency gate.
Run IDs are `20260919T223809Z-package-build-1ae404`,
`20260919T223810Z-tests-classic-90537b`, `20260919T223838Z-tests-connect-11ba06`,
`20260919T223904Z-offline-run-d1c9ec`, and `20260919T223916Z-febrl4-run-ff4b60`.
