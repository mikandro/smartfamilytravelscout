#!/usr/bin/env bash

###############################################################################
# SmartFamilyTravelScout - Automated Setup Script
###############################################################################
# This script automates the complete setup process for new users.
# It handles dependency installation, environment configuration, service
# startup, and database initialization.
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        print_success "$1 is installed"
        return 0
    else
        print_error "$1 is not installed"
        return 1
    fi
}

wait_for_service() {
    local service=$1
    local host=$2
    local port=$3
    local max_attempts=30
    local attempt=1

    print_info "Waiting for $service to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if nc -z "$host" "$port" 2>/dev/null; then
            print_success "$service is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    print_error "$service failed to start within expected time"
    return 1
}

###############################################################################
# Main Setup Process
###############################################################################

print_header "SmartFamilyTravelScout - Automated Setup"

echo "This script will set up the entire project for you automatically."
echo "It will install dependencies, configure services, and initialize the database."
echo ""

# Ask for confirmation
read -p "Continue with setup? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Setup cancelled by user"
    exit 0
fi

###############################################################################
# Step 1: Check Prerequisites
###############################################################################

print_header "Step 1/8: Checking Prerequisites"

prerequisites_ok=true

# Check for essential tools
if ! check_command "docker"; then
    print_error "Docker is required. Please install from: https://docs.docker.com/get-docker/"
    prerequisites_ok=false
fi

if ! check_command "docker-compose" && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is required. Please install from: https://docs.docker.com/compose/install/"
    prerequisites_ok=false
fi

if ! check_command "python3"; then
    print_error "Python 3.11+ is required. Please install from: https://www.python.org/downloads/"
    prerequisites_ok=false
else
    python_version=$(python3 --version | cut -d' ' -f2)
    print_info "Python version: $python_version"
fi

if ! check_command "poetry"; then
    print_warning "Poetry is not installed. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"

    if command -v poetry &> /dev/null; then
        print_success "Poetry installed successfully"
    else
        print_error "Poetry installation failed. Please install manually: https://python-poetry.org/docs/#installation"
        prerequisites_ok=false
    fi
fi

# Check for optional but useful tools
if ! check_command "git"; then
    print_warning "Git is not installed (optional but recommended)"
fi

if ! check_command "nc"; then
    print_warning "netcat (nc) is not installed. Service health checks may not work properly."
fi

if [ "$prerequisites_ok" = false ]; then
    print_error "Some prerequisites are missing. Please install them and run this script again."
    exit 1
fi

print_success "All prerequisites are installed!"

###############################################################################
# Step 2: Environment Configuration
###############################################################################

print_header "Step 2/8: Environment Configuration"

if [ -f ".env" ]; then
    print_warning ".env file already exists"
    read -p "Do you want to keep the existing .env file? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        cp .env.example .env
        print_success "Created new .env file from template"
    else
        print_info "Keeping existing .env file"
    fi
else
    cp .env.example .env
    print_success "Created .env file from template"
fi

print_info "You can start using the default (free) scrapers immediately!"
print_info "Optional API keys can be added to .env later for additional features."
echo ""
print_info "Quick start commands (no API key needed):"
echo "  poetry run scout scrape --origin MUC --destination BCN"
echo "  poetry run scout test-scraper skyscanner --origin VIE --dest LIS"
echo ""

###############################################################################
# Step 3: Install Python Dependencies
###############################################################################

print_header "Step 3/8: Installing Python Dependencies"

print_info "Installing Python packages with Poetry..."
if poetry install; then
    print_success "Python dependencies installed successfully"
else
    print_error "Failed to install Python dependencies"
    exit 1
fi

###############################################################################
# Step 4: Install Playwright Browsers
###############################################################################

print_header "Step 4/8: Installing Playwright Browsers"

print_info "Installing Chromium browser for web scraping..."
if poetry run playwright install chromium; then
    print_success "Playwright browsers installed successfully"
else
    print_error "Failed to install Playwright browsers"
    exit 1
fi

# Install system dependencies for Playwright (optional)
print_info "Installing system dependencies for Playwright..."
if poetry run playwright install-deps chromium 2>/dev/null; then
    print_success "Playwright system dependencies installed"
