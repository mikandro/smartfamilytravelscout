# Claude API Integration

Robust integration with Anthropic's Claude API for AI-powered travel analysis, deal scoring, and itinerary generation.

## Features

- ✅ **Caching Layer**: Redis-based response caching with configurable TTL
- ✅ **Cost Tracking**: Automatic tracking and logging of API costs to database
- ✅ **Error Handling**: Comprehensive error handling with retry logic for transient failures
- ✅ **JSON Parsing**: Intelligent parsing of JSON responses (handles markdown code blocks)
- ✅ **Prompt Management**: Template-based prompt system with variable substitution
- ✅ **Production-Ready**: Async/await support, connection pooling, monitoring

## Architecture

```
app/ai/
├── claude_client.py      # Main Claude API client
├── prompt_loader.py      # Prompt template management
├── prompts/              # Prompt template files
│   ├── deal_analysis.txt
│   ├── itinerary_generation.txt
│   ├── parent_escape_analysis.txt
│   └── event_scoring.txt
└── __init__.py

app/models/
└── api_cost.py           # Cost tracking model

tests/unit/
├── test_claude_client.py
└── test_prompt_loader.py

examples/
└── claude_integration_example.py
```

## Quick Start

### 1. Configuration

Add your Anthropic API key to `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### 2. Basic Usage

```python
from redis.asyncio import Redis
from app.ai import ClaudeClient
from app.config import settings
from app.database import AsyncSessionLocal

# Setup
redis = Redis.from_url(str(settings.redis_url))

async with AsyncSessionLocal() as db:
    # Initialize client
    client = ClaudeClient(
        api_key=settings.anthropic_api_key,
        redis_client=redis,
        db_session=db
    )

    # Analyze a deal
    result = await client.analyze(
        prompt="Score this travel deal on 0-100: {deal_details}",
        data={"deal_details": "Flight to Lisbon €400, Hotel €80/night"},
        response_format="json",
        operation="deal_scoring"
    )

    print(f"Score: {result['score']}/100")
    print(f"Cost: ${result['_cost']:.4f}")
    print(f"Tokens: {result['_tokens']['total']}")

await redis.close()
```

### 3. Using Prompt Templates

```python
from app.ai import load_prompt, ClaudeClient

# Load a predefined prompt template
prompt = load_prompt("deal_analysis")

# Use with client
result = await client.analyze(
    prompt=prompt,
    data={
        "deal_details": "Vienna to Barcelona, €300 for 4 people"
    },
    operation="deal_analysis"
)
```

## Core Components

### ClaudeClient

Main client for interacting with Claude API.

#### Key Methods

**`analyze(prompt, data, response_format='json', use_cache=True, ...)`**

Send a prompt to Claude and get parsed response.

- `prompt` (str): Prompt template with {variable} placeholders
- `data` (dict): Variables to format into prompt
- `response_format` (str): 'json' or 'text'
- `use_cache` (bool): Whether to use Redis caching
- `max_tokens` (int): Maximum response tokens (default: 2048)
- `operation` (str): Operation name for cost tracking
- `temperature` (float): Sampling temperature 0-1 (default: 1.0)

Returns: Dict with parsed response + `_cost`, `_model`, `_tokens` metadata

**`track_cost(input_tokens, output_tokens, operation, ...)`**

Calculate and log API costs to database.

**`clear_cache(pattern='claude:response:*')`**

Clear cached responses matching a pattern.

**`get_cache_stats()`**

Get cache statistics (count, TTL).

#### Configuration

```python
client = ClaudeClient(
    api_key="sk-ant-...",
    redis_client=redis,
    model="claude-sonnet-4-5-20250929",  # Default
    cache_ttl=86400,  # 24 hours (default)
    db_session=db_session  # Optional, for cost tracking
)
```

### PromptLoader

Manage prompt templates from files.

#### Key Methods

**`load(prompt_name, use_cache=True)`**

Load a prompt template from file.

**`save(prompt_name, prompt_content)`**

Save a new prompt template.

**`list_prompts()`**

List all available prompt templates.

**`validate_template(prompt_name, required_vars)`**

Validate that template contains required variables.

**`get_template_variables(prompt_name)`**

Extract all variables from a template.

#### Example

```python
from app.ai import PromptLoader

