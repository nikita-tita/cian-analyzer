#!/bin/bash

# ========================================
# Production Server Setup Script
# Автоматическая настройка VPS для Housler
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

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

print_header "Housler Production Server Setup"

# Configuration
DOMAIN="${DOMAIN:-housler.ru}"
APP_USER="${APP_USER:-housler}"
APP_DIR="/opt/housler"
REPO_URL="https://github.com/nikita-tita/cian-analyzer.git"

echo "Configuration:"
echo "  Domain: $DOMAIN"
echo "  User: $APP_USER"
echo "  Directory: $APP_DIR"
echo ""
read -p "Continue with this configuration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# ========================================
# 1. Update System
# ========================================

print_header "1. System Update"

apt-get update
apt-get upgrade -y
print_success "System updated"

# ========================================
# 2. Install Dependencies
# ========================================

print_header "2. Installing Dependencies"

# Essential tools
apt-get install -y \
    curl \
    wget \
    git \
    jq \
    htop \
    ufw \
    certbot \
    python3-certbot-nginx

print_success "Essential tools installed"

# ========================================
# 3. Install Docker
# ========================================

print_header "3. Installing Docker"

if command -v docker &> /dev/null; then
    print_warning "Docker already installed"
else
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    print_success "Docker installed"
fi

# ========================================
# 4. Install Docker Compose
# ========================================

print_header "4. Installing Docker Compose"

if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    print_warning "Docker Compose already installed"
else
    # Install Docker Compose plugin
    apt-get install -y docker-compose-plugin
    print_success "Docker Compose installed"
fi

# ========================================
# 5. Create Application User
# ========================================

print_header "5. Creating Application User"

if id "$APP_USER" &>/dev/null; then
    print_warning "User $APP_USER already exists"
else
    useradd -m -s /bin/bash "$APP_USER"
    usermod -aG docker "$APP_USER"
    print_success "User $APP_USER created"
fi

# ========================================
# 6. Setup Application Directory
# ========================================

print_header "6. Setting Up Application"

if [ -d "$APP_DIR" ]; then
    print_warning "Directory $APP_DIR already exists"
    read -p "Remove and re-clone? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$APP_DIR"
    fi
fi

if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
    cd "$APP_DIR"

    # Clone repository
    git clone "$REPO_URL" .
    print_success "Repository cloned"

    # Set ownership
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    print_success "Ownership set"
fi

# ========================================
# 7. Create Environment File
# ========================================

print_header "7. Creating Environment Configuration"

if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" << EOF
# Redis Configuration
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6380
REDIS_DB=0
REDIS_PASSWORD=$(openssl rand -base64 32)
REDIS_NAMESPACE=housler_prod

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=false

# Gunicorn Configuration
WORKERS=4
WORKER_CLASS=sync
TIMEOUT=300
BIND=0.0.0.0:5000

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://redis:6380/1

# Domain
DOMAIN=$DOMAIN
EOF

    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    print_success "Environment file created"
else
    print_warning ".env file already exists, skipping"
fi

# ========================================
# 8. Setup Nginx
# ========================================

print_header "8. Installing and Configuring Nginx"

apt-get install -y nginx

# Create Nginx configuration
cat > /etc/nginx/sites-available/housler << EOF
# HTTP - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;

    # Let's Encrypt ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect to HTTPS
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    # SSL certificates (will be created by certbot)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/housler_access.log;
    error_log /var/log/nginx/housler_error.log;

    # Max upload size
    client_max_body_size 100M;

    # Proxy to Docker container
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$server_name;

        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Static files caching
    location /static/ {
        proxy_pass http://localhost:5000/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Health check
    location /health {
        proxy_pass http://localhost:5000/health;
        access_log off;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/housler /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test configuration
nginx -t

print_success "Nginx configured"

# ========================================
# 9. Setup Firewall
# ========================================

print_header "9. Configuring Firewall"

ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw status

print_success "Firewall configured"

# ========================================
# 10. Create Systemd Service
# ========================================

print_header "10. Creating Systemd Service"

cat > /etc/systemd/system/housler.service << EOF
[Unit]
Description=Housler Real Estate Analytics
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose restart
TimeoutStartSec=300
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable housler.service

print_success "Systemd service created"

# ========================================
# 11. Setup SSL Certificate
# ========================================

print_header "11. SSL Certificate Setup"

echo ""
echo -e "${CYAN}To obtain SSL certificate, you need to:${NC}"
echo ""
echo "1. Make sure DNS A record points to this server:"
echo "   $DOMAIN -> $(curl -s ifconfig.me)"
echo ""
echo "2. Run certbot:"
echo "   sudo certbot certonly --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "3. Certificate will auto-renew via cron"
echo ""
print_warning "SSL certificate needs to be obtained manually (see instructions above)"

# Create certbot renewal hook
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
systemctl reload nginx
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# ========================================
# 12. Setup Backup Script
# ========================================

print_header "12. Setting Up Backup"

mkdir -p /opt/backups/housler

cat > /opt/backups/housler/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/housler"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup Redis data
docker exec housler-redis redis-cli BGSAVE
sleep 5
docker cp housler-redis:/data/dump.rdb "$BACKUP_DIR/redis_$DATE.rdb"

# Cleanup old backups (keep 7 days)
find "$BACKUP_DIR" -name "redis_*.rdb" -mtime +7 -delete

echo "Backup completed: redis_$DATE.rdb"
EOF

chmod +x /opt/backups/housler/backup.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/backups/housler/backup.sh >> /var/log/housler-backup.log 2>&1") | crontab -

print_success "Backup configured (daily at 3 AM)"

# ========================================
# 13. Setup Log Rotation
# ========================================

print_header "13. Configuring Log Rotation"

cat > /etc/logrotate.d/housler << EOF
$APP_DIR/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 $APP_USER $APP_USER
    sharedscripts
    postrotate
        systemctl reload housler
    endscript
}

/var/log/housler-backup.log {
    weekly
    rotate 4
    compress
    notifempty
}
EOF

print_success "Log rotation configured"

# ========================================
# Summary
# ========================================

print_header "Setup Complete!"

echo -e "${GREEN}Server is configured and ready!${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo ""
echo "1. Configure DNS:"
echo "   A record: $DOMAIN -> $(curl -s ifconfig.me)"
echo "   A record: www.$DOMAIN -> $(curl -s ifconfig.me)"
echo ""
echo "2. Obtain SSL certificate:"
echo "   sudo certbot certonly --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "3. Start Nginx:"
echo "   sudo systemctl restart nginx"
echo ""
echo "4. Deploy application:"
echo "   cd $APP_DIR"
echo "   sudo -u $APP_USER bash scripts/auto-deploy.sh 2"
echo ""
echo "5. Start on boot:"
echo "   sudo systemctl start housler"
echo ""
echo -e "${CYAN}Configuration files:${NC}"
echo "  App directory: $APP_DIR"
echo "  Environment: $APP_DIR/.env"
echo "  Nginx config: /etc/nginx/sites-available/housler"
echo "  Systemd service: /etc/systemd/system/housler.service"
echo "  Backup script: /opt/backups/housler/backup.sh"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo "  sudo systemctl status housler    # Check status"
echo "  sudo systemctl restart housler   # Restart app"
echo "  sudo systemctl reload nginx      # Reload nginx"
echo "  sudo docker compose logs -f      # View logs"
echo ""
print_success "Ready for production! 🚀"
