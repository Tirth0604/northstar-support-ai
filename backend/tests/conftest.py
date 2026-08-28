import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("UPLOAD_DIRECTORY", str(tmp_path / "uploads"))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(tmp_path / "vectors"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.db.session as session

    session.engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    session.SessionLocal = sessionmaker(bind=session.engine, autocommit=False, autoflush=False)
    from app.services.container import services

    services.cache_clear()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    services.cache_clear()
