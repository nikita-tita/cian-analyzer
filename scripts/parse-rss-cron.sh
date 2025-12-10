#!/bin/bash
# RSS News Parser Cron Job
# Parses news from multiple RSS sources and publishes to blog
#
# Recommended cron schedule:
#   0 */4 * * * /var/www/housler/scripts/parse-rss-cron.sh >> /var/log/housler/rss-parser.log 2>&1
#
# This will run every 4 hours

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Timestamp for logging
echo "=========================================="
echo "RSS Parser started at $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# Parse from all RSS sources with full text (CIAN + World Property Journal)
# Limit to 5 articles per source to avoid overwhelming
python3 blog_cli.py rss-all -n 5

echo ""
echo "RSS Parser finished at $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
