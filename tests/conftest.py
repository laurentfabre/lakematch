"""The suite runs twice: `pytest` (classic local session) and `LAKEMATCH_TEST_CONNECT=1 pytest` (a local Spark Connect
server, which behaves like serverless: no SparkContext, analysis at execution). scripts/test.sh runs both."""
import os

import pytest

from lakematch import config
from lakematch.runtime import Runtime, session

CONNECT = os.environ.get("LAKEMATCH_TEST_CONNECT") == "1"


def make_cfg(tmp_path=None, **user):
    user.setdefault("runtime", {})
    user["runtime"] = {"cores": 2, "shuffle_partitions": 4, "connect": CONNECT, **user["runtime"]}
    if tmp_path is not None:
        user.setdefault("storage", {"root": str(tmp_path / "data")})
    return config.build(user, tmp_path)


@pytest.fixture(scope="session")
def spark():
    s = session(make_cfg())
    yield s
    s.stop()


@pytest.fixture
def rt(spark, tmp_path):
    r = Runtime(make_cfg(tmp_path), spark)
    yield r
    r.close()
