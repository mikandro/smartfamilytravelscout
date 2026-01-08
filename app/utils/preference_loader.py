"""
Utility for loading user preference profiles from JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.user_preference import UserPreference

logger = logging.getLogger(__name__)


class PreferenceLoader:
    """
    Loads and manages user preference profiles.

    Preference profiles are stored as JSON files in app/preference_profiles/
    and can be loaded into the database or used directly.
    """

    def __init__(self):
        """Initialize the preference loader."""
        self.profiles_dir = Path(__file__).parent.parent / "preference_profiles"

        if not self.profiles_dir.exists():
            logger.warning(f"Preference profiles directory not found: {self.profiles_dir}")

    def list_available_profiles(self) -> List[str]:
        """
        List all available preference profile names.

        Returns:
            List of profile names (without .json extension)
        """
        if not self.profiles_dir.exists():
            return []

        profiles = []
        for file_path in self.profiles_dir.glob("*.json"):
            profiles.append(file_path.stem)

        return sorted(profiles)

    def load_profile_data(self, profile_name: str) -> Dict:
        """
        Load preference profile data from JSON file.

        Args:
            profile_name: Name of the profile (without .json extension)

        Returns:
            Dictionary with profile data

        Raises:
            FileNotFoundError: If profile file doesn't exist
            ValueError: If profile data is invalid
        """
        file_path = self.profiles_dir / f"{profile_name}.json"

        if not file_path.exists():
            available = self.list_available_profiles()
            raise FileNotFoundError(
                f"Profile '{profile_name}' not found. "
                f"Available profiles: {', '.join(available)}"
            )

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # Validate required fields
            required_fields = [
                "max_flight_price_family",
                "max_flight_price_parents",
                "max_total_budget_family",
            ]

            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            logger.info(f"Loaded preference profile: {profile_name}")
            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in profile {profile_name}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading profile {profile_name}: {e}")

    def create_user_preference(self, profile_data: Dict) -> UserPreference:
        """
        Create a UserPreference object from profile data.

        Args:
            profile_data: Dictionary with preference data

        Returns:
            UserPreference object (not yet saved to database)
        """
        # Extract and convert data
        user_pref = UserPreference(
            user_id=profile_data.get("user_id", 1),
            max_flight_price_family=float(profile_data["max_flight_price_family"]),
            max_flight_price_parents=float(profile_data["max_flight_price_parents"]),
            max_total_budget_family=float(profile_data["max_total_budget_family"]),
            preferred_destinations=profile_data.get("preferred_destinations"),
            avoid_destinations=profile_data.get("avoid_destinations"),
            interests=profile_data.get("interests"),
            notification_threshold=float(
                profile_data.get("notification_threshold", 70.0)
            ),
            parent_escape_frequency=profile_data.get(
                "parent_escape_frequency", "quarterly"
            ),
        )

        return user_pref

    def load_profile(self, profile_name: str) -> UserPreference:
        """
        Load a preference profile and create UserPreference object.

        Args:
            profile_name: Name of the profile to load

        Returns:
            UserPreference object (not yet saved to database)
        """
        profile_data = self.load_profile_data(profile_name)
        return self.create_user_preference(profile_data)

    def save_profile_to_db(
        self, profile_name: str, db: Session, user_id: Optional[int] = None
    ) -> UserPreference:
        """
        Load a preference profile and save it to the database (sync).

        Args:
            profile_name: Name of the profile to load
            db: Database session (sync)
            user_id: Optional user ID override

        Returns:
            Saved UserPreference object
        """
        user_pref = self.load_profile(profile_name)

        if user_id is not None:
            user_pref.user_id = user_id

        # Check if user preference already exists for this user
        existing = (
            db.query(UserPreference)
            .filter(UserPreference.user_id == user_pref.user_id)
            .first()
        )

        if existing:
            # Update existing preference
            for key, value in user_pref.__dict__.items():
                if not key.startswith("_") and key != "id":
                    setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            logger.info(
                f"Updated user preference for user {user_pref.user_id} "
                f"with profile {profile_name}"
            )
            return existing
        else:
            # Create new preference
            db.add(user_pref)
            db.commit()
            db.refresh(user_pref)
            logger.info(
                f"Created user preference for user {user_pref.user_id} "
                f"with profile {profile_name}"
            )
            return user_pref

    async def save_profile_to_db_async(
        self, profile_name: str, db: AsyncSession, user_id: Optional[int] = None
    ) -> UserPreference:
        """
        Load a preference profile and save it to the database (async).

        Args:
            profile_name: Name of the profile to load
            db: Database session (async)
            user_id: Optional user ID override

        Returns:
            Saved UserPreference object
        """
        from sqlalchemy import select

        user_pref = self.load_profile(profile_name)

        if user_id is not None:
            user_pref.user_id = user_id

        # Check if user preference already exists for this user
        result = await db.execute(
            select(UserPreference).where(UserPreference.user_id == user_pref.user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing preference
            for key, value in user_pref.__dict__.items():
                if not key.startswith("_") and key != "id":
                    setattr(existing, key, value)
            await db.commit()
            await db.refresh(existing)
            logger.info(
                f"Updated user preference for user {user_pref.user_id} "
                f"with profile {profile_name}"
            )
            return existing
        else:
            # Create new preference
            db.add(user_pref)
            await db.commit()
            await db.refresh(user_pref)
            logger.info(
                f"Created user preference for user {user_pref.user_id} "
                f"with profile {profile_name}"
            )
            return user_pref

    def get_profile_description(self, profile_name: str) -> str:
        """
        Get the description of a preference profile.

        Args:
            profile_name: Name of the profile

        Returns:
            Profile description string
        """
        try:
            data = self.load_profile_data(profile_name)
            return data.get("description", "No description available")
        except Exception:
            return "Profile not found"
