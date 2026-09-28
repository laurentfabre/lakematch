"""Jev (TypeSafe System One) as the LLM labeller: `labels.llm: jev`.

Driver-side only (a serverless UDF cannot reach the internet). For each pair, one request carrying the two records'
entity fields and one three-level Score — different / cannot tell / same. Code owns the policy: a label is kept
when P(same) or P(different) reaches `labels.llm_tau`; "cannot tell" is an answer, and the pair stays unlabelled.

Every answer is cached on disk (one JSON line per pair, keyed by a hash of the question and both records), so a
re-run asks nothing and costs nothing. Usage reports both what this call sent (requests, input_tokens, usd) and
what labelling the whole sample costs (label_input_tokens, label_usd — each cached answer keeps its own token count).
The key comes from TYPESAFE_API_KEY. Needs the optional `typesafe-sdk` package (extra `jev`); it is a paid feature
(`paid_features.llm_labeller`), off by default and never on the laptop profile.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

PRICE_PER_M_INPUT = 0.042        # USD per million input tokens, output free (docs.typesafe.ai/models, 2026-09-19)
QUESTION_VERSION = "v1"
CONCURRENCY = 8
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


def decide(probs: list[float], tau: float) -> float | None:
    """1.0 same, 0.0 different, None when Jev is not confident enough (probs = [different, unsure, same])."""
    if probs[2] >= tau:
        return 1.0
    if probs[0] >= tau:
        return 0.0
    return None


def ask(pairs: list[dict], what: str, thing: str, cache: Path, tau: float = 0.90, model: str | None = None) -> tuple[list[dict], dict]:
    """pairs: {l_id, r_id, record_a: {field: value}, record_b: {...}}. Returns one row per pair
    {l_id, r_id, probs, label (1.0 / 0.0 / None)} and usage (see the module docstring)."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    known: dict[str, dict] = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            j = json.loads(line)
            known[j["key"]] = j
    usage = {"requests": 0, "cached": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}
    keyed = [(p, _key({"record_a": p["record_a"], "record_b": p["record_b"]}, what, model)) for p in pairs]
    todo = [(p, k) for p, k in keyed if k not in known]
    usage["cached"] = len(keyed) - len(todo)
    if todo:
        fresh = asyncio.run(_ask_all(todo, _question(what, thing), model, usage))
        with cache.open("a", encoding="utf-8") as fh:
            for j in fresh:
                if "probs" in j:
                    known[j["key"]] = j
                    fh.write(json.dumps(j) + "\n")
                else:
                    usage["errors"] += 1
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
                "input_tokens": int(r.usage.input_tokens)}

    async with AsyncTypeSafeClient() as client:
        return list(await asyncio.gather(*(one(client, p, k) for p, k in todo)))
