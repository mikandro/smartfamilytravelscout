"""
Scraping job model for tracking web scraping tasks.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScrapingJob(Base):
    """
    Model for tracking scraping job execution and status.
    Used for monitoring and debugging scraping tasks.
    Note: Does not use TimestampMixin to use custom timestamp fields.
    """

    __tablename__ = "scraping_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Job details
    job_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="e.g., 'flights', 'accommodations', 'events'",
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="Source website or API"
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="'running', 'completed', 'failed', 'interrupted'",
    )
    items_scraped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Number of items successfully scraped"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<ScrapingJob(id={self.id}, type='{self.job_type}', "
            f"source='{self.source}', status='{self.status}', items={self.items_scraped})>"
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    @property
    def is_running(self) -> bool:
        """Check if job is currently running."""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if job completed successfully."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if job failed."""
        return self.status == "failed"

    @property
    def is_interrupted(self) -> bool:
        """Check if job was interrupted."""
        return self.status == "interrupted"
