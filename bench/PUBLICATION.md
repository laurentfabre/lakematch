# Durable identity publication

ZR-4 iteration 7 passed through the normal `lakematch cluster` command in fresh processes.

| Batch | Reused existing commit | Process wall s |
|---|---|---:|
| original | False | 43.28 |
| incremental | False | 45.04 |
| incremental | True | 1.28 |
| unchanged | False | 45.41 |
| original | True | 1.25 |

Both original and incremental crosswalks match the independently audited FEBRL3 reference exactly. The incremental journal and merge/split events match the sealed reference. Repeating the same batch returns its original commit; a historical retry cannot rewind the current snapshot. An unchanged-input new batch emits no new identity events. Exactly three commits exist after five CLI calls.

Three separate recovery tests passed, including abrupt writer process death before commit. The prior snapshot remained readable; retry removed the abandoned partial attempt. Published outputs are immutable Parquet directories resolved through one local SQLite commit transaction. Remote Delta publication remains ZR-6 work.

The read-only ZR-4 verifier checks artifact hashes, recomputes cluster metrics and method selection, independently replays journals and compares published Parquet against the sealed reference. It still rejects the current default of 20 rounds because historical verified merge required 21 (the measured envelope was 30). The current full classic/Connect acceptance suite also needs refresh.

- [CLI evidence](../experiments/20260920T014513Z-cluster-cli-8db05b/manifest.json).
- [Process recovery tests](../experiments/20260920T014513Z-publication-recovery-tests-22f9d1/manifest.json).
