# 🚀 Инструкция по деплою Report Export Feature

**Дата:** 2025-11-09
**Ветка:** `claude/investigate-report-system-011CUxTFgMSBuu1NcCgX5kvU`
**Сервер:** housler.ru (91.229.8.221)

---

## 📋 Что будет задеплоено

✅ **Export Reports** - кнопка "Скачать отчет" + API endpoint
✅ **Критические фиксы** - 93% парсинг, потеря данных, rate limiting
✅ **Browser Pool** - защита от утечек памяти
✅ **Расширенная аналитика** - индекс привлекательности, прогноз времени
✅ **230+ тестов** - не влияют на production, только для CI

---

## 🎯 Вариант 1: Быстрый деплой (рекомендуется)

### Шаг 1: Подключитесь к серверу
```bash
ssh root@91.229.8.221
# или
ssh housler@91.229.8.221
```

### Шаг 2: Обновите код
```bash
cd /var/www/housler

# Сохраните текущее состояние (на всякий случай)
git branch backup-$(date +%Y%m%d-%H%M%S)

# Получите последние изменения
git fetch origin

# Переключитесь на ветку с новыми фичами
git checkout claude/investigate-report-system-011CUxTFgMSBuu1NcCgX5kvU
git pull origin claude/investigate-report-system-011CUxTFgMSBuu1NcCgX5kvU
```

### Шаг 3: Обновите зависимости (если нужно)
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Шаг 4: Перезапустите сервис
```bash
sudo systemctl restart housler

# Проверьте что стартовал
sudo systemctl status housler

# Посмотрите логи
sudo journalctl -u housler -f --lines=50
```

### Шаг 5: Проверьте что работает
```bash
# Должен вернуть 200 и показать версию
curl -I https://housler.ru/health

# Проверьте что калькулятор загружается
curl https://housler.ru/calculator | grep wizard.js
```

---

## 🔄 Вариант 2: Создать main ветку и мержить

Если хотите иметь "стабильную" main ветку:

```bash
# Локально
git checkout -b main claude/investigate-report-system-011CUxTFgMSBuu1NcCgX5kvU
git push -u origin main

# На сервере
cd /var/www/housler
git fetch origin
git checkout main
git pull origin main
sudo systemctl restart housler
```

---

## 🎯 Вариант 3: Merge с существующей веткой

Если нужно мержить с веткой `claude/ui-improvements-list...`:

```bash
# Локально
git checkout claude/ui-improvements-list-011CUvLpHYLw6QmqZkT5gjF8
git merge claude/investigate-report-system-011CUxTFgMSBuu1NcCgX5kvU --no-ff
git push origin claude/ui-improvements-list-011CUvLpHYLw6QmqZkT5gjF8

# На сервере
cd /var/www/housler
git checkout claude/ui-improvements-list-011CUvLpHYLw6QmqZkT5gjF8
git pull
sudo systemctl restart housler
```

---

## 🧪 Тестирование после деплоя

### 1. Основные функции
```bash
# Health check
curl https://housler.ru/health

# CSRF token
curl https://housler.ru/api/csrf-token
```

### 2. Полный E2E тест
```bash
# Если pytest установлен на сервере
cd /var/www/housler
source venv/bin/activate
pytest tests/test_e2e_full_flow.py::TestE2EFullFlow::test_08_export_report -v
```

### 3. Ручное тестирование
1. Откройте https://housler.ru/calculator
2. Вставьте URL: `https://www.cian.ru/sale/flat/322762697/`
3. Нажмите "Парсить"
4. Найдите аналоги
5. Запустите анализ
6. **Проверьте кнопку "📥 Скачать детальный отчет"**
7. Кликните - должен скачаться `.md` файл
8. Откройте файл - проверьте все секции

---

## ⚠️ Rollback план

Если что-то пойдет не так:

```bash
# На сервере
cd /var/www/housler

# Вариант 1: Вернуться на предыдущую ветку
git checkout claude/ui-improvements-list-011CUvLpHYLw6QmqZkT5gjF8
sudo systemctl restart housler

# Вариант 2: Откатить на бекап
git checkout backup-YYYYMMDD-HHMMSS
sudo systemctl restart housler
```

---

## 📊 Мониторинг после деплоя

### Логи
```bash
# Смотреть логи в реальном времени
sudo journalctl -u housler -f

# Фильтровать ошибки
sudo journalctl -u housler -p err -f

# Искать экспорт отчетов
sudo journalctl -u housler | grep "Экспорт отчета"
```

### Метрики
```bash
# Использование памяти (проверить нет ли утечек)
ps aux | grep python | grep housler

# Статус systemd
sudo systemctl status housler

# Открытые файлы (проверить браузеры)
sudo lsof -p $(pgrep -f "python.*app_new.py") | grep -i chrome
```

---

## 🐛 Troubleshooting

### Сервис не стартует
```bash
# Проверьте логи
sudo journalctl -u housler -n 100 --no-pager

# Проверьте синтаксис Python
cd /var/www/housler
source venv/bin/activate
python -m py_compile app_new.py
```

### Import ошибки
```bash
# Переустановите зависимости
cd /var/www/housler
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Playwright не работает
```bash
# Переустановите браузеры
source venv/bin/activate
playwright install chromium
playwright install-deps
```

---

## ✅ Чеклист деплоя

- [ ] Подключился к серверу
- [ ] Сделал backup ветки
- [ ] Переключился на новую ветку
- [ ] Обновил зависимости
- [ ] Перезапустил сервис
- [ ] Проверил статус (running)
- [ ] Проверил логи (нет ошибок)
- [ ] Протестировал health endpoint
- [ ] Протестировал калькулятор
- [ ] Протестировал кнопку "Скачать отчет"
- [ ] Скачал и проверил отчет
- [ ] Мониторю логи 5-10 минут

---

## 🎉 Готово!

После успешного деплоя пользователи смогут:
- ✅ Скачивать детальные отчеты с методологией
- ✅ Видеть профессиональные рекомендации по продаже
- ✅ Получать более точную аналитику
- ✅ Работать без багов парсинга

**Профит!** 🚀
