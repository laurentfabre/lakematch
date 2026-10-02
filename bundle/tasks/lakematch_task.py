"""Entry point of every lakematch job task on Databricks: puts the synced source tree on sys.path, then runs
lakematch.jobs (python lakematch_task.py <task> --config <yaml> [--src <dir>])."""
import os
import sys

argv = sys.argv[1:]
src = None
if "--src" in argv:
    i = argv.index("--src")
    src = argv[i + 1]
    argv = argv[:i] + argv[i + 2:]
if src is None:
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
sys.path.insert(0, os.path.abspath(src))

from lakematch.jobs import main  # noqa: E402

rc = main(argv)
if rc:                       # a serverless task runs in an IPython shell: SystemExit(0) is reported as a failure
    sys.exit(rc)
