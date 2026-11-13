"""
Weekend weather from Open-Meteo (free, no API key).

The planner only needs one question answered per day: is it a day for being
outside with small children? ``DayForecast.verdict`` answers that.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

VERDICT_OUTDOOR = "outdoor"
VERDICT_MIXED = "mixed"
VERDICT_INDOOR = "indoor"

# WMO weather codes, grouped. https://open-meteo.com/en/docs#weathervariables
_WMO_DESCRIPTIONS = {
    0: "clear sky",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with hail",
}


class WeatherUnavailable(Exception):
    """The forecast could not be fetched or did not cover the requested days."""


@dataclass(frozen=True)
class DayForecast:
    """Forecast for one day, reduced to what matters for a family outing."""

    day: date
    temp_max_c: float
    temp_min_c: float
    precipitation_mm: float
    precipitation_probability: Optional[int]
    wind_max_kmh: float
    weather_code: Optional[int]

    @property
    def description(self) -> str:
        """Short human description of the weather code."""
        if self.weather_code is None:
            return "unknown"
        return _WMO_DESCRIPTIONS.get(self.weather_code, "unsettled")

    @property
    def verdict(self) -> str:
        """
        ``outdoor``, ``mixed`` or ``indoor``.

        Thresholds are tuned for a 3-year-old: a dry cold day is fine, steady
        rain, a storm or a hard frost is not.
        """
        probability = self.precipitation_probability or 0
        stormy = self.weather_code in (95, 96, 99) or self.wind_max_kmh >= 60
        if (
            stormy
            or self.precipitation_mm >= 5
            or (probability >= 70 and self.precipitation_mm >= 2)
            or self.temp_max_c <= -5
        ):
            return VERDICT_INDOOR
        if self.precipitation_mm < 1 and probability < 40:
            return VERDICT_OUTDOOR
        return VERDICT_MIXED

    @property
    def outdoor_score(self) -> float:
        """Higher is better for being outside. Used to pick the better day."""
        probability = self.precipitation_probability or 0
        # Comfort peaks around 22°C and falls off either side.
        comfort = -abs(self.temp_max_c - 22) * 1.5
        return comfort - self.precipitation_mm * 6 - probability * 0.3 - self.wind_max_kmh * 0.2

    def summary(self) -> str:
        """One line, e.g. ``Sat 14 Nov: light rain, 4–9°C, 60% rain (3.2 mm)``."""
        text = (
            f"{self.day.strftime('%a %d %b')}: {self.description}, "
            f"{self.temp_min_c:.0f}–{self.temp_max_c:.0f}°C"
        )
        if self.precipitation_probability is not None:
            text += f", {self.precipitation_probability}% rain"
        if self.precipitation_mm >= 0.1:
            text += f" ({self.precipitation_mm:.1f} mm)"
        return text

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe dict, including the derived verdict."""
        data = asdict(self)
        data["day"] = self.day.isoformat()
        data["verdict"] = self.verdict
        data["description"] = self.description
        data["summary"] = self.summary()
        return data


def parse_open_meteo(payload: Dict[str, Any], days: Sequence[date]) -> List[DayForecast]:
    """
    Turn an Open-Meteo ``daily`` response into forecasts for ``days``.

    Raises:
        WeatherUnavailable: If the payload is malformed or misses a requested day.
    """
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise WeatherUnavailable("Open-Meteo response has no daily data")

    def value(key: str, index: int) -> Any:
        series = daily.get(key) or []
        return series[index] if index < len(series) else None

    by_day: Dict[str, DayForecast] = {}
    for index, iso_day in enumerate(daily["time"]):
        temp_max = value("temperature_2m_max", index)
        temp_min = value("temperature_2m_min", index)
        if temp_max is None or temp_min is None:
            continue
        probability = value("precipitation_probability_max", index)
        code = value("weather_code", index)
        by_day[iso_day] = DayForecast(
            day=date.fromisoformat(iso_day),
            temp_max_c=float(temp_max),
            temp_min_c=float(temp_min),
            precipitation_mm=float(value("precipitation_sum", index) or 0.0),
            precipitation_probability=int(probability) if probability is not None else None,
            wind_max_kmh=float(value("wind_speed_10m_max", index) or 0.0),
            weather_code=int(code) if code is not None else None,
        )

    missing = [day.isoformat() for day in days if day.isoformat() not in by_day]
    if missing:
        raise WeatherUnavailable(f"No forecast for {', '.join(missing)}")
    return [by_day[day.isoformat()] for day in days]


async def fetch_forecast(
    latitude: float,
    longitude: float,
    days: Sequence[date],
    *,
    client: Optional[httpx.AsyncClient] = None,
    timeout: float = 15.0,
) -> List[DayForecast]:
    """
    Fetch the daily forecast for the given days.

    Args:
        latitude: Home latitude.
        longitude: Home longitude.
        days: Days to fetch (must be within Open-Meteo's 16-day horizon).
        client: Optional HTTP client (mainly for tests).
        timeout: Request timeout in seconds.

    Raises:
        WeatherUnavailable: On any network, HTTP or parsing problem.
    """
    if not days:
        return []

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
            ]
        ),
        "timezone": "Europe/Berlin",
        "start_date": min(days).isoformat(),
        "end_date": max(days).isoformat(),
    }

    try:
        if client is not None:
            response = await client.get(OPEN_METEO_URL, params=params, timeout=timeout)
        else:
            async with httpx.AsyncClient() as own_client:
                response = await own_client.get(OPEN_METEO_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherUnavailable(f"Open-Meteo request failed: {exc}") from exc

    return parse_open_meteo(payload, days)
