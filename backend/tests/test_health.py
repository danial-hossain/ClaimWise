"""Automated test cases for Health and Readiness endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify GET / returns valid service metadata and tagline."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "ClaimWise API"
        assert "Evidence first" in data["tagline"]
        assert data["health"] == "/api/v1/health"
        assert data["ready"] == "/api/v1/ready"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify GET /api/v1/health returns 200 and healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app_name"] == "ClaimWise API"
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_ready_endpoint():
    """Verify GET /api/v1/ready returns readiness payload and subsystem status without crashing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert "services" in data
        assert "api_server" in data["services"]
        assert data["services"]["api_server"]["status"] == "healthy"
        assert "database" in data["services"]
        assert "supabase_auth" in data["services"]
