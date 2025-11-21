## Summary

Implements issue #70 by adding user preference-based scoring to the AI deal analysis workflow. Users can now get personalized travel recommendations that match their specific budget constraints, interests, and destination preferences.

## Problem Solved

Previously, all users received identical recommendations regardless of their preferences. The `UserPreference` model existed but was unused in the scoring logic, making personalization impossible.

## Solution Implemented

### 1. Core Scoring Function
- Added `score_package()` async method to `DealScorer` class
- Accepts `TripPackage` and `UserPreference` parameters
- Filters packages by user's budget constraints before AI analysis
- Automatically rejects destinations in user's avoid list
- Uses new preference-aware prompt template for AI scoring

### 2. Preference Profiles System
Created 5 predefined profiles users can load:
- **family-with-toddlers**: €150/person max, beach/park focus, avoids expensive cities
- **budget-conscious**: €100/person max, Eastern Europe focus
- **beach-lovers**: €180/person, Mediterranean destinations
- **culture-lovers**: €180/person, museums and historical sites
- **adventure-family**: €200/person, hiking and outdoor activities

### 3. CLI Integration
New `scout prefs` command group:
```bash
scout prefs list                    # Show available profiles
scout prefs show family-with-toddlers  # Display profile details
scout prefs load family-with-toddlers  # Save to database
scout prefs current                 # Show current preferences
```

Enhanced `scout deals` command:
```bash
scout deals --profile family-with-toddlers --min-score 75
```

### 4. AI Prompt Enhancement
- New `deal_analysis_with_preferences.txt` template
- Includes budget limits, interests, preferred/avoided destinations
- Returns `preference_alignment` score (0-10) showing match quality
- Reasoning explicitly mentions preference matching

## Files Changed

### New Files
- `app/ai/prompts/deal_analysis_with_preferences.txt` - Preference-aware AI prompt
- `app/utils/preference_loader.py` - Profile loading and management utility
- `app/preference_profiles/*.json` - 5 predefined preference profiles
- `app/preference_profiles/README.md` - Profile documentation
- `tests/unit/test_preference_scoring.py` - Comprehensive unit tests
- `examples/preference_scoring_example.py` - Usage examples

### Modified Files
- `app/ai/deal_scorer.py`:
  - Added `score_package()` method with preference support
  - Added `_build_prompt_data_with_preferences()` helper
  - Imported `UserPreference` model
- `app/cli/main.py`:
  - Added `prefs` command group with 4 subcommands
  - Enhanced `deals` command with `--profile` option
  - Added preference filtering in `_show_deals()`

## Testing

Comprehensive unit tests covering:
- UserPreference model properties
- PreferenceLoader profile loading and validation
- Budget filtering (flight price and total budget)
- Avoided destination filtering
- Prompt data building with preferences
- Profile data consistency checks

## Usage Examples

### Loading a Profile
```bash
scout prefs load beach-lovers
```

### Getting Personalized Deals
```bash
scout deals --profile budget-conscious --min-score 75
```

### Programmatic Usage
```python
from app.utils.preference_loader import PreferenceLoader
from app.ai.deal_scorer import DealScorer

loader = PreferenceLoader()
user_prefs = loader.load_profile("family-with-toddlers")

result = await scorer.score_package(
    package=trip_package,
    user_prefs=user_prefs
)

print(f"Score: {result['score']}/100")
print(f"Preference Match: {result['preference_alignment']}/10")
```

## Backward Compatibility

- Original `score_trip()` method unchanged
- Existing code continues to work without modifications
- CLI defaults to standard scoring if no profile specified
- No database schema changes required

## Benefits

1. **Personalization**: Each user gets recommendations tailored to their needs
2. **Budget Control**: Automatic filtering prevents over-budget suggestions
3. **Destination Preferences**: Boost preferred destinations, avoid unwanted ones
4. **Interest Matching**: AI considers user interests (beaches, museums, hiking, etc.)
5. **Flexible**: Load profiles dynamically or save to database for persistence

## Future Enhancements

Potential improvements for future PRs:
- Web UI for creating custom profiles
- Profile versioning and history
- Machine learning to auto-adjust preferences based on user behavior
- Shared/community preference profiles
- Multi-user preference comparison

## Resolves

Closes #70

## Checklist

- [x] Code follows project style guidelines
- [x] Added comprehensive unit tests
- [x] Added example scripts demonstrating usage
- [x] Updated CLI with new commands
- [x] Created documentation (README in profiles directory)
- [x] Backward compatible with existing code
- [x] No database migrations required
