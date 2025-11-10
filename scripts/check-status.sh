#!/bin/bash

# ========================================
# Check Deployment Status
# ========================================

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# Check if docker-compose or docker compose
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

print_header "Deployment Status"

# Check if containers are running
echo -e "${CYAN}Running Containers:${NC}"
$DOCKER_COMPOSE ps

echo ""

# Check application health
echo -e "${CYAN}Application Health:${NC}"
if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:5000/health)
    echo -e "${GREEN}✓ Application is healthy${NC}"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    echo -e "${RED}✗ Application is not responding${NC}"
fi

echo ""

# Check last deployment info
if [ -f .last-deploy.json ]; then
    echo -e "${CYAN}Last Deployment:${NC}"
    cat .last-deploy.json | python3 -m json.tool 2>/dev/null || cat .last-deploy.json
else
    echo -e "${YELLOW}⚠ No deployment info found${NC}"
fi

echo ""

# Resource usage
echo -e "${CYAN}Resource Usage:${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep housler || echo "No containers running"
