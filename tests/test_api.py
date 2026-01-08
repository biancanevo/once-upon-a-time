"""Tests for API endpoints."""

import json

import pytest


class TestStoryAPI:
    """Tests for story-related API endpoints."""

    def test_get_current_story(self, client):
        """Test GET /api/story/current."""
        response = client.get("/api/story/current")
        assert response.status_code == 200

        data = response.get_json()
        assert "selected_animals" in data
        assert "current_story" in data
        assert "is_generating" in data
        assert "is_playing" in data

    def test_generate_story_no_animals(self, client):
        """Test story generation without animals returns error."""
        response = client.post(
            "/api/story/generate",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

        data = response.get_json()
        assert data["status"] == "error"

    def test_generate_story_with_animals(self, client):
        """Test story generation with animals."""
        response = client.post(
            "/api/story/generate",
            json={"animals": ["cat", "dog"]},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] in ("success", "partial")
        assert "full_text" in data
        assert "audio_segments" in data
        assert data["animals"] == ["cat", "dog"]


class TestCardAPI:
    """Tests for card management API endpoints."""

    def test_list_cards_empty(self, client):
        """Test GET /api/cards when empty."""
        response = client.get("/api/cards")
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, dict)

    def test_save_card(self, client):
        """Test POST /api/cards/save."""
        response = client.post(
            "/api/cards/save",
            json={"uid": "123456", "animal": "cat"},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "saved"
        assert data["uid"] == "123456"
        assert data["animal"] == "cat"

    def test_save_card_missing_fields(self, client):
        """Test POST /api/cards/save with missing fields."""
        response = client.post(
            "/api/cards/save",
            json={"uid": "123456"},  # Missing animal
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_delete_card(self, client):
        """Test DELETE /api/cards/delete/<uid>."""
        # First save a card
        client.post(
            "/api/cards/save",
            json={"uid": "to_delete", "animal": "dog"},
            content_type="application/json",
        )

        # Then delete it
        response = client.delete("/api/cards/delete/to_delete")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "deleted"

    def test_delete_nonexistent_card(self, client):
        """Test deleting a card that doesn't exist."""
        response = client.delete("/api/cards/delete/nonexistent")
        assert response.status_code == 404


class TestAnimalAPI:
    """Tests for animal management API endpoints."""

    def test_get_selected_animals(self, client):
        """Test GET /api/animals."""
        response = client.get("/api/animals")
        assert response.status_code == 200

        data = response.get_json()
        assert "animals" in data
        assert isinstance(data["animals"], list)

    def test_add_animal(self, client):
        """Test POST /api/animals."""
        response = client.post(
            "/api/animals",
            json={"animal": "elephant"},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "added"
        assert "elephant" in data["animals"]

    def test_add_animal_missing_name(self, client):
        """Test adding animal without name."""
        response = client.post(
            "/api/animals",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_remove_animal(self, client):
        """Test DELETE /api/animals/<animal>."""
        # First add an animal
        client.post(
            "/api/animals",
            json={"animal": "tiger"},
            content_type="application/json",
        )

        # Then remove it
        response = client.delete("/api/animals/tiger")
        assert response.status_code == 200

        data = response.get_json()
        assert "tiger" not in data["animals"]

    def test_clear_animals(self, client):
        """Test POST /api/animals/clear."""
        # Add some animals first
        client.post("/api/animals", json={"animal": "cat"})
        client.post("/api/animals", json={"animal": "dog"})

        # Clear all
        response = client.post("/api/animals/clear")
        assert response.status_code == 200

        data = response.get_json()
        assert data["animals"] == []


class TestVoiceAPI:
    """Tests for voice-related API endpoints."""

    def test_listen_voice(self, client):
        """Test POST /api/voice/listen."""
        response = client.post(
            "/api/voice/listen",
            json={"timeout": 3},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert "text" in data
        assert "animals" in data
        assert "status" in data

    def test_get_voice_languages(self, client):
        """Test GET /api/voice/languages."""
        response = client.get("/api/voice/languages")
        assert response.status_code == 200

        data = response.get_json()
        assert "languages" in data
        assert "current" in data

    def test_set_voice_language(self, client):
        """Test POST /api/voice/language."""
        response = client.post(
            "/api/voice/language",
            json={"language": "en-US"},
            content_type="application/json",
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "success"
        assert data["language"] == "en-US"


class TestStatusAPI:
    """Tests for status API endpoints."""

    def test_get_status(self, client):
        """Test GET /api/status."""
        response = client.get("/api/status")
        assert response.status_code == 200

        data = response.get_json()
        assert "state" in data
        assert "tts_provider" in data
        assert "cache" in data

    def test_clear_cache(self, client):
        """Test POST /api/cache/clear."""
        response = client.post("/api/cache/clear")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "cleared"


class TestWebRoutes:
    """Tests for web page routes."""

    def test_index_page(self, client):
        """Test GET / returns HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data

    def test_manage_page(self, client):
        """Test GET /manage returns HTML."""
        response = client.get("/manage")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data

    def test_voice_test_page(self, client):
        """Test GET /voice_test returns HTML."""
        response = client.get("/voice_test")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data

    def test_status_page(self, client):
        """Test GET /status returns HTML."""
        response = client.get("/status")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data
