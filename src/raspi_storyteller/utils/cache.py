"""
Audio cache management for TTS-generated files.

Provides caching functionality to avoid duplicate TTS synthesis.
"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger(__name__)


class AudioCache:
    """
    Manages caching of TTS-generated audio files.

    Features:
    - Hash-based cache keys for text content
    - Automatic cache cleanup when size limit exceeded
    - Provider-specific file naming
    """

    def __init__(
        self,
        cache_dir: str = "./audio_cache",
        max_size_mb: int = 500,
    ):
        """
        Initialize the audio cache.

        Args:
            cache_dir: Directory to store cached audio files.
            max_size_mb: Maximum cache size in megabytes.
        """
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"AudioCache initialized: {self.cache_dir} (max {max_size_mb}MB)"
        )

    def _generate_cache_key(self, text: str, provider: str) -> str:
        """
        Generate a unique cache key for text and provider.

        Args:
            text: The text content to hash.
            provider: The TTS provider name.

        Returns:
            A unique cache key string.
        """
        content = f"{provider}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_extension(self, provider: str) -> str:
        """Get the file extension for a TTS provider."""
        # Edge TTS and Google TTS produce MP3, pyttsx3 produces WAV
        if provider in ("edge", "google"):
            return ".mp3"
        return ".wav"

    def get_cache_path(self, text: str, provider: str) -> Path:
        """
        Get the cache file path for given text and provider.

        Args:
            text: The text content.
            provider: The TTS provider name.

        Returns:
            Path to the cache file (may not exist yet).
        """
        cache_key = self._generate_cache_key(text, provider)
        extension = self._get_extension(provider)
        return self.cache_dir / f"{provider}_{cache_key}{extension}"

    def get_cached(self, text: str, provider: str) -> Optional[str]:
        """
        Get cached audio file if it exists.

        Args:
            text: The text content.
            provider: The TTS provider name.

        Returns:
            Path to cached file as string, or None if not cached.
        """
        cache_path = self.get_cache_path(text, provider)
        if cache_path.exists():
            logger.debug(f"Cache hit: {cache_path.name}")
            return str(cache_path)
        logger.debug(f"Cache miss: {cache_path.name}")
        return None

    def store(self, text: str, provider: str, audio_path: str) -> str:
        """
        Store an audio file in the cache.

        Args:
            text: The text content.
            provider: The TTS provider name.
            audio_path: Path to the audio file to cache.

        Returns:
            Path to the cached file.
        """
        cache_path = self.get_cache_path(text, provider)

        # If source and destination are the same, already cached
        if Path(audio_path).resolve() == cache_path.resolve():
            return str(cache_path)

        # Copy file to cache
        try:
            shutil.copy2(audio_path, cache_path)
            logger.debug(f"Cached: {cache_path.name}")

            # Check if cleanup needed
            self._cleanup_if_needed()

            return str(cache_path)
        except IOError as e:
            logger.error(f"Failed to cache audio: {e}")
            return audio_path

    def _get_cache_size(self) -> int:
        """Get the current cache size in bytes."""
        total = 0
        for file_path in self.cache_dir.iterdir():
            if file_path.is_file():
                total += file_path.stat().st_size
        return total

    def _cleanup_if_needed(self) -> None:
        """Remove oldest files if cache exceeds size limit."""
        current_size = self._get_cache_size()

        if current_size <= self.max_size_bytes:
            return

        logger.info(
            f"Cache cleanup needed: {current_size / 1024 / 1024:.1f}MB "
            f"> {self.max_size_bytes / 1024 / 1024:.1f}MB"
        )

        # Get all cache files sorted by modification time (oldest first)
        files = sorted(
            [f for f in self.cache_dir.iterdir() if f.is_file()],
            key=lambda f: f.stat().st_mtime,
        )

        # Remove oldest files until under limit
        for file_path in files:
            if current_size <= self.max_size_bytes * 0.8:  # Target 80% capacity
                break
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                current_size -= file_size
                logger.debug(f"Removed from cache: {file_path.name}")
            except IOError as e:
                logger.error(f"Failed to remove cache file: {e}")

    def clear(self) -> None:
        """Clear all cached files."""
        for file_path in self.cache_dir.iterdir():
            if file_path.is_file():
                try:
                    file_path.unlink()
                except IOError:
                    pass
        logger.info("Cache cleared")

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        files = list(self.cache_dir.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())

        return {
            "file_count": len([f for f in files if f.is_file()]),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "max_size_mb": round(self.max_size_bytes / 1024 / 1024, 2),
            "usage_percent": round(total_size / self.max_size_bytes * 100, 1)
            if self.max_size_bytes > 0
            else 0,
        }
