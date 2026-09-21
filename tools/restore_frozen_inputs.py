"""Restore the exact public inference fixture from Git; optionally upload missing files."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_archive():
    assets = ROOT / "deployment/assets"
    receipt = json.loads((assets / "frozen-inference-v1.json").read_text())
    raw = (assets / receipt["archive"]).read_bytes()
    if digest(raw) != receipt["sha256"]:
        raise ValueError("Recovery archive checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    if digest(files["manifest.json"]) != receipt["manifest_sha256"]:
        raise ValueError("Recovery manifest checksum mismatch")
    if digest((ROOT / "bench/freeze.json").read_bytes()) != manifest["freeze_sha256"]:
        raise ValueError("Archive does not match the committed benchmark freeze")
    if set(files) != {*manifest["files"], "manifest.json"}:
        raise ValueError("Unexpected recovery archive contents")
    for name, data in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("Unsafe recovery path")
        if name != "manifest.json" and digest(data) != manifest["files"][name]:
            raise ValueError(f"Recovery file checksum mismatch: {name}")
    return files


def restore(destination):
    files = read_archive()
    # Check every existing file before writing anything; never change a frozen snapshot.
    for name, data in files.items():
        target = destination / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f"Refusing to replace changed frozen input: {target}")
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
    return files


def upload(files, profile):
    from databricks.sdk.errors import NotFound
    from workspace_support import client, INPUT_ROOT
    w = client(profile)
    missing = []
    for name, data in files.items():
        path = INPUT_ROOT + "/" + name
        try:
            with w.files.download(path).contents as stream:
                existing = stream.read()
            if existing != data:
                raise ValueError(f"Remote frozen input differs; refusing overwrite: {path}")
        except NotFound:
            missing.append(name)
    # Publish the manifest last so an interrupted upload can be safely resumed.
    for name in sorted(missing, key=lambda n: (n == "manifest.json", n)):
        w.files.upload(INPUT_ROOT + "/" + name, io.BytesIO(files[name]), overwrite=False)
    return {"verified": len(files) - len(missing), "uploaded": len(missing), "root": INPUT_ROOT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "data/serverless_frozen")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--profile")
    args = parser.parse_args()
    if args.upload and not args.profile:
        parser.error("--upload requires an explicitly selected --profile")
    files = restore(args.destination)
    result = {"local": str(args.destination), "verified_files": len(files)}
    if args.upload:
        result["workspace"] = upload(files, args.profile)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
