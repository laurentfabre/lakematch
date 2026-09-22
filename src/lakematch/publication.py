"""Atomic local publication of immutable, multi-output job snapshots.

SQLite is the local commit catalog; Parquet remains the data format. Readers
resolve one committed manifest, never scan attempt directories. A process dying
at any point before COMMIT leaves the previous snapshot visible. Retrying the
same batch returns its original commit, even after newer batches have landed.
Remote publication uses Delta and is supplied by the Databricks job adapter.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    root = Path(root)
    files = sorted(path for path in root.rglob('*') if path.is_file()) if root.is_dir() else [root]
    if not files:
        raise ValueError(f'No prepared input or output files at {root}')
    return {str(path.relative_to(root)) if root.is_dir() else path.name: file_hash(path) for path in files}


def request_digest(inputs, contract):
    """Hash exact prepared input bytes and the immutable model/config contract."""
    body = {'inputs': {name: inventory(path) for name, path in sorted(inputs.items())}, 'contract': contract}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _verified(root, body):
    attempt = root / 'attempts' / body['attempt']
    expected = body['files']
    if not expected or inventory(attempt) != expected:
        raise ValueError(f"Published files changed for batch {body['batch_id']}")
    return body


def current(root):
    """Read-only snapshot resolution; opening it never initializes a database."""
    root = Path(root).resolve()
    database = root / 'commits.sqlite'
    if not database.is_file():
        return None
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        row = connection.execute('SELECT body FROM commits ORDER BY sequence DESC LIMIT 1').fetchone()
    return _verified(root, json.loads(row[0])) if row else None


def committed(root, batch_id):
    """Resolve a historical committed batch without initializing or moving head."""
    root = Path(root).resolve()
    database = root / 'commits.sqlite'
    if not database.is_file():
        return None
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        row = connection.execute('SELECT body FROM commits WHERE batch_id=?', (batch_id,)).fetchone()
    return _verified(root, json.loads(row[0])) if row else None


def publish(root, batch_id, digest, build):
    """Serialize a local writer, stage build(path, previous), then commit once.

    build writes every output below path and returns JSON-serializable metadata.
    It may fail or be killed: no partial outputs become visible. Only abandoned
    attempts owned by this catalog are removed on recovery. Committed attempts
    are retained so historical readers and journals remain reproducible.
    """
    if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 200:
        raise ValueError('Publication requires a nonempty batch ID of at most 200 characters')
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Publication requires a SHA-256 request digest')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    attempts = root / 'attempts'
    attempts.mkdir(exist_ok=True)
    with closing(sqlite3.connect(root / 'commits.sqlite', timeout=5, isolation_level=None)) as connection:
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('CREATE TABLE IF NOT EXISTS commits ('
            'sequence INTEGER PRIMARY KEY, batch_id TEXT UNIQUE NOT NULL, '
            'request_digest TEXT NOT NULL, body TEXT NOT NULL)')
        connection.execute('BEGIN IMMEDIATE')
        try:
            committed = [json.loads(row[0]) for row in connection.execute('SELECT body FROM commits ORDER BY sequence')]
            owned = {body['attempt'] for body in committed}
            recovered = []
            for path in attempts.iterdir():
                # Names are generated here, never derived from user batch IDs.
                if path.is_dir() and len(path.name) == 32 and all(c in '0123456789abcdef' for c in path.name) and path.name not in owned:
                    shutil.rmtree(path)
                    recovered.append(path.name)
            duplicate = next((body for body in committed if body['batch_id'] == batch_id), None)
            if duplicate:
                if duplicate['request_digest'] != digest:
                    raise ValueError('Batch ID was already committed with different inputs or model/config')
                _verified(root, duplicate)
                connection.execute('ROLLBACK')
                return {**duplicate, 'reused': True, 'recovered_attempts': recovered}
            previous = _verified(root, committed[-1]) if committed else None
            attempt = attempts / uuid4().hex
            attempt.mkdir()
            metadata = build(attempt, previous)
            hashes = inventory(attempt)
            # Force data to stable storage before the durable catalog points to it.
            for name in hashes:
                with (attempt / name).open('rb') as stream:
                    os.fsync(stream.fileno())
            for path in [p for p in attempt.rglob('*') if p.is_dir()] + [attempt, attempts]:
                descriptor = os.open(path, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            body = {'schema_version': 1, 'batch_id': batch_id, 'request_digest': digest,
                'attempt': attempt.name, 'root': str(attempt), 'files': hashes,
                'previous_batch_id': previous['batch_id'] if previous else None, 'metadata': metadata}
            connection.execute('INSERT INTO commits (batch_id, request_digest, body) VALUES (?, ?, ?)',
                               (batch_id, digest, json.dumps(body, sort_keys=True)))
            connection.execute('COMMIT')
            return {**body, 'reused': False, 'recovered_attempts': recovered}
        except BaseException:
            if connection.in_transaction:
                connection.execute('ROLLBACK')
            raise
