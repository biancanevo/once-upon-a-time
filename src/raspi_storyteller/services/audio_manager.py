"""
Audio playback manager using pygame.

Provides sequential audio playback with callbacks and queue management.
"""

import asyncio
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class AudioManager:
    """
    Manages audio playback using pygame mixer.

    Features:
    - Sequential playback of audio segments
    - Volume control
    - Non-blocking playback with callbacks
    - Queue management
    """

    def __init__(self, volume: float = 0.8, mock: bool = False):
        """
        Initialize the audio manager.

        Args:
            volume: Initial volume level (0.0 to 1.0).
            mock: If True, simulate playback without actual audio.
        """
        self.volume = max(0.0, min(1.0, volume))
        self.mock = mock
        self._is_playing = False
        self._should_stop = False
        self._current_file: Optional[str] = None
        self._lock = threading.Lock()
        self._playback_thread: Optional[threading.Thread] = None
        self._on_segment_complete: Optional[Callable[[int], None]] = None
        self._on_playback_complete: Optional[Callable[[], None]] = None

        if not mock:
            self._init_pygame()

        logger.info(f"AudioManager initialized (mock={mock}, volume={volume})")

    def _init_pygame(self) -> None:
        """Initialize pygame mixer."""
        try:
            import pygame

            pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)
            logger.debug("pygame mixer initialized")
        except ImportError:
            logger.warning("pygame not installed, using mock mode")
            self.mock = True
        except Exception as e:
            logger.error(f"Failed to initialize pygame: {e}")
            self.mock = True

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        with self._lock:
            return self._is_playing

    @property
    def current_file(self) -> Optional[str]:
        """Get the currently playing file."""
        with self._lock:
            return self._current_file

    def set_volume(self, volume: float) -> None:
        """
        Set the playback volume.

        Args:
            volume: Volume level (0.0 to 1.0).
        """
        self.volume = max(0.0, min(1.0, volume))
        if not self.mock:
            try:
                import pygame

                pygame.mixer.music.set_volume(self.volume)
            except Exception as e:
                logger.error(f"Failed to set volume: {e}")
        logger.debug(f"Volume set to {self.volume}")

    def play_audio(self, file_path: str, blocking: bool = True) -> bool:
        """
        Play a single audio file.

        Args:
            file_path: Path to the audio file.
            blocking: If True, wait for playback to complete.

        Returns:
            True if playback started successfully.
        """
        if not Path(file_path).exists():
            logger.error(f"Audio file not found: {file_path}")
            return False

        with self._lock:
            self._is_playing = True
            self._current_file = file_path
            self._should_stop = False

        if self.mock:
            logger.info(f"[MOCK] Playing: {file_path}")
            if blocking:
                time.sleep(0.5)  # Simulate playback time
            with self._lock:
                self._is_playing = False
                self._current_file = None
            return True

        try:
            import pygame

            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            logger.debug(f"Playing: {file_path}")

            if blocking:
                while pygame.mixer.music.get_busy():
                    if self._should_stop:
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.1)

                with self._lock:
                    self._is_playing = False
                    self._current_file = None

            return True
        except Exception as e:
            logger.error(f"Playback failed: {e}")
            with self._lock:
                self._is_playing = False
                self._current_file = None
            return False

    def play_audio_async(
        self,
        file_path: str,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> bool:
        """
        Play audio file asynchronously (non-blocking).

        Args:
            file_path: Path to the audio file.
            on_complete: Callback when playback completes.

        Returns:
            True if playback started successfully.
        """
        if self._playback_thread and self._playback_thread.is_alive():
            logger.warning("Playback already in progress")
            return False

        def _play():
            self.play_audio(file_path, blocking=True)
            if on_complete:
                on_complete()

        self._playback_thread = threading.Thread(target=_play, daemon=True)
        self._playback_thread.start()
        return True

    async def play_sequence(
        self,
        segments: List[str],
        on_segment_complete: Optional[Callable[[int], None]] = None,
        on_playback_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Play a sequence of audio segments.

        Args:
            segments: List of audio file paths.
            on_segment_complete: Callback after each segment (receives index).
            on_playback_complete: Callback when all segments complete.
        """
        self._on_segment_complete = on_segment_complete
        self._on_playback_complete = on_playback_complete
        self._should_stop = False

        for i, segment in enumerate(segments):
            if self._should_stop:
                logger.info("Playback stopped by user")
                break

            logger.debug(f"Playing segment {i + 1}/{len(segments)}: {segment}")

            # Run blocking playback in executor to not block async loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.play_audio, segment, True)

            if self._on_segment_complete:
                self._on_segment_complete(i)

            # Small delay between segments
            await asyncio.sleep(0.2)

        with self._lock:
            self._is_playing = False
            self._current_file = None

        if self._on_playback_complete:
            self._on_playback_complete()

        logger.info("Sequence playback complete")

    def play_sequence_sync(
        self,
        segments: List[str],
        on_segment_complete: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Play a sequence of audio segments synchronously.

        Args:
            segments: List of audio file paths.
            on_segment_complete: Callback after each segment.
        """
        self._should_stop = False

        for i, segment in enumerate(segments):
            if self._should_stop:
                break

            self.play_audio(segment, blocking=True)

            if on_segment_complete:
                on_segment_complete(i)

            time.sleep(0.2)

        with self._lock:
            self._is_playing = False

    def stop_audio(self) -> None:
        """Stop current playback."""
        with self._lock:
            self._should_stop = True

        if not self.mock:
            try:
                import pygame

                pygame.mixer.music.stop()
            except Exception as e:
                logger.error(f"Failed to stop audio: {e}")

        with self._lock:
            self._is_playing = False
            self._current_file = None

        logger.info("Audio stopped")

    def pause_audio(self) -> None:
        """Pause current playback."""
        if not self.mock:
            try:
                import pygame

                pygame.mixer.music.pause()
                logger.debug("Audio paused")
            except Exception as e:
                logger.error(f"Failed to pause audio: {e}")

    def resume_audio(self) -> None:
        """Resume paused playback."""
        if not self.mock:
            try:
                import pygame

                pygame.mixer.music.unpause()
                logger.debug("Audio resumed")
            except Exception as e:
                logger.error(f"Failed to resume audio: {e}")

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_audio()
        if not self.mock:
            try:
                import pygame

                pygame.mixer.quit()
            except Exception:
                pass
        logger.info("AudioManager cleaned up")
