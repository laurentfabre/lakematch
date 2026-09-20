import importlib.util
import json

import pytest


def test_event_metrics_include_retries_and_require_completed_application(tmp_path):
    spec = importlib.util.spec_from_file_location('spark_events','tools/spark_event_metrics.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    folder=tmp_path/'eventlog_v2_app'
    folder.mkdir()
    path=folder/'events_1_app'
    events=[{'Event':'SparkListenerApplicationStart','App ID':'app'},
        {'Event':'SparkListenerTaskEnd','Stage ID':1,'Stage Attempt ID':0,'Task Info':{'Task ID':1,'Failed':True},
         'Task Metrics':{'Executor Run Time':10,'Shuffle Read Metrics':{'Remote Bytes Read':5,'Local Bytes Read':7},
            'Shuffle Write Metrics':{'Shuffle Bytes Written':30},'Peak Execution Memory':20}},
        {'Event':'SparkListenerTaskEnd','Stage ID':1,'Stage Attempt ID':1,'Task Info':{'Task ID':2},
         'Task Metrics':{'Executor Run Time':20,'Shuffle Read Metrics':{'Local Bytes Read':10}}}]
    path.write_text(''.join(json.dumps(x)+'\n' for x in events))
    with pytest.raises(ValueError,match='completed'):
        module.summarize(tmp_path)
    events.append({'Event':'SparkListenerApplicationEnd'})
    path.write_text(''.join(json.dumps(x)+'\n' for x in events))
    report=module.summarize(tmp_path)
    assert report['tasks']==2 and report['failed_or_killed_tasks']==1
    assert report['total_shuffle_read_bytes']==22 and report['total_shuffle_write_bytes']==30
    assert report['maximum_task_peak_execution_memory_bytes']==20
