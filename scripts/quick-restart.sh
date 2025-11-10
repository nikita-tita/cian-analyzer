#!/bin/bash

# ========================================
# Quick Restart (Zero-downtime)
# ========================================

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}Starting zero-downtime restart...${NC}"

# Check if docker-compose or docker compose
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Rebuild and restart only the app service
echo "Rebuilding application..."
$DOCKER_COMPOSE build app

echo "Restarting application..."
$DOCKER_COMPOSE up -d --force-recreate --no-deps app

echo "Waiting for health check..."
sleep 5

# Wait for health check
for i in {1..15}; do
    if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Application restarted successfully${NC}"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo -e "\n${CYAN}Application may still be starting. Check status with:${NC}"
echo "$DOCKER_COMPOSE logs -f app"
