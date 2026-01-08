"""
RFID reader handler for RC522 module.

Provides abstraction for RFID card detection with mock support.
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class RFIDHandlerBase(ABC):
    """Abstract base class for RFID handlers."""

    @abstractmethod
    def read_card(self, timeout: float = 1.0) -> Optional[Tuple[str, str]]:
        """
        Read an RFID card.

        Args:
            timeout: Maximum time to wait for a card (seconds).

        Returns:
            Tuple of (uid, text) or None if no card detected.
        """
        pass

    @abstractmethod
    def write_card(self, text: str) -> bool:
        """
        Write text to an RFID card.

        Args:
            text: Text to write to the card.

        Returns:
            True if write succeeded.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up hardware resources."""
        pass


class RC522Handler(RFIDHandlerBase):
    """
    Handler for RC522 RFID module via SPI.

    Requires:
    - SPI enabled on Raspberry Pi
    - mfrc522 library installed
    """

    def __init__(self):
        """Initialize the RC522 RFID handler."""
        self._reader = None
        self._init_reader()

    def _init_reader(self) -> None:
        """Initialize the MFRC522 reader."""
        try:
            from mfrc522 import SimpleMFRC522

            self._reader = SimpleMFRC522()
            logger.info("RC522 RFID reader initialized")
        except ImportError:
            logger.error("mfrc522 library not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize RFID reader: {e}")
            raise

    def read_card(self, timeout: float = 1.0) -> Optional[Tuple[str, str]]:
        """Read an RFID card with timeout."""
        try:
            # SimpleMFRC522.read() is blocking, so we use read_no_block()
            # and poll with timeout
            start_time = time.time()

            while time.time() - start_time < timeout:
                uid, text = self._reader.read_no_block()
                if uid is not None:
                    uid_str = str(uid)
                    text_str = text.strip() if text else ""
                    logger.info(f"Card detected: UID={uid_str}")
                    return (uid_str, text_str)
                time.sleep(0.1)

            return None
        except Exception as e:
            logger.error(f"RFID read failed: {e}")
            return None

    def write_card(self, text: str) -> bool:
        """Write text to an RFID card."""
        try:
            self._reader.write(text)
            logger.info(f"Wrote to card: {text[:20]}...")
            return True
        except Exception as e:
            logger.error(f"RFID write failed: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        try:
            import RPi.GPIO as GPIO

            GPIO.cleanup()
            logger.info("RFID handler cleaned up")
        except Exception:
            pass


class MockRFIDHandler(RFIDHandlerBase):
    """
    Mock RFID handler for testing without hardware.

    Allows injecting card data for testing.
    """

    def __init__(self):
        """Initialize mock handler."""
        self._injected_cards = []
        self._current_index = 0
        logger.info("Mock RFID handler initialized")

    def inject_card(self, uid: str, text: str = "") -> None:
        """
        Inject a card for testing.

        Args:
            uid: Card UID.
            text: Card text content.
        """
        self._injected_cards.append((uid, text))
        logger.debug(f"Injected card: UID={uid}")

    def clear_injected_cards(self) -> None:
        """Clear all injected cards."""
        self._injected_cards.clear()
        self._current_index = 0

    def read_card(self, timeout: float = 1.0) -> Optional[Tuple[str, str]]:
        """Read next injected card."""
        if self._current_index < len(self._injected_cards):
            card = self._injected_cards[self._current_index]
            self._current_index += 1
            logger.info(f"[MOCK] Card read: UID={card[0]}")
            return card
        return None

    def write_card(self, text: str) -> bool:
        """Mock write (always succeeds)."""
        logger.info(f"[MOCK] Card write: {text[:20]}...")
        return True

    def cleanup(self) -> None:
        """No cleanup needed for mock."""
        pass


class RFIDPollingLoop:
    """
    Daemon thread for continuous RFID polling.

    Runs in background and calls callback when cards are detected.
    """

    def __init__(
        self,
        handler: RFIDHandlerBase,
        on_card_detected: Callable[[str, str], None],
        debounce_time: float = 1.5,
    ):
        """
        Initialize the polling loop.

        Args:
            handler: RFID handler instance.
            on_card_detected: Callback function (uid, text).
            debounce_time: Minimum time between same card reads.
        """
        self.handler = handler
        self.on_card_detected = on_card_detected
        self.debounce_time = debounce_time

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_uid: Optional[str] = None
        self._last_time: float = 0

    def start(self) -> None:
        """Start the polling loop in a daemon thread."""
        if self._running:
            logger.warning("RFID polling loop already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("RFID polling loop started")

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("RFID polling loop stopped")

    def _poll_loop(self) -> None:
        """Main polling loop (runs in thread)."""
        while self._running:
            try:
                result = self.handler.read_card(timeout=0.5)
                if result:
                    uid, text = result

                    # Debounce check
                    now = time.time()
                    if (
                        uid == self._last_uid
                        and now - self._last_time < self.debounce_time
                    ):
                        continue

                    self._last_uid = uid
                    self._last_time = now

                    # Call callback
                    try:
                        self.on_card_detected(uid, text)
                    except Exception as e:
                        logger.error(f"Card callback error: {e}")

                time.sleep(0.1)
            except Exception as e:
                logger.error(f"RFID polling error: {e}")
                time.sleep(1.0)

    @property
    def is_running(self) -> bool:
        """Check if polling loop is running."""
        return self._running


def get_rfid_handler(mock: bool = False) -> RFIDHandlerBase:
    """
    Factory function to get appropriate RFID handler.

    Args:
        mock: If True, return mock handler.

    Returns:
        RFID handler instance.
    """
    if mock:
        return MockRFIDHandler()

    try:
        return RC522Handler()
    except Exception as e:
        logger.warning(f"Failed to initialize real RFID handler: {e}")
        logger.info("Falling back to mock RFID handler")
        return MockRFIDHandler()


# Export both classes for backwards compatibility
RFIDHandler = RC522Handler
