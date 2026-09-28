#!/usr/bin/env python3
"""Fit Jev's cost model on the benchmark answers -> bench/results/jev_cost_model.json (+ the PRIOR for labels/jev.py).

Every cached answer under data/runs/bench/jev/ holds the characters of the JSON state it sent and the input tokens
Jev billed. Fit input_tokens = a + b * chars by least squares over all of them, then check the prediction the way a
user meets it — on a corpus the fit never saw: leave one corpus out, fit on the others, predict that corpus's total.

    python bench/jev_calibrate.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from lakematch.labels.jev import PRICE_PER_M_INPUT, _fit  # noqa: E402

CACHE = HERE.parent / "data" / "runs" / "bench" / "jev"
OUT = HERE / "results" / "jev_cost_model.json"


def main() -> int:
    rows: dict[str, list[tuple[int, int]]] = {}
    for f in sorted(CACHE.glob("*.jsonl")):
        pts = [(j["chars"], j["input_tokens"]) for j in map(json.loads, f.read_text().splitlines())
               if "chars" in j and "input_tokens" in j]
        if pts:
            rows[f.stem] = pts
    everything = [p for pts in rows.values() for p in pts]
    fit = _fit(everything)
    out = {"model": "input_tokens = a + b * chars (chars = JSON of both records' entity fields)",
           "a": round(fit["a"], 2), "b": round(fit["b"], 4), "n": fit["n"],
           "median_chars": int(statistics.median(c for c, _ in everything)),
           "price_per_m_input_usd": PRICE_PER_M_INPUT, "leave_one_corpus_out": {}}
    for name, pts in rows.items():
        m = _fit([p for n, ps in rows.items() if n != name for p in ps])
        pred = sum(m["a"] + m["b"] * c for c, _ in pts)
        actual = sum(t for _, t in pts)
        out["leave_one_corpus_out"][name] = {
            "pairs": len(pts), "actual_tokens": actual, "predicted_tokens": int(round(pred)),
            "error_pct": round(100 * (pred - actual) / actual, 1),
            "actual_usd": round(actual * PRICE_PER_M_INPUT / 1e6, 5), "predicted_usd": round(pred * PRICE_PER_M_INPUT / 1e6, 5)}
    errs = [abs(v["error_pct"]) for v in out["leave_one_corpus_out"].values()]
    out["leave_one_corpus_out_max_abs_error_pct"] = max(errs)
    out["leave_one_corpus_out_median_abs_error_pct"] = round(statistics.median(errs), 1)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "leave_one_corpus_out"}, indent=1))
    for n, v in out["leave_one_corpus_out"].items():
        print(f"  {n:<28} {v['pairs']:>4} pairs  actual {v['actual_tokens']:>8,}  predicted {v['predicted_tokens']:>8,}  "
              f"{v['error_pct']:+.1f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
