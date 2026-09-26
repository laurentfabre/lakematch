import pytest

from lakematch.quality import native


@pytest.fixture
def people(spark):
    return spark.createDataFrame(
        [("1", "ada", "75001"), ("2", None, "75002"), ("2", "bob", "x"), ("4", "c" * 70, "75004")],
        "id string, name string, postcode string")


def test_split_quarantines_errors_and_keeps_warnings(people):
    checks = [native.is_not_null("name"), native.is_unique("id"),
              native.matches_regex("postcode", r"^\d{5}$", criticality="warn"),
              native.max_length("name", 60, criticality="warn")]
    valid, bad = native.apply_and_split(people, checks)
    assert sorted(r.id for r in valid.collect()) == ["1", "4"]
    reasons = {(r.id, r.name): r._errors for r in bad.collect()}
    assert reasons[("2", None)] == ["name is null", "id is not unique"]
    assert reasons[("2", "bob")] == ["id is not unique"]
    warned = {r.id: r._warnings for r in valid.collect()}
    assert warned == {"1": [], "4": ["name is longer than 60"]}
    assert "_errors" not in valid.columns and "_warnings" in bad.columns


def test_dataset_level_min_rows(people):
    valid, bad = native.apply_and_split(people, [native.min_rows(10)])
    assert valid.count() == 0 and bad.count() == 4


def test_checks_from_config(people):
    checks = native.from_config([{"check": "is_in", "column": "postcode", "values": ["75001", "75002"]},
                                 {"check": "sql", "name": "short", "fails_when": "length(name) < 3",
                                  "criticality": "warn"}])
    valid, bad = native.apply_and_split(people, checks)
    assert sorted(r.id for r in bad.collect()) == ["2", "4"]
    with pytest.raises(ValueError, match="unknown check"):
        native.from_config([{"check": "is_prime", "column": "id"}])
    with pytest.raises(ValueError, match="criticality"):
        native.is_not_null("id", criticality="fatal")
