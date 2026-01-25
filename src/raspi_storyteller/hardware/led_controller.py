"""
LED controller for NeoPixel/WS2812 LED rings.

Provides animations and status feedback with mock support.
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# RGB color type
Color = Tuple[int, int, int]

# Predefined colors
COLORS = {
    "off": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "purple": (128, 0, 128),
    "orange": (255, 165, 0),
    "white": (255, 255, 255),
    "cyan": (0, 255, 255),
    "pink": (255, 105, 180),
}

# Card type colors
CARD_TYPE_COLORS = {
    "character": (0, 255, 0),      # Green for characters
    "environment": (0, 128, 255),  # Blue for environments
    "moral_lesson": (180, 0, 255), # Purple/Violet for moral lessons
}


class LEDControllerBase(ABC):
    """Abstract base class for LED controllers."""

    @abstractmethod
    def set_color(self, color: Color) -> None:
        """Set all LEDs to a single color."""
        pass

    @abstractmethod
    def set_pixel(self, index: int, color: Color) -> None:
        """Set a single LED to a color."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Turn off all LEDs."""
        pass

    @abstractmethod
    def show(self) -> None:
        """Update the LED display."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources."""
        pass


class NeoPixelController(LEDControllerBase):
    """
    Controller for WS2812/NeoPixel LED rings on Raspberry Pi.

    Requires:
    - rpi_ws281x library installed
    - Running as root (for GPIO access)
    """

    def __init__(
        self,
        led_count: int = 12,
        led_pin: int = 18,
        brightness: float = 0.5,
    ):
        """
        Initialize the NeoPixel controller.

        Args:
            led_count: Number of LEDs in the ring.
            led_pin: GPIO pin number (PWM capable).
            brightness: LED brightness (0.0 to 1.0).
        """
        self.led_count = led_count
        self.led_pin = led_pin
        self.brightness = max(0.0, min(1.0, brightness))
        self._strip = None

        self._init_strip()

    def _init_strip(self) -> None:
        """Initialize the NeoPixel strip."""
        try:
            from rpi_ws281x import PixelStrip, ws

            self._strip = PixelStrip(
                self.led_count,
                self.led_pin,
                800000,  # LED signal frequency
                10,  # DMA channel
                False,  # Invert signal
                int(255 * self.brightness),  # Brightness
                0,  # Channel
                ws.WS2811_STRIP_GRB,  # Strip type
            )
            self._strip.begin()
            logger.info(f"NeoPixel initialized: {self.led_count} LEDs on pin {self.led_pin}")
        except ImportError:
            logger.error("rpi_ws281x library not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize NeoPixel: {e}")
            raise

    def set_color(self, color: Color) -> None:
        """Set all LEDs to a single color."""
        for i in range(self.led_count):
            self.set_pixel(i, color)
        self.show()

    def set_pixel(self, index: int, color: Color) -> None:
        """Set a single LED to a color."""
        if 0 <= index < self.led_count:
            from rpi_ws281x import Color as NeoColor

            self._strip.setPixelColor(index, NeoColor(*color))

    def clear(self) -> None:
        """Turn off all LEDs."""
        self.set_color(COLORS["off"])

    def show(self) -> None:
        """Update the LED display."""
        self._strip.show()

    def set_brightness(self, brightness: float) -> None:
        """Set LED brightness."""
        self.brightness = max(0.0, min(1.0, brightness))
        self._strip.setBrightness(int(255 * self.brightness))
        self.show()

    def cleanup(self) -> None:
        """Clean up and turn off LEDs."""
        self.clear()
        logger.info("NeoPixel controller cleaned up")


class MockLEDController(LEDControllerBase):
    """
    Mock LED controller for testing without hardware.

    Tracks color state for verification in tests.
    """

    def __init__(self, led_count: int = 12):
        """Initialize mock controller."""
        self.led_count = led_count
        self._pixels: List[Color] = [(0, 0, 0)] * led_count
        self._current_color: Color = (0, 0, 0)
        logger.info(f"Mock LED controller initialized: {led_count} LEDs")

    def set_color(self, color: Color) -> None:
        """Set all LEDs to a single color."""
        self._current_color = color
        self._pixels = [color] * self.led_count
        logger.debug(f"[MOCK] LED color: RGB{color}")

    def set_pixel(self, index: int, color: Color) -> None:
        """Set a single LED to a color."""
        if 0 <= index < self.led_count:
            self._pixels[index] = color

    def clear(self) -> None:
        """Turn off all LEDs."""
        self.set_color(COLORS["off"])

    def show(self) -> None:
        """Update display (no-op for mock)."""
        pass

    def get_current_color(self) -> Color:
        """Get the current LED color (for testing)."""
        return self._current_color

    def get_pixel(self, index: int) -> Color:
        """Get color of a specific LED (for testing)."""
        if 0 <= index < self.led_count:
            return self._pixels[index]
        return (0, 0, 0)

    def cleanup(self) -> None:
        """No cleanup needed for mock."""
        pass


