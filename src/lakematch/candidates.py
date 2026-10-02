"""Candidate pairs: a cheap first step that proposes, for each left record, a short list of right records worth scoring.

Every method *proposes* pairs; one shared step then ranks the proposals by the same IDF gram cosine and keeps the k
best per left record. So every method spends the same pair budget (at most k pairs per left record) and methods differ
only in which pairs they can reach — the comparison D06 asks for (candidate recall at equal pair budget).

The ranking score — IDF-weighted cosine over character q-gram sets:

    vocabulary  every q-gram of either side, minus the "ubiquitous" ones present in more than `rank_vocab_share` of
                the right records (a gram held by one right record always stays) — a cut relative to corpus size, not the join budget (ZR-3s: at 500 000 right
                records the fixed `gram_cap` of 400 left almost no gram a true pair shares, and most scores were 0)
    weight      w(g) = ln((1 + N) / (1 + df(g))) + 1 with N = |left| + |right| and df(g) = records holding g on
                either side (smoothed IDF, always > 0); `idf_weighted: false` sets w(g) = 1 (plain set cosine)
    score       cos(l, r) = sum_{g in l ∩ r} w(g)^2 / (||l|| · ||r||), both norms over the *same* vocabulary; a
                proposed pair that shares no kept gram scores 0
    keep        the k best right records per left record, ties broken by right id (deterministic)

Methods (`candidates.method`):

    gram_topk        pairs sharing a gram held by at most `gram_cap` right records (the join budget: at most
                     sum_l G_l × gram_cap rows, G_l = grams of left record l), pre-cut to the k best per left record
                     on the ranking score restricted to those grams, then ranked like every other method.
    field_blocks     equi-joins on keys: `field_blocks` is a list of blocks, each a list of Spark SQL expressions over
                     the entity columns, all non-empty and equal (e.g. [["postcode"], ["soundex(surname)",
                     "substring(date_of_birth, 1, 4)"]]). An empty list means the default blocks: every conjunction of
                     two scalar fields on their normalised values (soundex for person names) — two independent fields
                     agreeing stays selective at any size, where one field alone is shared by thousands of records at
                     10^6 — plus one block per multi-valued field; an entity with a single scalar field blocks on it
                     alone; a default conjunction whose join would emit more than `block_pairs_per_left` pairs per
                     left record is dropped. A key held by more than `gram_cap` right records is skipped.
    learned_blocker  set-cover blocking learnt from labelled matches (Bilenko et al. 2006; Michelson & Knoblock 2006):
                     a pool of cheap predicates (exact value, soundex, 3-character prefix, shared token, year, and the
                     conjunctions of the ten best), then greedily the predicate with the most newly covered matches per
                     generated pair, until `learned_coverage` of the labelled matches is covered or
                     `learned_max_predicates` are chosen. Learning is an action (a job task); needs labels.
    minhash_lsh      Spark MLlib MinHashLSH over the gram sets (HashingTF, binary), `lsh_tables` hash tables, pairs
                     within Jaccard distance `lsh_threshold`. MLlib: no Photon, not inside a pipeline flow.
    union            the union of the `union_of` methods' proposals.

Output: l_id, r_id, cand_score, cand_rank (1 = best), cand_gap (best score of this left record − this one).

The plan (ZR-6). Two choices depend on the data and need actions: which default field blocks stay under
`block_pairs_per_left` (a count per block) and which predicates the learned blocker picks (set cover over labels).
`resolve_plan()` makes them once, in a job task; `generate(..., plan=plan)` then builds the candidate plan with no
action at all, so it can sit inside a Spark Declarative Pipelines flow. Without a plan (the laptop run) each choice is
made inline, as before. minhash_lsh fits an MLlib model: it has no plan and cannot run inside a flow.
"""
from __future__ import annotations

import logging

from pyspark.sql import Column, DataFrame, Window, functions as F

from .config import Config

log = logging.getLogger("lakematch")


def _dedup(df: DataFrame, *cols: str) -> DataFrame:
    """Distinct rows of `cols`, as a group-by: Spark Connect plans distinct() / dropDuplicates() by analysing the
    input (its column list), which a pipeline flow cannot afford; an aggregate on named columns stays lazy."""
    return df.groupBy(*cols).agg(F.count(F.lit(1)).alias("_n")).select(*cols)


def _union(a: DataFrame, b: DataFrame) -> DataFrame:
    """Pair proposals (l_id, r_id) of two methods. Positional union after an explicit select: Spark Connect plans
    unionByName by analysing both inputs, which a pipeline flow cannot afford (the upstream tables do not exist yet
    when the flow is registered)."""
    return a.select("l_id", "r_id").union(b.select("l_id", "r_id"))


