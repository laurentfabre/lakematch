"""Lazy, typed comparison vectors. Statistics and embeddings fit outside flows."""
from pyspark.sql import functions as F

from .entity import grams
from .similarity import (affine_gap, array_cosine, jaccard, jaro_winkler, lev,
                         monge_elkan, tokens, weighted_cosine)


TYPE_METRICS = {
    "person_name": ["initials", "token_overlap", "accent_eq"],
    "address": ["numeric_overlap", "token_overlap"],
    "organisation": ["legal_name_eq", "acronym_eq", "token_overlap"],
    "title": ["numeric_overlap", "token_overlap"],
    "code": ["prefix_eq", "suffix_eq", "length_ratio"],
    "date": ["year_eq", "month_eq", "day_eq", "date_proximity", "invalid"],
    "number": ["numeric_eq", "relative_similarity", "sign_eq", "invalid"],
}


def embedding_fields(config):
    spec = config["features"]["embeddings"]
    return [n for n, f in config["entity"]["fields"].items()
            if spec["provider"] != "none" and f["type"] in spec["fields_of_type"]
            and f["type"] not in config["features"]["exclude_field_types"]]


def metrics_for(name, spec, config):
    settings = config["features"]
    if spec["type"] in settings["exclude_field_types"]:
        return []
    string = settings["string_similarity"]
    metrics = (["lev"] if string != "jaro_winkler" else []) + ["eq", "sdx", "missing"]
    if string != "levenshtein":
        metrics.append("jw")
    if settings["field_families"]:
        metrics += TYPE_METRICS[spec["type"]]
    metrics += settings["multi_token"]
    if spec.get("multiple"):
        metrics += ["value_overlap", "best_value_lev"]
    if name in embedding_fields(config):
        metrics += ["embedding_cosine", "embedding_missing"]
    return metrics


def feature_order(config):
    return ["cos", "rank", "gap"] + [f"{metric}_{name}" for name, spec in config["entity"]["fields"].items()
                                       for metric in metrics_for(name, spec, config)]