class LEDAnimator:
    """
    Provides animated LED patterns.

    Runs animations in a background thread.
    """

    def __init__(self, controller: LEDControllerBase):
        """
        Initialize the animator.

        Args:
            controller: LED controller instance.
        """
        self.controller = controller
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_animation: Optional[str] = None

    def _run_animation(self, name: str, func, *args) -> None:
        """Run an animation in a loop."""
        self._current_animation = name
        while self._running:
            try:
                func(*args)
            except Exception as e:
                logger.error(f"Animation error: {e}")
                break

    def stop(self) -> None:
        """Stop current animation."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self._current_animation = None
        self.controller.clear()

    def animate_thinking(self) -> None:
        """Blue spinning animation while generating story."""
        self.stop()
        self._running = True

        def _thinking():
            led_count = getattr(self.controller, "led_count", 12)
            for i in range(led_count):
                if not self._running:
                    break
                self.controller.clear()
                self.controller.set_pixel(i, COLORS["blue"])
                self.controller.set_pixel((i + 1) % led_count, (0, 0, 128))
                self.controller.show()
                time.sleep(0.1)

        self._thread = threading.Thread(target=self._run_animation, args=("thinking", _thinking))
        self._thread.daemon = True
        self._thread.start()

    def animate_success(self, duration: float = 2.0) -> None:
        """Green pulse animation on success."""
        self.stop()
        self._running = True

        def _success():
            start = time.time()
            while self._running and time.time() - start < duration:
                # Fade in
                for b in range(0, 256, 10):
                    if not self._running:
                        return
                    self.controller.set_color((0, b, 0))
                    time.sleep(0.02)
                # Fade out
                for b in range(255, -1, -10):
                    if not self._running:
                        return
                    self.controller.set_color((0, b, 0))
                    time.sleep(0.02)
            self._running = False
            # Return to idle state instead of clearing
            self.controller.set_color((10, 10, 10))

        self._thread = threading.Thread(target=self._run_animation, args=("success", _success))
        self._thread.daemon = True
        self._thread.start()

    def animate_error(self, duration: float = 2.0) -> None:
        """Red flash animation on error."""
        self.stop()
        self._running = True

        def _error():
            start = time.time()
            while self._running and time.time() - start < duration:
                self.controller.set_color(COLORS["red"])
                time.sleep(0.2)
                self.controller.clear()
                time.sleep(0.2)
            self._running = False
            # Return to idle state instead of clearing
            self.controller.set_color((10, 10, 10))

        self._thread = threading.Thread(target=self._run_animation, args=("error", _error))
        self._thread.daemon = True
        self._thread.start()

    def animate_listening(self) -> None:
        """Purple pulsing animation while listening for voice."""
        self.stop()
        self._running = True

        def _listening():
            while self._running:
                # Fade in
                for b in range(0, 256, 5):
                    if not self._running:
                        return
                    self.controller.set_color((b // 2, 0, b))
                    time.sleep(0.01)
                # Fade out
                for b in range(255, -1, -5):
                    if not self._running:
                        return
                    self.controller.set_color((b // 2, 0, b))
                    time.sleep(0.01)

        self._thread = threading.Thread(target=self._run_animation, args=("listening", _listening))
        self._thread.daemon = True
        self._thread.start()

    def animate_playing(self) -> None:
        """Cyan wave animation while playing audio."""
        self.stop()
        self._running = True

        def _playing():
            led_count = getattr(self.controller, "led_count", 12)
            offset = 0
            while self._running:
                for i in range(led_count):
                    if not self._running:
                        return
                    # Create wave effect
                    brightness = int(128 + 127 * ((i + offset) % led_count) / led_count)
                    self.controller.set_pixel(i, (0, brightness, brightness))
                self.controller.show()
                offset = (offset + 1) % led_count
                time.sleep(0.08)

        self._thread = threading.Thread(target=self._run_animation, args=("playing", _playing))
        self._thread.daemon = True
        self._thread.start()

    def animate_card_detected(self, card_type: str, duration: float = 1.0) -> None:
        """
        Pulse animation when a card is detected, color based on type.

        Args:
            card_type: Type of card ('character', 'environment', 'moral_lesson')
            duration: Animation duration in seconds.
        """
        self.stop()
        self._running = True

        color = CARD_TYPE_COLORS.get(card_type, COLORS["green"])

        def _card_pulse():
            start = time.time()
            while self._running and time.time() - start < duration:
                # Fade in
                for b in range(0, 256, 15):
                    if not self._running:
                        return
                    scaled_color = (
                        int(color[0] * b / 255),
                        int(color[1] * b / 255),
                        int(color[2] * b / 255),
                    )
                    self.controller.set_color(scaled_color)
                    time.sleep(0.015)
                # Fade out
                for b in range(255, -1, -15):
                    if not self._running:
                        return
                    scaled_color = (
                        int(color[0] * b / 255),
                        int(color[1] * b / 255),
                        int(color[2] * b / 255),
                    )
                    self.controller.set_color(scaled_color)
                    time.sleep(0.015)
            self._running = False
            self.controller.set_color((10, 10, 10))

        self._thread = threading.Thread(
            target=self._run_animation, args=(f"card_{card_type}", _card_pulse)
        )
        self._thread.daemon = True
        self._thread.start()

    def set_idle(self) -> None:
        """Set LEDs to dim idle state."""
        self.stop()
        self.controller.set_color((10, 10, 10))

    @property
    def current_animation(self) -> Optional[str]:
        """Get name of currently running animation."""
        return self._current_animation if self._running else None


def get_led_controller(
    mock: bool = False,
    led_count: int = 12,
    led_pin: int = 18,
    brightness: float = 0.5,
) -> LEDControllerBase:
    """
    Factory function to get appropriate LED controller.

    Args:
        mock: If True, return mock controller.
        led_count: Number of LEDs.
        led_pin: GPIO pin number.
        brightness: LED brightness.

    Returns:
        LED controller instance.
    """
    if mock:
        return MockLEDController(led_count)

    try:
        return NeoPixelController(led_count, led_pin, brightness)
    except Exception as e:
        logger.warning(f"Failed to initialize NeoPixel: {e}")
        logger.info("Falling back to mock LED controller")
        return MockLEDController(led_count)


# Export both classes
LEDController = NeoPixelController
