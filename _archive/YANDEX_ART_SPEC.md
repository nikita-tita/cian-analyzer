# ТЗ: Генерация обложек для блога через YandexART API

## Обзор

Автоматическая генерация уникальных обложек для статей блога HOUSLER. Обложки в едином черно-белом стиле (карандашный скетч + Pixar-like 3D) интегрируются в существующий поток публикации статей.

---

## Архитектура интеграции

### Текущий поток (без обложек)

```
Источник → Парсер → YandexGPT → BlogDatabase.create_post() → TelegramPublisher
                                        ↓
                                   blog_posts (SQLite)
                                        ↓
                                   Flask Routes → Шаблоны
```

### Новый поток (с обложками)

```
Источник → Парсер → YandexGPT → YandexART → BlogDatabase.create_post()
                                    ↓                    ↓
                              /static/blog/covers/   blog_posts (+ cover_image)
                                    ↓                    ↓
                              TelegramPublisher ← ← ← ← ←
                              (sendPhoto + caption)
                                    ↓
                              Flask Routes → Шаблоны (img)
```

---

## Часть 1: Модуль yandex_art.py

### 1.1 Расположение

```
/Users/fatbookpro/cian-analyzer/yandex_art.py
```

Рядом с существующим `yandex_gpt.py` — единый паттерн для Yandex API интеграций.

### 1.2 Зависимости

Уже есть в `requirements.txt`:
- `requests>=2.31.0`

Новые не требуются (base64, time, os — стандартная библиотека).

### 1.3 Полный код модуля

