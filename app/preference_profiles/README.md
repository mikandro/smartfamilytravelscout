# User Preference Profiles

This directory contains predefined user preference profiles that can be loaded to personalize travel deal recommendations.

## Available Profiles

### family-with-toddlers
Perfect for families with young children (ages 0-5). Focuses on:
- Family-friendly destinations with beaches, parks, and playgrounds
- Lower budget constraints (€150 max per person)
- Avoids expensive cities like Paris and London
- Interests: beaches, parks, aquariums, family attractions

### budget-conscious
For families looking for the best deals with strict budget constraints. Features:
- Very low budget (€100 max per person)
- Focuses on affordable Eastern European destinations
- Avoids expensive Nordic and Swiss cities
- Interests: free attractions, city walks, local markets

### beach-lovers
For families who love sun, sand, and sea. Includes:
- Mediterranean and coastal destinations preferred
- Moderate budget (€180 max per person)
- Interests: beaches, swimming, water sports, seafood

### culture-lovers
For families who enjoy museums, historical sites, and cultural experiences. Features:
- Historical European cities preferred (Rome, Athens, Prague, Vienna)
- Moderate budget (€180 max per person)
- Interests: museums, historical sites, architecture, UNESCO sites

### adventure-family
For active families who love outdoor activities. Includes:
- Mountain and nature destinations (Reykjavik, Bergen, Alps)
- Higher budget (€200 max per person)
- Interests: hiking, mountains, skiing, adventure sports

## Using Preference Profiles

### Via CLI

#### List available profiles
```bash
poetry run scout prefs list
```

#### View profile details
```bash
poetry run scout prefs show family-with-toddlers
```

#### Load a profile into database
```bash
poetry run scout prefs load family-with-toddlers
```

#### View current preferences
```bash
poetry run scout prefs current
```

#### Get deals with a specific profile
```bash
poetry run scout deals --profile family-with-toddlers --min-score 75
```

### Programmatically

```python
from app.utils.preference_loader import PreferenceLoader
from app.ai.deal_scorer import DealScorer

# Load a profile
loader = PreferenceLoader()
user_prefs = loader.load_profile("beach-lovers")

# Use with deal scorer
scorer = DealScorer(claude_client, db_session)
result = await scorer.score_package(
    package=trip_package,
    user_prefs=user_prefs
)
```

## Creating Custom Profiles

Create a new JSON file in this directory with the following structure:

```json
{
  "name": "Your Profile Name",
  "description": "Description of this profile",
  "user_id": 1,
  "max_flight_price_family": 150.0,
  "max_flight_price_parents": 300.0,
  "max_total_budget_family": 2000.0,
  "preferred_destinations": [
    "Barcelona",
    "Lisbon"
  ],
  "avoid_destinations": [
    "Paris"
  ],
  "interests": [
    "beaches",
    "museums"
  ],
  "notification_threshold": 75.0,
  "parent_escape_frequency": "quarterly"
}
```

### Field Descriptions

- **name**: Human-readable name for the profile
- **description**: Brief description of who this profile is for
- **user_id**: User ID to associate with (default: 1)
- **max_flight_price_family**: Maximum acceptable flight price per person for family trips (EUR)
- **max_flight_price_parents**: Maximum flight price per person for parent-only trips (EUR)
- **max_total_budget_family**: Maximum total budget for family trips including flights + accommodation (EUR)
- **preferred_destinations**: Array of preferred city names
- **avoid_destinations**: Array of cities to avoid
- **interests**: Array of interest keywords (used by AI for matching)
- **notification_threshold**: Minimum AI score (0-100) to trigger notifications
- **parent_escape_frequency**: How often to suggest parent trips ("monthly", "quarterly", "semi-annual")

## How Preferences Affect Scoring

When using preference-based scoring:

1. **Budget Filtering**: Packages exceeding `max_flight_price_family` or `max_total_budget_family` are automatically filtered out

2. **Destination Filtering**:
   - Destinations in `avoid_destinations` receive very low scores (10/100)
   - Destinations in `preferred_destinations` receive score boosts

3. **Interest Matching**: The AI considers your interests when scoring:
   - Destinations with activities matching your interests get higher scores
   - The `preference_alignment` score (0-10) indicates how well the destination matches

4. **Personalized Recommendations**:
   - "book_now": Exceptional match for your preferences
   - "wait": Partial match or might get better
   - "skip": Doesn't match preferences or in avoid list

## Examples

See `examples/preference_scoring_example.py` for complete usage examples including:
- Loading and comparing different profiles
- Scoring packages with preferences
- Filtering packages based on preferences
- Comparing how different profiles score the same destination
