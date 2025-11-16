"""
Unit tests for geo_utils module.
"""

import pytest

from app.utils.geo_utils import (
    CITY_COORDINATES,
    calculate_distance,
    estimate_driving_time,
    get_city_coordinates,
    calculate_city_distance,
    estimate_city_driving_time,
    is_within_radius,
    get_all_cities,
    get_cities_within_radius,
)


class TestCalculateDistance:
    """Tests for calculate_distance function."""

    def test_calculate_distance_munich_vienna(self):
        """Test distance between Munich and Vienna (approx 354 km)."""
        distance = calculate_distance(48.1351, 11.5820, 48.2082, 16.3738)
        assert 350 < distance < 360

    def test_calculate_distance_munich_berlin(self):
        """Test distance between Munich and Berlin (approx 504 km)."""
        distance = calculate_distance(48.1351, 11.5820, 52.5200, 13.4050)
        assert 500 < distance < 510

    def test_calculate_distance_same_location(self):
        """Test distance between same location (should be 0)."""
        distance = calculate_distance(48.1351, 11.5820, 48.1351, 11.5820)
        assert distance == 0.0

    def test_calculate_distance_none_values(self):
        """Test with None values."""
        assert calculate_distance(None, 11.5820, 48.2082, 16.3738) == 0.0
        assert calculate_distance(48.1351, None, 48.2082, 16.3738) == 0.0
        assert calculate_distance(48.1351, 11.5820, None, 16.3738) == 0.0
        assert calculate_distance(48.1351, 11.5820, 48.2082, None) == 0.0

    def test_calculate_distance_precision(self):
        """Test that distance is rounded to 1 decimal place."""
        distance = calculate_distance(48.1351, 11.5820, 48.2082, 16.3738)
        # Check that result has at most 1 decimal place
        assert distance == round(distance, 1)


class TestEstimateDrivingTime:
    """Tests for estimate_driving_time function."""

    def test_estimate_driving_time_100km(self):
        """Test driving time for 100 km at default speed."""
        time = estimate_driving_time(100)
        assert time == 60  # 1 hour

    def test_estimate_driving_time_350km(self):
        """Test driving time for Munich to Vienna distance."""
        time = estimate_driving_time(350)
        assert time == 210  # 3.5 hours

    def test_estimate_driving_time_custom_speed(self):
        """Test driving time with custom speed."""
        time = estimate_driving_time(100, avg_speed_kmh=80)
        assert time == 75  # 1.25 hours

    def test_estimate_driving_time_zero_distance(self):
        """Test with zero distance."""
        assert estimate_driving_time(0) == 0

    def test_estimate_driving_time_negative_distance(self):
        """Test with negative distance."""
        assert estimate_driving_time(-100) == 0

    def test_estimate_driving_time_none_distance(self):
        """Test with None distance."""
        assert estimate_driving_time(None) == 0

    def test_estimate_driving_time_none_speed(self):
        """Test with None speed (should use default)."""
        time = estimate_driving_time(100, avg_speed_kmh=None)
        assert time == 60


class TestGetCityCoordinates:
    """Tests for get_city_coordinates function."""

    def test_get_city_coordinates_exact_match(self):
        """Test getting coordinates with exact match."""
        coords = get_city_coordinates("Munich, Germany")
        assert coords == (48.1351, 11.5820)

    def test_get_city_coordinates_case_insensitive(self):
        """Test getting coordinates with different case."""
        coords = get_city_coordinates("munich, germany")
        assert coords == (48.1351, 11.5820)

    def test_get_city_coordinates_partial_match(self):
        """Test getting coordinates with partial match."""
        coords = get_city_coordinates("Munich")
        assert coords == (48.1351, 11.5820)

    def test_get_city_coordinates_vienna(self):
        """Test getting coordinates for Vienna."""
        coords = get_city_coordinates("Vienna")
        assert coords == (48.2082, 16.3738)

    def test_get_city_coordinates_not_found(self):
        """Test with unknown city."""
        assert get_city_coordinates("Unknown City") is None

    def test_get_city_coordinates_none(self):
        """Test with None."""
        assert get_city_coordinates(None) is None

    def test_get_city_coordinates_empty_string(self):
        """Test with empty string."""
        assert get_city_coordinates("") is None


class TestCalculateCityDistance:
    """Tests for calculate_city_distance function."""

    def test_calculate_city_distance_munich_vienna(self):
        """Test distance between Munich and Vienna."""
        distance = calculate_city_distance("Munich", "Vienna")
        assert distance is not None
        assert 350 < distance < 360

    def test_calculate_city_distance_munich_berlin(self):
        """Test distance between Munich and Berlin."""
        distance = calculate_city_distance("Munich", "Berlin")
        assert distance is not None
        assert 500 < distance < 510

    def test_calculate_city_distance_same_city(self):
        """Test distance between same city."""
        distance = calculate_city_distance("Munich", "Munich")
        assert distance == 0.0

    def test_calculate_city_distance_unknown_city(self):
        """Test with unknown city."""
        assert calculate_city_distance("Unknown", "Munich") is None
        assert calculate_city_distance("Munich", "Unknown") is None


