#!/usr/bin/env python3
from pathlib import Path
import sys

import pytest
from offline_run import assert_offline

assert_offline()
Path('data/native_ml').mkdir(parents=True, exist_ok=True)
sys.exit(pytest.main(['-q',
    'tests/test_features.py::test_prepared_features_accept_databricks_quality_and_app_configuration',
    '--junitxml=data/native_ml/feature-regression.xml']))
