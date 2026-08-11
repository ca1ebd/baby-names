import pytest
from fastapi.testclient import TestClient

from babynames_api.db import get_session
from babynames_api.main import app


@pytest.fixture(autouse=True)
def clean_overrides():
    """Ensure dependency overrides are cleaned up after each test"""
    yield
    app.dependency_overrides.clear()


def test_health_returns_ok_when_database_reachable(db_session):
    """GET /health should return 200 with ok status when database is reachable"""
    # Override with working test database session
    def get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = get_test_session

    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"


def test_health_returns_degraded_when_database_unavailable():
    """GET /health should return 200 with degraded status when database errors"""

    def mock_get_session():
        class MockSession:
            def execute(self, stmt):
                raise Exception("Database connection failed")

        yield MockSession()

    # Use FastAPI's dependency override
    app.dependency_overrides[get_session] = mock_get_session

    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "error"
