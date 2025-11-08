# GitHub Configuration

Эта директория содержит конфигурацию для GitHub Actions CI/CD и других GitHub features.

## 📁 Структура

```
.github/
├── workflows/              # GitHub Actions workflows
│   ├── test.yml           # Автоматическое тестирование
│   ├── security.yml       # Security scanning
│   ├── code-quality.yml   # Code quality checks
│   ├── deploy.yml.template # Deployment template
│   └── README.md          # Документация workflows
└── README.md              # Этот файл
```

## 🚀 Quick Start

1. **Workflows активируются автоматически** после push в репозиторий
2. Проверьте статус в разделе **Actions**
3. Для деплоя настройте `deploy.yml.template`

## 📚 Документация

Подробная документация по каждому workflow в:
→ `.github/workflows/README.md`

## 🎯 Основные функции

- ✅ Автоматические тесты на каждый PR
- ✅ Security scanning (Bandit, Safety, Semgrep, CodeQL)
- ✅ Code quality enforcement (Flake8, Black, MyPy)
- ✅ Coverage tracking
- ✅ Deployment template

## 🔗 Полезные ссылки

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Security Best Practices](https://docs.github.com/en/actions/security-guides)
