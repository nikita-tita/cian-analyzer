"""
Telegram бот для Housler
Отправляет PDF отчеты пользователям через deep links
Публикует статьи в блог по команде #блог (с диалоговым режимом)
"""

import os
import re
import time
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_BASE_URL = os.getenv('API_BASE_URL', 'https://housler.ru')
SITE_URL = os.getenv('SITE_URL', 'https://housler.ru')

# Whitelist админов для публикации в блог (comma-separated user IDs)
BLOG_ADMIN_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv('BLOG_ADMIN_USER_IDS', '').split(',')
    if uid.strip().isdigit()
]

# === Диалоговый режим для #блог ===
# Хранит состояние ожидания контента: {user_id: {'timestamp': ..., 'photos': [...]}}
pending_blog_posts = {}
PENDING_TIMEOUT = 300  # 5 минут

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")


# === Утилиты для блога ===

def create_slug(title: str) -> str:
    """Create URL-friendly slug from title (translit ru->en)"""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    slug = title.lower()
    for ru, en in translit_map.items():
        slug = slug.replace(ru, en)
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug[:80]  # Limit length


def parse_blog_message(text: str) -> tuple:
    """
    Parse message with #блог tag

    Supported formats:
    1. #блог
       Тема: Заголовок
       Текст статьи...

    2. #блог
       Заголовок (первая строка)
       Текст статьи...

    3. #блог Заголовок - первое предложение
       Остальной текст становится контентом

    Returns: (title, content) or (None, None) if parsing failed
    """
    if not text or '#блог' not in text.lower():
        return None, None

    # Remove #блог tag
    text = re.sub(r'#блог\s*', '', text, flags=re.IGNORECASE).strip()

    if not text:
        return None, None

    lines = text.split('\n')

    # Try to find "Тема:" prefix
    title = None
    content_start = 0

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped.lower().startswith('тема:'):
            title = line_stripped[5:].strip()
            content_start = i + 1
            break

    # If no "Тема:" found, use first non-empty line as title
    if title is None:
        for i, line in enumerate(lines):
            if line.strip():
                first_line = line.strip()
                # If line is too long, extract first sentence as title
                if len(first_line) > 100:
                    # Find first sentence end
                    for sep in ['. ', '! ', '? ', ' - ', ' — ']:
                        pos = first_line.find(sep)
                        if 20 < pos < 150:
                            title = first_line[:pos + 1].strip()
                            # Rest of this line becomes part of content
                            rest = first_line[pos + len(sep):].strip()
                            if rest:
                                lines[i] = rest
                                content_start = i
                            else:
                                content_start = i + 1
                            break
                    else:
                        # No sentence break found, truncate at ~100 chars
                        space_pos = first_line.rfind(' ', 50, 120)
                        if space_pos > 0:
                            title = first_line[:space_pos].strip()
                            lines[i] = first_line[space_pos:].strip()
                            content_start = i
                        else:
                            title = first_line[:100]
                            lines[i] = first_line[100:]
                            content_start = i
                else:
                    title = first_line
                    content_start = i + 1
                break

    if not title:
        return None, None

    # Rest is content
    content_lines = [l.strip() for l in lines[content_start:] if l.strip()]
    content = '\n\n'.join(content_lines)

    # If no separate content lines, the text might be one block
    if not content and title:
        # Title already extracted, but maybe there's more after first sentence
        return title, text  # Use full text as content for GPT to process

    return title, content if content else text


def is_pending_expired(user_id: int) -> bool:
    """Check if pending blog post has expired"""
    if user_id not in pending_blog_posts:
        return True
    return time.time() - pending_blog_posts[user_id]['timestamp'] > PENDING_TIMEOUT


def clear_pending(user_id: int):
    """Clear pending state for user"""
    if user_id in pending_blog_posts:
        del pending_blog_posts[user_id]


