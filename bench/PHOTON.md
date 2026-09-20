# Serverless Photon evidence — incomplete

The campaign pipeline `887f3271-3247-4082-82a9-9b62fb89e135` on
`fevm-gdpr2` has `serverless: true` and `photon: true`. Its corrected update
`8a8613de-98c0-4e67-835e-3fca82830d18` completed the candidates, features,
scores and links flows. These configuration and flow observations do not
establish the share of execution time spent in Photon.

The pipeline events API exposes flow status, output counts and planning
information in its raw `details` object; the CLI's typed event output omits
that object. The runner now preserves raw details. A query-history request
restricted to this run's time window, user and campaign objects returned no
matching queries during execution or after terminal cleanup. The bounded
terminal capture retrieved all 16 completed flow records; all event and query
pages were consumed. [Receipt](../experiments/serverless-dqx-profile.json).
The first capture exceeded the API's 250-event page limit; the rejected request
and corrected capture are both retained in the experiment ledger.

| Required observation | State |
|---|---|
| Photon task time / total task time per matching stage | Missing |
| Executed operators and every fallback operator | Missing |
| Campaign-attributed DBUs and observed cost | Unreconciled |

No percentage, zero-cost figure or claim of full Photon execution is inferred
from native SQL expressions or from an enabled setting. ZR-6 remains incomplete
until executed query profiles support these measurements. No alternate
Databricks profile was selected to obtain them.
