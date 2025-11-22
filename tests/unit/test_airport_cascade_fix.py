"""
Unit tests for verifying the airport CASCADE to RESTRICT fix.
Tests that the foreign key constraints are properly configured.
"""

import pytest
from sqlalchemy import inspect

from app.models.airport import Airport
from app.models.flight import Flight


def test_flight_foreign_key_ondelete_is_restrict():
    """
    Verify that Flight model has RESTRICT constraint on airport foreign keys.
    This prevents accidental deletion of airports that have associated flights.
    """
    # Inspect the Flight model's foreign keys
    inspector = inspect(Flight)
    foreign_keys = inspector.mapper.mapped_table.foreign_keys

    # Find the airport foreign keys
    origin_fk = None
    destination_fk = None

    for fk in foreign_keys:
        if fk.parent.name == "origin_airport_id":
            origin_fk = fk
        elif fk.parent.name == "destination_airport_id":
            destination_fk = fk

    # Verify both foreign keys exist
    assert origin_fk is not None, "origin_airport_id foreign key not found"
    assert destination_fk is not None, "destination_airport_id foreign key not found"

    # Verify ondelete is RESTRICT (not CASCADE)
    assert origin_fk.ondelete == "RESTRICT", (
        f"origin_airport_id should have ondelete='RESTRICT', got '{origin_fk.ondelete}'"
    )
    assert destination_fk.ondelete == "RESTRICT", (
        f"destination_airport_id should have ondelete='RESTRICT', got '{destination_fk.ondelete}'"
    )


def test_airport_relationships_no_delete_orphan():
    """
    Verify that Airport model relationships don't have delete-orphan cascade.
    This prevents automatic deletion of flights when accessing airport relationships.
    """
    inspector = inspect(Airport)
    relationships = inspector.mapper.relationships

    # Check departing_flights relationship
    departing_rel = relationships.get("departing_flights")
    assert departing_rel is not None, "departing_flights relationship not found"

    # Check arriving_flights relationship
    arriving_rel = relationships.get("arriving_flights")
    assert arriving_rel is not None, "arriving_flights relationship not found"

    # Verify cascade settings don't include delete-orphan
    departing_cascade = str(departing_rel.cascade)
    arriving_cascade = str(arriving_rel.cascade)

    assert "delete-orphan" not in departing_cascade, (
        "departing_flights should not have delete-orphan cascade"
    )
    assert "delete-orphan" not in arriving_cascade, (
        "arriving_flights should not have delete-orphan cascade"
    )


def test_airport_has_associated_flights_property():
    """
    Verify that Airport model has the has_associated_flights property.
    This is used to check if an airport can be safely deleted.
    """
    # Verify the property exists
    assert hasattr(Airport, "has_associated_flights"), (
        "Airport should have has_associated_flights property"
    )

    # Verify it's a property (not a regular method)
    assert isinstance(
        getattr(Airport, "has_associated_flights"), property
    ), "has_associated_flights should be a property"


def test_airport_flight_count_property():
    """
    Verify that Airport model has the flight_count property.
    This provides visibility into how many flights are associated with an airport.
    """
    # Verify the property exists
    assert hasattr(Airport, "flight_count"), (
        "Airport should have flight_count property"
    )

    # Verify it's a property (not a regular method)
    assert isinstance(
        getattr(Airport, "flight_count"), property
    ), "flight_count should be a property"


def test_flight_foreign_keys_are_not_nullable():
    """
    Verify that airport foreign keys in Flight are still required (not nullable).
    This maintains referential integrity - flights must have valid airports.
    """
    inspector = inspect(Flight)
    columns = inspector.mapper.mapped_table.columns

    origin_col = columns.get("origin_airport_id")
    destination_col = columns.get("destination_airport_id")

    assert origin_col is not None, "origin_airport_id column not found"
    assert destination_col is not None, "destination_airport_id column not found"

    # Verify columns are NOT nullable
    assert not origin_col.nullable, (
        "origin_airport_id should not be nullable (must have origin airport)"
    )
    assert not destination_col.nullable, (
        "destination_airport_id should not be nullable (must have destination airport)"
    )
