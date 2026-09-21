import pytest

from lakematch.mastering.retrieval import BudgetExceeded, Limits, normalize, retrieve


def row(key, name="Énergie Orchard SAS", registration="001", country="FR", address="8 River Road"):
    return {"record_id": key, "features": {"legal_name": name, "country": country,
            "registration_id": registration, "address_line1": address, "city": "Lyon", "postal_code": "00100"}}


def test_union_recovers_missing_identifier_and_preserves_provenance():
    left, right = [row("a")], [row("b", name="Energie Orchard", registration=None)]
    assert retrieve(left, right, "identifier")["retained_pairs"] == 0
    result = retrieve(left, right)
    assert result["rows"][0]["candidates"] == [{"right_id": "b", "methods": ["name", "tokens"]}]
    assert normalize("Énergie---ORCHARD") == "energie orchard"


def test_cap_applies_after_union_and_keeps_loss_evidence():
    result = retrieve([row("a")], [row("b"), row("c", registration="002")], limits=Limits(per_left=1))
    found = result["rows"][0]
    assert found["pre_cap_count"] == 2
    assert found["truncated"] is True
    assert len(found["candidates"]) == 1
    assert found["dropped_right_ids"] == ["c"]
    assert found["candidates"][0]["methods"] == ["identifier", "name", "tokens"]


def test_global_budgets_fail_before_silently_dropping_anchors():
    left, right = [row("a"), row("z")], [row("b"), row("c")]
    with pytest.raises(BudgetExceeded, match="posting"):
        retrieve(left, right, limits=Limits(posting_visits=1))
    with pytest.raises(BudgetExceeded, match="pair"):
        retrieve(left, right, limits=Limits(pairs=1))
    with pytest.raises(BudgetExceeded, match="row"):
        retrieve(left, right, limits=Limits(input_rows_per_source=1))
    with pytest.raises(ValueError):
        Limits(per_left=51)


def test_duplicate_source_ids_and_unapproved_feature_columns_are_rejected():
    with pytest.raises(ValueError, match="Duplicate right"):
        retrieve([row("a")], [row("b"), row("b")])
    with pytest.raises(ValueError, match="Duplicate left"):
        retrieve([row("a"), row("a")], [row("b")])
    unsafe = row("a")
    unsafe["features"]["truth_id"] = "hidden"
    with pytest.raises(ValueError, match="projection"):
        retrieve([unsafe], [row("b")])


def test_ids_only_break_exact_retrieval_ties_and_never_create_candidates():
    left = [row("same", name="Copper Mine", registration=None)]
    right = [row("same", name="Different Systems", registration=None, country="DE")]
    assert retrieve(left, right, "identifier_name_tokens")["retained_pairs"] == 0
    assert retrieve(left, right, "identifier")["retained_pairs"] == 0


def test_order_independence_and_no_missing_identifier_match():
    left = [row("a", registration=None), row("z", name="Beacon Logistics Limited")]
    right = [row("b", registration=None), row("c", name="Beacon Logistics Ltd")]
    first = retrieve(left, right)
    second = retrieve(left[::-1], right[::-1])
    assert sorted(first["rows"], key=lambda r:r["left_id"]) == sorted(second["rows"], key=lambda r:r["left_id"])
    assert "identifier" not in first["rows"][0]["candidates"][0]["methods"]


@pytest.mark.parametrize("change", [{"legal_name": " "}, {"country": None}, {"postal_code": 123}, {"legal_name": "x" * 2049}])
def test_malformed_feature_contract_fails(change):
    invalid = row("a")
    invalid["features"].update(change)
    with pytest.raises(ValueError):
        retrieve([invalid], [row("b")])
