# Databricks notebook source
"""Two-task synthetic ZR-5 acceptance; tasks get separate Python sessions."""
import json
import os
from pathlib import Path
import sys

root = dbutils.widgets.get("root")
workspace = dbutils.widgets.get("workspace_root")
sys.path[:0] = [workspace + "/src", workspace + "/tools"]
os.environ["MLFLOW_DFS_TMP"] = root + "/dfs_tmp"
Path(os.environ["MLFLOW_DFS_TMP"]).mkdir(parents=True, exist_ok=True)
from tracking_canary import train, reload

mode = dbutils.widgets.get("mode")
result = train(Path(root), remote=True) if mode == "train" else reload(root)
dbutils.notebook.exit(json.dumps(result))
