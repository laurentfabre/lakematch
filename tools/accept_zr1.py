#!/usr/bin/env python3
"""Execute ZR-1 acceptance; distinct from the strictly read-only verifier."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    java = Path(".tools/jdk/jdk-17.0.20.1+1/Contents/Home").resolve()
    env = {**os.environ, "SPARK_LOCAL_IP": "127.0.0.1", "PYSPARK_PYTHON": sys.executable,
           "JAVA_HOME": os.environ.get("JAVA_HOME", str(java)), "UV_CACHE_DIR": "/private/tmp/lakematch-uv-cache"}
    p = sys.executable
    runs = [
        ("package-build", "The wheel installs independently and the repository remains private",
         ["--artifact", "dist/lakematch-0.1.0-py3-none-any.whl", "--artifact", "experiments/repository.json"], [p, "tools/package_check.py"]),
        ("tests-classic", "The complete suite passes with no skips on classic local Spark",
         ["--artifact", "experiments/tests-classic.xml"], [p, "-m", "pytest", "-q", "--junitxml=experiments/tests-classic.xml"]),
        ("tests-connect", "The identical suite passes with no skips through local Spark Connect",
         ["--artifact", "experiments/tests-connect.xml"], [p, "tools/connect_tests.py"]),
        ("offline-run", "OS-denied external egress permits only local execution, producing links and quarantine",
         ["--config", "examples/synthetic.yaml", "--artifact", "data/synthetic/output/metrics.json"],
         ["/usr/bin/sandbox-exec", "-f", "tools/offline.sb", p, "tools/offline_run.py"]),
        ("febrl4-run", "Full prepared original FEBRL4 produces links within the predeclared candidate budgets",
         ["--config", "examples/febrl4.yaml", "--artifact", "data/febrl4/output/metrics.json", "--artifact", "data/febrl4/manifest.json"],
         [p, "-m", "lakematch.cli", "run", "--config", "examples/febrl4.yaml"]),
    ]
    for kind, hypothesis, options, command in runs:
        result = subprocess.run([p, "tools/experiment.py", "--phase", "ZR-1", "--kind", kind,
                                 "--hypothesis", hypothesis, "--timeout", "300", *options, "--", *command], env=env)
        if result.returncode:
            return result.returncode
    return subprocess.run(["bash", "verify_zr.sh", "1"], env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
