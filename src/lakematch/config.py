"""YAML contract. Accept future method choices, fail explicitly at execution."""
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re

import yaml


class ConfigError(ValueError):
    pass


class MethodUnavailable(NotImplementedError):
    pass


CHOICES = {
    "candidates.method": {"gram_topk", "learned_blocker", "minhash_lsh", "field_blocks", "union"},
    "features.string_similarity": {"levenshtein", "jaro_winkler", "both"},
    "matcher.estimator": {"gbt", "logistic_regression", "random_forest"},
    "decision.cardinality": {"one_to_one", "many_to_one", "unrestricted"},
    "cluster.method": {"verified_merge", "connected_components", "center", "star"},
    "quality.engine": {"native", "dqx", "expectations"},
    "runtime.mode": {"local", "serverless", "classic"},
    "runtime.materialize": {"auto", "cache", "table"},
    "features.embeddings.provider": {"auto", "local", "databricks_endpoint", "none"},
    "labels.llm": {"none", "jev", "ai_query"},
}
FIELD_TYPES = {"person_name", "address", "organisation", "title", "code", "date", "number"}
TOKEN_FEATURES = {"idf_token_cosine", "gram_overlap", "monge_elkan_token", "affine_gap_udf"}
PAID = {
    "photon_on_classic": "CLASSIC_COMPUTE", "serverless_performance_mode": "LAKEFLOW",
    "llm_labeller": "provider usage", "ai_functions": "MODEL_SERVING",
    "embedding_endpoint": "MODEL_SERVING", "ai_search_blocking": "AI_SEARCH",
    "lakebase_label_store": "LAKEBASE", "app": "APPS", "genie": "GENIE",
    "predictive_optimization": "PREDICTIVE_OPTIMIZATION",
    "data_quality_monitoring": "DATA_QUALITY_MONITORING", "llm_judges_in_evaluation": "provider usage",
}
DEFAULTS = {
    "profile": "laptop",
    "runtime": {"mode": "local", "connect": False, "remote": "sc://localhost:15002",
                "materialize": "auto", "master": "local[2]", "cli_profile": None},
    "classic": {"profile": None},
    "storage": {"catalog": None, "root": "./data", "scratch_schema": None},
    "entity": {"name": "person", "id_column": "rec_id", "fields": {}},
    "candidates": {"method": "gram_topk", "q": 3, "k": 5, "idf_weighted": True,
                   "gram_cap": 400, "max_join_rows": 5_000_000, "max_pairs": 100_000,
                   "union_of": [], "field_blocks": [], "max_block_rules": 3,
                   "num_hash_features": 128_000, "num_hash_tables": 4, "seed": 0},
    "features": {"string_similarity": "levenshtein", "multi_token": [], "udf_features": False,
                 "field_families": True, "exclude_field_types": [], "max_tokens": 64, "max_chars": 512,
                 "levenshtein_threshold": 64,
                 "embeddings": {"fields_of_type": [], "provider": "auto", "model": "data/models/all-MiniLM-L6-v2"}},
    "matcher": {"estimator": "gbt", "max_model_mb": 100, "max_iter": 20, "max_depth": 3, "seed": 0},
    "decision": {"threshold": "from_validation", "cardinality": "one_to_one"},
    "cluster": {"method": "verified_merge", "max_rounds": 20},
    "quality": {"engine": "native", "checks": []},
    "labels": {"llm": "none", "llm_tau": 0.90},
    "mlflow": {"tracking_uri": "sqlite:///mlflow.db", "registry": False,
               "model_name": "lakematch_person", "registry_uri": None, "alias": None,
               "experiment": "lakematch", "acceptance_f1": None},
    "paid_features": {**dict.fromkeys(PAID, False), "genie_auth_mode": "user"},
    "input": {"left": None, "right": None, "labels": None, "validation_labels": None, "format": "csv"},
    "output": {"root": "./data/output"},
    "model": {"path": "./data/model", "pointer": "models/current.json"},
}
DB_OVERRIDES = {
    "runtime": {"mode": "serverless"}, "quality": {"engine": "dqx"},
    "mlflow": {"tracking_uri": "databricks", "registry": True,
               "registry_uri": "databricks-uc", "alias": "champion"},
    "paid_features": {"app": True, "genie": True},
}