# --- the shared ranking --------------------------------------------------------------------------------------------
def _gram_weights(left: DataFrame, right: DataFrame, cfg: Config):
    """Weighted grams of each side over the ranking vocabulary, their norms, and `joinable` (the grams the gram join
    may use: held by at most `gram_cap` right records)."""
    cap, weighted = cfg.get("candidates.gram_cap"), cfg.get("candidates.idf_weighted")
    share = cfg.get("candidates.rank_vocab_share")
    el = left.select(F.col("id").alias("l_id"), F.explode("_grams").alias("gram"))
    er = right.select(F.col("id").alias("r_id"), F.explode("_grams").alias("gram"))
    df_l = el.groupBy("gram").agg(F.count(F.lit(1)).alias("df_l"))
    df_r = er.groupBy("gram").agg(F.count(F.lit(1)).alias("df_r"))
    sizes = left.agg(F.count(F.lit(1)).alias("n_l")).crossJoin(right.agg(F.count(F.lit(1)).alias("n_r")))
    # coalesce, not fillna: Spark Connect plans fillna by analysing its input, which a pipeline flow cannot afford
    vocab = (df_l.join(df_r, "gram", "full")
                 .select("gram", *[F.coalesce(c, F.lit(0)).alias(c) for c in ("df_l", "df_r")]).crossJoin(sizes)
                 .filter(F.col("df_r") <= F.greatest(F.lit(share) * F.col("n_r"), F.lit(1))))
    w = (F.log((1 + F.col("n_l") + F.col("n_r")) / (1 + F.col("df_l") + F.col("df_r"))) + 1) if weighted else F.lit(1.0)
    vocab = vocab.select("gram", w.alias("w"), (F.col("df_r") <= cap).alias("joinable"))
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
    props = _dedup(proposals, "l_id", "r_id")
    dot = (props.join(wl.select("l_id", "gram", "w"), "l_id")
                .join(wr.select("r_id", "gram", F.col("w").alias("w_r")), ["r_id", "gram"])
                .groupBy("l_id", "r_id").agg(F.sum(F.col("w") * F.col("w_r")).alias("dot")))
    scored = _cosine(dot, norm_l, norm_r)
    return (props.join(scored, ["l_id", "r_id"], "left")
                 .select("l_id", "r_id", F.coalesce("cand_score", F.lit(0.0)).alias("cand_score")))


