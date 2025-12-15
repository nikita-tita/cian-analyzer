# Security Review для Cian Analyzer

Проведи security review изменений. Это проект работающий с данными недвижимости.

## Что проверить

### 1. SQL Injection (SQLAlchemy)
```bash
# Найди потенциальные уязвимости - raw SQL без параметров
grep -r "execute(" --include="*.py" . | grep -v "\.pyc"
grep -r "text(" --include="*.py" . | grep -v "\.pyc"
```
- Все запросы через ORM или параметризованные
- НЕ должно быть f-strings в SQL

### 2. Утечки данных в логах
- Проверь что sensitive данные НЕ логируются
- logger.info/debug не должен содержать пароли/токены

### 3. Валидация входных данных
- Pydantic models для API
- Проверь api/ на валидацию

### 4. Секреты
```bash
# Поиск хардкода секретов
grep -rE "(password|secret|key|token|api_key)\s*[:=]\s*['\"][^'\"]+['\"]" --include="*.py" .
```
- Все секреты через .env
- .env в .gitignore

### 5. Зависимости
```bash
# Проверка уязвимых зависимостей
pip-audit 2>/dev/null || echo "pip-audit не установлен"
```

## Формат вывода

```
[SEVERITY: HIGH/MEDIUM/LOW]
Файл: path/to/file.py:line
Проблема: описание
Как исправить: рекомендация
```

Если проблем не найдено: "Security review пройден."
