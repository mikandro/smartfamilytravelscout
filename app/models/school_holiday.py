"""
School holidays model for Bavaria school calendar.
"""

from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SchoolHoliday(Base, TimestampMixin):
    """
    Model for storing school holiday periods.
    Used to optimize trip planning around Bavaria school calendar.
    """

    __tablename__ = "school_holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Holiday details
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="e.g., 'Easter Break 2025', 'Summer Holiday 2025'"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Holiday classification
    holiday_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="'major' for long holidays, 'long_weekend' for short breaks",
    )
    region: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Bavaria", comment="School region"
    )

    def __repr__(self) -> str:
        return (
            f"<SchoolHoliday(id={self.id}, name='{self.name}', "
            f"dates={self.start_date} to {self.end_date}, type='{self.holiday_type}')>"
        )

    @property
    def duration_days(self) -> int:
        """Calculate holiday duration in days."""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_major_holiday(self) -> bool:
        """Check if this is a major holiday (> 7 days)."""
        return self.holiday_type == "major" or self.duration_days > 7

    def contains_date(self, check_date: date) -> bool:
        """Check if a given date falls within this holiday period."""
        return self.start_date <= check_date <= self.end_date
