"""
Telegram бот для Housler
Отправляет PDF отчеты пользователям через deep links
Публикует статьи в блог по команде #блог
"""

import os
import re
import logging
import requests
from datetime import datetime
from pathlib import Path
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
                title = line.strip()
                content_start = i + 1
                break

    if not title:
        return None, None

    # Rest is content
    content_lines = [l for l in lines[content_start:] if l.strip()]
    content = '\n\n'.join(content_lines)

    return title, content


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


async def handle_blog_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик сообщений с тегом #блог

    Публикует статью в блог:
    1. Проверяет авторизацию
    2. Парсит сообщение (заголовок + текст)
    3. Скачивает фото если есть
    4. Рерайтит через YandexGPT
    5. Генерирует обложку через YandexART
    6. Сохраняет в БД
    7. Публикует в Telegram канал
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
    title, content = parse_blog_message(text)

    if not title or not content:
        await message.reply_text(
            "Не удалось распознать статью.\n\n"
            "Формат сообщения:\n"
            "#блог\n"
            "Тема: Заголовок статьи\n\n"
            "Текст статьи..."
        )
        return

    # Отправляем статус
    status_msg = await message.reply_text(
        f"Обрабатываю статью: {title[:50]}...\n"
        "Рерайт текста..."
    )

    try:
        # Lazy imports (avoid loading at bot startup)
        from yandex_gpt import YandexGPT
        from yandex_art import YandexART
        from blog_database import BlogDatabase
        from telegram_publisher import TelegramPublisher

        gpt = YandexGPT()
        art = YandexART()
        db = BlogDatabase()
        telegram_pub = TelegramPublisher()

        # 3. Проверяем, есть ли фото в сообщении
        photo_path = None
        if message.photo:
            # Берём фото максимального размера
            photo = message.photo[-1]
            photo_file = await photo.get_file()

            # Создаём slug для имени файла
            slug = create_slug(title)

            # Сохраняем фото
            photos_dir = Path("static/blog/images") / slug
            photos_dir.mkdir(parents=True, exist_ok=True)
            photo_path = photos_dir / "cover.jpg"

            await photo_file.download_to_drive(str(photo_path))
            logger.info(f"Downloaded photo to {photo_path}")

        # 4. Рерайтим через YandexGPT
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

        # Проверяем уникальность slug
        if db.post_exists(slug):
            slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M')}"

        # 5. Генерируем обложку
        cover_image = None
        if photo_path and photo_path.exists():
            # Используем загруженное фото как обложку
            # Копируем в папку covers
            covers_dir = Path("static/blog/covers")
            covers_dir.mkdir(parents=True, exist_ok=True)
            cover_dest = covers_dir / f"{slug}.jpg"

            import shutil
            shutil.copy(photo_path, cover_dest)
            cover_image = f"/static/blog/covers/{slug}.jpg"
            logger.info(f"Using uploaded photo as cover: {cover_image}")
        else:
            # Генерируем через YandexART
            await status_msg.edit_text(
                f"Обрабатываю статью: {new_title[:50]}...\n"
                "Генерирую обложку..."
            )
            try:
                cover_image = art.generate_cover(title=new_title, slug=slug)
            except Exception as e:
                logger.warning(f"Cover generation failed: {e}")

        # 6. Сохраняем в БД
        await status_msg.edit_text(
            f"Обрабатываю статью: {new_title[:50]}...\n"
            "Сохраняю в базу..."
        )

        post_id = db.create_post(
            slug=slug,
            title=new_title,
            content=new_content,
            excerpt=excerpt,
            original_url=None,  # Свой пост, не парсинг
            original_title=title,
            cover_image=cover_image,
            telegram_post_type="manual"
        )

        logger.info(f"Created blog post: {new_title} (ID: {post_id})")

        # 7. Публикуем в Telegram канал
        await status_msg.edit_text(
            f"Обрабатываю статью: {new_title[:50]}...\n"
            "Публикую в канал..."
        )

        telegram_pub.publish_post_with_image(
            title=new_title,
            content=new_content,
            slug=slug,
            cover_image=cover_image,
            excerpt=excerpt
        )

        # Помечаем как опубликованную в Telegram
        db.mark_telegram_published(post_id)

        # 8. Отвечаем пользователю
        article_url = f"{SITE_URL}/blog/{slug}"
        await status_msg.edit_text(
            f"Статья опубликована!\n\n"
            f"Заголовок: {new_title}\n"
            f"Ссылка: {article_url}"
        )

        logger.info(f"Blog post published successfully: {article_url}")

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

    # Обработчик сообщений с #блог (текст или фото с подписью)
    blog_filter = filters.Regex(r'(?i)#блог') & (filters.TEXT | filters.PHOTO)
    application.add_handler(MessageHandler(blog_filter, handle_blog_post))

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
