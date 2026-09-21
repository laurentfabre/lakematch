"""Fresh synthetic train/review/retrain acceptance with an isolated local app."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from source import hashes

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    root, report = args.root.resolve(), args.report_dir.resolve()
    if (root / 'baseline-output').exists() or (root / 'review.sqlite').exists():
        raise FileExistsError('Use a fresh acceptance directory; preserve previous evidence')
    root.mkdir(parents=True, exist_ok=True)
    report.mkdir(parents=True, exist_ok=True)
    (report / 'app-source.json').write_text(json.dumps(hashes(), indent=2) + '\n')

    def run(*command, timeout=180, **kwargs):
        subprocess.run(list(map(str, command)), cwd=ROOT, check=True, timeout=timeout, **kwargs)

    run(ROOT / 'app/.venv/bin/python', '-m', 'pytest', 'app/tests', '-q',
        '--junitxml=' + str(report / 'app-tests.xml'))
    run(sys.executable, 'app/acceptance/fixture.py', 'prepare', '--root', root)
    run(sys.executable, '-m', 'lakematch.cli', 'train', '--config', root / 'baseline.yaml', '--save-scores')
    run(sys.executable, 'app/acceptance/fixture.py', 'seed', '--root', root,
        '--database', root / 'review.sqlite')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'LAKEMATCH_REVIEW_STORE': 'sqlite',
           'LAKEMATCH_REVIEW_DATABASE': str(root / 'review.sqlite'),
           'LAKEMATCH_REVIEW_LOCAL_USER': 'synthetic-acceptance',
           'LAKEMATCH_REVIEW_GENIE_ENABLED': 'false'}

    def fetch():
        with urllib.request.urlopen(url + '/api/training-labels', timeout=3) as response:
            return json.load(response)

    def start(log):
        child = subprocess.Popen([str(ROOT / 'app/.venv/bin/python'), '-m', 'uvicorn',
            'lakematch_review.backend.app:app', '--host', '127.0.0.1', '--port', str(port)],
            cwd=ROOT / 'app', env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise RuntimeError('Acceptance app exited before readiness')
                try:
                    fetch()
                    return child
                except OSError:
                    time.sleep(.2)
            raise TimeoutError('Acceptance app did not become ready within 30 seconds')
        except BaseException:
            stop(child)
            raise

    def stop(child):
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)

    with (root / 'app-server.log').open('w') as log:
        child = start(log)
        try:
            run('node', 'app/acceptance/browser.mjs', root, url, timeout=90)
            before = fetch()
        finally:
            stop(child)
        child = start(log)
        try:
            after = fetch()
            assert len(after['reviews']) == 20 and after == before
            (root / 'restart-report.json').write_text(json.dumps({
                'status': 'passed', 'server': 'uvicorn', 'process_restart': True,
                'exact_snapshot_preserved': True, 'reviewed': 20,
                'label_set_sha256': after['label_set_sha256']}, indent=2) + '\n')
        finally:
            stop(child)
    run(sys.executable, 'app/acceptance/feedback.py', 'export', '--root', root)
    run(sys.executable, '-m', 'lakematch.cli', 'train', '--config', root / 'feedback.yaml', '--save-scores')
    run(sys.executable, 'app/acceptance/feedback.py', 'audit', '--root', root)
    for name in ('browser-report.json', 'restart-report.json', 'feedback-report.json',
                 'review-desktop.png', 'statistics-desktop.png', 'review-mobile.png'):
        shutil.copy2(root / name, report / name)
    print('Fresh synthetic review flow passed; test app stopped; interactive demo untouched.', flush=True)


if __name__ == '__main__':
    main()