```python
"""
YandexART Integration for Blog Cover Generation

Генерирует черно-белые обложки в едином стиле:
- Карандашный скетч + Pixar-like 3D объекты
- Формат 16:9
- Без текста и символов
"""

import os
import time
import base64
import random
import requests
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class YandexART:
    """
    Генератор обложек через YandexART API

    Использует те же credentials что и YandexGPT:
    - YANDEX_API_KEY
    - YANDEX_FOLDER_ID
    """

    # Единый стиль для всех обложек блога
    PROMPT_TEMPLATE = '''"{title}" Create an illustration in a mixed style: hand-drawn pencil sketch + Pixar-like 3D object but entirely in black and white, in a 16:9 aspect ratio. All elements must be grayscale only — no color, no tint, no warm tones. Represent modern apartment buildings as stylized 3D objects with soft Pixar-like volume, but rendered strictly in monochrome with realistic pencil shading. Surround them with hand-drawn pencil sketch lines showing market dynamics, arrows, rising graphs. The pencil part should look natural, imperfect, textured. The 3D part should look smooth, volumetric, slightly stylized, but strictly grayscale. No text, no captions, no symbols resembling letters. Soft clean background, balanced wide composition suited for 16:9, high detail, high resolution.'''

    def __init__(self, covers_dir: str = "static/blog/covers"):
        """
        Args:
            covers_dir: Директория для сохранения обложек (относительно корня проекта)
        """
        self.api_key = os.getenv('YANDEX_API_KEY')
        self.folder_id = os.getenv('YANDEX_FOLDER_ID')

        # API endpoints
        self.generation_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
        self.operations_url = "https://llm.api.cloud.yandex.net/operations"

        # Настройки
        self.enabled = os.getenv('YANDEX_ART_ENABLED', 'true').lower() == 'true'
        self.timeout = int(os.getenv('YANDEX_ART_TIMEOUT', '60'))
        self.poll_interval = 2  # секунды между проверками статуса

        # Директория для обложек
        self.covers_dir = Path(covers_dir)

        if self.enabled and (not self.api_key or not self.folder_id):
            logger.warning("YandexART: YANDEX_API_KEY or YANDEX_FOLDER_ID not set, disabling")
            self.enabled = False

    def ensure_covers_dir(self):
        """Создает директорию для обложек если не существует"""
        self.covers_dir.mkdir(parents=True, exist_ok=True)

    def generate_cover(
        self,
        title: str,
        slug: str,
        force: bool = False
    ) -> Optional[str]:
        """
        Генерирует обложку для статьи

        Args:
            title: Заголовок статьи (используется в промпте)
            slug: URL slug статьи (используется как имя файла)
            force: Перезаписать если файл уже существует

        Returns:
            Относительный путь к обложке ("/static/blog/covers/<slug>.png")
            или None при ошибке/отключении
        """
        if not self.enabled:
            logger.debug("YandexART disabled, skipping cover generation")
            return None

        self.ensure_covers_dir()

        # Проверяем существование файла
        filepath = self.covers_dir / f"{slug}.png"
        if filepath.exists() and not force:
            logger.info(f"Cover already exists: {filepath}")
            return f"/static/blog/covers/{slug}.png"

        try:
            logger.info(f"Generating cover for: {title[:50]}...")

            # 1. Запускаем генерацию
            operation_id = self._start_generation(title)
            if not operation_id:
                return None

            # 2. Ждем результат
            image_base64 = self._wait_for_result(operation_id)
            if not image_base64:
                return None

            # 3. Сохраняем файл
            return self._save_image(image_base64, slug)

        except requests.exceptions.Timeout:
            logger.error(f"YandexART request timeout for '{title[:30]}...'")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"YandexART request error: {e}")
            return None
        except Exception as e:
            logger.error(f"YandexART unexpected error: {e}")
            return None

    def _start_generation(self, title: str) -> Optional[str]:
        """
        Отправляет запрос на генерацию изображения

        Returns:
            operation_id для отслеживания или None при ошибке
        """
        prompt = self.PROMPT_TEMPLATE.format(title=title)

        payload = {
            "modelUri": f"art://{self.folder_id}/yandex-art/latest",
            "generationOptions": {
                "seed": random.randint(1, 1_000_000),
                "aspectRatio": {
                    "widthRatio": 16,
                    "heightRatio": 9
                }
            },
            "messages": [
                {
                    "weight": 1,
                    "text": prompt
                }
            ]
        }

        response = requests.post(
            self.generation_url,
            headers={
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"YandexART API error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()
        operation_id = data.get("id")

        if not operation_id:
            logger.error(f"YandexART: no operation_id in response: {data}")
            return None

        logger.debug(f"YandexART generation started: {operation_id}")
        return operation_id

    def _wait_for_result(self, operation_id: str) -> Optional[str]:
        """
        Ожидает завершения генерации (polling)

        Returns:
            base64-encoded изображение или None при ошибке/таймауте
        """
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            response = requests.get(
                f"{self.operations_url}/{operation_id}",
                headers={"Authorization": f"Api-Key {self.api_key}"},
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"YandexART status check failed: {response.status_code}")
                return None

            data = response.json()

            if data.get("done"):
                # Проверяем на ошибку генерации
                if "error" in data:
                    error = data["error"]
                    logger.error(f"YandexART generation failed: {error.get('message', error)}")
                    return None

                # Извлекаем изображение
                image_base64 = data.get("response", {}).get("image")
                if image_base64:
                    elapsed = time.time() - start_time
                    logger.info(f"YandexART generation completed in {elapsed:.1f}s")
                    return image_base64
                else:
                    logger.error("YandexART: no image in response")
                    return None

            time.sleep(self.poll_interval)

        logger.warning(f"YandexART generation timeout after {self.timeout}s")
        return None

    def _save_image(self, image_base64: str, slug: str) -> str:
        """
        Сохраняет base64 изображение в файл

        Returns:
            Относительный путь для использования в HTML/БД
        """
        image_data = base64.b64decode(image_base64)

        filename = f"{slug}.png"
        filepath = self.covers_dir / filename

        with open(filepath, "wb") as f:
            f.write(image_data)

        relative_path = f"/static/blog/covers/{filename}"
        logger.info(f"Saved cover: {relative_path} ({len(image_data) / 1024:.1f} KB)")

        return relative_path

    def cover_exists(self, slug: str) -> bool:
        """Проверяет существование обложки"""
        return (self.covers_dir / f"{slug}.png").exists()

    def get_cover_path(self, slug: str) -> Optional[str]:
        """Возвращает путь к обложке если существует"""
        if self.cover_exists(slug):
            return f"/static/blog/covers/{slug}.png"
        return None
```

---

## Часть 2: Изменения в blog_database.py

### 2.1 Миграция схемы

Добавить в метод `init_db()` после существующих миграций (строка ~65):

```python
# Add cover_image column if it doesn't exist (migration)
try:
    c.execute('ALTER TABLE blog_posts ADD COLUMN cover_image TEXT DEFAULT NULL')
except sqlite3.OperationalError:
    pass  # Column already exists
```

