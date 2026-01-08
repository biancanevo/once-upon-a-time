"""
Web routes for HTML page rendering.

Provides template-based web interface for the Storyteller application.
"""

from flask import Blueprint, render_template

from ..utils.logger import get_logger

logger = get_logger(__name__)

web_bp = Blueprint(
    "web",
    __name__,
    template_folder="../../templates",
    static_folder="../../static",
)


@web_bp.route("/")
def index():
    """Render the main storyteller interface."""
    return render_template("index.html")


@web_bp.route("/manage")
def manage():
    """Render the RFID card management page."""
    return render_template("manage.html")


@web_bp.route("/voice_test")
def voice_test():
    """Render the voice recognition test page."""
    return render_template("voice_test.html")


@web_bp.route("/status")
def status_page():
    """Render the system status page."""
    return render_template("status.html")
