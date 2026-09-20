# Serverless execution evidence

Selected workspace: `fevm-gdpr2`. Frozen models and thresholds are unchanged. App/Genie configuration flags do not establish application or delegated API functionality.

| Experiment | Remote run | Result | Cleanup |
|---|---|---|---|
| serverless-frozen-dqx | 299080784128178 | audited pass | verified |
| ↳ all | — | F1 0.988878; absolute local delta 0.000000 | {'left': 3, 'right': 3} quarantined |
| ↳ no_ssn | — | F1 0.986829; absolute local delta 0.000000 | {'left': 3, 'right': 3} quarantined |
| serverless-frozen-native | 622968507486615 | audited pass | verified |
| ↳ all | — | F1 0.988878; absolute local delta 0.000000 | {'left': 3, 'right': 3} quarantined |
| ↳ no_ssn | — | F1 0.986829; absolute local delta 0.000000 | {'left': 3, 'right': 3} quarantined |
| serverless-cluster-fixture | — | missing | untested |

## Retained attempts

- [20260920T024653Z-serverless-frozen-dqx-67e41c](../experiments/20260920T024653Z-serverless-frozen-dqx-67e41c/manifest.json): failed.
- [20260920T030627Z-serverless-frozen-dqx-82125c](../experiments/20260920T030627Z-serverless-frozen-dqx-82125c/manifest.json): passed.
- [20260920T033318Z-serverless-frozen-native-0277ba](../experiments/20260920T033318Z-serverless-frozen-native-0277ba/manifest.json): passed.

## Outstanding evidence

Training/clustering fixture evidence is limited to its small synthetic inputs. Normal remote cluster CLI publication remains unimplemented. Observed DBUs/cost and per-matching-stage Photon task-time shares/operator fallbacks remain missing. Available aggregate query-history timings are audited separately in [PHOTON.md](PHOTON.md). Photon enabled in configuration is not measured Photon execution. The shared warehouse is not campaign-owned.

- serverless-cluster-fixture: No sealed run
