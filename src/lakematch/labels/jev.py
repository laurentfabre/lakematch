"""Jev (TypeSafe System One) as the LLM labeller: `labels.llm: jev`.

Driver-side only (a serverless UDF cannot reach the internet). For each pair, one request carrying the two records'
entity fields and one three-level Score — different / cannot tell / same. Code owns the policy: a label is kept
when P(same) or P(different) reaches `labels.llm_tau`; "cannot tell" is an answer, and the pair stays unlabelled.

Every answer is cached on disk (one JSON line per pair, keyed by a hash of the question and both records), so a
re-run asks nothing and costs nothing. Usage reports both what this call sent (requests, input_tokens, usd) and
what labelling the whole sample costs (label_input_tokens, label_usd — each cached answer keeps its own token count).
Cost is predicted before anything is sent: `estimate()` prices the uncached pairs from the size of what would be
sent (input tokens ≈ a + b × characters of the two records' JSON), fitted on this cache's own answers once it holds
enough of them, else on the benchmark answers (PRIOR). `ask()` logs the prediction and refuses when it exceeds
`max_usd` (config `labels.llm_max_usd`). The key comes from TYPESAFE_API_KEY. Needs the optional `typesafe-sdk`
package (extra `jev`); a paid feature (`paid_features.llm_labeller`), off by default — allowed on the laptop profile.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path

log = logging.getLogger("lakematch")

PRICE_PER_M_INPUT = 0.042        # USD per million input tokens, output free (docs.typesafe.ai/models, 2026-09-19)
QUESTION_VERSION = "v1"
CONCURRENCY = 8
# tokens = a + b * chars, fitted by bench/jev_calibrate.py on the ZR-3 benchmark answers (11 corpora, jev-1.13.0,
# 2026-09-29): leave-one-corpus-out error of the predicted total 4.4 % median, 13.9 % worst (bench/results/jev_cost_model.json)
PRIOR = {"a": 386.07, "b": 0.4461, "n": 4399, "median_chars": 399, "worst_error_pct": 13.9,
         "source": "ZR-3 benchmarks, 11 corpora"}
MIN_LOCAL_FIT = 50          # answers with sizes this cache must hold before it calibrates its own estimate


class BudgetExceeded(RuntimeError):
    """The predicted cost of the uncached pairs exceeds labels.llm_max_usd: nothing was sent."""
CRITERIA = ["They describe two different {thing}s.",
            "They could be the same {thing}, but the fields shown do not settle it.",
            "They describe one and the same {thing}."]


def _question(what: str, thing: str):
    from typesafe_sdk import Score
    return {"relation": Score(
        instructions=[f"How do `record_a` and `record_b` relate? They are {what}.",
                      "An empty field is missing information, not a disagreement."],
        criteria=[c.format(thing=thing) for c in CRITERIA])}


def _key(state: dict, what: str, model: str | None) -> str:
    blob = json.dumps({"v": QUESTION_VERSION, "what": what, "model": model, "state": state}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()


def state_chars(pair: dict) -> int:
    """Characters of the JSON state one request carries (the size the token estimate is fitted on)."""
    return len(json.dumps({"record_a": pair["record_a"], "record_b": pair["record_b"]}, ensure_ascii=False))


def _fit(rows: list[tuple[int, int]]) -> dict | None:
    """Least squares tokens = a + b * chars over (chars, tokens) rows; None when the sizes do not vary."""
    n = len(rows)
    mx = sum(c for c, _ in rows) / n
    my = sum(t for _, t in rows) / n
    sxx = sum((c - mx) ** 2 for c, _ in rows)
    if sxx == 0:
        return None
    b = sum((c - mx) * (t - my) for c, t in rows) / sxx
    return {"a": my - b * mx, "b": b, "n": n}


def _load(cache: Path) -> dict[str, dict]:
    known: dict[str, dict] = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            j = json.loads(line)
            known[j["key"]] = j
    return known


def _predict(todo_chars: list[int], known: dict[str, dict]) -> dict:
    rows = [(j["chars"], j["input_tokens"]) for j in known.values() if "chars" in j and "input_tokens" in j]
    model = _fit(rows) if len(rows) >= MIN_LOCAL_FIT else None
    basis = f"fitted on this cache's {len(rows)} answers" if model else \
        f"prior fitted on {PRIOR['n']} benchmark answers ({PRIOR['source']})"
    model = model or PRIOR
    tokens = sum(max(model["a"] + model["b"] * c, 0.0) for c in todo_chars)
    return {"to_send": len(todo_chars), "est_input_tokens": int(round(tokens)),
            "est_usd": round(tokens * PRICE_PER_M_INPUT / 1e6, 6), "basis": basis,
            "per_pair_tokens": round(tokens / len(todo_chars), 1) if todo_chars else 0.0}


def estimate(pairs: list[dict], what: str, cache: Path, model: str | None = None) -> dict:
    """Predicted cost of labelling `pairs` now: only the pairs not already cached are sent."""
    known = _load(cache)
    todo = [p for p in pairs if _key({"record_a": p["record_a"], "record_b": p["record_b"]}, what, model) not in known]
    return {"pairs": len(pairs), "cached": len(pairs) - len(todo), **_predict([state_chars(p) for p in todo], known)}


def decide(probs: list[float], tau: float) -> float | None:
    """1.0 same, 0.0 different, None when Jev is not confident enough (probs = [different, unsure, same])."""
    if probs[2] >= tau:
        return 1.0
    if probs[0] >= tau:
        return 0.0
    return None


def ask(pairs: list[dict], what: str, thing: str, cache: Path, tau: float = 0.90, model: str | None = None,
        max_usd: float | None = None) -> tuple[list[dict], dict]:
    """pairs: {l_id, r_id, record_a: {field: value}, record_b: {...}}. Returns one row per pair
    {l_id, r_id, probs, label (1.0 / 0.0 / None)} and usage (see the module docstring). Raises BudgetExceeded,
    before any request, when the predicted cost of the uncached pairs exceeds `max_usd`."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    known = _load(cache)
    usage = {"requests": 0, "cached": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}
    keyed = [(p, _key({"record_a": p["record_a"], "record_b": p["record_b"]}, what, model)) for p in pairs]
    todo = [(p, k) for p, k in keyed if k not in known]
    usage["cached"] = len(keyed) - len(todo)
    pred = _predict([state_chars(p) for p, _ in todo], known)
    usage["predicted"] = pred
    log.info("jev: %d pairs, %d cached, %d to send ≈ %s input tokens ≈ $%.4f (%s)", len(keyed), usage["cached"],
             pred["to_send"], f"{pred['est_input_tokens']:,}", pred["est_usd"], pred["basis"])
    if max_usd is not None and pred["est_usd"] > max_usd:
        raise BudgetExceeded(f"Jev would cost about ${pred['est_usd']:.4f} for {pred['to_send']} uncached pairs "
                             f"(≈ {pred['est_input_tokens']:,} input tokens, {pred['basis']}), above "
                             f"labels.llm_max_usd = ${max_usd}. Nothing was sent; raise the budget or lower labels.n.")
    dirty = False
    for p, k in keyed:                      # sizes for answers cached before sizes were recorded (free backfill)
        if k in known and "chars" not in known[k]:
            known[k]["chars"] = state_chars(p)
            dirty = True
    if todo:
        fresh = asyncio.run(_ask_all(todo, _question(what, thing), model, usage))
        for j in fresh:
            if "probs" in j:
                known[j["key"]] = j
                dirty = True
            else:
                usage["errors"] += 1
    if dirty:                               # rewrite whole: new answers + backfilled sizes, one line per key
        tmp = cache.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(j) + "\n" for j in known.values()), encoding="utf-8")
        tmp.replace(cache)
    out, label_tokens = [], 0
    for p, k in keyed:
        j = known.get(k)
        probs = j["probs"] if j else None
        label_tokens += int(j.get("input_tokens", 0)) if j else 0
        out.append({"l_id": p["l_id"], "r_id": p["r_id"], "probs": probs,
                    "label": decide(probs, tau) if probs else None})
    usage["usd"] = round(usage["input_tokens"] * PRICE_PER_M_INPUT / 1e6, 6)
    usage["label_input_tokens"] = label_tokens
    usage["label_usd"] = round(label_tokens * PRICE_PER_M_INPUT / 1e6, 6)
    return out, usage


async def _ask_all(todo, questions, model, usage) -> list[dict]:
    from typesafe_sdk import AsyncTypeSafeClient
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(client, pair, key):
        chars = state_chars(pair)
        async with gate:
            try:
                r = await client.system_one(state={"record_a": pair["record_a"], "record_b": pair["record_b"]},
                                            questions=questions, model=model)
            except Exception as err:  # noqa: BLE001 — one failed pair must not lose the batch
                return {"key": key, "error": type(err).__name__}
        usage["requests"] += 1
        usage["input_tokens"] += int(r.usage.input_tokens)
        usage["output_tokens"] += int(r.usage.output_tokens)
        probs = r.answers["relation"].probabilities
        probs = [float(probs[k]) for k in sorted(probs)] if isinstance(probs, dict) else [float(x) for x in probs]
        return {"key": key, "probs": [round(x, 4) for x in probs], "model": r.model,
                "input_tokens": int(r.usage.input_tokens), "chars": chars}

    async with AsyncTypeSafeClient() as client:
        return list(await asyncio.gather(*(one(client, p, k) for p, k in todo)))
