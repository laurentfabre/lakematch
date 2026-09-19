#!/usr/bin/env python3
"""Run model logging and fresh-process reload under separate finite envelopes."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    env = {**os.environ, "SPARK_LOCAL_IP": "127.0.0.1", "PYSPARK_PYTHON": sys.executable,
           "JAVA_HOME": str(Path(".tools/jdk/jdk-17.0.20.1+1/Contents/Home").resolve()),
           "MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR": "false", "MLFLOW_ENABLE_TELEMETRY": "false"}
    for mode, artifact in (("train", "train.json"), ("reload", "report.json")):
        result = subprocess.run([sys.executable, "tools/experiment.py", "--phase", "ZR-5", "--kind", "tracking-" + mode,
            "--hypothesis", "A composite Spark model preserves its raw-pair predictions, lineage and decisions after reload",
            "--timeout", "300", "--artifact", "data/tracking-canary/" + artifact,
            "--", "/usr/bin/sandbox-exec", "-f", "tools/offline.sb", sys.executable,
            "tools/tracking_canary.py", mode, "--root", "data/tracking-canary"], env=env)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
