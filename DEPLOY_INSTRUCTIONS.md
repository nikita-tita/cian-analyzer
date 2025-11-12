# 🚀 Инструкция по деплою: Аддитивная модель расчета

**Дата**: 2025-01-12
**Ветка**: `claude/parser-calculator-updates-011CV2pdR7jVPb6BHaUwPn49`
**Коммит**: `0e1fed0`

---

## 📋 Что изменилось

### ⚠️ КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Логика расчета

**Было (мультипликативная модель):**
```
fair_price = median × coef1 × coef2 × coef3 × ...
```

**Стало (аддитивная модель с усреднением):**
```
variant1 = median × (1 + coef_ремонта)
variant2 = median × (1 + coef_вида)
variant3 = median × (1 + коef_санузлов)
...

fair_price_mean   = MEAN([variant1, variant2, ...])
fair_price_median = MEDIAN([variant1, variant2, ...])

# Выводим ОБА значения!
```

### 📦 Новые файлы

1. **src/analytics/fair_price_additive_helpers.py** (410 строк)

### 📝 Изменённые файлы

1. **src/analytics/fair_price_calculator.py**
2. **src/models/property.py** - Новые поля: material_quality, ownership_status
3. **src/analytics/analyzer.py**
4. **templates/wizard.html** - 6 новых полей

### 🔧 Пересмотренные коэффициенты

- Санузлы: ±30% → ±10%
- Окна: ±15% → ±10%
- Возраст дома: Отключен

### ✨ Новые коэффициенты

**material_quality**: -4% до +2%
**ownership_status**: -7% до +5%

---

## ✅ Проверки

**Синтаксис**: ✅ Все файлы OK
**Фронт**: ✅ Все 6 полей в HTML
**Git**: ✅ Закоммичено и запушено

---

## 🚀 Деплой

### Docker
```bash
cd /home/user/cian-analyzer
git checkout main
git merge claude/parser-calculator-updates-011CV2pdR7jVPb6BHaUwPn49
docker-compose down && docker-compose build --no-cache && docker-compose up -d
```

### Systemd
```bash
cd /home/user/cian-analyzer
git checkout main
git merge claude/parser-calculator-updates-011CV2pdR7jVPb6BHaUwPn49
sudo systemctl restart cian-analyzer
```

---

## 🧪 Тесты после деплоя

1. Открыть https://housler.ru/wizard
2. Проверить наличие 6 новых полей
3. Сгенерировать отчет с URL: https://spb.cian.ru/sale/flat/319270312/
4. Проверить что показываются MEAN и MEDIAN

---

## 🔄 Откат

```bash
git reset --hard ef85227  # Последний стабильный
docker-compose down && docker-compose up -d
```

**Готово к деплою!** 🚀
