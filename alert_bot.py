"""
Alert Bot для уведомлений о работе крон-задач
Отправляет алерты в Telegram при успешном/неуспешном выполнении парсинга
"""

import os
import requests
import logging
import json
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Токен бота для алертов (из переменных окружения)
ALERT_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Файл для кэширования chat_id
CHAT_ID_CACHE_FILE = Path(__file__).parent / ".telegram_chat_id"


@dataclass
class ParseResult:
    """Результат парсинга для отчёта"""
    source: str
    articles_found: int = 0
    articles_parsed: int = 0
    articles_rewritten: int = 0
    articles_published_site: int = 0
    pending_telegram: int = 0  # Статьи в очереди на публикацию в ТГ
    published_titles: List[str] = field(default_factory=list)  # Названия опубликованных статей
    errors: List[str] = field(default_factory=list)
    # Статистика токенов Yandex GPT
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def is_success(self) -> bool:
        """Успешен ли парсинг"""
        return (
            self.articles_published_site >= 1 and
            len(self.errors) == 0
        )

    @property
    def is_partial_success(self) -> bool:
        """Частичный успех (что-то опубликовано, но были ошибки)"""
        return (
            self.articles_published_site >= 1 and
            len(self.errors) > 0
        )


class AlertBot:
    def __init__(self, chat_id: Optional[str] = None):
        self.bot_token = ALERT_BOT_TOKEN
        self.chat_id = chat_id or self._load_chat_id()

    def _load_chat_id(self) -> Optional[str]:
        """
        Загрузить chat_id из разных источников (приоритет):
        1. Переменная окружения TELEGRAM_CHAT_ID
        2. Кэш-файл .telegram_chat_id
        3. API getUpdates
        """
        # 1. Проверяем переменную окружения
        env_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        if env_chat_id:
            logger.info(f"Using chat_id from environment: {env_chat_id}")
            self._save_chat_id(env_chat_id)
            return env_chat_id

        # 2. Проверяем кэш-файл
        try:
            if CHAT_ID_CACHE_FILE.exists():
                cached_data = json.loads(CHAT_ID_CACHE_FILE.read_text())
                cached_chat_id = cached_data.get('chat_id', '').strip()
                if cached_chat_id:
                    logger.info(f"Using cached chat_id: {cached_chat_id}")
                    return cached_chat_id
        except Exception as e:
            logger.warning(f"Failed to read cached chat_id: {e}")

        # 3. Пытаемся получить из API
        return self._fetch_chat_id_from_api()

    def _fetch_chat_id_from_api(self) -> Optional[str]:
        """Получить chat_id из Telegram API getUpdates"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    # Берём последнее сообщение
                    for update in reversed(data['result']):
                        if 'message' in update:
                            chat_id = str(update['message']['chat']['id'])
                            logger.info(f"Fetched chat_id from API: {chat_id}")
                            self._save_chat_id(chat_id)
                            return chat_id
        except Exception as e:
            logger.error(f"Failed to fetch chat_id from API: {e}")
        return None

    def _save_chat_id(self, chat_id: str) -> None:
        """Сохранить chat_id в кэш-файл"""
        try:
            CHAT_ID_CACHE_FILE.write_text(json.dumps({
                'chat_id': chat_id,
                'updated_at': datetime.now().isoformat()
            }))
            logger.debug(f"Saved chat_id to cache: {chat_id}")
        except Exception as e:
            logger.warning(f"Failed to save chat_id to cache: {e}")

    def _get_chat_id(self) -> Optional[str]:
        """Получить chat_id (обратная совместимость)"""
        if not self.chat_id:
            self.chat_id = self._load_chat_id()
        return self.chat_id

    def send_alert(self, message: str, parse_mode: str = "HTML") -> bool:
        """Отправить алерт"""
        chat_id = self._get_chat_id()
        if not chat_id:
            logger.error("No chat_id available. Send /start to @dogovorarenda_bot first")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            response = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": parse_mode
                },
                timeout=30
            )

            if response.status_code == 200 and response.json().get('ok'):
                logger.info("Alert sent successfully")
                return True
            else:
                logger.error(f"Failed to send alert: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False

    def send_success_report(self, result: ParseResult) -> bool:
        """Отправить отчёт об успешном парсинге"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        # Формируем список опубликованных статей
        published_list = ""
        if result.published_titles:
            published_list = "\n\n📝 <b>Опубликовано:</b>\n"
            for i, title in enumerate(result.published_titles, 1):
                published_list += f"{i}. {title}\n"

        # Формируем строку с токенами
        tokens_line = ""
        if result.total_tokens > 0:
            tokens_line = f"\n• Токены GPT: {result.input_tokens:,} вх / {result.output_tokens:,} вых"

        message = f"""✅ <b>Парсинг {result.source} завершён успешно</b>

📅 {now}

📊 <b>Статистика:</b>
• Найдено статей: {result.articles_found}
• Спаршено: {result.articles_parsed}
• Переписано ИИ: {result.articles_rewritten}
• Опубликовано на сайте: {result.articles_published_site}
• В очереди на ТГ: {result.pending_telegram}{tokens_line}{published_list}

🎉 Всё работает штатно!"""

        return self.send_alert(message)

    def send_partial_success_report(self, result: ParseResult) -> bool:
        """Отправить отчёт о частичном успехе"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        errors_text = "\n".join([f"• {e}" for e in result.errors[:5]])
        if len(result.errors) > 5:
            errors_text += f"\n• ...и ещё {len(result.errors) - 5} ошибок"

        # Формируем список опубликованных статей
        published_list = ""
        if result.published_titles:
            published_list = "\n\n📝 <b>Опубликовано:</b>\n"
            for i, title in enumerate(result.published_titles, 1):
                published_list += f"{i}. {title}\n"

        # Формируем строку с токенами
        tokens_line = ""
        if result.total_tokens > 0:
            tokens_line = f"\n• Токены GPT: {result.input_tokens:,} вх / {result.output_tokens:,} вых"

        message = f"""⚠️ <b>Парсинг {result.source} завершён с ошибками</b>

