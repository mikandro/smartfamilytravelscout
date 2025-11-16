"""
Geographical utility functions for SmartFamilyTravelScout.

Provides distance calculations, driving time estimates, and city coordinate lookups.
"""

import math
from typing import Dict, Tuple

# European city coordinates (latitude, longitude)
# Format: "City, Country": (latitude, longitude)
CITY_COORDINATES: Dict[str, Tuple[float, float]] = {
    # Germany
    "Munich, Germany": (48.1351, 11.5820),
    "Berlin, Germany": (52.5200, 13.4050),
    "Hamburg, Germany": (53.5511, 9.9937),
    "Frankfurt, Germany": (50.1109, 8.6821),
    "Cologne, Germany": (50.9375, 6.9603),
    "Stuttgart, Germany": (48.7758, 9.1829),
    "Nuremberg, Germany": (49.4521, 11.0767),
    # Austria
    "Vienna, Austria": (48.2082, 16.3738),
    "Salzburg, Austria": (47.8095, 13.0550),
    "Innsbruck, Austria": (47.2692, 11.4041),
    # Switzerland
    "Zurich, Switzerland": (47.3769, 8.5417),
    "Geneva, Switzerland": (46.2044, 6.1432),
    "Bern, Switzerland": (46.9480, 7.4474),
    # Italy
    "Rome, Italy": (41.9028, 12.4964),
    "Milan, Italy": (45.4642, 9.1900),
    "Venice, Italy": (45.4408, 12.3155),
    "Florence, Italy": (43.7696, 11.2558),
    "Naples, Italy": (40.8518, 14.2681),
    "Verona, Italy": (45.4384, 10.9916),
    # France
    "Paris, France": (48.8566, 2.3522),
    "Lyon, France": (45.7640, 4.8357),
    "Marseille, France": (43.2965, 5.3698),
    "Nice, France": (43.7102, 7.2620),
    "Strasbourg, France": (48.5734, 7.7521),
    # Spain
    "Barcelona, Spain": (41.3874, 2.1686),
    "Madrid, Spain": (40.4168, -3.7038),
    "Valencia, Spain": (39.4699, -0.3763),
    "Seville, Spain": (37.3891, -5.9845),
    "Mallorca, Spain": (39.6953, 3.0176),
    # Portugal
    "Lisbon, Portugal": (38.7223, -9.1393),
    "Porto, Portugal": (41.1579, -8.6291),
    # Netherlands
    "Amsterdam, Netherlands": (52.3676, 4.9041),
    "Rotterdam, Netherlands": (51.9225, 4.47917),
    # Belgium
    "Brussels, Belgium": (50.8503, 4.3517),
    "Bruges, Belgium": (51.2093, 3.2247),
    # Czech Republic
    "Prague, Czech Republic": (50.0755, 14.4378),
    # Poland
    "Krakow, Poland": (50.0647, 19.9450),
    "Warsaw, Poland": (52.2297, 21.0122),
    # Hungary
    "Budapest, Hungary": (47.4979, 19.0402),
    # Croatia
    "Zagreb, Croatia": (45.8150, 15.9819),
    "Split, Croatia": (43.5081, 16.4402),
    "Dubrovnik, Croatia": (42.6507, 18.0944),
    # Greece
    "Athens, Greece": (37.9838, 23.7275),
    # Denmark
    "Copenhagen, Denmark": (55.6761, 12.5683),
    # Sweden
    "Stockholm, Sweden": (59.3293, 18.0686),
    # Norway
    "Oslo, Norway": (59.9139, 10.7522),
}


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance in kilometers using the Haversine formula.

    The Haversine formula determines the great-circle distance between two points
    on a sphere given their longitudes and latitudes.

    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees

    Returns:
        Distance in kilometers (rounded to 1 decimal place)

    Examples:
        >>> # Munich to Vienna (approx 354 km)
        >>> distance = calculate_distance(48.1351, 11.5820, 48.2082, 16.3738)
        >>> 350 < distance < 360
        True
        >>> # Munich to Berlin (approx 504 km)
        >>> distance = calculate_distance(48.1351, 11.5820, 52.5200, 13.4050)
        >>> 500 < distance < 510
        True
    """
    if None in [lat1, lon1, lat2, lon2]:
        return 0.0

    # Earth's radius in kilometers
    R = 6371.0

    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    distance = R * c
    return round(distance, 1)


def estimate_driving_time(distance_km: float, avg_speed_kmh: float = 100.0) -> int:
    """
    Estimate driving time in minutes based on distance.

    Assumes an average speed of 100 km/h by default (highway driving).
    For city driving or mountain roads, use a lower avg_speed_kmh.

    Args:
        distance_km: Distance in kilometers
        avg_speed_kmh: Average driving speed in km/h (default: 100)

    Returns:
        Estimated driving time in minutes (rounded up)

    Examples:
        >>> estimate_driving_time(100)  # 100km at 100km/h
        60
        >>> estimate_driving_time(350)  # Munich to Vienna
        210
        >>> estimate_driving_time(100, avg_speed_kmh=80)  # Slower speed
        75
    """
    if distance_km is None or distance_km <= 0:
        return 0

    if avg_speed_kmh is None or avg_speed_kmh <= 0:
        avg_speed_kmh = 100.0

    hours = distance_km / avg_speed_kmh
    minutes = hours * 60
    return math.ceil(minutes)


def get_city_coordinates(city_name: str) -> Tuple[float, float] | None:
    """
    Get latitude and longitude coordinates for a city.

    Uses a hardcoded dictionary of major European cities.

    Args:
        city_name: City name (can include country, e.g., "Munich, Germany" or just "Munich")

    Returns:
        Tuple of (latitude, longitude) or None if city not found

    Examples:
        >>> coords = get_city_coordinates("Munich, Germany")
        >>> coords
        (48.1351, 11.582)
        >>> coords = get_city_coordinates("munich")
        >>> coords
        (48.1351, 11.582)
        >>> get_city_coordinates("Unknown City") is None
        True
    """
    if not city_name or not isinstance(city_name, str):
        return None

    city_name = city_name.strip()

    # Try exact match first
    if city_name in CITY_COORDINATES:
        return CITY_COORDINATES[city_name]

    # Try case-insensitive match
    city_lower = city_name.lower()
    for key, coords in CITY_COORDINATES.items():
        if key.lower() == city_lower:
            return coords

    # Try partial match (e.g., "Munich" matches "Munich, Germany")
    for key, coords in CITY_COORDINATES.items():
        if city_lower in key.lower() or key.lower().startswith(city_lower):
            return coords

    return None


def calculate_city_distance(city1: str, city2: str) -> float | None:
    """
    Calculate distance between two cities by name.

    Args:
        city1: Name of first city
        city2: Name of second city

    Returns:
        Distance in kilometers or None if either city is not found

    Examples:
        >>> distance = calculate_city_distance("Munich", "Vienna")
        >>> distance is not None and 350 < distance < 360
        True
        >>> calculate_city_distance("Unknown", "Munich") is None
        True
    """
    coords1 = get_city_coordinates(city1)
    coords2 = get_city_coordinates(city2)

    if coords1 is None or coords2 is None:
        return None

    lat1, lon1 = coords1
    lat2, lon2 = coords2

    return calculate_distance(lat1, lon1, lat2, lon2)


def estimate_city_driving_time(city1: str, city2: str, avg_speed_kmh: float = 100.0) -> int | None:
    """
    Estimate driving time between two cities.

    Args:
        city1: Name of first city
        city2: Name of second city
        avg_speed_kmh: Average driving speed in km/h (default: 100)

    Returns:
        Estimated driving time in minutes or None if either city is not found

    Examples:
        >>> time = estimate_city_driving_time("Munich", "Vienna")
        >>> time is not None and 200 < time < 220
        True
        >>> estimate_city_driving_time("Unknown", "Munich") is None
        True
    """
    distance = calculate_city_distance(city1, city2)

    if distance is None:
        return None

    return estimate_driving_time(distance, avg_speed_kmh)


def is_within_radius(
    center_lat: float, center_lon: float, check_lat: float, check_lon: float, radius_km: float
) -> bool:
    """
    Check if a location is within a given radius of a center point.

    Args:
        center_lat: Latitude of center point
        center_lon: Longitude of center point
        check_lat: Latitude of point to check
        check_lon: Longitude of point to check
        radius_km: Radius in kilometers

    Returns:
        True if the point is within the radius, False otherwise

    Examples:
        >>> # Check if Vienna is within 400km of Munich
        >>> is_within_radius(48.1351, 11.5820, 48.2082, 16.3738, 400)
        True
        >>> # Check if Berlin is within 400km of Munich
        >>> is_within_radius(48.1351, 11.5820, 52.5200, 13.4050, 400)
        False
    """
    if None in [center_lat, center_lon, check_lat, check_lon, radius_km]:
        return False

    if radius_km <= 0:
        return False

    distance = calculate_distance(center_lat, center_lon, check_lat, check_lon)
    return distance <= radius_km


def get_all_cities() -> list[str]:
    """
    Get a list of all available city names.

    Returns:
        List of city names in the format "City, Country"

    Examples:
        >>> cities = get_all_cities()
        >>> "Munich, Germany" in cities
        True
        >>> len(cities) >= 30
        True
    """
    return sorted(CITY_COORDINATES.keys())


def get_cities_within_radius(center_city: str, radius_km: float) -> list[Tuple[str, float]]:
    """
    Get all cities within a given radius of a center city.

    Args:
        center_city: Name of the center city
        radius_km: Radius in kilometers

    Returns:
        List of tuples (city_name, distance_km) sorted by distance

    Examples:
        >>> cities = get_cities_within_radius("Munich", 200)
        >>> len(cities) > 0
        True
        >>> cities[0][0] == "Munich, Germany"  # Center city first
        True
    """
    center_coords = get_city_coordinates(center_city)
    if center_coords is None:
        return []

    center_lat, center_lon = center_coords
    cities_in_radius = []

    for city, (lat, lon) in CITY_COORDINATES.items():
        distance = calculate_distance(center_lat, center_lon, lat, lon)
        if distance <= radius_km:
            cities_in_radius.append((city, distance))

    # Sort by distance
    return sorted(cities_in_radius, key=lambda x: x[1])
