"""Config: every method of the brief is accepted; unimplemented ones fail clearly; rules are enforced. No Spark."""
from pathlib import Path

import pytest

from lakematch import config
from lakematch.config import METHODS, PAID_FEATURES, ConfigError, MethodNotReady

ROOT = Path(__file__).resolve().parent.parent

# Choices whose legal use needs another key set alongside them.
NEEDS = {
    ("runtime.mode", "serverless"): {"profile": "databricks"},
    ("runtime.mode", "classic"): {"profile": "databricks", "classic": {"profile": "paid-workspace"}},
    ("candidates.method", "union"): {"candidates": {"union_of": ["gram_topk", "field_blocks"]}},
    ("labels.source", "file"): {"labels": {"path": "labels.csv"}},
}


def _user(key, value):
    section, *rest = key.split(".")
    node = value if key != "features.multi_token" else [value]
    for part in reversed(rest):
        node = {part: node}
    user = {section: node}
    for k, v in NEEDS.get((key, value), {}).items():
        if isinstance(v, dict) and isinstance(user.get(k), dict):
            user[k] = {**v, **user[k]}
        else:
            user.setdefault(k, v)
    return user


@pytest.mark.parametrize("key,value", [(k, v) for k, choices in METHODS.items() for v in choices])
def test_every_method_is_accepted(key, value):
    cfg = config.build(_user(key, value))
    phase = METHODS[key][value]
    if phase is None:
        assert cfg.require(key, value) == value
    else:
        with pytest.raises(MethodNotReady, match=phase):
            cfg.require(key, value)


def test_unknown_method_is_rejected_with_the_choices():
    with pytest.raises(ConfigError, match="gram_topk"):
        config.build({"candidates": {"method": "sorted_neighbourhood"}})


def test_unknown_keys_are_rejected():
    with pytest.raises(ConfigError, match="candidates.kk"):
        config.build({"candidates": {"kk": 3}})
    with pytest.raises(ConfigError, match="top-level"):
        config.build({"candidate": {}})


def test_laptop_profile_refuses_paid_features():
    for name in PAID_FEATURES:
        with pytest.raises(ConfigError, match=name):
            config.build({"paid_features": {name: True}})


def test_databricks_profile_turns_on_app_and_genie_only():
    cfg = config.build({"profile": "databricks"})
    assert cfg.enabled_paid_features() == ["app", "genie"]
    assert cfg.get("quality.engine") == "dqx" and cfg.get("mlflow.registry") is True
    off = config.build({"profile": "databricks", "paid_features": {"app": False, "genie": False}})
    assert off.enabled_paid_features() == []


def test_classic_needs_a_hand_set_profile():
    with pytest.raises(ConfigError, match="never guessed"):
        config.build({"profile": "databricks", "runtime": {"mode": "classic"}})


def test_field_types_and_numbers_are_checked():
    with pytest.raises(ConfigError, match="type must be"):
        config.build({"entity": {"fields": {"name": {"type": "free_text"}}}})
    with pytest.raises(ConfigError, match="candidates.k"):
        config.build({"candidates": {"k": 0}})
    with pytest.raises(ConfigError, match="threshold"):
        config.build({"decision": {"threshold": 1.5}})


def test_defaults_are_runnable_and_clustering_waits_for_zr4():
    cfg = config.build({})
    assert cfg.runnable_problems() == []
    with pytest.raises(MethodNotReady, match="ZR-4"):
        cfg.require("cluster.method")


def test_unimplemented_choice_blocks_the_run_with_its_phase():
    cfg = config.build({"features": {"string_similarity": "jaro_winkler"}})
    problems = cfg.runnable_problems()
    assert len(problems) == 1 and "ZR-2" in problems[0]


def test_example_config_loads():
    cfg = config.load(ROOT / "examples" / "febrl4.yaml")
    assert cfg.get("profile") == "laptop" and len(cfg.fields) == 10
    assert cfg.path(cfg.get("inputs.left.path")) == ROOT / "data" / "febrl4" / "left.csv"
    assert cfg.runnable_problems() == []


def test_mandatory_dependencies_are_exactly_three():
    import tomllib
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    assert sorted(d.split(">")[0].split("=")[0].split("<")[0].split("[")[0] for d in deps) == ["mlflow", "pyspark", "pyyaml"]
