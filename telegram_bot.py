"""
Telegram бот для Housler
Отправляет PDF отчеты пользователям через deep links
"""

import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
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

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")


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


def main():
    """Запуск бота"""
    logger.info("Запуск Housler Telegram бота...")

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Запускаем бота
    logger.info("✓ Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
