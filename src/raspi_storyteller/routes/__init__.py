"""Flask route blueprints for API and web endpoints."""

from .api import api_bp
from .web import web_bp

__all__ = ["api_bp", "web_bp"]
