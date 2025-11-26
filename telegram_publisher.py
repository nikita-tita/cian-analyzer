"""
Telegram Publisher for Blog Posts
Publishes new articles to Telegram channel
"""

import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramPublisher:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID', '@housler_ae')
        self.site_url = os.getenv('SITE_URL', 'https://housler.ru')

        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram publishing disabled")

    def publish_post(
        self,
        title: str,
        content: str,
        slug: str,
        excerpt: Optional[str] = None
    ) -> bool:
        """
        Publish blog post to Telegram channel

        Args:
            title: Article title
            content: Full article content
            slug: URL slug for the article
            excerpt: Optional excerpt (if not provided, will use 1/3 of content)

        Returns:
            True if published successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Telegram publishing skipped - no bot token")
            return False

        try:
            # Build article URL
            article_url = f"{self.site_url}/blog/{slug}"

            # Prepare post text: title + 1/3 of content
            if excerpt:
                preview_text = excerpt
            else:
                # Take approximately 1/3 of content
                content_length = len(content)
                preview_length = content_length // 3
                preview_text = content[:preview_length]

                # Cut at last complete sentence or paragraph
                last_period = preview_text.rfind('.')
                last_newline = preview_text.rfind('\n')
                cut_point = max(last_period, last_newline)

                if cut_point > 100:
                    preview_text = preview_text[:cut_point + 1]

            # Clean up the preview text
            preview_text = preview_text.strip()
            if len(preview_text) > 800:
                preview_text = preview_text[:800]
                last_period = preview_text.rfind('.')
                if last_period > 400:
                    preview_text = preview_text[:last_period + 1]

            # Format message with HTML
            message = f"<b>{title}</b>\n\n"
            message += f"{preview_text}\n\n"
            message += f'<a href="{article_url}">Продолжить на сайте</a>'

            # Send to Telegram
            api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            response = requests.post(
                api_url,
                json={
                    "chat_id": self.channel_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info(f"Published to Telegram: {title}")
                    return True
                else:
                    logger.error(f"Telegram API error: {result.get('description')}")
                    return False
            else:
                logger.error(f"Telegram API HTTP error: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to publish to Telegram: {e}")
            return False

    def test_connection(self) -> bool:
        """Test bot connection and channel access"""
        if not self.bot_token:
            return False

        try:
            # Test bot
            api_url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(api_url, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    bot_info = result.get('result', {})
                    logger.info(f"Bot connected: @{bot_info.get('username')}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to test Telegram connection: {e}")
            return False
