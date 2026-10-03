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
    "runtime.mode": {"local": None, "serverless": None, "classic": "ZR-9"},
    "candidates.method": {"gram_topk": None, "learned_blocker": None, "minhash_lsh": None,
                          "field_blocks": None, "union": None},
    "features.string_similarity": {"levenshtein": None, "jaro_winkler": None, "both": None},
    "features.multi_token": {"idf_token_cosine": None, "gram_overlap": None, "monge_elkan_token": None,
                             "affine_gap_udf": None},
    "features.embeddings.provider": {"auto": None, "none": None, "local": None, "databricks_endpoint": None},
    "matcher.estimator": {"gbt": None, "logistic_regression": None, "random_forest": None},
    "decision.cardinality": {"one_to_one": None, "many_to_one": None, "unrestricted": None},
    "cluster.method": {"verified_merge": None, "connected_components": None, "center": None, "star": None},
    "quality.engine": {"native": None, "dqx": None, "expectations": None},
    "labels.llm": {"none": None, "jev": None, "ai_query": None},
    "labels.source": {"file": None, "truth_sample": None, "app": None},
    "review.llm": {"none": None, "jev": None},
}

FIELD_TYPES = ("person_name", "address", "organisation", "title", "code", "date", "number")

# Feature families (features/__init__.py documents which field types each applies to). `features.exclude` drops
# families — the ablation's lever. Jaro-Winkler/affine-gap UDFs require features.udf_features; extras are built-ins.
EXTRA_FAMILIES = ("osa", "weighted_jaccard", "padded_bigram_dice", "qgram_count_cosine", "token_sort_lev",
                  "soft_tfidf_lev", "lcs_indel")
FAMILIES = ("candidate", "edit", "exact", "phonetic", "monge_elkan", "token_idf", "gram", "structure", "rarity",
            "embedding", "jaro_winkler", "affine_gap", *EXTRA_FAMILIES)
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
    # candidates.method: the ZR-3s validation winner (bench/METHODS.md, synthetic_1e6 included): union of the gram
    # join and the default conjunction blocks, mean recall 0.896 vs gram_topk 0.724 — gram_topk alone recalls 0.142 at 10^6
    "candidates": {"method": "union", "q": 3, "k": 5, "idf_weighted": True, "gram_cap": 400,
                   # the shared ranking's vocabulary drops grams held by more than this share of the right records
                   # (relative to corpus size; gram_cap is the join budget only — ZR-3s)
                   "rank_vocab_share": 0.1,
                   # default field blocks: a two-field conjunction whose join would emit more than this many pairs per
                   # left record is not selective at this corpus size and is dropped (e.g. state & postcode at 10^6)
                   "block_pairs_per_left": 10,
                   "union_of": ["gram_topk", "field_blocks"], "field_blocks": [],
                   # minhash_lsh: Jaccard-distance threshold and hash tables; learned_blocker: target coverage of
                   # the labelled matches and the most predicates it may pick
                   "lsh_threshold": 0.8, "lsh_tables": 5, "learned_coverage": 0.99, "learned_max_predicates": 8},
    "features": {"string_similarity": "levenshtein",
                 "multi_token": ["idf_token_cosine", "gram_overlap", "monge_elkan_token"],
                 "udf_features": False,
                 "exclude": [],
                 "extra_families": [],   # SIM-2 candidates remain opt-in until a SIM-3 validation winner
                 "sota_max_chars": 256,  # OSA/LCS reject longer strings; never silently truncate
                 "token_cap": 30,         # Monge-Elkan compares at most this many tokens per side (long titles)
                 "embeddings": {"fields_of_type": ["organisation", "title"], "provider": "auto",
                                "model": "minishlab/potion-base-32M"}},   # D12 winner, bench/ABLATION.md
    "matcher": {"estimator": "gbt", "max_model_mb": 100, "params": {}, "seed": 0},
    "decision": {"threshold": "from_validation", "cardinality": "one_to_one", "validation_share": 0.25},
    # cluster.method: the ZR-4 validation winner (bench/CLUSTERS.md); representatives: members per cluster compared
    # pairwise by verified_merge before two clusters join (one pair below the threshold vetoes)
    "cluster": {"method": "verified_merge", "max_rounds": 20, "representatives": 3},
    "quality": {"engine": "native", "checks": []},
    "labels": {"source": "truth_sample", "n": 400, "path": None, "llm": "none", "llm_tau": 0.90,
               "llm_cache": None,    # default <storage.root>/jev_cache.jsonl
               "llm_max_usd": 1.0,   # refuse, before sending, when Jev's predicted cost exceeds this (USD)
               # labels.llm ai_query: the Databricks serving endpoint asked (Model Serving, paid llm_labeller)
               "llm_endpoint": "databricks-meta-llama-3-3-70b-instruct",
               # labels.source app (ZR-7): the arbitration app's label store (labels/store.py). app_base: the source
               # whose labels lie beneath the app's (none | truth_sample | file); on a pair both name, the app wins.
               # store: {path} (a Delta directory) or {table}; unset = <storage.catalog>.lm_review_labels on
               # Databricks, <storage.root>/review/labels on the laptop. With paid_features.lakebase_label_store the
               # table is the Lakebase table registered in Unity Catalog (a database catalog).
               "app_base": "none", "store": {"path": None, "table": None}},
    # review (ZR-7): every run writes the arbitration app's queue and one line of run history (review.py).
    # band: |p - threshold| that counts as uncertain; impact_min: a linked pair whose merge yields an entity of at
    # least this many records is a high-impact merge; llm: an LLM's opinion on the llm_pairs most uncertain pairs
    # (a paid feature, paid_features.llm_labeller; Jev allowed on the laptop like labels.llm)
    "review": {"enabled": True, "max_pairs": 2000, "band": 0.25, "impact_min": 3, "llm": "none", "llm_pairs": 100},
    "evaluation": {"truth": None},
    # mlflow (ZR-5, tracking.py): relative sqlite URIs and the pointer resolve against the config's directory.
    # model_name null = lakematch_<entity.name>; with a UC registry it is registered as <storage.catalog>.<name>.
    # pointer: the accepted run's id when there is no registry (D17). accept_min_f1: optional acceptance floor.
    # eval_max_pairs: mlflow.models.evaluate scores every candidate pair up to this many, else the validation labels.
    # dfs_tmp: MLFLOW_DFS_TMP, a UC volume path on Databricks.
    "mlflow": {"enabled": True, "tracking_uri": "sqlite:///mlflow.db", "experiment": "lakematch", "registry": False,
               "registry_uri": None, "alias": None, "model_name": None, "pointer": "models/current.json",
               "accept_min_f1": None, "eval_max_pairs": 500_000, "dfs_tmp": None},
    "paid_features": {**{k: False for k in PAID_FEATURES}, "genie_auth_mode": "user"},
}

