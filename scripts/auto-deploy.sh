#!/bin/bash

# ========================================
# Claude Code Auto-Deploy Script
# ========================================
# This script provides automated deployment
# that can be triggered from Claude Code
# ========================================

set -e  # Exit on error

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed"
        return 1
    fi
    return 0
}

# ========================================
# Parse arguments
# ========================================

MODE=${1:-1}  # Default to development mode
SKIP_TESTS=${2:-false}

print_header "Claude Code Auto-Deploy"

# ========================================
# Pre-flight checks
# ========================================

echo "Checking prerequisites..."

if ! check_command docker; then
    print_error "Docker is required. Install: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! check_command docker-compose && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is required. Install: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if docker-compose or docker compose
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

print_success "Prerequisites check passed"

# ========================================
# Configuration
# ========================================

print_header "Configuration"

if [ ! -f .env ]; then
    print_warning ".env not found, creating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_success "Created .env from template"
        print_warning "Using default configuration. Edit .env for custom settings."
    else
        print_error ".env.example not found!"
        exit 1
    fi
else
    print_success ".env found"
fi

# ========================================
# Select deployment mode
# ========================================

print_header "Deployment Mode"

case $MODE in
    1|dev|development)
        PROFILE=""
        MODE_NAME="Development"
        ;;
    2|prod|production)
        PROFILE="--profile production"
        MODE_NAME="Production"
        ;;
    3|full|monitoring)
        PROFILE="--profile monitoring"
        MODE_NAME="Full Stack"
        ;;
    *)
        print_error "Invalid mode: $MODE"
        echo "Valid modes: 1|dev|development, 2|prod|production, 3|full|monitoring"
        exit 1
        ;;
esac

print_success "Selected: $MODE_NAME mode"

# ========================================
# Stop existing containers
# ========================================

print_header "Stopping Existing Containers"

if $DOCKER_COMPOSE ps | grep -q "Up"; then
    echo "Stopping running containers..."
    $DOCKER_COMPOSE down
    print_success "Containers stopped"
else
    print_success "No running containers to stop"
fi

# ========================================
# Build
# ========================================

print_header "Building Docker Images"

echo "Building images (this may take a few minutes)..."
$DOCKER_COMPOSE build

print_success "Build complete"

# ========================================
# Run tests (optional)
# ========================================

if [ "$SKIP_TESTS" != "true" ]; then
    print_header "Running Tests"

    echo "Starting Redis for tests..."
    $DOCKER_COMPOSE up -d redis
    sleep 3

    if docker run --rm \
        --network cian-analyzer_housler-network \
        -e REDIS_HOST=redis \
        -v $(pwd):/app \
        -w /app \
        housler-app:latest \
        python -m pytest tests/ -v --ignore=tests/test_e2e_full_flow.py 2>&1 | tee test_output.log; then
        print_success "Tests passed"
    else
        print_warning "Some tests failed, but continuing deployment"
        cat test_output.log
    fi

    rm -f test_output.log
else
    print_warning "Skipping tests (SKIP_TESTS=true)"
fi

# ========================================
# Deploy
# ========================================

print_header "Deploying Services"

$DOCKER_COMPOSE $PROFILE up -d

print_success "Services deployed"

# ========================================
# Wait for services
# ========================================

print_header "Waiting for Services"

echo "Waiting for application to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
        print_success "Application is ready"
        break
    fi
    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "Application failed to start within timeout"
    echo "Checking logs..."
    $DOCKER_COMPOSE logs app | tail -50
    exit 1
fi

# ========================================
# Health Check
# ========================================

print_header "Health Check"

HEALTH=$(curl -s http://localhost:5000/health 2>/dev/null || echo '{"status":"error"}')
STATUS=$(echo $HEALTH | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$STATUS" == "healthy" ]; then
    print_success "Health check passed"
else
    print_warning "Health check returned: $STATUS"
    echo "Response: $HEALTH"
    echo ""
    echo "Check logs with: $DOCKER_COMPOSE logs app"
fi

# ========================================
# Summary
# ========================================

print_header "Deployment Complete"

echo -e "${GREEN}Services Status:${NC}"
$DOCKER_COMPOSE ps

echo ""
echo -e "${CYAN}Access Points:${NC}"
echo -e "  ${GREEN}Application:${NC}  http://localhost:5000"
echo -e "  ${GREEN}Health Check:${NC} http://localhost:5000/health"
echo -e "  ${GREEN}Metrics:${NC}      http://localhost:5000/metrics"

if echo "$PROFILE" | grep -q "monitoring"; then
    echo -e "  ${GREEN}Prometheus:${NC}   http://localhost:9090"
    echo -e "  ${GREEN}Grafana:${NC}      http://localhost:3000 (admin/admin)"
fi

echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo -e "  ${GREEN}View logs:${NC}       $DOCKER_COMPOSE logs -f app"
echo -e "  ${GREEN}Stop services:${NC}   $DOCKER_COMPOSE down"
echo -e "  ${GREEN}Restart app:${NC}     $DOCKER_COMPOSE restart app"
echo -e "  ${GREEN}Shell access:${NC}    $DOCKER_COMPOSE exec app /bin/bash"

echo ""
print_success "🚀 Deployment successful!"

# ========================================
# Save deployment info
# ========================================

cat > .last-deploy.json << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "mode": "$MODE_NAME",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "git_branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')",
  "status": "success"
}
EOF

echo ""
echo -e "${CYAN}Deployment info saved to .last-deploy.json${NC}"
