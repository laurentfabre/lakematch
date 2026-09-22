# Company/supplier pilot integration fixture

These **13 entirely synthetic rows** implement the selected ERP vendor and CRM
account source proposal (LF-DEC-001). Six legal companies have one record in
each source; one additional CRM row is a branch of a legal company. This is an
integration fixture, not a training, validation or confirmation dataset.

- `domain.json` defines the legal-company contract.
- `erp_vendor_mapping.json` and `crm_account_mapping.json` bind literal source
  columns to the exact domain definition hash, using allowlisted transforms.
- `fixture.json` separates source records from truth, expected exceptions and
  mutation scenarios. Truth must never be passed as matching features.
- `survivorship_policy.json` adds a scalar policy for registry approval over the
  frozen domain and mappings: verification, ERP/CRM precedence, quality,
  freshness and deterministic ties. [Policy behavior and limits](../../../spec/lakefusion/SURVIVORSHIP.md).
- `manifest.json` records canonical-JSON hashes and counts; it is explicitly a
  draft fixture manifest, not an evaluation freeze.

The examples include a shared address between distinct related companies, similar
names across countries, a conflicting address, an erroneous identifier shared
by distinct companies, and a branch that must not become another legal-company
master. The identity worker now exercises merge/split; the scalar worker exercises
source update/deletion and approved override calculations. The fixture and its
mapping validator alone do not execute these operations. See the
[measured Phase B evidence](../../../bench/lakefusion/PHASE_B.md).

`DomainContract`/`SourceMapping` currently validate scalar types, source-schema
drift, required fields, version binding and deterministic mapping receipts.
Company retrieval and scalar selection enforce business eligibility; reference
resolution remains later work. A syntactically valid `record_kind=branch` is not permission to merge
that row into the legal-company domain.
