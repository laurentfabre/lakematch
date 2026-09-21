# Proposed company/supplier pilot fixture

These **13 entirely synthetic rows** propose ERP vendor and CRM account schemas
for the pending Phase A source decision. Six legal companies have one record in
each source; one additional CRM row is a branch of a legal company. This is an
integration fixture, not a training, validation or confirmation dataset.

- `domain.json` defines the proposed legal-company contract.
- `erp_vendor_mapping.json` and `crm_account_mapping.json` bind literal source
  columns to the exact domain definition hash, using allowlisted transforms.
- `fixture.json` separates source records from truth, expected exceptions and
  mutation scenarios. Truth must never be passed as matching features.
- `manifest.json` records canonical-JSON hashes and counts; it is explicitly a
  draft fixture manifest, not an evaluation freeze.

The examples include a shared address between distinct related companies, similar
names across countries, a conflicting address, an erroneous identifier shared
by distinct companies, and a branch that must not become another legal-company
master. Merge/split, source update and deletion scenarios are specified for later
acceptance. Matching, survivorship and mutation execution are not implemented by
this fixture or its mapping validator.

`DomainContract`/`SourceMapping` currently validate scalar types, source-schema
drift, required fields, version binding and deterministic mapping receipts.
Business eligibility, reference resolution and golden-value policy are later
services. A syntactically valid `record_kind=branch` is not permission to merge
that row into the legal-company domain.