# --- proposers -----------------------------------------------------------------------------------------------------
def _gram_all(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    """Every pair sharing a joinable gram, scored on the joinable grams only (the norms are the full ranking
    vocabulary's, so the score is a lower bound of the ranking cosine; `generate` rescores the survivors)."""
    wl, wr, norm_l, norm_r = _gram_weights(left, right, cfg)
    dot = (wl.filter("joinable").select("l_id", "gram", "w").join(wr.filter("joinable").select("r_id", "gram"), "gram")
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
        return _dedup(out.filter(F.col("k").isNotNull() & (F.length("k") > 0)), alias, "k")
    kl, kr = keyed(left, "l_id"), keyed(right, "r_id")
    small = kr.groupBy("k").agg(F.count(F.lit(1)).alias("n")).filter(F.col("n") <= cap).select("k")
    return _dedup(kl.join(small, "k").join(kr, "k"), "l_id", "r_id")


def default_blocks(cfg: Config) -> tuple[list[list[str]], list[str]]:
    """(scalar blocks, array-key expressions): every conjunction of two scalar fields (numbers excluded: their text
    form is not a key) on normalised values, one block alone when there is a single scalar field, and one
    share-any-item block per multi-valued field."""
    norm = lambda f, s: f"soundex({f})" if s["type"] == "person_name" else f
    scalar = [norm(f, s) for f, s in cfg.fields.items() if not s.get("multi") and s["type"] != "number"]
    arrays = [f"set_{f}" for f, s in cfg.fields.items() if s.get("multi")]
    if len(scalar) < 2:
        return [[e] for e in scalar], arrays
    return [[a, b] for i, a in enumerate(scalar) for b in scalar[i + 1:]], arrays


def _block_keys(left: DataFrame, right: DataFrame, blocks: list[list[str]], cap: int):
    def keyed(side: DataFrame, alias: str) -> DataFrame:
        keys = F.array(*[F.concat(F.lit(f"{i}\u0002"), _key(list(b), False)) for i, b in enumerate(blocks)])
        out = side.select(F.col("id").alias(alias), F.explode(keys).alias("k"))
        return out.filter(F.col("k").isNotNull())
    kl, kr = keyed(left, "l_id"), keyed(right, "r_id")
    return kl, kr, kr.groupBy("k").agg(F.count(F.lit(1)).alias("n_r")).filter(F.col("n_r") <= cap)


def kept_blocks(left: DataFrame, right: DataFrame, blocks: list[list[str]], cap: int, pairs_per_left: float) -> list[int]:
    """Indices of the blocks whose join emits at most `pairs_per_left` pairs per left record (an action: one count per
    block, collected — a few dozen rows)."""
    kl, _, small = _block_keys(left, right, blocks, cap)
    budget = pairs_per_left * left.count()
    block = F.substring_index("k", "\u0002", 1)
    sizes = (kl.groupBy("k").agg(F.count(F.lit(1)).alias("n_l")).join(small, "k")
               .groupBy(block.alias("b")).agg(F.sum(F.col("n_l") * F.col("n_r")).alias("pairs")).collect())
    dropped = {" & ".join(blocks[int(r.b)]): int(r.pairs) for r in sizes if r.pairs > budget}
    if dropped:
        log.info("field_blocks: dropped %d block(s) over %s pairs per left record: %s", len(dropped),
                 pairs_per_left, dropped)
    return sorted(int(r.b) for r in sizes if r.pairs <= budget)


def _multi_block_join(left: DataFrame, right: DataFrame, blocks: list[list[str]], cap: int,
                      pairs_per_left: float | None = None, kept: list[int] | None = None) -> DataFrame:
    """Pairs agreeing on any of `blocks`, in ONE join: each record explodes into one tagged key per block (a plan with
    a join per block is too deep for Spark Connect's protobuf at 28 blocks). A key held by more than `cap` right
    records is skipped, block by block. With `pairs_per_left`, a whole block whose join would emit more than that many
    pairs per left record is dropped first (one count per block, collected: a few dozen rows) — unless `kept`, the
    plan's answer to that question, is given: then the join has no action."""
    kl, kr, small = _block_keys(left, right, blocks, cap)
    if kept is None and pairs_per_left is not None:
        kept = kept_blocks(left, right, blocks, cap, pairs_per_left)
    if kept is not None:
        small = small.filter(F.substring_index("k", "\u0002", 1).isin([str(i) for i in kept]))
    return _dedup(kl.join(small.select("k"), "k").join(kr, "k"), "l_id", "r_id")


def _field_blocks(left: DataFrame, right: DataFrame, cfg: Config, plan: dict | None = None) -> DataFrame:
    cap = cfg.get("candidates.gram_cap")
    if cfg.get("candidates.field_blocks"):          # the user's own blocks: taken as written
        blocks, arrays, per_left = cfg.get("candidates.field_blocks"), [], None
    else:                                           # default conjunctions: only the ones selective at this size
        (blocks, arrays), per_left = default_blocks(cfg), cfg.get("candidates.block_pairs_per_left")
    kept = (plan or {}).get("field_blocks_kept") if per_left is not None else None
    parts = [_multi_block_join(left, right, [list(b) for b in blocks], cap, per_left, kept)] if blocks else []
    parts += [_block_join(left, right, [a], cap, is_array=True) for a in arrays]
    out = parts[0]
    for p in parts[1:]:
        out = _union(out, p)
    return _dedup(out, "l_id", "r_id")


def _minhash(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    from pyspark.ml.feature import HashingTF, MinHashLSH
    tf = HashingTF(inputCol="_grams", outputCol="_gv", numFeatures=1 << 20, binary=True)
    nonempty = F.size("_grams") > 0
    lv = tf.transform(left.select("id", "_grams").filter(nonempty))
    rv = tf.transform(right.select("id", "_grams").filter(nonempty))
    model = MinHashLSH(inputCol="_gv", outputCol="_mh", numHashTables=cfg.get("candidates.lsh_tables"),
                       seed=cfg.get("matcher.seed")).fit(lv.unionByName(rv))
    joined = model.approxSimilarityJoin(lv, rv, cfg.get("candidates.lsh_threshold"))   # distance column: distCol
    return _dedup(joined.select(F.col("datasetA.id").alias("l_id"), F.col("datasetB.id").alias("r_id")), "l_id", "r_id")


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
    # Cost and coverage both come from the capped join itself: a match whose key is held by more than gram_cap right
    # records is NOT covered (ZR-3s: at 10^6, single-field keys are all over the cap; counting them as covered at a
    # cost of 1 made the cover pick predicates that propose nothing).
    pos_ids = _dedup(pos, "l_id", "r_id").withColumn("_hit", F.lit(1))
    cost, covered_by = {}, {}
    for name, parts in candidates.items():
        if len(parts) == 1:
            exprs, is_array = pool[parts[0]]
        else:
            exprs, is_array = pool[parts[0]][0] + pool[parts[1]][0], False
        row = (_block_join(left, right, exprs, cap, is_array).join(pos_ids, ["l_id", "r_id"], "left")
               .agg(F.count(F.lit(1)).alias("n"),
                    F.collect_list(F.when(F.col("_hit") == 1, F.concat_ws("\u0001", "l_id", "r_id"))).alias("hits"))
               .first())
        cost[name], covered_by[name] = max(row.n, 1), set(row.hits)
    target = cfg.get("candidates.learned_coverage") * pos_ids.count()
    chosen, covered = [], set()
    while len(covered) < target and len(chosen) < cfg.get("candidates.learned_max_predicates"):
        best = max(candidates, key=lambda n: (len(covered_by[n] - covered) / cost[n], -cost[n], n))
        if not covered_by[best] - covered:
            break
        chosen.append(best)
        covered |= covered_by[best]
    log.info("learned_blocker: %s cover %d of %d labelled matches", chosen, len(covered),
             round(target / cfg.get("candidates.learned_coverage")))
    return chosen


def _learned(left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame | None,
             plan: dict | None = None) -> DataFrame:
    chosen = (plan or {}).get("learned_predicates")
    if chosen is None:
        if labelled is None:
            raise ValueError("candidates.method learned_blocker needs labelled pairs (labels.source file or "
                             "truth_sample), or a plan from resolve_plan()")
        chosen = learn_blocker(left, right, cfg, labelled)
    pool, cap = predicate_pool(cfg), cfg.get("candidates.gram_cap")
    parts = []
    for name in chosen:
        names = name.split(" & ")
        if len(names) == 1:
            exprs, is_array = pool[names[0]]
        else:
            exprs, is_array = pool[names[0]][0] + pool[names[1]][0], False
        parts.append(_block_join(left, right, exprs, cap, is_array))
    out = parts[0]
    for p in parts[1:]:
        out = _union(out, p)
    return _dedup(out, "l_id", "r_id")


# --- entry points --------------------------------------------------------------------------------------------------
def _methods(cfg: Config) -> set[str]:
    m = cfg.get("candidates.method")
    return set(cfg.get("candidates.union_of")) if m == "union" else {m}


def resolve_plan(left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame | None = None) -> dict:
    """The data-dependent choices of the configured methods, made once (actions; a job task). JSON-serialisable."""
    used, plan = _methods(cfg), {"method": cfg.get("candidates.method")}
    if "field_blocks" in used and not cfg.get("candidates.field_blocks"):
        blocks, _ = default_blocks(cfg)
        plan["field_blocks"] = blocks
        plan["field_blocks_kept"] = (kept_blocks(left, right, [list(b) for b in blocks], cfg.get("candidates.gram_cap"),
                                                 cfg.get("candidates.block_pairs_per_left")) if blocks else [])
    if "learned_blocker" in used:
        if labelled is None:
            raise ValueError("resolve_plan: learned_blocker needs labelled pairs")
        plan["learned_predicates"] = learn_blocker(left, right, cfg, labelled)
    if "minhash_lsh" in used:
        plan["unplannable"] = ["minhash_lsh"]       # fits an MLlib model: job task only, never inside a flow
    return plan


def propose(method: str, left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame | None = None,
            plan: dict | None = None) -> DataFrame:
    """The pairs a method proposes, before the shared top-k cut (l_id, r_id)."""
    if method == "gram_topk":
        return top_k(_gram_all(left, right, cfg), cfg.get("candidates.k")).select("l_id", "r_id")
    if method == "field_blocks":
        return _field_blocks(left, right, cfg, plan)
    if method == "minhash_lsh":
        return _minhash(left, right, cfg)
    if method == "learned_blocker":
        return _learned(left, right, cfg, labelled, plan)
    if method == "union":
        parts = [propose(m, left, right, cfg, labelled, plan) for m in cfg.get("candidates.union_of")]
        out = parts[0]
        for p in parts[1:]:
            out = _union(out, p)
        return _dedup(out, "l_id", "r_id")
    raise ValueError(f"unknown candidate method {method}")


def generate(left: DataFrame, right: DataFrame, cfg: Config, labelled: DataFrame | None = None,
             plan: dict | None = None) -> DataFrame:
    """Every method's proposals, ranked by the shared score and cut to k per left record. With a `plan` from
    resolve_plan(), no action runs (a pipeline flow)."""
    method = cfg.require("candidates.method")
    if plan is not None and plan.get("method") != method:
        raise ValueError(f"candidate plan was resolved for {plan.get('method')}, the config says {method}")
    return top_k(rescore(propose(method, left, right, cfg, labelled, plan), left, right, cfg),
                 cfg.get("candidates.k"))


def gram_topk(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    return top_k(rescore(propose("gram_topk", left, right, cfg), left, right, cfg), cfg.get("candidates.k"))


def budget_note(cfg: Config) -> str:
    return (f"{cfg.get('candidates.method')}: at most {cfg.get('candidates.k')} pairs per left record after the "
            f"shared ranking (vocabulary: grams in <= {cfg.get('candidates.rank_vocab_share'):.0%} of right records); "
            f"gram and key joins <= {cfg.get('candidates.gram_cap')} right records per gram or key")