### 2.2 Обновление create_post()

Изменить сигнатуру метода `create_post()` (строка ~69):

**Было:**
```python
def create_post(
    self,
    slug: str,
    title: str,
    content: str,
    excerpt: Optional[str] = None,
    original_url: Optional[str] = None,
    original_title: Optional[str] = None,
    published_at: Optional[str] = None,
    telegram_post_type: Optional[str] = None
) -> int:
```

**Стало:**
```python
def create_post(
    self,
    slug: str,
    title: str,
    content: str,
    excerpt: Optional[str] = None,
    original_url: Optional[str] = None,
    original_title: Optional[str] = None,
    published_at: Optional[str] = None,
    telegram_post_type: Optional[str] = None,
    cover_image: Optional[str] = None  # Новый параметр
) -> int:
```

Обновить SQL INSERT (строка ~92):

**Было:**
```python
c.execute('''
    INSERT INTO blog_posts
    (slug, title, excerpt, content, original_url, original_title,
     published_at, created_at, updated_at, telegram_post_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (slug, title, excerpt, content, original_url, original_title,
      published_at, now, now, telegram_post_type))
```

**Стало:**
```python
c.execute('''
    INSERT INTO blog_posts
    (slug, title, excerpt, content, original_url, original_title,
     published_at, created_at, updated_at, telegram_post_type, cover_image)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (slug, title, excerpt, content, original_url, original_title,
      published_at, now, now, telegram_post_type, cover_image))
```

### 2.3 Новый метод update_cover_image()

Добавить после метода `mark_telegram_published()` (строка ~247):

```python
def update_cover_image(self, post_id: int, cover_image: str):
    """Update cover image for existing post"""
    conn = sqlite3.connect(self.db_path)
    c = conn.cursor()

    c.execute('''
        UPDATE blog_posts
        SET cover_image = ?, updated_at = ?
        WHERE id = ?
    ''', (cover_image, datetime.now().isoformat(), post_id))

    conn.commit()
    conn.close()

def get_posts_without_cover(self, limit: int = 10) -> List[Dict]:
    """Get posts that don't have cover images"""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('''
        SELECT * FROM blog_posts
        WHERE is_published = 1 AND (cover_image IS NULL OR cover_image = '')
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))

    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]
```

---

## Часть 3: Изменения в blog_cli.py

### 3.1 Импорты

Добавить в начало файла (строка ~15):

```python
from yandex_art import YandexART
```

### 3.2 Интеграция в процесс парсинга

Найти функцию обработки статей (примерно строка ~150-200, где вызывается `db.create_post()`).

**Добавить генерацию обложки перед сохранением:**

```python
# После рерайта через YandexGPT, перед create_post()

# Генерируем обложку (не блокирует публикацию при ошибке)
cover_image = None
try:
    art = YandexART()
    cover_image = art.generate_cover(
        title=rewritten['title'],
        slug=slug
    )
except Exception as e:
    logger.warning(f"Cover generation failed, continuing without cover: {e}")

# Сохраняем в БД
post_id = db.create_post(
    slug=slug,
    title=rewritten['title'],
    content=rewritten['content'],
    excerpt=rewritten['excerpt'],
    original_url=article['url'],
    original_title=article['title'],
    cover_image=cover_image  # Новый параметр
)
```

### 3.3 Новые CLI команды

Добавить в конец файла (перед `if __name__ == "__main__":`):

