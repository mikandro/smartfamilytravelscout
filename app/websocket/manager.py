"""
WebSocket connection manager for real-time updates.

This module manages WebSocket connections and handles broadcasting of
scraping progress updates to connected clients.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from app.config import settings
from app.websocket.events import ScrapingEvent

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections and event broadcasting.

    This class handles:
    - WebSocket connection lifecycle (connect, disconnect)
    - Per-job connection tracking (multiple clients can watch same job)
    - Event broadcasting via Redis pub/sub (supports multiple workers)
    - Graceful error handling and connection cleanup

    Usage:
        manager = WebSocketManager()
        await manager.connect(websocket, job_id)
        await manager.broadcast_event(event)
        await manager.disconnect(websocket, job_id)
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        # Map job_id -> set of connected WebSockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self.listener_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def initialize_redis(self):
        """
        Initialize Redis connection for pub/sub.

        This allows multiple workers to coordinate WebSocket broadcasts.
        """
        if self.redis_client:
            return  # Already initialized

        try:
            self.redis_client = await aioredis.from_url(
                str(settings.redis_url),
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("WebSocket manager: Redis connection established")

            # Subscribe to scraping events channel
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("scraping_events")

            # Start listener task
            self.listener_task = asyncio.create_task(self._listen_to_redis())
            logger.info("WebSocket manager: Started Redis listener")

        except Exception as e:
            logger.error(f"Failed to initialize Redis for WebSocket manager: {e}")
            self.redis_client = None
            self.pubsub = None

    async def _listen_to_redis(self):
        """
        Listen to Redis pub/sub and broadcast to WebSocket clients.

        This runs as a background task and forwards Redis messages to connected WebSockets.
        """
        if not self.pubsub:
            return

        logger.info("Redis listener started")

        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Parse event from Redis
                        event_data = json.loads(message["data"])
                        job_id = event_data.get("job_id")

                        if job_id and job_id in self.active_connections:
                            # Broadcast to all clients watching this job
                            await self._broadcast_to_clients(job_id, event_data)

                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in Redis message: {message['data']}")
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
        except Exception as e:
            logger.error(f"Redis listener error: {e}", exc_info=True)

    async def _broadcast_to_clients(self, job_id: int, event_data: dict):
        """
        Broadcast event data to all WebSocket clients watching a job.

        Args:
            job_id: Job ID to broadcast to
            event_data: Event data dictionary
        """
        async with self._lock:
            connections = self.active_connections.get(job_id, set())
            disconnected = set()

            for websocket in connections:
                try:
                    await websocket.send_json(event_data)
                except WebSocketDisconnect:
                    disconnected.add(websocket)
                except Exception as e:
                    logger.error(f"Error sending to WebSocket: {e}")
                    disconnected.add(websocket)

            # Clean up disconnected clients
            if disconnected:
                self.active_connections[job_id] -= disconnected
                if not self.active_connections[job_id]:
                    del self.active_connections[job_id]

    async def connect(self, websocket: WebSocket, job_id: int):
        """
        Accept a new WebSocket connection and track it.

        Args:
            websocket: WebSocket connection to accept
            job_id: Scraping job ID the client wants to watch
        """
        await websocket.accept()

        async with self._lock:
            if job_id not in self.active_connections:
                self.active_connections[job_id] = set()
            self.active_connections[job_id].add(websocket)

        logger.info(
            f"WebSocket connected for job {job_id} "
            f"(total connections: {len(self.active_connections[job_id])})"
        )

    async def disconnect(self, websocket: WebSocket, job_id: int):
        """
        Remove a WebSocket connection from tracking.

        Args:
            websocket: WebSocket connection to remove
            job_id: Scraping job ID the client was watching
        """
        async with self._lock:
            if job_id in self.active_connections:
                self.active_connections[job_id].discard(websocket)
                if not self.active_connections[job_id]:
                    del self.active_connections[job_id]

        logger.info(f"WebSocket disconnected for job {job_id}")

    async def broadcast_event(self, event: ScrapingEvent):
        """
        Broadcast a scraping event to all connected clients via Redis.

        This publishes the event to Redis, which will then be picked up by
        the listener and broadcast to WebSocket clients.

        Args:
            event: Scraping event to broadcast
        """
        if not self.redis_client:
            await self.initialize_redis()

        if not self.redis_client:
            logger.warning("Cannot broadcast event: Redis not available")
            return

        try:
            # Publish to Redis pub/sub channel
            event_json = json.dumps(event.to_dict())
            await self.redis_client.publish("scraping_events", event_json)
            logger.debug(f"Broadcast event for job {event.job_id}: {event.event_type}")

        except Exception as e:
            logger.error(f"Error broadcasting event: {e}", exc_info=True)

    async def send_direct(self, job_id: int, event: ScrapingEvent):
        """
        Send event directly to connected clients without Redis.

        Use this for immediate delivery when Redis might not be available.

        Args:
            job_id: Job ID to send to
            event: Event to send
        """
        await self._broadcast_to_clients(job_id, event.to_dict())

    async def shutdown(self):
        """Clean up resources on shutdown."""
        # Cancel listener task
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass

        # Close Redis connections
        if self.pubsub:
            await self.pubsub.unsubscribe("scraping_events")
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

        # Close all WebSocket connections
        async with self._lock:
            for connections in self.active_connections.values():
                for websocket in connections:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
            self.active_connections.clear()

        logger.info("WebSocket manager shutdown complete")

    def get_connection_count(self, job_id: Optional[int] = None) -> int:
        """
        Get the number of active connections.

        Args:
            job_id: If provided, count connections for this job only.
                   If None, count all connections.

        Returns:
            Number of active WebSocket connections
        """
        if job_id:
            return len(self.active_connections.get(job_id, set()))
        else:
            return sum(len(conns) for conns in self.active_connections.values())


# Global instance
websocket_manager = WebSocketManager()
