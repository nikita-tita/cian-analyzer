#!/bin/bash

# ========================================
# Production Deployment Script
# Deploy to housler.ru production server
# ========================================

set -e

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

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# ========================================
# Configuration
# ========================================

BRANCH="${1:-main}"
SKIP_BACKUP="${2:-false}"

print_header "Housler Production Deployment"

echo "Configuration:"
echo "  Branch: $BRANCH"
echo "  Skip backup: $SKIP_BACKUP"
echo ""

# ========================================
# 1. Pre-deployment Backup
# ========================================

if [ "$SKIP_BACKUP" != "true" ]; then
    print_header "1. Creating Backup"

    if command -v docker &> /dev/null; then
        BACKUP_DIR="/opt/backups/housler"
        DATE=$(date +%Y%m%d_%H%M%S)

        mkdir -p "$BACKUP_DIR"

        # Backup Redis if running
        if docker ps | grep -q housler-redis; then
            echo "Backing up Redis data..."
            docker exec housler-redis redis-cli BGSAVE 2>/dev/null || true
            sleep 2
            docker cp housler-redis:/data/dump.rdb "$BACKUP_DIR/pre_deploy_$DATE.rdb" 2>/dev/null || true
            print_success "Redis backup created"
        else
            print_warning "Redis not running, skipping backup"
        fi
    else
        print_warning "Docker not found, skipping backup"
    fi
else
    print_warning "Backup skipped"
fi

# ========================================
# 2. Pull Latest Code
# ========================================

print_header "2. Pulling Latest Code"

# Stash any local changes
git stash save "Auto-stash before deployment $(date +%Y%m%d_%H%M%S)" || true

# Fetch updates
git fetch origin

# Get current commit
CURRENT_COMMIT=$(git rev-parse HEAD)

# Checkout and pull
git checkout "$BRANCH"
git pull origin "$BRANCH"

# Get new commit
NEW_COMMIT=$(git rev-parse HEAD)

if [ "$CURRENT_COMMIT" == "$NEW_COMMIT" ]; then
    print_warning "No changes to deploy"
else
    print_success "Updated from $CURRENT_COMMIT to $NEW_COMMIT"

    # Show changes
    echo ""
    echo "Changes:"
    git log --oneline "$CURRENT_COMMIT..$NEW_COMMIT"
    echo ""
fi

# ========================================
# 3. Check Environment
# ========================================

print_header "3. Checking Environment"

if [ ! -f .env ]; then
    print_error ".env file not found!"
    echo "Creating from .env.example..."

    if [ -f .env.example ]; then
        cp .env.example .env
        print_warning "Please edit .env with production settings"
        exit 1
    else
        print_error ".env.example not found!"
        exit 1
    fi
fi

print_success "Environment configured"

# ========================================
# 4. Stop Current Services
# ========================================

print_header "4. Stopping Current Services"

# Check if docker-compose or docker compose
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

if $DOCKER_COMPOSE ps | grep -q "Up"; then
    echo "Stopping services gracefully..."
    $DOCKER_COMPOSE down --timeout 30
    print_success "Services stopped"
else
    print_success "No services to stop"
fi

# ========================================
# 5. Build New Images
# ========================================

print_header "5. Building Docker Images"

echo "Building production images..."
$DOCKER_COMPOSE build --pull --no-cache

print_success "Images built"

# ========================================
# 6. Start Services
# ========================================

print_header "6. Starting Services"

$DOCKER_COMPOSE --profile production up -d

print_success "Services started"

# ========================================
# 7. Wait for Health Check
# ========================================

print_header "7. Health Check"

echo "Waiting for application to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
HEALTH_URL="http://localhost:5000/health"

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        print_success "Application is healthy"

        # Show health status
        HEALTH=$(curl -s "$HEALTH_URL")
        echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
        break
    fi

    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "Health check failed!"
    echo ""
    echo "Checking logs..."
    $DOCKER_COMPOSE logs --tail=50 app
    echo ""
    print_error "Deployment failed. Rolling back..."

    # Rollback to previous commit
    git checkout "$CURRENT_COMMIT"
    $DOCKER_COMPOSE build --no-cache
    $DOCKER_COMPOSE --profile production up -d

    exit 1
fi

# ========================================
# 8. Reload Nginx
# ========================================

print_header "8. Reloading Nginx"

if command -v nginx &> /dev/null; then
    if systemctl is-active --quiet nginx; then
        nginx -t && systemctl reload nginx
        print_success "Nginx reloaded"
    else
        print_warning "Nginx not running"
    fi
else
    print_warning "Nginx not installed"
fi

# ========================================
# 9. Cleanup
# ========================================

print_header "9. Cleanup"

# Remove old images
echo "Removing unused Docker images..."
docker image prune -f
print_success "Cleanup complete"

# ========================================
# 10. Save Deployment Info
# ========================================

print_header "10. Saving Deployment Info"

cat > .last-deploy.json << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "environment": "production",
  "branch": "$BRANCH",
  "commit": "$NEW_COMMIT",
  "deployed_by": "${USER:-automated}",
  "status": "success"
}
EOF

print_success "Deployment info saved"

# ========================================
# Summary
# ========================================

print_header "Deployment Complete!"

echo -e "${GREEN}Deployment successful!${NC}"
echo ""
echo -e "${CYAN}Deployment Details:${NC}"
echo "  Environment: Production"
echo "  Branch: $BRANCH"
echo "  Commit: $NEW_COMMIT"
echo "  Time: $(date)"
echo ""
echo -e "${CYAN}Services Status:${NC}"
$DOCKER_COMPOSE ps
echo ""
echo -e "${CYAN}Application URLs:${NC}"
echo "  Public: https://housler.ru"
echo "  Health: https://housler.ru/health"
echo "  Metrics: https://housler.ru/metrics"
echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo "  View logs:     $DOCKER_COMPOSE logs -f app"
echo "  Restart:       $DOCKER_COMPOSE restart app"
echo "  Stop:          $DOCKER_COMPOSE down"
echo "  Status:        $DOCKER_COMPOSE ps"
echo ""
print_success "🚀 Production deployment complete!"

# Send notification (optional)
if [ -n "$DEPLOY_WEBHOOK_URL" ]; then
    curl -X POST "$DEPLOY_WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"status\":\"success\",\"commit\":\"$NEW_COMMIT\",\"time\":\"$(date)\"}" \
        2>/dev/null || true
fi
