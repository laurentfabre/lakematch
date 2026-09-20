"""Read local Spark event logs without a JVM or Spark session."""
import json
from pathlib import Path


def summarize(directory):
    tasks = []
    completed = set()
    applications = []
    for path in sorted(Path(directory).rglob('*')):
        if not path.is_file() or not path.name.startswith('events_'):
            continue
        with path.open() as stream:
            for line in stream:
                event = json.loads(line)
                kind = event.get('Event')
                if kind == 'SparkListenerApplicationStart':
                    applications.append(event.get('App ID'))
                elif kind == 'SparkListenerApplicationEnd':
                    completed.add(path.parent.name)
                elif kind == 'SparkListenerTaskEnd':
                    info = event.get('Task Info', {})
                    metric = event.get('Task Metrics', {})
                    tasks.append({'stage': event['Stage ID'], 'attempt': event['Stage Attempt ID'],
                        'task': info.get('Task ID'), 'successful': not info.get('Failed', False) and not info.get('Killed', False),
                        'executor_run_ms': metric.get('Executor Run Time', 0),
                        'shuffle_read_bytes': sum(metric.get('Shuffle Read Metrics', {}).get(k, 0) for k in ('Remote Bytes Read', 'Local Bytes Read')),
                        'shuffle_write_bytes': metric.get('Shuffle Write Metrics', {}).get('Shuffle Bytes Written', 0),
                        'memory_spilled_bytes': metric.get('Memory Bytes Spilled', 0),
                        'disk_spilled_bytes': metric.get('Disk Bytes Spilled', 0),
                        'peak_execution_memory_bytes': metric.get('Peak Execution Memory', 0)})
    if not tasks or not completed:
        raise ValueError('No completed Spark application/task metrics in event log directory')
    durations = sorted(t['executor_run_ms'] for t in tasks if t['successful'])
    median = durations[len(durations)//2] if durations else 0
    return {'applications': applications, 'completed_log_directories': sorted(completed),
        'tasks': len(tasks), 'failed_or_killed_tasks': sum(not t['successful'] for t in tasks),
        'total_shuffle_read_bytes': sum(t['shuffle_read_bytes'] for t in tasks),
        'total_shuffle_write_bytes': sum(t['shuffle_write_bytes'] for t in tasks),
        'maximum_task_shuffle_read_bytes': max(t['shuffle_read_bytes'] for t in tasks),
        'maximum_task_peak_execution_memory_bytes': max(t['peak_execution_memory_bytes'] for t in tasks),
        'total_memory_spilled_bytes': sum(t['memory_spilled_bytes'] for t in tasks),
        'total_disk_spilled_bytes': sum(t['disk_spilled_bytes'] for t in tasks),
        'maximum_to_median_task_duration': max(durations)/median if median else None,
        'scope': 'whole application, all task attempts; execution-memory peak is per task, not process RSS',
        'stage_metrics': tasks}
