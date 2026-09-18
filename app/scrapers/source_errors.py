"""
Error modes for flight and accommodation sources.

Error modes are part of a module's interface. Before this existed, they were
unusable: ``app/exceptions.py`` declared 16 classes of which only 4 were ever
raised or caught, while the scrapers each declared their own unrelated bare
``Exception`` subclasses --

- ``RateLimitExceeded`` (ryanair), ``RateLimitExceededError`` (rate_limiter),
  ``WizzAirRateLimitError``, ``EventBriteRateLimitError`` -- four unrelated
  rate-limit types
- ``CaptchaDetected`` (ryanair) and ``CaptchaDetectedError`` (skyscanner) --
  two unrelated captcha types

No caller could write ``except ScraperException`` and mean it, so both fan-out
sites caught bare ``Exception`` -- and then disagreed about whether to re-raise.

These four modes are declared at the source seam so retry and threshold logic
can tell "rate limited, back off" from "parse broke, fix the code".
"""

from __future__ import annotations

from typing import Optional


class SourceError(Exception):
    """
    Base error mode for a flight or accommodation source.

    Attributes:
        source: Name of the source that failed ("ryanair", "booking", ...).
        retryable: Whether retrying the same request could plausibly succeed.
            Fan-out logic uses this rather than inspecting the concrete type.
    """

    retryable: bool = False

    def __init__(self, message: str, source: Optional[str] = None) -> None:
        self.source = source
        prefix = f"[{source}] " if source else ""
        super().__init__(f"{prefix}{message}")


class SourceRateLimited(SourceError):
    """
    The source refused the request because we asked too often.

    Retryable after a delay. Replaces the four separate rate-limit classes.
    """

    retryable = True

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        source: Optional[str] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, source)


class SourceBlocked(SourceError):
    """
    The source actively blocked us -- captcha, bot detection, or a ban.

    Not retryable in the same run: retrying immediately makes it worse.
    Replaces ``CaptchaDetected`` and ``CaptchaDetectedError``.
    """

    retryable = False


class SourceUnavailable(SourceError):
    """
    The source could not be reached, or returned a server error.

    Retryable: this is usually transient.
    """

    retryable = True


class SourceParseFailed(SourceError):
    """
    We reached the source but could not understand its response.

    Not retryable -- the page or payload shape changed and the adapter needs
    fixing. Distinguishing this from the retryable modes is the point: it is a
    code defect, not a transient condition.
    """

    retryable = False
