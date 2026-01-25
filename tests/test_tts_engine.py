"""Tests for TTS Engine module."""

import os
from pathlib import Path

import pytest

from raspi_storyteller.services.tts_engine import (
    TTSEngine,
    MockTTSProvider,
    EdgeTTSProvider,
    Pyttsx3Provider,
    GoogleTTSProvider,
)


class TestMockTTSProvider:
    """Tests for mock TTS provider."""

    @pytest.mark.asyncio
    async def test_synthesize(self, temp_cache_dir):
        """Test mock TTS synthesis."""
        provider = MockTTSProvider()
        output_path = str(Path(temp_cache_dir) / "test.wav")

        result = await provider.synthesize("Hello world", output_path)
        assert result is True
        assert Path(output_path).exists()

    def test_provider_name(self):
        """Test provider name."""
        provider = MockTTSProvider()
        assert provider.name == "mock"


class TestTTSEngine:
    """Tests for TTSEngine functionality."""

    def test_init(self, temp_cache_dir):
        """Test TTS engine initialization."""
        engine = TTSEngine(
            provider="mock",
            cache_dir=temp_cache_dir,
        )
        assert engine.provider_name == "mock"

    def test_init_with_unknown_provider(self, temp_cache_dir):
        """Test initialization with unknown provider defaults to pyttsx3."""
        engine = TTSEngine(
            provider="unknown_provider",
            cache_dir=temp_cache_dir,
            enable_fallback=False,
        )
        # Should fall back to pyttsx3
        assert engine.provider is not None

    @pytest.mark.asyncio
    async def test_synthesize_async(self, tts_engine, temp_cache_dir):
        """Test async synthesis."""
        result = await tts_engine.synthesize_async("Hello world")
        assert result is not None
        assert Path(result).exists()

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self, tts_engine):
        """Test synthesis with empty text returns None."""
        result = await tts_engine.synthesize_async("")
        assert result is None

        result = await tts_engine.synthesize_async("   ")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit(self, tts_engine):
        """Test that duplicate synthesis uses cache."""
        text = "Test text for caching"

        # First synthesis
        path1 = await tts_engine.synthesize_async(text)

        # Second synthesis should return same path (cache hit)
        path2 = await tts_engine.synthesize_async(text)

        assert path1 == path2

    def test_synthesize_sync(self, tts_engine):
        """Test synchronous synthesis wrapper."""
        result = tts_engine.synthesize_sync("Hello sync world")
        assert result is not None

    def test_set_provider(self, tts_engine):
        """Test changing TTS provider."""
        tts_engine.set_provider("mock")
        assert tts_engine.provider_name == "mock"

    def test_set_invalid_provider(self, tts_engine):
        """Test setting invalid provider (no crash)."""
        original = tts_engine.provider_name
        tts_engine.set_provider("invalid")
        # Should log warning but not crash

    def test_get_cache_stats(self, tts_engine):
        """Test cache statistics retrieval."""
        stats = tts_engine.get_cache_stats()
        assert "file_count" in stats
        assert "total_size_mb" in stats
        assert "max_size_mb" in stats
        assert "usage_percent" in stats

    def test_clear_cache(self, tts_engine, temp_cache_dir):
        """Test cache clearing."""
        # Create some cached files
        for i in range(3):
            (Path(temp_cache_dir) / f"test_{i}.mp3").touch()

        tts_engine.clear_cache()

        # Check cache is empty
        files = list(Path(temp_cache_dir).iterdir())
        assert len(files) == 0


class TestAudioCache:
    """Tests for audio cache functionality."""

    def test_cache_key_generation(self, temp_cache_dir):
        """Test that different texts generate different cache keys."""
        from raspi_storyteller.utils.cache import AudioCache

        cache = AudioCache(cache_dir=temp_cache_dir)

        path1 = cache.get_cache_path("text one", "edge")
        path2 = cache.get_cache_path("text two", "edge")

        assert path1 != path2

    def test_cache_key_provider_specific(self, temp_cache_dir):
        """Test that same text with different providers has different paths."""
        from raspi_storyteller.utils.cache import AudioCache

        cache = AudioCache(cache_dir=temp_cache_dir)

        path_edge = cache.get_cache_path("same text", "edge")
        path_pyttsx3 = cache.get_cache_path("same text", "pyttsx3")

        assert path_edge != path_pyttsx3

    def test_get_cached_miss(self, temp_cache_dir):
        """Test cache miss returns None."""
        from raspi_storyteller.utils.cache import AudioCache

        cache = AudioCache(cache_dir=temp_cache_dir)
        result = cache.get_cached("nonexistent text", "edge")
        assert result is None

    def test_get_cached_hit(self, temp_cache_dir):
        """Test cache hit returns path."""
        from raspi_storyteller.utils.cache import AudioCache

        cache = AudioCache(cache_dir=temp_cache_dir)

        # Create a cached file
        cache_path = cache.get_cache_path("test text", "edge")
        cache_path.touch()

        result = cache.get_cached("test text", "edge")
        assert result is not None
        assert result == str(cache_path)

    def test_cache_stats(self, temp_cache_dir):
        """Test cache statistics."""
        from raspi_storyteller.utils.cache import AudioCache

        cache = AudioCache(cache_dir=temp_cache_dir, max_size_mb=100)

        # Create some files (write enough data to show up in MB stats)
        for i in range(5):
            (Path(temp_cache_dir) / f"test_{i}.mp3").write_bytes(b"x" * 1024 * 50)  # 50KB each

        stats = cache.get_stats()
        assert stats["file_count"] == 5
        assert stats["total_size_mb"] > 0