class TestEstimateCityDrivingTime:
    """Tests for estimate_city_driving_time function."""

    def test_estimate_city_driving_time_munich_vienna(self):
        """Test driving time between Munich and Vienna."""
        time = estimate_city_driving_time("Munich", "Vienna")
        assert time is not None
        assert 200 < time < 220

    def test_estimate_city_driving_time_custom_speed(self):
        """Test driving time with custom speed."""
        time = estimate_city_driving_time("Munich", "Vienna", avg_speed_kmh=80)
        assert time is not None
        assert 250 < time < 280

    def test_estimate_city_driving_time_unknown_city(self):
        """Test with unknown city."""
        assert estimate_city_driving_time("Unknown", "Munich") is None


class TestIsWithinRadius:
    """Tests for is_within_radius function."""

    def test_is_within_radius_true(self):
        """Test location within radius."""
        # Vienna is within 400 km of Munich
        result = is_within_radius(48.1351, 11.5820, 48.2082, 16.3738, 400)
        assert result is True

    def test_is_within_radius_false(self):
        """Test location outside radius."""
        # Berlin is not within 400 km of Munich
        result = is_within_radius(48.1351, 11.5820, 52.5200, 13.4050, 400)
        assert result is False

    def test_is_within_radius_exact(self):
        """Test location exactly at radius boundary."""
        # Same location, 0 km radius
        result = is_within_radius(48.1351, 11.5820, 48.1351, 11.5820, 0)
        assert result is True

    def test_is_within_radius_none_values(self):
        """Test with None values."""
        assert is_within_radius(None, 11.5820, 48.2082, 16.3738, 400) is False
        assert is_within_radius(48.1351, None, 48.2082, 16.3738, 400) is False
        assert is_within_radius(48.1351, 11.5820, None, 16.3738, 400) is False
        assert is_within_radius(48.1351, 11.5820, 48.2082, None, 400) is False
        assert is_within_radius(48.1351, 11.5820, 48.2082, 16.3738, None) is False

    def test_is_within_radius_negative_radius(self):
        """Test with negative radius."""
        assert is_within_radius(48.1351, 11.5820, 48.2082, 16.3738, -100) is False


class TestGetAllCities:
    """Tests for get_all_cities function."""

    def test_get_all_cities_returns_list(self):
        """Test that function returns a list."""
        cities = get_all_cities()
        assert isinstance(cities, list)

    def test_get_all_cities_not_empty(self):
        """Test that list is not empty."""
        cities = get_all_cities()
        assert len(cities) > 0

    def test_get_all_cities_has_munich(self):
        """Test that Munich is in the list."""
        cities = get_all_cities()
        assert "Munich, Germany" in cities

    def test_get_all_cities_sorted(self):
        """Test that cities are sorted."""
        cities = get_all_cities()
        assert cities == sorted(cities)

    def test_get_all_cities_minimum_count(self):
        """Test that we have at least 30 cities."""
        cities = get_all_cities()
        assert len(cities) >= 30


class TestGetCitiesWithinRadius:
    """Tests for get_cities_within_radius function."""

    def test_get_cities_within_radius_munich(self):
        """Test getting cities within 200 km of Munich."""
        cities = get_cities_within_radius("Munich", 200)
        assert len(cities) > 0
        # Munich itself should be first (distance 0)
        assert cities[0][0] == "Munich, Germany"
        assert cities[0][1] == 0.0

    def test_get_cities_within_radius_sorted(self):
        """Test that results are sorted by distance."""
        cities = get_cities_within_radius("Munich", 500)
        for i in range(len(cities) - 1):
            assert cities[i][1] <= cities[i + 1][1]

    def test_get_cities_within_radius_distances_correct(self):
        """Test that all returned cities are within radius."""
        cities = get_cities_within_radius("Munich", 200)
        for city, distance in cities:
            assert distance <= 200

    def test_get_cities_within_radius_unknown_city(self):
        """Test with unknown city."""
        cities = get_cities_within_radius("Unknown City", 500)
        assert cities == []

    def test_get_cities_within_radius_small_radius(self):
        """Test with very small radius (only center city)."""
        cities = get_cities_within_radius("Munich", 10)
        # Should only include Munich itself
        assert len(cities) == 1
        assert cities[0][0] == "Munich, Germany"


class TestCityCoordinatesData:
    """Tests for CITY_COORDINATES data."""

    def test_city_coordinates_not_empty(self):
        """Test that coordinates dictionary is not empty."""
        assert len(CITY_COORDINATES) > 0

    def test_city_coordinates_format(self):
        """Test that all coordinates have correct format."""
        for city, (lat, lon) in CITY_COORDINATES.items():
            # City name should be a string
            assert isinstance(city, str)
            assert len(city) > 0

            # Coordinates should be floats
            assert isinstance(lat, (int, float))
            assert isinstance(lon, (int, float))

            # Latitude should be between -90 and 90
            assert -90 <= lat <= 90

            # Longitude should be between -180 and 180
            assert -180 <= lon <= 180

    def test_city_coordinates_has_major_cities(self):
        """Test that major cities are included."""
        major_cities = [
            "Munich, Germany",
            "Berlin, Germany",
            "Vienna, Austria",
            "Paris, France",
            "Rome, Italy",
            "Barcelona, Spain",
            "Amsterdam, Netherlands",
        ]
        for city in major_cities:
            assert city in CITY_COORDINATES

    def test_city_coordinates_minimum_count(self):
        """Test that we have at least 30 cities."""
        assert len(CITY_COORDINATES) >= 30
