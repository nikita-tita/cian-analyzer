# Деплой Cian Analyzer (housler.ru)

> **Последнее обновление:** 2026-01-08

---

## Сервер

| Параметр | Значение |
|----------|----------|
| **IP** | 95.163.227.26 |
| **SSH** | `ssh root@95.163.227.26` |
| **Пароль** | `NsUurH93jSHNW8QS` |
| **Путь** | `/root/cian-analyzer` |
| **URL** | https://housler.ru |
| **Порт** | 5000 |

> **Главный документ:** [housler_pervichka/DEPLOY.md](../housler_pervichka/DEPLOY.md)
> **Доступ к серверу:** [SHARED/SERVER_ACCESS.md](../housler_pervichka/docs/SHARED/SERVER_ACCESS.md)

---

## Контейнеры

| Контейнер | Описание | Порт |
|-----------|----------|------|
| `housler-app` | Python Flask приложение | 5000 |
| `housler-redis` | Redis (порт 6380) | 6380 |

---

## Быстрый деплой

```bash
# С локальной машины
ssh root@95.163.227.26 "cd /root/cian-analyzer && git pull && docker compose up -d --build"

# Или на сервере
cd /root/cian-analyzer
git pull
docker compose up -d --build
```

---

## Проверка

```bash
# Статус сайта
curl -s -o /dev/null -w "%{http_code}" https://housler.ru/

# Статус контейнеров
docker ps | grep housler

# Логи
docker logs housler-app --tail 100 -f
```

---

## Структура на сервере

```
/root/cian-analyzer/
├── app.py               # Flask приложение
├── docker-compose.yml   # Docker конфиг
├── Dockerfile           # Образ приложения
├── requirements.txt     # Python зависимости
├── templates/           # HTML шаблоны
├── static/              # Статические файлы
└── parsers/             # Парсеры CIAN
```

---

## Откат

```bash
cd /root/cian-analyzer
git log --oneline -5
git checkout <commit-hash>
docker compose up -d --build
```

---

## Troubleshooting

### Приложение не запускается

```bash
docker logs housler-app --tail 50
docker exec housler-app pip install -r requirements.txt
```

### Redis не работает

```bash
docker logs housler-redis --tail 50
docker restart housler-redis
```

---

## Связанные документы

- [housler_pervichka/DEPLOY.md](../housler_pervichka/DEPLOY.md) — Главный гайд
- [SHARED/DOCKER_GUIDE.md](../housler_pervichka/docs/SHARED/DOCKER_GUIDE.md) — Docker команды

---

*Обновлено: 2026-01-08*