```python
@click.command()
@click.argument('slug')
@click.option('--force', is_flag=True, help='Regenerate even if cover exists')
def generate_cover(slug: str, force: bool):
    """Generate cover image for a specific post"""
    db = BlogDatabase()
    post = db.get_post_by_slug(slug)

    if not post:
        click.echo(f"Post not found: {slug}", err=True)
        return

    art = YandexART()

    if not art.enabled:
        click.echo("YandexART is disabled (check YANDEX_API_KEY and YANDEX_FOLDER_ID)", err=True)
        return

    click.echo(f"Generating cover for: {post['title'][:50]}...")

    cover_path = art.generate_cover(
        title=post['title'],
        slug=slug,
        force=force
    )

    if cover_path:
        db.update_cover_image(post['id'], cover_path)
        click.echo(f"Cover saved: {cover_path}")
    else:
        click.echo("Cover generation failed", err=True)


@click.command()
@click.option('--limit', default=10, help='Maximum posts to process')
@click.option('--delay', default=5, help='Delay between generations (seconds)')
def generate_all_covers(limit: int, delay: int):
    """Generate covers for all posts without covers"""
    db = BlogDatabase()
    art = YandexART()

    if not art.enabled:
        click.echo("YandexART is disabled", err=True)
        return

    posts = db.get_posts_without_cover(limit=limit)

    if not posts:
        click.echo("All posts already have covers")
        return

    click.echo(f"Found {len(posts)} posts without covers")

    success = 0
    failed = 0

    for i, post in enumerate(posts, 1):
        click.echo(f"\n[{i}/{len(posts)}] {post['title'][:40]}...")

        cover_path = art.generate_cover(
            title=post['title'],
            slug=post['slug']
        )

        if cover_path:
            db.update_cover_image(post['id'], cover_path)
            click.echo(f"  OK: {cover_path}")
            success += 1
        else:
            click.echo(f"  FAILED")
            failed += 1

        # Задержка между запросами (rate limiting)
        if i < len(posts):
            time.sleep(delay)

    click.echo(f"\nDone: {success} generated, {failed} failed")


# Добавить команды в группу cli
cli.add_command(generate_cover)
cli.add_command(generate_all_covers)
```

---

## Часть 4: Изменения в telegram_publisher.py

### 4.1 Ограничения Telegram API

| Метод | Лимит текста | Использование |
|-------|--------------|---------------|
| `sendMessage` | 4096 символов | Текущий формат (3100-3400 символов) |
| `sendPhoto` caption | **1024 символа** | Новый формат с картинкой |

**Важно:** При отправке фото с обложкой мы ограничены 1024 символами caption.

### 4.2 Формат сообщения с картинкой

```
┌─────────────────────────────────┐
│         [ОБЛОЖКА 16:9]          │
│                                 │
├─────────────────────────────────┤
│ <b>Заголовок статьи</b>         │
│                                 │
│ Краткое превью статьи,          │
│ обрезанное по границе           │
│ предложения...                  │
│                                 │
│ Читать полностью на сайте →     │
└─────────────────────────────────┘
```

**Структура caption (до 1020 символов):**
- Заголовок (bold): ~80-150 символов
- Превью текста: ~700-800 символов
- Ссылка "Читать полностью на сайте": ~60 символов
- Переносы строк и отступы: ~20 символов

### 4.3 Новый метод publish_post_with_image()

Добавить после метода `publish_post()` (строка ~91):

