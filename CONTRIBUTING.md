# Contributing to SmartFamilyTravelScout

Thank you for your interest in contributing to SmartFamilyTravelScout! We welcome contributions from the community and appreciate your effort to make this project better.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style Standards](#code-style-standards)
- [Commit Message Format](#commit-message-format)
- [Pull Request Process](#pull-request-process)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Getting Help](#getting-help)

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:
- **Python 3.11+**
- **Poetry** (Python dependency management)
- **Docker & Docker Compose** (for PostgreSQL and Redis)
- **Git**

### Fork and Clone

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/smartfamilytravelscout.git
   cd smartfamilytravelscout
   ```

3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/mikandro/smartfamilytravelscout.git
   ```

### Environment Setup

1. **Install dependencies**:
   ```bash
   poetry install
   ```

2. **Install Playwright browsers** (required for web scrapers):
   ```bash
   poetry run playwright install chromium
   poetry run playwright install-deps
   ```

3. **Start infrastructure services**:
   ```bash
   docker-compose up -d postgres redis
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. **Run database migrations**:
   ```bash
   poetry run alembic upgrade head
   ```

6. **Seed the database** (optional, for sample data):
   ```bash
   poetry run scout db seed
   ```

7. **Verify installation**:
   ```bash
   poetry run scout health
   ```

## Development Workflow

### Creating a Feature Branch

Always create a new branch for your work:

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/bug-description
```

### Development Cycle

1. **Make your changes** in the appropriate files
2. **Run tests** to ensure nothing breaks:
   ```bash
   poetry run pytest
   ```

3. **Format your code** with Black:
   ```bash
   poetry run black app/
   ```

4. **Lint your code** with Ruff:
   ```bash
   poetry run ruff check app/
   ```

5. **Type check** with mypy (if applicable):
   ```bash
   poetry run mypy app/
   ```

6. **Test your changes manually** if needed:
   ```bash
   # For scraper changes:
   poetry run scout test-scraper skyscanner --origin MUC --dest BCN

   # For API changes:
   poetry run uvicorn app.api.main:app --reload
   ```

### Pre-commit Checks

Before committing, ensure:
- [ ] All tests pass
- [ ] Code is formatted with Black
- [ ] Linting passes (no Ruff errors)
- [ ] Type hints are added where appropriate
- [ ] Documentation is updated

## Code Style Standards

### Python Code Style

We follow **PEP 8** with some project-specific guidelines:

1. **Formatting**: Use Black (line length: 88 characters)
   ```bash
   poetry run black app/
   ```

2. **Linting**: Use Ruff for fast Python linting
   ```bash
   poetry run ruff check app/
   ```

3. **Type Hints**: Add type hints to all function signatures
   ```python
   # Good
   def scrape_flights(origin: str, destination: str, date: datetime) -> list[dict]:
       pass

   # Bad
   def scrape_flights(origin, destination, date):
       pass
   ```

4. **Docstrings**: Use Google-style docstrings for public functions
   ```python
   def calculate_true_cost(flight: Flight, num_passengers: int = 4) -> float:
       """Calculate the true cost of a flight including all fees.

       Args:
           flight: The flight object to calculate cost for
           num_passengers: Number of passengers (default: 4 for family)

       Returns:
           Total cost in EUR including flights, parking, and travel costs
       """
       pass
   ```

5. **Function Design**: Keep functions focused and single-purpose
   - Functions should do one thing well
   - Avoid functions longer than 50 lines
   - Extract complex logic into helper functions

6. **Async/Sync Pattern**:
   - Use **async** in FastAPI routes and async database operations
   - Use **sync** in Celery tasks and CLI commands
   ```python
   # FastAPI route (async)
   async def get_flights(db: AsyncSession = Depends(get_async_session)):
       result = await db.execute(select(Flight))

   # Celery task (sync)
   @celery_app.task
   def scrape_flights_task():
       db = get_sync_session()
       try:
           flights = db.query(Flight).all()
       finally:
           db.close()
   ```

### Import Organization

Organize imports in this order:
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# Standard library
import logging
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import APIRouter, Depends
from sqlalchemy import select
from pydantic import BaseModel

# Local
from app.database import get_async_session
from app.models import Flight
from app.config import settings
```

## Commit Message Format

We use **Conventional Commits** format for clear and consistent commit history:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring (no feature changes or bug fixes)
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Maintenance tasks (dependencies, build, etc.)
- **ci**: CI/CD changes

### Scopes

Common scopes in this project:
- **scraper**: Web scraper changes (e.g., `skyscanner`, `ryanair`, `kiwi`)
- **api**: FastAPI route changes
- **ai**: Claude AI integration changes
- **db**: Database model or migration changes
- **orchestration**: Orchestrator changes
- **tasks**: Celery task changes
- **cli**: CLI command changes
- **docs**: Documentation updates

### Examples

```bash
# Good commit messages
feat(scraper): add Lufthansa scraper with Playwright
fix(api): correct flight price calculation in GET /flights endpoint
docs(readme): update installation instructions for M1 Macs
refactor(orchestration): simplify flight deduplication logic
test(scraper): add integration tests for Ryanair scraper
chore(deps): update Playwright to version 1.40.0

# Bad commit messages
update stuff
fix bug
WIP
changes
```

### Commit Message Guidelines

- Use imperative mood ("add feature" not "added feature")
- Keep the subject line under 72 characters
- Capitalize the subject line
- Don't end subject line with a period
- Add body for complex changes (explain why, not what)

## Pull Request Process

### Before Creating a PR

1. **Update your branch** with latest main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-feature-branch
   git rebase main
   ```

2. **Ensure all checks pass**:
   - [ ] Tests pass: `poetry run pytest`
   - [ ] Linting passes: `poetry run ruff check app/`
   - [ ] Code formatted: `poetry run black app/`
   - [ ] Type checking (if applicable): `poetry run mypy app/`

3. **Update documentation**:
   - [ ] Update README.md if adding new features
   - [ ] Update CLAUDE.md for development workflow changes
   - [ ] Add/update docstrings for new functions
   - [ ] Create docs in `docs/` for major features

4. **Update CHANGELOG** (if applicable):
   - Add entry under "Unreleased" section
   - Follow the format: `- [TYPE] Description (#PR-number)`

### Creating the PR

1. **Push your branch**:
   ```bash
   git push origin your-feature-branch
   ```

2. **Create PR on GitHub** with:
   - **Clear title**: Use conventional commit format
   - **Description**: Explain what, why, and how
   - **Screenshots**: For UI changes
   - **Testing notes**: How reviewers can test
   - **Breaking changes**: If any
   - **Issue reference**: Link related issues (e.g., "Fixes #123")

### PR Template

```markdown
## Description
[Brief description of changes]

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to break)
- [ ] Documentation update

## Related Issue
Fixes #[issue number]

## How Has This Been Tested?
[Describe testing performed]

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] No new warnings generated
```

### Review Process

- **Be responsive** to review feedback
- **Address all comments** or explain why not
- **Keep discussions focused** on the code
- **Squash commits** before merging (if requested)
- **Update branch** if main changes during review

### After Approval

1. **Squash commits** (if multiple small commits):
   ```bash
   git rebase -i main
   ```

2. **Final checks** before merge:
   - All CI checks pass
   - No merge conflicts
   - At least one approval from maintainer

## Testing Guidelines

### Test Structure

- **Unit tests**: `tests/unit/` - Fast, mocked, isolated tests
- **Integration tests**: `tests/integration/` - Real browsers, network calls

### Writing Tests

1. **Use pytest fixtures** from `tests/conftest.py`:
   ```python
   def test_flight_scraper(db_session, sample_flight):
       assert sample_flight.price > 0
   ```

2. **Mark integration tests**:
   ```python
   @pytest.mark.integration
   async def test_real_scraper():
       # Test with real browser
       pass
   ```

3. **Mock external services** in unit tests:
   ```python
   from unittest.mock import patch, AsyncMock

   @patch('app.scrapers.kiwi_scraper.httpx.AsyncClient')
   async def test_kiwi_scraper(mock_client):
       mock_client.get.return_value.json.return_value = {"data": []}
   ```

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html

# Only unit tests (fast)
poetry run pytest -m unit

# Only integration tests (slow)
poetry run pytest -m integration

# Specific test file
poetry run pytest tests/unit/test_scrapers.py

# Specific test function
poetry run pytest tests/unit/test_scrapers.py::test_kiwi_scraper
```

## Documentation

### Code Documentation

- **Docstrings**: Required for all public functions and classes
- **Inline comments**: For complex logic only (code should be self-documenting)
- **Type hints**: Required for function signatures

### Project Documentation

When adding features, update:
- **README.md**: User-facing features and quick start
- **CLAUDE.md**: Developer guidance for Claude Code
- **docs/**: Detailed guides for specific components
  - Create new file in `docs/` for major features
  - Follow existing naming convention: `feature_name.md`

### Documentation Examples

See existing docs for reference:
- `docs/SKYSCANNER_SCRAPER.md` - Scraper guide
- `docs/CLAUDE_INTEGRATION.md` - AI integration
- `docs/DATABASE_SCHEMA.md` - Database reference

## Getting Help

If you have questions or need help:

1. **Check existing documentation**:
   - README.md
   - CLAUDE.md
   - docs/ directory

2. **Search existing issues**: Your question might already be answered

3. **Create a GitHub issue**: For bugs or feature requests

4. **Discussion**: Use GitHub Discussions for general questions

5. **Discord**: Join our Discord server (if available)

## Code Review Guidelines

### For Contributors

- **Be open to feedback**: Reviews help improve code quality
- **Ask questions**: If feedback is unclear, ask for clarification
- **Be patient**: Reviewers are volunteers

### For Reviewers

- **Be constructive**: Suggest improvements, don't just criticize
- **Be specific**: Point to exact lines and explain why
- **Be timely**: Review within a few days if possible
- **Approve or request changes**: Don't leave PRs in limbo

## Common Development Tasks

### Adding a New Scraper

1. Create `app/scrapers/newsource_scraper.py`
2. Implement `scrape_flights()` or `scrape_accommodations()`
3. Add to orchestrator in `app/orchestration/`
4. Add tests in `tests/unit/test_newsource_scraper.py`
5. Update documentation in `docs/`

### Adding a New AI Feature

1. Create prompt in `app/ai/prompts/new_feature.txt`
2. Create analyzer in `app/ai/new_feature.py`
3. Use `ClaudeClient` and track costs
4. Add example in `examples/`
5. Update docs

### Database Changes

1. Modify model in `app/models/`
2. Generate migration: `poetry run alembic revision --autogenerate -m "description"`
3. Review generated migration
4. Test: `poetry run alembic upgrade head`
5. If issues: `poetry run alembic downgrade -1`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Thank you for contributing to SmartFamilyTravelScout! Your efforts help make family travel more accessible and affordable for everyone.

---

**Questions?** Open an issue or reach out to the maintainers.
