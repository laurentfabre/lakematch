"""References for BENCHMARKS.md: published figures, the Zingg runs recorded on 2026-09-19 and earlier measurements.

Every figure names its source. "Recorded" figures come from ~/Projects/Personal/Lake/mdm/bench/README.md (measured
2026-09-19, reviewed by Codex on gpt-6-astra): they are copied here, never re-run — Zingg is not a dependency of
lakematch or of this harness. Splink figures are measured by bench/splink_reference.py (bench/results/splink.json).
Published figures use other splits and selection protocols: they are indicative, not a like-for-like comparison.
F1 is on a 0..1 scale everywhere.
"""
from __future__ import annotations

LAKE_BENCH = "Lake/mdm/bench/README.md (recorded 2026-09-19)"
MUDGAL = "Mudgal et al., SIGMOD 2018 (Magellan, DeepMatcher)"
DITTO = "Li et al., VLDB 2021 (Ditto)"
PEETERS = "Peeters, Steiner & Bizer, EDBT 2025 (GPT-4, best of 10 prompts, downsampled test)"

STATIC: dict[str, dict[str, list[dict]]] = {
    "febrl4_half_unmatched": {
        "zingg": [{"what": "Zingg, perfect labels, all fields", "f1": 0.841, "precision": 1.000, "recall": 0.726, "source": LAKE_BENCH},
                  {"what": "Zingg, perfect labels, SSN hidden", "f1": 0.862, "precision": 0.999, "recall": 0.758, "source": LAKE_BENCH},
                  {"what": "Zingg, labels from Jev", "f1": 0.849, "precision": 1.000, "recall": 0.738, "source": LAKE_BENCH}],
        "published": [],
        "recorded": [{"what": "prototype: classifier on Jev labels, all fields / SSN hidden", "f1": [0.9748, 0.9356], "source": LAKE_BENCH},
                     {"what": "prototype + Jev arbitrates, all fields / SSN hidden", "f1": [0.9944, 0.9637], "source": LAKE_BENCH}],
    },
    "febrl4_original": {
        "zingg": [{"what": "Zingg, labels from Jev (6 rounds)", "f1": 0.853, "precision": 1.000, "recall": 0.744, "source": LAKE_BENCH},
                  {"what": "Zingg, ground-truth labels (6 rounds)", "f1": 0.858, "precision": 1.000, "recall": 0.751, "source": LAKE_BENCH}],
        "published": [],
        "recorded": [{"what": "nearest neighbour, always link", "f1": 1.0000, "source": LAKE_BENCH},
                     {"what": "top-k candidates + classifier on Jev labels", "f1": 0.9992, "source": LAKE_BENCH}],
    },
    "febrl3": {
        "zingg": [],
        "published": [{"what": "Splink on Febrl (blog figure, unverified)", "f1": 0.998, "source": "Splink blog, cited in the brief"}],
        "recorded": [],
    },
    "bpid": {
        "zingg": [],
        "published": [{"what": "Sudowoodo (best published)", "f1": 0.788, "source": "BPID, EMNLP 2024 Industry"},
                      {"what": "Ditto", "f1": 0.752, "source": "BPID, EMNLP 2024 Industry"},
                      {"what": "Llama3-70B zero-shot", "f1": 0.729, "source": "BPID, EMNLP 2024 Industry"},
                      {"what": "GPT-4-turbo zero-shot", "f1": 0.687, "source": "BPID, EMNLP 2024 Industry"},
                      {"what": "rules", "f1": 0.608, "source": "BPID, EMNLP 2024 Industry"}],
        "recorded": [{"what": "Jev zero-shot (own 70/10/20 split)", "f1": 0.813, "source": LAKE_BENCH},
                     {"what": "classical, 7 000 gold labels (own split)", "f1": 0.749, "source": LAKE_BENCH}],
    },
    "abt_buy": {
        "zingg": [],
        "published": [{"what": "Magellan (Zingg-class)", "f1": 0.436, "source": MUDGAL},
                      {"what": "DeepMatcher", "f1": 0.628, "source": MUDGAL},
                      {"what": "Ditto", "f1": 0.893, "source": DITTO},
                      {"what": "GPT-4 zero-shot", "f1": 0.958, "source": PEETERS}],
        "recorded": [{"what": "classifier (scikit-learn)", "f1": 0.768, "source": LAKE_BENCH},
                     {"what": "Jev zero-shot", "f1": 0.930, "source": LAKE_BENCH}],
    },
    "amazon_google": {
        "zingg": [],
        "published": [{"what": "Magellan (Zingg-class)", "f1": 0.491, "source": MUDGAL},
                      {"what": "DeepMatcher", "f1": 0.693, "source": MUDGAL},
                      {"what": "Ditto", "f1": 0.756, "source": DITTO},
                      {"what": "GPT-4 zero-shot", "f1": 0.764, "source": PEETERS}],
        "recorded": [{"what": "classifier (scikit-learn)", "f1": 0.684, "source": LAKE_BENCH},
                     {"what": "Jev zero-shot", "f1": 0.705, "source": LAKE_BENCH}],
    },
    "walmart_amazon": {
        "zingg": [],
        "published": [{"what": "Magellan (Zingg-class)", "f1": 0.719, "source": MUDGAL},
                      {"what": "DeepMatcher", "f1": 0.676, "source": MUDGAL},
                      {"what": "Ditto", "f1": 0.868, "source": DITTO},
                      {"what": "GPT-4 zero-shot", "f1": 0.897, "source": PEETERS}],
        "recorded": [{"what": "classifier (scikit-learn)", "f1": 0.831, "source": LAKE_BENCH},
                     {"what": "Jev zero-shot", "f1": 0.916, "source": LAKE_BENCH}],
    },
    "dblp_acm": {
        "zingg": [],
        "published": [{"what": "Magellan (Zingg-class)", "f1": 0.984, "source": MUDGAL},
                      {"what": "Ditto", "f1": 0.990, "source": DITTO}],
        "recorded": [],
    },
    "splink_historical_50k": {"zingg": [], "published": [], "recorded": []},
    "leipzig_affiliations": {
        "zingg": [],
        "published": [{"what": "Dedupe classifier + F-MWSP clustering (whole dataset)", "f1": 0.63,
                       "source": "Lokhande et al., arXiv 1909.05460 (2019); a hand-written rule classifier "
                                 "(Aumueller & Rahm, ICIQ 2009) is reported higher, figure not extracted"}],
        "recorded": [],
    },
    "synthetic_1e6": {"zingg": [], "published": [], "recorded": []},
}

NO_ZINGG = "not run: Zingg figures exist only for FEBRL4 (recorded 2026-09-19); Zingg is never a dependency here"


def for_corpus(name: str, splink: dict | None) -> dict:
    ref = {k: list(v) for k, v in STATIC[name].items()}
    ref["zingg_note"] = None if ref["zingg"] else NO_ZINGG
    ref["splink"] = splink or {"note": "not measured on this corpus (bench/splink_reference.py covers the person "
                                       "corpora with a Splink demo-style model)"}
    return ref
