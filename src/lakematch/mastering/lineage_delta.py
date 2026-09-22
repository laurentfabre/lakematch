"""Optional Spark/Delta adapter; one serialized job owns its namespace."""
import json

from lakematch.delta_publication import DeltaPublisher
from .lineage import (TABLES, MAX_MASTERS, MAX_SOURCES, MAX_ATTRIBUTES, LineageConflict,
                      build_snapshot, prepare_entries, request_sha256, verify_snapshot)
from .lineage_publication import header, metadata

COMMON = "publication_id string, domain_id string, "
SCHEMAS = {
    "golden_records": COMMON + "master_id string, revision long, identity_revision long, contract_sha256 string, calculation_sha256 string, values_json string, calculation_json string",
    "attribute_lineage": COMMON + "master_id string, revision long, field_path string, value_json string, value_sha256 string, reason string, winner_json string, alternatives_json string, policy_id string, policy_version long, policy_sha256 string, contract_sha256 string",
    "source_versions": COMMON + "source_id string, source_key string, source_version long, source_sha256 string, mapping_version long, mapping_sha256 string, deleted boolean, source_json string",
    "memberships": COMMON + "master_id string, identity_revision long, source_id string, source_key string, source_version long, source_sha256 string, deleted boolean",
    "contracts": COMMON + "contract_sha256 string, definition_json string",
}
ORDER = {"golden_records": ("master_id",), "attribute_lineage": ("master_id", "field_path"),
         "source_versions": ("source_id", "source_key"), "memberships": ("master_id", "source_id", "source_key"),
         "contracts": ("contract_sha256",)}
LIMITS = {"golden_records": MAX_MASTERS, "attribute_lineage": MAX_ATTRIBUTES,
          "source_versions": MAX_SOURCES, "memberships": MAX_SOURCES, "contracts": MAX_MASTERS}


def frames(spark, snapshot):
    verified = verify_snapshot(snapshot)
    return {name: spark.createDataFrame(verified["tables"][name], SCHEMAS[name]) for name in TABLES}


class DeltaLineageStore:
    def __init__(self, spark, schema, namespace):
        self.publisher = DeltaPublisher(spark, schema, namespace)

    def _read(self, body):
        if body is None:
            return None
        h = header(body)
        if set(body["tables"]) != set(TABLES):
            raise LineageConflict("Incomplete Delta provenance publication")
        tables = {}
        for name in TABLES:
            count = h["counts"][name]
            if type(count) is not int or not 0 <= count <= LIMITS[name] or body["tables"][name]["rows"] != count:
                raise LineageConflict("Delta table row count exceeds bound or manifest differs")
            frame = self.publisher.read(body, name)
            rows = frame.orderBy(*ORDER[name]).limit(count + 1).collect()
            if len(rows) != count:
                raise LineageConflict("Delta table count differs from immutable publication")
            tables[name] = [r.asDict(recursive=True) for r in rows]
        return verify_snapshot({**h, "tables": tables})

    def current(self):
        return self._read(self.publisher.current())

    def read(self, publication_id):
        return self._read(self.publisher.committed(publication_id))

    def publish(self, publication_id, entries, context, *, expected_previous):
        # Preserve old-batch receipts without requiring today's scalar code.
        # The builder still fully replays calculations for every new batch.
        entries, context = prepare_entries(entries, context, replay=False)
        checksum = request_sha256(publication_id, expected_previous, entries, context)
        def build(previous):
            snapshot = build_snapshot(publication_id, entries, context, expected_previous=expected_previous,
                                      previous=self._read(previous))
            return frames(self.publisher.spark, snapshot), metadata(snapshot)
        receipt = self.publisher.publish(publication_id, checksum, build)
        # DeltaPublisher's duplicate path preserves its old general contract.
        # The provenance adapter also verifies referenced historic tables.
        self._read(receipt)
        return receipt
