"""Local immutable publication adapter for bounded provenance snapshots."""
import json
from pathlib import Path

from lakematch import publication
from .lineage import (TABLES, MAX_SNAPSHOT_BYTES, LineageConflict, build_snapshot, encode,
                      prepare_entries, request_sha256, verify_snapshot)

KIND = "golden_provenance_v1"


def metadata(snapshot):
    return {"kind": KIND, "snapshot": {k: v for k, v in snapshot.items() if k != "tables"}}


def header(body):
    if body.get("metadata", {}).get("kind") != KIND:
        raise LineageConflict("Publication namespace does not contain golden provenance")
    return body["metadata"]["snapshot"]


class LocalLineageStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def _read(self, body):
        if body is None:
            return None
        h = header(body)
        attempt = self.root / "attempts" / body["attempt"]
        paths = {name: attempt / (name + ".json") for name in TABLES}
        if sum(p.stat().st_size for p in paths.values()) > MAX_SNAPSHOT_BYTES:
            raise LineageConflict("Published tables exceed snapshot byte bound")
        return verify_snapshot({**h, "tables": {name: json.loads(path.read_text()) for name, path in paths.items()}})

    def current(self):
        return self._read(publication.current(self.root))

    def read(self, publication_id):
        return self._read(publication.committed(self.root, publication_id))

    def publish(self, publication_id, entries, context, *, expected_previous):
        # A committed retry must remain readable after an implementation upgrade.
        # New batches replay inside build_snapshot, under the publisher's lock.
        entries, context = prepare_entries(entries, context, replay=False)
        checksum = request_sha256(publication_id, expected_previous, entries, context)
        def build(path, previous):
            snapshot = build_snapshot(publication_id, entries, context, expected_previous=expected_previous,
                                      previous=self._read(previous))
            for name, rows in snapshot["tables"].items():
                (path / (name + ".json")).write_text(encode(rows) + "\n")
            return metadata(snapshot)
        return publication.publish(self.root, publication_id, checksum, build)
