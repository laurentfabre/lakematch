#!/usr/bin/env python3
"""jev_worker.py — send prepared jobs to Jev from the system Python (where typesafe_sdk lives); everything else in
bench/ runs in the venv (scikit-learn) and shells out to this file.

    python3 jev_worker.py <jobs.jsonl> <out.jsonl> <tag>

A job is {"id": ..., "state": {...}, "questions": {qid: {"type": "score"|"noul"|"choice", "instructions": ...,
"criteria": ...}}}. One output line per job: {"id", "answers": {qid: {...}}}. Token usage is appended to
cache/usage.jsonl under <tag>, so costs are measured and never estimated.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mdm_jev import api_key  # noqa: E402
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score  # noqa: E402

KIND = {"score": Score, "noul": Noul, "choice": Choice}


def build(spec: dict) -> dict:
    return {qid: KIND[q["type"]](**{k: v for k, v in q.items() if k != "type" and v is not None}) for qid, q in spec.items()}


async def main() -> None:
    jobs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    os.environ["TYPESAFE_API_KEY"] = api_key()
    gate, lock, usage = asyncio.Semaphore(12), asyncio.Lock(), {"in": 0, "out": 0, "req": 0, "err": 0}
    out, t0 = open(sys.argv[2], "a", encoding="utf-8"), time.time()

    async def one(client, job):
        async with gate:
            for attempt in range(3):
                try:
                    r = await client.system_one(state=job["state"], questions=build(job["questions"]))
                    break
                except Exception:  # noqa: BLE001
                    if attempt == 2:
                        usage["err"] += 1
                        return
                    await asyncio.sleep(2 * (attempt + 1))
        answers = {}
        for qid, a in r.answers.items():
            d = {}
            for f in ("score", "confidence", "noul", "choice"):
                if hasattr(a, f) and getattr(a, f) is not None:
                    d[f] = getattr(a, f)
            pr = getattr(a, "probabilities", None)
            if pr is not None:
                d["probs"] = [float(pr[k]) for k in sorted(pr)] if isinstance(pr, dict) and "pick" not in qid else (
                    {k: float(v) for k, v in pr.items()} if isinstance(pr, dict) else [float(x) for x in pr])
            answers[qid] = d
        usage["in"] += r.usage.input_tokens; usage["out"] += r.usage.output_tokens; usage["req"] += 1
        async with lock:
            out.write(json.dumps({"id": job["id"], "answers": answers}) + "\n"); out.flush()

    async with AsyncTypeSafeClient() as client:
        await asyncio.gather(*(one(client, j) for j in jobs))
    usage.update(tag=sys.argv[3], seconds=round(time.time() - t0, 1), at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    with open(HERE / "cache" / "usage.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(usage) + "\n")
    print(json.dumps(usage))


if __name__ == "__main__":
    asyncio.run(main())
