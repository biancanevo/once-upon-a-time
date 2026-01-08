"""
API routes for the Storyteller application.

Provides REST API endpoints for story generation, voice commands, and card management.
"""

import asyncio
from flask import Blueprint, jsonify, request, current_app, send_from_directory
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def run_async(coro):
    """Run an async coroutine in the Flask context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# Story endpoints

@api_bp.route("/story/generate", methods=["POST"])
def generate_story():
    """
    Generate a new story with audio.

    Request JSON:
    {
        "animals": ["cat", "dog"],  # Optional, uses selected animals if not provided
        "tts_provider": "edge"      # Optional, override TTS provider
    }

    Response JSON:
    {
        "full_text": "...",
        "audio_segments": [{"text": "...", "audio": "/api/audio/<filename>"}],
        "animals": [...],
        "status": "success" | "error"
    }
    """
    try:
        data = request.get_json() or {}
        state = current_app.state
        tts_engine = current_app.tts_engine
        story_generator = current_app.story_generator
        led_animator = current_app.led_animator

        # Get animals from request or state
        animals = data.get("animals", state.selected_animals)
        if not animals:
            return jsonify({
                "status": "error",
                "error": "No animals selected",
            }), 400

        # Override TTS provider if requested
        tts_provider = data.get("tts_provider")
        if tts_provider:
            tts_engine.set_provider(tts_provider)

        # Start LED animation
        if led_animator:
            led_animator.animate_thinking()

        # Set generating state
        state.set_generating(True)

        try:
            # Generate story with audio
            result = run_async(
                story_generator.generate_story_with_audio(animals, tts_engine)
            )

            # Update audio paths to API URLs
            for segment in result.get("audio_segments", []):
                audio_path = segment.get("audio", "")
                if audio_path:
                    filename = Path(audio_path).name
                    segment["audio"] = f"/api/audio/{filename}"

            # Success animation
            if led_animator:
                led_animator.animate_success()

            return jsonify(result)

        except Exception as e:
            logger.error(f"Story generation failed: {e}")
            if led_animator:
                led_animator.animate_error()
            return jsonify({
                "status": "error",
                "error": str(e),
            }), 500

        finally:
            state.set_generating(False)

    except Exception as e:
        logger.error(f"API error in generate_story: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
        }), 500


@api_bp.route("/story/current", methods=["GET"])
def get_current_story():
    """
    Get the current story state.

    Response JSON:
    {
        "selected_animals": [...],
        "current_story": {...} | null,
        "is_generating": bool,
        "is_playing": bool
    }
    """
    try:
        state = current_app.state
        return jsonify(state.to_dict())
    except Exception as e:
        logger.error(f"API error in get_current_story: {e}")
        return jsonify({"error": str(e)}), 500


# Audio endpoints

@api_bp.route("/audio/<filename>", methods=["GET"])
def serve_audio(filename):
    """Serve audio files from the cache directory."""
    try:
        cache_dir = current_app.config.get("AUDIO_CACHE_DIR", "./audio_cache")
        return send_from_directory(
            cache_dir,
            filename,
            mimetype="audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
        )
    except Exception as e:
        logger.error(f"Failed to serve audio {filename}: {e}")
        return jsonify({"error": "Audio file not found"}), 404


# Voice endpoints

@api_bp.route("/voice/listen", methods=["POST"])
def listen_voice():
    """
    Listen for a voice command.

    Request JSON:
    {
        "timeout": 5  # Optional, override default timeout
    }

    Response JSON:
    {
        "text": "recognized text",
        "animals": ["parsed", "animals"],
        "status": "success" | "error"
    }
    """
    try:
        data = request.get_json() or {}
        speech_recognizer = current_app.speech_recognizer
        led_animator = current_app.led_animator

        timeout = data.get("timeout")

        # Start listening animation
        if led_animator:
            led_animator.animate_listening()

        try:
            # Listen for voice command
            text, animals = run_async(speech_recognizer.listen_for_command())

            # Stop animation
            if led_animator:
                if text:
                    led_animator.animate_success(duration=1.0)
                else:
                    led_animator.set_idle()

            return jsonify({
                "text": text,
                "animals": animals,
                "status": "success" if text else "no_speech",
            })

        except Exception as e:
            logger.error(f"Voice recognition failed: {e}")
            if led_animator:
                led_animator.animate_error()
            return jsonify({
                "text": "",
                "animals": [],
                "status": "error",
                "error": str(e),
            }), 500

    except Exception as e:
        logger.error(f"API error in listen_voice: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/voice/languages", methods=["GET"])
def get_voice_languages():
    """Get available voice recognition languages."""
    return jsonify({
        "languages": [
            {"code": "es-ES", "name": "Spanish (Spain)"},
            {"code": "es-MX", "name": "Spanish (Mexico)"},
            {"code": "en-US", "name": "English (US)"},
            {"code": "en-GB", "name": "English (UK)"},
        ],
        "current": current_app.speech_recognizer.language,
    })


@api_bp.route("/voice/language", methods=["POST"])
def set_voice_language():
    """Set voice recognition language."""
    try:
        data = request.get_json() or {}
        language = data.get("language")

        if not language:
            return jsonify({"error": "Language code required"}), 400

        current_app.speech_recognizer.set_language(language)
        return jsonify({"status": "success", "language": language})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Card management endpoints

@api_bp.route("/cards", methods=["GET"])
def list_cards():
    """
    List all registered RFID cards.

    Response JSON:
    {
        "<uid>": {
            "animal": "...",
            "registered": "ISO timestamp"
        },
        ...
    }
    """
    try:
        state = current_app.state
        return jsonify(state.cards_db)
    except Exception as e:
        logger.error(f"API error in list_cards: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/cards/save", methods=["POST"])
def save_card():
    """
    Register a new RFID card with an animal.

    Request JSON:
    {
        "uid": "card uid",
        "animal": "animal name"
    }

    Response JSON:
    {
        "status": "saved",
        "uid": "...",
        "animal": "..."
    }
    """
    try:
        data = request.get_json() or {}
        uid = data.get("uid")
        animal = data.get("animal")

        if not uid or not animal:
            return jsonify({
                "status": "error",
                "error": "Both uid and animal are required",
            }), 400

        state = current_app.state
        state.register_card(uid, animal)

        return jsonify({
            "status": "saved",
            "uid": uid,
            "animal": animal,
        })
    except Exception as e:
        logger.error(f"API error in save_card: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/cards/delete/<uid>", methods=["DELETE"])
def delete_card(uid):
    """
    Delete an RFID card.

    Response JSON:
    {
        "status": "deleted" | "not_found"
    }
    """
    try:
        state = current_app.state
        if state.unregister_card(uid):
            return jsonify({"status": "deleted", "uid": uid})
        else:
            return jsonify({"status": "not_found", "uid": uid}), 404
    except Exception as e:
        logger.error(f"API error in delete_card: {e}")
        return jsonify({"error": str(e)}), 500


# Animal management endpoints

@api_bp.route("/animals", methods=["GET"])
def get_selected_animals():
    """Get currently selected animals."""
    try:
        state = current_app.state
        return jsonify({"animals": state.selected_animals})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/animals", methods=["POST"])
def add_animal():
    """Add an animal to the selection."""
    try:
        data = request.get_json() or {}
        animal = data.get("animal")

        if not animal:
            return jsonify({"error": "Animal name required"}), 400

        state = current_app.state
        state.add_animal(animal)
        return jsonify({"status": "added", "animals": state.selected_animals})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/animals/<animal>", methods=["DELETE"])
def remove_animal(animal):
    """Remove an animal from the selection."""
    try:
        state = current_app.state
        state.remove_animal(animal)
        return jsonify({"status": "removed", "animals": state.selected_animals})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/animals/clear", methods=["POST"])
def clear_animals():
    """Clear all selected animals."""
    try:
        state = current_app.state
        state.clear_animals()
        return jsonify({"status": "cleared", "animals": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# System status endpoints

@api_bp.route("/status", methods=["GET"])
def get_status():
    """
    Get system status.

    Response JSON:
    {
        "state": {...},
        "hardware": {...},
        "cache": {...}
    }
    """
    try:
        state = current_app.state
        tts_engine = current_app.tts_engine
        audio_device = current_app.audio_device

        return jsonify({
            "state": state.to_dict(),
            "tts_provider": tts_engine.provider_name,
            "cache": tts_engine.get_cache_stats(),
            "audio_devices": audio_device.get_device_info() if audio_device else {},
        })
    except Exception as e:
        logger.error(f"API error in get_status: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/cache/clear", methods=["POST"])
def clear_cache():
    """Clear the audio cache."""
    try:
        tts_engine = current_app.tts_engine
        tts_engine.clear_cache()
        return jsonify({"status": "cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