loader = PromptLoader()

# List available prompts
prompts = loader.list_prompts()
# ['deal_analysis', 'event_scoring', 'itinerary_generation', ...]

# Load a prompt
prompt = loader.load("deal_analysis")

# Get template variables
vars = loader.get_template_variables("deal_analysis")
# ['deal_details']

# Validate template
is_valid = loader.validate_template("deal_analysis", ["deal_details"])
```

## Prompt Templates

Prompt templates are stored in `app/ai/prompts/` as `.txt` files.

### Available Templates

1. **deal_analysis.txt**: Analyze and score travel deals
2. **itinerary_generation.txt**: Generate day-by-day family itineraries
3. **parent_escape_analysis.txt**: Analyze parent relaxation opportunities
4. **event_scoring.txt**: Score events for family-friendliness

### Creating Custom Prompts

Create a new file in `app/ai/prompts/`:

```text
# app/ai/prompts/my_custom_prompt.txt

You are analyzing {destination} for {travelers} travelers.
Budget: {budget}

Provide a detailed analysis in JSON format with:
- suitability_score (0-100)
- highlights (array)
- concerns (array)
- recommendation (string)
```

Use it:

```python
prompt = load_prompt("my_custom_prompt")
result = await client.analyze(
    prompt=prompt,
    data={
        "destination": "Rome",
        "travelers": 4,
        "budget": "€2000"
    }
)
```

## Cost Tracking

All API calls are automatically tracked in the `api_costs` table:

### Database Model

```python
class ApiCost(Base):
    service: str           # 'claude'
    model: str            # 'claude-sonnet-4-5-20250929'
    input_tokens: int     # Input token count
    output_tokens: int    # Output token count
    cost_usd: float       # Total cost in USD
    operation: str        # Operation type (e.g., 'deal_scoring')
    prompt_hash: str      # SHA256 hash for deduplication
    cache_hit: bool       # Whether response was cached
    error: str            # Error message if failed
    created_at: datetime
```

### Querying Costs

```python
from sqlalchemy import select, func
from app.models import ApiCost

# Total cost for today
today_cost = await db.execute(
    select(func.sum(ApiCost.cost_usd))
    .where(ApiCost.created_at >= date.today())
)

# Cost by operation
costs_by_op = await db.execute(
    select(
        ApiCost.operation,
        func.sum(ApiCost.cost_usd).label('total_cost'),
        func.sum(ApiCost.input_tokens + ApiCost.output_tokens).label('total_tokens')
    )
    .group_by(ApiCost.operation)
)
```

### Pricing (Claude Sonnet 4.5)

- **Input tokens**: $3.00 per 1M tokens
- **Output tokens**: $15.00 per 1M tokens

Example costs:
- 1000 input + 500 output tokens = $0.0105
- Typical deal analysis (200 in, 150 out) = ~$0.0028

## Caching

Redis-based caching reduces costs and improves performance.

### How It Works

1. **Cache Key Generation**: Hash of (model + format + max_tokens + prompt)
2. **Cache Check**: Before API call, check Redis
3. **Cache Store**: After successful call, store for TTL (default: 24h)
4. **Cache Hit Tracking**: Logged in database with `cache_hit=True`

### Cache Management

```python
# Clear all cached responses
deleted = await client.clear_cache()

# Clear specific pattern
deleted = await client.clear_cache("claude:response:abc*")

# Get cache statistics
stats = await client.get_cache_stats()
print(f"Cached responses: {stats['cached_responses']}")
```

### Benefits

- **Cost Savings**: Identical requests don't hit the API
- **Speed**: Cached responses return in ~10ms vs ~2000ms
- **Reliability**: Continue serving cached results during API outages

## Error Handling

Robust error handling with automatic retry logic.

### Automatic Retries

Transient failures (rate limits, connection errors) are automatically retried:

- **Max attempts**: 3
- **Backoff**: Exponential (2s, 4s, 8s)
- **Retry on**: `RateLimitError`, `APIConnectionError`

### Error Types

```python
from app.ai import ClaudeAPIError

