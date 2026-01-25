"""
Main Flask application for the AI-powered Storyteller.

Provides the entry point for the web application with all services initialized.
"""

import os
import sys
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .config import get_config, Config
from .state import StorytellerState
from .services.tts_engine import TTSEngine
from .services.audio_manager import AudioManager
from .services.speech_recognizer import SpeechRecognizer
from .services.story_generator import StoryGenerator
from .hardware.rfid_handler import get_rfid_handler, RFIDPollingLoop
from .hardware.led_controller import get_led_controller, LEDAnimator
from .hardware.audio_device import AudioDeviceManager
from .hardware.length_slider import get_slider_controller
from .routes.api import api_bp
from .routes.web import web_bp
from .utils.logger import setup_logger, get_logger


def create_app(config_class=None):
    """
    Create and configure the Flask application.

    Args:
        config_class: Configuration class to use (default: auto-detect).

    Returns:
        Configured Flask application.
    """
    # Get configuration
    if config_class is None:
        config_class = get_config()

    # Set up logging
    setup_logger(
        name="raspi_storyteller",
        log_file=config_class.LOG_FILE,
        level=config_class.LOG_LEVEL,
    )
    logger = get_logger(__name__)

    # Create Flask app
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent.parent.parent / "templates"),
        static_folder=str(Path(__file__).parent.parent.parent / "static"),
    )

    # Load configuration
    app.config.from_object(config_class)
    config_class.init_app(app)

    # Enable CORS
    CORS(app)

    # Initialize state
    app.state = StorytellerState()
    logger.info("StorytellerState initialized")

    # Initialize services
    mock_mode = config_class.MOCK_HARDWARE or os.getenv("MOCK_HARDWARE", "").lower() in ("true", "1")
    mock_ollama = config_class.MOCK_OLLAMA or os.getenv("MOCK_OLLAMA", "").lower() in ("true", "1")

    # TTS Engine
    app.tts_engine = TTSEngine(
        provider=config_class.TTS_PROVIDER,
        cache_dir=str(config_class.AUDIO_CACHE_DIR),
        max_cache_size_mb=config_class.MAX_CACHE_SIZE_MB,
        voice=config_class.EDGE_TTS_VOICE,
        language=config_class.SPEECH_LANGUAGE,
    )
    logger.info(f"TTSEngine initialized with provider: {config_class.TTS_PROVIDER}, language: {config_class.SPEECH_LANGUAGE}")

    # Audio Manager
    app.audio_manager = AudioManager(mock=mock_mode)
    logger.info("AudioManager initialized")

    # Speech Recognizer
    app.speech_recognizer = SpeechRecognizer(
        language=config_class.SPEECH_LANGUAGE,
        timeout=config_class.SPEECH_TIMEOUT,
        mock=mock_mode,
    )
    logger.info("SpeechRecognizer initialized")

    # Story Generator
    # Extract short language code (e.g., 'it' from 'it-IT' or 'it')
    story_language = config_class.SPEECH_LANGUAGE.split("-")[0] if config_class.SPEECH_LANGUAGE else "es"
    app.story_generator = StoryGenerator(
        ollama_host=config_class.OLLAMA_HOST,
        model=config_class.OLLAMA_MODEL,
        timeout=config_class.OLLAMA_TIMEOUT,
        language=story_language,
        mock=mock_ollama,
    )
    logger.info(f"StoryGenerator initialized with language: {story_language}")

    # Audio Device Manager
    app.audio_device = AudioDeviceManager(mock=mock_mode)
    logger.info("AudioDeviceManager initialized")

    # LED Controller and Animator
    led_controller = get_led_controller(
        mock=mock_mode,
        led_count=config_class.LED_COUNT,
        led_pin=config_class.LED_PIN,
        brightness=config_class.LED_BRIGHTNESS,
    )
    app.led_controller = led_controller
    app.led_animator = LEDAnimator(led_controller)
    logger.info("LEDController initialized")

    # Slider Controller for story length
    slider_controller = get_slider_controller(
        mock=mock_mode,
        spi_bus=config_class.SLIDER_SPI_BUS,
        spi_device=config_class.SLIDER_SPI_DEVICE,
        adc_channel=config_class.SLIDER_ADC_CHANNEL,
    )
    app.slider_controller = slider_controller
    # Set initial story length from slider or default
    initial_minutes = slider_controller.get_minutes()
    app.state.set_story_length(initial_minutes)
    logger.info(f"SliderController initialized (initial length: {initial_minutes} min)")

    # RFID Handler and Polling Loop
    rfid_handler = get_rfid_handler(mock=mock_mode)
    app.rfid_handler = rfid_handler

    def on_card_detected(uid: str, text: str):
        """Callback when RFID card is detected."""
        logger.info(f"RFID card detected: {uid}")

        # Check debounce
        if not app.state.should_process_card(uid, config_class.RFID_DEBOUNCE_TIME):
            logger.debug(f"Card {uid} debounced")
            return

        # Look up animal for this card
        animal = app.state.get_animal_for_card(uid)
        if animal:
            logger.info(f"Card {uid} mapped to animal: {animal}")
            app.state.add_animal(animal)
            # Trigger success animation for visual feedback
            if app.led_animator:
                app.led_animator.animate_success(duration=0.5)
        else:
            logger.warning(f"Unknown card: {uid}")
            # Trigger error animation for unknown cards
            if app.led_animator:
                app.led_animator.animate_error(duration=0.5)

    app.rfid_polling = RFIDPollingLoop(
        handler=rfid_handler,
        on_card_detected=on_card_detected,
        debounce_time=config_class.RFID_DEBOUNCE_TIME,
    )
    logger.info("RFID polling loop initialized")

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)
    logger.info("Routes registered")

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return {"error": "Internal server error"}, 500

    # Startup hook
    @app.before_request
    def startup():
        """Start background services on first request."""
        if not hasattr(app, "_started"):
            app._started = True
            # Start RFID polling if not in testing mode
            if not app.config.get("TESTING"):
                app.rfid_polling.start()
                logger.info("RFID polling started")
            # Set LEDs to idle
            app.led_animator.set_idle()

    # Shutdown hook
    @app.teardown_appcontext
    def shutdown(exception=None):
        """Clean up on shutdown."""
        pass

    logger.info(f"Application created (env={config_class.FLASK_ENV})")
    return app


def cleanup_app(app):
    """Clean up application resources."""
    logger = get_logger(__name__)

    try:
        if hasattr(app, "rfid_polling"):
            app.rfid_polling.stop()
        if hasattr(app, "led_animator"):
            app.led_animator.stop()
        if hasattr(app, "led_controller"):
            app.led_controller.cleanup()
        if hasattr(app, "slider_controller"):
            app.slider_controller.cleanup()
        if hasattr(app, "audio_manager"):
            app.audio_manager.cleanup()
        if hasattr(app, "rfid_handler"):
            app.rfid_handler.cleanup()
        logger.info("Application cleaned up")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


def main():
    """Main entry point for running the application."""
    app = create_app()

    try:
        port = app.config.get("PORT", 5000)
        debug = app.config.get("DEBUG", False)

        print(f"\n🎭 AI-powered Storyteller starting...")
        print(f"   Web interface: http://localhost:{port}")
        print(f"   Manage cards:  http://localhost:{port}/manage")
        print(f"   Voice test:    http://localhost:{port}/voice_test")
        print(f"\n   Press Ctrl+C to stop\n")

        app.run(
            host="0.0.0.0",
            port=port,
            debug=debug,
            use_reloader=debug,
        )
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
    finally:
        cleanup_app(app)


if __name__ == "__main__":
    main()
