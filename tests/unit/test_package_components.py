"""
Unit tests for the TripPackage components seam.

The regression these exist for: ``flights_json`` carried three incompatible
shapes, and ``DealScorer`` crashed with
``AttributeError: 'int' object has no attribute 'get'`` on every package the
main pipeline produced. Reading through this module must handle every
historical shape without raising.
"""

import pytest

from app.domain.package_components import (
    TRAVEL_METHOD_CAR,
    TRAVEL_METHOD_FLIGHT,
    TRAVEL_METHOD_TRAIN,
    PackageFlights,
    build_alternative_travel_components,
    build_flight_components,
    describe_flight,
    empty_components,
    read_flight_components,
)

pytestmark = pytest.mark.unit


class _FakeAirport:
    def __init__(self, iata_code):
        self.iata_code = iata_code


class _FakeFlight:
    def __init__(self, id=None, origin="MUC", destination="LIS", airline="TAP"):
        self.id = id
        self.origin_airport = _FakeAirport(origin)
        self.destination_airport = _FakeAirport(destination)
        self.airline = airline


class TestBuildFlightComponents:
    def test_stores_flight_ids(self):
        payload = build_flight_components([_FakeFlight(id=4)])
        assert payload["flight_ids"] == [4]
        assert payload["travel_method"] == TRAVEL_METHOD_FLIGHT

    def test_stores_several_ids_in_order(self):
        payload = build_flight_components([_FakeFlight(id=7), _FakeFlight(id=3)])
        assert payload["flight_ids"] == [7, 3]

    def test_unpersisted_flight_is_rejected(self):
        """A package referencing a flight with no id would reference nothing."""
        with pytest.raises(ValueError, match="unpersisted"):
            build_flight_components([_FakeFlight(id=None)])

    def test_empty_list_is_allowed(self):
        assert build_flight_components([])["flight_ids"] == []


class TestBuildAlternativeTravel:
    def test_train_keeps_details(self):
        payload = build_alternative_travel_components(
            TRAVEL_METHOD_TRAIN, {"country": "Italy"}
        )
        assert payload["travel_method"] == TRAVEL_METHOD_TRAIN
        assert payload["details"]["country"] == "Italy"
        assert payload["flight_ids"] == []

    def test_details_default_to_empty(self):
        payload = build_alternative_travel_components(TRAVEL_METHOD_CAR)
        assert payload["details"] == {}


class TestRoundTrip:
    def test_flight_components_round_trip(self):
        payload = build_flight_components([_FakeFlight(id=11)])
        components = read_flight_components(payload)
        assert components.flight_ids == (11,)
        assert components.is_flight

    def test_train_components_round_trip(self):
        payload = build_alternative_travel_components(
            TRAVEL_METHOD_TRAIN, {"country": "Austria"}
        )
        components = read_flight_components(payload)
        assert components.travel_method == TRAVEL_METHOD_TRAIN
        assert components.details["country"] == "Austria"
        assert not components.is_flight

    def test_empty_components_round_trip(self):
        components = read_flight_components(empty_components())
        assert components.flight_ids == ()


class TestLegacyListOfIds:
    """The shape AccommodationMatcher wrote: `[flight.id]`."""

    def test_list_of_ints_is_read_as_ids(self):
        components = read_flight_components([4])
        assert components.flight_ids == (4,)
        assert components.is_flight

    def test_several_ids(self):
        assert read_flight_components([4, 9]).flight_ids == (4, 9)

    def test_numeric_strings_are_coerced(self):
        assert read_flight_components(["4"]).flight_ids == (4,)

    def test_booleans_are_not_treated_as_ids(self):
        """bool is a subclass of int; True must not become id 1."""
        assert read_flight_components([True, False]).flight_ids == ()


class TestLegacyDictShapes:
    """The shape ParentEscapeAnalyzer wrote, and bare snapshots."""

    def test_travel_method_envelope(self):
        components = read_flight_components(
            {"travel_method": "train", "details": {"country": "Italy"}}
        )
        assert components.travel_method == "train"
        assert components.details["country"] == "Italy"

    def test_bare_flight_snapshot_is_kept(self):
        components = read_flight_components(
            {"price_per_person": 120.0, "origin_airport": "MUC", "airline": "TAP"}
        )
        assert components.snapshot["price_per_person"] == 120.0
        assert components.is_flight

    def test_snapshot_id_is_extracted(self):
        components = read_flight_components(
            {"id": 42, "price_per_person": 99.0}
        )
        assert components.flight_ids == (42,)

    def test_list_of_snapshots(self):
        components = read_flight_components(
            [{"id": 5, "price_per_person": 80.0, "airline": "Ryanair"}]
        )
        assert components.flight_ids == (5,)
        assert components.snapshot["airline"] == "Ryanair"

    def test_unrecognised_mapping_is_preserved_as_details(self):
        components = read_flight_components({"something": "else"})
        assert components.details["something"] == "else"


class TestMalformedInputNeverRaises:
    """A reporting path must not crash on one bad row."""

    @pytest.mark.parametrize(
        "raw", [None, {}, [], "garbage", 17, 3.5, object()]
    )
    def test_does_not_raise(self, raw):
        components = read_flight_components(raw)
        assert isinstance(components, PackageFlights)

    def test_empty_values_give_no_ids(self):
        for raw in (None, {}, []):
            assert read_flight_components(raw).flight_ids == ()


class TestDescribeFlight:
    def test_prefers_the_resolved_flight(self):
        text = describe_flight(
            _FakeFlight(id=1, origin="MUC", destination="BCN", airline="Vueling"),
            read_flight_components([1]),
        )
        assert text == "MUC → BCN via Vueling"

    def test_falls_back_to_snapshot(self):
        components = read_flight_components(
            {"origin_airport": "VIE", "destination_airport": "LIS", "airline": "TAP"}
        )
        assert describe_flight(None, components) == "VIE → LIS via TAP"

    def test_describes_train_travel(self):
        components = read_flight_components(
            build_alternative_travel_components(
                TRAVEL_METHOD_TRAIN, {"country": "Italy"}
            )
        )
        text = describe_flight(None, components)
        assert "train" in text
        assert "Italy" in text

    def test_handles_nothing_at_all(self):
        assert describe_flight(None, PackageFlights()) == (
            "Travel details not available"
        )


class TestPackageFlightsValueType:
    def test_defaults_are_a_flight_with_no_ids(self):
        components = PackageFlights()
        assert components.is_flight
        assert not components.has_ids

    def test_has_ids_reflects_content(self):
        assert PackageFlights(flight_ids=(1,)).has_ids

    def test_to_json_omits_empty_snapshot(self):
        assert "snapshot" not in PackageFlights().to_json()

    def test_to_json_includes_snapshot_when_present(self):
        payload = PackageFlights(snapshot={"airline": "TAP"}).to_json()
        assert payload["snapshot"]["airline"] == "TAP"
