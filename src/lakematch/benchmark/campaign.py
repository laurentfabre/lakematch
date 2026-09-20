"""Repository benchmark entry point; the installed engine has no corpus downloads."""
from pathlib import Path
import subprocess
import sys


def execute(*, project_root='.', plan=False):
    root = Path(project_root).resolve()
    runner = root / 'tools/benchmark_campaign.py'
    if not runner.is_file() or not (root / 'bench/freeze.json').is_file():
        raise ValueError('bench --all requires a prepared lakematch checkout; set --project-root')
    command = [sys.executable, str(runner)]
    if plan:
        command.append('--plan')
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        raise ValueError('Benchmark campaign did not complete; see bench/campaign_execution.json and experiments/runs.jsonl')
    return {'status': 'plan_only' if plan else 'completed', 'project_root': str(root),
            'report': str(root / ('bench/ACCEPTANCE_PLAN.md' if plan else 'bench/BENCHMARKS.md'))}
