#!/usr/bin/env python3
"""Why candidate recall collapses on synthetic_1e6 (BENCHMARKS.md, "Findings") -> bench/results/scale_probe.json.

Measures, on the 10^6-record corpus, candidate recall at each step:
  1. gram_topk proposals (the default): the join keeps grams held by <= gram_cap (400) right records;
  2. union(gram_topk, conjunction field_blocks) proposals — the blocks Splink's demo-style model uses;
  3. the shared top-k ranking of those proposals with its vocabulary cut at gram_cap (today) and at 5 % / 10 % of
     the right records (a ranking vocabulary that is not the join budget).
No default is changed here: the re-decision belongs on validation data (bench/methods.py) with this corpus added.

    python bench/scale_probe.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpora  # noqa: E402

from lakematch import candidates, config  # noqa: E402
from lakematch.pipeline import entity_sides  # noqa: E402
from lakematch.runtime import Runtime  # noqa: E402

BLOCKS = [["given_name", "surname"], ["surname", "date_of_birth"], ["given_name", "date_of_birth"],
          ["postcode", "street_number"], ["address_1", "suburb"], ["soundex(surname)", "postcode"]]


def main() -> int:
    c = corpora.LOADERS["synthetic_1e6"]()
    base = {"entity": {"name": "person", "fields": c.fields}, "storage": {"root": str(corpora.DATA / "runs" / "scale_probe")},
            "runtime": {"cores": 8, "shuffle_partitions": 64, "driver_memory": "24g"},
            "features": {"embeddings": {"provider": "none"}}}
    cfg = config.build({**base, "candidates": {"method": "union", "union_of": ["gram_topk", "field_blocks"],
                                                 "field_blocks": BLOCKS}})
    rt = Runtime(cfg)
    sp = rt.spark
    L, R = entity_sides(rt, cfg, sp.createDataFrame(c.left), sp.createDataFrame(c.right))
    truth = rt.materialize(sp.createDataFrame(c.truth[["l_id", "r_id"]]), "truth")
    n = truth.count()
    recall = lambda df: round(df.join(truth, ["l_id", "r_id"]).count() / n, 4)
    out = {"true_links": n, "records": len(c.left) + len(c.right), "blocks": BLOCKS, "rows": []}

    def row(what, df, t0):
        df = rt.materialize(df.select("l_id", "r_id").distinct(), "probe")
        r = {"what": what, "pairs": df.count(), "recall": recall(df), "s": round(time.time() - t0, 1)}
        out["rows"].append(r)
        print(r, flush=True)
        return df

    t0 = time.time()
    row("gram_topk proposals (join: grams in <= 400 right records)", candidates.propose("gram_topk", L, R, cfg, None), t0)
    t0 = time.time()
    props = row("union(gram_topk, conjunction field_blocks) proposals", candidates.propose("union", L, R, cfg, None), t0)
    for label, cap in (("gram_cap 400 (today)", 400), ("5 % of right records", len(c.right) // 20),
                       ("10 % of right records", len(c.right) // 10)):
        c2 = config.build({**cfg.data, "candidates": {**cfg.data["candidates"], "gram_cap": cap}})
        t0 = time.time()
        row(f"union proposals -> top 5, ranking vocabulary {label}",
            candidates.top_k(candidates.rescore(props, L, R, c2), 5), t0)
    rt.close(stop=True)
    (HERE / "results" / "scale_probe.json").write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
