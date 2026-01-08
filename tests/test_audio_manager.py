"""Tests for AudioManager module."""

import pytest
import time
from pathlib import Path

from raspi_storyteller.services.audio_manager import AudioManager


class TestAudioManager:
    """Tests for AudioManager functionality."""

    def test_init(self):
        """Test audio manager initialization."""
        manager = AudioManager(mock=True)
        assert manager.mock is True
        assert manager.is_playing is False

    def test_init_with_volume(self):
        """Test initialization with custom volume."""
        manager = AudioManager(volume=0.5, mock=True)
        assert manager.volume == 0.5

    def test_volume_clamping(self):
        """Test volume value clamping."""
        manager = AudioManager(volume=1.5, mock=True)
        assert manager.volume == 1.0

        manager = AudioManager(volume=-0.5, mock=True)
        assert manager.volume == 0.0

    def test_set_volume(self, audio_manager):
        """Test volume adjustment."""
        audio_manager.set_volume(0.5)
        assert audio_manager.volume == 0.5

    def test_is_playing_property(self, audio_manager):
        """Test is_playing property."""
        assert audio_manager.is_playing is False

    def test_play_audio_mock(self, audio_manager, temp_dir):
        """Test audio playback in mock mode."""
        # Create a test file
        test_file = Path(temp_dir) / "test.mp3"
        test_file.touch()

        result = audio_manager.play_audio(str(test_file), blocking=True)
        assert result is True
        assert audio_manager.is_playing is False  # Completed

    def test_play_nonexistent_file(self, audio_manager):
        """Test playing nonexistent file returns False."""
        result = audio_manager.play_audio("/nonexistent/file.mp3")
        assert result is False

    def test_play_audio_async(self, audio_manager, temp_dir):
        """Test async audio playback."""
        test_file = Path(temp_dir) / "test.mp3"
        test_file.touch()

        callback_called = []

        def on_complete():
            callback_called.append(True)

        result = audio_manager.play_audio_async(
            str(test_file),
            on_complete=on_complete,
        )
        assert result is True

        # Wait for playback to complete
        time.sleep(1)
        assert len(callback_called) > 0

    def test_stop_audio(self, audio_manager):
        """Test stopping audio playback."""
        audio_manager.stop_audio()
        assert audio_manager.is_playing is False

    def test_pause_resume(self, audio_manager):
        """Test pause and resume (mock mode does nothing but shouldn't crash)."""
        audio_manager.pause_audio()
        audio_manager.resume_audio()

    @pytest.mark.asyncio
    async def test_play_sequence(self, audio_manager, temp_dir):
        """Test sequential playback of multiple files."""
        # Create test files
        files = []
        for i in range(3):
            f = Path(temp_dir) / f"segment_{i}.mp3"
            f.touch()
            files.append(str(f))

        segments_completed = []

        def on_segment(index):
            segments_completed.append(index)

        playback_complete = []

        def on_complete():
            playback_complete.append(True)

        await audio_manager.play_sequence(
            files,
            on_segment_complete=on_segment,
            on_playback_complete=on_complete,
        )

        assert len(segments_completed) == 3
        assert len(playback_complete) == 1

    def test_play_sequence_sync(self, audio_manager, temp_dir):
        """Test synchronous sequential playback."""
        files = []
        for i in range(2):
            f = Path(temp_dir) / f"segment_{i}.mp3"
            f.touch()
            files.append(str(f))

        segments_completed = []

        def on_segment(index):
            segments_completed.append(index)

        audio_manager.play_sequence_sync(files, on_segment_complete=on_segment)

        assert len(segments_completed) == 2

    def test_cleanup(self, audio_manager):
        """Test cleanup method."""
        audio_manager.cleanup()
        assert audio_manager.is_playing is False
