"""
StorytellerState - Thread-safe state management for the storyteller application.

Manages selected animals, current story, RFID card database, and audio state.
"""

import json
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils.logger import get_logger

logger = get_logger(__name__)


# Card type enumeration
class CardType(str, Enum):
    CHARACTER = "character"
    ENVIRONMENT = "environment"
    MORAL_LESSON = "moral_lesson"


# Character role enumeration
class CharacterRole(str, Enum):
    MAIN = "main"
    SECONDARY = "secondary"
    FELON = "felon"
    EVIL = "evil"


# Default species for each card type
DEFAULT_SPECIES = {
    CardType.CHARACTER: [
        "dog", "cat", "little boy", "little girl", "dragon", "wolf", "witch",
        "wizard", "troll", "pig", "donkey", "princess", "prince", "knight",
        "fairy", "elf", "unicorn", "rabbit", "bear", "fox", "owl", "mouse",
        "frog", "lion", "turtle", "squirrel"
    ],
    CardType.ENVIRONMENT: [
        "village", "city", "park", "forest", "mountain", "lake", "sea", "beach",
        "castle", "cave", "meadow", "river", "desert", "jungle", "island",
        "garden", "farm", "tower", "bridge", "waterfall", "valley", "swamp"
    ],
    CardType.MORAL_LESSON: [
        "friendship", "sharing", "caring", "brotherhood", "nature", "braveness",
        "honesty", "kindness", "respect", "patience", "perseverance", "gratitude",
        "forgiveness", "teamwork", "responsibility", "empathy", "generosity",
        "humility", "loyalty", "courage", "love", "acceptance"
    ],
}


@dataclass
class AudioSegment:
    """Represents a single audio segment with text and audio path."""

    text: str
    audio_path: str
    duration: float = 0.0


@dataclass
class Card:
    """Represents an RFID card with type and species."""

    uid: str
    card_type: CardType
    species: str
    name: Optional[str] = None  # Name used in story (not required for moral lessons)
    role: Optional[CharacterRole] = None  # Only for character cards
    registered: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "card_type": self.card_type.value,
            "species": self.species,
            "name": self.name,
            "role": self.role.value if self.role else None,
            "registered": self.registered,
        }

    @classmethod
    def from_dict(cls, uid: str, data: Dict[str, Any]) -> "Card":
        """Create Card from dictionary."""
        # Handle legacy cards that only have "animal" field
        if "animal" in data and "card_type" not in data:
            return cls(
                uid=uid,
                card_type=CardType.CHARACTER,
                species=data["animal"],
                name=data["animal"],
                role=CharacterRole.MAIN,
                registered=data.get("registered", datetime.now().isoformat()),
            )

        return cls(
            uid=uid,
            card_type=CardType(data["card_type"]),
            species=data["species"],
            name=data.get("name"),
            role=CharacterRole(data["role"]) if data.get("role") else None,
            registered=data.get("registered", datetime.now().isoformat()),
        )


@dataclass
class SelectedCard:
    """Represents a card currently selected for story generation."""

    card: Card
    role: Optional[CharacterRole] = None  # Override role for this story session

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "uid": self.card.uid,
            "card_type": self.card.card_type.value,
            "species": self.card.species,
            "name": self.card.name,
            "role": (self.role or self.card.role).value if (self.role or self.card.role) else None,
        }


