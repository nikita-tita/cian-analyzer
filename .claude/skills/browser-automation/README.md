# Browser Automation Skill - Установлен! 🎉

Скилл для автоматизации браузера установлен и готов к использованию после завершения настройки.

## Статус установки

✅ **Зависимости**: Установлены (npm packages)
✅ **Browser CLI**: Установлен и доступен глобально
⚠️ **Chrome**: Требуется установка
⚠️ **API ключ**: Требуется настройка

## Что делает этот скилл?

Скилл интегрирует **Stagehand** (AI-фреймворк для автоматизации браузера) с Claude Code. Позволяет управлять браузером на естественном языке:

- 🌐 Открывать веб-страницы
- 🖱️ Кликать кнопки
- ⌨️ Заполнять формы
- 📸 Делать скриншоты
- 🔍 Извлекать данные
- 🎯 Находить элементы

Всё работает из **вашего аутентифицированного браузера** с сохранением cookies и сессий!

## Завершение установки

### 1. Установите Chrome (если ещё не установлен)

**macOS/Windows:**
```bash
# Скачайте с https://www.google.com/chrome/
```

**Linux:**
```bash
sudo apt install google-chrome-stable
```

### 2. Настройте API ключ Anthropic

**Вариант 1 (рекомендуется):** Экспортируйте в терминале
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

**Вариант 2:** Используйте .env файл
```bash
cd .claude-plugins/agent-browse
cp .env.example .env
# Отредактируйте .env и добавьте ваш API ключ
```

### 3. Проверьте установку

```bash
browser navigate https://example.com
```

Если команда работает - всё готово! 🎉

### 4. Обновите setup.json

После успешного теста обновите `.claude/skills/browser-automation/setup.json`:
```json
{
  "setupComplete": true,
  "prerequisites": {
    "chrome": { "installed": true },
    "dependencies": { "installed": true },
    "apiKey": { "configured": true },
    "browserCommand": { "installed": true }
  }
}
```

## Примеры использования

### Простой браузинг
```bash
browser navigate https://news.ycombinator.com
browser screenshot
browser close
```

### Извлечение данных
```bash
browser navigate https://example.com/products
browser extract "get all products" '{"name": "string", "price": "number"}'
browser close
```

### Заполнение форм
```bash
browser navigate https://example.com/login
browser act "fill in email with user@example.com"
browser act "fill in password with mypassword"
browser act "click the submit button"
browser screenshot
browser close
```

### Автоматизация задач
```bash
browser navigate https://cian.ru
browser act "type 'квартира москва' in search and press enter"
browser act "wait for results to load"
browser extract "get first 5 listings" '{"title": "string", "price": "number", "address": "string"}'
browser close
```

## Важные особенности

- 🔄 **Персистентный браузер**: Браузер остаётся открытым между командами
- 🍪 **Сохранение сессий**: Cookies и сессии сохраняются
- 📸 **Автоматические скриншоты**: Каждая команда сохраняет скриншот в `.claude-plugins/agent-browse/agent/browser_screenshots/`
- 🎯 **Natural language**: Команды на естественном языке

## Где находятся файлы?

- **Скилл**: `.claude/skills/browser-automation/`
- **Плагин**: `.claude-plugins/agent-browse/`
- **Скриншоты**: `.claude-plugins/agent-browse/agent/browser_screenshots/`

## Документация

- `SKILL.md` - Полное описание скилла
- `EXAMPLES.md` - Примеры использования
- `REFERENCE.md` - Техническая документация
- `setup.json` - Статус установки

## Troubleshooting

**Chrome не найден:**
```bash
# Установите Chrome для вашей ОС
```

**API ключ не настроен:**
```bash
export ANTHROPIC_API_KEY="your-key"
```

**Порт 9222 занят:**
```bash
# Закройте другие Chrome debugging сессии
```

**Нужно обновить профиль:**
```bash
cd .claude-plugins/agent-browse
rm -rf .chrome-profile
```

## Ссылки

- [Stagehand Documentation](https://github.com/browserbase/stagehand)
- [Agent Browse Repository](https://github.com/browserbase/agent-browse)
- [Claude Code Skills](https://docs.claude.com/en/docs/claude-code)

---

**Готово к работе!** Установите Chrome и API ключ, и можете начинать автоматизировать браузер! 🚀
