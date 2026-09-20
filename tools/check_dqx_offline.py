#!/usr/bin/env python3
import runpy

from offline_run import assert_offline

assert_offline()
runpy.run_path('integration/check_dqx.py', run_name='__main__')
