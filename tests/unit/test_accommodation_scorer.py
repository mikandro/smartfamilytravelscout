"""
Unit tests for AccommodationScorer.

Tests the accommodation comparison and scoring system to ensure correct
price calculations, scoring across multiple dimensions, and ranking logic.
"""

import pytest

from app.ai.accommodation_scorer import AccommodationScorer
from app.models.accommodation import Accommodation


class TestAccommodationScorer:
    """Test suite for AccommodationScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create an AccommodationScorer instance."""
        return AccommodationScorer()

    @pytest.fixture
    def excellent_accommodation(self):
        """Create an excellent value accommodation for testing."""
        return Accommodation(
            id=1,
            destination_city="Barcelona",
            name="Family Apartment Barcelona",
            type="apartment",
            bedrooms=2,
            price_per_night=80.0,
            family_friendly=True,
            has_kitchen=True,
            has_kids_club=False,
            rating=9.0,
            review_count=150,
            source="booking.com",
        )

    @pytest.fixture
    def good_accommodation(self):
        """Create a good value accommodation for testing."""
        return Accommodation(
            id=2,
            destination_city="Lisbon",
            name="Central Hotel Lisbon",
            type="hotel",
            bedrooms=1,
            price_per_night=120.0,
            family_friendly=True,
            has_kitchen=False,
            has_kids_club=True,
            rating=8.2,
            review_count=80,
            source="booking.com",
        )

    @pytest.fixture
    def poor_accommodation(self):
        """Create a poor value accommodation for testing."""
        return Accommodation(
            id=3,
            destination_city="Barcelona",
            name="Budget Hostel",
            type="hostel",
            bedrooms=None,
            price_per_night=200.0,
            family_friendly=False,
            has_kitchen=False,
            has_kids_club=False,
            rating=6.5,
            review_count=10,
            source="airbnb",
        )

    def test_score_accommodation_excellent(self, scorer, excellent_accommodation):
        """Test scoring an excellent value accommodation."""
        result = scorer.score_accommodation(excellent_accommodation)

        assert "overall_score" in result
        assert "price_per_person_per_night" in result
        assert "price_quality_score" in result
        assert "family_suitability_score" in result
        assert "quality_score" in result

        # Excellent accommodation should have high scores
        assert result["overall_score"] > 70.0
        assert result["value_category"] in ["excellent", "good"]
        assert result["family_features"]["family_friendly"] is True
        assert result["family_features"]["has_kitchen"] is True

    def test_score_accommodation_poor(self, scorer, poor_accommodation):
        """Test scoring a poor value accommodation."""
        result = scorer.score_accommodation(poor_accommodation)

        # Poor accommodation should have lower scores
        assert result["overall_score"] < 70.0
        assert result["value_category"] in ["poor", "average"]
        assert result["family_features"]["family_friendly"] is False

    def test_price_per_person_calculation(self, scorer, excellent_accommodation):
        """Test price per person per night calculation."""
        result = scorer.score_accommodation(excellent_accommodation)

        # 2 bedrooms * 2 persons = 4 capacity
        # 80 EUR / 4 persons = 20 EUR per person
        assert result["estimated_capacity"] == 4
        assert result["price_per_person_per_night"] == 20.0

    def test_price_per_person_no_bedrooms(self, scorer, poor_accommodation):
        """Test price per person calculation when bedrooms not specified."""
        result = scorer.score_accommodation(poor_accommodation)

        # Should default to minimum family capacity of 4
        assert result["estimated_capacity"] == 4
        assert result["price_per_person_per_night"] == 50.0  # 200 / 4

    def test_compare_accommodations(self, scorer, excellent_accommodation, good_accommodation, poor_accommodation):
        """Test comparing and ranking multiple accommodations."""
        accommodations = [poor_accommodation, good_accommodation, excellent_accommodation]

        results = scorer.compare_accommodations(accommodations)

        # Should return 3 results
        assert len(results) == 3

        # Should be sorted by overall_score descending
        assert results[0]["overall_score"] >= results[1]["overall_score"]
        assert results[1]["overall_score"] >= results[2]["overall_score"]

        # Best accommodation should be first
        assert results[0]["accommodation"].id == excellent_accommodation.id

    def test_filter_by_score(self, scorer, excellent_accommodation, good_accommodation, poor_accommodation):
        """Test filtering accommodations by minimum score."""
        accommodations = [poor_accommodation, good_accommodation, excellent_accommodation]

        # Filter for good accommodations (score >= 70)
        filtered = scorer.filter_by_score(accommodations, min_score=70.0)

        # Should only include accommodations with score >= 70
        assert len(filtered) <= len(accommodations)

        # All filtered accommodations should meet threshold
        for accommodation in filtered:
            result = scorer.score_accommodation(accommodation)
            assert result["overall_score"] >= 70.0

    def test_family_suitability_score_all_features(self, scorer, excellent_accommodation):
        """Test family suitability scoring with all features."""
        result = scorer.score_accommodation(excellent_accommodation)

        # Accommodation has: family_friendly, kitchen, 2 bedrooms, high rating
        # Should get high family suitability score
        assert result["family_suitability_score"] > 60.0

    def test_family_suitability_score_no_features(self, scorer, poor_accommodation):
        """Test family suitability scoring with no features."""
        result = scorer.score_accommodation(poor_accommodation)

        # Accommodation has: no family features, no bedrooms specified
        # Should get low family suitability score
        assert result["family_suitability_score"] < 50.0

    def test_quality_score_high_reviews(self, scorer, excellent_accommodation):
        """Test quality score with high review count."""
        result = scorer.score_accommodation(excellent_accommodation)

        # 150 reviews, 9.0 rating should give high quality score
        assert result["quality_score"] > 80.0

    def test_quality_score_low_reviews(self, scorer, poor_accommodation):
        """Test quality score with low review count."""
        result = scorer.score_accommodation(poor_accommodation)

        # 10 reviews should reduce credibility
        # Should be lower than high-review accommodations
        assert result["quality_score"] < 70.0

    def test_value_category_excellent(self, scorer, excellent_accommodation):
        """Test value category determination for excellent value."""
        result = scorer.score_accommodation(excellent_accommodation)

        # Low price (80), high rating (9.0) = excellent value
        assert result["value_category"] == "excellent"

    def test_value_category_poor(self, scorer, poor_accommodation):
        """Test value category determination for poor value."""
        result = scorer.score_accommodation(poor_accommodation)

        # High price (200), low rating (6.5) = poor value
        assert result["value_category"] == "poor"

    def test_comparison_notes_generation(self, scorer, excellent_accommodation):
        """Test comparison notes generation."""
        result = scorer.score_accommodation(excellent_accommodation)

        assert "comparison_notes" in result
        assert len(result["comparison_notes"]) > 0
        assert "value" in result["comparison_notes"].lower()

    def test_estimate_capacity_with_bedrooms(self, scorer):
        """Test capacity estimation with bedroom count."""
        # 3 bedrooms should give capacity of 6 (3 * 2)
        accommodation = Accommodation(
            id=1,
            destination_city="Test",
            name="Test",
            type="apartment",
            bedrooms=3,
            price_per_night=100.0,
            family_friendly=True,
            has_kitchen=True,
            has_kids_club=False,
            source="test",
        )

        capacity = scorer._estimate_capacity(accommodation)
        assert capacity == 6

    def test_estimate_capacity_minimum(self, scorer):
        """Test capacity estimation respects minimum family size."""
        # 1 bedroom should still give minimum capacity of 4 for families
        accommodation = Accommodation(
            id=1,
            destination_city="Test",
            name="Test",
            type="apartment",
            bedrooms=1,
            price_per_night=100.0,
            family_friendly=True,
            has_kitchen=True,
            has_kids_club=False,
            source="test",
        )

        capacity = scorer._estimate_capacity(accommodation)
        assert capacity == 4  # Minimum for family

    def test_estimate_capacity_no_bedrooms(self, scorer):
        """Test capacity estimation when bedrooms not specified."""
        accommodation = Accommodation(
            id=1,
            destination_city="Test",
            name="Test",
            type="hotel",
            bedrooms=None,
            price_per_night=100.0,
            family_friendly=True,
            has_kitchen=False,
            has_kids_club=False,
            source="test",
        )

        capacity = scorer._estimate_capacity(accommodation)
        assert capacity == 4  # Default to family of 4

    def test_weighted_overall_score(self, scorer, excellent_accommodation):
        """Test overall score is weighted combination of component scores."""
        result = scorer.score_accommodation(excellent_accommodation)

        # Calculate expected weighted score
        expected = (
            result["price_quality_score"] * 0.40
            + result["family_suitability_score"] * 0.40
            + result["quality_score"] * 0.20
        )

        # Should match with small floating point tolerance
        assert abs(result["overall_score"] - expected) < 0.01

    def test_score_accommodation_missing_rating(self, scorer):
        """Test scoring when rating is missing."""
        accommodation = Accommodation(
            id=1,
            destination_city="Test",
            name="Test",
            type="apartment",
            bedrooms=2,
            price_per_night=100.0,
            family_friendly=True,
            has_kitchen=True,
            has_kids_club=False,
            rating=None,  # Missing rating
            review_count=0,
            source="test",
        )

        result = scorer.score_accommodation(accommodation)

        # Should use default rating of 7.0
        assert result["overall_score"] > 0
        assert "value_category" in result

    def test_empty_accommodations_list(self, scorer):
        """Test compare_accommodations with empty list."""
        results = scorer.compare_accommodations([])

        assert results == []

    def test_single_accommodation(self, scorer, excellent_accommodation):
        """Test compare_accommodations with single accommodation."""
        results = scorer.compare_accommodations([excellent_accommodation])

        assert len(results) == 1
        assert results[0]["accommodation"].id == excellent_accommodation.id