# profile: databricks — only what differs (D17, D18, D19).
DATABRICKS_PROFILE: dict[str, Any] = {
    "runtime": {"mode": "serverless"},
    "storage": {"catalog": "workspace.lakematch"},
    "quality": {"engine": "dqx"},
    "mlflow": {"tracking_uri": "databricks", "registry": True, "registry_uri": "databricks-uc", "alias": "champion",
               "experiment": "/Shared/lakematch", "dfs_tmp": "/Volumes/workspace/lakematch/mlflow_tmp"},
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
        """Every choice `lakematch run` would execute that has not landed yet."""
        problems = []
        for key in ("runtime.mode", "candidates.method", "features.string_similarity", "matcher.estimator",
                    "decision.cardinality", "cluster.method", "quality.engine", "labels.llm", "labels.source",
                    "features.embeddings.provider", "review.llm"):
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
    extras = cfg.get("features.extra_families")
    if not isinstance(extras, list) or any(not isinstance(f, str) or f not in EXTRA_FAMILIES for f in extras):
        raise ConfigError(f"features.extra_families must be a list of new feature families ({', '.join(EXTRA_FAMILIES)})")
    if len(set(extras)) != len(extras):
        raise ConfigError("features.extra_families must not contain duplicates")
    for key in ("features.token_cap", "features.sota_max_chars"):
        if type(cfg.get(key)) is not int or cfg.get(key) < 1:
            raise ConfigError(f"{key} must be a positive integer")
    for fam in cfg.get("features.exclude"):
        if fam not in FAMILIES:
            raise ConfigError(f"features.exclude: '{fam}' is not a feature family ({', '.join(FAMILIES)})")
    # The UDF choices (affine_gap_udf always, jaro_winkler before Spark 4.3) are accepted here and gated in
    # features.check(), which knows the session's Spark version: they need features.udf_features: true to run.
    for t in cfg.get("features.embeddings.fields_of_type"):
        if t not in FIELD_TYPES:
            raise ConfigError(f"features.embeddings.fields_of_type: '{t}' is not a field type")
    for key in ("candidates.q", "candidates.k", "candidates.gram_cap", "cluster.max_rounds", "cluster.representatives",
                "labels.n"):
        if not isinstance(cfg.get(key), int) or cfg.get(key) < 1:
            raise ConfigError(f"{key} must be a positive integer")
    if not 0 < cfg.get("candidates.lsh_threshold") < 1:
        raise ConfigError("candidates.lsh_threshold is a Jaccard distance in (0, 1)")
    share = cfg.get("candidates.rank_vocab_share")
    if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1:
        raise ConfigError("candidates.rank_vocab_share must be in (0, 1]")
    bpl = cfg.get("candidates.block_pairs_per_left")
    if isinstance(bpl, bool) or not isinstance(bpl, (int, float)) or bpl <= 0:
        raise ConfigError("candidates.block_pairs_per_left must be a positive number")
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
        # Laurent, 2026-09-29: Jev may run on the laptop, provided its cost is predicted first (labels/jev.py) —
        # the one paid switch the laptop accepts, and only for Jev (labels.llm or review.llm; ai_query is Model Serving).
        on = [k for k in PAID_FEATURES if paid.get(k)
              and not (k == "llm_labeller" and "jev" in (data["labels"]["llm"], data["review"]["llm"]))]
        if on:
            raise ConfigError(f"profile laptop turns every paid feature off; enabled here: {', '.join(on)}")
        if data["runtime"]["mode"] != "local":
            raise ConfigError("profile laptop runs runtime.mode: local")
        if data["quality"]["engine"] == "dqx":
            raise ConfigError("quality.engine dqx runs on Databricks only (Databricks License, D18); the laptop "
                              "engine is native")
    if data["runtime"]["mode"] == "classic" and not data["classic"].get("profile"):
        raise ConfigError("runtime.mode classic needs classic.profile, set by hand — it is never guessed")
    ml = data["mlflow"]
    if not isinstance(ml["tracking_uri"], str) or not ml["tracking_uri"]:
        raise ConfigError("mlflow.tracking_uri must be a URI (sqlite:///mlflow.db on the laptop, databricks on Databricks)")
    if ml["registry"] and not (ml["registry_uri"] and ml["alias"]):
        raise ConfigError("mlflow.registry: true needs mlflow.registry_uri and mlflow.alias")
    if not ml["registry"] and not ml["pointer"]:
        raise ConfigError("mlflow.pointer: without a registry the accepted run id is resolved through this file (D17)")
    if ml["accept_min_f1"] is not None and not 0 <= ml["accept_min_f1"] <= 1:
        raise ConfigError("mlflow.accept_min_f1 must be null or in [0, 1]")
    if not isinstance(ml["eval_max_pairs"], int) or ml["eval_max_pairs"] < 1:
        raise ConfigError("mlflow.eval_max_pairs must be a positive integer")
    if data["inputs"]:
        for side in ("left", "right"):
            spec = data["inputs"].get(side)
            if not spec or "path" not in spec or "id" not in spec:
                raise ConfigError(f"inputs.{side} needs path and id")
    if data["features"]["embeddings"]["provider"] == "databricks_endpoint" and not paid.get("embedding_endpoint"):
        raise ConfigError("features.embeddings.provider databricks_endpoint is a paid feature (Model Serving): set "
                          "paid_features.embedding_endpoint: true")
    if data["labels"]["llm"] != "none" and not paid.get("llm_labeller"):
        raise ConfigError(f"labels.llm: {data['labels']['llm']} is a paid feature: set paid_features.llm_labeller: true "
                          "(Jev is allowed on the laptop; its cost is predicted before sending, capped by "
                          "labels.llm_max_usd)")
    mx = data["labels"]["llm_max_usd"]
    if not isinstance(mx, (int, float)) or isinstance(mx, bool) or mx < 0:
        raise ConfigError("labels.llm_max_usd must be a non-negative number of US dollars")
    if not 0.5 < data["labels"]["llm_tau"] <= 1:
        raise ConfigError("labels.llm_tau must be in (0.5, 1]")
    if data["labels"]["source"] == "file" and not data["labels"]["path"]:
        raise ConfigError("labels.source: file needs labels.path")
    if data["labels"]["source"] == "truth_sample" and data["inputs"] and not data["evaluation"]["truth"]:
        raise ConfigError("labels.source: truth_sample needs evaluation.truth")
    lab = data["labels"]
    if lab["app_base"] not in ("none", "truth_sample", "file"):
        raise ConfigError("labels.app_base must be none, truth_sample or file (the labels beneath the app's)")
    if lab["source"] == "app" and lab["app_base"] == "file" and not lab["path"]:
        raise ConfigError("labels.app_base: file needs labels.path")
    if lab["source"] == "app" and lab["app_base"] == "truth_sample" and data["inputs"] and not data["evaluation"]["truth"]:
        raise ConfigError("labels.app_base: truth_sample needs evaluation.truth")
    store = lab["store"]
    if not isinstance(store, dict) or set(store) - {"path", "table"} or (store.get("path") and store.get("table")):
        raise ConfigError("labels.store is {path: <Delta directory>} or {table: <table name>}, not both")
    if paid.get("lakebase_label_store") and not store.get("table"):
        raise ConfigError("paid_features.lakebase_label_store: labels.store.table must name the label table of the "
                          "Lakebase database catalog registered in Unity Catalog (<catalog>.<schema>.<table>)")
    rv = data["review"]
    if not isinstance(rv["enabled"], bool):
        raise ConfigError("review.enabled must be true or false")
    for key in ("max_pairs", "impact_min"):
        if type(rv[key]) is not int or rv[key] < 1:
            raise ConfigError(f"review.{key} must be a positive integer")
    if type(rv["llm_pairs"]) is not int or rv["llm_pairs"] < 0:
        raise ConfigError("review.llm_pairs must be a non-negative integer")
    if isinstance(rv["band"], bool) or not isinstance(rv["band"], (int, float)) or not 0 < rv["band"] <= 0.5:
        raise ConfigError("review.band must be in (0, 0.5]")
    if rv["llm"] != "none" and not paid.get("llm_labeller"):
        raise ConfigError(f"review.llm: {rv['llm']} is a paid feature: set paid_features.llm_labeller: true (Jev is "
                          "allowed on the laptop; its cost is predicted before sending, capped by labels.llm_max_usd)")


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
