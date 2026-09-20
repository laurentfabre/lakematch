# Serverless Photon evidence — incomplete

Completed DQX run `299080784128178` on `fevm-gdpr2`. [Terminal capture](../experiments/serverless-dqx-profile-v2.json); query IDs and hashes are in [the index](photon_index.json).

The Query History API reports cumulative execution time for all tasks and for Photon tasks. The ratios below sum those milliseconds across the exact job-task query IDs. They exclude provisioning and are not wall-clock percentages.

| Job task | Queries | All task ms | Photon task ms | Photon share |
|---|---:|---:|---:|---:|
| prepare | 16 | 11,310 | 1,995 | 17.64% |
| pipeline | 16 | 183,699 | 7,008 | 3.81% |
| audit | 8 | 3,337 | 2,960 | 88.70% |

## Remaining acceptance evidence

The pipeline row aggregates its 16 refresh queries. Query text is redacted and no query tags identify the output table, so this capture does not assign query timings to individual candidate, feature, scoring or link stages. Raw events contain the 16 completed flows and planning summaries, but no complete executed operator profiles. The attempted query-profile export route returned `ENDPOINT_NOT_FOUND`; no alternate profile was selected.

The documented export route is the query-profile UI Download action, which saves JSON. The reviewed public documentation does not establish a supported REST export. [Research receipt](../experiments/query-profile-export-research.json). Exporting the pipeline query profiles from this workspace is still required.

Every fallback operator, per-matching-stage Photon share, campaign-attributed DBUs and observed cost remain missing. No cause for the low aggregate Photon share is inferred from timing alone. ZR-6 remains incomplete.

## Capture corrections

The first raw-event request exceeded the API limit of 250 events per page. The next capture filtered only SQL text and returned zero matches because the text is redacted. The corrected capture uses exact job-task IDs, retains all 40 queries, and restricts events to the completed run window. All earlier requests and files are retained; new captures use immutable directories.
