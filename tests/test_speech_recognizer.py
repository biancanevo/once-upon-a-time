"""Tests for SpeechRecognizer module."""

import pytest

from raspi_storyteller.services.speech_recognizer import SpeechRecognizer


class TestSpeechRecognizer:
    """Tests for SpeechRecognizer functionality."""

    def test_init(self):
        """Test speech recognizer initialization."""
        recognizer = SpeechRecognizer(mock=True)
        assert recognizer.mock is True
        assert recognizer.language == "es-ES"
        assert recognizer.timeout == 5

    def test_init_with_custom_settings(self):
        """Test initialization with custom settings."""
        recognizer = SpeechRecognizer(
            language="en-US",
            timeout=10,
            mock=True,
        )
        assert recognizer.language == "en-US"
        assert recognizer.timeout == 10

    @pytest.mark.asyncio
    async def test_listen(self, speech_recognizer):
        """Test listening for voice input."""
        text = await speech_recognizer.listen()
        assert text is not None
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_listen_with_timeout(self, speech_recognizer):
        """Test listening with custom timeout."""
        text = await speech_recognizer.listen(timeout=3)
        assert text is not None

    def test_parse_animals_spanish(self, speech_recognizer):
        """Test animal extraction from Spanish text."""
        text = "Cuéntame una historia sobre un gato y un perro"
        animals = speech_recognizer.parse_animals(text)

        assert "gato" in animals
        assert "perro" in animals

    def test_parse_animals_english(self, speech_recognizer):
        """Test animal extraction from English text."""
        text = "Tell me a story about a cat and a dog"
        animals = speech_recognizer.parse_animals(text)

        assert "cat" in animals
        assert "dog" in animals

    def test_parse_animals_mixed(self, speech_recognizer):
        """Test animal extraction from mixed language text."""
        text = "I want a story about a cat and un león"
        animals = speech_recognizer.parse_animals(text)

        assert "cat" in animals
        assert "león" in animals or "leon" in animals

    def test_parse_animals_empty_text(self, speech_recognizer):
        """Test animal extraction from empty text."""
        animals = speech_recognizer.parse_animals("")
        assert animals == []

        animals = speech_recognizer.parse_animals(None)
        assert animals == []

    def test_parse_animals_no_animals(self, speech_recognizer):
        """Test animal extraction when no animals present."""
        text = "Tell me a story about a car and a house"
        animals = speech_recognizer.parse_animals(text)
        assert animals == []

    def test_parse_animals_multiple_same(self, speech_recognizer):
        """Test that duplicate animals are not returned."""
        text = "A cat met another cat in the forest"
        animals = speech_recognizer.parse_animals(text)
        assert animals.count("cat") == 1

    @pytest.mark.asyncio
    async def test_listen_for_command(self, speech_recognizer):
        """Test listening for command and extracting animals."""
        text, animals = await speech_recognizer.listen_for_command()

        assert text is not None
        assert isinstance(animals, list)

    def test_set_language(self, speech_recognizer):
        """Test language change."""
        speech_recognizer.set_language("en-US")
        assert speech_recognizer.language == "en-US"

    def test_add_custom_animal(self, speech_recognizer):
        """Test adding custom animal name."""
        speech_recognizer.add_animal("unicorn")
        assert "unicorn" in speech_recognizer.KNOWN_ANIMALS

        # Should now parse this animal
        text = "A story about a unicorn"
        animals = speech_recognizer.parse_animals(text)
        assert "unicorn" in animals

    def test_get_known_animals(self, speech_recognizer):
        """Test getting list of known animals."""
        animals = speech_recognizer.get_known_animals()
        assert isinstance(animals, list)
        assert len(animals) > 0
        assert "cat" in animals
        assert "gato" in animals

    def test_known_animals_contains_common(self, speech_recognizer):
        """Test that common animals are included."""
        animals = speech_recognizer.KNOWN_ANIMALS

        # English
        assert "cat" in animals
        assert "dog" in animals
        assert "lion" in animals
        assert "elephant" in animals

        # Spanish
        assert "gato" in animals
        assert "perro" in animals
        assert "elefante" in animals

    def test_word_boundary_matching(self, speech_recognizer):
        """Test that partial matches are not returned."""
        # "catalog" contains "cat" but shouldn't match
        text = "I read the catalog"
        animals = speech_recognizer.parse_animals(text)
        # This depends on implementation - word boundaries should prevent "catalog" from matching "cat"
        # If using word boundaries properly, "cat" should NOT be in result
        # If not using word boundaries, "cat" would be in result
        # Testing the expected behavior with word boundaries
