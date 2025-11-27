"""
Alert Bot для уведомлений о работе крон-задач
Отправляет алерты в Telegram при успешном/неуспешном выполнении парсинга
"""

import os
import requests
import logging
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Токен бота для алертов (отдельный от публикации в канал)
ALERT_BOT_TOKEN = "8107613087:AAH6CZ7b1mHVfCoa8vZOwrpLRSoCbILHqV0"


@dataclass
class ParseResult:
    """Результат парсинга для отчёта"""
    source: str
    articles_found: int = 0
    articles_parsed: int = 0
    articles_rewritten: int = 0
    articles_published_site: int = 0
    pending_telegram: int = 0  # Статьи в очереди на публикацию в ТГ
    errors: List[str] = field(default_factory=list)

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
        self.chat_id = chat_id  # Будет установлен после первого сообщения боту

    def _get_chat_id(self) -> Optional[str]:
        """Получить chat_id из последних обновлений бота"""
        if self.chat_id:
            return self.chat_id

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    # Берём последнее сообщение
                    for update in reversed(data['result']):
                        if 'message' in update:
                            self.chat_id = str(update['message']['chat']['id'])
                            return self.chat_id
        except Exception as e:
            logger.error(f"Failed to get chat_id: {e}")
        return None

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

        message = f"""✅ <b>Парсинг {result.source} завершён успешно</b>

📅 {now}

📊 <b>Статистика:</b>
• Найдено статей: {result.articles_found}
• Спаршено: {result.articles_parsed}
• Переписано ИИ: {result.articles_rewritten}
• Опубликовано на сайте: {result.articles_published_site}
• В очереди на ТГ: {result.pending_telegram}

🎉 Всё работает штатно!"""

        return self.send_alert(message)

    def send_partial_success_report(self, result: ParseResult) -> bool:
        """Отправить отчёт о частичном успехе"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        errors_text = "\n".join([f"• {e}" for e in result.errors[:5]])
        if len(result.errors) > 5:
            errors_text += f"\n• ...и ещё {len(result.errors) - 5} ошибок"

        message = f"""⚠️ <b>Парсинг {result.source} завершён с ошибками</b>

📅 {now}

📊 <b>Статистика:</b>
• Найдено статей: {result.articles_found}
• Спаршено: {result.articles_parsed}
• Переписано ИИ: {result.articles_rewritten}
• Опубликовано на сайте: {result.articles_published_site}
• В очереди на ТГ: {result.pending_telegram}

❌ <b>Ошибки:</b>
{errors_text}"""

        return self.send_alert(message)

    def send_failure_report(self, result: ParseResult) -> bool:
        """Отправить отчёт о провале"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        errors_text = "\n".join([f"• {e}" for e in result.errors[:5]])
        if len(result.errors) > 5:
            errors_text += f"\n• ...и ещё {len(result.errors) - 5} ошибок"

        message = f"""🚨 <b>Парсинг {result.source} ПРОВАЛЕН</b>

📅 {now}

📊 <b>Статистика:</b>
• Найдено статей: {result.articles_found}
• Спаршено: {result.articles_parsed}
• Переписано ИИ: {result.articles_rewritten}
• Опубликовано на сайте: {result.articles_published_site}

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
