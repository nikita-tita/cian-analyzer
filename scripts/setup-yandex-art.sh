#!/bin/bash
# Setup YandexART role for cover image generation
# Run on server: bash /var/www/housler/scripts/setup-yandex-art.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Setup YandexART Access${NC}"
echo "================================"
echo ""
echo "Current API key has access to YandexGPT but not YandexART."
echo "Need to add role: ai.imageGeneration.user"
echo ""
echo -e "${YELLOW}Option 1: Via Yandex Cloud Console (Recommended)${NC}"
echo "1. Open https://console.cloud.yandex.ru/"
echo "2. Select folder: b1gga6i2l1rmfei43br9"
echo "3. Go to 'Service accounts' (Сервисные аккаунты)"
echo "4. Find your service account"
echo "5. Click 'Edit roles' (Редактировать роли)"
echo "6. Add role: ai.imageGeneration.user"
echo "7. Save"
echo ""
echo -e "${YELLOW}Option 2: Via yc CLI${NC}"
echo "If you have yc CLI configured with admin access:"
echo ""
echo "  # Get service account ID"
echo "  yc iam service-account list --folder-id b1gga6i2l1rmfei43br9"
echo ""
echo "  # Add role (replace SA_ID with actual ID)"
echo "  yc resource-manager folder add-access-binding b1gga6i2l1rmfei43br9 \\"
echo "    --role ai.imageGeneration.user \\"
echo "    --subject serviceAccount:SA_ID"
echo ""
echo "================================"
echo ""
echo "After adding the role, test with:"
echo "  cd /var/www/housler"
echo "  ./venv/bin/python blog_cli.py generate-cover <any-slug>"
echo ""
