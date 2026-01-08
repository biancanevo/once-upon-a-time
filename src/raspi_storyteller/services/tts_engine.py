"""
Text-to-Speech Engine with multiple provider support.

Supports:
- Edge TTS (Microsoft, online, async)
- pyttsx3 (offline, sync)
- Google TTS (online, requires API key)
"""

import asyncio
import os
import tempfile
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from ..utils.cache import AudioCache
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Thread pool for sync operations
_executor = ThreadPoolExecutor(max_workers=4)


class TTSProviderBase(ABC):
    """Abstract base class for TTS providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    async def synthesize(self, text: str, output_path: str) -> bool:
        """
        Synthesize text to audio file.

        Args:
            text: Text to convert to speech.
            output_path: Path to save the audio file.

        Returns:
            True if synthesis succeeded, False otherwise.
        """
        pass


class EdgeTTSProvider(TTSProviderBase):
    """Microsoft Edge TTS provider (online, high quality)."""

    def __init__(self, voice: str = "es-ES-PabloNeural"):
        """
        Initialize Edge TTS provider.

        Args:
            voice: Voice identifier (e.g., 'es-ES-PabloNeural').
        """
        self.voice = voice

    @property
    def name(self) -> str:
        return "edge"

    async def synthesize(self, text: str, output_path: str) -> bool:
        """Synthesize text using Edge TTS."""
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_path)
            logger.debug(f"Edge TTS synthesized: {output_path}")
            return True
        except ImportError:
            logger.error("edge-tts not installed")
            return False
        except Exception as e:
            logger.error(f"Edge TTS synthesis failed: {e}")
            return False


class Pyttsx3Provider(TTSProviderBase):
    """pyttsx3 provider (offline, cross-platform)."""

    def __init__(self, rate: int = 150, volume: float = 1.0):
        """
        Initialize pyttsx3 provider.

        Args:
            rate: Speech rate (words per minute).
            volume: Volume level (0.0 to 1.0).
        """
        self.rate = rate
        self.volume = volume
        self._engine = None

    def _get_engine(self):
        """Get or create pyttsx3 engine (must be done in executor thread)."""
        if self._engine is None:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
        return self._engine

    @property
    def name(self) -> str:
        return "pyttsx3"

    async def synthesize(self, text: str, output_path: str) -> bool:
        """Synthesize text using pyttsx3 (runs in executor)."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _executor, self._synthesize_sync, text, output_path
            )
            return result
        except Exception as e:
            logger.error(f"pyttsx3 synthesis failed: {e}")
            return False

    def _synthesize_sync(self, text: str, output_path: str) -> bool:
        """Synchronous synthesis (runs in thread pool)."""
        try:
            import pyttsx3

            # Create a fresh engine each time to avoid threading issues
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            engine.stop()
            logger.debug(f"pyttsx3 synthesized: {output_path}")
            return True
        except ImportError:
            logger.error("pyttsx3 not installed")
            return False
        except Exception as e:
            logger.error(f"pyttsx3 sync synthesis failed: {e}")
            return False


class GoogleTTSProvider(TTSProviderBase):
    """Google Text-to-Speech provider (online, requires API key)."""

    def __init__(self, lang: str = "es"):
        """
        Initialize Google TTS provider.

        Args:
            lang: Language code (e.g., 'es', 'en').
        """
        self.lang = lang

    @property
    def name(self) -> str:
        return "google"

    async def synthesize(self, text: str, output_path: str) -> bool:
        """Synthesize text using gTTS."""
        try:
            from gtts import gTTS

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _executor, self._synthesize_sync, text, output_path
            )
            return result
        except Exception as e:
            logger.error(f"Google TTS synthesis failed: {e}")
            return False

    def _synthesize_sync(self, text: str, output_path: str) -> bool:
        """Synchronous synthesis (runs in thread pool)."""
        try:
            from gtts import gTTS

            tts = gTTS(text=text, lang=self.lang)
            tts.save(output_path)
            logger.debug(f"Google TTS synthesized: {output_path}")
            return True
        except ImportError:
            logger.error("gTTS not installed")
            return False
        except Exception as e:
            logger.error(f"Google TTS sync synthesis failed: {e}")
            return False


