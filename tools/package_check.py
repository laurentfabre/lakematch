#!/usr/bin/env python3
"""Build, install in isolation and inspect the private wheel; never publish."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    subprocess.run(["uv", "build", "--python", sys.executable, "--wheel"], check=True)
    wheel = Path("dist/lakematch-0.1.0-py3-none-any.whl").resolve()
    with zipfile.ZipFile(wheel) as archive:
        files = archive.namelist()
        metadata = archive.read(next(p for p in files if p.endswith("METADATA"))).decode()
        assert "License-Expression: Apache-2.0" in metadata
        assert "lakematch/cli.py" in files and "lakematch/runtime.py" in files
        assert not any(p.startswith(("app/", "spec/", "data/")) for p in files)
    with tempfile.TemporaryDirectory(prefix="lakematch-wheel-") as target:
        subprocess.run(["uv", "pip", "install", "--python", sys.executable, "--no-deps", "--no-index", "--target", target, str(wheel)], check=True)
        code = "import sys; sys.path.insert(0, sys.argv[1]); import lakematch; assert lakematch.__file__.startswith(sys.argv[1]); from lakematch.config import load; assert not load('examples/synthetic.yaml').enabled_paid; print(lakematch.__version__)"
        subprocess.run([sys.executable, "-c", code, target], check=True)
    repo = json.loads(subprocess.check_output(["gh", "repo", "view", "laurentfabre/lakematch", "--json", "visibility,isPrivate,url"]))
    assert repo["isPrivate"] is True
    Path("experiments/repository.json").write_text(json.dumps(repo, indent=2) + "\n")
    print(json.dumps({"wheel": str(wheel), "installed_import": "passed", "repository": repo}))


if __name__ == "__main__":
    main()
