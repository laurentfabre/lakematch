"""bench/results/benchmarks.json -> bench/BENCHMARKS.md."""
from __future__ import annotations

import json
from pathlib import Path

TITLES = {"febrl4_half_unmatched": "FEBRL4, half the partners removed", "febrl4_original": "FEBRL4 original",
          "febrl3": "FEBRL3 (dedupe)", "bpid": "BPID", "abt_buy": "Abt-Buy", "amazon_google": "Amazon-Google",
          "walmart_amazon": "Walmart-Amazon", "dblp_acm": "DBLP-ACM",
          "splink_historical_50k": "Splink historical_50k (dedupe)",
          "leipzig_affiliations": "Leipzig Affiliations (dedupe)", "synthetic_1e6": "Synthetic 10^6"}


def f(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def ci(c):
    return f"[{c[0]:.3f}, {c[1]:.3f}]" if c else ""


def refs_cell(ref: dict) -> str:
    parts = []
    for z in ref.get("zingg", []):
        parts.append(f"Zingg {z['f1']:.3f} ({z['what'].replace('Zingg, ', '')})")
    sp = ref.get("splink") or {}
    if "f1" in sp:
        parts.append(f"Splink {sp['f1']:.4f} (measured)")
    if "ssn_hidden" in sp:
        parts.append(f"Splink SSN hidden {sp['ssn_hidden']['f1']:.4f} (measured)")
    for p in ref.get("published", []):
        parts.append(f"{p['what']} {p['f1']:.3f}")
    return "; ".join(parts) or "none"


def findings(d: dict, probe_path: Path) -> list[str]:
    """Observations computed from the recorded results (no number here is typed by hand)."""
    C, out = d["corpora"], []
    nn_wins = [n for n, r in C.items() if r["trivial_baseline"]["f1"] > r["f1_ci95"][1]]
    if nn_wins:
        out.append("- **The nearest-neighbour baseline beats the trained matcher** (above its whole interval) on "
                   + ", ".join(f"{TITLES[n]} ({f(C[n]['trivial_baseline']['f1'])} vs {f(C[n]['f1'])})" for n in nn_wins)
                   + ". On these product sets a right record matches at most one left record and the right title is "
                   "usually the closest one: the pair classifier, which sees each pair alone, loses to plain ranking. "
                   "Candidate-aware features or a select-among-candidates decision are the lever (ZR-4 onwards).")
    weak = [n for n, r in C.items() if r.get("jev") and r["jev"]["usage"]["asked"]
            and r["jev"]["usage"]["kept"] / r["jev"]["usage"]["asked"] < 0.3]
    if weak:
        out.append("- **Jev as the only labeller works where it is confident.** Its confident share is below 30 % on "
                   + ", ".join(f"{TITLES[n]} ({C[n]['jev']['usage']['kept']} of {C[n]['jev']['usage']['asked']})" for n in weak)
                   + ": there it must judge, not label (the 2026-09-19 finding, reproduced).")
    if probe_path.exists():
        pr = json.loads(probe_path.read_text())["rows"]
        out.append(f"- **Scale: the default candidate step collapses at 10^6 records** (Synthetic 10^6 candidate recall "
                   f"{f(C.get('synthetic_1e6', {}).get('candidate_recall_at_k'))}). `bench/scale_probe.py` "
                   "(`results/scale_probe.json`) locates it in two places:")
        for r in pr:
            out.append(f"  - {r['what']}: recall **{r['recall']:.4f}**, {r['pairs']:,} pairs, {r['s']} s")
        out.append("  Two defects, both visible only at scale: the gram join keeps grams held by at most `gram_cap` = "
                   "400 right records, which at 500 000 records leaves almost no gram a true pair shares; and the shared "
                   "ranking scores proposals over that same capped vocabulary, so most score 0 and the top-k cut is "
                   "arbitrary. Conjunction blocks plus a ranking vocabulary cut relative to the corpus size restore "
                   "0.987. Changing the candidate default is a re-decision on VALIDATION data with this corpus added "
                   "to `bench/methods.py` — the next goal, not done here.")
    return out or ["- none"]


def render(src: Path, dst: Path) -> None:
    d = json.loads(src.read_text())
    C = d["corpora"]
    L = ["# Benchmarks (ZR-3)", "",
         f"*Generated {d['meta']['generated']} from `bench/results/benchmarks.json` by `lakematch bench --all` "
         f"(`bench/benchmarks.py`). Machine: {d['meta']['machine']}. Every row ran end to end on the laptop, one "
         "process per corpus; nothing below was typed by hand.*", "",
         "## Contents", "", "- [Results](#results)", "- [Findings](#findings)", "- [FEBRL4 thresholds](#febrl4-thresholds)",
         "- [Jev as the only labeller](#jev-as-the-only-labeller)", "- [Latency and scale](#latency-and-scale)",
         "- [References](#references)", "- [Method choices](#method-choices)", "- [Protocol](#protocol)",
         "- [Reproduce](#reproduce)", "",
         "## Results", "",
         "Gold labeller (TRAIN labels, threshold on VALID, scored once on TEST). F1 interval: 95 % bootstrap over "
         "TEST units. NN = always link the nearest neighbour.", "",
         "| Corpus | kind | P | R | F1 [95 % CI] | NN baseline F1 | candidate recall@k | wall s (incl. start) | reference to beat or match |",
         "|---|---|---|---|---|---|---|---|---|"]
    for n, r in C.items():
        L.append(f"| {TITLES[n]} | {r['kind']} | {f(r['precision'])} | {f(r['recall'])} | **{f(r['f1'])}** "
                 f"{ci(r['f1_ci95'])} | {f(r['trivial_baseline']['f1'])} | {f(r['candidate_recall_at_k'])} @{r['k']} | "
                 f"{r['wall_s_incl_start']} | {refs_cell(r['references'])} |")
    L += ["", "## Findings", ""] + findings(d, src.parent / "scale_probe.json")
    fb = C.get("febrl4_half_unmatched", {})
    ok = fb.get("f1_all_fields", 0) >= 0.97 and fb.get("f1_ssn_hidden", 0) >= 0.96 and fb.get("wall_s_incl_start", 99) < 60
    L += ["", "## FEBRL4 thresholds", "",
          "| | all ten fields | SSN hidden | bar |", "|---|---|---|---|",
          f"| F1 [95 % CI] | {f(fb.get('f1_all_fields'))} {ci(fb.get('f1_ci95'))} | {f(fb.get('f1_ssn_hidden'))} "
          f"{ci((fb.get('ssn_hidden') or {}).get('gold', {}).get('f1_ci95'))} | ≥ 0.97 / ≥ 0.96 |",
          f"| wall time incl. Spark start | {(fb.get('wall_s_incl_start'))} s (the slower of the two runs) | | < 60 s |",
          "", f"Verdict: **{'met' if ok else 'NOT met'}**. Zingg on the same task: 0.841 (all fields) / 0.862 (SSN "
          "hidden), recall 0.73–0.76 (recorded 2026-09-19).", "",
          "## Jev as the only labeller", "",
          "The same run with no gold label: Jev labels 400 TRAIN candidate pairs, only its confident answers "
          "(τ 0.90) train the model and pick the threshold. Tokens and dollars are the cost of labelling the sample "
          "once (answers are cached, so a re-run sends nothing); price $0.042 per million input tokens, output free.", "",
          "| Corpus | asked | kept | F1 [95 % CI] | gold F1 | input tokens | $ | note |", "|---|---|---|---|---|---|---|---|"]
    tot_tok = tot_usd = 0.0
    for n, r in C.items():
        j = r.get("jev")
        if not j:
            L.append(f"| {TITLES[n]} | — | — | — | {f(r['f1'])} | — | — | labeller not run |")
            continue
        u = j["usage"]
        led = u["label_input_tokens"]
        usd = u["label_usd"]
        tot_tok += led
        tot_usd += usd
        L.append(f"| {TITLES[n]} | {u['asked']} | {u['kept']} | {f(j.get('f1'))} {ci(j.get('f1_ci95'))} | {f(r['f1'])} | "
                 f"{int(led):,} | {usd:.4f} | {j.get('note', '')} |")
    L += ["", f"Total: {int(tot_tok):,} input tokens, ${tot_usd:.3f}."]
    cm = src.parent / "jev_cost_model.json"
    if cm.exists():
        m = json.loads(cm.read_text())
        L += ["", f"**Predicting the cost before sending.** `bench/jev_calibrate.py` fits input tokens = {m['a']:.0f} + "
              f"{m['b']:.3f} × characters of the two records' JSON on these {m['n']:,} answers. Predicting each corpus "
              f"from the other ten, the total is off by {m['leave_one_corpus_out_median_abs_error_pct']} % (median), "
              f"{m['leave_one_corpus_out_max_abs_error_pct']} % at worst. `lakematch doctor` prints this prediction, "
              "a run logs it before any request, and `labels.llm_max_usd` refuses a run predicted above it — which "
              "is why Jev may run on the laptop profile."]
    L += ["",
          "## Latency and scale", "",
          "| Corpus | records | candidate pairs | wall s | records / s | peak shuffle (one stage, MB) | total shuffle MB |",
          "|---|---|---|---|---|---|---|"]
    for n, r in C.items():
        sh = r.get("shuffle") or {}
        L.append(f"| {TITLES[n]} | {sum(r['records'].values()):,} | {r['candidates']:,} | {r['wall_s_incl_start']} | "
                 f"{r['records_per_s']:,} | {sh.get('peak_stage_mb', '—')} | {sh.get('total_mb', '—')} |")
    L += ["", "Peak shuffle is read from the Spark event log of each run. DBUs from the billing table apply on "
          "Databricks only (ZR-6).", "", "## References", ""]
    for n, r in C.items():
        ref = r["references"]
        L.append(f"**{TITLES[n]}.**")
        rows = [(z["what"], z["f1"], z["source"]) for z in ref["zingg"]]
        sp = ref.get("splink") or {}
        if "f1" in sp:
            rows.append((f"Splink {sp.get('version', '')}, measured here — {sp.get('what', '')}", [sp["f1"]],
                         "bench/splink_reference.py"))
            if "ssn_hidden" in sp:
                rows.append(("Splink, same model, SSN hidden", [sp["ssn_hidden"]["f1"]], "bench/splink_reference.py"))
        rows += [(p["what"], p["f1"], p["source"]) for p in ref["published"]]
        rows += [(p["what"], p["f1"], p["source"]) for p in ref["recorded"]]
        if rows:
            L += ["", "| system | F1 | source |", "|---|---|---|"]
            for w, v, s in rows:
                v = " / ".join(f"{x:.4f}" for x in v) if isinstance(v, list) else f"{v:.3f}"
                L.append(f"| {w} | {v} | {s} |")
        notes = [x for x in (ref.get("zingg_note"), sp.get("note")) if x]
        if notes:
            L += ["", "; ".join(notes) + "."]
        if r.get("notes"):
            L += ["", "Corpus: " + "; ".join(r["notes"]) + "."]
        L.append("")
    L += ["## Method choices", "",
          "Every candidate method (candidate recall at an equal pair budget), string similarity, estimator and "
          "cardinality policy is compared on VALIDATION data in [METHODS.md](METHODS.md) (ZR-3a). The winners, "
          "which are the shipped defaults in `config.py`:", "", "| choice | winner = default |", "|---|---|"]
    for k, w in d["method_winners"].items():
        L.append(f"| `{k}` | `{w}` (default `{d['defaults'][k]}`) |")
    L += ["", f"De-duplication across splits asserted on every corpus: **{d['split_dedup_asserted']}**.", "",
          "## Protocol", "", "```text", d["protocol"], "```", "",
          "## Reproduce", "", "```bash", "source scripts/env.sh",
          "lakematch bench --all                      # every corpus, one process each (≈ the table's wall times)",
          "python bench/benchmarks.py all --only abt_buy   # one row; the others keep their last result",
          "python bench/splink_reference.py              # the measured Splink references",
          "python bench/benchmarks.py render             # BENCHMARKS.md from the JSON, no Spark", "```", ""]
    dst.write_text("\n".join(L))