```python
def publish_post_with_image(
    self,
    title: str,
    content: str,
    slug: str,
    cover_image: Optional[str] = None,
    excerpt: Optional[str] = None
) -> bool:
    """
    Publish blog post to Telegram channel with cover image

    Telegram sendPhoto caption limit: 1024 characters
    We use 1020 as safe limit.

    Format:
    - Bold title
    - Short preview (truncated at sentence boundary)
    - Link to full article on blog

    If cover_image is not provided or file not found,
    falls back to text-only publish_post() with full 3400 chars.

    Args:
        title: Article title
        content: Full article content
        slug: URL slug for the article
        cover_image: Path to cover image (e.g., "/static/blog/covers/slug.png")
        excerpt: Optional custom excerpt

    Returns:
        True if published successfully, False otherwise
    """
    if not self.bot_token:
        logger.warning("Telegram publishing skipped - no bot token")
        return False

    # Если нет обложки — используем текстовый метод (3400 символов)
    if not cover_image:
        return self.publish_post(title, content, slug, excerpt)

    # Проверяем существование файла
    image_path = cover_image.lstrip('/')  # "/static/..." -> "static/..."
    if not os.path.exists(image_path):
        logger.warning(f"Cover image not found: {image_path}, falling back to text")
        return self.publish_post(title, content, slug, excerpt)

    try:
        article_url = f"{self.site_url}/blog/{slug}"

        # Формируем caption с жестким лимитом 1020 символов
        caption = self._build_photo_caption(title, content, excerpt, article_url)

        # Отправляем фото
        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

        with open(image_path, 'rb') as photo:
            response = requests.post(
                api_url,
                data={
                    "chat_id": self.channel_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                },
                files={
                    "photo": photo
                },
                timeout=60  # больший таймаут для загрузки файла
            )

        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info(f"Published to Telegram with image: {title[:50]}...")
                return True
            else:
                logger.error(f"Telegram API error: {result.get('description')}")
                # Fallback к тексту
                return self.publish_post(title, content, slug, excerpt)
        else:
            logger.error(f"Telegram API HTTP error: {response.status_code}")
            return self.publish_post(title, content, slug, excerpt)

    except Exception as e:
        logger.error(f"Failed to publish with image: {e}")
        # Fallback к текстовому посту
        return self.publish_post(title, content, slug, excerpt)


def _build_photo_caption(
    self,
    title: str,
    content: str,
    excerpt: Optional[str],
    article_url: str
) -> str:
    """
    Build caption for photo post with 1020 char limit

    Structure:
    <b>Title</b>

    Preview text truncated at sentence boundary...

    <a href="url">Читать полностью на сайте</a>
    """
    MAX_CAPTION = 1020  # Безопасный лимит (Telegram: 1024)

    # Фиксированные части
    link_text = f'<a href="{article_url}">Читать полностью на сайте</a>'
    title_formatted = f"<b>{title}</b>"

    # Считаем доступное место для превью
    # title + \n\n + preview + \n\n + link
    fixed_length = len(title_formatted) + len(link_text) + 4  # 4 = два "\n\n"
    max_preview_length = MAX_CAPTION - fixed_length

    # Получаем превью
    if excerpt and len(excerpt) <= max_preview_length:
        preview = excerpt
    else:
        # Генерируем превью из контента
        preview = self._generate_short_preview(content, max_preview_length)

    # Собираем caption
    caption = f"{title_formatted}\n\n{preview}\n\n{link_text}"

    # Финальная проверка длины
    if len(caption) > MAX_CAPTION:
        # Аварийное обрезание превью
        overflow = len(caption) - MAX_CAPTION
        preview = preview[:len(preview) - overflow - 3] + "..."
        caption = f"{title_formatted}\n\n{preview}\n\n{link_text}"

    return caption


def _generate_short_preview(self, content: str, max_length: int) -> str:
    """
    Generate short preview for photo caption

    - Removes promotional content (HOUSLER mentions, CTAs)
    - Truncates at sentence boundary
    - Max length enforced
    """
    # Разбиваем на параграфы
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

    if not paragraphs:
        return content[:max_length]

    # Фильтруем промо-контент
    skip_words = [
        'housler', 'оставьте заявку', 'свяжется с вами',
        'агентство', '[оставьте заявку]', 'эксперт свяжется'
    ]

    content_paragraphs = []
    for paragraph in paragraphs:
        if any(word in paragraph.lower() for word in skip_words):
            continue
        content_paragraphs.append(paragraph)

    if not content_paragraphs:
        content_paragraphs = paragraphs[:2]  # fallback

    # Собираем текст до лимита
    result = ''
    for paragraph in content_paragraphs:
        test_result = result + ('\n\n' if result else '') + paragraph

        if len(test_result) > max_length:
            # Обрезаем текущий параграф
            remaining = max_length - len(result) - (2 if result else 0)
            if remaining > 50:
                partial = paragraph[:remaining]
                # Ищем конец предложения
                for char in '.!?':
                    pos = partial.rfind(char)
                    if pos > remaining * 0.5:
                        result += ('\n\n' if result else '') + partial[:pos + 1]
                        break
                else:
                    # Нет конца предложения — обрезаем по слову
                    last_space = partial.rfind(' ')
                    if last_space > remaining * 0.5:
                        result += ('\n\n' if result else '') + partial[:last_space] + '...'
            break
        else:
            result = test_result

    return result.strip() or content[:max_length]
```

### 4.4 Обновить импорты

Добавить в начало файла (если еще нет):

```python
import os
```

### 4.5 Сравнение форматов

| Параметр | Без картинки | С картинкой |
|----------|--------------|-------------|
| Метод | `sendMessage` | `sendPhoto` |
| Лимит | 4096 символов | 1024 символа |
| Используем | 3100-3400 | **до 1020** |
| Превью | 60-70% статьи | Краткое (700-800 символов) |
| Визуал | Только текст | Обложка + текст |
| Ссылка | "Читать полностью на сайте" | "Читать полностью на сайте" |
| Fallback | — | При ошибке → sendMessage |

