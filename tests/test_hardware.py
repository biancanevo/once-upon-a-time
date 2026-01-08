"""Tests for hardware abstraction layer."""

import time
import threading

import pytest

from raspi_storyteller.hardware.rfid_handler import MockRFIDHandler, RFIDPollingLoop
from raspi_storyteller.hardware.led_controller import (
    MockLEDController,
    LEDAnimator,
    COLORS,
)
from raspi_storyteller.hardware.audio_device import AudioDeviceManager


class TestMockRFIDHandler:
    """Tests for MockRFIDHandler."""

    def test_init(self):
        """Test mock RFID handler initialization."""
        handler = MockRFIDHandler()
        assert handler is not None

    def test_inject_card(self, mock_rfid_handler):
        """Test card injection for testing."""
        mock_rfid_handler.inject_card("123456", "test_text")
        result = mock_rfid_handler.read_card()

        assert result is not None
        assert result[0] == "123456"
        assert result[1] == "test_text"

    def test_read_no_card(self, mock_rfid_handler):
        """Test reading when no card injected."""
        result = mock_rfid_handler.read_card()
        assert result is None

    def test_multiple_cards(self, mock_rfid_handler):
        """Test injecting multiple cards."""
        mock_rfid_handler.inject_card("111", "card1")
        mock_rfid_handler.inject_card("222", "card2")

        result1 = mock_rfid_handler.read_card()
        result2 = mock_rfid_handler.read_card()

        assert result1[0] == "111"
        assert result2[0] == "222"

    def test_clear_injected_cards(self, mock_rfid_handler):
        """Test clearing injected cards."""
        mock_rfid_handler.inject_card("123", "test")
        mock_rfid_handler.clear_injected_cards()

        result = mock_rfid_handler.read_card()
        assert result is None

    def test_write_card(self, mock_rfid_handler):
        """Test writing to card (mock always succeeds)."""
        result = mock_rfid_handler.write_card("test_data")
        assert result is True

    def test_cleanup(self, mock_rfid_handler):
        """Test cleanup (no-op for mock)."""
        mock_rfid_handler.cleanup()  # Should not raise


class TestRFIDPollingLoop:
    """Tests for RFID polling loop."""

    def test_init(self, mock_rfid_handler):
        """Test polling loop initialization."""
        detected = []

        def callback(uid, text):
            detected.append((uid, text))

        loop = RFIDPollingLoop(
            handler=mock_rfid_handler,
            on_card_detected=callback,
        )

        assert loop.is_running is False

    def test_start_stop(self, mock_rfid_handler):
        """Test starting and stopping the loop."""
        loop = RFIDPollingLoop(
            handler=mock_rfid_handler,
            on_card_detected=lambda u, t: None,
        )

        loop.start()
        assert loop.is_running is True

        loop.stop()
        assert loop.is_running is False

    def test_card_detection_callback(self, mock_rfid_handler):
        """Test that callback is called when card detected."""
        detected = []

        def callback(uid, text):
            detected.append(uid)

        loop = RFIDPollingLoop(
            handler=mock_rfid_handler,
            on_card_detected=callback,
            debounce_time=0.1,
        )

        mock_rfid_handler.inject_card("123", "test")

        loop.start()
        time.sleep(0.5)
        loop.stop()

        assert "123" in detected


class TestMockLEDController:
    """Tests for MockLEDController."""

    def test_init(self):
        """Test mock LED controller initialization."""
        led = MockLEDController(led_count=12)
        assert led.led_count == 12

    def test_set_color(self, mock_led_controller):
        """Test setting LED color."""
        mock_led_controller.set_color((255, 0, 0))
        assert mock_led_controller.get_current_color() == (255, 0, 0)

    def test_set_pixel(self, mock_led_controller):
        """Test setting individual pixel."""
        mock_led_controller.set_pixel(0, (0, 255, 0))
        assert mock_led_controller.get_pixel(0) == (0, 255, 0)

    def test_clear(self, mock_led_controller):
        """Test clearing LEDs."""
        mock_led_controller.set_color((255, 255, 255))
        mock_led_controller.clear()
        assert mock_led_controller.get_current_color() == (0, 0, 0)

    def test_cleanup(self, mock_led_controller):
        """Test cleanup."""
        mock_led_controller.cleanup()  # Should not raise