def _merge(base, patch, prefix=""):
    for key, value in patch.items():
        path = f"{prefix}{key}"
        if key not in base:
            raise ConfigError(f"Unknown configuration key: {path}")
        if isinstance(base[key], dict) and path != "entity.fields":
            if not isinstance(value, dict):
                raise ConfigError(f"{path} must be a mapping")
            _merge(base[key], value, path + ".")
        else:
            base[key] = deepcopy(value)


@dataclass(frozen=True)
class Config:
    data: dict

    def __getitem__(self, key):
        return self.data[key]

    @property
    def fields(self):
        return list(self.data["entity"]["fields"])

    @property
    def enabled_paid(self):
        return {key: PAID[key] for key in PAID if self.data["paid_features"][key]}

    def canonical_json(self):
        return json.dumps(self.data, sort_keys=True, separators=(",", ":"))

    def require_implemented(self):
        supported = {"candidates.method": CHOICES["candidates.method"],
                     "quality.engine": {"native"}, "labels.llm": {"none"}}
        for key, values in supported.items():
            value = _get(self.data, key)
            if value not in values:
                raise MethodUnavailable(f"{key}={value} is a declared choice, not implemented")
        if self["features"]["embeddings"]["provider"] == "databricks_endpoint":
            raise MethodUnavailable("Remote embedding provider is not implemented")
        if self.enabled_paid:
            raise MethodUnavailable("Paid integrations are not implemented in ZR-1")


def _get(data, dotted):
    for key in dotted.split("."):
        data = data[key]
    return data


