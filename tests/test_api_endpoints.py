import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint_json(async_client: AsyncClient):
    """Verifies that root endpoint returns API metadata when queried as JSON."""
    response = await async_client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "smart-educator"
    assert "version" in data
    assert data["docs_url"] == "/docs"


@pytest.mark.asyncio
async def test_web_interface_html(async_client: AsyncClient):
    """Verifies that the web interface HTML is served for browser requests."""
    response = await async_client.get("/app")
    assert response.status_code == 200
    assert "Smart-Educator" in response.text
    assert "<!DOCTYPE html>" in response.text


@pytest.mark.asyncio
async def test_health_liveness(async_client: AsyncClient):
    """Verifies the fast process liveness probe."""
    response = await async_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_health_general(async_client: AsyncClient):
    """Verifies high-level health endpoint."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "smart-educator"


@pytest.mark.asyncio
async def test_readiness_probe(async_client: AsyncClient):
    """Verifies the deep dependency readiness probe."""
    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "dependencies" in data
    assert "database" in data["dependencies"]
    assert "redis" in data["dependencies"]
    assert "chromadb" in data["dependencies"]


@pytest.mark.asyncio
async def test_recommendations_empty_query_fails(async_client: AsyncClient):
    """Verifies that empty recommendation queries fail with 400 Bad Request."""
    response = await async_client.post(
        "/api/v1/recommendations/questions",
        json={"query": "   ", "top_k": 5},
    )
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["error"]


@pytest.mark.asyncio
async def test_dataset_export(async_client: AsyncClient):
    """Verifies that dataset export returns a list of records."""
    response = await async_client.get("/api/v1/dataset/export")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
