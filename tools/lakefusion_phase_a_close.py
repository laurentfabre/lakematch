#!/usr/bin/env python3
"""Sequential final LF-A checks under the enclosing bounded experiment runner."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    output = Path("bench/lakefusion/close-20260921.json")
    if output.exists():
        raise SystemExit("Final Phase A receipt exists; do not overwrite evidence")
    checks = [
        ("local_contracts", 120, [sys.executable, "-m", "pytest", "-q",
            "tests/test_mastering_contracts.py", "tests/test_mastering_policy.py",
            "tests/test_company_pilot.py", "tests/test_source_hygiene.py",
            "--junitxml=bench/lakefusion/close-tests-20260921.xml"]),
        ("source_preparation", 60, [sys.executable, "tools/prepare_company_pilot.py",
            "--output", "data/lakefusion/company-pilot-v0.1",
            "--manifest", "bench/lakefusion/company-pilot-v0.1.json"]),
        ("unity_gateway", 90, [sys.executable, "tools/lakefusion_gateway_probe.py",
            "--profile", "fevm-gdpr2", "--output", "bench/lakefusion/gateway-corrected-20260921.json"]),
    ]
    results = []
    for name, timeout, command in checks:
        result = subprocess.run(command, timeout=timeout)
        results.append({"name": name, "exit_code": result.returncode, "command": command})
        output.write_text(json.dumps({"checks": results}, indent=2) + "\n")
    return int(any(r["exit_code"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
