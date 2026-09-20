"""Optional adapter integration, run in the isolated DQX environment."""
import importlib.metadata
import json
from pathlib import Path
from unittest.mock import patch

from lakematch.config import from_dict
from lakematch.quality import native, apply_and_split
from lakematch.runtime import create_session


def check(spark):
    config = from_dict({'entity': {'fields': {'name': {'type': 'person_name'}, 'age': {'type': 'number'}}},
        'quality': {'checks': [
            {'name': 'name_required', 'kind': 'not_null', 'column': 'name'},
            {'name': 'age_range', 'kind': 'range', 'column': 'age', 'min': 0, 'max': 120},
            {'name': 'name_letters', 'kind': 'regex', 'column': 'name', 'pattern': '^[A-Za-z ]+$', 'criticality': 'warn'},
            {'name': 'size', 'kind': 'min_rows', 'value': 6}]}})
    frame = spark.createDataFrame([('good', 'Alice', '40'), ('warn', 'Zoë', '25'), ('dup', 'Bob', '20'),
        ('dup', 'Bill', 'oops'), (None, '', '-1'), ('   ', None, None)], 'rec_id string, name string, age string')
    dqx_config = from_dict({**config.data, 'profile': 'databricks',
        'quality': {**config['quality'], 'engine': 'dqx'}})
    dqx_config.require_implemented()
    # Rule construction must not execute Spark jobs or initialize workspace auth.
    with patch.object(type(frame), 'collect', side_effect=AssertionError('unexpected action')), \
         patch.object(type(frame), 'count', side_effect=AssertionError('unexpected action')), \
         patch.object(type(frame), 'toPandas', side_effect=AssertionError('unexpected action')), \
         patch('databricks.sdk.WorkspaceClient', side_effect=AssertionError('unexpected workspace client')):
        expected, actual = native.apply_and_split(frame, config), apply_and_split(frame, dqx_config)
    def canonical(data):
        return sorted(json.dumps(row.asDict(recursive=True), sort_keys=True) for row in data.collect())
    assert canonical(expected.valid) == canonical(actual.valid)
    assert canonical(expected.quarantined) == canonical(actual.quarantined)
    assert {row.rec_id for row in actual.valid.collect()} == {'good', 'warn'}
    assert actual.quarantined.count() == 4
    return {'status': 'completed', 'native_dqx_exact_parity': True, 'valid': 2, 'quarantined': 4,
        'warning_remains_valid': True, 'duplicate_ids_all_quarantined': True,
        'construction_has_no_spark_actions_or_workspace_client': True, 'dqx_api': 'DQRowRule.get_check_condition',
        'dqx_version': importlib.metadata.version('databricks-labs-dqx'),
        'cases': ['null/blank ID', 'duplicate ID', 'missing name', 'invalid/range numeric value', 'regex warning', 'row count']}


if __name__ == '__main__':
    cfg = from_dict({'entity': {'fields': {'name': {'type': 'person_name'}}}})
    spark = create_session(cfg)
    try:
        report = check(spark)
    finally:
        spark.stop()
    Path('data/dqx').mkdir(parents=True, exist_ok=True)
    Path('data/dqx/report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
