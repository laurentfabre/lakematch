import os

import pytest

from lakematch.config import from_dict
from lakematch.runtime import create_session


@pytest.fixture(scope="session")
def spark():
    cfg = from_dict({"entity": {"fields": {"name": {"type": "person_name"}}},
                     "runtime": {"connect": os.environ.get("LAKEMATCH_TEST_MODE") == "connect",
                                 "remote": os.environ.get("LAKEMATCH_CONNECT_URL", "sc://localhost:15002")}})
    session = create_session(cfg)
    yield session
    session.stop()


@pytest.fixture
def config():
    return from_dict({"entity": {"fields": {"name": {"type": "person_name"}, "code": {"type": "code"}}},
                      "candidates": {"q": 2, "k": 3, "gram_cap": 20},
                      "features": {"embeddings": {"provider": "none"}},
                      "matcher": {"max_iter": 3, "max_depth": 2},
                      "decision": {"threshold": 0.5}})
