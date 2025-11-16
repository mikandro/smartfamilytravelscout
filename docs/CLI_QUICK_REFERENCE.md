# CLI Quick Reference

## Most Common Commands

```bash
# Full pipeline execution
scout run

# View best deals
scout deals --min-score 80

# Check system health
scout health

# Show configuration
scout config show

# View statistics
scout stats
```

## Command Categories

### 🚀 Main Operations
- `scout run` - Run full pipeline
- `scout deals` - View top deals
- `scout stats` - Show statistics

### ⚙️ Configuration
- `scout config show` - Display all settings
- `scout config get <key>` - Get single value
- `scout config set <key> <value>` - Update setting

### 🔍 Testing & Debugging
- `scout test-scraper <name>` - Test scraper
- `scout kiwi-search` - Search Kiwi flights
- `scout health` - Health check

### 💾 Database
- `scout db init` - Create tables
- `scout db seed` - Add sample data
- `scout db reset` - Reset database ⚠️

### 👷 Workers
- `scout worker` - Start Celery worker
- `scout beat` - Start scheduler

## Quick Examples

### Find Deals to Lisbon
```bash
scout deals --destination lisbon --min-score 75
```

### Run Pipeline for Specific Destinations
```bash
scout run --destinations LIS,BCN,PRG --max-price 200
```

### Test Kiwi Scraper
```bash
scout test-scraper kiwi --origin MUC --dest LIS
```

### View Weekly Statistics
```bash
scout stats --period week
```

### Export Deals as JSON
```bash
scout deals --format json > deals.json
```

## Common Options

| Option | Short | Description |
|--------|-------|-------------|
| `--help` | `-h` | Show help |
| `--version` | `-v` | Show version |
| `--destination` | `-d` | Filter by destination |
| `--origin` | `-o` | Set origin airport |
| `--period` | `-p` | Time period |
| `--format` | `-f` | Output format |

## Status Indicators

- 🟢 **Green** - Success, healthy
- 🟡 **Yellow** - Warning, pending
- 🔴 **Red** - Error, unhealthy
- 🔵 **Cyan** - Information
- 🟣 **Magenta** - Headers, scores

## Environment Setup

1. Install dependencies: `poetry install`
2. Activate shell: `poetry shell`
3. Configure: `cp .env.example .env`
4. Initialize DB: `scout db init`
5. Seed data: `scout db seed`
6. Check health: `scout health`
7. Run pipeline: `scout run`

## Tips

💡 Use `--help` on any command for detailed options
💡 Set `DEBUG=true` in .env for verbose output
💡 Use `--format json` for scripting
💡 Check `scout health` if commands fail
💡 Lower `--min-score` if no deals found
