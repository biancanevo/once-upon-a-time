"""
Length slider controller for variable story duration.

Provides abstraction for reading a potentiometer via MCP3008 ADC
with mock support for development.
"""

from abc import ABC, abstractmethod
from typing import Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Story length mapping based on slider position
# Format: (min_minutes, max_minutes, length_description, paragraph_range, word_target)
LENGTH_RANGES = [
    (1, 3, "very short", "1-2 paragraphs", 300),      # ~150-450 words
    (4, 6, "short", "3-4 paragraphs", 750),           # ~600-900 words
    (7, 9, "medium-length", "5-6 paragraphs", 1200),  # ~1050-1350 words
    (10, 12, "long", "7-8 paragraphs", 1650),         # ~1500-1800 words
    (13, 15, "very long, detailed", "9-10 paragraphs", 2100),  # ~1950-2250 words
]


def get_length_params(minutes: int) -> dict:
    """
    Get story length parameters based on target duration in minutes.

    Args:
        minutes: Target story duration (1-15).

    Returns:
        Dictionary with length_description, paragraph_range, word_target, and token_limit.
    """
    # Clamp minutes to valid range
    minutes = max(1, min(15, minutes))

    for min_min, max_min, description, paragraphs, word_target in LENGTH_RANGES:
        if min_min <= minutes <= max_min:
            # Token limit: approximately 1.2 tokens per word, plus some buffer
            token_limit = int(word_target * 1.3)
            return {
                "length_description": description,
                "paragraph_range": paragraphs,
                "word_target": word_target,
                "token_limit": token_limit,
                "minutes": minutes,
            }

    # Default to medium if somehow not matched
    return {
        "length_description": "medium-length",
        "paragraph_range": "5-6 paragraphs",
        "word_target": 1200,
        "token_limit": 1560,
        "minutes": minutes,
    }


class SliderControllerBase(ABC):
    """Abstract base class for slider controllers."""

    @abstractmethod
    def read_value(self) -> float:
        """
        Read slider position as a normalized value.

        Returns:
            Float between 0.0 and 1.0 representing slider position.
        """
        pass

    @abstractmethod
    def get_minutes(self) -> int:
        """
        Get story duration in minutes based on slider position.

        Returns:
            Integer between 1 and 15 representing target story duration.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up hardware resources."""
        pass


class MCP3008SliderController(SliderControllerBase):
    """
    Slider controller using MCP3008 ADC for potentiometer reading.

    Reads analog value from potentiometer connected to MCP3008 ADC.
    Uses SPI interface via spidev library.

    Hardware connections:
    - MCP3008 VDD, VREF -> 3.3V
    - MCP3008 AGND, DGND -> Ground
    - MCP3008 CLK -> GPIO 11 (SCLK)
    - MCP3008 DOUT -> GPIO 9 (MISO)
    - MCP3008 DIN -> GPIO 10 (MOSI)
    - MCP3008 CS -> GPIO 7 (CE1) - to avoid conflict with RFID on CE0
    - Potentiometer: GND, center to CH0, 3.3V
    """

    def __init__(
        self,
        spi_bus: int = 0,
        spi_device: int = 1,  # CE1 to avoid conflict with RFID
        adc_channel: int = 0,
    ):
        """
        Initialize the MCP3008 slider controller.

        Args:
            spi_bus: SPI bus number (usually 0).
            spi_device: SPI device/chip select (1 for CE1).
            adc_channel: MCP3008 channel (0-7).
        """
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.adc_channel = adc_channel
        self._spi = None
        self._init_spi()

    def _init_spi(self) -> None:
        """Initialize SPI communication."""
        try:
            import spidev

            self._spi = spidev.SpiDev()
            self._spi.open(self.spi_bus, self.spi_device)
            self._spi.max_speed_hz = 1350000  # 1.35 MHz
            logger.info(
                f"MCP3008 slider initialized on SPI{self.spi_bus}.{self.spi_device}, "
                f"channel {self.adc_channel}"
            )
        except ImportError:
            logger.error("spidev library not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize MCP3008: {e}")
            raise

    def _read_adc(self, channel: int) -> int:
        """
        Read raw value from MCP3008 ADC channel.

        Args:
            channel: ADC channel (0-7).

        Returns:
            Raw 10-bit ADC value (0-1023).
        """
        if channel < 0 or channel > 7:
            raise ValueError(f"Invalid ADC channel: {channel}")

        # MCP3008 SPI protocol:
        # Send: [start bit, single/diff mode + channel, don't care]
        # Receive: [don't care, leading zeros + 10-bit value]
        cmd = [1, (8 + channel) << 4, 0]
        response = self._spi.xfer2(cmd)

        # Extract 10-bit value from response
        value = ((response[1] & 3) << 8) + response[2]
        return value

    def read_value(self) -> float:
        """Read slider position as normalized value (0.0 to 1.0)."""
        try:
            raw_value = self._read_adc(self.adc_channel)
            # Normalize to 0.0-1.0 range
            normalized = raw_value / 1023.0
            return normalized
        except Exception as e:
            logger.error(f"Failed to read slider value: {e}")
            return 0.5  # Default to middle position on error

    def get_minutes(self) -> int:
        """Get story duration in minutes based on slider position."""
        value = self.read_value()
        # Map 0.0-1.0 to 1-15 minutes
        minutes = int(1 + value * 14)
        return max(1, min(15, minutes))

    def cleanup(self) -> None:
        """Clean up SPI resources."""
        try:
            if self._spi:
                self._spi.close()
                logger.info("MCP3008 slider cleaned up")
        except Exception:
            pass


