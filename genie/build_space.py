#!/usr/bin/env python3
"""ZR-8: build the serialized_space payload for the lakematch Genie Agent.

Binds the stable 'all'-fixture gold serving set (source inputs, scored
candidate pairs, accepted links) over gdpr2_catalog.lakematch_20260919 and
encodes descriptions, synonyms, joins, SQL expressions, sample questions,
example SQL and benchmarks in one version-2 serialized_space.
"""
import json
import uuid

CAT = "gdpr2_catalog.lakematch_20260919"


def nid() -> str:
    return uuid.uuid4().hex


# ---- input record columns (shared left/right schema) --------------------
INPUT_COLS = {
    "rec_id": (["Record identifier of a source record. Join key: matches a_id "
                "(left) or b_id (right) in lm_scores_all / lm_links_all."],
               ["record id", "id", "record key"]),
    "given_name": (["First / given name of the person on this record."],
                   ["first name", "forename"]),
    "surname": (["Family name / last name."], ["last name", "family name"]),
    "date_of_birth": (["Date of birth (string, YYYYMMDD-style synthetic FEBRL value)."],
                      ["dob", "birth date", "birthdate"]),
    "suburb": (["Suburb / locality of the address."], ["locality", "town"]),
    "postcode": (["Postal code of the address."], ["zip", "zip code", "postal code"]),
    "state": (["State / region code of the address."], ["region", "province"]),
    "soc_sec_id": (["Synthetic social-security identifier (FEBRL fixture, not real PII)."],
                   ["ssn", "social security", "national id"]),
}
# address_1/2, street_number are context; keep visible but undescribed.


def input_configs():
    cfgs = []
    for col, (desc, syn) in INPUT_COLS.items():
        c = {"column_name": col, "description": desc, "synonyms": syn}
        # entity matching only on stable low-cardinality strings users name
        if col in ("state",):
            c["enable_format_assistance"] = True
            c["enable_entity_matching"] = True
        cfgs.append(c)
    return sorted(cfgs, key=lambda x: x["column_name"])


# ---- scores columns: keep the 6 meaningful, hide raw features -----------
SCORES_KEEP = {
    "a_id": (["Left record id of the candidate pair. Joins lm_input_all_left.rec_id."],
             ["left id", "a"]),
    "b_id": (["Right record id of the candidate pair. Joins lm_input_all_right.rec_id."],
             ["right id", "b"]),
    "cos": (["Raw blocking cosine similarity of the pair (higher = more similar). "
             "NOT a probability — use p for match likelihood."],
            ["cosine", "similarity", "cos similarity"]),
    "rank": (["Rank of this candidate among a record's blocked candidates (1 = closest)."],
             ["candidate rank", "position"]),
    "gap": (["Score gap to the next-best candidate; a large gap indicates a confident top match."],
            ["margin", "score gap"]),
    "p": (["Model match probability for the pair, 0..1 (GBT classifier output)."],
          ["match probability", "probability", "score"]),
}
SCORES_ALL = "a_id,b_id,cos,rank,gap,lev_given_name,eq_given_name,sdx_given_name,missing_given_name,initials_given_name,token_overlap_given_name,accent_eq_given_name,idf_token_cosine_given_name,lev_surname,eq_surname,sdx_surname,missing_surname,initials_surname,token_overlap_surname,accent_eq_surname,idf_token_cosine_surname,lev_street_number,eq_street_number,sdx_street_number,missing_street_number,prefix_eq_street_number,suffix_eq_street_number,length_ratio_street_number,idf_token_cosine_street_number,lev_address_1,eq_address_1,sdx_address_1,missing_address_1,numeric_overlap_address_1,token_overlap_address_1,idf_token_cosine_address_1,lev_address_2,eq_address_2,sdx_address_2,missing_address_2,numeric_overlap_address_2,token_overlap_address_2,idf_token_cosine_address_2,lev_suburb,eq_suburb,sdx_suburb,missing_suburb,numeric_overlap_suburb,token_overlap_suburb,idf_token_cosine_suburb,lev_postcode,eq_postcode,sdx_postcode,missing_postcode,prefix_eq_postcode,suffix_eq_postcode,length_ratio_postcode,idf_token_cosine_postcode,lev_state,eq_state,sdx_state,missing_state,prefix_eq_state,suffix_eq_state,length_ratio_state,idf_token_cosine_state,lev_date_of_birth,eq_date_of_birth,sdx_date_of_birth,missing_date_of_birth,year_eq_date_of_birth,month_eq_date_of_birth,day_eq_date_of_birth,date_proximity_date_of_birth,invalid_date_of_birth,idf_token_cosine_date_of_birth,lev_soc_sec_id,eq_soc_sec_id,sdx_soc_sec_id,missing_soc_sec_id,prefix_eq_soc_sec_id,suffix_eq_soc_sec_id,length_ratio_soc_sec_id,idf_token_cosine_soc_sec_id,p".split(",")


