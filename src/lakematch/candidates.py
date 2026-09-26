"""Candidate pairs: a cheap first step that proposes, for each left record, a short list of right records worth scoring.

Every method *proposes* pairs; one shared step then ranks the proposals by the same IDF gram cosine and keeps the k
best per left record. So every method spends the same pair budget (at most k pairs per left record) and methods differ
only in which pairs they can reach — the comparison D06 asks for (candidate recall at equal pair budget).

The ranking score — IDF-weighted cosine over character q-gram sets:

    vocabulary  every q-gram of either side, minus the "ubiquitous" ones present in more than `gram_cap` right records
    weight      w(g) = ln((1 + N) / (1 + df(g))) + 1 with N = |left| + |right| and df(g) = records holding g on
                either side (smoothed IDF, always > 0); `idf_weighted: false` sets w(g) = 1 (plain set cosine)
    score       cos(l, r) = sum_{g in l ∩ r} w(g)^2 / (||l|| · ||r||), both norms over the *same* vocabulary; a
                proposed pair that shares no kept gram scores 0
    keep        the k best right records per left record, ties broken by right id (deterministic)

Methods (`candidates.method`):

    gram_topk        every pair sharing a kept gram. Budget: a kept gram is held by at most `gram_cap` right records,
                     so the join emits at most sum_l G_l × gram_cap rows (G_l = grams of left record l).
    field_blocks     equi-joins on hand-written keys: `field_blocks` is a list of blocks, each a list of Spark SQL
                     expressions over the entity columns, all non-empty and equal (e.g. [["postcode"],
                     ["soundex(surname)", "substring(date_of_birth, 1, 4)"]]). An empty list means one block per field
                     on its normalised value (soundex for person names). A key held by more than `gram_cap` right
                     records is skipped.
    learned_blocker  set-cover blocking learnt from labelled matches (Bilenko et al. 2006; Michelson & Knoblock 2006):
                     a pool of cheap predicates (exact value, soundex, 3-character prefix, shared token, year, and the
                     conjunctions of the ten best), then greedily the predicate with the most newly covered matches per
                     generated pair, until `learned_coverage` of the labelled matches is covered or
                     `learned_max_predicates` are chosen. Learning is an action (a job task); needs labels.
    minhash_lsh      Spark MLlib MinHashLSH over the gram sets (HashingTF, binary), `lsh_tables` hash tables, pairs
                     within Jaccard distance `lsh_threshold`. MLlib: no Photon, not inside a pipeline flow.
    union            the union of the `union_of` methods' proposals.

Output: l_id, r_id, cand_score, cand_rank (1 = best), cand_gap (best score of this left record − this one).
"""
from __future__ import annotations

import logging

from pyspark.sql import Column, DataFrame, Window, functions as F

from .config import Config

log = logging.getLogger("lakematch")


# --- the shared ranking --------------------------------------------------------------------------------------------
def _gram_weights(left: DataFrame, right: DataFrame, cfg: Config):
    cap, weighted = cfg.get("candidates.gram_cap"), cfg.get("candidates.idf_weighted")
    el = left.select(F.col("id").alias("l_id"), F.explode("_grams").alias("gram"))
    er = right.select(F.col("id").alias("r_id"), F.explode("_grams").alias("gram"))
    df_l = el.groupBy("gram").agg(F.count(F.lit(1)).alias("df_l"))
    df_r = er.groupBy("gram").agg(F.count(F.lit(1)).alias("df_r"))
    sizes = left.agg(F.count(F.lit(1)).alias("n_l")).crossJoin(right.agg(F.count(F.lit(1)).alias("n_r")))
    vocab = (df_l.join(df_r, "gram", "full").fillna(0, ["df_l", "df_r"])
                 .filter(F.col("df_r") <= cap).crossJoin(sizes))
    w = (F.log((1 + F.col("n_l") + F.col("n_r")) / (1 + F.col("df_l") + F.col("df_r"))) + 1) if weighted else F.lit(1.0)
    vocab = vocab.select("gram", w.alias("w"))
    wl, wr = el.join(vocab, "gram"), er.join(vocab, "gram")
    norm_l = wl.groupBy("l_id").agg(F.sqrt(F.sum(F.col("w") * F.col("w"))).alias("norm_l"))
    norm_r = wr.groupBy("r_id").agg(F.sqrt(F.sum(F.col("w") * F.col("w"))).alias("norm_r"))
    return wl, wr, norm_l, norm_r


def _cosine(dot: DataFrame, norm_l: DataFrame, norm_r: DataFrame) -> DataFrame:
    return (dot.join(norm_l, "l_id").join(norm_r, "r_id")
               .select("l_id", "r_id", (F.col("dot") / (F.col("norm_l") * F.col("norm_r"))).alias("cand_score")))


def top_k(scored: DataFrame, k: int) -> DataFrame:
    by_left = Window.partitionBy("l_id").orderBy(F.desc("cand_score"), F.asc("r_id"))
    return (scored.withColumn("cand_rank", F.row_number().over(by_left)).filter(F.col("cand_rank") <= k)
                  .withColumn("cand_gap", F.max("cand_score").over(Window.partitionBy("l_id")) - F.col("cand_score")))


