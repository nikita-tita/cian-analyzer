#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════
# HOUSLER VPS Deployment Script
# Автоматический деплой на VPS с Ubuntu 22.04
# ═══════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

echo "🚀 Starting Housler deployment..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Конфигурация
DOMAIN="housler.ru"
APP_DIR="/var/www/housler"
APP_USER="housler"
PYTHON_VERSION="3.11"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 1: System Update${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

apt update
apt upgrade -y

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 2: Install Dependencies${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Основные пакеты
apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nginx \
    git \
    curl \
    wget \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    certbot \
    python3-certbot-nginx \
    redis-server

# Playwright dependencies
apt install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 3: Create Application User${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash $APP_USER
    echo -e "${YELLOW}Created user: $APP_USER${NC}"
else
    echo -e "${YELLOW}User $APP_USER already exists${NC}"
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 4: Setup Application Directory${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

mkdir -p $APP_DIR
chown -R $APP_USER:$APP_USER $APP_DIR

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 5: Clone Repository${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd $APP_DIR

# Check if git repo exists
if [ -d ".git" ]; then
    echo -e "${YELLOW}Repository exists, pulling latest changes${NC}"
    sudo -u $APP_USER git pull
else
    echo -e "${YELLOW}Cloning repository${NC}"
    # Временно клонируем как root, потом поменяем владельца
    git clone https://github.com/nikita-tita/cian-analyzer.git .
    chown -R $APP_USER:$APP_USER $APP_DIR
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 6: Setup Python Virtual Environment${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

sudo -u $APP_USER python3.11 -m venv venv
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install --upgrade pip"
sudo -u $APP_USER bash -c "source venv/bin/activate && pip install -r requirements.txt"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 7: Install Playwright Browsers${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

sudo -u $APP_USER bash -c "source venv/bin/activate && playwright install chromium"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 8: Setup Gunicorn Service${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cat > /etc/systemd/system/housler.service << EOF
[Unit]
Description=Housler Real Estate Analyzer
After=network.target

[Service]
Type=notify
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 2 --threads 2 --timeout 300 --bind 127.0.0.1:8000 app_new:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 9: Setup Nginx${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cat > /etc/nginx/sites-available/housler << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location /static {
        alias $APP_DIR/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/housler /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx config
nginx -t

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 10: Start Services${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

systemctl daemon-reload
systemctl enable housler
systemctl start housler
systemctl restart nginx

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Step 11: Setup SSL Certificate${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}Waiting 10 seconds for DNS to propagate...${NC}"
sleep 10

# Try to get SSL certificate
certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
    echo -e "${RED}SSL certificate setup failed - will use HTTP for now${NC}"
    echo -e "${YELLOW}Make sure DNS A record points to this server IP${NC}"
}

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Setup DNS A record: $DOMAIN -> $(curl -s ifconfig.me)"
echo "2. Visit http://$DOMAIN to check if site is running"
echo "3. SSL will auto-renew via certbot"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  sudo systemctl status housler   - Check app status"
echo "  sudo systemctl restart housler  - Restart app"
echo "  sudo journalctl -u housler -f   - View logs"
echo "  sudo nginx -t                   - Test nginx config"
echo ""