📅 {now}

📊 <b>Статистика:</b>
• Найдено статей: {result.articles_found}
• Спаршено: {result.articles_parsed}
• Переписано ИИ: {result.articles_rewritten}
• Опубликовано на сайте: {result.articles_published_site}
• В очереди на ТГ: {result.pending_telegram}{tokens_line}{published_list}

❌ <b>Ошибки:</b>
{errors_text}"""

        return self.send_alert(message)

    def send_failure_report(self, result: ParseResult) -> bool:
        """Отправить отчёт о провале"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        errors_text = "\n".join([f"• {e}" for e in result.errors[:5]])
        if len(result.errors) > 5:
            errors_text += f"\n• ...и ещё {len(result.errors) - 5} ошибок"

        # Формируем строку с токенами
        tokens_line = ""
        if result.total_tokens > 0:
            tokens_line = f"\n• Токены GPT: {result.input_tokens:,} вх / {result.output_tokens:,} вых"

        message = f"""🚨 <b>Парсинг {result.source} ПРОВАЛЕН</b>

📅 {now}

📊 <b>Статистика:</b>
• Найдено статей: {result.articles_found}
• Спаршено: {result.articles_parsed}
• Переписано ИИ: {result.articles_rewritten}
• Опубликовано на сайте: {result.articles_published_site}{tokens_line}

❌ <b>Ошибки:</b>
{errors_text}

⚡️ Требуется проверка!"""

        return self.send_alert(message)

    def send_report(self, result: ParseResult) -> bool:
        """Автоматически выбрать тип отчёта и отправить"""
        if result.is_success:
            return self.send_success_report(result)
        elif result.is_partial_success:
            return self.send_partial_success_report(result)
        else:
            return self.send_failure_report(result)


# Глобальный инстанс для удобства
alert_bot = AlertBot()


def send_alert(message: str) -> bool:
    """Быстрая функция для отправки алерта"""
    return alert_bot.send_alert(message)


def send_parse_report(result: ParseResult) -> bool:
    """Быстрая функция для отправки отчёта"""
    return alert_bot.send_report(result)
