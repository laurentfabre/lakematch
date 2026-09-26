"""The one YAML config that drives every runtime: defaults, profiles, validation, the paid-features guard.

A config is the laptop defaults, overlaid with the `databricks` profile when `profile: databricks`, overlaid with the
user's YAML. Every method choice of spec/BRIEF.md *Method choices* is a legal value from day one; a choice whose phase
has not landed is still *accepted* by `validate()` and fails with a clear message only when a stage that runs it is
built (`require()`), so a config written today keeps working as the phases land.
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("lakematch")


class ConfigError(ValueError):
    """The YAML is malformed, names an unknown key or method, or breaks a rule (paid features on the laptop)."""


class MethodNotReady(NotImplementedError):
    """A legal method choice whose implementation lands in a later phase."""


# --- method registry ----------------------------------------------------------------------------------------------
# config path -> {choice: None if implemented, else the phase that lands it}
METHODS: dict[str, dict[str, str | None]] = {
    "runtime.mode": {"local": None, "serverless": "ZR-6", "classic": "ZR-9"},
    "candidates.method": {"gram_topk": None, "learned_blocker": None, "minhash_lsh": None,
                          "field_blocks": None, "union": None},
    "features.string_similarity": {"levenshtein": None, "jaro_winkler": None, "both": None},
    "features.multi_token": {"idf_token_cosine": None, "gram_overlap": None, "monge_elkan_token": None,
                             "affine_gap_udf": None},
    "features.embeddings.provider": {"auto": None, "none": None, "local": None, "databricks_endpoint": "ZR-6"},
    "matcher.estimator": {"gbt": None, "logistic_regression": None, "random_forest": None},
    "decision.cardinality": {"one_to_one": None, "many_to_one": None, "unrestricted": None},
    "cluster.method": {"verified_merge": "ZR-4", "connected_components": "ZR-4", "center": "ZR-4", "star": "ZR-4"},
    "quality.engine": {"native": None, "dqx": "ZR-6", "expectations": "ZR-6"},
    "labels.llm": {"none": None, "jev": "ZR-3", "ai_query": "ZR-6"},
    "labels.source": {"file": None, "truth_sample": None, "app": "ZR-7"},
}

FIELD_TYPES = ("person_name", "address", "organisation", "title", "code", "date", "number")

# Feature families (features/__init__.py documents which field types each applies to). `features.exclude` drops
# families — the ablation's lever. The last two are UDF families: optional, only with `features.udf_features: true`.
FAMILIES = ("candidate", "edit", "exact", "phonetic", "monge_elkan", "token_idf", "gram", "structure", "rarity",
            "embedding", "jaro_winkler", "affine_gap")
UDF_CHOICES = {"jaro_winkler", "both", "affine_gap_udf"}   # UDFs before Spark 4.3 (affine gap: always)

# Everything that bills on top of plain compute. The laptop profile turns all of them off.
PAID_FEATURES = {
    "photon_on_classic": "classic compute, PHOTON runtime_engine DBU rate",
    "serverless_performance_mode": "serverless pipelines, performance-optimised",
    "llm_labeller": "Jev (external) or ai_query (Model Serving)",
    "ai_functions": "Databricks AI Functions",
    "embedding_endpoint": "Model Serving / Foundation Model embeddings",
    "ai_search_blocking": "AI Search endpoint",
    "lakebase_label_store": "Lakebase",
    "app": "Databricks Apps compute",
    "genie": "Genie",
    "predictive_optimization": "predictive optimisation",
    "data_quality_monitoring": "data quality monitoring",
    "llm_judges_in_evaluation": "LLM judges in MLflow evaluation",
}

DEFAULTS: dict[str, Any] = {
    "profile": "laptop",
    "runtime": {"mode": "local", "connect": False, "connect_url": None, "materialize": "auto", "driver_memory": "4g",
                "cores": 4, "shuffle_partitions": 16, "databricks_profile": None},
    "classic": {"profile": None, "cluster_id": None},
    "storage": {"catalog": None, "root": "./data"},
    "inputs": {},
    "entity": {"name": "record", "fields": {}},
    # Starting hypotheses (spec/BRIEF.md); ZR-3 / ZR-4 replace them with the validation winners.
    "candidates": {"method": "gram_topk", "q": 3, "k": 5, "idf_weighted": True, "gram_cap": 400,
                   "union_of": [], "field_blocks": [],
                   # minhash_lsh: Jaccard-distance threshold and hash tables; learned_blocker: target coverage of
                   # the labelled matches and the most predicates it may pick
                   "lsh_threshold": 0.8, "lsh_tables": 5, "learned_coverage": 0.99, "learned_max_predicates": 8},
    "features": {"string_similarity": "levenshtein",
                 "multi_token": ["idf_token_cosine", "gram_overlap", "monge_elkan_token"],
                 "udf_features": False,
                 "exclude": [],
                 "token_cap": 30,         # Monge-Elkan compares at most this many tokens per side (long titles)
                 "embeddings": {"fields_of_type": ["organisation", "title"], "provider": "auto",
                                "model": "minishlab/potion-base-32M"}},   # D12 winner, bench/ABLATION.md
    "matcher": {"estimator": "gbt", "max_model_mb": 100, "params": {}, "seed": 0},
    "decision": {"threshold": "from_validation", "cardinality": "one_to_one", "validation_share": 0.25},
    "cluster": {"method": "verified_merge", "max_rounds": 20},
    "quality": {"engine": "native", "checks": []},
    "labels": {"source": "truth_sample", "n": 400, "path": None, "llm": "none", "llm_tau": 0.90},
    "evaluation": {"truth": None},
    "mlflow": {"tracking_uri": "sqlite:///mlflow.db", "registry": False, "registry_uri": None, "alias": None,
               "model_name": "lakematch_record"},
    "paid_features": {**{k: False for k in PAID_FEATURES}, "genie_auth_mode": "user"},
}

# profile: databricks — only what differs (D17, D18, D19).
DATABRICKS_PROFILE: dict[str, Any] = {
    "runtime": {"mode": "serverless"},
    "storage": {"catalog": "workspace.lakematch"},
    "quality": {"engine": "dqx"},
    "mlflow": {"tracking_uri": "databricks", "registry": True, "registry_uri": "databricks-uc", "alias": "champion"},
    "paid_features": {"app": True, "genie": True},
}

# Sections whose keys are the user's own names, not config keys.
FREE_FORM = {"inputs", "entity.fields", "matcher.params", "evaluation.truth", "classic"}


def _merge(base: dict, over: dict, path: str = "") -> dict:
    out = copy.deepcopy(base)
    for key, val in (over or {}).items():
        here = f"{path}.{key}" if path else key
        if path not in FREE_FORM and here not in FREE_FORM and key not in base and path:
            raise ConfigError(f"unknown key '{here}'")
        if isinstance(val, dict) and isinstance(out.get(key), dict) and here not in FREE_FORM:
            out[key] = _merge(out[key], val, here)
        else:
            out[key] = copy.deepcopy(val)
    return out


class Config:
    """A validated config. `get("candidates.k")` reads a dotted path; `base_dir` resolves relative paths."""

    def __init__(self, data: dict, base_dir: Path | None = None):
        self.data = data
        self.base_dir = Path(base_dir or Path.cwd())

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path(self, value: str | None) -> Path | None:
        if value is None:
            return None
        p = Path(value).expanduser()
        return p if p.is_absolute() else (self.base_dir / p).resolve()

    @property
    def fields(self) -> dict[str, dict]:
        return self.data["entity"]["fields"]

    def fields_of_type(self, *types: str) -> list[str]:
        return [name for name, spec in self.fields.items() if spec["type"] in types]

    def enabled_paid_features(self) -> list[str]:
        return [k for k in PAID_FEATURES if self.data["paid_features"].get(k)]

    def require(self, key: str, value: str | None = None) -> str:
        """Fail clearly if the chosen method for `key` is not implemented yet. Returns the choice."""
        value = self.get(key) if value is None else value
        phase = METHODS[key].get(value)
        if phase is not None:
            raise MethodNotReady(f"{key}: '{value}' is a valid choice, but it is not implemented yet — it lands in "
                                 f"{phase} (spec/BRIEF.md). Implemented today: "
                                 f"{', '.join(c for c, p in METHODS[key].items() if p is None)}.")
        return value

    def runnable_problems(self) -> list[str]:
        """Every choice `lakematch run` would execute that has not landed yet (clustering is not in the ZR-1 run)."""
        problems = []
        for key in ("runtime.mode", "candidates.method", "features.string_similarity", "matcher.estimator",
                    "decision.cardinality", "quality.engine", "labels.llm", "labels.source",
                    "features.embeddings.provider"):
            try:
                self.require(key)
            except MethodNotReady as e:
                problems.append(str(e))
        for choice in self.get("features.multi_token"):
            try:
                self.require("features.multi_token", choice)
            except MethodNotReady as e:
                problems.append(str(e))
        return problems


def validate(data: dict) -> None:
    """Membership and shape checks. Accepts every method named in the brief, implemented or not."""
    if data["profile"] not in ("laptop", "databricks"):
        raise ConfigError(f"profile: '{data['profile']}' is not one of laptop, databricks")
    cfg = Config(data)
    for key, choices in METHODS.items():
        values = cfg.get(key)
        for v in values if isinstance(values, list) else [values]:
            if v not in choices:
                raise ConfigError(f"{key}: '{v}' is not a known choice ({', '.join(choices)})")
    for sub in cfg.get("candidates.union_of"):
        if sub not in METHODS["candidates.method"] or sub == "union":
            raise ConfigError(f"candidates.union_of: '{sub}' is not a candidate method")
    if cfg.get("candidates.method") == "union" and len(cfg.get("candidates.union_of")) < 2:
        raise ConfigError("candidates.method: union needs at least two methods in candidates.union_of")
    for name, spec in data["entity"]["fields"].items():
        if not isinstance(spec, dict) or spec.get("type") not in FIELD_TYPES:
            raise ConfigError(f"entity.fields.{name}: type must be one of {', '.join(FIELD_TYPES)}")
        if set(spec) - {"type", "multi"}:
            raise ConfigError(f"entity.fields.{name}: unknown option(s) {', '.join(sorted(set(spec) - {'type', 'multi'}))}")
        if spec.get("multi") and spec["type"] != "code":
            raise ConfigError(f"entity.fields.{name}: multi applies to code fields (a set of identifiers)")
    for fam in cfg.get("features.exclude"):
        if fam not in FAMILIES:
            raise ConfigError(f"features.exclude: '{fam}' is not a feature family ({', '.join(FAMILIES)})")
    # The UDF choices (affine_gap_udf always, jaro_winkler before Spark 4.3) are accepted here and gated in
    # features.check(), which knows the session's Spark version: they need features.udf_features: true to run.
    for t in cfg.get("features.embeddings.fields_of_type"):
        if t not in FIELD_TYPES:
            raise ConfigError(f"features.embeddings.fields_of_type: '{t}' is not a field type")
    for key in ("candidates.q", "candidates.k", "candidates.gram_cap", "cluster.max_rounds", "labels.n"):
        if not isinstance(cfg.get(key), int) or cfg.get(key) < 1:
            raise ConfigError(f"{key} must be a positive integer")
    if not 0 < cfg.get("candidates.lsh_threshold") < 1:
        raise ConfigError("candidates.lsh_threshold is a Jaccard distance in (0, 1)")
    if not 0 < cfg.get("candidates.learned_coverage") <= 1:
        raise ConfigError("candidates.learned_coverage must be in (0, 1]")
    for key in ("candidates.lsh_tables", "candidates.learned_max_predicates"):
        if not isinstance(cfg.get(key), int) or cfg.get(key) < 1:
            raise ConfigError(f"{key} must be a positive integer")
    for block in cfg.get("candidates.field_blocks"):
        if not isinstance(block, list) or not block or not all(isinstance(e, str) for e in block):
            raise ConfigError("candidates.field_blocks: each block is a non-empty list of Spark SQL expressions")
    thr = cfg.get("decision.threshold")
    if thr != "from_validation" and not (isinstance(thr, (int, float)) and 0 <= thr <= 1):
        raise ConfigError("decision.threshold must be 'from_validation' or a probability in [0, 1]")
    if not 0 < cfg.get("decision.validation_share") < 1:
        raise ConfigError("decision.validation_share must be in (0, 1)")
    if cfg.get("runtime.materialize") not in ("auto", "checkpoint", "cache", "table"):
        raise ConfigError("runtime.materialize must be auto, checkpoint, cache or table")
    if cfg.get("runtime.connect") and cfg.get("runtime.mode") != "local":
        raise ConfigError("runtime.connect applies to mode: local only (serverless is always Spark Connect)")
    if cfg.get("matcher.max_model_mb") > 100 and cfg.get("runtime.mode") == "serverless":
        raise ConfigError("matcher.max_model_mb: serverless caps a model at 100 MB")
    paid = data["paid_features"]
    unknown = set(paid) - set(PAID_FEATURES) - {"genie_auth_mode"}
    if unknown:
        raise ConfigError(f"paid_features: unknown switch(es) {', '.join(sorted(unknown))}")
    if paid["genie_auth_mode"] not in ("user", "service_principal"):
        raise ConfigError("paid_features.genie_auth_mode must be user or service_principal")
    if data["profile"] == "laptop":
        on = [k for k in PAID_FEATURES if paid.get(k)]
        if on:
            raise ConfigError(f"profile laptop turns every paid feature off; enabled here: {', '.join(on)}")
        if data["runtime"]["mode"] != "local":
            raise ConfigError("profile laptop runs runtime.mode: local")
    if data["runtime"]["mode"] == "classic" and not data["classic"].get("profile"):
        raise ConfigError("runtime.mode classic needs classic.profile, set by hand — it is never guessed")
    if data["inputs"]:
        for side in ("left", "right"):
            spec = data["inputs"].get(side)
            if not spec or "path" not in spec or "id" not in spec:
                raise ConfigError(f"inputs.{side} needs path and id")
    if data["labels"]["source"] == "file" and not data["labels"]["path"]:
        raise ConfigError("labels.source: file needs labels.path")
    if data["labels"]["source"] == "truth_sample" and data["inputs"] and not data["evaluation"]["truth"]:
        raise ConfigError("labels.source: truth_sample needs evaluation.truth")


def build(user: dict | None = None, base_dir: Path | None = None) -> Config:
    user = copy.deepcopy(user or {})
    unknown_top = set(user) - set(DEFAULTS)
    if unknown_top:
        raise ConfigError(f"unknown top-level key(s): {', '.join(sorted(unknown_top))}")
    data = copy.deepcopy(DEFAULTS)
    if user.get("profile") == "databricks":
        data = _merge(data, DATABRICKS_PROFILE)
    data = _merge(data, user)
    validate(data)
    return Config(data, base_dir)


def load(path: str | Path) -> Config:
    path = Path(path)
    try:
        user = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: not valid YAML ({e})") from e
    if not isinstance(user, dict):
        raise ConfigError(f"{path}: the top level must be a mapping")
    return build(user, path.parent.resolve())


def log_paid_features(cfg: Config) -> None:
    on = cfg.enabled_paid_features()
    log.info("paid features enabled: %s", ", ".join(on) if on else "none")
