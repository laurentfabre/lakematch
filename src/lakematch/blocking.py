"""Budgeted alternative retrievers and job-only blocker fitting.

Keyed methods and union emit native Spark expressions. MinHash uses the public
MLlib API in a job task; it is not a Photon/declarative-flow implementation.
Learned blocking is an independent greedy weighted set-cover implementation:
cover training matches with a small disjunction of keys at low estimated cost.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from pyspark.sql import Window, functions as F


def key_spec(text, fields):
    if text in fields:
        return "exact", text
    match = re.fullmatch(r"(soundex|prefix3|year)\(([A-Za-z][A-Za-z0-9_]*)\)", text)
    if not match or match[2] not in fields:
        raise ValueError(f"Invalid blocking key: {text}")
    return match[1], match[2]


def proposed_rules(config):
    rules = []
    for name, spec in config["entity"]["fields"].items():
        rules.append([name])
        if spec["type"] == "person_name":
            rules.append([f"soundex({name})"])
        elif spec["type"] in {"organisation", "title", "address"}:
            rules.append([f"prefix3({name})"])
        elif spec["type"] == "date":
            rules.append([f"year({name})"])
    return rules


def key_value(text, config):
    kind, name = key_spec(text, config.fields)
    value = F.col(name)
    if kind == "soundex":
        value = F.soundex(value)
    elif kind == "prefix3":
        value = F.substring(value, 1, 3)
    elif kind == "year":
        spec = config["entity"]["fields"][name]
        if spec["type"] != "date":
            raise ValueError("year blocking keys require a typed date field")
        raw = F.col(f"lm_raw_{name}")
        timestamp = F.try_to_timestamp(raw, F.lit(spec.get("date_format", "yyyy-MM-dd")))
        value = F.year(timestamp).cast("string")
    return value


def keys(frame, rules, config, id_name):
    expressions = []
    for index, rule in enumerate(rules):
        values = [key_value(key, config) for key in rule]
        present = F.lit(True)
        for value in values:
            present = present & value.isNotNull() & (F.length(value) > 0)
        expressions.append(F.when(present, F.struct(F.lit(index).alias("rule"),
                                                    F.to_json(F.array(*values)).alias("key"))))
    entries = F.array(*expressions) if expressions else F.array().cast("array<struct<rule:int,key:string>>")
    return (frame.select(F.col("rec_id").alias(id_name), F.explode(entries).alias("entry"))
            .filter(F.col("entry").isNotNull()).select(id_name, "entry.rule", "entry.key"))


def key_statistics(a, b, cap):
    columns = ["rule", "key"]
    da = a.groupBy(*columns).count().withColumnRenamed("count", "da")
    db = b.groupBy(*columns).count().withColumnRenamed("count", "db")
    stats = da.join(db, columns, "full").fillna(0, ["da", "db"])
    retained = (F.col("da") <= cap) & (F.col("db") <= cap)
    diagnostics = stats.agg(
        F.coalesce(F.sum(F.col("da") * F.col("db")), F.lit(0)).alias("join_rows_before_cap"),
        F.coalesce(F.sum(F.when(retained, F.col("da") * F.col("db")).otherwise(0)), F.lit(0)).alias("join_rows_after_cap"),
        F.coalesce(F.sum(F.when(~retained, 1).otherwise(0)), F.lit(0)).alias("dropped_grams"))
    return stats, stats.filter(retained).select(*columns), diagnostics


def guarded(frame, diagnostics, maximum):
    guard = diagnostics.select(F.when(F.col("join_rows_after_cap") <= maximum, True)
        .otherwise(F.raise_error("Candidate pre-top-k join budget exceeded")).alias("lm_budget_ok"))
    return frame.crossJoin(guard).filter("lm_budget_ok").drop("lm_budget_ok")


def text_grams(frame, config, key, column):
    from .entity import grams
    return frame.select(F.col("rec_id").alias(key),
        grams(F.trim(F.concat_ws(" ", *config.fields)), config["candidates"]["q"]).alias(column))


def rerank(pairs, left, right, config):
    """Exact unweighted gram-set cosine after alternative retrieval, bounded by k."""
    a, b = text_grams(left, config, "a_id", "lm_a"), text_grams(right, config, "b_id", "lm_b")
    frame = pairs.select("a_id", "b_id").distinct().join(a, "a_id").join(b, "b_id")
    denominator = F.sqrt(F.size("lm_a").cast("double") * F.size("lm_b"))
    frame = frame.withColumn("cos", F.when(denominator > 0,
        F.size(F.array_intersect("lm_a", "lm_b")) / denominator).otherwise(0.))
    order = Window.partitionBy("a_id").orderBy(F.desc("cos"), "b_id")
    return (frame.withColumn("rank", F.row_number().over(order))
        .filter(F.col("rank") <= config["candidates"]["k"])
        .withColumn("gap", F.max("cos").over(Window.partitionBy("a_id")) - F.col("cos"))
        .select("a_id", "b_id", "cos", "rank", "gap"))


def child_config(config, method):
    from .config import from_dict
    raw = deepcopy(config.data)
    raw["candidates"]["method"] = method
    return from_dict(raw)


def needs_state(config):
    method = config["candidates"]["method"]
    return method in {"learned_blocker", "minhash_lsh"} or (method == "union" and bool(
        {"learned_blocker", "minhash_lsh"} & set(config["candidates"]["union_of"])))


def hashed_records(frame, config):
    from pyspark.ml.feature import HashingTF
    from .entity import grams
    tokens = frame.withColumn("lm_grams", grams(F.trim(F.concat_ws(" ", *config.fields)), config["candidates"]["q"]))
    # MinHash rejects zero vectors; missing records simply generate no candidates.
    return HashingTF(inputCol="lm_grams", outputCol="lm_hash_vector", binary=True,
                     numFeatures=config["candidates"]["num_hash_features"]).transform(tokens.filter(F.size("lm_grams") > 0))


def prepare_state(left, right, labels, config):
    """Job action. Caller must pass only training records/labels to supervised fit."""
    method = config["candidates"]["method"]
    if method == "union":
        return {"method": method, "children": {name: prepare_state(left, right, labels, child_config(config, name))
                for name in config["candidates"]["union_of"]}}
    if method == "minhash_lsh":
        from pyspark.ml.feature import MinHashLSH
        model = MinHashLSH(inputCol="lm_hash_vector", outputCol="lm_hashes",
            numHashTables=config["candidates"]["num_hash_tables"], seed=config["candidates"]["seed"]).fit(hashed_records(left, config))
        return {"method": method, "model": model}
    if method != "learned_blocker":
        return {"method": method}
    if labels is None:
        raise ValueError("Learned blocking requires explicit training labels")
    from .tracking import label_digest
    rows = labels.limit(config["candidates"]["max_pairs"] + 1).collect()
    if len(rows) > config["candidates"]["max_pairs"]:
        raise ValueError("Learned-blocker training labels exceed the configured budget")
    digest, canonical = label_digest(rows)
    positives = labels.filter(F.col("label") == 1.).select("a_id", "b_id").distinct()
    true_pairs = {(a, b) for a, b, y in json.loads(canonical) if y == 1.}
    if not true_pairs:
        raise ValueError("Learned blocking needs positive training pairs")
    rules = config["candidates"]["field_blocks"] or proposed_rules(config)
    a, b = keys(left, rules, config, "a_id"), keys(right, rules, config, "b_id")
    stats, retained, _ = key_statistics(a, b, config["candidates"]["gram_cap"])
    costs = {r.rule: r.cost for r in stats.join(retained, ["rule", "key"]).groupBy("rule").agg(
        F.sum(F.col("da") * F.col("db")).alias("cost")).collect()}
    b = b.select("b_id", F.col("rule").alias("b_rule"), F.col("key").alias("b_key"))
    matching = (a.join(retained, ["rule", "key"]).join(positives, "a_id").join(b, "b_id")
                .filter((F.col("rule") == F.col("b_rule")) & (F.col("key") == F.col("b_key"))))
    coverage = {r.rule: {(p.a_id, p.b_id) for p in r.pairs} for r in matching.groupBy("rule").agg(
        F.collect_set(F.struct("a_id", "b_id")).alias("pairs")).collect()}
    remaining, chosen, trace = set(true_pairs), [], []
    for _ in range(config["candidates"]["max_block_rules"]):
        eligible = [i for i in coverage if i not in chosen and coverage[i] & remaining]
        if not eligible:
            break
        selected = min(eligible, key=lambda i: (-len(coverage[i] & remaining) / max(1, costs.get(i, 0)), i))
        covered = coverage[selected] & remaining
        chosen.append(selected)
        remaining -= covered
        trace.append({"rule": rules[selected], "new_positives": len(covered), "estimated_join_rows": costs.get(selected, 0)})
    return {"method": method, "rules": [rules[i] for i in chosen], "label_set_sha256": digest,
            "training_positives": len(true_pairs), "training_uncovered": len(remaining), "selection": trace}


def save_state(state, path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    metadata = {k: v for k, v in state.items() if k not in {"model", "children"}}
    if "model" in state:
        state["model"].write().overwrite().save(str((path / "lsh").resolve()))
    if "children" in state:
        metadata["children"] = sorted(state["children"])
        for name, child in state["children"].items():
            save_state(child, path / name)
    (path / "state.json").write_text(json.dumps(metadata, indent=2) + "\n")


def load_state(path):
    path = Path(path)
    state = json.loads((path / "state.json").read_text())
    if state["method"] == "minhash_lsh":
        from pyspark.ml.feature import MinHashLSHModel
        state["model"] = MinHashLSHModel.load(str((path / "lsh").resolve()))
    if state["method"] == "union":
        state["children"] = {name: load_state(path / name) for name in state["children"]}
    return state


def build_alternative(left, right, config, *, state=None):
    from .candidates import CandidatePlan, build
    spec = config["candidates"]
    method = spec["method"]
    if method in {"learned_blocker", "minhash_lsh"} and (not state or state.get("method") != method):
        raise ValueError(f"{method} requires state prepared in a job task")
    if method == "union":
        if not spec["union_of"]:
            raise ValueError("Candidate union requires at least one child method")
        children = state.get("children", {}) if state else {}
        plans = [build(left, right, child_config(config, name), state=children.get(name)) for name in spec["union_of"]]
        diagnostic = plans[0].diagnostics
        for plan in plans[1:]:
            diagnostic = diagnostic.unionByName(plan.diagnostics)
        diagnostic = diagnostic.agg(*[F.sum(name).alias(name) for name in
            ("join_rows_before_cap", "join_rows_after_cap", "dropped_grams")])
        # Put the aggregate budget guard in each child's left input, before its
        # pair join. A post-union filter alone would run the expensive joins first.
        guarded_left = guarded(left, diagnostic, spec["max_join_rows"])
        plans = [build(guarded_left, right, child_config(config, name), state=children.get(name)) for name in spec["union_of"]]
        pairs = plans[0].pairs.select("a_id", "b_id")
        for plan in plans[1:]:
            pairs = pairs.unionByName(plan.pairs.select("a_id", "b_id"))
    else:
        if method == "minhash_lsh":
            from pyspark.ml.functions import vector_to_array
            def minhash_keys(frame, ident):
                hashed = state["model"].transform(hashed_records(frame, config))
                return hashed.select(F.col("rec_id").alias(ident), F.posexplode("lm_hashes").alias("rule", "bucket")).select(
                    ident, "rule", vector_to_array("bucket")[0].cast("long").cast("string").alias("key"))
            a, b = minhash_keys(left, "a_id"), minhash_keys(right, "b_id")
        else:
            rules = state["rules"] if method == "learned_blocker" else spec["field_blocks"]
            if method == "field_blocks" and not rules:
                raise ValueError("field_blocks requires explicit key rules")
            a, b = keys(left, rules, config, "a_id"), keys(right, rules, config, "b_id")
        _, retained, diagnostic = key_statistics(a, b, spec["gram_cap"])
        pairs = guarded(a.join(retained, ["rule", "key"]), diagnostic, spec["max_join_rows"]).join(b, ["rule", "key"])
    result = rerank(pairs, left, right, config)
    return CandidatePlan(result, diagnostic, spec["max_join_rows"], spec["max_pairs"],
        {"method": method, "score": "exact unweighted gram-set cosine after retrieval",
         "dropped_grams_semantics": "discarded blocking keys/hash buckets; summed across union children"})
