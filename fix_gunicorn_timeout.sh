#!/bin/bash
# Fix Gunicorn timeout for long parsing operations

echo "🔧 Fixing Gunicorn timeout..."

# Backup current config
ssh root@91.229.8.221 "cp /etc/systemd/system/housler.service /etc/systemd/system/housler.service.backup-$(date +%Y%m%d)"

# Update timeout from 300s to 600s (10 minutes)
ssh root@91.229.8.221 "sed -i 's/--timeout 300/--timeout 600/' /etc/systemd/system/housler.service"

# Reload systemd and restart service
ssh root@91.229.8.221 "systemctl daemon-reload && systemctl restart housler"

echo "✅ Done!"
echo ""
echo "Verify:"
echo "  ssh root@91.229.8.221 'systemctl status housler'"
