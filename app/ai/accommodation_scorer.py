"""
Accommodation comparison and scoring system.

This module provides standardized scoring for accommodations across different
booking platforms, enabling price comparison and quality assessment.

Example:
    >>> scorer = AccommodationScorer()
    >>> score = scorer.score_accommodation(accommodation)
    >>> print(f"Score: {score['overall_score']}/100")
    >>> print(f"Price per person per night: €{score['price_per_person_per_night']}")
"""

import logging
from typing import Dict, List, Optional

from app.models.accommodation import Accommodation

logger = logging.getLogger(__name__)


class AccommodationScorer:
    """
    Scores and compares accommodations across multiple dimensions.

    This class evaluates accommodations based on:
    - Price per night per person (normalized for family size)
    - Price-to-quality ratio (value for money)
    - Family suitability (features and amenities)
    - Overall rating and review count

    Features:
        - Standardized scoring (0-100 scale)
        - Cross-platform comparison
        - Family-focused evaluation
        - Transparent scoring breakdown

    Scoring Components:
        - Price-Quality Score (40%): Value assessment based on price vs rating
        - Family Suitability Score (40%): Family-friendly features and space
        - Quality Score (20%): Raw rating and review credibility
    """

    # Default capacity assumptions
    DEFAULT_PERSONS_PER_BEDROOM = 2
    MIN_FAMILY_CAPACITY = 4  # Family of 4 (2 adults + 2 kids)

    # Scoring weights
    WEIGHT_PRICE_QUALITY = 0.40
    WEIGHT_FAMILY_SUITABILITY = 0.40
    WEIGHT_QUALITY = 0.20

    # Price benchmarks (EUR per night for family of 4)
    EXCELLENT_PRICE = 80.0  # Below this = excellent value
    GOOD_PRICE = 120.0  # Below this = good value
    AVERAGE_PRICE = 160.0  # Below this = average value
    EXPENSIVE_PRICE = 200.0  # Above this = expensive

    # Rating benchmarks (0-10 scale)
    EXCELLENT_RATING = 9.0
    GOOD_RATING = 8.0
    AVERAGE_RATING = 7.0
    POOR_RATING = 6.0

    def score_accommodation(self, accommodation: Accommodation) -> Dict:
        """
        Score an accommodation across multiple dimensions.

        Args:
            accommodation: Accommodation object to score

        Returns:
            Dictionary with detailed scoring breakdown:
            {
                'overall_score': 85.5,                    # 0-100
                'price_per_person_per_night': 20.0,      # EUR
                'estimated_capacity': 4,                  # persons
                'price_quality_score': 82.0,              # 0-100
                'family_suitability_score': 90.0,         # 0-100
                'quality_score': 85.0,                    # 0-100
                'value_category': 'excellent',            # excellent/good/average/poor
                'family_features': {                      # Boolean flags
                    'family_friendly': True,
                    'has_kitchen': True,
                    'has_kids_club': False,
                    'adequate_bedrooms': True,
                },
                'comparison_notes': 'Excellent value...'  # Text assessment
            }

        Example:
            >>> scorer = AccommodationScorer()
            >>> result = scorer.score_accommodation(accommodation)
            >>> print(f"Overall: {result['overall_score']}/100")
            >>> print(f"Family suitability: {result['family_suitability_score']}/100")
        """
        # Calculate price per person per night
        capacity = self._estimate_capacity(accommodation)
        price_per_person_per_night = float(accommodation.price_per_night) / capacity

        # Calculate component scores
        price_quality_score = self._calculate_price_quality_score(
            accommodation, price_per_person_per_night
        )
        family_suitability_score = self._calculate_family_suitability_score(
            accommodation
        )
        quality_score = self._calculate_quality_score(accommodation)

        # Calculate weighted overall score
        overall_score = (
            price_quality_score * self.WEIGHT_PRICE_QUALITY
            + family_suitability_score * self.WEIGHT_FAMILY_SUITABILITY
            + quality_score * self.WEIGHT_QUALITY
        )

        # Determine value category
        value_category = self._determine_value_category(
            price_per_person_per_night, accommodation.rating
        )

        # Extract family features
        family_features = {
            "family_friendly": accommodation.family_friendly,
            "has_kitchen": accommodation.has_kitchen,
            "has_kids_club": accommodation.has_kids_club,
            "adequate_bedrooms": (accommodation.bedrooms or 0) >= 2,
        }

        # Generate comparison notes
        comparison_notes = self._generate_comparison_notes(
            accommodation, price_per_person_per_night, value_category
        )

        return {
            "overall_score": round(overall_score, 2),
            "price_per_person_per_night": round(price_per_person_per_night, 2),
            "estimated_capacity": capacity,
            "price_quality_score": round(price_quality_score, 2),
            "family_suitability_score": round(family_suitability_score, 2),
            "quality_score": round(quality_score, 2),
            "value_category": value_category,
            "family_features": family_features,
            "comparison_notes": comparison_notes,
        }

    def compare_accommodations(
        self, accommodations: List[Accommodation]
    ) -> List[Dict]:
        """
        Score and rank multiple accommodations.

        Args:
            accommodations: List of Accommodation objects to compare

        Returns:
            List of scoring results sorted by overall_score descending.
            Each result includes the accommodation object plus all scoring data.

        Example:
            >>> scorer = AccommodationScorer()
            >>> ranked = scorer.compare_accommodations(accommodations)
            >>> for result in ranked[:5]:  # Top 5
            ...     print(f"{result['accommodation'].name}: {result['overall_score']}/100")
        """
        results = []

        for accommodation in accommodations:
            try:
                score_result = self.score_accommodation(accommodation)
                score_result["accommodation"] = accommodation
                results.append(score_result)
            except Exception as e:
                logger.error(
                    f"Error scoring accommodation {accommodation.id}: {e}",
                    exc_info=True,
                )
                continue

        # Sort by overall score descending
        results.sort(key=lambda x: x["overall_score"], reverse=True)

        logger.info(
            f"Compared {len(results)} accommodations, "
            f"best score: {results[0]['overall_score']:.1f}" if results else 0
        )

        return results

    def filter_by_score(
        self, accommodations: List[Accommodation], min_score: float = 70.0
    ) -> List[Accommodation]:
        """
        Filter accommodations by minimum score threshold.

        Args:
            accommodations: List of Accommodation objects
            min_score: Minimum overall score (default: 70.0)

        Returns:
            List of Accommodation objects meeting the threshold, sorted by score.

        Example:
            >>> scorer = AccommodationScorer()
            >>> good_accommodations = scorer.filter_by_score(all_accommodations, min_score=80)
        """
        results = self.compare_accommodations(accommodations)
        filtered = [
            r["accommodation"] for r in results if r["overall_score"] >= min_score
        ]

        logger.info(
            f"Filtered {len(filtered)}/{len(accommodations)} accommodations "
            f"with score >= {min_score}"
        )

        return filtered

    def _estimate_capacity(self, accommodation: Accommodation) -> int:
        """
        Estimate accommodation capacity for a family.

        Uses bedrooms to estimate capacity, assuming 2 persons per bedroom.
        Defaults to minimum family capacity of 4 if bedrooms not specified.

        Args:
            accommodation: Accommodation object

        Returns:
            Estimated capacity in persons (minimum 4)
        """
        if accommodation.bedrooms and accommodation.bedrooms > 0:
            capacity = accommodation.bedrooms * self.DEFAULT_PERSONS_PER_BEDROOM
            # Ensure minimum capacity for family of 4
            return max(capacity, self.MIN_FAMILY_CAPACITY)

        # Default to family of 4 if bedrooms not specified
        return self.MIN_FAMILY_CAPACITY

    def _calculate_price_quality_score(
        self, accommodation: Accommodation, price_per_person_per_night: float
    ) -> float:
        """
        Calculate price-to-quality score (0-100).

        Evaluates value for money by comparing price against rating.
        Lower price + higher rating = better score.

        Args:
            accommodation: Accommodation object
            price_per_person_per_night: Calculated price per person per night

        Returns:
            Score from 0 to 100
        """
        rating = float(accommodation.rating) if accommodation.rating else 7.0

        # Price score (0-100): lower is better
        # Excellent (€20/person) = 100, Expensive (€50+/person) = 0
        if price_per_person_per_night <= self.EXCELLENT_PRICE / 4:
            price_score = 100.0
        elif price_per_person_per_night >= self.EXPENSIVE_PRICE / 4:
            price_score = 0.0
        else:
            # Linear interpolation
            price_range = (self.EXPENSIVE_PRICE / 4) - (self.EXCELLENT_PRICE / 4)
            price_diff = price_per_person_per_night - (self.EXCELLENT_PRICE / 4)
            price_score = 100.0 - (price_diff / price_range) * 100.0

        # Rating score (0-100): convert 0-10 rating to 0-100 scale
        rating_score = (rating / 10.0) * 100.0

        # Combine: 60% price weight, 40% rating weight
        # (price matters more for value assessment)
        combined_score = (price_score * 0.6) + (rating_score * 0.4)

        return max(0.0, min(100.0, combined_score))

    def _calculate_family_suitability_score(
        self, accommodation: Accommodation
    ) -> float:
        """
        Calculate family suitability score (0-100).

        Evaluates features important for families:
        - Family-friendly flag
        - Kitchen availability
        - Kids club
        - Adequate bedrooms
        - Good rating

        Args:
            accommodation: Accommodation object

        Returns:
            Score from 0 to 100
        """
        score = 0.0

        # Family-friendly flag (30 points)
        if accommodation.family_friendly:
            score += 30.0

        # Kitchen (25 points) - important for families to save on dining
        if accommodation.has_kitchen:
            score += 25.0

        # Kids club (20 points) - great for parents to get some time
        if accommodation.has_kids_club:
            score += 20.0

        # Adequate bedrooms (15 points) - at least 2 for family of 4
        bedrooms = accommodation.bedrooms or 0
        if bedrooms >= 2:
            score += 15.0
        elif bedrooms == 1:
            score += 7.0

        # Good rating (10 points) - high rating suggests good experience
        rating = float(accommodation.rating) if accommodation.rating else 7.0
        if rating >= self.EXCELLENT_RATING:
            score += 10.0
        elif rating >= self.GOOD_RATING:
            score += 7.0
        elif rating >= self.AVERAGE_RATING:
            score += 4.0

        return max(0.0, min(100.0, score))

    def _calculate_quality_score(self, accommodation: Accommodation) -> float:
        """
        Calculate raw quality score (0-100).

        Based on rating and review count (more reviews = more credible).

        Args:
            accommodation: Accommodation object

        Returns:
            Score from 0 to 100
        """
        rating = float(accommodation.rating) if accommodation.rating else 7.0
        review_count = accommodation.review_count or 0

        # Convert rating (0-10) to score (0-100)
        base_score = (rating / 10.0) * 100.0

        # Credibility multiplier based on review count
        # 0-10 reviews: 0.7x, 11-50: 0.85x, 51-100: 0.95x, 100+: 1.0x
        if review_count >= 100:
            credibility = 1.0
        elif review_count >= 51:
            credibility = 0.95
        elif review_count >= 11:
            credibility = 0.85
        else:
            credibility = 0.7

        return base_score * credibility

    def _determine_value_category(
        self, price_per_person_per_night: float, rating: Optional[float]
    ) -> str:
        """
        Categorize accommodation value.

        Args:
            price_per_person_per_night: Price per person per night
            rating: Accommodation rating (0-10)

        Returns:
            Category: 'excellent', 'good', 'average', or 'poor'
        """
        rating_value = float(rating) if rating else 7.0
        total_price_per_night = price_per_person_per_night * 4  # Family of 4

        # Excellent value: Low price + high rating
        if total_price_per_night <= self.GOOD_PRICE and rating_value >= self.GOOD_RATING:
            return "excellent"

        # Good value: Reasonable price + decent rating
        if (
            total_price_per_night <= self.AVERAGE_PRICE
            and rating_value >= self.AVERAGE_RATING
        ):
            return "good"

        # Poor value: High price or low rating
        if (
            total_price_per_night > self.EXPENSIVE_PRICE
            or rating_value < self.AVERAGE_RATING
        ):
            return "poor"

        # Otherwise average
        return "average"

    def _generate_comparison_notes(
        self,
        accommodation: Accommodation,
        price_per_person_per_night: float,
        value_category: str,
    ) -> str:
        """
        Generate human-readable comparison notes.

        Args:
            accommodation: Accommodation object
            price_per_person_per_night: Calculated price per person
            value_category: Value category

        Returns:
            Comparison notes text
        """
        notes = []

        # Value assessment
        if value_category == "excellent":
            notes.append("Excellent value for money")
        elif value_category == "good":
            notes.append("Good value")
        elif value_category == "poor":
            notes.append("Below-average value")
        else:
            notes.append("Average value")

        # Price context
        total_per_night = price_per_person_per_night * 4
        notes.append(f"€{price_per_person_per_night:.2f}/person/night (€{total_per_night:.2f} total)")

        # Rating
        if accommodation.rating:
            rating = float(accommodation.rating)
            if rating >= self.EXCELLENT_RATING:
                notes.append("Excellent rating")
            elif rating >= self.GOOD_RATING:
                notes.append("Good rating")

        # Family features
        family_perks = []
        if accommodation.family_friendly:
            family_perks.append("family-friendly")
        if accommodation.has_kitchen:
            family_perks.append("kitchen")
        if accommodation.has_kids_club:
            family_perks.append("kids club")

        if family_perks:
            notes.append(f"Features: {', '.join(family_perks)}")

        return ". ".join(notes) + "."
