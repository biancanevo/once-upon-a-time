"""
StorytellerState - Thread-safe state management for the storyteller application.

Manages selected animals, current story, RFID card database, and audio state.
"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AudioSegment:
    """Represents a single audio segment with text and audio path."""

    text: str
    audio_path: str
    duration: float = 0.0


@dataclass
class Story:
    """Represents a generated story with text and audio segments."""

    full_text: str
    audio_segments: List[AudioSegment] = field(default_factory=list)
    animals: List[str] = field(default_factory=list)
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class StorytellerState:
    """
    Thread-safe state management for the storyteller application.

    Manages:
    - Selected animals from RFID cards
    - Current story and audio state
    - RFID card database
    - Playback state
    """

    def __init__(self, cards_db_path: str = "cards_db.json"):
        """
        Initialize the storyteller state.

        Args:
            cards_db_path: Path to the JSON file storing RFID card mappings.
        """
        self._lock = threading.RLock()
        self._cards_db_path = Path(cards_db_path)

        # State variables
        self._selected_animals: List[str] = []
        self._current_story: Optional[Story] = None
        self._cards_db: Dict[str, Dict[str, Any]] = {}
        self._is_generating: bool = False
        self._is_playing: bool = False
        self._current_segment_index: int = 0
        self._last_rfid_uid: Optional[str] = None
        self._last_rfid_time: Optional[datetime] = None

        # Load cards database
        self._load_cards_db()

        logger.info("StorytellerState initialized")

    def _load_cards_db(self) -> None:
        """Load the cards database from JSON file."""
        if self._cards_db_path.exists():
            try:
                with open(self._cards_db_path, "r") as f:
                    self._cards_db = json.load(f)
                logger.info(f"Loaded {len(self._cards_db)} cards from database")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load cards database: {e}")
                self._cards_db = {}
        else:
            logger.info("No cards database found, starting fresh")
            self._cards_db = {}

    def save_cards_db(self) -> None:
        """Save the cards database to JSON file."""
        with self._lock:
            try:
                with open(self._cards_db_path, "w") as f:
                    json.dump(self._cards_db, f, indent=2)
                logger.info(f"Saved {len(self._cards_db)} cards to database")
            except IOError as e:
                logger.error(f"Failed to save cards database: {e}")

    # Animal management
    @property
    def selected_animals(self) -> List[str]:
        """Get the list of currently selected animals."""
        with self._lock:
            return self._selected_animals.copy()

    def add_animal(self, animal: str) -> None:
        """Add an animal to the selection."""
        with self._lock:
            if animal and animal not in self._selected_animals:
                self._selected_animals.append(animal)
                logger.info(f"Added animal: {animal}")

    def remove_animal(self, animal: str) -> None:
        """Remove an animal from the selection."""
        with self._lock:
            if animal in self._selected_animals:
                self._selected_animals.remove(animal)
                logger.info(f"Removed animal: {animal}")

    def clear_animals(self) -> None:
        """Clear all selected animals."""
        with self._lock:
            self._selected_animals.clear()
            logger.info("Cleared all animals")

    # Story management
    @property
    def current_story(self) -> Optional[Story]:
        """Get the current story."""
        with self._lock:
            return self._current_story

    def set_story(self, story: Story) -> None:
        """Set the current story."""
        with self._lock:
            self._current_story = story
            logger.info(f"Set new story with {len(story.audio_segments)} segments")

    def clear_story(self) -> None:
        """Clear the current story."""
        with self._lock:
            self._current_story = None
            self._current_segment_index = 0
            logger.info("Cleared current story")

    # Generation state
    @property
    def is_generating(self) -> bool:
        """Check if a story is currently being generated."""
        with self._lock:
            return self._is_generating

    def set_generating(self, value: bool) -> None:
        """Set the generating state."""
        with self._lock:
            self._is_generating = value
            logger.debug(f"Generation state: {value}")

    # Playback state
    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        with self._lock:
            return self._is_playing

    def set_playing(self, value: bool) -> None:
        """Set the playing state."""
        with self._lock:
            self._is_playing = value
            logger.debug(f"Playback state: {value}")

    @property
    def current_segment_index(self) -> int:
        """Get the current audio segment index."""
        with self._lock:
            return self._current_segment_index

    def set_segment_index(self, index: int) -> None:
        """Set the current audio segment index."""
        with self._lock:
            self._current_segment_index = index

    def advance_segment(self) -> bool:
        """
        Advance to the next audio segment.

        Returns:
            True if there are more segments, False if playback complete.
        """
        with self._lock:
            if self._current_story and self._current_segment_index < len(
                self._current_story.audio_segments
            ) - 1:
                self._current_segment_index += 1
                return True
            return False

    # RFID card management
    @property
    def cards_db(self) -> Dict[str, Dict[str, Any]]:
        """Get the cards database."""
        with self._lock:
            return self._cards_db.copy()

    def register_card(self, uid: str, animal: str) -> None:
        """
        Register a new RFID card with an animal.

        Args:
            uid: The RFID card UID.
            animal: The animal name to associate with the card.
        """
        with self._lock:
            self._cards_db[uid] = {
                "animal": animal,
                "registered": datetime.now().isoformat(),
            }
            self.save_cards_db()
            logger.info(f"Registered card {uid} with animal {animal}")

    def unregister_card(self, uid: str) -> bool:
        """
        Remove an RFID card from the database.

        Args:
            uid: The RFID card UID to remove.

        Returns:
            True if the card was removed, False if not found.
        """
        with self._lock:
            if uid in self._cards_db:
                del self._cards_db[uid]
                self.save_cards_db()
                logger.info(f"Unregistered card {uid}")
                return True
            return False

    def get_animal_for_card(self, uid: str) -> Optional[str]:
        """
        Get the animal associated with an RFID card.

        Args:
            uid: The RFID card UID.

        Returns:
            The animal name or None if not found.
        """
        with self._lock:
            card = self._cards_db.get(uid)
            return card["animal"] if card else None

    # RFID debounce
    def should_process_card(self, uid: str, debounce_time: float = 1.5) -> bool:
        """
        Check if an RFID card should be processed (debounce logic).

        Args:
            uid: The RFID card UID.
            debounce_time: Minimum time between readings of the same card.

        Returns:
            True if the card should be processed, False otherwise.
        """
        with self._lock:
            now = datetime.now()
            if (
                self._last_rfid_uid == uid
                and self._last_rfid_time
                and (now - self._last_rfid_time).total_seconds() < debounce_time
            ):
                return False

            self._last_rfid_uid = uid
            self._last_rfid_time = now
            return True

    # Serialization
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for API responses."""
        with self._lock:
            story_dict = None
            if self._current_story:
                story_dict = {
                    "full_text": self._current_story.full_text,
                    "audio_segments": [
                        {"text": seg.text, "audio": seg.audio_path}
                        for seg in self._current_story.audio_segments
                    ],
                    "animals": self._current_story.animals,
                    "status": self._current_story.status,
                    "created_at": self._current_story.created_at,
                }

            return {
                "selected_animals": self._selected_animals.copy(),
                "current_story": story_dict,
                "is_generating": self._is_generating,
                "is_playing": self._is_playing,
                "current_segment_index": self._current_segment_index,
            }
