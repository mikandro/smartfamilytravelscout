"""
Starter list of family places in and around Munich.

IMPORTANT: this is a hand-written starting point, not verified data. Travel
times are rough one-way estimates from Marienplatz in light traffic, costs are
rough entry prices for 2 adults + 2 children, and coordinates are approximate.
Check a place's website before relying on any of it, and correct entries as
you learn better (``seed_places`` never overwrites rows that already exist
unless ``update=True``).

Transit times are only given for places reachable by S-Bahn, U-Bahn or tram
with a walk a 3-year-old can manage. Places that need a regional train are
listed as car only on purpose.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.place import Place

logger = logging.getLogger(__name__)

SUMMER = [5, 6, 7, 8, 9]
APRIL_TO_OCTOBER = [4, 5, 6, 7, 8, 9, 10]


def _place(
    slug: str,
    name: str,
    category: str,
    setting: str,
    lat: float,
    lon: float,
    drive: int,
    *,
    transit: int | None = None,
    transit_note: str | None = None,
    age_min: int = 0,
    age_max: int | None = None,
    stroller: bool = True,
    hours: float = 2.0,
    cost: int | None = 0,
    booking: bool = False,
    months: List[int] | None = None,
    notes: str = "",
    url: str | None = None,
) -> Dict[str, Any]:
    return {
        "slug": slug,
        "name": name,
        "category": category,
        "setting": setting,
        "latitude": lat,
        "longitude": lon,
        "drive_minutes": drive,
        "transit_minutes": transit,
        "transit_note": transit_note,
        "age_min": age_min,
        "age_max": age_max,
        "stroller_friendly": stroller,
        "duration_hours": hours,
        "cost_family_eur": cost,
        "booking_required": booking,
        "months_open": months,
        "notes": notes,
        "url": url,
    }


PLACES: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------ #
    # In the city: indoor
    # ------------------------------------------------------------------ #
    _place(
        "deutsches-museum",
        "Deutsches Museum (with Kinderreich)",
        "museum",
        "indoor",
        48.1299,
        11.5834,
        10,
        transit=10,
        transit_note="S-Bahn Isartor, 8 min walk",
        age_min=3,
        hours=3,
        cost=31,
        notes="The Kinderreich is built for ages 3-8, so both kids play at once; the "
        "7-year-old can also do ships, planes and the mine. Tickets online save queueing.",
        url="https://www.deutsches-museum.de",
    ),
    _place(
        "verkehrszentrum",
        "Deutsches Museum Verkehrszentrum",
        "museum",
        "indoor",
        48.1327,
        11.5440,
        12,
        transit=12,
        transit_note="U4/U5 Schwanthalerhöhe",
        age_min=2,
        hours=2,
        cost=16,
        notes="Halls of trains, trams and cars with room to roam; smaller and calmer "
        "than the main museum, easy with a 3-year-old.",
        url="https://www.deutsches-museum.de/verkehrszentrum",
    ),
    _place(
        "flugwerft-schleissheim",
        "Flugwerft Schleißheim",
        "museum",
        "indoor",
        48.2460,
        11.5570,
        25,
        transit=35,
        transit_note="S1 Oberschleißheim, 15 min walk",
        age_min=3,
        hours=2,
        cost=16,
        notes="Aircraft hangars on an old airfield; planes and helicopters up close "
        "for the 7-year-old, lots of space for the 3-year-old.",
        url="https://www.deutsches-museum.de/flugwerft-schleissheim",
    ),
    _place(
        "sea-life",
        "Sea Life München",
        "aquarium",
        "indoor",
        48.1745,
        11.5560,
        15,
        transit=20,
        transit_note="U3 Olympiazentrum, 10 min walk",
        age_min=2,
        hours=1.5,
        cost=70,
        booking=True,
        notes="Short, dark and calm: good for a rainy morning. Book a time slot "
        "online; it is cheaper and weekends fill up.",
    ),
    _place(
        "bmw-welt",
        "BMW Welt",
        "showroom",
        "indoor",
        48.1771,
        11.5562,
        15,
        transit=15,
        transit_note="U3 Olympiazentrum",
        age_min=3,
        hours=1.5,
        cost=0,
        notes="Free. Kids can sit in cars and on motorbikes; combine with a run "
        "around the Olympiapark if the rain stops.",
    ),
    _place(
        "spielzeugmuseum",
        "Spielzeugmuseum (Altes Rathaus)",
        "museum",
        "indoor",
        48.1366,
        11.5770,
        10,
        transit=5,
        transit_note="S/U Marienplatz",
        age_min=3,
        stroller=False,
        hours=1,
        cost=12,
        notes="Small toy museum up a tower staircase: a one-hour stop, leave the "
        "stroller at home. Works as an add-on to a city-centre trip.",
    ),
    _place(
        "jagd-und-fischereimuseum",
        "Deutsches Jagd- und Fischereimuseum",
        "museum",
        "indoor",
        48.1385,
        11.5715,
        10,
        transit=5,
        transit_note="S/U Marienplatz or Karlsplatz",
        age_min=3,
        hours=1.5,
        cost=12,
        notes="Stuffed animals at child height and a kids' trail; quiet even on wet "
        "weekends and right in the pedestrian zone.",
    ),
    _place(
        "kinderkunsthaus",
        "Kinderkunsthaus",
        "creative",
        "indoor",
        48.1620,
        11.5770,
        12,
        transit=15,
        transit_note="U3/U6 Münchner Freiheit, 8 min walk",
        age_min=2,
        age_max=12,
        hours=2,
        cost=20,
        notes="Open workshop: painting, building, printing. Both kids make their own "
        "thing side by side. Check the opening times before going.",
    ),
    _place(
        "cosimawellenbad",
        "Cosimawellenbad",
        "pool",
        "indoor",
        48.1528,
        11.6290,
        15,
        transit=20,
        transit_note="U4 Arabellapark, 10 min walk",
        age_min=2,
        hours=2.5,
        cost=20,
        notes="Wave pool: big hit with a 7-year-old, with a shallow area for the "
        "little one. Bring swim aids for the 3-year-old.",
    ),
    _place(
        "westbad",
        "Westbad",
        "pool",
        "indoor",
        48.1437,
        11.4720,
        20,
        transit=25,
        transit_note="Tram 19 Westbad",
        age_min=1,
        hours=2.5,
        cost=20,
        notes="Family pool with slide and toddler area; outdoor pools in summer.",
    ),
    # ------------------------------------------------------------------ #
    # In the city: outdoor and mixed
    # ------------------------------------------------------------------ #
    _place(
        "tierpark-hellabrunn",
        "Tierpark Hellabrunn",
        "zoo",
        "mixed",
        48.0975,
        11.5540,
        15,
        transit=20,
        transit_note="U3 Thalkirchen, 5 min walk",
        hours=3.5,
        cost=50,
        notes="Works in any season: animal houses to warm up in, petting zoo for the "
        "3-year-old, big playgrounds for the 7-year-old. Bring or rent a wagon.",
        url="https://www.hellabrunn.de",
    ),
    _place(
        "botanischer-garten",
        "Botanischer Garten Nymphenburg",
        "garden",
        "mixed",
        48.1630,
        11.5010,
        20,
        transit=25,
        transit_note="Tram 17 Botanischer Garten",
        hours=2,
        cost=12,
        notes="The tropical greenhouses are a warm escape on a cold day (turtles and "
        "fish to spot); the gardens are best from April to October.",
    ),
    _place(
        "schlosspark-nymphenburg",
        "Schlosspark Nymphenburg",
        "park",
        "outdoor",
        48.1583,
        11.5033,
        20,
        transit=25,
        transit_note="Tram 17 Schloss Nymphenburg",
        hours=2,
        cost=0,
        notes="Flat paths for scooter and balance bike, swans and ducks on the canal. "
        "Free; no playground inside the park.",
    ),
    _place(
        "hirschgarten",
        "Hirschgarten",
        "park",
        "outdoor",
        48.1500,
        11.5110,
        15,
        transit=15,
        transit_note="S-Bahn Hirschgarten, 10 min walk",
        hours=2.5,
        cost=0,
        notes="Deer enclosure, a large playground and a beer garden next to each "
        "other: lunch sorted while the kids play.",
    ),
    _place(
        "olympiapark",
        "Olympiapark",
        "park",
        "outdoor",
        48.1731,
        11.5466,
        15,
        transit=15,
        transit_note="U3 Olympiazentrum",
        hours=2.5,
        cost=0,
        notes="Climb the Olympiaberg for the view, playgrounds, lake with ducks. "
        "Good for scooters; exposed when windy.",
    ),
    _place(
        "westpark",
        "Westpark",
        "park",
        "outdoor",
        48.1228,
        11.5180,
        12,
        transit=15,
        transit_note="U6 Westpark",
        hours=2.5,
        cost=0,
        notes="Several big playgrounds including a water playground in summer, "
        "plus lakes and Asian gardens to walk between them.",
    ),
    _place(
        "englischer-garten",
        "Englischer Garten (Chinesischer Turm)",
        "park",
        "outdoor",
        48.1525,
        11.5920,
        12,
        transit=15,
        transit_note="U3/U6 Universität, 10 min walk",
        hours=2.5,
        cost=0,
        notes="Playground and old wooden carousel by the Chinesischer Turm (carousel "
        "in the warm months), streams to throw sticks in, surfers at the Eisbach.",
    ),
    _place(
        "riemer-park",
        "Riemer Park and Riemer See",
        "park",
        "outdoor",
        48.1250,
        11.7040,
        20,
        transit=25,
        transit_note="U2 Messestadt Ost, 10 min walk",
        hours=2.5,
        cost=0,
        notes="Huge playgrounds and wide paths for bikes; swimming lake with a "
        "shallow shore in summer. Little shade, so bring hats.",
    ),
    _place(
        "flaucher",
        "Isar at the Flaucher",
        "river",
        "outdoor",
        48.1080,
        11.5560,
        15,
        transit=20,
        transit_note="U3 Thalkirchen, 10 min walk",
        hours=2.5,
        cost=0,
        months=APRIL_TO_OCTOBER,
        notes="Gravel banks for throwing stones and paddling, playground and beer "
        "garden nearby. Keep the 3-year-old close to the shallow side channels.",
    ),
    _place(
        "feringasee",
        "Feringasee",
        "lake",
        "outdoor",
        48.1790,
        11.6680,
        20,
        hours=3,
        cost=0,
        months=SUMMER,
        notes="Swimming lake with shallow entry, lawns and a playground. Parking "
        "fills by late morning on hot days.",
    ),
    # ------------------------------------------------------------------ #
    # On the S-Bahn
    # ------------------------------------------------------------------ #
    _place(
        "wildpark-poing",
        "Wildpark Poing",
        "wildlife park",
        "outdoor",
        48.1660,
        11.8290,
        30,
        transit=35,
        transit_note="S2 Poing, 15 min walk",
        hours=3,
        cost=40,
        notes="Deer eat from the kids' hands, the loop is stroller-friendly and "
        "there is a big playground halfway. Open all year; wrap up in winter.",
        url="https://www.wildpark-poing.de",
    ),
    _place(
        "therme-erding",
        "Therme Erding",
        "water park",
        "indoor",
        48.2930,
        11.8870,
        40,
        transit=45,
        transit_note="S2 Altenerding, 15 min walk",
        age_min=1,
        hours=4,
        cost=130,
        booking=True,
        notes="Slides for the 7-year-old (some have height limits), warm toddler "
        "pools for the 3-year-old. Book online: rainy weekends sell out.",
        url="https://www.therme-erding.de",
    ),
    _place(
        "starnberger-see",
        "Starnberger See (Starnberg promenade)",
        "lake",
        "outdoor",
        47.9990,
        11.3410,
        35,
        transit=35,
        transit_note="S6 Starnberg, lake is at the station",
        hours=3,
        cost=0,
        notes="Promenade walk with mountain view, ducks, playground and ice cream; "
        "boat trips in the warm months. Easiest lake to reach by S-Bahn.",
    ),
    _place(
        "ammersee-herrsching",
        "Ammersee (Herrsching)",
        "lake",
        "outdoor",
        47.9990,
        11.1700,
        45,
        transit=50,
        transit_note="S8 Herrsching, 5 min walk",
        hours=3,
        cost=0,
        notes="Long flat lakeside promenade with playgrounds; steamer trips in the "
        "warm months. Skip the walk up to Andechs with a 3-year-old.",
    ),
    _place(
        "woerthsee",
        "Wörthsee",
        "lake",
        "outdoor",
        48.0580,
        11.1900,
        35,
        transit=45,
        transit_note="S8 Steinebach, 10 min walk",
        hours=3,
        cost=10,
        months=SUMMER,
        notes="Warm, clear swimming lake with shallow bathing lawns (small entry "
        "fee at the lidos).",
    ),
    _place(
        "besucherpark-flughafen",
        "Besucherpark Flughafen München",
        "airport",
        "outdoor",
        48.3520,
        11.7640,
        35,
        transit=40,
        transit_note="S1/S8 Besucherpark",
        hours=2,
        cost=5,
        notes="Viewing hill to watch planes land, historic aircraft to climb into "
        "and a playground. Windy and exposed, so pick a dry day.",
    ),
    _place(
        "maerchenwald-isartal",
        "Märchenwald im Isartal",
        "amusement park",
        "outdoor",
        47.9280,
        11.4270,
        40,
        age_min=2,
        age_max=10,
        hours=4,
        cost=60,
        months=APRIL_TO_OCTOBER,
        notes="Fairy-tale scenes and gentle rides sized for small children; the "
        "7-year-old still gets the faster rides. Closed in winter.",
    ),
    # ------------------------------------------------------------------ #
    # By car
    # ------------------------------------------------------------------ #
    _place(
        "walderlebniszentrum-gruenwald",
        "Walderlebniszentrum Grünwald",
        "forest",
        "outdoor",
        48.0330,
        11.5200,
        30,
        hours=2.5,
        cost=0,
        notes="Short forest discovery trails, a wild boar enclosure and a nature "
        "playground. Free; bring a picnic and wellies after rain.",
    ),
    _place(
        "bergtierpark-blindham",
        "Bergtierpark Blindham",
        "wildlife park",
        "outdoor",
        47.9400,
        11.8300,
        40,
        hours=3,
        cost=25,
        months=APRIL_TO_OCTOBER,
        notes="Small hillside animal park with goats to feed and a very large "
        "playground with mountain views.",
    ),
    _place(
        "tegernsee",
        "Tegernsee",
        "lake",
        "outdoor",
        47.7080,
        11.7560,
        55,
        hours=4,
        cost=0,
        notes="Flat lakeside paths, playgrounds and boat trips with the Alps behind. "
        "Leave early: the road back is slow on sunny Sunday afternoons.",
    ),
    _place(
        "schliersee",
        "Schliersee",
        "lake",
        "outdoor",
        47.7360,
        11.8600,
        55,
        hours=4,
        cost=0,
        notes="Smaller and quieter than Tegernsee, with a lakeside playground and an "
        "easy path along the shore.",
    ),
    _place(
        "wasmeier-freilichtmuseum",
        "Markus Wasmeier Freilichtmuseum",
        "open-air museum",
        "outdoor",
        47.7200,
        11.8650,
        60,
        age_min=2,
        hours=3,
        cost=30,
        months=APRIL_TO_OCTOBER,
        notes="Old farmhouses, animals and craft demonstrations in a compact village: "
        "short distances for the 3-year-old, plenty to try for the 7-year-old.",
    ),
    _place(
        "blomberg",
        "Blomberg (Bad Tölz)",
        "mountain",
        "outdoor",
        47.7450,
        11.5050,
        55,
        age_min=3,
        stroller=False,
        hours=3.5,
        cost=40,
        months=APRIL_TO_OCTOBER,
        notes="Chairlift up and a summer toboggan run (small children ride with an "
        "adult). The run closes in wet weather, so check before driving.",
    ),
    _place(
        "freilichtmuseum-glentleiten",
        "Freilichtmuseum Glentleiten",
        "open-air museum",
        "outdoor",
        47.6640,
        11.2860,
        60,
        age_min=2,
        hours=3.5,
        cost=20,
        months=APRIL_TO_OCTOBER,
        notes="Large open-air museum above the Kochelsee with farm animals, a water "
        "playground and hands-on stations. Hilly: bring the carrier or a sturdy buggy.",
    ),
    _place(
        "zoo-augsburg",
        "Zoo Augsburg",
        "zoo",
        "mixed",
        48.3470,
        10.9160,
        60,
        hours=3.5,
        cost=40,
        notes="A change from Hellabrunn: compact, flat and less crowded, with good "
        "playgrounds. Open all year.",
    ),
    _place(
        "skyline-park",
        "Skyline Park",
        "amusement park",
        "outdoor",
        48.0170,
        10.6000,
        60,
        age_min=3,
        hours=5,
        cost=150,
        months=APRIL_TO_OCTOBER,
        notes="Rides for both ages (many are height-limited, so check the list for "
        "the 3-year-old). A full day; go on a dry day outside school holidays.",
    ),
    _place(
        "legoland",
        "Legoland Deutschland",
        "amusement park",
        "outdoor",
        48.4240,
        10.2980,
        80,
        age_min=2,
        age_max=12,
        hours=6,
        cost=200,
        booking=True,
        months=APRIL_TO_OCTOBER,
        notes="Ideal for exactly these ages but a long day with a long drive. Dated "
        "online tickets are much cheaper.",
    ),
    _place(
        "bavaria-filmstadt",
        "Bavaria Filmstadt",
        "studio tour",
        "mixed",
        48.0670,
        11.5540,
        25,
        transit=35,
        transit_note="Tram 25 Bavariafilmplatz",
        age_min=6,
        hours=2.5,
        cost=80,
        booking=True,
        notes="Guided 90-minute studio tour: great for a 7-year-old, too long for a "
        "3-year-old. One for when the younger one is older.",
    ),
]


def seed_places(db: Session, update: bool = False) -> Dict[str, int]:
    """
    Insert the starter places.

    Args:
        db: Sync database session (caller owns lifecycle; this commits).
        update: Also overwrite the fields of places that already exist. Off by
            default so manual corrections survive a re-seed.

    Returns:
        Counts: ``{"created": n, "updated": n, "skipped": n}``.
    """
    existing = {place.slug: place for place in db.query(Place).all()}
    counts = {"created": 0, "updated": 0, "skipped": 0}

    for data in PLACES:
        place = existing.get(data["slug"])
        if place is None:
            db.add(Place(**data, is_active=True))
            counts["created"] += 1
        elif update:
            for key, value in data.items():
                setattr(place, key, value)
            counts["updated"] += 1
        else:
            counts["skipped"] += 1

    db.commit()
    logger.info("Places seeded: %s", counts)
    return counts
