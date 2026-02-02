"""
Tests for the satellite data viewer backend.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_get_collections():
    """Test getting available collections."""
    response = client.get("/collections")
    assert response.status_code == 200
    data = response.json()
    assert "collections" in data
    assert len(data["collections"]) > 0
    
    # Check that sentinel-2 is in the list
    collection_ids = [c["id"] for c in data["collections"]]
    assert "sentinel-2-l2a" in collection_ids


def test_get_collection_assets():
    """Test getting assets for a specific collection."""
    response = client.get("/collections/sentinel-2-l2a/assets")
    assert response.status_code == 200
    data = response.json()
    assert data["collection_id"] == "sentinel-2-l2a"
    assert "visual" in data["assets"]
    assert "B04" in data["assets"]


def test_get_collection_assets_not_found():
    """Test getting assets for a non-existent collection."""
    response = client.get("/collections/non-existent/assets")
    assert response.status_code == 404


def test_download_missing_fields():
    """Test download endpoint with missing required fields."""
    response = client.post("/download", json={})
    assert response.status_code == 422  # Validation error


def test_download_invalid_collection():
    """Test download with invalid collection."""
    response = client.post("/download", json={
        "collection": "invalid-collection",
        "item_id": "test-item",
        "asset_key": "visual",
        "format": "geotiff"
    })
    # Should fail with 400 (invalid collection/asset)
    assert response.status_code == 400


# Integration tests (require network access)
@pytest.mark.integration
def test_download_sentinel2_visual():
    """
    Integration test: Download a Sentinel-2 visual tile.
    Requires network access to Microsoft Planetary Computer.
    """
    # This would need a valid item_id from MPC
    pass
