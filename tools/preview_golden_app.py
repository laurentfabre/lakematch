"""Start an owned loopback app for a bounded, read-only synthetic UI preview."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="lakematch-golden-preview-") as directory:
        env = {**os.environ, "LAKEMATCH_REVIEW_STORE": "sqlite",
               "LAKEMATCH_REVIEW_DATABASE": str(Path(directory) / "review.sqlite"),
               "LAKEMATCH_REVIEW_LOCAL_USER": "synthetic-demo-preview"}
        env.pop("DATABRICKS_APP_NAME", None)
        with socket.socket() as sock, (output / "server.log").open("w") as log:
            sock.bind(("127.0.0.1", 0))
            url = f"http://127.0.0.1:{sock.getsockname()[1]}"
            process = subprocess.Popen([str(ROOT / "app/.venv/bin/python"), "-m", "uvicorn",
                "lakematch_review.backend.app:app", "--fd", str(sock.fileno())],
                cwd=ROOT / "app", env=env, pass_fds=(sock.fileno(),), stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        with urllib.request.urlopen(url + "/api/demo/golden-records", timeout=1):
                            break
                    except OSError:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError("Owned preview server did not start; inspect server.log")
                        time.sleep(.1)
                print(f"Previewing {url}/#golden-records", flush=True)
                subprocess.run(["node", str(ROOT / "app/dev/preview_golden.mjs"), url, str(output)],
                               env=env, check=True, timeout=90)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            print(f"Preview saved to {output}; owned server stopped.")


if __name__ == "__main__":
    main()