else
    print_warning "Could not install Playwright system dependencies (requires sudo). Skipping..."
    print_info "If you encounter issues, run: sudo poetry run playwright install-deps chromium"
fi

###############################################################################
# Step 5: Start Docker Services
###############################################################################

print_header "Step 5/8: Starting Docker Services"

print_info "Starting PostgreSQL and Redis containers..."

# Stop any existing containers
docker-compose down 2>/dev/null || true

# Start database services
if docker-compose up -d postgres redis; then
    print_success "Docker services started successfully"
else
    print_error "Failed to start Docker services"
    exit 1
fi

# Wait for PostgreSQL
if wait_for_service "PostgreSQL" "localhost" "5432"; then
    print_success "PostgreSQL is ready"
else
    print_error "PostgreSQL failed to start"
    docker-compose logs postgres
    exit 1
fi

# Wait for Redis
if wait_for_service "Redis" "localhost" "6379"; then
    print_success "Redis is ready"
else
    print_error "Redis failed to start"
    docker-compose logs redis
    exit 1
fi

###############################################################################
# Step 6: Database Migrations
###############################################################################

print_header "Step 6/8: Running Database Migrations"

print_info "Applying database schema migrations..."

# Give the database a moment to fully initialize
sleep 2

if poetry run alembic upgrade head; then
    print_success "Database migrations applied successfully"
else
    print_error "Failed to apply database migrations"
    print_info "Checking database logs..."
    docker-compose logs postgres | tail -20
    exit 1
fi

###############################################################################
# Step 7: Seed Database
###############################################################################

print_header "Step 7/8: Seeding Database"

print_info "Populating database with initial data (airports, school holidays)..."

if poetry run scout db seed; then
    print_success "Database seeded successfully"
else
    print_warning "Database seeding encountered issues (non-critical)"
    print_info "You can manually seed later with: poetry run scout db seed"
fi

###############################################################################
# Step 8: Verify Installation
###############################################################################

print_header "Step 8/8: Verifying Installation"

print_info "Running health checks..."

# Check if we can import the main application
if poetry run python -c "from app.api.main import app; print('OK')" 2>/dev/null; then
    print_success "Application imports successfully"
else
    print_warning "Could not verify application imports"
fi

# Check database connection
if poetry run scout health 2>/dev/null; then
    print_success "System health check passed"
else
    print_warning "Health check encountered issues (may need API keys configured)"
fi

###############################################################################
# Setup Complete!
###############################################################################

print_header "🎉 Setup Complete!"

echo -e "${GREEN}SmartFamilyTravelScout is ready to use!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}Quick Start Commands:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}1. Start scraping immediately (no API key needed!):${NC}"
echo "   poetry run scout scrape --origin MUC --destination BCN"
echo "   poetry run scout scrape --origin VIE --destination LIS --scraper skyscanner"
echo ""
echo -e "${GREEN}2. Test individual scrapers:${NC}"
echo "   poetry run scout test-scraper ryanair --origin MUC --dest PRG"
echo "   poetry run scout test-scraper wizzair --origin VIE --dest LIS"
echo ""
echo -e "${GREEN}3. Start the FastAPI web server:${NC}"
echo "   poetry run uvicorn app.api.main:app --reload"
echo "   Then visit: http://localhost:8000/docs"
echo ""
echo -e "${GREEN}4. View system status:${NC}"
echo "   poetry run scout health"
echo "   poetry run scout stats"
echo ""
echo -e "${GREEN}5. Start all services with Docker Compose:${NC}"
echo "   docker-compose up -d"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}Optional Configuration:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "For AI-powered deal scoring, add to .env file:"
echo "  ANTHROPIC_API_KEY=your_key_here"
echo ""
echo "For additional scrapers (optional):"
echo "  KIWI_API_KEY=your_key_here (100 calls/month free)"
echo "  EVENTBRITE_API_KEY=your_key_here"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}Running Services:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
docker-compose ps
echo ""
echo -e "${GREEN}Happy travel deal hunting! 🛫🏖️${NC}"
echo ""
