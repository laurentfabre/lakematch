"""Deterministic, family-disjoint ERP/CRM preparation. No matching or inference.

Truth is kept in a separate artifact. Preparing the default corpus never
materializes confirmation records; final evaluation must explicitly release it.
"""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from lakematch.mastering.contracts import digest

VERSION = "company-pilot-v0.1"
PARTITIONS = ("development", "validation", "confirmation")
FEATURES = ("legal_name", "country", "registration_id", "address_line1", "city", "postal_code")
STRATA = {"clean": 20, "spelling_suffix": 15, "missing_identifier": 20,
          "identifier_collision": 10, "changed_address": 15, "multilingual": 10,
          "cross_jurisdiction_name": 5, "combined": 5}
BRANDS = "Aster Beacon Cedar Delta Ember Falcon Grove Harbor Indigo Juniper Kestrel Linden Maple Nimbus Orchard Pebble Quartz Rowan Summit Thistle Umber Valley Willow Zephyr".split()
MODIFIERS = "Amber Baltic Clear Dawn Eastern Field Global Highland Inland Jade Keystone Lunar Marine Northern Oak Pacific Quiet River Silver Terra Urban Violet Western Zenith".split()
INDUSTRIES = "Supply Trading Logistics Engineering Foods Textiles Energy Materials Systems Components".split()
COUNTRIES = ("FR", "GB", "DE", "NL", "ES", "BE")
SUFFIX = dict(zip(COUNTRIES, ("SAS", "Limited", "GmbH", "BV", "SL", "SA")))
CITIES = {"FR": ("Lyon", "Nantes"), "GB": ("Bristol", "Leeds"), "DE": ("Bonn", "Essen"),
          "NL": ("Delft", "Utrecht"), "ES": ("Bilbao", "Sevilla"), "BE": ("Gent", "Namur")}
TRANSLATIONS = {"Supply": "Approvisionnement", "Trading": "Commerce", "Logistics": "Logistique",
                "Engineering": "Ingénierie", "Foods": "Alimentation", "Textiles": "Tissus",
                "Energy": "Énergie", "Materials": "Matériaux", "Systems": "Systèmes", "Components": "Composants"}


def rank(seed, *key):
    return digest([seed, *key])


def number(seed, *key):
    return int(rank(seed, *key), 16)


def choose(values, seed, *key):
    return values[number(seed, *key) % len(values)]


@dataclass(frozen=True)
class GeneratorSpec:
    families: int = 10_000
    generation_seed: int = 20260921
    split_seed: int = 20260922
    perturbation_seed: int = 20260923
    key_seed: int = 20260924
    order_seed: int = 20260925
    negative_seed: int = 20260926

    def __post_init__(self):
        # This gives integral percentages in every 60/20/20 company partition.
        if type(self.families) is not int or not 250 <= self.families <= 10_000 or self.families % 250:
            raise ValueError("families must be a multiple of 250 in [250, 10000]")
        seeds = [v for k, v in asdict(self).items() if k.endswith("seed")]
        if any(type(v) is not int or v < 0 for v in seeds) or len(set(seeds)) != len(seeds):
            raise ValueError("Seed streams must be distinct nonnegative integers")


def family_partitions(spec):
    ordered = sorted(range(spec.families), key=lambda f: rank(spec.split_seed, "family", f))
    a, b = spec.families * 3 // 5, spec.families * 4 // 5
    return dict(zip(PARTITIONS, (ordered[:a], ordered[a:b], ordered[b:])))


def source_key(spec, source, company):
    return rank(spec.key_seed, "source_key", source, company)[:32]


def _company(spec, company):
    family, member = divmod(company, 2)
    seed = spec.generation_seed
    base_country = number(seed, family, "country") % len(COUNTRIES)
    country = COUNTRIES[(base_country + member * (1 + number(seed, family, "other_country") % 5)) % 6]
    name = " ".join((choose(BRANDS, seed, family, "brand"),
                     choose(MODIFIERS, seed, family, "modifier"),
                     choose(INDUSTRIES, seed, family, "industry"), SUFFIX[country]))
    # No IDs, rank, split or corruption stratum is encoded in a match feature.
    return {"record_kind": "legal_company", "legal_name": name, "country": country,
            "registration_id": f"{number(seed, company, 'registration') % 10**12:012d}",
            "address_line1": f"{1 + number(seed, company, 'house') % 300} {choose(BRANDS, seed, company, 'street')} Road",
            "city": choose(CITIES[country], seed, company, "city"),
            "postal_code": f"{number(seed, company, 'postcode') % 100000:05d}"}


def _corrupt(record, sibling, stratum):
    result = dict(record)
    if stratum in {"spelling_suffix", "combined"}:
        first, rest = result["legal_name"].split(" ", 1)
        result["legal_name"] = first[1] + first[0] + first[2:] + " " + rest.rsplit(" ", 1)[0]
    if stratum in {"missing_identifier", "combined"}:
        result["registration_id"] = None
    if stratum == "identifier_collision":
        # Keep the erroneous tuple within one family, avoiding cross-split donors.
        result["registration_id"] = sibling["registration_id"]
        result["country"] = sibling["country"]
    if stratum in {"changed_address", "combined"}:
        result["address_line1"] = "900 New Market Avenue"
        result["postal_code"] = "00000"
    if stratum == "multilingual":
        for original, translated in TRANSLATIONS.items():
            result["legal_name"] = result["legal_name"].replace(original, translated)
    if stratum == "cross_jurisdiction_name":
        result["legal_name"] = sibling["legal_name"]
    return result


