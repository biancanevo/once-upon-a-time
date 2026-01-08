"""Tests for StoryGenerator module."""

import pytest

from raspi_storyteller.services.story_generator import StoryGenerator


class TestStoryGenerator:
    """Tests for StoryGenerator functionality."""

    def test_init(self):
        """Test story generator initialization."""
        generator = StoryGenerator(mock=True)
        assert generator.mock is True
        assert generator.language == "es"

    def test_init_with_custom_language(self):
        """Test initialization with custom language."""
        generator = StoryGenerator(mock=True, language="en")
        assert generator.language == "en"

    @pytest.mark.asyncio
    async def test_generate_story(self, story_generator):
        """Test story generation."""
        story = await story_generator.generate_story(["cat", "dog"])
        assert story is not None
        assert len(story) > 0
        assert "cat" in story.lower() or "gato" in story.lower()

    @pytest.mark.asyncio
    async def test_generate_story_empty_animals(self, story_generator):
        """Test story generation with empty animal list."""
        story = await story_generator.generate_story([])
        assert story is not None  # Should still generate with default animals

    @pytest.mark.asyncio
    async def test_generate_story_with_audio(self, story_generator, tts_engine):
        """Test story generation with audio synthesis."""
        result = await story_generator.generate_story_with_audio(
            ["cat", "dog"],
            tts_engine,
        )

        assert result["status"] in ("success", "partial")
        assert result["full_text"] is not None
        assert len(result["full_text"]) > 0
        assert result["animals"] == ["cat", "dog"]
        assert isinstance(result["audio_segments"], list)

    def test_detect_paragraphs(self, story_generator):
        """Test paragraph detection."""
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        paragraphs = story_generator.detect_paragraphs(text)

        assert len(paragraphs) == 3
        assert "Paragraph one" in paragraphs[0]
        assert "Paragraph two" in paragraphs[1]
        assert "Paragraph three" in paragraphs[2]

    def test_detect_paragraphs_no_breaks(self, story_generator):
        """Test paragraph detection with no explicit breaks."""
        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        paragraphs = story_generator.detect_paragraphs(text)

        # Should split into groups when no paragraph breaks
        assert len(paragraphs) >= 1

    def test_detect_paragraphs_empty(self, story_generator):
        """Test paragraph detection with empty text."""
        paragraphs = story_generator.detect_paragraphs("")
        assert paragraphs == []

    def test_set_language(self, story_generator):
        """Test language setting."""
        story_generator.set_language("en")
        assert story_generator.language == "en"

    def test_set_model(self, story_generator):
        """Test model setting."""
        story_generator.set_model("llama2")
        assert story_generator.model == "llama2"

    @pytest.mark.asyncio
    async def test_generate_story_stream(self, story_generator):
        """Test streaming story generation."""
        chunks = []
        async for chunk in story_generator.generate_story_stream(["cat"]):
            chunks.append(chunk)

        assert len(chunks) > 0
        full_text = "".join(chunks)
        assert len(full_text) > 0

    def test_get_prompt_spanish(self):
        """Test Spanish prompt generation."""
        generator = StoryGenerator(mock=True, language="es")
        prompt = generator._get_prompt(["gato", "perro"])
        assert "gato, perro" in prompt
        assert "niños" in prompt  # Spanish word

    def test_get_prompt_english(self):
        """Test English prompt generation."""
        generator = StoryGenerator(mock=True, language="en")
        prompt = generator._get_prompt(["cat", "dog"])
        assert "cat, dog" in prompt
        assert "children" in prompt  # English word

    def test_mock_story_spanish(self):
        """Test mock story generation in Spanish."""
        generator = StoryGenerator(mock=True, language="es")
        story = generator._get_mock_story(["gato"])
        assert "bosque" in story.lower() or "amigos" in story.lower()

    def test_mock_story_english(self):
        """Test mock story generation in English."""
        generator = StoryGenerator(mock=True, language="en")
        story = generator._get_mock_story(["cat"])
        assert "forest" in story.lower() or "friends" in story.lower()
