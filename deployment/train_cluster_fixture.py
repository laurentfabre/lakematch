# Databricks notebook source
"""A bounded training task for the remote identity-publication fixture."""
import json
from pathlib import Path
import runpy
import sys

source_root = Path(dbutils.widgets.get('source_root'))
sys.path.insert(0, str(source_root))
implementation = runpy.run_path(str(source_root.parent / 'integration/check_remote_cluster.py'))
report = implementation['train'](spark, dbutils.widgets.get('root'), dbutils.widgets.get('schema'))
dbutils.notebook.exit(json.dumps(report))