class TestLEDAnimator:
    """Tests for LEDAnimator."""

    def test_init(self, mock_led_controller):
        """Test animator initialization."""
        animator = LEDAnimator(mock_led_controller)
        assert animator.current_animation is None

    def test_animate_thinking(self, mock_led_controller):
        """Test thinking animation."""
        animator = LEDAnimator(mock_led_controller)
        animator.animate_thinking()

        assert animator.current_animation == "thinking"
        time.sleep(0.3)

        animator.stop()
        assert animator.current_animation is None

    def test_animate_success(self, mock_led_controller):
        """Test success animation."""
        animator = LEDAnimator(mock_led_controller)
        animator.animate_success(duration=0.5)

        assert animator.current_animation == "success"
        time.sleep(0.7)

        # Animation should have stopped after duration
        animator.stop()

    def test_animate_error(self, mock_led_controller):
        """Test error animation."""
        animator = LEDAnimator(mock_led_controller)
        animator.animate_error(duration=0.5)

        assert animator.current_animation == "error"
        animator.stop()

    def test_animate_listening(self, mock_led_controller):
        """Test listening animation."""
        animator = LEDAnimator(mock_led_controller)
        animator.animate_listening()

        assert animator.current_animation == "listening"
        animator.stop()

    def test_set_idle(self, mock_led_controller):
        """Test idle state."""
        animator = LEDAnimator(mock_led_controller)
        animator.set_idle()

        # Should set a dim color
        color = mock_led_controller.get_current_color()
        assert color == (10, 10, 10)

    def test_stop_clears_animation(self, mock_led_controller):
        """Test that stop clears the current animation."""
        animator = LEDAnimator(mock_led_controller)
        animator.animate_thinking()
        animator.stop()

        assert animator.current_animation is None


class TestAudioDeviceManager:
    """Tests for AudioDeviceManager."""

    def test_init_mock(self):
        """Test mock mode initialization."""
        manager = AudioDeviceManager(mock=True)
        assert manager.mock is True
        assert manager.has_speaker is True
        assert manager.has_microphone is True

    def test_playback_devices(self):
        """Test getting playback devices."""
        manager = AudioDeviceManager(mock=True)
        devices = manager.playback_devices
        assert isinstance(devices, list)
        assert len(devices) > 0

    def test_capture_devices(self):
        """Test getting capture devices."""
        manager = AudioDeviceManager(mock=True)
        devices = manager.capture_devices
        assert isinstance(devices, list)

    def test_get_default_playback(self):
        """Test getting default playback device."""
        manager = AudioDeviceManager(mock=True)
        device = manager.get_default_playback()
        assert device is not None

    def test_get_default_capture(self):
        """Test getting default capture device."""
        manager = AudioDeviceManager(mock=True)
        device = manager.get_default_capture()
        assert device is not None

    def test_test_speaker_mock(self):
        """Test speaker test in mock mode."""
        manager = AudioDeviceManager(mock=True)
        result = manager.test_speaker()
        assert result is True

    def test_test_microphone_mock(self):
        """Test microphone test in mock mode."""
        manager = AudioDeviceManager(mock=True)
        result = manager.test_microphone()
        assert result is True

    def test_set_volume_mock(self):
        """Test volume setting in mock mode."""
        manager = AudioDeviceManager(mock=True)
        result = manager.set_volume(50)
        assert result is True

    def test_get_volume_mock(self):
        """Test volume getting in mock mode."""
        manager = AudioDeviceManager(mock=True)
        volume = manager.get_volume()
        assert volume == 80  # Mock default

    def test_get_device_info(self):
        """Test device info retrieval."""
        manager = AudioDeviceManager(mock=True)
        info = manager.get_device_info()

        assert "has_speaker" in info
        assert "has_microphone" in info
        assert "playback_devices" in info
        assert "capture_devices" in info
        assert "volume" in info
