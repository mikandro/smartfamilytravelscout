"""
Price history tracking service.

This module provides functionality for:
- Tracking flight price changes
- Querying price history
- Detecting price drops
- Analyzing price trends
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.flight import Flight
from app.models.price_history import PriceHistory

logger = logging.getLogger(__name__)


class PriceHistoryService:
    """Service for tracking and analyzing flight price history."""

    @staticmethod
    async def track_price_change(
        db: AsyncSession,
        flight: Flight,
        old_price: Optional[float] = None,
    ) -> Optional[PriceHistory]:
        """
        Track a price change for a flight.

        Creates a PriceHistory record when a flight price is updated.
        Should be called after updating a flight price in the database.

        Args:
            db: Database session
            flight: Flight object with current price
            old_price: Previous price (if this is an update)

        Returns:
            PriceHistory record if created, None otherwise
        """
        try:
            # Create route code
            route = f"{flight.origin_airport.iata_code}-{flight.destination_airport.iata_code}"

            # Create price history record
            price_record = PriceHistory(
                route=route,
                price=float(flight.price_per_person),
                source=flight.source,
                scraped_at=flight.scraped_at or datetime.now(),
            )

            db.add(price_record)
            await db.flush()

            if old_price is not None:
                change_pct = ((float(flight.price_per_person) - old_price) / old_price) * 100
                logger.info(
                    f"Price change tracked: {route} {flight.source} "
                    f"€{old_price:.2f} → €{flight.price_per_person:.2f} "
                    f"({change_pct:+.1f}%)"
                )
            else:
                logger.info(
                    f"Price tracked: {route} {flight.source} €{flight.price_per_person:.2f}"
                )

            return price_record

        except Exception as e:
            logger.error(f"Error tracking price change: {e}", exc_info=True)
            return None

    @staticmethod
    def track_price_change_sync(
        db: Session,
        origin_iata: str,
        destination_iata: str,
        price: float,
        source: str,
        scraped_at: Optional[datetime] = None,
    ) -> Optional[PriceHistory]:
        """
        Track a price change (synchronous version for Celery tasks).

        Args:
            db: Synchronous database session
            origin_iata: Origin airport IATA code
            destination_iata: Destination airport IATA code
            price: Price per person
            source: Data source (e.g., 'kiwi', 'skyscanner')
            scraped_at: When the price was scraped

        Returns:
            PriceHistory record if created, None otherwise
        """
        try:
            route = f"{origin_iata}-{destination_iata}"

            price_record = PriceHistory(
                route=route,
                price=float(price),
                source=source,
                scraped_at=scraped_at or datetime.now(),
            )

            db.add(price_record)
            db.flush()

            logger.info(f"Price tracked: {route} {source} €{price:.2f}")

            return price_record

        except Exception as e:
            logger.error(f"Error tracking price change: {e}", exc_info=True)
            return None

    @staticmethod
    async def get_price_history(
        db: AsyncSession,
        route: Optional[str] = None,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        source: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[PriceHistory]:
        """
        Query price history records.

        Args:
            db: Database session
            route: Route code (e.g., 'MUC-LIS') - takes precedence
            origin: Origin airport IATA code
            destination: Destination airport IATA code
            source: Filter by data source
            days: Number of days to look back
            limit: Maximum number of records

        Returns:
            List of PriceHistory records ordered by scraped_at desc
        """
        try:
            # Build route filter
            if route:
                route_filter = route.upper()
            elif origin and destination:
                route_filter = f"{origin.upper()}-{destination.upper()}"
            else:
                route_filter = None

            # Build query
            query = select(PriceHistory)

            # Apply filters
            conditions = []

            if route_filter:
                conditions.append(PriceHistory.route == route_filter)

            if source:
                conditions.append(PriceHistory.source == source)

            # Date filter
            cutoff_date = datetime.now() - timedelta(days=days)
            conditions.append(PriceHistory.scraped_at >= cutoff_date)

            if conditions:
                query = query.where(and_(*conditions))

            # Order and limit
            query = query.order_by(desc(PriceHistory.scraped_at)).limit(limit)

            result = await db.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Error querying price history: {e}", exc_info=True)
            return []

    @staticmethod
    async def detect_price_drops(
        db: AsyncSession,
        threshold_percent: float = 10.0,
        days: int = 7,
    ) -> List[Dict]:
        """
        Detect significant price drops.

        Compares recent prices (last 24 hours) with historical prices
        (last N days) to find routes with significant price drops.

        Args:
            db: Database session
            threshold_percent: Minimum price drop percentage to report
            days: Number of days to compare against

        Returns:
            List of dicts with price drop information:
                {
                    'route': 'MUC-LIS',
                    'source': 'kiwi',
                    'current_price': 100.0,
                    'previous_avg_price': 150.0,
                    'drop_percent': 33.3,
                    'drop_amount': 50.0,
                }
        """
        try:
            # Get recent prices (last 24 hours)
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_query = (
                select(
                    PriceHistory.route,
                    PriceHistory.source,
                    func.min(PriceHistory.price).label("current_price"),
                )
                .where(PriceHistory.scraped_at >= recent_cutoff)
                .group_by(PriceHistory.route, PriceHistory.source)
            )

            recent_result = await db.execute(recent_query)
            recent_prices = {
                (row.route, row.source): row.current_price for row in recent_result.all()
            }

            if not recent_prices:
                return []

            # Get historical average prices
            historical_cutoff = datetime.now() - timedelta(days=days)
            historical_exclude_cutoff = datetime.now() - timedelta(hours=24)

            drops = []

            for (route, source), current_price in recent_prices.items():
                # Get historical average for this route/source
                hist_query = (
                    select(func.avg(PriceHistory.price).label("avg_price"))
                    .where(
                        and_(
                            PriceHistory.route == route,
                            PriceHistory.source == source,
                            PriceHistory.scraped_at >= historical_cutoff,
                            PriceHistory.scraped_at < historical_exclude_cutoff,
                        )
                    )
                )

                hist_result = await db.execute(hist_query)
                avg_price = hist_result.scalar()

                if avg_price and avg_price > 0:
                    drop_amount = avg_price - current_price
                    drop_percent = (drop_amount / avg_price) * 100

                    if drop_percent >= threshold_percent:
                        drops.append({
                            "route": route,
                            "source": source,
                            "current_price": float(current_price),
                            "previous_avg_price": float(avg_price),
                            "drop_percent": float(drop_percent),
                            "drop_amount": float(drop_amount),
                        })

            # Sort by drop percentage (highest first)
            drops.sort(key=lambda x: x["drop_percent"], reverse=True)

            logger.info(f"Detected {len(drops)} price drops (threshold: {threshold_percent}%)")
            return drops

        except Exception as e:
            logger.error(f"Error detecting price drops: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_price_trends(
        db: AsyncSession,
        route: str,
        source: Optional[str] = None,
        days: int = 30,
    ) -> Dict:
        """
        Analyze price trends for a specific route.

        Args:
            db: Database session
            route: Route code (e.g., 'MUC-LIS')
            source: Optional source filter
            days: Number of days to analyze

        Returns:
            Dict with trend analysis:
                {
                    'route': 'MUC-LIS',
                    'current_price': 100.0,
                    'min_price': 80.0,
                    'max_price': 150.0,
                    'avg_price': 115.0,
                    'trend': 'decreasing',  # 'increasing', 'decreasing', 'stable'
                    'price_points': [(datetime, price), ...],
                }
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # Build query
            query = select(PriceHistory).where(
                and_(
                    PriceHistory.route == route.upper(),
                    PriceHistory.scraped_at >= cutoff_date,
                )
            )

            if source:
                query = query.where(PriceHistory.source == source)

            query = query.order_by(PriceHistory.scraped_at)

            result = await db.execute(query)
            records = list(result.scalars().all())

            if not records:
                return {
                    "route": route,
                    "error": "No price data found",
                }

            prices = [float(r.price) for r in records]
            price_points = [(r.scraped_at, float(r.price)) for r in records]

            # Calculate statistics
            current_price = prices[-1]
            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)

            # Determine trend (simple linear trend)
            if len(prices) >= 3:
                # Compare first third vs last third
                first_third_avg = sum(prices[:len(prices)//3]) / (len(prices)//3)
                last_third_avg = sum(prices[-len(prices)//3:]) / (len(prices)//3)

                change_percent = ((last_third_avg - first_third_avg) / first_third_avg) * 100

                if change_percent < -5:
                    trend = "decreasing"
                elif change_percent > 5:
                    trend = "increasing"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            return {
                "route": route,
                "source": source or "all",
                "current_price": current_price,
                "min_price": min_price,
                "max_price": max_price,
                "avg_price": round(avg_price, 2),
                "trend": trend,
                "data_points": len(records),
                "price_points": price_points,
            }

        except Exception as e:
            logger.error(f"Error analyzing price trends: {e}", exc_info=True)
            return {
                "route": route,
                "error": str(e),
            }

    @staticmethod
    async def get_best_booking_time(
        db: AsyncSession,
        route: str,
        days: int = 90,
    ) -> Dict:
        """
        Analyze historical data to suggest best booking time.

        Args:
            db: Database session
            route: Route code (e.g., 'MUC-LIS')
            days: Number of days of historical data to analyze

        Returns:
            Dict with booking recommendations:
                {
                    'route': 'MUC-LIS',
                    'recommendation': 'Book now' or 'Wait',
                    'current_price': 100.0,
                    'avg_price': 120.0,
                    'confidence': 'high',  # high, medium, low
                }
        """
        trends = await PriceHistoryService.get_price_trends(db, route, days=days)

        if "error" in trends:
            return {
                "route": route,
                "recommendation": "Insufficient data",
                "confidence": "low",
            }

        current_price = trends["current_price"]
        avg_price = trends["avg_price"]
        min_price = trends["min_price"]
        trend = trends["trend"]
        data_points = trends["data_points"]

        # Determine confidence based on data points
        if data_points >= 20:
            confidence = "high"
        elif data_points >= 10:
            confidence = "medium"
        else:
            confidence = "low"

        # Make recommendation
        price_vs_avg = ((current_price - avg_price) / avg_price) * 100
        price_vs_min = ((current_price - min_price) / min_price) * 100

        if current_price <= min_price * 1.05:  # Within 5% of minimum
            recommendation = "Book now - near historical low"
        elif trend == "increasing" and current_price < avg_price:
            recommendation = "Book soon - prices rising"
        elif trend == "decreasing":
            recommendation = "Wait - prices falling"
        elif price_vs_avg < -10:  # More than 10% below average
            recommendation = "Book now - good deal"
        elif price_vs_avg > 20:  # More than 20% above average
            recommendation = "Wait - prices high"
        else:
            recommendation = "Normal price - your choice"

        return {
            "route": route,
            "recommendation": recommendation,
            "current_price": current_price,
            "avg_price": avg_price,
            "min_price": min_price,
            "price_vs_avg_percent": round(price_vs_avg, 1),
            "price_vs_min_percent": round(price_vs_min, 1),
            "trend": trend,
            "confidence": confidence,
            "data_points": data_points,
        }
