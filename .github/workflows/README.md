# GitHub Actions CI/CD Workflows

Автоматизация тестирования, security scanning, code quality checks и деплоя для Housler.

## 📋 Доступные Workflows

### 1. **test.yml** - Автоматическое тестирование
**Триггеры:** Push и PR на `main`, `master`, `develop`

**Что делает:**
- Запускает ~230 тестов на Python 3.10, 3.11, 3.12
- Проверяет code coverage (минимум 70%)
- Security tests отдельно
- Integration tests с Redis
- Генерирует coverage report
- Загружает результаты в Codecov

**Матрица тестирования:**
```yaml
- Unit tests (быстрые)
- Security tests (отдельный job)
- Integration tests (с Redis)
```

**Артефакты:**
- Coverage report (HTML + XML)
- Coverage badge (SVG)

---

### 2. **security.yml** - Security scanning
**Триггеры:** Push, PR, по расписанию (еженедельно)

**Инструменты:**
- **Bandit** - Python security issues (SQL injection, hardcoded passwords, etc.)
- **Safety** - Проверка уязвимых зависимостей
- **Semgrep** - SAST (Static Application Security Testing)
- **CodeQL** - GitHub advanced security analysis
- **Dependency Review** - Новые уязвимые зависимости в PR

**Артефакты:**
- bandit-security-report.json
- safety-dependency-report.json
- semgrep-security-report.json

**Расписание:**
```yaml
cron: '0 0 * * 1'  # Каждый понедельник в 00:00 UTC
```

---

### 3. **code-quality.yml** - Code quality checks
**Триггеры:** Push и PR на `main`, `master`, `develop`

**Проверки:**

#### Linting
- **Flake8** - PEP8 style guide compliance
- **Black** - Code formatting
- **isort** - Import sorting
- **MyPy** - Type checking

#### Complexity Analysis
- **Radon** - Cyclomatic complexity
- **Xenon** - Complexity thresholds
- Maintainability index

#### Documentation
- **Interrogate** - Docstring coverage
- **pydocstyle** - Docstring style

#### Other
- **pip-audit** - Dependency audit
- **pre-commit** - Pre-commit hooks
- Code statistics

---

### 4. **deploy.yml.template** - Deployment template
**Статус:** Template (требует настройки)

**Опции деплоя:**
1. SSH deployment (Gunicorn + systemd)
2. Docker deployment
3. Cloud platforms (Railway, Heroku)

**Как использовать:**
```bash
# 1. Переименовать template
mv .github/workflows/deploy.yml.template .github/workflows/deploy.yml

# 2. Настроить GitHub Secrets (Settings → Secrets)
# Required secrets:
SSH_HOST=your-server.com
SSH_USERNAME=deploy
SSH_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----...
SSH_PORT=22

# 3. Обновить команды деплоя под вашу инфраструктуру
```

**Features:**
- Automatic health checks
- Rollback on failure
- Database backup (опционально)
- Smoke tests после деплоя
- Deployment summary

---

## 🚀 Быстрый Старт

### Для первого запуска:

1. **Workflows уже активны** после push в репозиторий
2. Проверьте вкладку **Actions** в GitHub
3. Исправьте любые failing tests/checks

### Настройка Codecov (опционально):

```bash
# 1. Зарегистрироваться на codecov.io
# 2. Подключить ваш GitHub репозиторий
# 3. Получить CODECOV_TOKEN
# 4. Добавить в GitHub Secrets:
CODECOV_TOKEN=your-token-here
```

### Настройка badges в README:

```markdown
![Tests](https://github.com/your-username/cian-analyzer/workflows/Tests/badge.svg)
![Security](https://github.com/your-username/cian-analyzer/workflows/Security%20Scanning/badge.svg)
![Code Quality](https://github.com/your-username/cian-analyzer/workflows/Code%20Quality/badge.svg)
[![codecov](https://codecov.io/gh/your-username/cian-analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/your-username/cian-analyzer)
```

---

## 🔒 Security Scanning Details

### Bandit Checks
Проверяет на:
- SQL injection patterns
- Hardcoded passwords/tokens
- Unsafe YAML/pickle usage
- Shell injection
- Insecure SSL/TLS
- Known bad functions

### Safety Checks
Проверяет зависимости в requirements.txt на:
- Known CVEs
- Security advisories
- Vulnerable versions

### Semgrep Rules
- OWASP Top 10
- Language-specific security patterns
- Best practices violations

---

## 📊 Monitoring Results

### GitHub Actions Dashboard
```
Repository → Actions tab
- View all workflow runs
- Download artifacts
- See logs and errors
```

### Status Checks on PRs
Все workflows автоматически проверяются перед merge:
- ✅ Tests passing
- ✅ Security scan clean
- ✅ Code quality acceptable

### Notifications
Configure в: `Settings → Notifications → Actions`

---

## 🛠️ Troubleshooting

### Test failures

```bash
# Локально запустить те же тесты:
pytest -v --cov=src --cov=app_new --cov-fail-under=70 -m "not slow"
```

### Security scan false positives

Добавить в `.bandit`:
```yaml
skips:
  - B101  # Skip assert_used test
```

### Slow CI runs

- Используйте caching для pip
- Skip slow tests: `-m "not slow"`
- Параллельные jobs уже настроены

---

## 📝 Customization

### Изменить Python versions:
```yaml
# In test.yml
matrix:
  python-version: ["3.10", "3.11", "3.12"]
```

### Изменить coverage threshold:
```yaml
# In test.yml
--cov-fail-under=70  # Change to your desired %
```

### Добавить deployment target:
```yaml
# Uncomment option in deploy.yml.template:
# - Option 1: SSH
# - Option 2: Docker
# - Option 3: Cloud (Railway, Heroku)
```

---

## 🎯 Best Practices

1. **Always run tests locally** before pushing
2. **Fix security issues immediately** when found
3. **Keep dependencies updated** (use Dependabot)
4. **Monitor workflow failures** in Actions tab
5. **Require status checks** before merging PRs

---

## 🔗 Links

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Codecov](https://about.codecov.io/)
- [Semgrep Rules](https://semgrep.dev/r)

---

## 📞 Support

Проблемы с CI/CD workflows? Check:
1. **Actions logs** в GitHub
2. **Workflow syntax** с GitHub Actions Validator
3. **Secrets configuration** в Settings

## 🎉 Итог

С этими workflows у вас:
- ✅ Автоматические тесты на каждый PR
- ✅ Security scanning 24/7
- ✅ Code quality enforcement
- ✅ Ready-to-use deployment template
- ✅ Coverage tracking
- ✅ Professional CI/CD pipeline

**Production-ready! 🚀**
