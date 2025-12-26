# AWS Lambda Parser

Serverless парсер Cian с поддержкой Decodo SOCKS5 прокси.

## Зачем нужен

VPS в России заблокирован Decodo (санкции с марта 2022). Lambda в EU регионе работает с прокси без ограничений.

## Архитектура

```
VPS (housler.ru)                    AWS Lambda (eu-central-1)
     |                                      |
     | 1. POST /parse {url}                 |
     +------------------------------------->|
     |                                      | 2. Fetch via Decodo proxy
     |                                      +----> ru.decodo.com:40000
     |                                      |           |
     |                                      |<----------+
     | 4. Return parsed data                | 3. Parse HTML
     |<-------------------------------------+
     |                                      |
```

## Требования

- AWS Account
- AWS CLI configured
- SAM CLI installed

## Установка AWS CLI

```bash
# macOS
brew install awscli aws-sam-cli

# Linux
pip install awscli aws-sam-cli

# Настройка
aws configure
# Ввести: Access Key ID, Secret Access Key, Region (eu-central-1)
```

## Деплой

### 1. Создать секрет в Secrets Manager

```bash
aws secretsmanager create-secret \
    --name decodo/proxy-prod \
    --region eu-central-1 \
    --secret-string '{
        "host": "ru.decodo.com",
        "port": 40000,
        "username": "YOUR_DECODO_USER",
        "password": "YOUR_DECODO_PASS",
        "protocol": "socks5"
    }'
```

### 2. Сборка и деплой

```bash
cd lambda

# Сборка
sam build

# Деплой (первый раз - guided)
sam deploy --guided

# Ответы на вопросы:
# Stack Name: housler-parser
# Region: eu-central-1
# Confirm changes: Y
# Allow SAM to create IAM roles: Y
# Save arguments: Y
```

### 3. Получить URL

После деплоя SAM выведет:
```
Outputs:
ApiUrl: https://xxx.execute-api.eu-central-1.amazonaws.com/Prod/parse
```

### 4. Настроить VPS

Добавить в `.env` на сервере:
```
LAMBDA_PARSER_URL=https://xxx.execute-api.eu-central-1.amazonaws.com/Prod/parse
```

## Тестирование

### Локально

```bash
cd lambda

# Установить зависимости
pip install -r requirements.txt

# Тест без прокси
python lambda_parser.py

# Тест handler
python handler.py
```

### Через curl

```bash
curl -X POST https://xxx.execute-api.eu-central-1.amazonaws.com/Prod/parse \
  -H "Content-Type: application/json" \
  -d '{"url": "https://spb.cian.ru/sale/flat/316296015/"}'
```

## Использование в коде

```python
from src.services import lambda_client

# Парсинг через Lambda
result = lambda_client.parse("https://spb.cian.ru/sale/flat/123/")
if result:
    print(result['title'], result['price'])
```

## Стоимость

~$1-3/месяц при 100-500 парсингов/день:
- Lambda: ~$0.20/1M requests
- API Gateway: ~$3.50/1M requests
- Secrets Manager: ~$0.40/secret/month

## Обновление

```bash
cd lambda
sam build
sam deploy
```

## Удаление

```bash
sam delete --stack-name housler-parser
```