---

## Часть 5: Изменения в шаблонах

### 5.1 templates/blog_post.html

Найти секцию `<header class="blog-post-header">` (примерно строка ~180) и добавить обложку:

```html
<header class="blog-post-header">
    {% if post.cover_image %}
    <div class="blog-post-cover">
        <img src="{{ post.cover_image }}"
             alt="{{ post.title }}"
             class="blog-cover-image"
             loading="lazy">
    </div>
    {% endif %}

    <span class="blog-post-meta">{{ post.published_at[:10] }}</span>
    <h1 class="blog-post-title">{{ post.title }}</h1>
    {% if post.excerpt %}
    <p class="blog-post-excerpt">{{ post.excerpt }}</p>
    {% endif %}
</header>
```

### 5.2 templates/blog_index.html

Найти блок `<article class="blog-entry">` и добавить миниатюру:

```html
<a href="/blog/{{ post.slug }}" class="blog-entry-link">
    <article class="blog-entry">
        {% if post.cover_image %}
        <div class="blog-entry-cover">
            <img src="{{ post.cover_image }}"
                 alt="{{ post.title }}"
                 class="blog-entry-image"
                 loading="lazy">
        </div>
        {% endif %}
        <div class="blog-entry-content">
            <div class="blog-entry-meta">{{ post.published_at[:10] }}</div>
            <h3 class="blog-entry-title">{{ post.title }}</h3>
            <p class="blog-entry-excerpt">{{ post.excerpt }}</p>
        </div>
    </article>
</a>
```

### 5.3 Open Graph мета-теги

Добавить в `<head>` секцию `blog_post.html`:

```html
{% if post.cover_image %}
<meta property="og:image" content="{{ request.url_root.rstrip('/') }}{{ post.cover_image }}">
<meta property="og:image:width" content="1920">
<meta property="og:image:height" content="1080">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{{ request.url_root.rstrip('/') }}{{ post.cover_image }}">
{% endif %}
```

---

## Часть 6: CSS стили

### 6.1 Добавить в static/css/blog-post.css

```css
/* ===== Blog Cover Image ===== */

.blog-post-cover {
    margin-bottom: 2rem;
    border-radius: var(--border-radius-md);
    overflow: hidden;
}

.blog-cover-image {
    width: 100%;
    height: auto;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    display: block;
}

/* Мобильная версия */
@media (max-width: 768px) {
    .blog-post-cover {
        margin: -1rem -1rem 1.5rem -1rem;
        border-radius: 0;
    }
}
```

### 6.2 Добавить в static/css/blog-minimal.css

```css
/* ===== Blog Entry Covers (List View) ===== */

.blog-entry {
    display: flex;
    flex-direction: column;
}

.blog-entry-cover {
    margin: -2rem -2rem 1.5rem -2rem;
    overflow: hidden;
}

.blog-entry-image {
    width: 100%;
    height: auto;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    display: block;
    transition: transform var(--transition-base);
}

.blog-entry:hover .blog-entry-image {
    transform: scale(1.03);
}

.blog-entry-content {
    flex: 1;
}

/* Без обложки — старый стиль */
.blog-entry:not(:has(.blog-entry-cover)) {
    padding-top: 2rem;
}

/* Fallback для браузеров без :has() */
@supports not selector(:has(*)) {
    .blog-entry {
        padding-top: 2rem;
    }
    .blog-entry-cover + .blog-entry-content {
        padding-top: 0;
    }
    .blog-entry:has(.blog-entry-cover) {
        padding-top: 0;
    }
}
```

---

## Часть 7: Конфигурация

### 7.1 Обновить .env.example

Добавить после секции Yandex GPT:

```env
# Yandex ART (Cover Image Generation)
# Uses same YANDEX_API_KEY and YANDEX_FOLDER_ID as GPT
YANDEX_ART_ENABLED=true
YANDEX_ART_TIMEOUT=60
```

### 7.2 Создать директорию

```bash
mkdir -p static/blog/covers
touch static/blog/covers/.gitkeep
```

### 7.3 Обновить .gitignore

Добавить:

```
# Blog covers (generated, not in git)
static/blog/covers/*.png
!static/blog/covers/.gitkeep
```

---

## Часть 8: Интеграция в автоматический парсинг

