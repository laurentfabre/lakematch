"""Job-only Delta commit catalog over immutable snapshot tables.

Every writer must use the same single-concurrency job. A compare-and-swap on the
catalog head additionally rejects stale writers; this adapter does not supply a
distributed lease. Readers pin a single catalog body and Delta table version.
Partial table writes are never visible through a committed body.
"""
import hashlib
import json
import re
from uuid import uuid4

from pyspark.sql import functions as F


def _identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError('Delta publication requires an explicitly owned catalog.schema')
    return '.'.join(f'`{part}`' for part in value.split('.'))


def digest(contract):
    """Include input Delta versions and immutable model/config identities."""
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class DeltaPublisher:
    def __init__(self, spark, schema, namespace):
        self.spark, self.schema = spark, schema
        quoted = _identifier(schema)
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError('Publication namespace must be nonempty')
        self.prefix = 'lm_pub_' + hashlib.sha256(namespace.encode()).hexdigest()[:16]
        self.catalog = f'{quoted}.`{self.prefix}_commits`'

    def initialize(self):
        self.spark.sql(f'CREATE TABLE IF NOT EXISTS {self.catalog} ('
            'key STRING, sequence BIGINT, batch_id STRING, request_digest STRING, body STRING) '
            "USING DELTA TBLPROPERTIES ('delta.isolationLevel' = 'Serializable')").collect()
        # An initialized head is updated by every commit, making competing
        # catalog writers conflict in Delta instead of independently appending.
        self.spark.sql(f"MERGE INTO {self.catalog} t USING (SELECT 'head' AS key) s ON t.key=s.key "
            "WHEN NOT MATCHED THEN INSERT (key, sequence) VALUES ('head', 0)").collect()
        rows = self.spark.table(self.catalog).filter("key = 'head'").collect()
        if len(rows) != 1:
            raise ValueError('Publication catalog has an invalid head; serialize initialization')

    def _row(self, key):
        rows = self.spark.table(self.catalog).filter(F.col('key') == key).collect()
        if len(rows) > 1:
            raise ValueError('Publication catalog contains duplicate keys')
        return rows[0] if rows else None

    def current(self):
        row = self._row('head')
        return json.loads(row.body) if row and row.body else None

    def committed(self, batch_id):
        """Read an existing historical batch; never initialize or move the head."""
        row = self._row('batch:' + batch_id)
        return json.loads(row.body) if row and row.body else None

    def cleanup_abandoned(self):
        """Run only in the serialized writer, when no other build is active."""
        referenced = set()
        for row in self.spark.table(self.catalog).select('body').collect():
            if row.body:
                referenced.update(item['table'] for item in json.loads(row.body)['tables'].values())
        removed = []
        pattern = re.compile(re.escape(self.prefix) + r'_[0-9a-f]{32}_[a-z][a-z0-9_]*')
        for row in self.spark.sql(f'SHOW TABLES IN {_identifier(self.schema)}').collect():
            table = self.schema + '.' + row.tableName
            if pattern.fullmatch(row.tableName) and table not in referenced:
                self.spark.sql(f'DROP TABLE {table}').collect()
                removed.append(table)
        return removed

    def read(self, body, name):
        snapshot = body['tables'][name]
        expected_prefix = f'{self.schema}.{self.prefix}_{body["attempt"]}_'
        if not snapshot['table'].startswith(expected_prefix) or snapshot['version'] != 0:
            raise ValueError('Snapshot points outside its owned immutable attempt')
        return self.spark.read.option('versionAsOf', snapshot['version']).table(snapshot['table'])

    def publish(self, batch_id, request_digest, build):
        """build(previous) returns (named DataFrames, metadata); only jobs call it.

        A retry returns the original batch without rewinding the catalog head.
        A failure before MERGE leaves the previous snapshot visible. Abandoned
        attempt tables are never picked up by readers. The serialized writer
        removes them on its next attempt, preserving every committed snapshot.
        """
        if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 200:
            raise ValueError('Publication needs a nonempty batch ID of at most 200 characters')
        if not re.fullmatch(r'[0-9a-f]{64}', request_digest):
            raise ValueError('Publication needs a SHA-256 request digest')
        self.initialize()
        recovered = self.cleanup_abandoned()
        key = 'batch:' + batch_id
        duplicate = self._row(key)
        if duplicate:
            if duplicate.request_digest != request_digest:
                raise ValueError('Batch already committed with different inputs or model/config')
            return {**json.loads(duplicate.body), 'reused': True, 'recovered_tables': recovered}
        head = self._row('head')
        previous = json.loads(head.body) if head.body else None
        attempt = uuid4().hex
        frames, metadata = build(previous)
        if not frames:
            raise ValueError('A publication requires at least one output')
        tables = {}
        for name, frame in frames.items():
            if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
                raise ValueError('Output names must be simple lowercase identifiers')
            table = f'{self.schema}.{self.prefix}_{attempt}_{name}'
            frame.write.format('delta').mode('error').saveAsTable(table)
            version = self.spark.sql(f'DESCRIBE HISTORY {table} LIMIT 1').first().version
            if version != 0:
                raise ValueError('A new immutable attempt must have Delta version zero')
            tables[name] = {'table': table, 'version': version,
                'rows': self.spark.read.option('versionAsOf', version).table(table).count()}
        body = {'schema_version': 1, 'batch_id': batch_id, 'request_digest': request_digest,
            'attempt': attempt, 'sequence': head.sequence + 1, 'tables': tables,
            'previous_batch_id': previous['batch_id'] if previous else None, 'metadata': metadata}
        payload = json.dumps(body, sort_keys=True)
        view = 'lm_commit_' + uuid4().hex
        staged = self.spark.createDataFrame([
            ('head', body['sequence'], batch_id, request_digest, payload, head.sequence),
            (key, body['sequence'], batch_id, request_digest, payload, head.sequence)],
            'key string, sequence long, batch_id string, request_digest string, body string, expected_sequence long')
        staged.createOrReplaceTempView(view)
        try:
            # Both the historical batch row and head move in one Delta transaction.
            self.spark.sql(f'MERGE INTO {self.catalog} t USING {view} s ON t.key=s.key '
                "WHEN MATCHED AND t.key='head' THEN UPDATE SET "
                "sequence=CASE WHEN t.sequence=s.expected_sequence THEN s.sequence "
                "ELSE CAST(raise_error('Stale publication head; retry through serialized job') AS BIGINT) END, "
                'batch_id=s.batch_id, request_digest=s.request_digest, body=s.body '
                "WHEN MATCHED THEN UPDATE SET body=CAST(raise_error('Concurrent batch commit; retry') AS STRING) "
                'WHEN NOT MATCHED THEN INSERT (key, sequence, batch_id, request_digest, body) '
                'VALUES (s.key,s.sequence,s.batch_id,s.request_digest,s.body)').collect()
        finally:
            self.spark.catalog.dropTempView(view)
        committed = self._row(key)
        if not committed or committed.body != payload:
            raise RuntimeError('Commit was not observed; resolve the batch before retrying')
        return {**body, 'reused': False, 'recovered_tables': recovered}
