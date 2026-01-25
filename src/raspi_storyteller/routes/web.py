"""
Web routes for HTML page rendering.

Provides template-based web interface for the Storyteller application.
"""

from flask import Blueprint, render_template, current_app

from ..utils.logger import get_logger
from ..i18n import get_translations

logger = get_logger(__name__)

web_bp = Blueprint(
    "web",
    __name__,
    template_folder="../../templates",
    static_folder="../../static",
)


def _get_template_context():
    """Get common template context with translations."""
    lang_code = current_app.config.get("SPEECH_LANGUAGE", "en")
    return {
        "t": get_translations(lang_code),
        "lang": lang_code.split("-")[0]
    }


@web_bp.route("/")
def index():
    """Render the main storyteller interface."""
    return render_template("index.html", **_get_template_context())


@web_bp.route("/manage")
def manage():
    """Render the RFID card management page."""
    return render_template("manage.html", **_get_template_context())


@web_bp.route("/voice_test")
def voice_test():
    """Render the voice recognition test page."""
    return render_template("voice_test.html", **_get_template_context())


@web_bp.route("/status")
def status_page():
    """Render the system status page."""
    return render_template("status.html", **_get_template_context())
