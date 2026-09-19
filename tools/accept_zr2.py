#!/usr/bin/env python3
"""Run the declared ZR-2 sweep and render evidence; verification is separate."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from lakematch.config import FIELD_TYPES

CORPORA = {"febrl4": "febrl4_half_all", "bpid": "bpid", "abt_buy": "abt_buy", "affiliations": "affiliations"}
VARIANTS = ["native_all", "without_field_families", "without_idf", "without_grams", "without_monge", "plus_jaro_winkler", "plus_affine", "embedding_on"]
VARIANTS += [f"without_{kind}_fields" for kind in sorted(FIELD_TYPES)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=CORPORA, action="append")
    args = parser.parse_args()
    env = {**os.environ, "JAVA_HOME": os.environ.get("JAVA_HOME", str(Path(".tools/jdk/jdk-17.0.20.1+1/Contents/Home").resolve())),
           "SPARK_LOCAL_IP": "127.0.0.1", "PYSPARK_PYTHON": sys.executable,
           "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    for name in args.corpus or CORPORA:
        directory = CORPORA[name]
        command = [sys.executable, "tools/experiment.py", "--phase", "ZR-2", "--kind", "ablation-" + name,
            "--hypothesis", "Frozen feature ablations reproduce on validation; both training endpoints obey partitions; confirmation is unscored",
            "--dataset", directory, "--baseline", "native_all", "--primary-metric", "validation F1 and paired 95% bootstrap intervals",
            "--seed", "0", "--seed", "2026091901", "--seed", "2026091902", "--timeout", "900",
            "--config", f"data/bench/{directory}/manifest.json", "--artifact", f"data/ablation/{directory}/report.json"]
        for variant in VARIANTS:
            command += ["--artifact", f"data/ablation/{directory}/{variant}.predictions.json",
                        "--artifact", f"data/ablation/{directory}/{variant}.plan.txt"]
        command += ["--", "/usr/bin/sandbox-exec", "-f", "tools/offline.sb", sys.executable, "tools/run_ablation.py", name]
        result = subprocess.run(command, env=env)
        if result.returncode:
            return result.returncode
    if not args.corpus:
        return subprocess.run([sys.executable, "tools/report_ablation.py"], env=env).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