try:
    result = await client.analyze(...)
except ClaudeAPIError as e:
    # All Claude-related errors are wrapped
    logger.error(f"Analysis failed: {e}")
```

### Error Tracking

Failed API calls are tracked in the database:

```python
# Check for recent errors
errors = await db.execute(
    select(ApiCost)
    .where(ApiCost.error.isnot(None))
    .order_by(ApiCost.created_at.desc())
    .limit(10)
)
```

## Testing

Comprehensive unit tests with mocked API responses.

### Run Tests

```bash
# Run all Claude integration tests
pytest tests/unit/test_claude_client.py -v

# Run prompt loader tests
pytest tests/unit/test_prompt_loader.py -v

# Run with coverage
pytest tests/unit/test_claude_client.py --cov=app.ai
```

### Test Coverage

- ✅ Cache hit/miss scenarios
- ✅ JSON parsing (plain, markdown wrapped)
- ✅ Cost calculation and tracking
- ✅ Error handling
- ✅ Retry logic
- ✅ Prompt template management
- ✅ Template validation

## Examples

See `examples/claude_integration_example.py` for comprehensive examples:

```bash
python examples/claude_integration_example.py
```

Includes:
1. Deal analysis
2. Event scoring
3. Caching demonstration
4. Custom analysis
5. Error handling

## Database Migration

Apply the migration to create the `api_costs` table:

```bash
alembic upgrade head
```

Or manually:

```sql
-- See alembic/versions/2025_11_16_1200-002_add_api_cost_tracking.py
```

## Performance Optimization

### Tips

1. **Use caching**: Enable for repeated queries
2. **Batch requests**: Group similar analyses
3. **Optimize prompts**: Shorter prompts = lower costs
4. **Adjust max_tokens**: Use minimum needed
5. **Monitor costs**: Regular database queries

### Monitoring

```python
# Daily cost report
daily_cost = await db.execute(
    select(
        func.date(ApiCost.created_at).label('date'),
        func.sum(ApiCost.cost_usd).label('cost'),
        func.count(ApiCost.id).label('calls')
    )
    .where(ApiCost.created_at >= datetime.now() - timedelta(days=7))
    .group_by(func.date(ApiCost.created_at))
)
```

## Best Practices

### 1. Always Set Operation Names

```python
# Good
await client.analyze(..., operation="deal_scoring")

# Bad
await client.analyze(...)  # operation=None
```

### 2. Use Prompt Templates

```python
# Good - reusable, versioned
prompt = load_prompt("deal_analysis")

# Okay - for one-off cases
prompt = "Analyze this: {data}"
```

### 3. Handle Errors Gracefully

```python
try:
    result = await client.analyze(...)
    score = result['score']
except ClaudeAPIError:
    score = None  # Fallback
```

### 4. Monitor Costs

Set up alerts for daily cost thresholds:

```python
if daily_cost > BUDGET_LIMIT:
    send_alert(f"Claude API costs: ${daily_cost:.2f}")
```

### 5. Validate JSON Responses

```python
result = await client.analyze(...)

# Validate expected fields
assert 'score' in result, "Missing score field"
assert 0 <= result['score'] <= 100, "Invalid score range"
```

## Troubleshooting

### Issue: "Module not found: anthropic"

**Solution**: Install dependencies

```bash
poetry install
```

### Issue: "Redis connection failed"

**Solution**: Check Redis is running

```bash
redis-cli ping  # Should return "PONG"
```

### Issue: "API key invalid"

**Solution**: Check `.env` file

```bash
grep ANTHROPIC_API_KEY .env
```

### Issue: "JSON parsing failed"

**Solution**: Claude might return text instead of JSON. Either:
1. Use `response_format='text'`
2. Improve prompt to explicitly request JSON
3. Add example JSON to prompt

## API Reference

See inline documentation in:
- `app/ai/claude_client.py`
- `app/ai/prompt_loader.py`
- `app/models/api_cost.py`

## License

MIT License - See main project LICENSE file.
