#!/usr/bin/env python3
"""Download only declared public benchmark files, with revisions and checksums.

Preparation is separate from offline execution and never accesses personal data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile


DITTO_REV = "52985564a93fb11308439516d3e17a033d43ec8f"
MODEL_REV = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
ROOT = Path("data/sources")


def download(url, destination, expected=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix(destination.suffix + ".partial")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lakematch-research/0.1"}), timeout=60) as response, temporary.open("wb") as out:
            while block := response.read(1024 * 1024):
                out.write(block)
        temporary.replace(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    if expected and digest != expected:
        raise ValueError(f"Public corpus checksum mismatch: {destination}")
    return {"url": url, "path": str(destination), "sha256": digest, "bytes": destination.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="store_true")
    args = parser.parse_args()
    entries = []
    for name, url, sha, selected, license_ in [
        ("bpid", "https://zenodo.org/api/records/13932202/files/BPID.zip/content",
         "39196f9689aa3b2955dc3d6582b8991c399b91964d4eeaf1ab256e1be3149699",
         ["data_release/matching_dataset.jsonl"], "Apache-2.0, Zenodo 13932202"),
        ("affiliations", "https://dbs.uni-leipzig.de/files/datasets/affiliationstrings.zip",
         "cc611eb36dc276967dd1b832859f9f1adc6a725d1b0924ad6ae24b3b17f73219",
         ["affiliationstrings_ids.csv", "affiliationstrings_mapping.csv"], "CC BY 4.0, Leipzig benchmark page"),
    ]:
        item = download(url, ROOT / f"{name}.zip", sha)
        item["license"] = license_
        with zipfile.ZipFile(ROOT / f"{name}.zip") as archive:
            for member in selected:
                out = ROOT / name / Path(member).name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(archive.read(member))
        entries.append(item)
    for dataset in ("Textual/Abt-Buy", "Structured/Amazon-Google", "Structured/Walmart-Amazon", "Structured/DBLP-ACM"):
        for split in ("train", "valid", "test"):
            url = f"https://raw.githubusercontent.com/megagonlabs/ditto/{DITTO_REV}/data/er_magellan/{dataset}/{split}.txt"
            item = download(url, ROOT / "ditto" / dataset.split("/")[1] / f"{split}.txt")
            item.update(revision=DITTO_REV, license="Ditto mirror Apache-2.0; upstream corpus license unspecified; public research use")
            entries.append(item)
    if args.model:
        from huggingface_hub import snapshot_download
        path = snapshot_download("sentence-transformers/all-MiniLM-L6-v2", revision=MODEL_REV,
            local_dir="data/models/all-MiniLM-L6-v2", allow_patterns=["*.json", "*.txt", "model.safetensors", "README.md"])
        entries.append({"model": "sentence-transformers/all-MiniLM-L6-v2", "revision": MODEL_REV,
                        "path": path, "license": "Apache-2.0"})
    (ROOT / "manifest.json").write_text(json.dumps({"sources": entries}, indent=2) + "\n")
    print(json.dumps({"prepared_sources": len(entries), "manifest": str(ROOT / "manifest.json")}))


if __name__ == "__main__":
    main()
