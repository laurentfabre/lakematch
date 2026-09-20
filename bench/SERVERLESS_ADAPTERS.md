# Lazy serverless adapter evidence

Offline local validation only. Remote SDP execution and Photon support require separate measurements.

| Check | Result | Process seconds | Evidence |
|---|---|---:|---|
| dqx-parity | 2 valid / 4 quarantined; exact reasons and multiplicity; no definition-time actions | 8.88 | [20260920T030209Z-dqx-parity-9c802b](../experiments/20260920T030209Z-dqx-parity-9c802b/manifest.json) |
| native-ml-all | 14 hash cases; exact keys/candidates; 4985 scores; maximum delta 1.39e-16 | 37.42 | [20260920T030218Z-native-ml-all-b8a98f](../experiments/20260920T030218Z-native-ml-all-b8a98f/manifest.json) |
| native-ml-no_ssn | 14 hash cases; exact keys/candidates; 4983 scores; maximum delta 1.42e-16 | 34.25 | [20260920T030256Z-native-ml-no_ssn-404afb](../experiments/20260920T030256Z-native-ml-no_ssn-404afb/manifest.json) |

The first native check failed on a harness column-name collision (`Row.index`). That failed run is retained. Iteration 2 fixed bracket-based column access; the SQL hash expression was unchanged. [Predeclared plan](SERVERLESS_ADAPTER_PLAN.md). No model or threshold was fitted or changed.
