# LF-A evaluation protocol v0.1

Status: **draft for the required user decision; not frozen; no quality run
authorized by this document alone**. Profile: `fevm-gdpr2`. The existing sealed
benchmark confirmation sets and million-record campaign limits remain intact.

## Proposed matching workload and splits

Use the selected synthetic ERP/CRM legal-company domain, with a proposed **10,000 independent
corporate-family groups, two legal companies per group and one record per company
per source**: 20,000 company identities and 40,000 total source rows. Members of
the same family and every alias/source version stay in the same partition.

| Partition | Family groups | Company identities | Total source rows | Use |
|---|---:|---:|---:|---|
| Development | 6,000 | 12,000 | 24,000 | Train and diagnose |
| Validation | 2,000 | 4,000 | 8,000 | Compare candidates, calibrate and select thresholds |
| Untouched confirmation | 2,000 | 4,000 | 8,000 | Evaluate the selected frozen configuration once |

The generator and partition manifest must be committed before comparison runs.
Use generation seed `20260921` and independent perturbation/split seeds recorded
in the manifest. Assign groups before source corruption; opaque source keys
must not encode truth IDs. Keep truth and family metadata outside the engine's
candidate/features inputs. Confirmation data/labels are withheld from tuning;
opening them early invalidates their untouched status.

Predeclare source corruption strata: spelling/legal-suffix variants, missing
identifiers, wrong identifiers/collisions, conflicting/changed addresses,
multilingual names and similar names in different jurisdictions. Freeze counts,
overlaps, generator code and hashes before use. Apply error strata across all
splits independently. A generator built to favor one method is not a neutral
benchmark; retain the historical public corpora only as fixed regression replays.
Synthetic confirmation qualifies this declared synthetic workload, not arbitrary
enterprise data. A real-domain quality claim later needs new representative
labelled evidence under the same no-leakage rules.

The 13-row integration fixture is separate. Use it for business invariants,
mapping, hierarchy, conflict and merge/split tests, never for classifier quality.

## Matching gates and finite envelopes

- Candidate recall ≥95% for every declared pilot task; report misses by stratum,
  truncation and retrieval method. Preserve unknown-pair semantics and count
  known positives lost before classification as false negatives.
- Auto-merge precision lower one-sided 95% confidence bound ≥99.5%. Report
  acceptance coverage, rejected positives, abstentions and review burden. Sample
  at most one audited accepted decision per family for the independent bound;
  use grouped resampling for whole-workload metrics. Fewer than roughly 600
  error-free independent decisions cannot establish the proposed precision gate.
- Compare alternatives at the same caps: **50 candidates per input record,
  2 million retained candidate pairs, 20 million pre-join rows, 4 GiB local Spark
  driver memory and 15 minutes per matching/training run**. A cap hit fails
  feasibility or marks truncation explicitly; it does not justify removing hard
  examples. Initial comparisons contain at most four declared alternatives.
- One remote experiment at a time; at most eight iterations per LF phase,
  including failed experiment iterations, with no reset of old ZR caps. Existing
  Phase A feasibility receipts count toward that limit. Infrastructure retries
  are limited to two and retained separately.
- Declare 30-minute remote job and 60-minute outer experiment bounds at most;
  use smaller bounds for metadata and integration checks. Record resource sizes
  before runs. Do not start a new service or enlarge a run silently to pass a gate.

Candidate cap interpretation (per-left vs both-source queries), negative-label
sampling and exact error-stratum counts must be included in the generator freeze
before any matching experiment. They are not decided from confirmation outcomes.

## Separate serving workloads

Online and graph tests are separate generated serving fixtures, not additional
matching/scale-campaign runs. Their source manifests, seeds and configurations
must be saved before measurements.

- **Resolve:** 100,000 published masters, 20 requests/second; proposed mix 60%
  exact identifier, 30% perturbed names/addresses, 10% no-match inputs. One warm-up
  minute, then five measured minutes. Warm p95 <1 second, with failures and timeout
  rates reported over every request. Cold start measured separately on an owned
  service; no exclusion of error responses from availability statistics.
- **Graph:** 100,000 nodes and one million directed edges at 10 requests/second;
  record edge types, degree distribution, cycles and supernodes. Five measured
  minutes after warm-up. Bounded three-hop p95 <2 seconds, at most 10,000 visited
  nodes and 2,000 returned edges. Truncation is part of the result; compare like
  workloads, not unlimited vendor-advertised traversals.
- **Freshness:** start with **10 source changes/second for 10 minutes**, 80%
  updates, 10% inserts, 10% deletes. Proposed source-to-serving p95 <60 seconds.
  Record source and projection watermarks; verify final state against an
  authoritative rebuild. Measure recovery after a bounded interrupted publisher.
- **Authorization:** fixed role/domain/object/field scenarios across APIs,
  search, graph intermediates and cache paths; revocation is tested independently
  of data freshness. Denied requests must not expose protected records.

These are proposed SLO qualification workloads. Phase A selection freezes the
workload contract; resource sizing is recorded before each later-phase run.

## Cost method

The user waived a dev-workspace spend-ceiling discovery prerequisite; no numeric
dollar ceiling has been supplied. Enforce the finite envelopes above and record
all owned service start/stop times, resource IDs, tags, runtime and sizes.

Attribute billed usage by resource/job ID and experiment time window. Reconcile
system billing after its reporting lag; unresolved attribution stays explicitly
missing. Report observed DBUs and actual currency only where usable price/billing
evidence exists; otherwise label the price calculation as an estimate. Include
app, warehouse, Lakebase, index, storage/synchronization and model-call costs.
Record local hardware/time separately without describing it as cloud billing.

Report per-1,000 input records, candidate pairs and online requests; distinguish
preprocessing, provisioning/cold start, warm execution and idle capacity. Compare
configurations at equal workload and quality. Optional AI is proposed disabled
for the pilot; activation requires a selected provider boundary and token/cost
limits before calls.

## Freeze record

Before quality experiments, record user selection, protocol version/hash,
generator/fixture/split hashes, code revision, feature exclusions, resource/run
bounds and analysis procedure. Append changes as new versions with rationale;
never edit a completed experiment's evidence to satisfy an updated threshold.
Phase A can record an approved workload contract before the later generator is
implemented, but matching execution requires the complete generator/split freeze.
