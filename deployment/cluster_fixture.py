# Databricks notebook source
"""A fresh clustering task loads the trained model and audits durable commits."""
import json
import os
from pathlib import Path
import runpy
import sys

source_root = Path(dbutils.widgets.get('source_root'))
sys.path.insert(0, str(source_root))
root = dbutils.widgets.get('root')
os.environ['MLFLOW_DFS_TMP'] = root + '/dfs_tmp'
Path(os.environ['MLFLOW_DFS_TMP']).mkdir(parents=True, exist_ok=True)
implementation = runpy.run_path(str(source_root.parent / 'integration/check_remote_cluster.py'))
report = implementation['check'](spark, root, dbutils.widgets.get('schema'), root)
dbutils.notebook.exit(json.dumps(report))
