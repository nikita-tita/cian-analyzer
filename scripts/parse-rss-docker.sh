#!/bin/bash
# RSS News Parser for Docker environment
# Runs the parser inside the housler-app container
#
# Setup cron on host:
#   0 */4 * * * /var/www/housler/scripts/parse-rss-docker.sh >> /var/log/housler/rss-parser.log 2>&1
#
# Or use systemd timer (recommended):
#   sudo cp /var/www/housler/systemd/rss-parser.* /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now rss-parser.timer

set -e

CONTAINER_NAME="housler-app"
LOG_PREFIX="[RSS-PARSER]"

log() {
    echo "$LOG_PREFIX $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log "Starting RSS parser job..."

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "ERROR: Container $CONTAINER_NAME is not running"
    exit 1
fi

# Run the parser inside the container
log "Executing parser in container..."
docker exec "$CONTAINER_NAME" python3 blog_cli.py rss-all -n 5

log "RSS parser job completed"