class MockTTSProvider(TTSProviderBase):
    """Mock TTS provider for testing."""

    @property
    def name(self) -> str:
        return "mock"

    async def synthesize(self, text: str, output_path: str) -> bool:
        """Create an empty file to simulate synthesis."""
        try:
            Path(output_path).touch()
            logger.debug(f"Mock TTS created: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Mock TTS failed: {e}")
            return False


class TTSEngine:
    """
    Main TTS engine with provider abstraction and caching.

    Supports automatic fallback between providers.
    """

    PROVIDERS = {
        "edge": EdgeTTSProvider,
        "pyttsx3": Pyttsx3Provider,
        "google": GoogleTTSProvider,
        "mock": MockTTSProvider,
    }

    FALLBACK_ORDER = ["edge", "pyttsx3", "google"]

    def __init__(
        self,
        provider: str = "pyttsx3",
        cache_dir: str = "./audio_cache",
        max_cache_size_mb: int = 500,
        voice: str = "es-ES-PabloNeural",
        enable_fallback: bool = True,
    ):
        """
        Initialize the TTS engine.

        Args:
            provider: Primary TTS provider name.
            cache_dir: Directory for audio cache.
            max_cache_size_mb: Maximum cache size in MB.
            voice: Voice identifier for Edge TTS.
            enable_fallback: Whether to try fallback providers on failure.
        """
        self.provider_name = provider
        self.enable_fallback = enable_fallback
        self.voice = voice

        # Initialize cache
        self.cache = AudioCache(cache_dir, max_cache_size_mb)

        # Initialize primary provider
        self.provider = self._create_provider(provider)

        logger.info(f"TTSEngine initialized with provider: {provider}")

    def _create_provider(self, name: str) -> TTSProviderBase:
        """Create a TTS provider by name."""
        if name == "edge":
            return EdgeTTSProvider(voice=self.voice)
        elif name == "pyttsx3":
            return Pyttsx3Provider()
        elif name == "google":
            return GoogleTTSProvider()
        elif name == "mock":
            return MockTTSProvider()
        else:
            logger.warning(f"Unknown provider '{name}', using pyttsx3")
            return Pyttsx3Provider()

    async def synthesize_async(
        self, text: str, cache_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Synthesize text to audio file with caching.

        Args:
            text: Text to convert to speech.
            cache_key: Optional cache key (uses text hash if not provided).

        Returns:
            Path to audio file, or None if synthesis failed.
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for synthesis")
            return None

        # Check cache first
        cached = self.cache.get_cached(text, self.provider.name)
        if cached:
            return cached

        # Get output path from cache
        output_path = str(self.cache.get_cache_path(text, self.provider.name))

        # Try primary provider
        success = await self.provider.synthesize(text, output_path)

        if success and Path(output_path).exists():
            return output_path

        # Try fallback providers if enabled
        if self.enable_fallback:
            for fallback_name in self.FALLBACK_ORDER:
                if fallback_name == self.provider_name:
                    continue

                logger.info(f"Trying fallback provider: {fallback_name}")
                fallback_provider = self._create_provider(fallback_name)
                fallback_path = str(
                    self.cache.get_cache_path(text, fallback_provider.name)
                )

                success = await fallback_provider.synthesize(text, fallback_path)
                if success and Path(fallback_path).exists():
                    return fallback_path

        logger.error("All TTS providers failed")
        return None

    def synthesize_sync(self, text: str) -> Optional[str]:
        """
        Synchronous wrapper for synthesize_async.

        Args:
            text: Text to convert to speech.

        Returns:
            Path to audio file, or None if synthesis failed.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.synthesize_async(text))

    def set_provider(self, provider: str) -> None:
        """
        Change the primary TTS provider.

        Args:
            provider: Provider name ('edge', 'pyttsx3', 'google').
        """
        if provider in self.PROVIDERS:
            self.provider = self._create_provider(provider)
            self.provider_name = provider
            logger.info(f"TTS provider changed to: {provider}")
        else:
            logger.warning(f"Unknown provider: {provider}")

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the audio cache."""
        self.cache.clear()
