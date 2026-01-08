# Pull Request: Fix #45 - Replace hard-coded model pricing with database configuration

## Summary

This PR fixes issue #45 by replacing hard-coded Anthropic API pricing with a database-backed configuration system. This allows pricing updates to be made through configuration management rather than requiring code changes and redeployment.

## Changes Made

### 1. Database Schema
- **New Model**: Added `ModelPricing` model (`app/models/model_pricing.py`) to store pricing data with:
  - Service and model identifiers
  - Input and output costs per million tokens
  - Effective dates for historical tracking
  - Optional notes for documentation
- **Migration**: Created Alembic migration `2025_11_21_2219-2924c2c01a59_add_model_pricing_table.py`

### 2. ClaudeClient Updates
- Replaced hard-coded constants `INPUT_COST_PER_MILLION` and `OUTPUT_COST_PER_MILLION` with database-loaded values
- Added `DEFAULT_INPUT_COST_PER_MILLION` and `DEFAULT_OUTPUT_COST_PER_MILLION` as fallback values
- Implemented `_load_pricing()` method to fetch pricing from database
- Pricing is loaded lazily on first API call and cached for the instance lifetime
- Graceful fallback to defaults when:
  - No database session is provided
  - No pricing found in database
  - Database query fails

### 3. Seed Data
- Added `seed_model_pricing()` function to populate initial pricing data
- Includes pricing for current Claude models (Sonnet 4.5, 3.5 Sonnet, Opus, Haiku)
- Integrated into main `seed_all()` function

### 4. CLI Commands
Added two new commands under `scout db`:
- `scout db pricing-list` - List all pricing configurations with optional filters
- `scout db pricing-add` - Add or update model pricing with parameters:
  - `--service`: Service name (e.g., 'claude')
  - `--model`: Model name
  - `--input-cost`: Input cost per million tokens
  - `--output-cost`: Output cost per million tokens
  - `--effective-date`: When pricing becomes effective (optional, defaults to today)
  - `--notes`: Additional notes (optional)

### 5. Tests
Added comprehensive unit tests:
- `test_load_pricing_from_database` - Verifies pricing loads from database
- `test_load_pricing_fallback_to_defaults` - Verifies fallback behavior
- `test_load_pricing_without_db_session` - Tests behavior without DB session
- `test_track_cost_uses_loaded_pricing` - Ensures cost tracking uses loaded pricing

All new tests pass ✓

## Benefits

1. **No Code Changes for Pricing Updates**: When Anthropic changes pricing, simply run:
   ```bash
   scout db pricing-add --service claude --model claude-sonnet-4-5-20250929 \
     --input-cost 3.0 --output-cost 15.0 --effective-date 2025-12-01
   ```

2. **Historical Accuracy**: Historical cost data remains accurate because we preserve old pricing with effective dates

3. **Operational Flexibility**: Pricing can be updated by DevOps/operations without requiring developer intervention

4. **Backward Compatible**: If pricing isn't in database, system gracefully falls back to default values

5. **Audit Trail**: All pricing changes are tracked with effective dates and optional notes

## Usage Examples

### View current pricing
```bash
scout db pricing-list
scout db pricing-list --service claude
```

### Update pricing for new model version
```bash
scout db pricing-add --service claude \
  --model claude-sonnet-5-20260101 \
  --input-cost 4.0 \
  --output-cost 20.0 \
  --notes "New Sonnet 5 pricing"
```

### Historical pricing
Multiple pricing entries can exist for the same model with different effective dates. The system automatically uses the most recent pricing that has become effective.

## Migration Instructions

After merging this PR:

1. Run database migrations:
   ```bash
   poetry run alembic upgrade head
   ```

2. Seed pricing data:
   ```bash
   poetry run scout db seed
   ```

3. Verify pricing:
   ```bash
   scout db pricing-list
   ```

## Testing

- All existing tests continue to pass (with 3 pre-existing failures unrelated to this PR)
- New tests added for pricing functionality all pass
- Manual testing of CLI commands successful

## Files Changed

- `app/models/model_pricing.py` - New model for pricing configuration
- `app/models/__init__.py` - Added ModelPricing to exports
- `alembic/versions/2025_11_21_2219-2924c2c01a59_add_model_pricing_table.py` - Database migration
- `app/ai/claude_client.py` - Updated to load pricing from database
- `app/utils/seed_data.py` - Added pricing seed data
- `app/cli/main.py` - Added CLI commands for pricing management
- `tests/unit/test_claude_client.py` - Added tests for new functionality

## Closes

Fixes #45
