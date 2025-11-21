"""
WebSocket event definitions for real-time updates.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ScrapingEventType(str, Enum):
    """Types of scraping events that can be broadcast."""

    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    SCRAPER_STARTED = "scraper_started"
    SCRAPER_COMPLETED = "scraper_completed"
    SCRAPER_FAILED = "scraper_failed"
    RESULTS_UPDATED = "results_updated"


class ScrapingEvent(BaseModel):
    """
    Event model for scraping updates.

    This model represents a real-time update about a scraping job's progress.
    It's broadcast via WebSocket to connected clients.
    """

    job_id: int = Field(..., description="ID of the scraping job")
    event_type: ScrapingEventType = Field(..., description="Type of event")
    status: str = Field(..., description="Current job status: running, completed, failed")
    progress: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Progress percentage (0-100)"
    )
    results_count: int = Field(0, description="Number of items scraped so far")
    message: Optional[str] = Field(None, description="Human-readable message")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional event-specific data"
    )
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        use_enum_values = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "event_type": self.event_type,
            "status": self.status,
            "progress": self.progress,
            "results_count": self.results_count,
            "message": self.message,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