def scores_configs():
    cfgs = []
    for col in SCORES_ALL:
        if col in SCORES_KEEP:
            desc, syn = SCORES_KEEP[col]
            cfgs.append({"column_name": col, "description": desc, "synonyms": syn})
        else:
            cfgs.append({"column_name": col, "exclude": True})  # hide raw feature
    return sorted(cfgs, key=lambda x: x["column_name"])


LINKS_CFG = sorted([
    {"column_name": "a_id", "description": ["Left record id of the accepted match. Joins lm_input_all_left.rec_id."], "synonyms": ["left id"]},
    {"column_name": "b_id", "description": ["Right record id of the accepted match. Joins lm_input_all_right.rec_id."], "synonyms": ["right id"]},
    {"column_name": "p", "description": ["Match probability of the accepted link, 0..1."], "synonyms": ["match probability", "confidence", "score"]},
], key=lambda x: x["column_name"])


tables = sorted([
    {"identifier": f"{CAT}.lm_input_all_left", "column_configs": input_configs()},
    {"identifier": f"{CAT}.lm_input_all_right", "column_configs": input_configs()},
    {"identifier": f"{CAT}.lm_scores_all", "column_configs": scores_configs()},
    {"identifier": f"{CAT}.lm_links_all", "column_configs": LINKS_CFG},
], key=lambda t: t["identifier"])


sample_qs = [
    "How many source records are on each side (left vs right)?",
    "How many accepted matches (links) are there?",
    "What is the average match probability across all links?",
    "Show the 10 highest-probability matches with their record IDs.",
    "How many candidate pairs were scored, and what share became links?",
    "Show the distribution of link match probability in 0.1-wide buckets.",
    "For a given left record id, which right record did it match and with what probability?",
    "Which candidate pairs have high cosine similarity but were not linked?",
    "Compare average cosine and gap for linked vs non-linked candidate pairs.",
    "How many distinct left records appear in at least one accepted link?",
]
config = {"sample_questions": sorted(
    [{"id": nid(), "question": [q]} for q in sample_qs], key=lambda x: x["id"])}


example_sqls = [
    ("How many source records are on each side?",
     f"SELECT 'left' AS side, COUNT(*) AS n FROM {CAT}.lm_input_all_left "
     f"UNION ALL SELECT 'right', COUNT(*) FROM {CAT}.lm_input_all_right"),
    ("What is the average match probability across all links?",
     f"SELECT ROUND(AVG(lm_links_all.p), 4) AS avg_p, COUNT(*) AS links FROM {CAT}.lm_links_all AS lm_links_all"),
    ("Show the 10 highest-probability matches with record IDs.",
     f"SELECT lm_links_all.a_id, lm_links_all.b_id, lm_links_all.p FROM {CAT}.lm_links_all AS lm_links_all ORDER BY lm_links_all.p DESC LIMIT 10"),
    ("What share of scored candidate pairs became links?",
     f"SELECT (SELECT COUNT(*) FROM {CAT}.lm_links_all) AS links, "
     f"COUNT(*) AS scored, ROUND((SELECT COUNT(*) FROM {CAT}.lm_links_all) * 100.0 / COUNT(*), 2) AS link_pct "
     f"FROM {CAT}.lm_scores_all AS lm_scores_all"),
    ("Distribution of link match probability in 0.1 buckets.",
     f"SELECT FLOOR(lm_links_all.p * 10) / 10 AS p_bucket, COUNT(*) AS n FROM {CAT}.lm_links_all AS lm_links_all GROUP BY 1 ORDER BY 1"),
    ("High-cosine candidate pairs that were not linked.",
     f"SELECT lm_scores_all.a_id, lm_scores_all.b_id, lm_scores_all.cos, lm_scores_all.p "
     f"FROM {CAT}.lm_scores_all AS lm_scores_all "
     f"LEFT JOIN {CAT}.lm_links_all AS lm_links_all "
     f"ON lm_scores_all.a_id = lm_links_all.a_id AND lm_scores_all.b_id = lm_links_all.b_id "
     f"WHERE lm_links_all.a_id IS NULL AND lm_scores_all.cos >= 0.8 ORDER BY lm_scores_all.cos DESC LIMIT 50"),
]
example_question_sqls = sorted(
    [{"id": nid(), "question": [q], "sql": [s]} for q, s in example_sqls],
    key=lambda x: x["id"])


