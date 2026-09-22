"""Read-only packaged synthetic provenance; no customer/workspace data adapter."""
import hashlib
from importlib.resources import files
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DemoModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoAlternativeOut(DemoModel):
    source_id: str
    source_key: str
    version: int
    value: str | None
    excluded: str | None
    verified: bool | None
    quality: int | None


class DemoFieldOut(DemoModel):
    name: str
    value: str | None
    reason: str
    conflicting_values: bool
    winner_source_id: str | None
    winner_source_key: str | None
    winner_version: int | None
    decision_id: str | None
    decision_reason: str | None
    approved_by: str | None
    alternatives: list[DemoAlternativeOut] = Field(max_length=2)


class DemoSourceOut(DemoModel):
    source_id: str
    source_key: str
    version: int
    deleted: bool
    updated_at: str
    values: dict[str, str | None]


class DemoEntityOut(DemoModel):
    master_id: str
    revision: int
    identity_revision: int
    values: dict[str, str | None]
    fields: list[DemoFieldOut] = Field(max_length=8)
    policy_id: str
    policy_version: int
    policy_sha256: str
    sources: list[DemoSourceOut] = Field(max_length=2)


class DemoPublication(DemoModel):
    publication_id: Literal["first", "second"]
    snapshot_sha256: str
    as_of: str
    entities: list[DemoEntityOut] = Field(min_length=6, max_length=6)


class DemoBundle(DemoModel):
    schema_version: Literal[1]
    kind: Literal["synthetic_company_demo"]
    membership_basis: Literal["synthetic_fixture_truth"]
    default_master_id: str
    publications: list[DemoPublication] = Field(min_length=2, max_length=2)
    bundle_sha256: str


class DemoCompanyOut(DemoModel):
    master_id: str
    legal_name: str
    country: str


class DemoCatalogOut(DemoModel):
    kind: Literal["synthetic_company_demo"] = "synthetic_company_demo"
    default_master_id: str
    publications: list[Literal["first", "second"]]
    companies: list[DemoCompanyOut]


class DemoDetailOut(DemoModel):
    kind: Literal["synthetic_company_demo"] = "synthetic_company_demo"
    membership_basis: Literal["synthetic_fixture_truth"] = "synthetic_fixture_truth"
    publication_id: Literal["first", "second"]
    snapshot_sha256: str
    as_of: str
    entity: DemoEntityOut


def read_demo():
    path = files("lakematch_review").joinpath("demo/company_lineage.json")
    with path.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Packaged demo exceeds 1 MiB")
    payload = json.loads(raw)
    expected = payload.pop("bundle_sha256")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != expected:
        raise ValueError("Packaged demo checksum differs")
    bundle = DemoBundle.model_validate({**payload, "bundle_sha256": expected})
    if [p.publication_id for p in bundle.publications] != ["first", "second"]:
        raise ValueError("Packaged demo publications differ")
    ids = {e.master_id for e in bundle.publications[0].entities}
    if len(ids) != 6 or bundle.default_master_id not in ids or ids != {e.master_id for e in bundle.publications[1].entities}:
        raise ValueError("Packaged demo identities differ")
    return bundle


def catalog(bundle):
    return DemoCatalogOut(default_master_id=bundle.default_master_id,
        publications=[p.publication_id for p in bundle.publications],
        companies=[DemoCompanyOut(master_id=e.master_id, legal_name=e.values["legal_name"] or "Unnamed company",
                                  country=e.values["country"] or "Unknown")
                   for e in bundle.publications[0].entities])


def detail(bundle, master_id, publication):
    snapshot = next(p for p in bundle.publications if p.publication_id == publication)
    entity = next((e for e in snapshot.entities if e.master_id == master_id), None)
    if entity is None:
        return None
    return DemoDetailOut(publication_id=snapshot.publication_id, snapshot_sha256=snapshot.snapshot_sha256,
                         as_of=snapshot.as_of, entity=entity)
