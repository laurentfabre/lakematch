# Databricks notebook source
"""A fresh clustering task loads the trained model and audits durable commits."""
import json
from pathlib import Path
import runpy
import sys

source_root = Path(dbutils.widgets.get('source_root'))
sys.path.insert(0, str(source_root))
implementation = runpy.run_path(str(source_root.parent / 'integration/check_remote_cluster.py'))
root = dbutils.widgets.get('root')
report = implementation['check'](spark, root, dbutils.widgets.get('schema'), root)
dbutils.notebook.exit(json.dumps(report))
