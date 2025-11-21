# API Versioning Strategy

## Overview

SmartFamilyTravelScout uses **URL-based versioning** for its REST API. This strategy ensures backward compatibility while allowing the API to evolve safely.

## Versioning Approach

### URL-Based Versioning

All API endpoints are prefixed with their version number:

```
/api/v1/...
/api/v2/... (future)
```

### Benefits

- **Clear and explicit**: Version is visible in the URL
- **Easy to use**: No special headers required
- **Cacheable**: Different versions can be cached independently
- **Browser-friendly**: Can be tested directly in browsers
- **Simple routing**: FastAPI handles routing based on URL prefix

## Current API Versions

### Version 1.0 (v1) - Stable

**Status**: Stable
**Prefix**: `/api/v1`
**Release Date**: November 2025

#### Available Endpoints

##### Version Information
- `GET /api/v1/version` - Get API version information

##### Health Check
- `GET /api/v1/health` - Check API and dependency health

##### Deals
- `GET /api/v1/deals` - List deals with optional filters
- `GET /api/v1/deals/{id}` - Get detailed deal information
- `GET /api/v1/deals/top/{limit}` - Get top-scored deals

##### Statistics
- `GET /api/v1/stats` - Get overall statistics
- `GET /api/v1/stats/destinations` - Get statistics by destination

## Usage Examples

### Discovering API Versions

```bash
# Get information about available API versions
curl http://localhost:8000/api

# Response:
{
  "name": "SmartFamilyTravelScout",
  "version": "0.1.0",
  "api_versions": {
    "v1": {
      "status": "stable",
      "prefix": "/api/v1",
      "endpoints": {
        "version": "/api/v1/version",
        "health": "/api/v1/health",
        "deals": "/api/v1/deals",
        "stats": "/api/v1/stats"
      }
    }
  }
}
```

### Using v1 API

```bash
# Get version information
curl http://localhost:8000/api/v1/version

# Get health status
curl http://localhost:8000/api/v1/health

# List deals
curl http://localhost:8000/api/v1/deals

# Filter deals
curl "http://localhost:8000/api/v1/deals?min_score=70&destination=Barcelona"

# Get specific deal
curl http://localhost:8000/api/v1/deals/123

# Get top 10 deals
curl http://localhost:8000/api/v1/deals/top/10

# Get statistics
curl http://localhost:8000/api/v1/stats

# Get destination statistics
curl http://localhost:8000/api/v1/stats/destinations?limit=5
```

## Deprecation Policy

When introducing breaking changes:

1. **New version is released** (e.g., v2) with the changes
2. **Old version remains available** for at least 6 months
3. **Deprecation notice** is added to old version responses
4. **Documentation** is updated with migration guide
5. **Sunset date** is announced at least 3 months in advance

### Example Deprecation Response

```json
{
  "data": { ... },
  "deprecated": true,
  "deprecation_notice": "API v1 will be sunset on 2026-06-01. Please migrate to v2.",
  "migration_guide": "https://docs.example.com/api/migration/v1-to-v2"
}
```

## Future Versions

### Version 2.0 (v2) - Planned

When v2 is needed, it will be added with:
- New prefix: `/api/v2`
- Backwards-incompatible changes (if any)
- Migration guide from v1 to v2
- Both v1 and v2 running in parallel

## API Stability Guarantees

### Stable Versions

- No breaking changes
- Only additive changes (new optional fields, new endpoints)
- Bug fixes that don't change behavior
- Performance improvements

### Breaking Changes Examples

These require a new version:
- Removing endpoints
- Removing response fields
- Changing response structure
- Changing authentication requirements
- Renaming fields

### Non-Breaking Changes Examples

These can be added to existing versions:
- Adding new endpoints
- Adding new optional query parameters
- Adding new optional response fields
- Expanding allowed values for parameters

## Implementation Details

### FastAPI Router Structure

```python
# app/api/routes/v1/__init__.py
from fastapi import APIRouter
from app.api.routes.v1 import deals, stats, version, health

router = APIRouter()
router.include_router(version.router, prefix="/version", tags=["Version"])
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(deals.router, prefix="/deals", tags=["Deals"])
router.include_router(stats.router, prefix="/stats", tags=["Statistics"])

# app/api/main.py
from app.api.routes.v1 import router as v1_router
app.include_router(v1_router, prefix="/api/v1", tags=["API v1"])
```

### Adding New Versions

To add a new API version:

1. Create new directory: `app/api/routes/v2/`
2. Copy and modify endpoints from v1
3. Create v2 router: `app/api/routes/v2/__init__.py`
4. Include in main.py: `app.include_router(v2_router, prefix="/api/v2")`
5. Update `/api` root endpoint with v2 info
6. Add tests in `tests/unit/test_api_v2.py`
7. Update documentation

## Testing

All API versions have comprehensive test coverage:

```bash
# Run v1 API tests
poetry run pytest tests/unit/test_api_v1.py -v

# Run all API tests
poetry run pytest tests/unit/test_api_*.py -v
```

## OpenAPI Documentation

Each version is documented in the auto-generated OpenAPI spec:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

The documentation automatically groups endpoints by version using tags.

## Migration Between Versions

When a new version is released, a migration guide will be provided showing:

1. What changed between versions
2. How to update client code
3. New features available
4. Deprecated features to avoid

## References

- [FastAPI Versioning Best Practices](https://fastapi.tiangolo.com/advanced/custom-request-and-route/)
- [REST API Versioning Strategies](https://www.baeldung.com/rest-versioning)
- Issue #55: API Versioning Strategy Implementation