def _source_row(spec, source, company, payload):
    parent = source_key(spec, source, company - 1) if company % 2 else None
    key = source_key(spec, source, company)
    if source == "erp_vendor":
        names = ("vendor_id", "record_type", "vendor_name", "country_code", "registration_number",
                 "street", "city", "postal_code", "parent_vendor_id")
    else:
        names = ("account_id", "account_type", "account_name", "country", "company_registration",
                 "billing_street", "billing_city", "billing_postcode", "parent_account_id")
    return dict(zip(names, (key, payload["record_kind"], *(payload[f] for f in FEATURES), parent)))


def build_partition(spec, partition, *, release_confirmation=False):
    if partition not in PARTITIONS:
        raise ValueError("Unknown partition")
    if partition == "confirmation" and not release_confirmation:
        raise ValueError("Confirmation is withheld until a separately frozen final evaluation")
    families = family_partitions(spec)[partition]
    companies = [2 * family + member for family in families for member in (0, 1)]
    assignment = sorted(companies, key=lambda c: rank(spec.perturbation_seed, partition, c))
    strata, start = {}, 0
    for stratum, percent in STRATA.items():
        end = start + len(companies) * percent // 100
        strata.update({company: stratum for company in assignment[start:end]})
        start = end
    sources = {"erp_vendor": [], "crm_account": []}
    truth = []
    for company in companies:
        base, sibling = _company(spec, company), _company(spec, company ^ 1)
        sources["erp_vendor"].append(_source_row(spec, "erp_vendor", company, base))
        sources["crm_account"].append(_source_row(spec, "crm_account", company,
                                                _corrupt(base, sibling, strata[company])))
        truth.append({"company": company, "family": company // 2, "stratum": strata[company],
                      "erp_key": source_key(spec, "erp_vendor", company),
                      "crm_key": source_key(spec, "crm_account", company)})
    for source, key in (("erp_vendor", "vendor_id"), ("crm_account", "account_id")):
        sources[source].sort(key=lambda row: rank(spec.order_seed, source, row[key]))
    return {"sources": sources, "truth": truth}


def matching_projection(mapping, rows):
    """Routing key stays outside the explicitly allowlisted match-feature object."""
    output = []
    for row in rows:
        receipt = mapping.apply(row)
        output.append({"record_id": receipt["source_key"],
                       "features": {f: receipt["payload"][f] for f in FEATURES}})
    return output


def training_pairs(spec, partition, truth):
    """All positives, one sibling and four unrelated negatives per ERP anchor.

    Only for development fitting; validation/confirmation precision must use
    full retrieved decisions, not these deliberately enriched negatives.
    """
    if partition != "development":
        raise ValueError("Sampled fitting pairs are development-only")
    lookup = {row["company"]: row for row in truth}
    companies = sorted(lookup)
    pairs = []
    for company in companies:
        row = lookup[company]
        pairs.append({"erp_key": row["erp_key"], "crm_key": row["crm_key"], "label": 1})
        negatives = [company ^ 1]
        draw = 0
        while len(negatives) < 5:
            other = companies[number(spec.negative_seed, company, draw) % len(companies)]
            draw += 1
            if other // 2 != company // 2 and other not in negatives:
                negatives.append(other)
            if draw > 1000:
                raise RuntimeError("Negative-sampling bound exceeded")
        pairs.extend({"erp_key": row["erp_key"], "crm_key": lookup[other]["crm_key"], "label": 0}
                     for other in negatives)
    return pairs


def preparation_manifest(spec):
    partitions = family_partitions(spec)
    return {"schema_version": 1, "generator": VERSION, "spec": asdict(spec),
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "partitions": {p: {"families": len(fs), "companies": len(fs) * 2, "source_rows": len(fs) * 4,
                                "family_assignment_sha256": digest(fs),
                                "stratum_company_counts": {s: len(fs) * 2 * n // 100 for s, n in STRATA.items()}}
                           for p, fs in partitions.items()},
            "matching_features": list(FEATURES),
            "excluded_features": ["record_id", "source_id", "parent_source_key", "family", "company", "stratum", "partition"],
            "candidate_orientation": "ERP left queries CRM right in same partition; 50 unique CRM candidates per ERP after union",
            "negative_sampling": "development only: all positives + one sibling + four distinct other-family CRM rows per ERP",
            "confirmation_materialized": False, "files": {}}


def prepare(output, spec=GeneratorSpec()):
    """Write once to a new directory. No confirmation rows or labels are opened."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = preparation_manifest(spec)
    for partition in ("development", "validation"):
        data = build_partition(spec, partition)
        artifacts = {**data["sources"], "truth": data["truth"]}
        if partition == "development":
            artifacts["training_pairs"] = training_pairs(spec, partition, data["truth"])
        if Counter(row["stratum"] for row in data["truth"]) != manifest["partitions"][partition]["stratum_company_counts"]:
            raise ValueError("Corruption allocation differs from the declared manifest")
        for name, rows in artifacts.items():
            path = output / f"{partition}.{name}.jsonl"
            raw = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode()
            path.write_bytes(raw)
            manifest["files"][path.name] = {"rows": len(rows), "sha256": hashlib.sha256(raw).hexdigest()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
