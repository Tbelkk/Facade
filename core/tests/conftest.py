import os
import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORE))
os.environ.setdefault("FACADE_QUIET", "1")

from tests import legacy_site  # noqa: E402


@pytest.fixture()
def site():
    """A fresh legacy test site per test, so request logs don't mix."""
    srv = legacy_site.start()
    yield srv
    srv.shutdown()


@pytest.fixture()
def creds():
    return {"username": legacy_site.USER, "password": legacy_site.PASSWORD}
