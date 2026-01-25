"""
API routes for the Storyteller application.

Provides REST API endpoints for story generation, voice commands, and card management.
"""

import asyncio
from flask import Blueprint, jsonify, request, current_app, send_from_directory
from pathlib import Path

from ..state import CardType, CharacterRole
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
        "tts_provider": "edge",     # Optional, override TTS provider
        "story_minutes": 5          # Optional, story duration in minutes (1-15)
    }

    Response JSON:
    {
        "full_text": "...",
        "audio_segments": [{"text": "...", "audio": "/api/audio/<filename>"}],
        "animals": [...],
        "characters": [...],
        "environment": "...",
        "moral_lesson": "...",
        "story_minutes": 5,
        "status": "success" | "error"
    }
    """
    try:
        data = request.get_json() or {}
        state = current_app.state
        tts_engine = current_app.tts_engine
        story_generator = current_app.story_generator
        led_animator = current_app.led_animator

        # Check for character cards first (new system)
        if state.selected_cards:
            if not state.has_character_card():
                return jsonify({
                    "status": "error",
                    "error": "At least one character card is required to start a story",
                }), 400

        # Get animals from request or state (for legacy compatibility)
        animals = data.get("animals", state.selected_animals)
        if not animals and not state.selected_cards:
            return jsonify({
                "status": "error",
                "error": "No characters selected. Please add at least one character card.",
            }), 400

        # Get story duration from request, slider, or state
        story_minutes = data.get("story_minutes")
        if story_minutes is None:
            # Try to read from slider controller if available
            slider = getattr(current_app, "slider_controller", None)
            if slider:
                story_minutes = slider.get_minutes()
            else:
                story_minutes = state.story_length_minutes

        # Ensure valid range
        story_minutes = max(1, min(15, int(story_minutes)))

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
            # Get story elements from selected cards if available
            story_elements = state.get_story_elements() if state.selected_cards else None

            # Generate story with audio
            result = run_async(
                story_generator.generate_story_with_audio(
                    animals, tts_engine, story_minutes, story_elements
                )
            )

            # Update audio paths to API URLs
            for segment in result.get("audio_segments", []):
                audio_path = segment.get("audio", "")
                if audio_path:
                    filename = Path(audio_path).name
                    segment["audio"] = f"/api/audio/{filename}"

            # Add story_minutes to response
            result["story_minutes"] = story_minutes

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
        # Get cache directory and ensure it's an absolute path
        cache_dir = current_app.config.get("AUDIO_CACHE_DIR", "./audio_cache")
        if isinstance(cache_dir, Path):
            cache_dir = cache_dir.resolve()
        else:
            cache_dir = Path(cache_dir).resolve()

        audio_path = cache_dir / filename
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return jsonify({"error": "Audio file not found"}), 404

        return send_from_directory(
            str(cache_dir),
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
    Register a new RFID card.

    Request JSON:
    {
        "card_type": "character" | "environment" | "moral_lesson",
        "species": "dog" | "forest" | "friendship" | etc.,
        "name": "Buddy" (optional, not required for moral_lesson),
        "role": "main" | "secondary" | "felon" | "evil" (optional, only for character),
        "uid": "card uid" (optional, will be auto-generated if not provided)
    }

    Legacy format (for backwards compatibility):
    {
        "uid": "card uid",
        "animal": "animal name"
    }

    Response JSON:
    {
        "status": "saved",
        "uid": "...",
        "card_type": "...",
        "species": "...",
        "name": "..."
    }
    """
    try:
        data = request.get_json() or {}
        uid = data.get("uid")

        state = current_app.state

        # Auto-generate UID if not provided
        if not uid:
            import hashlib
            import time
            # Generate a unique UID based on timestamp and card data
            timestamp = str(time.time())
            card_type_str = data.get("card_type", "card")
            species = data.get("species", "unknown")
            uid_source = f"{timestamp}_{card_type_str}_{species}"
            uid = hashlib.md5(uid_source.encode()).hexdigest()[:8]
            logger.info(f"Auto-generated UID: {uid}")

        # Handle legacy format (just animal)
        if "animal" in data and "card_type" not in data:
            animal = data.get("animal")
            if not animal:
                return jsonify({
                    "status": "error",
                    "error": "animal is required",
                }), 400
            state.register_card_legacy(uid, animal)
            return jsonify({
                "status": "saved",
                "uid": uid,
                "animal": animal,
            })

        # New format
        card_type_str = data.get("card_type")
        species = data.get("species")
        name = data.get("name")
        role_str = data.get("role")

        if not card_type_str or not species:
            return jsonify({
                "status": "error",
                "error": "card_type and species are required",
            }), 400

        try:
            card_type = CardType(card_type_str)
        except ValueError:
            return jsonify({
                "status": "error",
                "error": f"Invalid card_type: {card_type_str}. Must be 'character', 'environment', or 'moral_lesson'",
            }), 400

        # Validate name requirement
        if card_type in (CardType.CHARACTER, CardType.ENVIRONMENT) and not name:
            name = species  # Use species as default name

        # Parse role if provided
        role = None
        if role_str and card_type == CardType.CHARACTER:
            try:
                role = CharacterRole(role_str)
            except ValueError:
                return jsonify({
                    "status": "error",
                    "error": f"Invalid role: {role_str}. Must be 'main', 'secondary', 'felon', or 'evil'",
                }), 400

        card = state.register_card(
            uid=uid,
            card_type=card_type,
            species=species,
            name=name,
            role=role,
        )

        return jsonify({
            "status": "saved",
            "uid": uid,
            "card_type": card.card_type.value,
            "species": card.species,
            "name": card.name,
            "role": card.role.value if card.role else None,
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


# Species management endpoints

@api_bp.route("/species", methods=["GET"])
def get_all_species():
    """
    Get all species for all card types.

    Response JSON:
    {
        "character": ["dog", "cat", ...],
        "environment": ["forest", "castle", ...],
        "moral_lesson": ["friendship", "courage", ...]
    }
    """
    try:
        state = current_app.state
        return jsonify({
            "character": state.get_species_for_type(CardType.CHARACTER),
            "environment": state.get_species_for_type(CardType.ENVIRONMENT),
            "moral_lesson": state.get_species_for_type(CardType.MORAL_LESSON),
        })
    except Exception as e:
        logger.error(f"API error in get_all_species: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/species/<card_type>", methods=["GET"])
def get_species_by_type(card_type):
    """
    Get species for a specific card type.

    Response JSON:
    {
        "species": ["dog", "cat", ...],
        "card_type": "character"
    }
    """
    try:
        try:
            ct = CardType(card_type)
        except ValueError:
            return jsonify({
                "error": f"Invalid card_type: {card_type}"
            }), 400

        state = current_app.state
        return jsonify({
            "species": state.get_species_for_type(ct),
            "card_type": card_type,
        })
    except Exception as e:
        logger.error(f"API error in get_species_by_type: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/species/<card_type>", methods=["POST"])
def add_species(card_type):
    """
    Add a custom species to a card type.

    Request JSON:
    {
        "species": "unicorn"
    }

    Response JSON:
    {
        "status": "added" | "exists",
        "species": "unicorn",
        "card_type": "character"
    }
    """
    try:
        try:
            ct = CardType(card_type)
        except ValueError:
            return jsonify({
                "error": f"Invalid card_type: {card_type}"
            }), 400

        data = request.get_json() or {}
        species = data.get("species", "").strip().lower()

        if not species:
            return jsonify({
                "status": "error",
                "error": "species is required"
            }), 400

        state = current_app.state
        if state.add_species(ct, species):
            return jsonify({
                "status": "added",
                "species": species,
                "card_type": card_type,
            })
        else:
            return jsonify({
                "status": "exists",
                "species": species,
                "card_type": card_type,
            })
    except Exception as e:
        logger.error(f"API error in add_species: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/species/<card_type>/<species>", methods=["DELETE"])
def remove_species(card_type, species):
    """
    Remove a custom species (cannot remove defaults).

    Response JSON:
    {
        "status": "deleted" | "not_found" | "is_default"
    }
    """
    try:
        try:
            ct = CardType(card_type)
        except ValueError:
            return jsonify({
                "error": f"Invalid card_type: {card_type}"
            }), 400

        state = current_app.state

        # Check if it's a default species
        from ..state import DEFAULT_SPECIES
        if species.lower() in [s.lower() for s in DEFAULT_SPECIES.get(ct, [])]:
            return jsonify({
                "status": "is_default",
                "error": "Cannot delete default species"
            }), 400

        if state.remove_species(ct, species):
            return jsonify({"status": "deleted", "species": species})
        else:
            return jsonify({"status": "not_found", "species": species}), 404
    except Exception as e:
        logger.error(f"API error in remove_species: {e}")
        return jsonify({"error": str(e)}), 500


# Selected cards management endpoints

@api_bp.route("/cards/selected", methods=["GET"])
def get_selected_cards():
    """
    Get currently selected cards for story generation.

    Response JSON:
    {
        "cards": [...],
        "has_character": true,
        "story_elements": {...}
    }
    """
    try:
        state = current_app.state
        return jsonify({
            "cards": [sc.to_dict() for sc in state.selected_cards],
            "has_character": state.has_character_card(),
            "story_elements": state.get_story_elements() if state.selected_cards else None,
        })
    except Exception as e:
        logger.error(f"API error in get_selected_cards: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/cards/selected/<uid>", methods=["DELETE"])
def remove_selected_card(uid):
    """Remove a card from the selection."""
    try:
        state = current_app.state
        state.remove_selected_card(uid)
        return jsonify({
            "status": "removed",
            "uid": uid,
            "cards": [sc.to_dict() for sc in state.selected_cards],
        })
    except Exception as e:
        logger.error(f"API error in remove_selected_card: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/cards/selected/clear", methods=["POST"])
def clear_selected_cards():
    """Clear all selected cards."""
    try:
        state = current_app.state
        state.clear_selected_cards()
        return jsonify({"status": "cleared", "cards": []})
    except Exception as e:
        logger.error(f"API error in clear_selected_cards: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/cards/selected/<uid>/role", methods=["POST"])
def update_card_role(uid):
    """
    Update the role of a selected character card.

    Request JSON:
    {
        "role": "main" | "secondary" | "felon" | "evil"
    }
    """
    try:
        data = request.get_json() or {}
        role_str = data.get("role")

        if not role_str:
            return jsonify({
                "status": "error",
                "error": "role is required"
            }), 400

        try:
            role = CharacterRole(role_str)
        except ValueError:
            return jsonify({
                "status": "error",
                "error": f"Invalid role: {role_str}"
            }), 400

        state = current_app.state
        if state.update_card_role(uid, role):
            return jsonify({
                "status": "updated",
                "uid": uid,
                "role": role.value,
            })
        else:
            return jsonify({
                "status": "not_found",
                "error": "Card not found in selection or not a character"
            }), 404
    except Exception as e:
        logger.error(f"API error in update_card_role: {e}")
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


# Hardware simulation endpoints (for development)

@api_bp.route("/hardware/leds", methods=["GET"])
def get_led_state():
    """
    Get current LED ring state (for development/mock mode).

    Response JSON:
    {
        "led_count": 12,
        "pixels": [[255, 0, 0], [0, 255, 0], ...],
        "current_color": [255, 0, 0],
        "mock": true
    }
    """
    try:
        led_controller = current_app.led_controller

        # Check if it's a mock controller
        from ..hardware.led_controller import MockLEDController
        is_mock = isinstance(led_controller, MockLEDController)

        if not is_mock:
            return jsonify({
                "error": "LED state only available in mock mode",
                "mock": False
            }), 400

        # Get pixel data from mock controller
        pixels = [list(led_controller.get_pixel(i)) for i in range(led_controller.led_count)]

        return jsonify({
            "led_count": led_controller.led_count,
            "pixels": pixels,
            "current_color": list(led_controller.get_current_color()),
            "mock": True
        })
    except Exception as e:
        logger.error(f"API error in get_led_state: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/hardware/rfid/inject", methods=["POST"])
def inject_rfid_card():
    """
    Inject an RFID card (for development/mock mode).

    Request JSON:
    {
        "animal": "cat"  # Legacy: Animal name
    }
    OR
    {
        "uid": "card_uid"  # Inject specific registered card
    }

    Response JSON:
    {
        "status": "injected",
        "animal": "cat",
        "uid": "12345",
        "card_type": "character"
    }
    """
    try:
        data = request.get_json() or {}
        animal = data.get("animal")
        uid = data.get("uid")

        rfid_handler = current_app.rfid_handler
        state = current_app.state
        led_animator = current_app.led_animator

        # Check if it's a mock handler
        from ..hardware.rfid_handler import MockRFIDHandler
        is_mock = isinstance(rfid_handler, MockRFIDHandler)

        if not is_mock:
            return jsonify({
                "error": "RFID injection only available in mock mode",
                "mock": False
            }), 400

        # If UID provided, look up that card
        if uid:
            card = state.get_card(uid)
            if not card:
                return jsonify({"error": f"Card {uid} not found"}), 404
            animal = card.name or card.species
        elif animal:
            # Find a registered card for this animal/species
            uid = None
            for card_uid, card_data in state.cards_db.items():
                # Check both legacy and new format
                card_animal = card_data.get("animal") or card_data.get("name") or card_data.get("species")
                if card_animal == animal:
                    uid = card_uid
                    break

            # If no card found, create a temporary character card
            if not uid:
                import hashlib
                uid = hashlib.md5(animal.encode()).hexdigest()[:8]
                state.register_card(
                    uid=uid,
                    card_type=CardType.CHARACTER,
                    species=animal,
                    name=animal,
                    role=CharacterRole.MAIN,
                )
                logger.info(f"Auto-registered card {uid} for animal: {animal}")
        else:
            return jsonify({"error": "Either 'animal' or 'uid' required"}), 400

        # Get the card to determine type
        card = state.get_card(uid)
        card_type = card.card_type if card else CardType.CHARACTER

        # Inject the card
        rfid_handler.inject_card(uid, animal)
        logger.info(f"Injected RFID card: {uid} -> {animal} ({card_type.value})")

        # Animate LED with card type color
        if led_animator:
            led_animator.animate_card_detected(card_type.value, duration=1.0)

        # Add to selected cards
        if card:
            state.add_selected_card(card)

        return jsonify({
            "status": "injected",
            "animal": animal,
            "uid": uid,
            "card_type": card_type.value,
        })
    except Exception as e:
        logger.error(f"API error in inject_rfid_card: {e}")
        return jsonify({"error": str(e)}), 500


# Slider endpoints

@api_bp.route("/hardware/slider", methods=["GET"])
def get_slider_state():
    """
    Get current slider state.

    Response JSON:
    {
        "value": 0.33,      # Normalized value (0.0-1.0)
        "minutes": 5,       # Story duration in minutes (1-15)
        "mock": true        # Whether using mock controller
    }
    """
    try:
        slider = getattr(current_app, "slider_controller", None)
        if not slider:
            return jsonify({
                "error": "Slider controller not initialized",
                "mock": False
            }), 400

        from ..hardware.length_slider import MockSliderController
        is_mock = isinstance(slider, MockSliderController)

        return jsonify({
            "value": slider.read_value(),
            "minutes": slider.get_minutes(),
            "mock": is_mock
        })
    except Exception as e:
        logger.error(f"API error in get_slider_state: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/hardware/slider/set", methods=["POST"])
def set_slider_value():
    """
    Set slider value (mock mode only).

    Request JSON:
    {
        "minutes": 10       # Story duration in minutes (1-15)
    }
    OR
    {
        "value": 0.5        # Normalized value (0.0-1.0)
    }

    Response JSON:
    {
        "status": "set",
        "value": 0.64,
        "minutes": 10,
        "mock": true
    }
    """
    try:
        data = request.get_json() or {}
        slider = getattr(current_app, "slider_controller", None)
        state = current_app.state

        if not slider:
            return jsonify({
                "error": "Slider controller not initialized",
                "mock": False
            }), 400

        from ..hardware.length_slider import MockSliderController
        is_mock = isinstance(slider, MockSliderController)

        if not is_mock:
            return jsonify({
                "error": "Slider value can only be set in mock mode",
                "mock": False
            }), 400

        # Set value based on minutes or raw value
        minutes = data.get("minutes")
        value = data.get("value")

        if minutes is not None:
            minutes = max(1, min(15, int(minutes)))
            slider.set_minutes(minutes)
        elif value is not None:
            value = max(0.0, min(1.0, float(value)))
            slider.set_value(value)
        else:
            return jsonify({
                "error": "Either 'minutes' or 'value' must be provided"
            }), 400

        # Update state as well
        current_minutes = slider.get_minutes()
        state.set_story_length(current_minutes)

        return jsonify({
            "status": "set",
            "value": slider.read_value(),
            "minutes": current_minutes,
            "mock": True
        })
    except Exception as e:
        logger.error(f"API error in set_slider_value: {e}")
        return jsonify({"error": str(e)}), 500
