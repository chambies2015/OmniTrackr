"""
Tests for Custom Tab API endpoints.
"""
import pytest
import json
from io import BytesIO


class TestCustomTabEndpoints:
    """Test custom tab API endpoints."""
    
    def test_create_custom_tab(self, authenticated_client):
        """Test creating a custom tab."""
        tab_data = {
            "name": "Books",
            "source_type": "none",
            "allow_uploads": True,
            "fields": [
                {"key": "author", "label": "Author", "field_type": "text", "required": True},
                {"key": "year", "label": "Year", "field_type": "number", "required": False}
            ]
        }
        response = authenticated_client.post("/custom-tabs/", json=tab_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == tab_data["name"]
        assert data["source_type"] == tab_data["source_type"]
        assert len(data["fields"]) == 2
        assert "id" in data
        assert "slug" in data
    
    def test_list_custom_tabs(self, authenticated_client):
        """Test listing custom tabs."""
        tab_data = {
            "name": "Comics",
            "source_type": "none",
            "allow_uploads": False,
            "fields": []
        }
        authenticated_client.post("/custom-tabs/", json=tab_data)
        
        response = authenticated_client.get("/custom-tabs/")
        
        assert response.status_code == 200
        tabs = response.json()
        assert len(tabs) >= 1
        assert any(t["name"] == "Comics" for t in tabs)
    
    def test_get_custom_tab_by_id(self, authenticated_client):
        """Test retrieving a specific custom tab."""
        tab_data = {
            "name": "Test Tab",
            "source_type": "none",
            "allow_uploads": True,
            "fields": []
        }
        create_response = authenticated_client.post("/custom-tabs/", json=tab_data)
        tab_id = create_response.json()["id"]
        
        response = authenticated_client.get(f"/custom-tabs/{tab_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tab_id
        assert data["name"] == tab_data["name"]
    
    def test_update_custom_tab(self, authenticated_client):
        """Test updating a custom tab."""
        tab_data = {
            "name": "Original Name",
            "source_type": "none",
            "allow_uploads": True,
            "fields": []
        }
        create_response = authenticated_client.post("/custom-tabs/", json=tab_data)
        tab_id = create_response.json()["id"]
        
        update_data = {"name": "Updated Name"}
        response = authenticated_client.put(f"/custom-tabs/{tab_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
    
    def test_delete_custom_tab(self, authenticated_client):
        """Test deleting a custom tab."""
        tab_data = {
            "name": "To Delete",
            "source_type": "none",
            "allow_uploads": False,
            "fields": []
        }
        create_response = authenticated_client.post("/custom-tabs/", json=tab_data)
        tab_id = create_response.json()["id"]
        
        response = authenticated_client.delete(f"/custom-tabs/{tab_id}")
        
        assert response.status_code == 200
        
        get_response = authenticated_client.get(f"/custom-tabs/{tab_id}")
        assert get_response.status_code == 404


class TestCustomTabItemEndpoints:
    """Test custom tab item API endpoints."""
    
    @pytest.fixture
    def custom_tab(self, authenticated_client):
        """Create a custom tab for testing."""
        tab_data = {
            "name": "Test Collection",
            "source_type": "none",
            "allow_uploads": True,
            "fields": [
                {"key": "year", "label": "Year", "field_type": "number", "required": False},
                {"key": "rating", "label": "Rating", "field_type": "rating", "required": False}
            ]
        }
        response = authenticated_client.post("/custom-tabs/", json=tab_data)
        return response.json()
    
    def test_create_custom_tab_item(self, authenticated_client, custom_tab):
        """Test creating a custom tab item."""
        item_data = {
            "title": "Test Item",
            "field_values": {
                "year": 2020,
                "rating": 8.5
            },
            "poster_url": None
        }
        response = authenticated_client.post(f"/custom-tabs/{custom_tab['id']}/items", json=item_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == item_data["title"]
        assert data["field_values"]["year"] == 2020
        assert data["field_values"]["rating"] == 8.5
        assert "id" in data
    
    def test_list_custom_tab_items(self, authenticated_client, custom_tab):
        """Test listing custom tab items."""
        item_data = {
            "title": "Item 1",
            "field_values": {},
            "poster_url": None
        }
        authenticated_client.post(f"/custom-tabs/{custom_tab['id']}/items", json=item_data)
        
        response = authenticated_client.get(f"/custom-tabs/{custom_tab['id']}/items")
        
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 1
        assert any(i["title"] == "Item 1" for i in items)
    
    def test_get_custom_tab_item_by_id(self, authenticated_client, custom_tab):
        """Test retrieving a specific custom tab item."""
        item_data = {
            "title": "Specific Item",
            "field_values": {},
            "poster_url": None
        }
        create_response = authenticated_client.post(f"/custom-tabs/{custom_tab['id']}/items", json=item_data)
        item_id = create_response.json()["id"]
        
        response = authenticated_client.get(f"/custom-tabs/{custom_tab['id']}/items/{item_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["title"] == item_data["title"]
    
    def test_update_custom_tab_item(self, authenticated_client, custom_tab):
        """Test updating a custom tab item."""
        item_data = {
            "title": "Original Title",
            "field_values": {"year": 2020},
            "poster_url": None
        }
        create_response = authenticated_client.post(f"/custom-tabs/{custom_tab['id']}/items", json=item_data)
        item_id = create_response.json()["id"]
        
        update_data = {
            "title": "Updated Title",
            "field_values": {"year": 2021, "rating": 9.0}
        }
        response = authenticated_client.put(f"/custom-tabs/{custom_tab['id']}/items/{item_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["field_values"]["year"] == 2021
        assert data["field_values"]["rating"] == 9.0
    
    def test_delete_custom_tab_item(self, authenticated_client, custom_tab):
        """Test deleting a custom tab item."""
        item_data = {
            "title": "To Delete",
            "field_values": {},
            "poster_url": None
        }
        create_response = authenticated_client.post(f"/custom-tabs/{custom_tab['id']}/items", json=item_data)
        item_id = create_response.json()["id"]
        
        response = authenticated_client.delete(f"/custom-tabs/{custom_tab['id']}/items/{item_id}")
        
        assert response.status_code == 200
        
        get_response = authenticated_client.get(f"/custom-tabs/{custom_tab['id']}/items/{item_id}")
        assert get_response.status_code == 404
    
    def test_create_item_with_required_field(self, authenticated_client):
        """Test creating an item with required field validation."""
        tab_data = {
            "name": "Required Field Tab",
            "source_type": "none",
            "allow_uploads": False,
            "fields": [
                {"key": "required_field", "label": "Required", "field_type": "text", "required": True}
            ]
        }
        tab_response = authenticated_client.post("/custom-tabs/", json=tab_data)
        tab_id = tab_response.json()["id"]
        
        item_data = {
            "title": "Test Item",
            "field_values": {},
            "poster_url": None
        }
        response = authenticated_client.post(f"/custom-tabs/{tab_id}/items", json=item_data)
        
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()
    
    def test_create_item_with_invalid_rating(self, authenticated_client):
        """Test creating an item with invalid rating value."""
        tab_data = {
            "name": "Rating Tab",
            "source_type": "none",
            "allow_uploads": False,
            "fields": [
                {"key": "rating", "label": "Rating", "field_type": "rating", "required": False}
            ]
        }
        tab_response = authenticated_client.post("/custom-tabs/", json=tab_data)
        tab_id = tab_response.json()["id"]
        
        item_data = {
            "title": "Test Item",
            "field_values": {"rating": 15},
            "poster_url": None
        }
        response = authenticated_client.post(f"/custom-tabs/{tab_id}/items", json=item_data)
        
        assert response.status_code == 400
        assert "rating" in response.json()["detail"].lower()


class TestCustomTabPosterEndpoints:
    """Test custom tab poster upload endpoints."""
    
    @pytest.fixture
    def custom_tab_with_uploads(self, authenticated_client):
        """Create a custom tab that allows uploads."""
        tab_data = {
            "name": "Poster Test Tab",
            "source_type": "none",
            "allow_uploads": True,
            "fields": []
        }
        response = authenticated_client.post("/custom-tabs/", json=tab_data)
        return response.json()
    
    def test_upload_poster(self, authenticated_client, custom_tab_with_uploads):
        """Test uploading a poster image."""
        item_data = {
            "title": "Item with Poster",
            "field_values": {},
            "poster_url": None
        }
        create_response = authenticated_client.post(
            f"/custom-tabs/{custom_tab_with_uploads['id']}/items",
            json=item_data
        )
        item_id = create_response.json()["id"]
        
        image_data = BytesIO(b'\x89PNG\r\n\x1a\n' + b'0' * 100)
        files = {"file": ("test.png", image_data, "image/png")}
        
        response = authenticated_client.post(
            f"/custom-tabs/{custom_tab_with_uploads['id']}/items/{item_id}/poster",
            files=files
        )
        
        assert response.status_code in [200, 400]
    
    def test_upload_poster_not_allowed(self, authenticated_client):
        """Test uploading poster when uploads are not allowed."""
        tab_data = {
            "name": "No Upload Tab",
            "source_type": "none",
            "allow_uploads": False,
            "fields": []
        }
        tab_response = authenticated_client.post("/custom-tabs/", json=tab_data)
        tab_id = tab_response.json()["id"]
        
        item_data = {
            "title": "Test Item",
            "field_values": {},
            "poster_url": None
        }
        create_response = authenticated_client.post(f"/custom-tabs/{tab_id}/items", json=item_data)
        item_id = create_response.json()["id"]
        
        image_data = BytesIO(b'\x89PNG\r\n\x1a\n' + b'0' * 100)
        files = {"file": ("test.png", image_data, "image/png")}
        
        response = authenticated_client.post(
            f"/custom-tabs/{tab_id}/items/{item_id}/poster",
            files=files
        )
        
        assert response.status_code == 403
