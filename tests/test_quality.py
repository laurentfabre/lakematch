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


SEEDED = [("1", "ada", "75001", "1950"), ("2", None, "75002", "1951"), ("2", "bob", "x", "1952"),
          ("4", "c" * 70, "75004", None), ("5", "   ", "75005", "1953"), (None, "eve", "75006", "1954"),
          (None, "fay", None, "1955"), ("8", "gus", "99999", "19x6"), ("9", "hal", "75009", "1957")]
SPECS = [{"check": "is_not_null", "column": "id"}, {"check": "is_unique", "columns": ["id"]},
         {"check": "is_not_empty", "column": "name"},
         {"check": "matches_regex", "column": "postcode", "pattern": r"^\d{5}$"},
         {"check": "is_in", "column": "postcode", "values": ["75001", "75002", "75004", "75005", "75006", "75009", "x"],
          "criticality": "warn"},
         {"check": "max_length", "column": "name", "n": 60},
         {"check": "sql", "name": "year_digits", "fails_when": "year IS NOT NULL AND NOT year RLIKE '^[0-9]{4}$'"},
         {"check": "min_rows", "n": 3}]


def _split_ids(valid, bad):
    key = lambda r: (r.id, r.name, r.postcode, r.year)
    return (sorted(map(key, valid.collect()), key=str), sorted(map(key, bad.collect()), key=str),
            sorted(len(r._warnings) for r in valid.collect()))


def test_dqx_and_native_give_the_same_split(spark):
    # ZR-6: DQX is the Databricks default; native is the reference. DQX's documented local testing mode
    # (a mocked WorkspaceClient, apply_checks only) runs the same checks on the same seeded rows.
    pytest.importorskip("databricks.labs.dqx")
    from unittest.mock import MagicMock
    from databricks.sdk import WorkspaceClient
    from lakematch.quality import dqx_adapter
    df = spark.createDataFrame(SEEDED, "id string, name string, postcode string, year string")
    nat = _split_ids(*native.apply_and_split(df, native.from_config(SPECS)))
    dqx = _split_ids(*dqx_adapter.split(df, SPECS, MagicMock(spec=WorkspaceClient)))
    assert dqx == nat
    assert len(nat[1]) == 6                         # null id x2, duplicate id x2, blank name, bad postcode / year


def test_expectation_constraints_give_the_native_split(spark):
    # ZR-6: quality.engine expectations (Lakeflow only) — the drop constraints plus the dataset flags must keep exactly
    # the rows native keeps; the warn constraints must fail on exactly the rows native warns about
    from lakematch.quality import expectations
    df = spark.createDataFrame(SEEDED, "id string, name string, postcode string, year string")
    drop, warn, dataset = expectations.constraints(SPECS)
    flagged = expectations.with_dataset_flags(df, dataset)
    keep = " AND ".join(f"({c})" for c in drop.values())
    kept = flagged.filter(keep)
    valid, _ = native.apply_and_split(df, native.from_config(SPECS))
    key = lambda d: sorted(str((r.id, r.name, r.postcode, r.year)) for r in d.collect())
    assert key(kept) == key(valid)
    warned = kept.filter(" OR ".join(f"NOT ({c})" for c in warn.values()))
    assert key(warned) == key(valid.filter("size(_warnings) > 0"))