async def download_photos(message, slug: str) -> List[str]:
    """
    Download all photos from message

    Returns list of saved file paths
    """
    photos = []
    if not message.photo:
        return photos

    photos_dir = Path("static/blog/images") / slug
    photos_dir.mkdir(parents=True, exist_ok=True)

    # Telegram sends multiple sizes, we take the largest (last)
    photo = message.photo[-1]
    photo_file = await photo.get_file()

    # Determine filename
    idx = len(list(photos_dir.glob("*.jpg")))
    filename = f"{idx + 1}.jpg" if idx > 0 else "cover.jpg"
    photo_path = photos_dir / filename

    await photo_file.download_to_drive(str(photo_path))
    logger.info(f"Downloaded photo to {photo_path}")

    return [str(photo_path)]


async def process_blog_post(
    user_id: int,
    title: str,
    content: str,
    photo_paths: List[str],
    status_msg,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Process and publish blog post

    Args:
        user_id: Telegram user ID
        title: Article title
        content: Article content
        photo_paths: List of photo file paths
        status_msg: Status message to update
        context: Telegram context
    """
    from yandex_gpt import YandexGPT
    from yandex_art import YandexART
    from blog_database import BlogDatabase
    from telegram_publisher import TelegramPublisher

    gpt = YandexGPT()
    art = YandexART()
    db = BlogDatabase()
    telegram_pub = TelegramPublisher()

    # 1. Rewrite via YandexGPT
    await status_msg.edit_text(
        f"Обрабатываю статью: {title[:50]}...\n"
        "Рерайт через YandexGPT..."
    )

    rewritten = gpt.rewrite_article(
        original_title=title,
        original_content=content
    )

    new_title = rewritten['title']
    new_content = rewritten['content']
    excerpt = rewritten.get('excerpt', '')

    slug = create_slug(new_title)

    # Check slug uniqueness
    if db.post_exists(slug):
        slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M')}"

    # 2. Handle images
    cover_image = None
    gallery_images = []

    if photo_paths:
        # First photo becomes cover
        import shutil
        covers_dir = Path("static/blog/covers")
        covers_dir.mkdir(parents=True, exist_ok=True)

        # Copy first photo as cover
        first_photo = Path(photo_paths[0])
        cover_dest = covers_dir / f"{slug}.jpg"
        shutil.copy(first_photo, cover_dest)
        cover_image = f"/static/blog/covers/{slug}.jpg"

        # Rename photos to match new slug if needed
        new_photos_dir = Path("static/blog/images") / slug
        new_photos_dir.mkdir(parents=True, exist_ok=True)

        for i, photo_path in enumerate(photo_paths):
            old_path = Path(photo_path)
            if old_path.exists():
                new_filename = f"{i + 1}.jpg"
                new_path = new_photos_dir / new_filename
                if old_path != new_path:
                    shutil.copy(old_path, new_path)
                gallery_images.append(f"/static/blog/images/{slug}/{new_filename}")

        logger.info(f"Processed {len(photo_paths)} photos, cover: {cover_image}")
    else:
        # Generate cover via YandexART
        await status_msg.edit_text(
            f"Обрабатываю статью: {new_title[:50]}...\n"
            "Генерирую обложку..."
        )
        try:
            cover_image = art.generate_cover(title=new_title, slug=slug)
        except Exception as e:
            logger.warning(f"Cover generation failed: {e}")

    # 3. Save to DB
    await status_msg.edit_text(
        f"Обрабатываю статью: {new_title[:50]}...\n"
        "Сохраняю в базу..."
    )

    post_id = db.create_post(
        slug=slug,
        title=new_title,
        content=new_content,
        excerpt=excerpt,
        original_url=None,
        original_title=title,
        cover_image=cover_image,
        gallery_images=gallery_images if gallery_images else None,
        telegram_post_type="manual"
    )

    logger.info(f"Created blog post: {new_title} (ID: {post_id})")

    # 4. Publish to Telegram channel
    await status_msg.edit_text(
        f"Обрабатываю статью: {new_title[:50]}...\n"
        "Публикую в канал..."
    )

    # Use gallery method if multiple photos
    all_images = [cover_image] + gallery_images[1:] if gallery_images else ([cover_image] if cover_image else [])

    if len(all_images) > 1:
        telegram_pub.publish_post_with_gallery(
            title=new_title,
            content=new_content,
            slug=slug,
            images=all_images,
            excerpt=excerpt
        )
    else:
        telegram_pub.publish_post_with_image(
            title=new_title,
            content=new_content,
            slug=slug,
            cover_image=cover_image,
            excerpt=excerpt
        )

    # Mark as published
    db.mark_telegram_published(post_id)

    # 5. Reply to user
    article_url = f"{SITE_URL}/blog/{slug}"
    photos_info = f"\nФото: {len(gallery_images)}" if gallery_images else ""
    await status_msg.edit_text(
        f"Статья опубликована!\n\n"
        f"Заголовок: {new_title}{photos_info}\n"
        f"Ссылка: {article_url}"
    )

    logger.info(f"Blog post published successfully: {article_url}")
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start
    Формат: /start TOKEN или просто /start
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) запустил бота")

    # Проверяем, есть ли токен в аргументах
    if context.args and len(context.args) > 0:
        token = context.args[0]
        logger.info(f"Получен токен: {token[:8]}...")

        try:
            # Запрашиваем данные отчета у API
            response = requests.get(
                f"{API_BASE_URL}/api/telegram/report/{token}",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                if data['status'] == 'success':
                    # Получаем данные отчета
                    description = data['description']
                    pdf_url = data['pdf_url']
                    web_url = data['web_url']

                    # Отправляем описание
                    await update.message.reply_text(description)

                    # Скачиваем и отправляем PDF
                    pdf_response = requests.get(pdf_url, timeout=60)
                    if pdf_response.status_code == 200:
                        await update.message.reply_document(
                            document=pdf_response.content,
                            filename=f"housler_report.pdf",
                            caption=f"📎 Детальный отчет по объекту\n\n🌐 Открыть в браузере: {web_url}"
                        )
                        logger.info(f"Отчет успешно отправлен пользователю {user.id}")
                    else:
                        await update.message.reply_text(
                            "❌ Не удалось загрузить PDF. Попробуйте позже или откройте отчет в браузере:\n"
                            f"{web_url}"
                        )
                else:
                    await update.message.reply_text(
                        f"❌ Ошибка: {data.get('message', 'Неизвестная ошибка')}"
                    )
            elif response.status_code == 404:
                await update.message.reply_text(
                    "❌ Токен не найден или уже использован.\n"
                    "Каждая ссылка работает только один раз."
                )
            elif response.status_code == 410:
                await update.message.reply_text(
                    "⏰ Срок действия ссылки истек.\n"
                    "Пожалуйста, создайте новый отчет на housler.ru"
                )
            else:
                await update.message.reply_text(
                    f"❌ Ошибка сервера: {response.status_code}\n"
                    "Попробуйте позже."
                )

        except requests.exceptions.Timeout:
            await update.message.reply_text(
                "⏱️ Время ожидания истекло. Сервер не отвечает.\n"
                "Попробуйте позже."
            )
        except Exception as e:
            logger.error(f"Ошибка получения отчета: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при получении отчета.\n"
                "Попробуйте позже или обратитесь в поддержку."
            )
    else:
        # Приветственное сообщение без токена
        await update.message.reply_markdown_v2(
            "👋 *Добро пожаловать в Housler Bot\\!*\n\n"
            "🏠 Я помогаю получать детальные отчеты об анализе недвижимости\\.\n\n"
            "*Как использовать:*\n"
            "1\\. Создайте анализ на [housler\\.ru](https://housler.ru)\n"
            "2\\. На шаге 3 нажмите кнопку \"Поделиться\"\n"
            "3\\. Выберите \"Получить в Telegram\"\n"
            "4\\. Перейдите по ссылке или отсканируйте QR\\-код\n\n"
            "📊 Вы получите PDF отчет с полным анализом объекта\\!"
        )
        logger.info(f"Отправлено приветственное сообщение для {user.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_markdown_v2(
        "*📖 Справка по Housler Bot*\n\n"
        "*Доступные команды:*\n"
        "• /start \\- Начать работу с ботом\n"
        "• /help \\- Показать эту справку\n\n"
        "*Как получить отчет:*\n"
        "1\\. Зайдите на [housler\\.ru](https://housler.ru)\n"
        "2\\. Создайте анализ недвижимости\n"
        "3\\. На 3\\-м шаге нажмите \"Поделиться\" → \"Получить в Telegram\"\n"
        "4\\. Откройте ссылку или отсканируйте QR\\-код\n\n"
        "🔐 *Безопасность:*\n"
        "Каждая ссылка работает один раз и действительна 1 час\\.\n\n"
        "💬 *Поддержка:* @nickkita"
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ожидания контента для #блог"""
    user = update.effective_user

    if user.id in pending_blog_posts:
        clear_pending(user.id)
        await update.message.reply_text("Публикация отменена.")
        logger.info(f"Blog post cancelled by user {user.id}")
    else:
        await update.message.reply_text("Нет активной публикации для отмены.")


async def handle_blog_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик сообщений с тегом #блог

    Диалоговый режим:
    1. Если #блог с текстом — публикуем сразу
    2. Если #блог без текста — ждём следующее сообщение с контентом
    3. Фото собираются из обоих сообщений
    """
    user = update.effective_user
    message = update.message

    # 1. Проверяем авторизацию
    if user.id not in BLOG_ADMIN_USER_IDS:
        logger.warning(f"Unauthorized blog post attempt from user {user.id} (@{user.username})")
        await message.reply_text(
            "У вас нет прав для публикации в блог.\n"
            "Обратитесь к администратору."
        )
        return

    logger.info(f"Blog post request from admin {user.id} (@{user.username})")

    # 2. Парсим сообщение
    text = message.text or message.caption or ''
    logger.info(f"Raw message text ({len(text)} chars): {text[:100]}...")

    title, content = parse_blog_message(text)
    logger.info(f"Parsed: title={title[:50] if title else None}, content_len={len(content) if content else 0}")

    # 3. Скачиваем фото если есть
    temp_slug = f"temp_{user.id}_{int(time.time())}"
    photo_paths = await download_photos(message, temp_slug)

    # 4. Если есть текст — публикуем сразу
    if title and content:
        # Clear any pending state
        clear_pending(user.id)

        status_msg = await message.reply_text(
            f"Обрабатываю статью: {title[:50]}...\n"
            "Рерайт текста..."
        )

        try:
            await process_blog_post(
                user_id=user.id,
                title=title,
                content=content,
                photo_paths=photo_paths,
                status_msg=status_msg,
                context=context
            )
        except Exception as e:
            logger.error(f"Failed to publish blog post: {e}", exc_info=True)
            await status_msg.edit_text(
                f"Ошибка публикации: {str(e)[:200]}\n\n"
                "Попробуйте позже или обратитесь к разработчику."
            )
        return

    # 5. Текста нет — переходим в режим ожидания
    pending_blog_posts[user.id] = {
        'timestamp': time.time(),
        'photos': photo_paths
    }

    photos_info = f"\nФото получены: {len(photo_paths)}" if photo_paths else ""
    await message.reply_text(
        f"Отправьте текст статьи следующим сообщением.{photos_info}\n\n"
        "Формат:\n"
        "Первая строка — заголовок\n"
        "Остальное — текст статьи\n\n"
        "Для отмены: /cancel"
    )
    logger.info(f"Waiting for content from user {user.id}, photos: {len(photo_paths)}")


async def handle_blog_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик контента для ожидающего #блог

    Срабатывает когда пользователь в pending отправляет сообщение без #блог
    """
    user = update.effective_user
    message = update.message

    # Проверяем что пользователь в режиме ожидания
    if user.id not in pending_blog_posts:
        return  # Не наше сообщение

    # Проверяем timeout
    if is_pending_expired(user.id):
        clear_pending(user.id)
        await message.reply_text(
            "Время ожидания истекло (5 минут).\n"
            "Начните заново с #блог"
        )
        return

    # Проверяем авторизацию (на всякий случай)
    if user.id not in BLOG_ADMIN_USER_IDS:
        clear_pending(user.id)
        return

    logger.info(f"Received content from pending user {user.id}")

    # Получаем сохранённые фото
    pending = pending_blog_posts[user.id]
    saved_photos = pending.get('photos', [])

    # Скачиваем новые фото если есть
    temp_slug = f"temp_{user.id}_{int(time.time())}"
    new_photos = await download_photos(message, temp_slug)
    all_photos = saved_photos + new_photos

    # Парсим текст
    text = message.text or message.caption or ''

    if not text.strip():
        photos_info = f" (фото: {len(all_photos)})" if all_photos else ""
        await message.reply_text(
            f"Текст не получен{photos_info}.\n"
            "Отправьте текст статьи или /cancel для отмены."
        )
        # Обновляем фото в pending
        pending_blog_posts[user.id]['photos'] = all_photos
        return

    # Парсим как обычный текст (без #блог)
    lines = text.strip().split('\n')

    # Первая строка — заголовок
    title = None
    content_start = 0

    for i, line in enumerate(lines):
        if line.strip():
            first_line = line.strip()
            # Если строка длинная — берём первое предложение
            if len(first_line) > 100:
                for sep in ['. ', '! ', '? ', ' - ', ' — ']:
                    pos = first_line.find(sep)
                    if 20 < pos < 150:
                        title = first_line[:pos + 1].strip()
                        lines[i] = first_line[pos + len(sep):].strip()
                        content_start = i
                        break
                else:
                    title = first_line[:100]
                    lines[i] = first_line[100:]
                    content_start = i
            else:
                title = first_line
                content_start = i + 1
            break

    if not title:
        await message.reply_text(
            "Не удалось распознать заголовок.\n"
            "Первая строка должна быть заголовком."
        )
        return

    # Остальное — контент
    content_lines = [l.strip() for l in lines[content_start:] if l.strip()]
    content = '\n\n'.join(content_lines)

    if not content:
        content = title  # Если только заголовок — используем его как контент

    # Очищаем pending
    clear_pending(user.id)

    # Публикуем
    status_msg = await message.reply_text(
        f"Обрабатываю статью: {title[:50]}...\n"
        f"Фото: {len(all_photos)}\n"
        "Рерайт текста..."
    )

    try:
        await process_blog_post(
            user_id=user.id,
            title=title,
            content=content,
            photo_paths=all_photos,
            status_msg=status_msg,
            context=context
        )
    except Exception as e:
        logger.error(f"Failed to publish blog post: {e}", exc_info=True)
        await status_msg.edit_text(
            f"Ошибка публикации: {str(e)[:200]}\n\n"
            "Попробуйте позже или обратитесь к разработчику."
        )


def main():
    """Запуск бота"""
    logger.info("Запуск Housler Telegram бота...")

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    # Обработчик сообщений с #блог (текст или фото с подписью)
    blog_filter = filters.Regex(r'(?i)#блог') & (filters.TEXT | filters.PHOTO | filters.CAPTION)
    application.add_handler(MessageHandler(blog_filter, handle_blog_post))

    # Обработчик контента для ожидающих пользователей (без #блог)
    # Важно: должен быть ПОСЛЕ blog_filter, чтобы не перехватывать #блог сообщения
    content_filter = (filters.TEXT | filters.PHOTO | filters.CAPTION) & ~filters.COMMAND & ~filters.Regex(r'(?i)#блог')
    application.add_handler(MessageHandler(content_filter, handle_blog_content))

    # Логируем список админов
    if BLOG_ADMIN_USER_IDS:
        logger.info(f"Blog admins: {BLOG_ADMIN_USER_IDS}")
    else:
        logger.warning("BLOG_ADMIN_USER_IDS not set - #блог functionality disabled")

    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
