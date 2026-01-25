"""Tests for StorytellerState class."""

import json
import threading
from pathlib import Path

import pytest

from raspi_storyteller.state import StorytellerState, Story, AudioSegment


class TestStorytellerState:
    """Tests for StorytellerState functionality."""

    def test_init(self, temp_cards_db):
        """Test state initialization."""
        state = StorytellerState(cards_db_path=temp_cards_db)
        assert state.selected_animals == []
        assert state.current_story is None
        assert state.is_generating is False
        assert state.is_playing is False

    def test_add_animal(self, state):
        """Test adding animals to selection."""
        state.add_animal("cat")
        state.add_animal("dog")
        assert state.selected_animals == ["cat", "dog"]

    def test_add_duplicate_animal(self, state):
        """Test that duplicate animals are not added."""
        state.add_animal("cat")
        state.add_animal("cat")
        assert state.selected_animals == ["cat"]

    def test_add_empty_animal(self, state):
        """Test that empty animal names are not added."""
        state.add_animal("")
        state.add_animal(None)
        assert state.selected_animals == []

    def test_remove_animal(self, state):
        """Test removing animals from selection."""
        state.add_animal("cat")
        state.add_animal("dog")
        state.remove_animal("cat")
        assert state.selected_animals == ["dog"]

    def test_clear_animals(self, state):
        """Test clearing all animals."""
        state.add_animal("cat")
        state.add_animal("dog")
        state.clear_animals()
        assert state.selected_animals == []

    def test_set_story(self, state):
        """Test setting current story."""
        story = Story(
            full_text="Once upon a time...",
            audio_segments=[AudioSegment(text="Once upon a time", audio_path="/tmp/test.mp3")],
            animals=["cat"],
            status="success",
        )
        state.set_story(story)
        assert state.current_story is not None
        assert state.current_story.full_text == "Once upon a time..."

    def test_clear_story(self, state):
        """Test clearing current story."""
        story = Story(full_text="Test", animals=["cat"])
        state.set_story(story)
        state.clear_story()
        assert state.current_story is None

    def test_generation_state(self, state):
        """Test generation state management."""
        assert state.is_generating is False
        state.set_generating(True)
        assert state.is_generating is True
        state.set_generating(False)
        assert state.is_generating is False

    def test_playback_state(self, state):
        """Test playback state management."""
        assert state.is_playing is False
        state.set_playing(True)
        assert state.is_playing is True
        state.set_playing(False)
        assert state.is_playing is False

    def test_register_card(self, state):
        """Test RFID card registration (legacy)."""
        state.register_card_legacy("123456", "cat")
        assert "123456" in state.cards_db
        # Legacy format should have name/species
        card_data = state.cards_db["123456"]
        assert card_data.get("species") == "cat" or card_data.get("animal") == "cat"

    def test_unregister_card(self, state):
        """Test RFID card unregistration."""
        state.register_card_legacy("123456", "cat")
        result = state.unregister_card("123456")
        assert result is True
        assert "123456" not in state.cards_db

    def test_unregister_nonexistent_card(self, state):
        """Test unregistering a card that doesn't exist."""
        result = state.unregister_card("nonexistent")
        assert result is False

    def test_get_animal_for_card(self, state):
        """Test getting animal for a card."""
        state.register_card_legacy("123456", "cat")
        animal = state.get_animal_for_card("123456")
        assert animal == "cat"

    def test_get_animal_for_unknown_card(self, state):
        """Test getting animal for an unknown card."""
        animal = state.get_animal_for_card("unknown")
        assert animal is None

    def test_cards_db_persistence(self, temp_cards_db):
        """Test that cards database is persisted to file."""
        state = StorytellerState(cards_db_path=temp_cards_db)
        state.register_card_legacy("123456", "cat")

        # Create new state instance and verify data is loaded
        state2 = StorytellerState(cards_db_path=temp_cards_db)
        assert "123456" in state2.cards_db
        # Check for either new or legacy format
        card_data = state2.cards_db["123456"]
        assert card_data.get("species") == "cat" or card_data.get("animal") == "cat"

    def test_should_process_card_debounce(self, state):
        """Test RFID card debounce logic."""
        # First read should process
        assert state.should_process_card("123", debounce_time=1.0) is True
        # Immediate second read should not process
        assert state.should_process_card("123", debounce_time=1.0) is False
        # Different card should process
        assert state.should_process_card("456", debounce_time=1.0) is True

    def test_segment_advancement(self, state):
        """Test audio segment advancement."""
        story = Story(
            full_text="Test",
            audio_segments=[
                AudioSegment(text="Seg 1", audio_path="/tmp/1.mp3"),
                AudioSegment(text="Seg 2", audio_path="/tmp/2.mp3"),
            ],
            animals=["cat"],
        )
        state.set_story(story)

        assert state.current_segment_index == 0
        assert state.advance_segment() is True
        assert state.current_segment_index == 1
        assert state.advance_segment() is False  # No more segments

    def test_to_dict(self, state):
        """Test state serialization."""
        state.add_animal("cat")
        state.set_generating(True)

        data = state.to_dict()
        assert data["selected_animals"] == ["cat"]
        assert data["is_generating"] is True
        assert data["current_story"] is None

    def test_thread_safety(self, state):
        """Test thread-safe operations."""
        results = []

        def add_animals(count):
            for i in range(count):
                state.add_animal(f"animal_{threading.current_thread().name}_{i}")
            results.append(len(state.selected_animals))

        threads = [
            threading.Thread(target=add_animals, args=(10,), name=f"t{i}")
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All animals should be added
        assert len(state.selected_animals) == 50
