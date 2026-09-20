from copy import deepcopy

import pytest

from lakematch.config import CHOICES, ConfigError, MethodUnavailable, from_dict, load


def base():
    return {"entity": {"fields": {"name": {"type": "person_name"}}}}


@pytest.mark.parametrize("path,values", [(k, v) for k, v in CHOICES.items() if k.startswith(("candidates.", "matcher.", "decision.", "cluster."))])
def test_all_declared_method_choices_are_accepted(path, values):
    section, key = path.split(".")
    for value in values:
        raw = base()
        raw[section] = {key: value}
        assert from_dict(raw)[section][key] == value


@pytest.mark.parametrize("patch", [
    {"paid_features": {"app": True}}, {"candidates": {"k": 0}},
    {"candidates": {"max_join_rows": -1}}, {"paid_features": {"app": "false"}},
    {"features": {"string_similarity": "both"}}, {"labels": {"llm": "jev"}},
    {"decision": {"threshold": 2}}, {"unknown": True},
    {"runtime": {"mode": "serverless"}},
])
def test_invalid_or_billable_laptop_configuration_fails(patch):
    with pytest.raises(ConfigError):
        from_dict({**base(), **patch})


def test_databricks_defaults_and_disabled_paid_features():
    c = from_dict({**base(), "profile": "databricks"})
    assert set(c.enabled_paid) == {"app", "genie"}
    assert c["quality"]["engine"] == "dqx"
    assert c["mlflow"]["registry"]
    assert from_dict({**base(), "profile": "databricks", "paid_features": {"app": False, "genie": False}}).enabled_paid == {}


def test_future_method_is_never_silently_replaced():
    cfg = from_dict({**base(), "profile": "databricks", "quality": {"engine": "dqx"}})
    with pytest.raises(MethodUnavailable, match="not implemented"):
        cfg.require_implemented()


def test_examples_load():
    assert load("examples/synthetic.yaml").enabled_paid == {}
