#!/bin/bash

# ========================================
# Housler v2.0 - Automated Deployment Script
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
# Pre-flight checks
# ========================================

print_header "Housler v2.0 Deployment"

echo "Checking prerequisites..."

if ! check_command docker; then
    print_error "Docker is required. Please install: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! check_command docker-compose; then
    print_error "Docker Compose is required. Please install: https://docs.docker.com/compose/install/"
    exit 1
fi

print_success "Prerequisites check passed"

# ========================================
# Configuration
# ========================================

print_header "Configuration"

if [ ! -f .env ]; then
    print_warning ".env not found, creating from template..."
    cp .env.example .env
    print_success "Created .env from template"
    print_warning "Please edit .env and configure your settings"
    read -p "Press Enter to continue after editing .env..."
else
    print_success ".env found"
fi

# ========================================
# Choose deployment mode
# ========================================

print_header "Select Deployment Mode"

echo "1) Development (app + redis)"
echo "2) Production (app + redis + nginx)"
echo "3) Full Stack (app + redis + prometheus + grafana)"
echo ""
read -p "Choose mode [1-3]: " MODE

case $MODE in
    1)
        PROFILE=""
        MODE_NAME="Development"
        ;;
    2)
        PROFILE="--profile production"
        MODE_NAME="Production"
        ;;
    3)
        PROFILE="--profile monitoring"
        MODE_NAME="Full Stack"
        ;;
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

print_success "Selected: $MODE_NAME"

# ========================================
# Build
# ========================================

print_header "Building Docker Images"

echo "This may take 5-10 minutes on first run..."
docker-compose build --no-cache

print_success "Build complete"

# ========================================
# Deploy
# ========================================

print_header "Deploying Services"

docker-compose $PROFILE up -d

print_success "Services deployed"

# ========================================
# Wait for services
# ========================================

print_header "Waiting for Services"

echo "Waiting for application to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        print_success "Application is ready"
        break
    fi
    echo -n "."
    sleep 2
done

# ========================================
# Health Check
# ========================================

print_header "Health Check"

HEALTH=$(curl -s http://localhost:5000/health | jq -r '.status' 2>/dev/null || echo "error")

if [ "$HEALTH" == "healthy" ]; then
    print_success "Health check passed"
else
    print_warning "Health check returned: $HEALTH"
    echo "Check logs with: docker-compose logs app"
fi

# ========================================
# Summary
# ========================================

print_header "Deployment Complete"

echo -e "${GREEN}Services running:${NC}"
docker-compose ps

echo ""
echo -e "${CYAN}Access points:${NC}"
echo -e "  ${GREEN}Application:${NC} http://localhost:5000"
echo -e "  ${GREEN}Health Check:${NC} http://localhost:5000/health"
echo -e "  ${GREEN}Metrics:${NC} http://localhost:5000/metrics"
echo -e "  ${GREEN}API Docs:${NC} See API_DOCS.md"

if [ "$MODE" == "3" ]; then
    echo -e "  ${GREEN}Prometheus:${NC} http://localhost:9090"
    echo -e "  ${GREEN}Grafana:${NC} http://localhost:3000 (admin/admin)"
fi

echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo -e "  ${GREEN}View logs:${NC} docker-compose logs -f app"
echo -e "  ${GREEN}Stop services:${NC} docker-compose down"
echo -e "  ${GREEN}Restart:${NC} docker-compose restart app"
echo -e "  ${GREEN}Run make help:${NC} make help"

echo ""
print_success "Deployment successful! 🚀"
