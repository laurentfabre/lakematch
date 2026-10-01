"""bench/results/clusters.json -> bench/CLUSTERS.md."""
from __future__ import annotations

import json
from pathlib import Path

TITLES = {"febrl3": "FEBRL3", "splink_historical_50k": "Splink historical_50k"}
METHODS = ("verified_merge", "connected_components", "center", "star")


def render(src: Path, dst: Path) -> None:
    d = json.loads(src.read_text())
    corp = [c for c in TITLES if c in d]
    L = ["# Clusters and identity (ZR-4)", "",
         f"*Generated {d['meta']['generated']} from `bench/results/clusters.json` by `bench/clusters.py`. "
         "Nothing below was typed by hand.*", "",
         "## Contents", "", "- [Methods](#methods)", "- [Convergence](#convergence)", "- [Stable ids](#stable-ids)",
         "- [Incremental run](#incremental-run)", "",
         "## Methods", "",
         "Scored like the ZR-3 benchmark (default candidates, model on TRAIN pairs, threshold on VALID); the links at or "
         "above the threshold are clustered four ways. Metrics are on the clustering induced on TEST records "
         "(pairwise F1 over within-cluster pairs, and B-cubed F1); the winner is the highest mean **VALID** B-cubed F1.",
         ""]
    L.append("| Method | " + " | ".join(f"{TITLES[c]} pairwise F1 · B-cubed F1 · largest · s" for c in corp)
             + " | Mean VALID B-cubed F1 |")
    L.append("|---|" + "---|" * len(corp) + "---|")
    for m in METHODS:
        cells = [f"{d[c][m]['pairwise_f1']:.4f} · {d[c][m]['b_cubed_f1']:.4f} · {d[c][m]['largest_predicted']} · "
                 f"{d[c][m]['wall_s']}" for c in corp]
        name = f"**{m}** (winner, default)" if m == d["winner"] else m
        L.append(f"| {name} | " + " | ".join(cells) + f" | {d['mean_valid_b_cubed_f1'][m]:.4f} |")
    L += ["", " · ".join(f"{TITLES[c]}: {d[c]['records']:,} records, {d[c]['gold_clusters']:,} gold clusters "
                         f"(largest {d[c]['largest_gold_cluster']}), {d[c]['links']:,} links at p >= {d[c]['threshold']}"
                         for c in corp), ""]
    conv = d["convergence_test"] or d.get("convergence_detail", {})
    L += ["## Convergence", "", f"Rule: {conv.get('rule', '')}. Passed: **{bool(d['convergence_test'])}**.", ""]
    for c, s in conv.get("per_corpus", {}).items():
        L.append(f"- {TITLES[c]}: {s['rounds']} rounds, {s['merges']:,} merges, {s['vetoes']:,} vetoes, "
                 f"{s['scored_pairs']:,} representative pairs scored, converged {s['converged']}")
    L += ["", "## Stable ids", "", f"Two independent passes per corpus with `{d['winner']}`; the second pass's ids are "
          f"carried from the first pass's crosswalk. Records whose `mdm_id` changed: **{d['rerun_changed_ids']}**.", ""]
    for c, r in d["rerun"].items():
        L.append(f"- {TITLES[c]}: {r['entities']:,} entities, {r['changed_ids']} changed, {r['events']} log events, "
                 f"ids equal without history: {r['ids_equal_without_history']}")
    L += ["", "## Incremental run", "", "1 % of the records held out of a base pass; the next pass adds them, deletes "
          "another 1 % and changes another 1 % (surname: two adjacent characters swapped). Identity is assigned from the "
          f"base crosswalk and the log is reconciled (`identity.reconcile`). Reconciles: "
          f"**{d['incremental_log_reconciles']}**.", ""]
    for c, r in d["incremental"].items():
        L.append(f"- {TITLES[c]}: +{r['added']} / −{r['deleted']} / ~{r['changed']} records; events {r['events']}; "
                 f"{r['records_whose_id_changed']} surviving records changed id, every one explained: {r['reconciles']}")
    dst.write_text("\n".join(L) + "\n")
