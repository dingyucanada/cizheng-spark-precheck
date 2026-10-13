from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from cizheng_precheck.api import create_app
from cizheng_precheck.config import Settings, ROOT


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, model_url="", model="", enable_online=False)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        c.headers["x-cz-csrf"] = c.get("/api/status").json()["csrf"]
        yield c


def photo_bytes(identifier=48450, view=1):
    return (ROOT / "knowledge/photos" / f"met-{identifier}-{view:02}.jpg").read_bytes()
