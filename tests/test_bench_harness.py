"""ZR-3 harness pieces that need neither Spark nor the network: Jev's decision rule and cache, the per-unit counts
and bootstrap of bench/benchmarks.py, and `lakematch bench` argument handling."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lakematch import cli
from lakematch.labels import jev

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))


def test_jev_decide_keeps_only_confident_answers():
    assert jev.decide([0.02, 0.03, 0.95], 0.9) == 1.0
    assert jev.decide([0.93, 0.05, 0.02], 0.9) == 0.0
    assert jev.decide([0.40, 0.20, 0.40], 0.9) is None      # "cannot tell" is an answer: no label


def test_jev_cache_answers_without_a_request_and_prices_the_sample(tmp_path, monkeypatch):
    pairs = [{"l_id": "a", "r_id": "b", "record_a": {"n": "x"}, "record_b": {"n": "x"}}]
    key = jev._key({"record_a": {"n": "x"}, "record_b": {"n": "x"}}, "w", None)
    cache = tmp_path / "c.jsonl"
    cache.write_text(json.dumps({"key": key, "probs": [0.01, 0.01, 0.98], "input_tokens": 500}) + "\n")
    monkeypatch.setattr(jev, "_ask_all", lambda *a: (_ for _ in ()).throw(AssertionError("no request expected")))
    out, usage = jev.ask(pairs, "w", "thing", cache)
    assert out[0]["label"] == 1.0
    assert usage["requests"] == 0 and usage["cached"] == 1 and usage["usd"] == 0
    assert usage["label_input_tokens"] == 500 and usage["label_usd"] == round(500 * 0.042 / 1e6, 6)


def test_unit_counts_count_a_missed_candidate_as_a_false_negative():
    import benchmarks
    truth = pd.DataFrame({"l_id": ["a", "b", "c"], "r_id": ["1", "2", "3"]})
    links = pd.DataFrame({"l_id": ["a", "b"], "r_id": ["1", "9"]})
    tp, fp, fn = benchmarks.unit_counts(["a", "b", "c", "d"], links, truth)
    assert list(tp) == [1, 0, 0, 0] and list(fp) == [0, 1, 0, 0] and list(fn) == [0, 1, 1, 0]
    s = benchmarks.summarise(tp, fp, fn)
    assert s["f1"] == round(2 * 1 / (2 + 1 + 2), 4) and s["units"] == 4
    assert s["f1_ci95"][0] <= s["f1"] <= s["f1_ci95"][1]


def test_bootstrap_is_seeded():
    import benchmarks
    rng = np.random.default_rng(3)
    tp, fp, fn = rng.integers(0, 2, 50), rng.integers(0, 2, 50), rng.integers(0, 2, 50)
    assert benchmarks.summarise(tp, fp, fn) == benchmarks.summarise(tp, fp, fn)


def test_bench_cli_needs_a_mode(capsys):
    assert cli.main(["bench"]) == 2
    assert "--all" in capsys.readouterr().err