def build(pairs, left, right, config):
    config.require_implemented()
    settings = config["features"]
    extras = []
    for name, spec in config["entity"]["fields"].items():
        if spec["type"] in {"date", "number"}:
            extras.append(f"lm_raw_{name}")
        if spec.get("multiple"):
            extras.append(f"lm_values_{name}")
        if "idf_token_cosine" in settings["multi_token"]:
            extras.append(f"lm_weights_{name}")
    extras += [f"lm_emb_{n}" for n in embedding_fields(config)]
    def side(frame, prefix, key):
        return frame.select(F.col("rec_id").alias(key), *[F.col(n).alias(f"{prefix}{n}") for n in config.fields + extras])
    joined = pairs.join(side(left, "l_", "a_id"), "a_id").join(side(right, "r_", "b_id"), "b_id")
    expressions = []
    for name, spec in config["entity"]["fields"].items():
        original_l, original_r = F.col(f"l_{name}"), F.col(f"r_{name}")
        l, r = [F.substring(c, 1, settings["max_chars"]) for c in (original_l, original_r)]
        both = (F.length(l) > 0) & (F.length(r) > 0)
        lt, rt = [tokens(c, settings["max_tokens"]) for c in (l, r)]
        def present(value):
            return F.when(both, value.cast("double")).otherwise(-1.0)
        overlap = F.size(F.array_intersect(lt, rt)) / F.greatest(F.least(F.size(lt), F.size(rt)), F.lit(1))
        initials = lambda ts: F.concat_ws("", F.transform(ts, lambda t: F.substring(t, 1, 1)))
        numeric = lambda ts: F.filter(ts, lambda t: t.rlike("[0-9]"))
        legal = lambda value: F.trim(F.regexp_replace(value, r"\b(inc|incorporated|ltd|limited|llc|corp|corporation|gmbh)\b", ""))
        values = {
            "lev": present(lev(l, r, settings["levenshtein_threshold"])),
            "eq": present(original_l == original_r),
            "sdx": present(F.soundex(l) == F.soundex(r)),
            "missing": (~both).cast("double"),
            "initials": present(initials(lt) == initials(rt)),
            "token_overlap": present(overlap),
            "accent_eq": present(F.collate(l, "UNICODE_CI_AI") == F.collate(r, "UNICODE_CI_AI")),
            "numeric_overlap": jaccard(numeric(lt), numeric(rt)),
            "legal_name_eq": present((F.length(legal(l)) > 0) & (F.length(legal(r)) > 0) & (legal(l) == legal(r))),
            "acronym_eq": present((initials(lt) == F.regexp_replace(r, " ", "")) |
                                   (initials(rt) == F.regexp_replace(l, " ", ""))),
            "prefix_eq": present(F.substring(l, 1, 3) == F.substring(r, 1, 3)),
            "suffix_eq": present(F.substring(l, -3, 3) == F.substring(r, -3, 3)),
            "length_ratio": present(F.least(F.length(l), F.length(r)) / F.greatest(F.length(l), F.length(r))),
        }
        if spec["type"] in {"date", "number"}:
            raw_l, raw_r = F.col(f"l_lm_raw_{name}"), F.col(f"r_lm_raw_{name}")
            if spec["type"] == "date":
                a, b = [F.try_to_timestamp(c, F.lit(spec.get("date_format", "yyyy-MM-dd"))).cast("date") for c in (raw_l, raw_r)]
                valid = a.isNotNull() & b.isNotNull()
                values.update({f"{part}_eq": F.when(valid, (func(a) == func(b)).cast("double")).otherwise(-1.0)
                               for part, func in (("year", F.year), ("month", F.month), ("day", F.dayofmonth))})
                values["date_proximity"] = F.when(valid, 1 / (1 + F.abs(F.datediff(a, b)))).otherwise(-1.0)
            else:
                a, b = raw_l.try_cast("double"), raw_r.try_cast("double")
                valid = a.isNotNull() & b.isNotNull() & ~F.isnan(a) & ~F.isnan(b) & (F.abs(a) < float("inf")) & (F.abs(b) < float("inf"))
                values["numeric_eq"] = F.when(valid, (a == b).cast("double")).otherwise(-1.0)
                scale = F.greatest(F.abs(a), F.abs(b), F.lit(1.0))
                values["relative_similarity"] = F.when(valid, F.greatest(F.lit(0.0), 1 - F.abs(a / scale - b / scale))).otherwise(-1.0)
                values["sign_eq"] = F.when(valid, (F.signum(a) == F.signum(b)).cast("double")).otherwise(-1.0)
            values["invalid"] = (~F.coalesce(valid, F.lit(False))).cast("double")
        if settings["string_similarity"] != "levenshtein":
            values["jw"] = F.udf(jaro_winkler, "double")(l, r)
        for metric in settings["multi_token"]:
            if metric == "gram_overlap":
                values[metric] = jaccard(grams(l, 3), grams(r, 3))
            elif metric == "monge_elkan_token":
                values[metric] = monge_elkan(lt, rt, settings["levenshtein_threshold"])
            elif metric == "idf_token_cosine":
                values[metric] = weighted_cosine(F.col(f"l_lm_weights_{name}"), F.col(f"r_lm_weights_{name}"))
            else:
                values[metric] = F.udf(affine_gap, "double")(l, r)
        if spec.get("multiple"):
            a, b = [F.slice(F.col(f"{side}_lm_values_{name}"), 1, settings["max_tokens"]) for side in ("l", "r")]
            values["value_overlap"] = jaccard(a, b)
            values["best_value_lev"] = F.coalesce(F.array_max(F.transform(a, lambda x:
                F.array_max(F.transform(b, lambda y: lev(F.substring(x, 1, settings["max_chars"]),
                    F.substring(y, 1, settings["max_chars"]), settings["levenshtein_threshold"]))))), F.lit(-1.0))
        if name in embedding_fields(config):
            a, b = F.col(f"l_lm_emb_{name}"), F.col(f"r_lm_emb_{name}")
            values["embedding_cosine"] = array_cosine(a, b)
            values["embedding_missing"] = (a.isNull() | b.isNull() | (F.size(a) == 0) | (F.size(b) == 0)).cast("double")
        expressions += [values[m].alias(f"{m}_{name}") for m in metrics_for(name, spec, config)]
    return joined.select("a_id", "b_id", "cos", "rank", "gap", *expressions)
