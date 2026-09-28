"""lakematch run | doctor | train | bench."""
from __future__ import annotations

import time

T_PROCESS = time.time()          # wall time is measured from process start, Spark start-up included

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULTS, METHODS, PAID_FEATURES, ConfigError, Config, load


def _default(key: str):
    node = DEFAULTS
    for part in key.split("."):
        node = node[part]
    return node


def doctor(cfg: Config, probe_session: bool) -> int:
    print(f"lakematch {__version__} · profile {cfg.get('profile')} · config base {cfg.base_dir}")
    java = os.environ.get("JAVA_HOME") or "(unset)"
    try:
        ver = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.splitlines()[0]
    except (OSError, IndexError):
        ver = "java not found"
    print(f"java      JAVA_HOME={java} · PATH java: {ver}")
    print("methods   (default = the brief's starting hypothesis until ZR-3 / ZR-4 name the validation winner)")
    for key, choices in METHODS.items():
        val = cfg.get(key)
        vals = val if isinstance(val, list) else [val]
        state = "; ".join(f"{v}: {'ready' if choices[v] is None else 'lands in ' + choices[v]}" for v in vals)
        mark = "default" if val == _default(key) else "custom"
        print(f"  {key:<30} {str(val):<52} {mark:<8} {state}")
    print("paid features")
    on = cfg.enabled_paid_features()
    for k, product in PAID_FEATURES.items():
        print(f"  {k:<30} {'ON ' if k in on else 'off'}  bills: {product}")
    if cfg.get("profile") == "laptop":
        print("laptop    every paid feature is off; DQX, the registry, the app and Genie are not used")
    from .candidates import budget_note
    print(f"budget    {budget_note(cfg)}")
    problems = cfg.runnable_problems()
    print("run       " + ("ready" if not problems else "blocked:\n  " + "\n  ".join(problems)))
    if probe_session:
        from .runtime import Runtime
        rt = Runtime(cfg)
        c = rt.caps
        print(f"session   spark {c.spark_version} · remote {c.remote} · cache() {'allowed' if c.can_cache else 'refused'}"
              f" · materialize -> {rt.strategy()}" + (f" · {'; '.join(c.notes)}" if c.notes else ""))
        rt.close(stop=True)
    return 0 if not problems else 1


def bench(args) -> int:
    """The harness lives in the repository's bench/ (corpora are fetched there, results are committed there)."""
    script = Path(__file__).resolve().parents[2] / "bench" / "benchmarks.py"
    if not script.exists():
        print("lakematch bench needs a source checkout (bench/benchmarks.py next to src/)", file=sys.stderr)
        return 2
    if args.render:
        cmd = ["render"]
    elif args.all or args.only:
        cmd = ["all"] + (["--only", args.only] if args.only else []) + (["--skip-jev"] if args.skip_jev else [])
    else:
        print("lakematch bench: pass --all, --only a,b or --render", file=sys.stderr)
        return 2
    return subprocess.run([sys.executable, str(script), *cmd]).returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lakematch", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="gate, candidates, features, train, score, link")
    r.add_argument("--config", required=True)
    r.add_argument("--root", help="override storage.root (outputs and scratch data)")
    r.add_argument("--connect", action="store_true", help="run over a local Spark Connect server")
    d = sub.add_parser("doctor", help="print what the config would do on this machine")
    d.add_argument("--config", required=True)
    d.add_argument("--session", action="store_true", help="also start a session and probe its capabilities")
    t = sub.add_parser("train", help="lands in ZR-5")
    t.add_argument("rest", nargs="*")
    b = sub.add_parser("bench", help="the benchmark harness (a source checkout: bench/benchmarks.py)")
    b.add_argument("--all", action="store_true", help="run every corpus, one process each, then render BENCHMARKS.md")
    b.add_argument("--only", help="comma-separated corpora; the others keep their last result")
    b.add_argument("--skip-jev", action="store_true", help="no Jev-labelled runs (no network, no cost)")
    b.add_argument("--render", action="store_true", help="only re-render BENCHMARKS.md from the recorded JSON")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    if args.cmd == "train":
        print("lakematch train: not implemented yet — it lands in ZR-5; `lakematch run` trains and scores in one go "
              "today.", file=sys.stderr)
        return 2
    if args.cmd == "bench":
        return bench(args)
    try:
        cfg = load(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    if args.cmd == "doctor":
        return doctor(cfg, args.session)
    if args.connect:
        cfg.data["runtime"]["connect"] = True
    from .pipeline import run
    summary = run(cfg, Path(args.root).resolve() if args.root else None, T_PROCESS)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
