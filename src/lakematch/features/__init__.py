"""Comparison vector for each candidate pair: one feature family per field type (spec/BRIEF.md *Similarity*,
research digest spec/research/similarity_sota.md).

Every feature a missing value can touch gives -1 when either side is empty, so the classifier learns "unknown" apart
from "different". Families (`features.exclude` drops any of them — the ablation's lever):

| Family       | Columns        | Field types                                   | What                                                     |
|--------------|----------------|-----------------------------------------------|----------------------------------------------------------|
| candidate    | cand_*         | (pair)                                        | candidate score, rank, gap to the best (linkage runs)    |
| edit         | lev_           | all but number                                | 1 - levenshtein / max length (string_similarity levenshtein or both) |
| exact        | eq_            | all                                           | equality after normalisation (multi codes: any shared item) |
| phonetic     | sdx_, sdt_     | person_name                                   | soundex agreement; soundex token-set Jaccard (order-free) |
| monge_elkan  | mek_           | person_name, address, organisation, title, multi code | symmetric token Monge-Elkan, m = 2 (Jimenez 2009), inner = normalised levenshtein |
| token_idf    | itc_           | person_name, address, organisation, title     | cosine of IDF-weighted token sets (Cohen 2003)           |
| gram         | gov_           | address, organisation, title                  | Jaccard of character q-gram sets                         |
| structure    | swp_ ini_ num_ lgf_ fpe_ fpl_ cnt_ yr_ dpj_ rel_ csj_ | per type (below)          | swapped name order, initial vs full name, numeric-token agreement, legal form, fingerprint, containment, year, date parts, relative number gap, code-set Jaccard |
| rarity       | rar_           | person_name, organisation                     | IDF of the rarest shared token, scaled to [0, 1]         |
| embedding    | ebc_           | embeddings.fields_of_type (organisation, title) | cosine of record embeddings computed once per record by a provider |
| jaro_winkler | jw_            | person_name, organisation, code (single)      | UDF before Spark 4.3, the built-in from 4.3 — optional   |
| affine_gap   | agp_           | address, organisation, title                  | character local alignment with affine gaps — UDF, optional |

Structure features: person_name -> swp_ (same tokens, other order), ini_ (an initial on one side matches a token on
the other); address and title -> num_ (Jaccard of tokens holding a digit: house and model numbers); organisation ->
num_, lgf_ (legal-form agreement), fpe_ / fpl_ (fingerprint without legal forms: equal / levenshtein), cnt_ (one
token set inside the other); date -> yr_ (same year), dpj_ (Jaccard of day/month/year parts, month names mapped);
number -> rel_ (1 - |a - b| / max(|a|, |b|)); multi code -> csj_ (Jaccard of the identifier sets).

Everything outside the last three families is a Spark SQL built-in expression. The embedding family's *comparison* is a
built-in too; the vectors are computed once per record at the entity stage (a pandas UDF, see embeddings/) and pinned
there by materialize(), so the pair plan scores them with array expressions only.
"""
from __future__ import annotations

import logging

from pyspark.sql import Column, DataFrame, functions as F

from .. import embeddings
from ..config import Config, ConfigError
from ..entity import MULTI_TOKEN_TYPES, TEXT_TYPES, qgrams

log = logging.getLogger("lakematch")
MISSING = -1.0
LEGAL_FORMS = ["sa", "sas", "sasu", "sarl", "eurl", "sci", "snc", "gie", "se", "gmbh", "ag", "kg", "ohg", "ltd",
               "limited", "inc", "incorporated", "llc", "llp", "lp", "corp", "corporation", "co", "company", "plc",
               "bv", "nv", "spa", "srl", "ab", "as", "oy", "pty", "pte", "kk"]