def from_dict(raw):
    if not isinstance(raw, dict):
        raise ConfigError("Config must be a YAML mapping")
    cfg = deepcopy(DEFAULTS)
    if raw.get("profile") == "databricks":
        _merge(cfg, DB_OVERRIDES)
    _merge(cfg, raw)
    if cfg["profile"] not in {"laptop", "databricks"}:
        raise ConfigError("profile must be laptop or databricks")
    for key, options in CHOICES.items():
        if _get(cfg, key) not in options:
            raise ConfigError(f"{key} must be one of {sorted(options)}")
    fields = cfg["entity"]["fields"]
    if not isinstance(fields, dict) or not fields:
        raise ConfigError("entity.fields must be a nonempty mapping")
    for name, spec in fields.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or name.startswith("lm_"):
            raise ConfigError(f"Invalid or reserved field name: {name}")
        if (not isinstance(spec, dict) or "type" not in spec or
                set(spec) - {"type", "date_format", "multiple"} or spec["type"] not in FIELD_TYPES):
            raise ConfigError(f"{name}: expected type in {sorted(FIELD_TYPES)}")
        if "multiple" in spec and type(spec["multiple"]) is not bool:
            raise ConfigError(f"{name}.multiple must be boolean")
        if "date_format" in spec and (spec["type"] != "date" or not isinstance(spec["date_format"], str) or not spec["date_format"]):
            raise ConfigError(f"{name}.date_format requires a nonempty Spark date pattern on a date field")
        if spec.get("multiple") and spec["type"] in {"date", "number"}:
            raise ConfigError("Multi-valued date/number fields require explicit upstream scalar extraction")
    ident = cfg["entity"]["id_column"]
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", ident) or ident in fields:
        raise ConfigError("entity.id_column must be a simple identifier separate from fields")
    for key in ("candidates.q", "candidates.k", "candidates.gram_cap", "candidates.max_join_rows",
                "candidates.max_pairs", "matcher.max_iter", "matcher.max_depth", "matcher.max_model_mb", "cluster.max_rounds",
                "features.max_tokens", "features.max_chars", "features.levenshtein_threshold"):
        value = _get(cfg, key)
        if type(value) is not int or value <= 0:
            raise ConfigError(f"{key} must be a positive integer")
    for key in ("max_block_rules", "num_hash_features", "num_hash_tables"):
        if type(cfg["candidates"][key]) is not int or cfg["candidates"][key] <= 0:
            raise ConfigError(f"candidates.{key} must be a positive integer")
    if type(cfg["candidates"]["seed"]) is not int:
        raise ConfigError("candidates.seed must be an integer")
    for key in ["runtime.connect", "features.udf_features", "features.field_families", "candidates.idf_weighted", "mlflow.registry"]:
        if type(_get(cfg, key)) is not bool:
            raise ConfigError(f"{key} must be boolean")
    for name in PAID:
        if type(cfg["paid_features"][name]) is not bool:
            raise ConfigError(f"paid_features.{name} must be boolean")
    if cfg["paid_features"]["genie_auth_mode"] not in {"user", "service_principal"}:
        raise ConfigError("paid_features.genie_auth_mode must be user or service_principal")
    threshold = cfg["decision"]["threshold"]
    if threshold != "from_validation" and (type(threshold) not in (int, float) or not 0 <= threshold <= 1):
        raise ConfigError("decision.threshold must be from_validation or a number in [0, 1]")
    acceptance = cfg["mlflow"]["acceptance_f1"]
    if acceptance is not None and (type(acceptance) not in (float, int) or not 0 <= acceptance <= 1):
        raise ConfigError("mlflow.acceptance_f1 must be null or a number in [0, 1]")
    if cfg["profile"] == "databricks" and cfg["matcher"]["max_model_mb"] > 100:
        raise ConfigError("Databricks composite models must remain under the 100 MB runtime limit")
    tokens = cfg["features"]["multi_token"]
    if not isinstance(tokens, list) or any(t not in TOKEN_FEATURES for t in tokens) or len(tokens) != len(set(tokens)):
        raise ConfigError(f"features.multi_token must be a unique list from {sorted(TOKEN_FEATURES)}")
    needs_udf = cfg["features"]["string_similarity"] != "levenshtein" or "affine_gap_udf" in tokens
    if needs_udf and not cfg["features"]["udf_features"]:
        raise ConfigError("Optional similarities require features.udf_features=true")
    excluded = cfg["features"]["exclude_field_types"]
    if (not isinstance(excluded, list) or any(t not in FIELD_TYPES for t in excluded) or len(excluded) != len(set(excluded))):
        raise ConfigError("features.exclude_field_types must contain unique field types")
    embedding = cfg["features"]["embeddings"]
    if (not isinstance(embedding["fields_of_type"], list) or
            any(t not in FIELD_TYPES for t in embedding["fields_of_type"]) or
            len(embedding["fields_of_type"]) != len(set(embedding["fields_of_type"]))):
        raise ConfigError("features.embeddings.fields_of_type must contain unique field types")
    if embedding["model"] is not None and (not isinstance(embedding["model"], str) or not embedding["model"]):
        raise ConfigError("features.embeddings.model must be a prepared local path or null")
    if cfg["paid_features"]["photon_on_classic"] and needs_udf:
        raise ConfigError("Optional UDF similarities cannot be selected for the Photon classic comparison")
    if cfg["profile"] == "laptop":
        if any(cfg["paid_features"][x] for x in PAID):
            raise ConfigError("Laptop profile requires every paid feature off")
        if cfg["runtime"]["mode"] != "local" or cfg["quality"]["engine"] != "native" or cfg["mlflow"]["registry"]:
            raise ConfigError("Laptop requires local runtime, native quality and no registry")
        if cfg["labels"]["llm"] != "none" or cfg["features"]["embeddings"]["provider"] == "databricks_endpoint":
            raise ConfigError("Laptop profile cannot use remote providers")
    for provider, flag in [(cfg["labels"]["llm"] != "none", "llm_labeller"),
                           (cfg["features"]["embeddings"]["provider"] == "databricks_endpoint", "embedding_endpoint"),
                           (cfg["labels"]["llm"] == "ai_query", "ai_functions")]:
        if provider and not cfg["paid_features"][flag]:
            raise ConfigError(f"Selected provider requires paid_features.{flag}=true")
    for block in cfg["candidates"]["field_blocks"]:
        if not isinstance(block, list) or not block:
            raise ConfigError("field_blocks must contain nonempty lists of configured fields")
        for key in block:
            if not isinstance(key, str):
                raise ConfigError("Blocking keys must be field names or soundex/prefix3/year expressions")
            if key in fields:
                continue
            match = re.fullmatch(r"(soundex|prefix3|year)\(([A-Za-z][A-Za-z0-9_]*)\)", key)
            if not match or match[2] not in fields or (match[1] == "year" and fields[match[2]]["type"] != "date"):
                raise ConfigError(f"Invalid blocking key: {key}")
    if any(m not in CHOICES["candidates.method"] - {"union"} for m in cfg["candidates"]["union_of"]):
        raise ConfigError("union_of must contain non-union candidate methods")
    if len(cfg["candidates"]["union_of"]) != len(set(cfg["candidates"]["union_of"])):
        raise ConfigError("union_of must contain unique methods")
    return Config(cfg)


def load(path):
    return from_dict(yaml.safe_load(Path(path).read_text()))