def rescore(proposals: DataFrame, left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    """IDF gram cosine for arbitrary proposed pairs (0 when they share no kept gram)."""
    wl, wr, norm_l, norm_r = _gram_weights(left, right, cfg)
    props = proposals.select("l_id", "r_id").distinct()
    dot = (props.join(wl, "l_id").join(wr.select("r_id", "gram", F.col("w").alias("w_r")), ["r_id", "gram"])
                .groupBy("l_id", "r_id").agg(F.sum(F.col("w") * F.col("w_r")).alias("dot")))
    scored = _cosine(dot, norm_l, norm_r)
    return props.join(scored, ["l_id", "r_id"], "left").fillna(0.0, ["cand_score"])


# --- proposers -----------------------------------------------------------------------------------------------------
def _gram_all(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    """Every pair sharing a kept gram, already scored."""
    wl, wr, norm_l, norm_r = _gram_weights(left, right, cfg)
    dot = (wl.join(wr.select("r_id", "gram"), "gram")
             .groupBy("l_id", "r_id").agg(F.sum(F.col("w") * F.col("w")).alias("dot")))
    return _cosine(dot, norm_l, norm_r)


def _key(exprs: list[str], is_array: bool) -> Column:
    """A blocking key: an array of values (share any) or one string (all parts non-empty, else null)."""
    if is_array:
        return F.array_distinct(F.expr(exprs[0]))
    parts = [F.expr(e).cast("string") for e in exprs]
    ok = F.lit(True)
    for part in parts:
        ok = ok & part.isNotNull() & (F.length(part) > 0)
    return F.when(ok, F.concat_ws("\u0001", *parts))


def _block_join(left: DataFrame, right: DataFrame, exprs: list[str], cap: int, is_array: bool = False) -> DataFrame:
    """Pairs whose keys are equal (or, for array keys, share an element); a key value held by more than `cap` right
    records is skipped — the same budget rule as the gram cap."""
    def keyed(side: DataFrame, alias: str) -> DataFrame:
        k = _key(exprs, is_array)
        out = side.select(F.col("id").alias(alias), (F.explode(k) if is_array else k).alias("k"))
        return out.filter(F.col("k").isNotNull() & (F.length("k") > 0)).distinct()
    kl, kr = keyed(left, "l_id"), keyed(right, "r_id")
    small = kr.groupBy("k").agg(F.count(F.lit(1)).alias("n")).filter(F.col("n") <= cap).select("k")
    return kl.join(small, "k").join(kr, "k").select("l_id", "r_id").distinct()


def default_blocks(cfg: Config) -> list[list[str]]:
    return [[f"soundex({f})"] if s["type"] == "person_name" else [f] for f, s in cfg.fields.items()]


def _field_blocks(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    blocks = cfg.get("candidates.field_blocks") or default_blocks(cfg)
    cap = cfg.get("candidates.gram_cap")
    parts = [_block_join(left, right, list(block), cap) for block in blocks]
    out = parts[0]
    for p in parts[1:]:
        out = out.unionByName(p)
    return out.distinct()


def _minhash(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    from pyspark.ml.feature import HashingTF, MinHashLSH
    tf = HashingTF(inputCol="_grams", outputCol="_gv", numFeatures=1 << 20, binary=True)
    nonempty = F.size("_grams") > 0
    lv = tf.transform(left.select("id", "_grams").filter(nonempty))
    rv = tf.transform(right.select("id", "_grams").filter(nonempty))
    model = MinHashLSH(inputCol="_gv", outputCol="_mh", numHashTables=cfg.get("candidates.lsh_tables"),
                       seed=cfg.get("matcher.seed")).fit(lv.unionByName(rv))
    joined = model.approxSimilarityJoin(lv, rv, cfg.get("candidates.lsh_threshold"))   # distance column: distCol
    return joined.select(F.col("datasetA.id").alias("l_id"), F.col("datasetB.id").alias("r_id")).distinct()


# --- learned blocker (set cover) ------------------------------------------------------------------------------------
def predicate_pool(cfg: Config) -> dict[str, tuple[list[str], bool]]:
    """name -> (key SQL expressions, is_array_key). Single predicates over the entity columns."""
    pool = {}
    for f, s in cfg.fields.items():
        t = s["type"]
        if s.get("multi"):
            pool[f"any_item({f})"] = ([f"set_{f}"], True)
            continue
        pool[f"exact({f})"] = ([f], False)
        pool[f"prefix3({f})"] = ([f"substring({f}, 1, 3)"], False)
        if t in ("person_name", "address", "organisation", "title"):
            pool[f"soundex({f})"] = ([f"soundex({f})"], False)
            pool[f"any_token({f})"] = ([f"tok_{f}"], True)
        if t == "date":
            pool[f"year({f})"] = ([f"regexp_extract({f}, '(1[89]|20)[0-9][0-9]', 0)"], False)
    return pool


def _covers(labelled_pos: DataFrame, left: DataFrame, right: DataFrame, pool: dict) -> list[dict]:
    """For each labelled match, which single predicates put its two records in one block (collected: the labelled
    matches are a few hundred rows). Keys are computed on each side's own columns, then compared."""
    names = list(pool)
    lk = left.select(F.col("id").alias("l_id"), *[_key(*pool[n]).alias(f"p{i}") for i, n in enumerate(names)])
    rk = right.select(F.col("id").alias("r_id"), *[_key(*pool[n]).alias(f"q{i}") for i, n in enumerate(names)])
    x = labelled_pos.select("l_id", "r_id").join(lk, "l_id").join(rk, "r_id")
    tests = []
    for i, n in enumerate(names):
        a, b = F.col(f"p{i}"), F.col(f"q{i}")
        hit = F.arrays_overlap(a, b) if pool[n][1] else (a.isNotNull() & (a == b))
        tests.append(F.coalesce(hit, F.lit(False)).alias(f"t{i}"))
    return [{n: r[f"t{i}"] for i, n in enumerate(names)} for r in x.select(*tests).collect()]


def learn_blocker(left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame) -> list[str]:
    """Greedy weighted set cover; returns the chosen predicate names (a conjunction is 'a & b')."""
    pool = predicate_pool(cfg)
    pos = labelled.filter(F.col("label") == 1.0)
    covers = _covers(pos, left, right, pool)
    if not covers:
        raise ValueError("learned_blocker: no labelled match to learn from")
    cap = cfg.get("candidates.gram_cap")
    singles = sorted(pool, key=lambda p: -sum(c[p] for c in covers))[:10]
    candidates = {p: [p] for p in pool}
    for i, a in enumerate(singles):
        for b in singles[i + 1:]:
            if not (pool[a][1] or pool[b][1]):                     # conjunctions of scalar keys only
                candidates[f"{a} & {b}"] = [a, b]
    cost = {}
    for name, parts in candidates.items():
        if len(parts) == 1:
            exprs, is_array = pool[parts[0]]
        else:
            exprs, is_array = pool[parts[0]][0] + pool[parts[1]][0], False
        cost[name] = max(_block_join(left, right, exprs, cap, is_array).count(), 1)
    covered_by = {name: {i for i, c in enumerate(covers) if all(c[p] for p in parts)}
                  for name, parts in candidates.items()}
    target = cfg.get("candidates.learned_coverage") * len(covers)
    chosen, covered = [], set()
    while len(covered) < target and len(chosen) < cfg.get("candidates.learned_max_predicates"):
        best = max(candidates, key=lambda n: (len(covered_by[n] - covered) / cost[n], -cost[n], n))
        if not covered_by[best] - covered:
            break
        chosen.append(best)
        covered |= covered_by[best]
    log.info("learned_blocker: %s cover %d of %d labelled matches", chosen, len(covered), len(covers))
    return chosen


def _learned(left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame | None) -> DataFrame:
    if labelled is None:
        raise ValueError("candidates.method learned_blocker needs labelled pairs (labels.source file or truth_sample)")
    pool, cap = predicate_pool(cfg), cfg.get("candidates.gram_cap")
    parts = []
    for name in learn_blocker(left, right, cfg, labelled):
        names = name.split(" & ")
        if len(names) == 1:
            exprs, is_array = pool[names[0]]
        else:
            exprs, is_array = pool[names[0]][0] + pool[names[1]][0], False
        parts.append(_block_join(left, right, exprs, cap, is_array))
    out = parts[0]
    for p in parts[1:]:
        out = out.unionByName(p)
    return out.distinct()


# --- entry points --------------------------------------------------------------------------------------------------
def propose(method: str, left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame | None = None) -> DataFrame:
    """The pairs a method proposes, before the shared top-k cut (l_id, r_id)."""
    if method == "gram_topk":
        return top_k(_gram_all(left, right, cfg), cfg.get("candidates.k")).select("l_id", "r_id")
    if method == "field_blocks":
        return _field_blocks(left, right, cfg)
    if method == "minhash_lsh":
        return _minhash(left, right, cfg)
    if method == "learned_blocker":
        return _learned(left, right, cfg, labelled)
    if method == "union":
        parts = [propose(m, left, right, cfg, labelled) for m in cfg.get("candidates.union_of")]
        out = parts[0]
        for p in parts[1:]:
            out = out.unionByName(p)
        return out.distinct()
    raise ValueError(f"unknown candidate method {method}")


def generate(left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame | None = None) -> DataFrame:
    method = cfg.require("candidates.method")
    k = cfg.get("candidates.k")
    if method == "gram_topk":
        return top_k(_gram_all(left, right, cfg), k)
    return top_k(rescore(propose(method, left, right, cfg, labelled), left, right, cfg), k)


def gram_topk(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    return top_k(_gram_all(left, right, cfg), cfg.get("candidates.k"))


def budget_note(cfg: Config) -> str:
    return (f"{cfg.get('candidates.method')}: at most {cfg.get('candidates.k')} pairs per left record after the "
            f"shared ranking; gram joins <= sum over left records of (grams per record x {cfg.get('candidates.gram_cap')})")