@dataclass
class Story:
    """Represents a generated story with text and audio segments."""

    full_text: str
    audio_segments: List[AudioSegment] = field(default_factory=list)
    animals: List[str] = field(default_factory=list)
    characters: List[Dict[str, Any]] = field(default_factory=list)
    environment: Optional[str] = None
    moral_lesson: Optional[str] = None
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class StorytellerState:
    """
    Thread-safe state management for the storyteller application.

    Manages:
    - Selected cards from RFID (characters, environments, moral lessons)
    - Current story and audio state
    - RFID card database
    - Species metadata (custom characters, environments, lessons)
    - Playback state
    """

    def __init__(self, cards_db_path: str = "cards_db.json", species_db_path: str = "species_db.json"):
        """
        Initialize the storyteller state.

        Args:
            cards_db_path: Path to the JSON file storing RFID card mappings.
            species_db_path: Path to the JSON file storing custom species.
        """
        self._lock = threading.RLock()
        self._cards_db_path = Path(cards_db_path)
        self._species_db_path = Path(species_db_path)

        # State variables
        self._selected_animals: List[str] = []  # Legacy compatibility
        self._selected_cards: List[SelectedCard] = []  # New card system
        self._current_story: Optional[Story] = None
        self._cards_db: Dict[str, Dict[str, Any]] = {}
        self._species_db: Dict[str, List[str]] = {}  # Custom species by type
        self._is_generating: bool = False
        self._is_playing: bool = False
        self._current_segment_index: int = 0
        self._last_rfid_uid: Optional[str] = None
        self._last_rfid_time: Optional[datetime] = None
        self._story_length_minutes: int = 5  # Default story duration

        # Load databases
        self._load_cards_db()
        self._load_species_db()

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

    def _load_species_db(self) -> None:
        """Load the species database from JSON file."""
        if self._species_db_path.exists():
            try:
                with open(self._species_db_path, "r") as f:
                    self._species_db = json.load(f)
                logger.info(f"Loaded custom species from database")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load species database: {e}")
                self._species_db = {}
        else:
            logger.info("No species database found, using defaults")
            self._species_db = {}

    def save_cards_db(self) -> None:
        """Save the cards database to JSON file."""
        with self._lock:
            try:
                with open(self._cards_db_path, "w") as f:
                    json.dump(self._cards_db, f, indent=2)
                logger.info(f"Saved {len(self._cards_db)} cards to database")
            except IOError as e:
                logger.error(f"Failed to save cards database: {e}")

    def save_species_db(self) -> None:
        """Save the species database to JSON file."""
        with self._lock:
            try:
                with open(self._species_db_path, "w") as f:
                    json.dump(self._species_db, f, indent=2)
                logger.info("Saved species database")
            except IOError as e:
                logger.error(f"Failed to save species database: {e}")

    # Species management
    def get_species_for_type(self, card_type: CardType) -> List[str]:
        """Get all species for a card type (defaults + custom)."""
        with self._lock:
            default_species = DEFAULT_SPECIES.get(card_type, [])
            custom_species = self._species_db.get(card_type.value, [])
            # Combine and deduplicate
            all_species = list(default_species) + [s for s in custom_species if s not in default_species]
            return sorted(all_species)

    def add_species(self, card_type: CardType, species: str) -> bool:
        """Add a custom species to a card type."""
        with self._lock:
            species = species.strip().lower()
            if not species:
                return False

            # Check if already exists (in defaults or custom)
            if species in DEFAULT_SPECIES.get(card_type, []):
                return False

            if card_type.value not in self._species_db:
                self._species_db[card_type.value] = []

            if species not in self._species_db[card_type.value]:
                self._species_db[card_type.value].append(species)
                self.save_species_db()
                logger.info(f"Added custom species: {species} to {card_type.value}")
                return True
            return False

    def remove_species(self, card_type: CardType, species: str) -> bool:
        """Remove a custom species (cannot remove defaults)."""
        with self._lock:
            species = species.strip().lower()
            if card_type.value in self._species_db and species in self._species_db[card_type.value]:
                self._species_db[card_type.value].remove(species)
                self.save_species_db()
                logger.info(f"Removed custom species: {species} from {card_type.value}")
                return True
            return False

    def get_random_species(self, card_type: CardType) -> str:
        """Get a random species for a card type."""
        species_list = self.get_species_for_type(card_type)
        return random.choice(species_list) if species_list else ""

    # Animal management (legacy compatibility)
    @property
    def selected_animals(self) -> List[str]:
        """
        Get the list of currently selected animals (legacy compatibility).
        
        Reflected from selected character cards.
        """
        with self._lock:
            # Return names from selected character cards
            return [
                sc.card.name or sc.card.species
                for sc in self._selected_cards
                if sc.card.card_type == CardType.CHARACTER
            ]

    # Selected cards management
    @property
    def selected_cards(self) -> List[SelectedCard]:
        """Get the list of currently selected cards."""
        with self._lock:
            return self._selected_cards.copy()

    def add_selected_card(self, card: Card, role: Optional[CharacterRole] = None) -> None:
        """Add a card to the selection."""
        with self._lock:
            # Check if card is already selected
            for sc in self._selected_cards:
                if sc.card.uid == card.uid:
                    return  # Already selected

            # Use the card's defined role if available and no override provided
            if card.card_type == CardType.CHARACTER:
                if role is None:
                    # Respect the card's persistent role
                    if card.role:
                        role = card.role
                    else:
                        # Fallback for cards without a role (legacy or incomplete data)
                        # Default to Secondary unless it's the very first character
                        has_main = any(
                            (sc.role or sc.card.role) == CharacterRole.MAIN
                            for sc in self._selected_cards
                            if sc.card.card_type == CardType.CHARACTER
                        )
                        role = CharacterRole.SECONDARY if has_main else CharacterRole.MAIN

            self._selected_cards.append(SelectedCard(card=card, role=role))
            # Also add to legacy animals list for backwards compatibility
            if card.card_type == CardType.CHARACTER:
                name = card.name or card.species
                if name not in self._selected_animals:
                    self._selected_animals.append(name)
            logger.info(f"Added card: {card.uid} ({card.card_type.value}: {card.species})")

    def remove_selected_card(self, uid: str) -> None:
        """Remove a card from the selection by UID."""
        with self._lock:
            for sc in self._selected_cards[:]:
                if sc.card.uid == uid:
                    self._selected_cards.remove(sc)
                    # Also remove from legacy animals list
                    if sc.card.card_type == CardType.CHARACTER:
                        name = sc.card.name or sc.card.species
                        if name in self._selected_animals:
                            self._selected_animals.remove(name)
                    logger.info(f"Removed card: {uid}")
                    break

    def update_card_role(self, uid: str, role: CharacterRole) -> bool:
        """Update the role of a selected character card."""
        with self._lock:
            for sc in self._selected_cards:
                if sc.card.uid == uid and sc.card.card_type == CardType.CHARACTER:
                    sc.role = role
                    logger.info(f"Updated card role: {uid} -> {role.value}")
                    return True
            return False

    def clear_selected_cards(self) -> None:
        """Clear all selected cards."""
        with self._lock:
            self._selected_cards.clear()
            self._selected_animals.clear()
            logger.info("Cleared all selected cards")

    def get_selected_by_type(self, card_type: CardType) -> List[SelectedCard]:
        """Get selected cards filtered by type."""
        with self._lock:
            return [sc for sc in self._selected_cards if sc.card.card_type == card_type]

    def has_character_card(self) -> bool:
        """Check if at least one character card is selected."""
        with self._lock:
            return any(sc.card.card_type == CardType.CHARACTER for sc in self._selected_cards)

    def get_story_elements(self) -> Dict[str, Any]:
        """Get all story elements from selected cards."""
        with self._lock:
            characters = []
            environment = None
            moral_lesson = None

            for sc in self._selected_cards:
                if sc.card.card_type == CardType.CHARACTER:
                    characters.append({
                        "name": sc.card.name or sc.card.species,
                        "species": sc.card.species,
                        "role": (sc.role or sc.card.role or CharacterRole.SECONDARY).value,
                    })
                elif sc.card.card_type == CardType.ENVIRONMENT:
                    environment = sc.card.species
                elif sc.card.card_type == CardType.MORAL_LESSON:
                    moral_lesson = sc.card.species

            # If no environment or moral lesson selected, pick random ones
            if environment is None:
                environment = self.get_random_species(CardType.ENVIRONMENT)
            if moral_lesson is None:
                moral_lesson = self.get_random_species(CardType.MORAL_LESSON)

            return {
                "characters": characters,
                "environment": environment,
                "moral_lesson": moral_lesson,
            }

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

    def register_card(
        self,
        uid: str,
        card_type: CardType,
        species: str,
        name: Optional[str] = None,
        role: Optional[CharacterRole] = None,
    ) -> Card:
        """
        Register a new RFID card.

        Args:
            uid: The RFID card UID.
            card_type: The type of card (character, environment, moral_lesson).
            species: The species/instance (e.g., dog, forest, friendship).
            name: The name used in story (required for character/environment, not moral lesson).
            role: Character role (only for character cards).

        Returns:
            The created Card object.
        """
        with self._lock:
            card = Card(
                uid=uid,
                card_type=card_type,
                species=species,
                name=name,
                role=role if card_type == CardType.CHARACTER else None,
            )
            self._cards_db[uid] = card.to_dict()
            self.save_cards_db()
            logger.info(f"Registered card {uid}: {card_type.value} - {species}")
            return card

    def register_card_legacy(self, uid: str, animal: str) -> None:
        """
        Register a new RFID card with an animal (legacy compatibility).

        Args:
            uid: The RFID card UID.
            animal: The animal name to associate with the card.
        """
        self.register_card(
            uid=uid,
            card_type=CardType.CHARACTER,
            species=animal,
            name=animal,
            role=CharacterRole.MAIN,
        )

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

    def get_card(self, uid: str) -> Optional[Card]:
        """
        Get a Card object for the given UID.

        Args:
            uid: The RFID card UID.

        Returns:
            Card object or None if not found.
        """
        with self._lock:
            data = self._cards_db.get(uid)
            if data:
                return Card.from_dict(uid, data)
            return None

    def get_card_type(self, uid: str) -> Optional[CardType]:
        """
        Get the type of an RFID card.

        Args:
            uid: The RFID card UID.

        Returns:
            CardType or None if not found.
        """
        with self._lock:
            data = self._cards_db.get(uid)
            if data:
                if "card_type" in data:
                    return CardType(data["card_type"])
                # Legacy cards are characters
                return CardType.CHARACTER
            return None

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

    # Story length management
    @property
    def story_length_minutes(self) -> int:
        """Get the current story length setting in minutes."""
        with self._lock:
            return self._story_length_minutes

    def set_story_length(self, minutes: int) -> None:
        """
        Set the story length in minutes.

        Args:
            minutes: Story duration (1-15 minutes).
        """
        with self._lock:
            self._story_length_minutes = max(1, min(15, minutes))
            logger.debug(f"Story length set to {self._story_length_minutes} minutes")

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
                    "characters": self._current_story.characters,
                    "environment": self._current_story.environment,
                    "moral_lesson": self._current_story.moral_lesson,
                    "status": self._current_story.status,
                    "created_at": self._current_story.created_at,
                }

            return {
                "selected_animals": self._selected_animals.copy(),
                "selected_cards": [sc.to_dict() for sc in self._selected_cards],
                "has_character": self.has_character_card(),
                "story_elements": self.get_story_elements() if self._selected_cards else None,
                "current_story": story_dict,
                "is_generating": self._is_generating,
                "is_playing": self._is_playing,
                "current_segment_index": self._current_segment_index,
                "story_length_minutes": self._story_length_minutes,
            }
