#!/bin/bash
# Скрипт для быстрого деплоя улучшений калькулятора

set -e  # Остановка при ошибке

echo "═══════════════════════════════════════════════════════════════════"
echo "🚀 ДЕПЛОЙ: Улучшения калькулятора недвижимости"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# 1. Проверка текущей ветки
echo "📍 Проверка текущей ветки..."
CURRENT_BRANCH=$(git branch --show-current)
echo "   Текущая ветка: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Переключение на main..."
    git checkout main
    git pull origin main
fi

echo ""

# 2. Мерж feature ветки
echo "🔀 Мерж feature ветки..."
git merge claude/review-calculator-functionality-011CUvo2xo7a3DG4TPqMSr7w --no-ff -m "Merge: Advanced calculator analytics and reporting

- Add price range calculator (min/fair/recommended/max)
- Add attractiveness index (0-100 score)  
- Add time-to-sell forecast with probabilities
- Enhance reports with methodology and promotion packages
- Full documentation and test coverage

Includes:
- 3 new analytics modules (1,000+ lines)
- Enhanced markdown reports
- Comprehensive documentation
- 15+ new tests

Business impact: Better pricing insights + built-in upsell packages"

echo "✅ Мерж выполнен"
echo ""

# 3. Показать изменения
echo "📋 Последние коммиты:"
git log --oneline -5
echo ""

# 4. Пуш в main
echo "⬆️  Пуш в origin/main..."
read -p "   Продолжить? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git push origin main
    echo "✅ Изменения запушены в main"
else
    echo "❌ Деплой отменен"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "✅ ГИТ ДЕПЛОЙ ЗАВЕРШЕН!"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
echo "   1. Перезапустить сервис:"
echo "      sudo systemctl restart cian-analyzer"
echo "      # ИЛИ"  
echo "      docker-compose down && docker-compose up -d"
echo ""
echo "   2. Проверить логи:"
echo "      sudo journalctl -u cian-analyzer -f"
echo "      # ИЛИ"
echo "      docker-compose logs -f"
echo ""
echo "   3. Тестовый запрос анализа"
echo "   4. Проверить новые секции в отчете"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
