"""Render the SIM-3 report exclusively from measured, auditable results."""
from __future__ import annotations

from pathlib import Path
import shlex


def render_report(d):
    corpora = ("febrl4_half_unmatched", "bpid", "abt_buy", "leipzig_affiliations")
    headings = ("FEBRL4", "BPID", "Abt-Buy", "Leipzig")
    avg = lambda per: sum(per[c]["f1"] for c in corpora) / 4
    interval = lambda r: f"{r['f1']:.4f} [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]"
    if d['meta']['manifest']['protocol'] == 'simbeat-v2':
        work = Path(d['meta']['work_dir'])
        args = f"--work-dir {shlex.quote(str(work))} --result {shlex.quote(str(work / 'result.json'))}"
        reproduce = ["```bash", f"cd {shlex.quote(str(Path(__file__).resolve().parent.parent))}",
                     "source scripts/env.sh", f"python bench/simbeat.py run --work-dir {shlex.quote(str(work))}",
                     f"python bench/simbeat.py audit {args}", f"python bench/simbeat.py render {args}", "```", "",
                     "Completed runs verify their saved evidence without new inference. Fresh v2 execution requires "
                     "explicitly provisioned separated inputs and a new work directory; see `spec/SIMBEAT_PROTOCOL.md` "
                     "in the source checkout. This run's result, selection and metrics are in [result.json](result.json). "
                     "Prepared data, models, physical plans, releases and predictions are retained alongside this report. "
                     "The default historical phase-3 shell gate checks the canonical v1 result; the explicit audit command "
                     "above checks this v2 run.", ""]
    else:
        reproduce = ["```bash", "cd ~/Projects/Pro/lakematch", "source scripts/env.sh",
            "python bench/simbeat.py run", "python bench/simbeat.py audit", "python bench/simbeat.py render",
            "cd ~/Projects/Personal", "bash goals/verify_simbeat.sh 3", "```", "",
            "`run` needs the cached corpora and embedding model and makes no download requests. It resumes only an "
            "identical source/data/config/version manifest. For an independent complete rerun, use a fresh "
            "`--work-dir data/runs/simbeat-reproduction`; do not use repeated TEST runs to revise the choice. "
            "Results, per-unit confusion counts, thresholds, feature columns, plan hashes, input hashes, model hashes "
            "and the selection lock are in [results/simbeat.json](results/simbeat.json). Local feature Parquet, model "
            "directories, physical plan text and prediction evidence remain under `data/runs/simbeat/` (gitignored). "
            "The audit recomputes greedy choices, stopping, F1, intervals, paired TEST difference and verdict. "
            "The shell judge independently recomputes the four verdict conditions.", ""]
    out = ["# String similarity benchmark — SIM-3", "", "## What / why", "",
           "Compare seven shortlisted Spark SQL feature families with Levenshtein and the Jaro–Winkler UDF, "
           "keeping the rest of the matching pipeline fixed. Select on VALID, then confirm the frozen choice once on TEST.", "",
           f"> Verdict: **`{d['verdict']}`**. Chosen additions: **{', '.join(d['chosen_families']) or 'none'}**. "
           "This is a benchmark-specific result, not a universal ranking of string measures.", "",
           "## Contents", "", "- [Protocol](#protocol)", "- [Validation](#validation)",
           "- [Forward selection](#forward-selection)", "- [TEST confirmation](#test-confirmation)",
           "- [Verdict](#verdict)", "- [Reproduce and audit](#reproduce-and-audit)",
           "- [Limitations](#limitations)", "- [License](#license)", "", "---", "", "## Protocol", "",
           "| Setting | Frozen choice |", "|---|---|",
           "| Candidate generation | Existing `gram_topk`; k=5 for FEBRL4, k=11 then remove self and canonicalize for Leipzig |",
           "| Pair corpora | BPID and Abt-Buy retain their fixed loader splits and supplied labelled pairs |",
           "| Model | Spark MLlib GBT, 60 iterations, depth 3, seed 0; same existing non-edit families in every variant |",
           "| Fit / calibration | 80/20 of TRAIN by hash; thresholds maximize pair F1 on calibration, grid 0.05–0.95 step 0.01 |",
           "| Outer split | FEBRL4 left-ID hash 60/20/20; Leipzig canonical pair hash 60/20/20 |",
           "| Selection | Greedy forward addition by strictly positive, unrounded mean VALID F1 gain; shortlist rank breaks ties |",
           "| Confirmation | Saved chosen and JW models and thresholds, no refit; selection JSON locked before TEST scoring |",
           "| Intervals | 1,000 percentile bootstrap replicates; pair units except FEBRL4 left-record units |",
           "| TEST difference | Paired resampling within each corpus, then equal-weight mean of four corpus F1 differences |",
           "| Record features | Default cached local embedding model and transductive IDF; record UDFs pinned before pair comparison |",
           "| New-feature limits | 512 characters, 128 distinct tokens; checked on normalized inputs; no truncation |",
           "| Existing Monge–Elkan | Original 30-token cap retained |", "",
           "**Corrections to the historical `methods.py` measurements.** The old linkage fit/calibration hash was "
           "correlated with the outer hash, producing approximately 5/6 versus 1/6 within TRAIN. This run uses an "
           "independently salted inner hash for FEBRL4 and Leipzig. Leipzig now uses the documented pair hash. "
           "Canonical candidate orientation is deterministic. Jaro–Winkler now covers every field that receives "
           "Levenshtein, including Abt-Buy titles: the old JW-only Abt-Buy row contained no JW features. "
           "All three baselines are remeasured here; historical scores are not directly comparable.", "",
           "FEBRL4 applies the existing greedy one-to-one decision and counts truth links missed by blocking; its "
           "evaluation units include every held-out left record, even without candidates. BPID, Abt-Buy and Leipzig "
           "use unrestricted pair classification, matching the actual ZR-3a similarity evaluation. The old harness's "
           "prose suggesting one-to-one Abt-Buy scoring did not describe that implementation. Leipzig F1 is conditional "
           "on its candidate pairs; it is not cluster F1 or full all-pairs recall.", "",
           ("Explicit provisioning separates public records, development labels and sealed TEST outcomes. "
            "Development reads only the public bundle; confirmation releases outcomes after validating the frozen "
            "selection and models. Saved releases and predictions are reused on resume."
            if d['meta']['manifest']['protocol'] == 'simbeat-v2' else
            "TEST files and all record strings are parsed by the existing loaders during preprocessing. No TEST score "
            "or label-driven statistic is used for selection. TEST comparison vectors and predictions are evaluated "
            "only after the selection lock. The saved confirmation is reused on resume."), "",
           "### Development split counts", "", "| Corpus | Fit pairs / positives | Calibration pairs / positives | VALID pairs / positives |",
           "|---|---:|---:|---:|"]
    for c in corpora:
        counts = d['prepared'][c]['counts']
        out.append("| " + c + " | " + " | ".join(f"{counts[p]['pairs']} / {counts[p]['positives']}" for p in ('fit','thr','valid')) + " |")
    out += ["", "---", "", "## Validation", "", "F1 [95% percentile interval]. Means and selection use full precision in the JSON. Field eligibility follows SIM-2: a family with no applicable fields repeats the baseline (for example, OSA on Leipzig organisation fields).", "",
            "| Variant | " + " | ".join(headings) + " | Mean | Pair plan UDF-free |",
            "|---|" + "---:|" * 5 + "---|"]
    singles = ['levenshtein','jaro_winkler','both'] + ['levenshtein + ' + f for f in d['meta']['manifest']['shortlist']] + ['chosen']
    def row(name):
        per = d['valid'][name]
        return "| " + name + " | " + " | ".join(interval(per[c]) for c in corpora) + f" | {avg(per):.4f} | " + ("yes" if all(per[c]['plan_udf_free'] for c in corpora) else "no (JW UDF)") + " |"
    out += [row(n) for n in singles]
    out += ["", "<details><summary>All additional combination measurements</summary>", "",
            "| Variant | " + " | ".join(headings) + " | Mean | Pair plan UDF-free |", "|---|" + "---:|" * 5 + "---|"]
    out += [row(n) for n in d['selection_lock']['variants'] if n not in singles]
    out += ["", "</details>", "", "---", "", "## Forward selection", "",
            "Every remaining family is tested at each round. Combinations are canonicalized in shortlist order. "
            "The trace records rejected additions as well as accepted ones; this is greedy search, not exhaustive subset search.", "",
            "| Round | Starting variant | Best addition result | Mean VALID gain | Accepted |", "|---:|---|---|---:|---|"]
    for i, s in enumerate(d['forward_selection'], 1):
        out.append(f"| {i} | {s['base']} | {s['best']} | {s['gain']:+.8f} | {s['accepted']} |")
    out += ["", "---", "", "## TEST confirmation", "", "| Corpus | Chosen F1 [CI] | Jaro–Winkler F1 [CI] |", "|---|---:|---:|"]
    for c in corpora:
        out.append(f"| {c} | {interval(d['test']['chosen']['corpora'][c])} | {interval(d['test']['jaro_winkler']['corpora'][c])} |")
    t = d['test']
    out += [f"| Equal-weight mean | {t['chosen']['mean_f1']:.6f} | {t['jaro_winkler']['mean_f1']:.6f} |", "",
            f"Chosen − JW mean F1: **{t['delta_mean_f1']:+.6f}**, paired 95% CI "
            f"**[{t['delta_ci95'][0]:+.6f}, {t['delta_ci95'][1]:+.6f}]**.", "",
            "---", "", "## Verdict", "", "The supplied judge requires all four conditions below; statistical significance is reported "
            "through the interval but is not an additional judge condition.", "", "| Condition | Passed |", "|---|---|"]
    out += [f"| `{k}` | {v} |" for k, v in sorted(d['verdict_checks'].items())]
    out += ["", f"Recomputed verdict: **`{d['verdict']}`**. " +
            ("SIM-4 adoption may now be evaluated separately." if d['verdict']=='beaten' else "SIM-4 adoption is not applicable; the new families remain opt-in."),
            "", "---", "", "## Reproduce and audit", "", *reproduce,
            f"Spark **{d['meta']['manifest']['versions']['spark']}**; embedding "
            f"`{d['meta']['manifest']['embedding']['model']}` at `{d['meta']['manifest']['embedding']['revision']}`. "
            "Models use eight deterministic ID partitions sorted within each partition; numerical reproducibility "
            "across different Spark/JVM versions is not claimed.", "", "---", "", "## Limitations", "",
            "- VALID is reused for several comparisons; its bootstrap intervals are descriptive, not corrected for selection.",
            "- Abt-Buy and Leipzig share records across pair splits; they measure pair generalization, not unseen-entity generalization. Their pair bootstrap does not model dependence between pairs sharing an entity.",
            "- IDF and record embeddings use all record strings, including held-out records, without outcome labels.",
            "- Pair-plan purity excludes the precomputed embedding UDF and MLlib model scoring. It proves the string comparison path only; it is not a Photon execution claim.",
            "- The larger DP limits cover this benchmark but OSA/LCS repeatedly copy DP row arrays and can be costly on long text (beyond the usual O(n*m) cell count).",
            "- All four corpora carry equal weight regardless of size; conclusions depend on the fixed candidate, model and threshold protocol.",
            "", "---", "", "## License", "", "Benchmark code follows the repository license. Dataset terms and provenance are documented in " +
            ("`bench/corpora.py` in the source checkout; cached data and model weights retain their original licenses."
             if d['meta']['manifest']['protocol'] == 'simbeat-v2' else
             "[corpora.py](corpora.py); cached data and model weights retain their original licenses."), ""]
    return "\n".join(out)
