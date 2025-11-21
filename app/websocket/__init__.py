"""WebSocket support for real-time updates."""

from app.websocket.manager import websocket_manager
from app.websocket.events import ScrapingEvent, ScrapingEventType

__all__ = ["websocket_manager", "ScrapingEvent", "ScrapingEventType"]
