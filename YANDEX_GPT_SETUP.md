# 🤖 Настройка Яндекс GPT для блога

## Два способа использования Яндекс GPT

### Способ 1: API ключ (рекомендуется)

#### Шаг 1: Получить API ключ

1. Откройте [Yandex Cloud Console](https://console.cloud.yandex.ru/)
2. Выберите каталог (folder)
3. Перейдите в раздел **Service accounts** (Сервисные аккаунты)
4. Создайте сервисный аккаунт с ролью `ai.languageModels.user`
5. Создайте API ключ для этого аккаунта

#### Шаг 2: Настроить переменные окружения

```bash
# В файле .env или напрямую в терминале
export YANDEX_API_KEY="AQVNxxxxx..."
export YANDEX_FOLDER_ID="b1gxxxxx..."
```

Где взять `FOLDER_ID`:
- В консоли Yandex Cloud откройте ваш каталог
- ID каталога будет в URL: `https://console.cloud.yandex.ru/folders/b1gxxxxx...`

### Способ 2: IAM токен

```bash
# Получить IAM токен
yc iam create-token

# Установить в переменные окружения
export YANDEX_IAM_TOKEN="t1.9euelZrOy..."
export YANDEX_FOLDER_ID="b1gxxxxx..."
```

## Если у вас уже есть ключи в другом проекте

### Вариант A: Скопировать из ai-calendar-assistant

```bash
# Если ai-calendar-assistant находится рядом
cd ../ai-calendar-assistant
cat .env | grep YANDEX

# Скопировать значения в cian-analyzer/.env
```

### Вариант B: Использовать те же ключи

Яндекс GPT API ключи можно использовать в нескольких проектах одновременно.

Просто скопируйте значения `YANDEX_API_KEY` и `YANDEX_FOLDER_ID` из вашего другого проекта.

## Проверка настройки

### Тест 1: Через Python

```python
import os
from src.blog import YandexGPTRewriter

# Проверка переменных окружения
print("API Key:", os.getenv('YANDEX_API_KEY')[:20] + "..." if os.getenv('YANDEX_API_KEY') else "НЕ УСТАНОВЛЕН")
print("Folder ID:", os.getenv('YANDEX_FOLDER_ID'))

# Тест рерайтера
rewriter = YandexGPTRewriter()
result = rewriter.rewrite_article(
    original_content="Это тестовая статья о недвижимости.",
    title="Тестовая статья"
)
print("Результат рерайта:", result[:100] + "...")
```

### Тест 2: Через curl

```bash
curl -X POST https://llm.api.cloud.yandex.net/foundationModels/v1/completion \
  -H "Content-Type: application/json" \
  -H "Authorization: Api-Key ${YANDEX_API_KEY}" \
  -d '{
    "modelUri": "gpt://'${YANDEX_FOLDER_ID}'/yandexgpt-lite",
    "completionOptions": {
      "stream": false,
      "temperature": 0.7,
      "maxTokens": 100
    },
    "messages": [
      {
        "role": "user",
        "text": "Привет! Как дела?"
      }
    ]
  }'
```

## Модели Яндекс GPT

В текущей реализации используется `yandexgpt-lite` - это быстрая и дешевая модель.

Доступные модели:
- `yandexgpt-lite` - быстрая модель для простых задач
- `yandexgpt` - стандартная модель (дороже)
- `yandexgpt-32k` - модель с большим контекстом

Чтобы изменить модель, отредактируйте `src/blog/yandex_gpt_rewriter.py`:

```python
data = {
    "modelUri": f"gpt://{self.folder_id}/yandexgpt",  # Вместо yandexgpt-lite
    ...
}
```

## Лимиты и цены

- **yandexgpt-lite**: ~0.4₽ за 1000 токенов
- **yandexgpt**: ~1.2₽ за 1000 токенов

Средняя статья (~2000 токенов) обойдется в:
- yandexgpt-lite: ~0.8₽
- yandexgpt: ~2.4₽

Генерация 100 статей в месяц:
- yandexgpt-lite: ~80₽
- yandexgpt: ~240₽

## Работа без Яндекс GPT

Если не настроить Яндекс GPT, система будет работать в fallback режиме:

1. Статьи будут парситься с Cian Magazine
2. Контент будет очищен от HTML
3. Добавится базовая HTML разметка (параграфы, заголовки)
4. Статьи сохранятся БЕЗ рерайтинга

Это подходит для:
- Тестирования системы
- Разработки без затрат
- Создания черновиков для ручного редактирования

## Альтернативные варианты рерайтинга

### OpenAI GPT

Можно заменить Яндекс GPT на OpenAI GPT-4:

```python
# В src/blog/openai_rewriter.py
import openai

class OpenAIRewriter:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        openai.api_key = self.api_key

    def rewrite_article(self, original_content, title):
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты профессиональный копирайтер..."},
                {"role": "user", "content": f"Перепиши статью: {original_content}"}
            ]
        )
        return response.choices[0].message.content
```

### Gigachat (Сбер)

```python
# pip install gigachat
from gigachat import GigaChat

class GigaChatRewriter:
    def __init__(self, credentials=None):
        self.credentials = credentials or os.getenv('GIGACHAT_CREDENTIALS')
        self.client = GigaChat(credentials=self.credentials)

    def rewrite_article(self, original_content, title):
        response = self.client.chat(f"Перепиши эту статью: {original_content}")
        return response.choices[0].message.content
```

## Устранение проблем

### Ошибка: "Invalid API key"

```bash
# Проверьте что API ключ установлен
echo $YANDEX_API_KEY

# Проверьте что ключ не содержит лишних пробелов
export YANDEX_API_KEY="$(echo $YANDEX_API_KEY | tr -d ' \n')"
```

### Ошибка: "Folder not found"

```bash
# Проверьте FOLDER_ID
echo $YANDEX_FOLDER_ID

# ID должен начинаться с b1g
# Пример: b1g12345abcde
```

### Ошибка: "Quota exceeded"

Превышен лимит запросов. Подождите или увеличьте квоту в консоли Yandex Cloud.

### Ошибка: "Permission denied"

Сервисный аккаунт должен иметь роль `ai.languageModels.user`.

Проверьте в консоли: Service accounts → Ваш аккаунт → Roles

## Дополнительные ресурсы

- [Документация Yandex GPT](https://cloud.yandex.ru/docs/yandexgpt/)
- [API Reference](https://cloud.yandex.ru/docs/yandexgpt/api-ref/)
- [Примеры использования](https://cloud.yandex.ru/docs/yandexgpt/quickstart)
- [Тарифы](https://cloud.yandex.ru/docs/yandexgpt/pricing)
