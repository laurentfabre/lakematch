#!/usr/bin/env python3
"""One finite local-plus-Delta follow-up; stops if local acceptance fails."""
import subprocess
import sys


def main():
    subprocess.run([sys.executable, "tools/lakefusion_lineage_run.py",
                    "--output", "bench/lakefusion/lineage-local-20260922-final.json",
                    "--tests-output", "bench/lakefusion/lineage-tests-20260922-final.xml",
                    "--fixture-output", "data/lakefusion/lineage-20260922-final/fixture.json"], check=True, timeout=300)
    subprocess.run([sys.executable, "tools/lakefusion_lineage_remote.py", "--profile", "fevm-gdpr2",
                    "--output", "bench/lakefusion/lineage-remote-20260922-final.json",
                    "--fixture", "data/lakefusion/lineage-20260922-final/fixture.json"], check=True, timeout=1150)


if __name__ == "__main__":
    main()
