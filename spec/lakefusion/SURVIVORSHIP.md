# Scalar survivorship v1

LM-005 implements a portable, deterministic calculation for trusted workers.
It consumes an approved, immutable policy resolved through the PostgreSQL
registry, a pinned active identity snapshot, an explicit UTC evaluation time and
one current source version for **every** identity member. It returns a calculated
record and explanations. It does not publish, change identity memberships,
authenticate actors, ingest CDC or persist steward approvals.

## Selection policy

The policy pins the domain and source mapping versions and digests, and the
`scalar_survivorship_v1` algorithm. Every scalar domain field has an explicit
rule. The pilot prefers ERP over CRM at equal verification status. Ranking is:

1. An active approved steward override for this master, identity revision and
   policy digest. Its proposer and approver must differ; a reason and decision
   ID are required. Multiple active overrides for one field are a conflict.
2. Verified values before unverified values.
3. Lower source priority number.
4. Higher field quality score (integer 0–100).
5. Newer source effective timestamp.
6. Lexicographically smaller source ID and literal source key.

Verification and quality are explicit trusted upstream assessments, not inferred
from a label, nonempty value or source name. Their assessment reference travels
with each source version. They are synthetic assessments in the demo; this work
does not implement an external verification provider or quality workflow.
An optional minimum quality and maximum age filter precede ranking. Freshness
uses the supplied evaluation time, never the machine clock. Timezone offsets
normalize to UTC and comparisons retain microsecond precision.

## Missing, invalid and deleted values

- An absent field, explicit null and blank string have distinct exclusion
  reasons. None displaces a valid candidate. No implicit type conversion occurs.
- Type-invalid or disallowed values are retained in the input evidence and
  excluded. The pilot allows only `legal_company` record kinds and its declared
  synthetic country codes; an ineligible record kind excludes the entire row.
- Tombstones contain no values or assessments. They exclude that source from
  every field. A missing member is an incomplete snapshot error, not a deletion.
  Duplicate source references (including two different versions) are rejected;
  upstream must supply the explicit current snapshot. No old winning value is
  used as an input or carried forward.
- With no eligible candidate an optional field is null; a required field adds
  a blocking issue. When all members are deleted, `no_live_sources` blocks the
  result even if overrides would fill required fields. IDs are not retired.
- A steward may explicitly clear an optional field with an approved null
  override. Required-null and other invalid overrides fail visibly. Revoked,
  pending and expired overrides are excluded with reasons. Invalid active or
  stale approvals fail; they never quietly fall back to source values.
- An override remains effective after a source deletion because it belongs to
  the master, until revoked, expired or invalidated by a changed identity revision
  or policy. Applying it requires a trusted workflow snapshot; a client-supplied
  `approved` string is not authorization. LM-007/008/011 own that integration.

All alternatives retain their source version, content hash, assessment reference,
eligibility and rank. A winner identifies the first ranking criterion that
distinguishes it from the runner-up, or the approved override decision. Domain,
mapping, policy, implementation, identity revision and complete input hashes
accompany the result. Persisted historic snapshots and publication are LM-006/009.

## Scalar boundary and limits

Arrays and nested values are refused. Pilot country/address/city/postal fields
have a coherence check: if their nonnull winners come from different source
versions or decisions, the calculation is marked `needs_review`. This prevents
an assembled address from being treated as ready. It does not implement tuple
selection or structured address mastering (LM-016).

Maximums: 1,000 source members, 100 scalar fields, 200 override decisions and
4 MiB of canonical request JSON per master. The caller owns snapshot acquisition
and must recheck identity/source/approval watermarks before later publication.
The calculator cannot prove that a supplied snapshot is the latest database state.
Registry resolution checks current domain/mapping/policy approval and immutable
audit events. Previously resolved bindings can replay historical calculations;
retirement does not rewrite history. Neither `calculated` nor `needs_review` is a
publication receipt. Frozen Phase A contracts and prior migrations are unchanged.