MONTHS = {m: str(i + 1) for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
FAMILY_OF_PREFIX = {"cand": "candidate", "lev": "edit", "eq": "exact", "sdx": "phonetic", "sdt": "phonetic",
                    "mek": "monge_elkan", "itc": "token_idf", "gov": "gram", "rar": "rarity", "ebc": "embedding",
                    "jw": "jaro_winkler", "agp": "affine_gap",
                    **{p: "structure" for p in ("swp", "ini", "num", "lgf", "fpe", "fpl", "cnt", "yr", "dpj", "rel",
                                                "csj")}}


def family_of(column: str) -> str:
    return FAMILY_OF_PREFIX[column.split("_", 1)[0]]


# --- building blocks (all built-ins) ---------------------------------------------------------------------------------
def _norm_lev(a: Column, b: Column) -> Column:
    return 1 - F.levenshtein(a, b) / F.greatest(F.length(a), F.length(b))


def _present(a: Column, b: Column) -> Column:
    return (F.length(a) > 0) & (F.length(b) > 0)


def _nonempty(a: Column, b: Column) -> Column:
    return (F.size(a) > 0) & (F.size(b) > 0)


def _jaccard(ga: Column, gb: Column) -> Column:
    return F.when(_nonempty(ga, gb),
                  F.size(F.array_intersect(ga, gb)) / F.size(F.array_union(ga, gb))).otherwise(MISSING)


def _monge_elkan(ta: Column, tb: Column) -> Column:
    def directed(xs: Column, ys: Column) -> Column:
        best = F.transform(xs, lambda x: F.pow(F.array_max(F.transform(ys, lambda y: _norm_lev(x, y))), 2))
        return F.sqrt(F.aggregate(best, F.lit(0.0), lambda acc, v: acc + v) / F.size(xs))
    return F.when(_nonempty(ta, tb), (directed(ta, tb) + directed(tb, ta)) / 2).otherwise(MISSING)


def _idf_cosine(ma: Column, mb: Column) -> Column:
    def norm(m: Column) -> Column:
        return F.sqrt(F.aggregate(F.map_values(m), F.lit(0.0), lambda acc, v: acc + v * v))
    shared = F.array_intersect(F.map_keys(ma), F.map_keys(mb))
    dot = F.aggregate(shared, F.lit(0.0), lambda acc, t: acc + ma[t] * mb[t])
    both = (F.size(F.map_keys(ma)) > 0) & (F.size(F.map_keys(mb)) > 0)
    return F.when(both, dot / (norm(ma) * norm(mb))).otherwise(MISSING)


def _rarity(ma: Column, mb: Column) -> Column:
    shared = F.array_intersect(F.map_keys(ma), F.map_keys(mb))
    top = F.aggregate(shared, F.lit(0.0), lambda acc, t: F.greatest(acc, ma[t]))
    return F.when((F.size(F.map_keys(ma)) > 0) & (F.size(F.map_keys(mb)) > 0), top).otherwise(MISSING)


def _digit_tokens(t: Column) -> Column:
    return F.filter(t, lambda x: x.rlike(r"\d"))


def _date_parts(t: Column) -> Column:
    month = F.create_map(*[x for kv in MONTHS.items() for x in (F.lit(kv[0]), F.lit(kv[1]))])
    mapped = F.transform(t, lambda x: F.coalesce(F.try_element_at(month, F.substring(x, 1, 3)), x))
    nums = F.filter(mapped, lambda x: x.rlike(r"^\d+$"))
    return F.array_distinct(F.transform(nums, lambda x: F.regexp_replace(x, r"^0+(?=\d)", "")))


def _year(t: Column) -> Column:
    return F.try_element_at(F.filter(t, lambda x: x.rlike(r"^(1[89]|20)\d\d$")), F.lit(1))


def _number(s: Column) -> Column:
    return F.regexp_extract(F.regexp_replace(s, ",", ""), r"-?\d+(\.\d+)?", 0).try_cast("double")


def token_weights(left: DataFrame, right: DataFrame, fields: list[str]) -> tuple[DataFrame, DataFrame]:
    """Add `ti_<field>` for each field: the record's distinct tokens -> smoothed IDF over both sides, scaled to (0, 1]
    by the IDF of a token seen once (cosines are scale-free; the rarity feature reads the scaled value). An empty map
    means no token. All fields in one pass — one join per side — so the plan stays shallow enough for Spark Connect."""
    if isinstance(fields, str):
        fields = [fields]

    def long(side: DataFrame) -> DataFrame:
        per_field = F.array(*[F.struct(F.lit(f).alias("f"), F.array_distinct(f"tok_{f}").alias("ts")) for f in fields])
        return (side.select("id", F.explode(per_field).alias("x"))
                    .select("id", F.col("x.f").alias("f"), F.explode("x.ts").alias("t")))
    ll, rl = long(left), long(right)
    n = left.agg(F.count(F.lit(1)).alias("n_l")).crossJoin(right.agg(F.count(F.lit(1)).alias("n_r")))
    total = 1 + F.col("n_l") + F.col("n_r")
    idf = (ll.select("f", "t").unionAll(rl.select("f", "t")).groupBy("f", "t").agg(F.count(F.lit(1)).alias("df"))
             .crossJoin(n)
             .select("f", "t", ((F.log(total / (1 + F.col("df"))) + 1) / (F.log(total / 2) + 1)).alias("w")))

    def add(side: DataFrame, lng: DataFrame) -> DataFrame:
        maps = [F.map_from_entries(F.collect_list(F.when(F.col("f") == f, F.struct("t", "w")))).alias(f"ti_{f}")
                for f in fields]
        weights = lng.join(idf, ["f", "t"]).groupBy("id").agg(*maps)
        empty = F.create_map().cast("map<string,double>")
        return (side.join(weights, "id", "left")
                    .withColumns({f"ti_{f}": F.coalesce(F.col(f"ti_{f}"), empty) for f in fields}))
    return add(left, ll), add(right, rl)


# --- which families run ------------------------------------------------------------------------------------------------
def active_families(cfg: Config) -> set[str]:
    fams = {"candidate", "exact", "phonetic", "structure", "rarity", "embedding"}
    sim = cfg.get("features.string_similarity")
    fams |= {"edit"} if sim in ("levenshtein", "both") else set()
    fams |= {"jaro_winkler"} if sim in ("jaro_winkler", "both") else set()
    multi = cfg.get("features.multi_token")
    fams |= {"token_idf"} if "idf_token_cosine" in multi else set()
    fams |= {"gram"} if "gram_overlap" in multi else set()
    fams |= {"monge_elkan"} if "monge_elkan_token" in multi else set()
    fams |= {"affine_gap"} if "affine_gap_udf" in multi else set()
    return fams - set(cfg.get("features.exclude"))


def spark_at_least(version: str, major: int, minor: int) -> bool:
    parts = [int(p) for p in version.split(".")[:2] if p.isdigit()]
    return tuple(parts) >= (major, minor)


def check(cfg: Config, spark_version: str | None = None) -> None:
    cfg.require("features.string_similarity")
    for choice in cfg.get("features.multi_token"):
        cfg.require("features.multi_token", choice)
    cfg.require("features.embeddings.provider")
    fams = active_families(cfg)
    if "affine_gap" in fams and not cfg.get("features.udf_features"):
        raise ConfigError("affine_gap_udf is a UDF feature (never Photon); set features.udf_features: true to allow it")
    if "jaro_winkler" in fams and spark_version and not spark_at_least(spark_version, 4, 3) \
            and not cfg.get("features.udf_features"):
        raise ConfigError(f"string_similarity {cfg.get('features.string_similarity')}: Jaro-Winkler is a UDF on Spark "
                          f"{spark_version} (a built-in from 4.3); set features.udf_features: true to allow it")


def embedded_fields(cfg: Config) -> list[str]:
    if "embedding" not in active_families(cfg):
        return []
    return cfg.fields_of_type(*cfg.get("features.embeddings.fields_of_type"))


def prepare_sides(left: DataFrame, right: DataFrame, cfg: Config) -> tuple[DataFrame, DataFrame]:
    """Record-level work done once per record, before pairs exist. Materialise the result before pairing."""
    fams = active_families(cfg)
    types = {f: s["type"] for f, s in cfg.fields.items()}
    if fams & {"token_idf", "rarity"}:
        text = [f for f, t in types.items() if t in TEXT_TYPES]
        if text:
            left, right = token_weights(left, right, text)
    if "gram" in fams:
        q = cfg.get("candidates.q")
        for f in cfg.fields_of_type(*MULTI_TOKEN_TYPES):
            left, right = left.withColumn(f"qg_{f}", qgrams(F.col(f), q)), right.withColumn(f"qg_{f}", qgrams(F.col(f), q))
    fields = embedded_fields(cfg)
    if fields:
        provider = embeddings.resolve(cfg)
        if provider is not None:
            for f in fields:
                left, right = provider.add_column(left, f), provider.add_column(right, f)
    return left, right


# --- the comparison vector -------------------------------------------------------------------------------------------
def compare(pairs: DataFrame, cfg: Config, candidates: bool = True, embedded: bool | None = None) -> tuple[DataFrame, list[str]]:
    """`pairs` holds l_<col> and r_<col> for every entity column (and cand_* when `candidates`); returns it with the
    feature columns added, and their names. `embedded` says whether prepare_sides added embeddings (default: whether a
    provider resolves now)."""
    version = pairs.sparkSession.version
    check(cfg, version)
    fams = active_families(cfg)
    cap = cfg.get("features.token_cap")
    if embedded is None:
        embedded = bool(embedded_fields(cfg)) and embeddings.resolve(cfg, quiet=True) is not None
    emb_fields = set(embedded_fields(cfg)) if embedded else set()
    cols: dict[str, Column] = {}
    L = lambda c: F.col(f"l_{c}")
    R = lambda c: F.col(f"r_{c}")

    for f, spec in cfg.fields.items():
        t, multi = spec["type"], spec.get("multi", False)
        a, b = L(f), R(f)
        ok = _present(a, b)
        if "edit" in fams and t != "number":
            cols[f"lev_{f}"] = F.when(ok, _norm_lev(a, b)).otherwise(MISSING)
        if "exact" in fams:
            same = F.arrays_overlap(L(f"set_{f}"), R(f"set_{f}")) if multi else (a == b)
            cols[f"eq_{f}"] = F.when(ok, same.cast("double")).otherwise(MISSING)
        if t == "person_name" and "phonetic" in fams:
            cols[f"sdx_{f}"] = F.when(ok, (F.soundex(a) == F.soundex(b)).cast("double")).otherwise(MISSING)
            sx = lambda c: F.array_distinct(F.transform(L(f"tok_{f}") if c == "l" else R(f"tok_{f}"), lambda x: F.soundex(x)))
            cols[f"sdt_{f}"] = _jaccard(sx("l"), sx("r"))
        if "monge_elkan" in fams and (t in TEXT_TYPES or multi):
            src = f"set_{f}" if multi else f"tok_{f}"
            cols[f"mek_{f}"] = _monge_elkan(F.slice(L(src), 1, cap), F.slice(R(src), 1, cap))
        if "token_idf" in fams and t in TEXT_TYPES:
            cols[f"itc_{f}"] = _idf_cosine(L(f"ti_{f}"), R(f"ti_{f}"))
        if "gram" in fams and t in MULTI_TOKEN_TYPES:
            cols[f"gov_{f}"] = _jaccard(L(f"qg_{f}"), R(f"qg_{f}"))
        if "rarity" in fams and t in ("person_name", "organisation"):
            cols[f"rar_{f}"] = _rarity(L(f"ti_{f}"), R(f"ti_{f}"))
        if "structure" in fams:
            ta, tb = L(f"tok_{f}"), R(f"tok_{f}")
            if t == "person_name":
                same_set = F.array_sort(ta) == F.array_sort(tb)
                cols[f"swp_{f}"] = F.when(ok, (same_set & (a != b)).cast("double")).otherwise(MISSING)
                init = lambda xs: F.filter(xs, lambda x: F.length(x) == 1)
                firsts = lambda xs: F.transform(xs, lambda x: F.substring(x, 1, 1))
                cols[f"ini_{f}"] = F.when(ok, (F.arrays_overlap(init(ta), firsts(tb)) |
                                               F.arrays_overlap(init(tb), firsts(ta))).cast("double")).otherwise(MISSING)
            if t in MULTI_TOKEN_TYPES:
                cols[f"num_{f}"] = _jaccard(F.array_distinct(_digit_tokens(ta)), F.array_distinct(_digit_tokens(tb)))
            if t == "organisation":
                legal = lambda xs: F.array_sort(F.array_distinct(F.filter(xs, lambda x: x.isin(LEGAL_FORMS))))
                fp = lambda xs: F.array_join(F.array_sort(F.array_distinct(
                    F.filter(xs, lambda x: ~x.isin(LEGAL_FORMS)))), "")
                la, lb, fa, fb = legal(ta), legal(tb), fp(ta), fp(tb)
                cols[f"lgf_{f}"] = F.when(_nonempty(la, lb), (la == lb).cast("double")).otherwise(MISSING)
                cols[f"fpe_{f}"] = F.when(_present(fa, fb), (fa == fb).cast("double")).otherwise(MISSING)
                cols[f"fpl_{f}"] = F.when(_present(fa, fb), _norm_lev(fa, fb)).otherwise(MISSING)
                small = F.least(F.size(F.array_distinct(ta)), F.size(F.array_distinct(tb)))
                cols[f"cnt_{f}"] = F.when(_nonempty(ta, tb), (F.size(F.array_intersect(ta, tb)) == small)
                                          .cast("double")).otherwise(MISSING)
            if t == "date":
                ya, yb = _year(ta), _year(tb)
                cols[f"yr_{f}"] = F.when(ya.isNotNull() & yb.isNotNull(), (ya == yb).cast("double")).otherwise(MISSING)
                cols[f"dpj_{f}"] = _jaccard(_date_parts(ta), _date_parts(tb))
            if t == "number":
                na, nb = _number(a), _number(b)
                gap = 1 - F.abs(na - nb) / F.greatest(F.abs(na), F.abs(nb))
                cols[f"rel_{f}"] = (F.when(na.isNull() | nb.isNull(), MISSING)
                                     .when((na == 0) & (nb == 0), 1.0).otherwise(F.greatest(gap, F.lit(0.0))))
            if multi:
                cols[f"csj_{f}"] = _jaccard(L(f"set_{f}"), R(f"set_{f}"))
        if f in emb_fields:
            ea, eb = L(f"emb_{f}"), R(f"emb_{f}")
            dot = F.aggregate(F.zip_with(ea, eb, lambda x, y: x * y), F.lit(0.0), lambda acc, v: acc + v)
            cols[f"ebc_{f}"] = F.when(ea.isNotNull() & eb.isNotNull(), dot).otherwise(MISSING)
        if "jaro_winkler" in fams and (t in ("person_name", "organisation") or (t == "code" and not multi)):
            from . import udf
            cols[f"jw_{f}"] = F.when(ok, udf.jaro_winkler(a, b, version)).otherwise(MISSING)
        if "affine_gap" in fams and t in MULTI_TOKEN_TYPES:
            from . import udf
            cols[f"agp_{f}"] = F.when(ok, udf.affine_gap(a, b)).otherwise(MISSING)

    out = pairs.withColumns({k: v.cast("double") for k, v in cols.items()})
    names = list(cols)
    if candidates and "candidate" in fams:
        out = out.withColumn("cand_rank", F.col("cand_rank").cast("double"))
        names = ["cand_score", "cand_rank", "cand_gap"] + names
    return out, names