join_specs = sorted([
    {"id": nid(),
     "left": {"identifier": f"{CAT}.lm_scores_all", "alias": "lm_scores_all"},
     "right": {"identifier": f"{CAT}.lm_links_all", "alias": "lm_links_all"},
     "sql": ["`lm_scores_all`.`a_id` = `lm_links_all`.`a_id` AND `lm_scores_all`.`b_id` = `lm_links_all`.`b_id`",
             "--rt=FROM_RELATIONSHIP_TYPE_ONE_TO_ONE--"]},
    {"id": nid(),
     "left": {"identifier": f"{CAT}.lm_links_all", "alias": "lm_links_all"},
     "right": {"identifier": f"{CAT}.lm_input_all_left", "alias": "lm_input_all_left"},
     "sql": ["`lm_links_all`.`a_id` = `lm_input_all_left`.`rec_id`",
             "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_ONE--"]},
    {"id": nid(),
     "left": {"identifier": f"{CAT}.lm_links_all", "alias": "lm_links_all"},
     "right": {"identifier": f"{CAT}.lm_input_all_right", "alias": "lm_input_all_right"},
     "sql": ["`lm_links_all`.`b_id` = `lm_input_all_right`.`rec_id`",
             "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_ONE--"]},
], key=lambda x: x["id"])


sql_snippets = {
    "measures": sorted([
        {"id": nid(), "alias": "link_count", "display_name": "Number of links",
         "sql": ["COUNT(lm_links_all.a_id)"], "synonyms": ["matches", "accepted matches"]},
        {"id": nid(), "alias": "avg_match_probability", "display_name": "Average match probability",
         "sql": ["AVG(lm_links_all.p)"], "synonyms": ["avg p", "mean probability"]},
        {"id": nid(), "alias": "scored_pairs", "display_name": "Scored candidate pairs",
         "sql": ["COUNT(lm_scores_all.a_id)"], "synonyms": ["candidates", "scored pairs"]},
    ], key=lambda x: x["id"]),
    "filters": sorted([
        {"id": nid(), "display_name": "High-confidence links",
         "sql": ["lm_links_all.p >= 0.9"], "synonyms": ["confident matches", "strong matches"]},
    ], key=lambda x: x["id"]),
    "expressions": sorted([
        {"id": nid(), "alias": "probability_bucket", "display_name": "Probability bucket",
         "sql": ["FLOOR(lm_links_all.p * 10) / 10"]},
    ], key=lambda x: x["id"]),
}

text_instructions = [{"id": nid(), "content": [
    "## PURPOSE",
    "- Answer questions about the lakematch entity-resolution benchmark: source records, scored candidate pairs, and accepted matches over gdpr2_catalog.lakematch_20260919 (synthetic FEBRL4 fixture, no real PII).",
    "- Users are data/ML engineers reviewing match quality.",
    "",
    "## DISAMBIGUATION",
    "- A 'match', 'link', or 'accepted pair' means a row in lm_links_all. A 'candidate' or 'scored pair' means a row in lm_scores_all.",
    "- 'probability' / 'confidence' is lm_links_all.p or lm_scores_all.p (0..1). 'cosine' / 'similarity' is lm_scores_all.cos and is NOT a probability.",
    "- a_id joins to lm_input_all_left.rec_id; b_id joins to lm_input_all_right.rec_id.",
    "",
    "## DATA QUALITY NOTES",
    "- lm_scores_all has one row per candidate pair; a pair is linked only if it also appears in lm_links_all (left join on a_id AND b_id).",
    "",
    "## CONSTRAINTS",
    "- soc_sec_id is a synthetic FEBRL identifier, not real PII; do not treat it as sensitive but note it is fixture data.",
    "",
    "## Instructions you must follow when providing summaries",
    "- Round probabilities and rates to at most 4 decimal places.",
    "- When reporting a link/match rate, state both the numerator (links) and denominator (scored pairs).",
]}]


benchmarks = {"questions": sorted([
    {"id": nid(), "question": ["How many accepted matches (links) are there?"],
     "answer": [{"format": "SQL", "content": [f"SELECT COUNT(*) AS n FROM {CAT}.lm_links_all"]}]},
    {"id": nid(), "question": ["What is the average match probability across all links?"],
     "answer": [{"format": "SQL", "content": [f"SELECT ROUND(AVG(p), 4) AS avg_p FROM {CAT}.lm_links_all"]}]},
    {"id": nid(), "question": ["How many candidate pairs were scored?"],
     "answer": [{"format": "SQL", "content": [f"SELECT COUNT(*) AS n FROM {CAT}.lm_scores_all"]}]},
], key=lambda x: x["id"])}


serialized = {
    "version": 2,
    "config": config,
    "data_sources": {"tables": tables},
    "instructions": {
        "example_question_sqls": example_question_sqls,
        "text_instructions": text_instructions,
        "join_specs": join_specs,
        "sql_snippets": sql_snippets,
    },
    "benchmarks": benchmarks,
}

with open("genie/serialized_space.json", "w") as f:
    json.dump(serialized, f, indent=2)
print("wrote genie/serialized_space.json  bytes=", len(json.dumps(serialized)))
print("tables:", [t["identifier"].split(".")[-1] for t in tables])
print("sample_qs:", len(config["sample_questions"]), "examples:", len(example_question_sqls),
      "joins:", len(join_specs), "benchmarks:", len(benchmarks["questions"]))
