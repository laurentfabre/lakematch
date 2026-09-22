"""Export the six-company synthetic slice for the isolated Python 3.11 APX app.

This is a demo build, not an acceptance/quality experiment or a publication to a
workspace. No database, corpus, model, customer data or network is accessed.
"""
import argparse
import json
from pathlib import Path

from lakematch.mastering.contracts import digest
from lakematch.mastering.lineage import build_snapshot, entity_detail
from lakematch.mastering.match_contract import FIELDS, MatchBinding, MatchRuleset
from lakematch.mastering.match_evidence import compare_pair, implementation_digest
from lakematch.mastering.survivorship_contract import MappingPin
from lakefusion_lineage_fixture import dataset
from lakefusion_survivorship_fixture import fixture

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "app/src/lakematch_review/demo/company_lineage.json"


def export():
    data = dataset()
    policy, _, _ = fixture()
    rules = MatchRuleset("synthetic_company_comparison", 1, policy.domain.domain_id,
                        policy.domain.version, policy.domain.sha256,
                        tuple(MappingPin(m.source_id, m.version, m.sha256) for m in policy.mappings),
                        implementation_digest())
    comparison_binding = MatchBinding(rules, policy.domain, policy.mappings)
    first = build_snapshot("first", data["first"], data["context"], expected_previous=None)
    second = build_snapshot("second", data["second"], data["context"], expected_previous="first", previous=first)
    publications = []
    for snapshot in (first, second):
        entities = []
        for master in snapshot["tables"]["golden_records"]:
            detail = entity_detail(snapshot, master["master_id"])
            binding = detail["contract"]["binding"]
            comparison = compare_pair(comparison_binding,
                *[{k: s[k] for k in ("source_id", "source_key", "version", "mapping_version", "mapping_sha256", "deleted", "values")}
                  for s in detail["sources"]], candidate_methods=[], pair_origin="explicit_comparison")
            comparison_display = {
                "schema_version": comparison["schema_version"], "pair_origin": comparison["pair_origin"],
                "pair_id": comparison["pair_id"], "evidence_sha256": comparison["evidence_sha256"],
                "ruleset_id": rules.ruleset_id, "ruleset_version": rules.version, "ruleset_sha256": rules.sha256,
                "algorithm": rules.algorithm, "implementation_sha256": rules.implementation_sha256,
                "records": [{k: r[k] for k in ("source_id", "source_key", "version", "deleted")} for r in comparison["records"]],
                "fields": [{"name": name, **comparison["fields"][name]} for name in FIELDS],
                "rules": comparison["rules"], "decision": comparison["decision"],
                "probability": comparison["probability"], "qualification": comparison["qualification"],
            }
            fields = []
            for name, field in detail["fields"].items():
                winner = field["winner"]
                decision = next((o["decision"] for o in detail["overrides"]
                                 if winner and o["decision"]["decision_id"] == winner.get("decision_id")), None)
                fields.append({"name": name, "value": detail["values"][name], "reason": field["reason"],
                    "conflicting_values": field["conflicting_values"],
                    "winner_source_id": winner.get("source_id") if winner else None,
                    "winner_source_key": winner.get("source_key") if winner else None,
                    "winner_version": winner.get("version") if winner else None,
                    "decision_id": decision["decision_id"] if decision else None,
                    "decision_reason": decision["reason"] if decision else None,
                    "approved_by": decision["approved_by"] if decision else None,
                    "alternatives": [{"source_id": a["source"]["source_id"], "source_key": a["source"]["source_key"],
                        "version": a["source"]["version"], "value": a["value"], "excluded": a["excluded"],
                        "verified": a["assessment"]["verified"] if a["assessment"] else None,
                        "quality": a["assessment"]["quality"] if a["assessment"] else None}
                        for a in field["alternatives"]]})
            entities.append({"master_id": detail["master_id"], "revision": detail["revision"],
                "identity_revision": detail["identity_revision"], "values": detail["values"], "fields": fields,
                "policy_id": binding["policy"]["policy_id"], "policy_version": binding["policy"]["version"],
                "policy_sha256": binding["policy_sha256"],
                "comparison": comparison_display,
                "sources": [{k: s[k] for k in ("source_id", "source_key", "version", "deleted", "updated_at", "values")}
                            for s in detail["sources"]]})
        publications.append({"publication_id": snapshot["publication_id"], "snapshot_sha256": snapshot["snapshot_sha256"],
                             "as_of": data["first"][0]["calculation"]["inputs"]["as_of"], "entities": entities})
    result = {"schema_version": 2, "kind": "synthetic_company_demo", "membership_basis": "synthetic_fixture_truth",
              "default_master_id": data["cedar_id"], "publications": publications}
    return {**result, "bundle_sha256": digest(result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare the packaged demo with current source fixtures")
    args = parser.parse_args()
    content = json.dumps(export(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.check:
        if DESTINATION.read_text() != content:
            raise SystemExit("Golden demo differs; rebuild and review the fixture changes")
    else:
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        DESTINATION.write_text(content)
    print(f"Synthetic golden demo: 6 companies, 2 publications, {len(content.encode()):,} bytes")


if __name__ == "__main__":
    main()
