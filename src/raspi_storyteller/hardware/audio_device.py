"""
Audio device detection and management.

Provides speaker and microphone detection with fallback strategies.
"""

import subprocess
from dataclasses import dataclass
from typing import List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AudioDevice:
    """Represents an audio device."""

    name: str
    card_id: int
    device_id: int
    device_type: str  # 'playback' or 'capture'
    is_default: bool = False


class AudioDeviceManager:
    """
    Manages audio device detection and selection.

    Detects available speakers and microphones on the system.
    """

    def __init__(self, mock: bool = False):
        """
        Initialize the audio device manager.

        Args:
            mock: If True, use mock device list.
        """
        self.mock = mock
        self._playback_devices: List[AudioDevice] = []
        self._capture_devices: List[AudioDevice] = []

        if not mock:
            self._detect_devices()
        else:
            self._setup_mock_devices()

        logger.info(
            f"AudioDeviceManager: {len(self._playback_devices)} playback, "
            f"{len(self._capture_devices)} capture devices"
        )

    def _setup_mock_devices(self) -> None:
        """Set up mock devices for testing."""
        self._playback_devices = [
            AudioDevice(
                name="Mock Speaker",
                card_id=0,
                device_id=0,
                device_type="playback",
                is_default=True,
            ),
        ]
        self._capture_devices = [
            AudioDevice(
                name="Mock Microphone",
                card_id=0,
                device_id=0,
                device_type="capture",
                is_default=True,
            ),
        ]

    def _detect_devices(self) -> None:
        """Detect available audio devices using aplay/arecord."""
        self._playback_devices = self._list_devices("playback")
        self._capture_devices = self._list_devices("capture")

    def _list_devices(self, device_type: str) -> List[AudioDevice]:
        """
        List audio devices of a specific type.

        Args:
            device_type: 'playback' or 'capture'.

        Returns:
            List of detected audio devices.
        """
        devices = []
        command = "aplay -l" if device_type == "playback" else "arecord -l"

        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to list {device_type} devices")
                return devices

            # Parse output
            for line in result.stdout.split("\n"):
                if line.startswith("card "):
                    try:
                        # Parse line like: "card 0: bcm2835 [bcm2835 HDMI], device 0: ..."
                        parts = line.split(":")
                        card_part = parts[0].strip()
                        card_id = int(card_part.replace("card ", ""))

                        device_part = parts[1] if len(parts) > 1 else ""
                        name = device_part.split("[")[0].strip()

                        # Extract device ID
                        device_id = 0
                        if "device " in line:
                            dev_str = line.split("device ")[1].split(":")[0]
                            device_id = int(dev_str)

                        device = AudioDevice(
                            name=name or f"Device {card_id}",
                            card_id=card_id,
                            device_id=device_id,
                            device_type=device_type,
                            is_default=(card_id == 0 and device_id == 0),
                        )
                        devices.append(device)
                        logger.debug(f"Found {device_type} device: {device.name}")
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse device line: {e}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout listing {device_type} devices")
        except FileNotFoundError:
            logger.warning(f"aplay/arecord not found (not on Linux?)")
        except Exception as e:
            logger.error(f"Error detecting {device_type} devices: {e}")

        return devices

    @property
    def playback_devices(self) -> List[AudioDevice]:
        """Get list of playback devices (speakers)."""
        return self._playback_devices.copy()

    @property
    def capture_devices(self) -> List[AudioDevice]:
        """Get list of capture devices (microphones)."""
        return self._capture_devices.copy()

    @property
    def has_speaker(self) -> bool:
        """Check if a speaker is available."""
        return len(self._playback_devices) > 0

    @property
    def has_microphone(self) -> bool:
        """Check if a microphone is available."""
        return len(self._capture_devices) > 0

    def get_default_playback(self) -> Optional[AudioDevice]:
        """Get the default playback device."""
        for device in self._playback_devices:
            if device.is_default:
                return device
        return self._playback_devices[0] if self._playback_devices else None

    def get_default_capture(self) -> Optional[AudioDevice]:
        """Get the default capture device."""
        for device in self._capture_devices:
            if device.is_default:
                return device
        return self._capture_devices[0] if self._capture_devices else None

    def test_speaker(self) -> bool:
        """
        Test if speaker output works.

        Returns:
            True if speaker test succeeded.
        """
        if self.mock:
            logger.info("[MOCK] Speaker test passed")
            return True

        try:
            # Try to play a test sound
            result = subprocess.run(
                ["aplay", "-d", "1", "/dev/zero"],
                capture_output=True,
                timeout=3,
            )
            success = result.returncode == 0
            logger.info(f"Speaker test: {'passed' if success else 'failed'}")
            return success
        except Exception as e:
            logger.warning(f"Speaker test failed: {e}")
            return False

    def test_microphone(self) -> bool:
        """
        Test if microphone input works.

        Returns:
            True if microphone test succeeded.
        """
        if self.mock:
            logger.info("[MOCK] Microphone test passed")
            return True

        try:
            # Try to record briefly
            result = subprocess.run(
                ["arecord", "-d", "1", "-f", "cd", "/dev/null"],
                capture_output=True,
                timeout=3,
            )
            success = result.returncode == 0
            logger.info(f"Microphone test: {'passed' if success else 'failed'}")
            return success
        except Exception as e:
            logger.warning(f"Microphone test failed: {e}")
            return False

    def set_volume(self, volume: int) -> bool:
        """
        Set system volume using amixer.

        Args:
            volume: Volume level (0-100).

        Returns:
            True if volume was set successfully.
        """
        if self.mock:
            logger.info(f"[MOCK] Volume set to {volume}%")
            return True

        volume = max(0, min(100, volume))

        try:
            # Try different mixer controls
            controls = ["PCM", "Speaker", "Master"]
            for control in controls:
                result = subprocess.run(
                    ["amixer", "set", control, f"{volume}%"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    logger.info(f"Volume set to {volume}% via {control}")
                    return True

            logger.warning("Could not set volume via any control")
            return False
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False

    def get_volume(self) -> int:
        """
        Get current system volume.

        Returns:
            Current volume level (0-100), or -1 if unknown.
        """
        if self.mock:
            return 80

        try:
            result = subprocess.run(
                ["amixer", "get", "PCM"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Parse output for percentage
                for line in result.stdout.split("\n"):
                    if "%" in line:
                        # Extract percentage from [XX%]
                        start = line.find("[")
                        end = line.find("%")
                        if start != -1 and end != -1:
                            return int(line[start + 1 : end])

            return -1
        except Exception:
            return -1

    def get_device_info(self) -> dict:
        """
        Get summary of audio device status.

        Returns:
            Dictionary with device information.
        """
        return {
            "has_speaker": self.has_speaker,
            "has_microphone": self.has_microphone,
            "playback_devices": [
                {"name": d.name, "card": d.card_id, "device": d.device_id}
                for d in self._playback_devices
            ],
            "capture_devices": [
                {"name": d.name, "card": d.card_id, "device": d.device_id}
                for d in self._capture_devices
            ],
            "volume": self.get_volume(),
        }
