"""Definition-time configuration only; no Spark action or workspace API calls."""
import json
from pathlib import Path
import sys

from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()
if spark is None:
    raise RuntimeError('A pipeline-managed Spark session is required')
sys.path.insert(0, spark.conf.get('lakematch.source_root'))

from lakematch.config import from_dict

ROOT = Path(spark.conf.get('lakematch.input_root'))


def load(variant):
    raw = json.loads((ROOT / variant / 'config.json').read_text())
    raw['quality']['engine'] = spark.conf.get('lakematch.quality_engine')
    raw['paid_features']['app'] = spark.conf.get('lakematch.app_enabled') == 'true'
    raw['paid_features']['genie'] = spark.conf.get('lakematch.genie_enabled') == 'true'
    state = json.loads((ROOT / variant / 'native-state.json').read_text())
    return from_dict(raw), state
