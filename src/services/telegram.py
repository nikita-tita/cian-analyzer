"""
Сервис отправки уведомлений в Telegram

Отвечает за:
- Отправку сообщений в Telegram бота
- Форматирование сообщений
- Санитизацию HTML
"""

import os
import json
import logging
import urllib.request
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Сервис отправки уведомлений в Telegram

    Использование:
        notifier = TelegramNotifier()
        notifier.send("Текст сообщения")

        # Или использовать singleton:
        from src.services import telegram_notifier
        telegram_notifier.send("Текст")
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        """
        Args:
            bot_token: Токен Telegram бота (по умолчанию из env TELEGRAM_BOT_TOKEN)
            chat_id: ID чата (по умолчанию из env TELEGRAM_CHAT_ID)
        """
        self.bot_token = bot_token or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID', '')
        self._timeout = 10

    def send(self, text: str, parse_mode: str = 'HTML') -> bool:
        """
        Отправить сообщение в Telegram

        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга (HTML или Markdown)

        Returns:
            True если отправлено успешно
        """
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN не задан")
            return False

        chat_id = self._get_chat_id()
        if not chat_id:
            logger.error("Chat ID не найден. Напишите боту /start")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }

            data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')

            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get('ok', False)

        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
            return False

    def _get_chat_id(self) -> Optional[str]:
        """
        Получить chat_id (из конфига или через getUpdates)
        """
        if self.chat_id:
            return self.chat_id

        # Пробуем получить из последних обновлений бота
        try:
            updates_url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            req = urllib.request.Request(updates_url)

            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

                if data.get('ok') and data.get('result'):
                    for update in reversed(data['result']):
                        if 'message' in update:
                            return str(update['message']['chat']['id'])

        except Exception as e:
            logger.warning(f"Не удалось получить chat_id: {e}")

        return None

    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Экранировать HTML спецсимволы для безопасной отправки

        Args:
            text: Исходный текст

        Returns:
            Экранированный текст
        """
        if not text:
            return ''
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))


# Singleton instance
telegram_notifier = TelegramNotifier()
