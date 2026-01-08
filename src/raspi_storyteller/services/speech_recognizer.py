"""
Speech recognition service using Google Speech-to-Text.

Provides voice command input with language selection and timeout handling.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Thread pool for blocking operations
_executor = ThreadPoolExecutor(max_workers=2)


class SpeechRecognizer:
    """
    Voice input handler using Google Speech Recognition.

    Features:
    - Language selection (Spanish/English)
    - Configurable timeout
    - Animal name extraction from commands
    """

    # Common animal names in Spanish and English
    KNOWN_ANIMALS = {
        # Spanish
        "gato",
        "perro",
        "leon",
        "león",
        "tigre",
        "elefante",
        "jirafa",
        "mono",
        "oso",
        "conejo",
        "raton",
        "ratón",
        "pajaro",
        "pájaro",
        "pez",
        "serpiente",
        "caballo",
        "vaca",
        "cerdo",
        "oveja",
        "lobo",
        "zorro",
        "cebra",
        "hipopotamo",
        "hipopótamo",
        "cocodrilo",
        "tortuga",
        "delfin",
        "delfín",
        "ballena",
        "aguila",
        "águila",
        "buho",
        "búho",
        # English
        "cat",
        "dog",
        "lion",
        "tiger",
        "elephant",
        "giraffe",
        "monkey",
        "bear",
        "rabbit",
        "mouse",
        "bird",
        "fish",
        "snake",
        "horse",
        "cow",
        "pig",
        "sheep",
        "wolf",
        "fox",
        "zebra",
        "hippo",
        "crocodile",
        "turtle",
        "dolphin",
        "whale",
        "eagle",
        "owl",
    }

    def __init__(
        self,
        language: str = "es-ES",
        timeout: int = 5,
        mock: bool = False,
    ):
        """
        Initialize the speech recognizer.

        Args:
            language: Language code for recognition (e.g., 'es-ES', 'en-US').
            timeout: Maximum recording duration in seconds.
            mock: If True, use mock responses for testing.
        """
        self.language = language
        self.timeout = timeout
        self.mock = mock
        self._recognizer = None
        self._microphone = None

        if not mock:
            self._init_recognizer()

        logger.info(
            f"SpeechRecognizer initialized (lang={language}, timeout={timeout}s)"
        )

    def _init_recognizer(self) -> None:
        """Initialize the speech recognition library."""
        try:
            import speech_recognition as sr

            self._recognizer = sr.Recognizer()
            # Adjust for ambient noise will be done during listening
            logger.debug("Speech recognizer initialized")
        except ImportError:
            logger.warning("speech_recognition not installed, using mock mode")
            self.mock = True
        except Exception as e:
            logger.error(f"Failed to initialize recognizer: {e}")
            self.mock = True

    async def listen(self, timeout: Optional[int] = None) -> str:
        """
        Listen for voice input and return recognized text.

        Args:
            timeout: Override default timeout (seconds).

        Returns:
            Recognized text, or empty string if nothing recognized.
        """
        actual_timeout = timeout or self.timeout

        if self.mock:
            logger.info(f"[MOCK] Listening for {actual_timeout} seconds...")
            await asyncio.sleep(0.5)
            return "cuéntame una historia sobre un gato y un perro"

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, self._listen_sync, actual_timeout
        )

    def _listen_sync(self, timeout: int) -> str:
        """
        Synchronous listening (runs in thread pool).

        Args:
            timeout: Recording timeout in seconds.

        Returns:
            Recognized text or empty string.
        """
        try:
            import speech_recognition as sr

            with sr.Microphone() as source:
                logger.info(f"Listening for {timeout} seconds...")

                # Adjust for ambient noise
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

                try:
                    audio = self._recognizer.listen(
                        source, timeout=timeout, phrase_time_limit=timeout
                    )
                except sr.WaitTimeoutError:
                    logger.warning("No speech detected within timeout")
                    return ""

            # Recognize using Google Speech-to-Text
            try:
                text = self._recognizer.recognize_google(
                    audio, language=self.language
                )
                logger.info(f"Recognized: {text}")
                return text
            except sr.UnknownValueError:
                logger.warning("Speech not understood")
                return ""
            except sr.RequestError as e:
                logger.error(f"Recognition service error: {e}")
                return ""

        except ImportError:
            logger.error("speech_recognition or pyaudio not available")
            return ""
        except Exception as e:
            logger.error(f"Listening failed: {e}")
            return ""

    def parse_animals(self, text: str) -> List[str]:
        """
        Extract animal names from text.

        Args:
            text: Input text (e.g., "Tell me a story about a cat and dog").

        Returns:
            List of recognized animal names.
        """
        if not text:
            return []

        # Normalize text
        text_lower = text.lower()

        # Find all known animals in the text
        found_animals = []
        for animal in self.KNOWN_ANIMALS:
            # Use word boundary matching
            pattern = rf"\b{re.escape(animal)}\b"
            if re.search(pattern, text_lower):
                # Use the canonical form (lowercase)
                found_animals.append(animal)

        # Remove duplicates while preserving order
        seen = set()
        unique_animals = []
        for animal in found_animals:
            if animal not in seen:
                seen.add(animal)
                unique_animals.append(animal)

        logger.info(f"Parsed animals from '{text}': {unique_animals}")
        return unique_animals

    async def listen_for_command(self) -> Tuple[str, List[str]]:
        """
        Listen for a voice command and extract animals.

        Returns:
            Tuple of (recognized_text, list_of_animals).
        """
        text = await self.listen()
        animals = self.parse_animals(text)
        return text, animals

    def set_language(self, language: str) -> None:
        """
        Change the recognition language.

        Args:
            language: Language code (e.g., 'es-ES', 'en-US').
        """
        self.language = language
        logger.info(f"Language changed to: {language}")

    def add_animal(self, animal: str) -> None:
        """
        Add a custom animal name to the known list.

        Args:
            animal: Animal name to add.
        """
        self.KNOWN_ANIMALS.add(animal.lower())
        logger.debug(f"Added animal: {animal}")

    def get_known_animals(self) -> List[str]:
        """Get list of all known animal names."""
        return sorted(list(self.KNOWN_ANIMALS))