class MockSliderController(SliderControllerBase):
    """
    Mock slider controller for development and testing.

    Allows setting slider value programmatically via web interface.
    """

    def __init__(self, initial_value: float = 0.33):
        """
        Initialize mock slider controller.

        Args:
            initial_value: Initial slider position (0.0-1.0).
                          Default 0.33 corresponds to ~5 minutes.
        """
        self._value = max(0.0, min(1.0, initial_value))
        logger.info(f"Mock slider controller initialized (value={self._value:.2f})")

    def set_value(self, value: float) -> None:
        """
        Set slider value (for web interface injection).

        Args:
            value: Slider position (0.0-1.0).
        """
        self._value = max(0.0, min(1.0, value))
        logger.debug(f"Mock slider value set to {self._value:.2f}")

    def set_minutes(self, minutes: int) -> None:
        """
        Set slider value based on target minutes.

        Args:
            minutes: Target story duration (1-15).
        """
        minutes = max(1, min(15, minutes))
        # Map 1-15 to 0.0-1.0
        self._value = (minutes - 1) / 14.0
        logger.debug(f"Mock slider set to {minutes} minutes (value={self._value:.2f})")

    def read_value(self) -> float:
        """Read current slider position."""
        return self._value

    def get_minutes(self) -> int:
        """Get story duration in minutes based on slider position."""
        # Map 0.0-1.0 to 1-15 minutes
        minutes = int(1 + self._value * 14)
        return max(1, min(15, minutes))

    def cleanup(self) -> None:
        """No cleanup needed for mock."""
        pass


def get_slider_controller(
    mock: bool = False,
    spi_bus: int = 0,
    spi_device: int = 1,
    adc_channel: int = 0,
) -> SliderControllerBase:
    """
    Factory function to get appropriate slider controller.

    Args:
        mock: If True, return mock controller.
        spi_bus: SPI bus number for real hardware.
        spi_device: SPI device number for real hardware.
        adc_channel: ADC channel for real hardware.

    Returns:
        Slider controller instance.
    """
    if mock:
        return MockSliderController()

    try:
        return MCP3008SliderController(
            spi_bus=spi_bus,
            spi_device=spi_device,
            adc_channel=adc_channel,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize MCP3008 slider: {e}")
        logger.info("Falling back to mock slider controller")
        return MockSliderController()


# Export for backwards compatibility
SliderController = MCP3008SliderController