### 8.1 auto_blog_daemon.py

Обложки генерируются автоматически при парсинге через `blog_cli.py` (изменения в Части 3).

### 8.2 telegram_post_scheduler.py

Обновить вызов публикации (строка ~60):

**Было:**
```python
publisher.publish_post(
    title=post['title'],
    content=post['content'],
    slug=post['slug'],
    excerpt=post.get('excerpt')
)
```

**Стало:**
```python
publisher.publish_post_with_image(
    title=post['title'],
    content=post['content'],
    slug=post['slug'],
    cover_image=post.get('cover_image'),
    excerpt=post.get('excerpt')
)
```

---

## Часть 9: Тестирование

### 9.1 Ручное тестирование

```bash
# 1. Проверить credentials
python -c "from yandex_art import YandexART; print(YandexART().enabled)"

# 2. Сгенерировать тестовую обложку
python blog_cli.py generate-cover <existing-slug>

# 3. Проверить файл
ls -la static/blog/covers/

# 4. Проверить отображение на сайте
open http://localhost:5000/blog/<slug>

# 5. Тест Telegram с картинкой
python -c "
from telegram_publisher import TelegramPublisher
from blog_database import BlogDatabase
db = BlogDatabase()
post = db.get_post_by_slug('<slug>')
pub = TelegramPublisher()
pub.publish_post_with_image(
    post['title'], post['content'], post['slug'],
    post.get('cover_image'), post.get('excerpt')
)
"
```

### 9.2 Массовая генерация

```bash
# Сгенерировать обложки для 10 последних постов без обложек
python blog_cli.py generate-all-covers --limit 10 --delay 5
```

---

## Часть 10: План реализации (чеклист)

### Этап 1: Инфраструктура
- [ ] Создать `yandex_art.py`
- [ ] Создать директорию `static/blog/covers/`
- [ ] Добавить `.gitkeep` и обновить `.gitignore`
- [ ] Обновить `.env.example`

### Этап 2: База данных
- [ ] Добавить миграцию `cover_image` в `blog_database.py`
- [ ] Добавить параметр в `create_post()`
- [ ] Добавить метод `update_cover_image()`
- [ ] Добавить метод `get_posts_without_cover()`

### Этап 3: CLI
- [ ] Интегрировать генерацию в процесс парсинга (`blog_cli.py`)
- [ ] Добавить команду `generate-cover`
- [ ] Добавить команду `generate-all-covers`

### Этап 4: Telegram
- [ ] Добавить метод `publish_post_with_image()` в `telegram_publisher.py`
- [ ] Обновить `telegram_post_scheduler.py`

### Этап 5: Фронтенд
- [ ] Обновить `templates/blog_post.html`
- [ ] Обновить `templates/blog_index.html`
- [ ] Добавить OG мета-теги
- [ ] Добавить CSS стили в `blog-post.css`
- [ ] Добавить CSS стили в `blog-minimal.css`

### Этап 6: Тестирование
- [ ] Локальное тестирование генерации
- [ ] Тест отображения на сайте
- [ ] Тест Telegram публикации с картинкой
- [ ] Массовая генерация для существующих постов

### Этап 7: Деплой
- [ ] Коммит и пуш в main
- [ ] Деплой на production
- [ ] Проверка на housler.ru

---

## Оценка трудозатрат

| Этап | Файлы | Оценка |
|------|-------|--------|
| 1. Инфраструктура | yandex_art.py, dirs | ~150 строк |
| 2. База данных | blog_database.py | ~30 строк |
| 3. CLI | blog_cli.py | ~80 строк |
| 4. Telegram | telegram_publisher.py, scheduler | ~60 строк |
| 5. Фронтенд | templates, CSS | ~80 строк |
| **Итого** | 7 файлов | ~400 строк |

---

## Стоимость

- YandexART: ~0.04 руб/изображение
- При 10 статьях/день: ~12 руб/месяц
- При 30 статьях/день: ~36 руб/месяц

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| API недоступен | Graceful degradation — статья публикуется без обложки |
| Таймаут генерации | 60 сек лимит, не блокирует процесс |
| Нет места на диске | Логирование размера, мониторинг |
| Rate limiting от Yandex | 5 сек задержка между запросами |
| Некачественная картинка | Единый промпт, проверенный стиль |
