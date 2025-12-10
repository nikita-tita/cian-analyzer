"""
Telegram Publisher for Blog Posts
Publishes new articles to Telegram channel
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)


class TelegramPublisher:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID', '@housler_ae')
        self.site_url = os.getenv('SITE_URL', 'https://housler.ru')

        # Content configuration: 60-70% of article, max 4096 symbols (Telegram limit)
        self.content_ratio = float(os.getenv('TELEGRAM_CONTENT_RATIO', '0.65'))
        self.max_symbols = int(os.getenv('TELEGRAM_MAX_SYMBOLS', '4000'))

        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram publishing disabled")

    def publish_post(
        self,
        title: str,
        content: str,
        slug: str
    ) -> bool:
        """
        Publish blog post to Telegram channel

        Args:
            title: Article title
            content: Full article content (will extract 60-70% for preview)
            slug: URL slug for the article

        Returns:
            True if published successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Telegram publishing skipped - no bot token")
            return False

        try:
            article_url = f"{self.site_url}/blog/{slug}"

            # Generate preview (60-70% of content)
            preview_text = self._generate_preview(content)

            # Format message with HTML
            message = f"<b>{title}</b>\n\n"
            message += f"{preview_text}\n\n"
            message += f'<a href="{article_url}">Читать полностью на сайте</a>'

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

    def _generate_preview(self, content: str) -> str:
        """
        Generate preview with 60-70% of article content

        Args:
            content: Full article content

        Returns:
            Preview text for Telegram
        """
        # Split into paragraphs and filter promotional content
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        if not paragraphs:
            return content[:self.max_symbols]

        # Remove promotional/CTA paragraphs
        content_paragraphs = []
        skip_words = [
            'housler', 'оставьте заявку', 'свяжется с вами',
            'агентство', '[оставьте заявку]', 'эксперт свяжется'
        ]
        for paragraph in paragraphs:
            if any(word in paragraph.lower() for word in skip_words):
                continue
            content_paragraphs.append(paragraph)

        if not content_paragraphs:
            return content[:self.max_symbols]

        # Calculate target length
        full_text = '\n\n'.join(content_paragraphs)
        target_length = self._calculate_target_length(len(full_text))

        # Take sequential paragraphs up to target length
        result = ''
        current_length = 0

        for paragraph in content_paragraphs:
            paragraph_text = paragraph + '\n\n' if result else paragraph
            new_length = current_length + len(paragraph_text)

            if new_length > target_length:
                # Try to fit partial paragraph
                remaining = target_length - current_length
                if remaining > 100:
                    partial = paragraph[:remaining]
                    # Cut at sentence boundary
                    for char in '.!?':
                        pos = partial.rfind(char)
                        if pos > remaining * 0.6:
                            result += ('\n\n' if result else '') + partial[:pos + 1]
                            break
                break
            else:
                result += paragraph_text
                current_length = new_length

        result = result.strip()

        # Ensure we don't exceed Telegram limit
        if len(result) > self.max_symbols:
            result = self._truncate_at_sentence(result, self.max_symbols)

        return result

    def _calculate_target_length(self, content_length: int) -> int:
        """
        Calculate target length for preview (60-70% of content)
        Aims for 3400-3900 symbols for optimal Telegram display
        """
        target_min, target_max = 3400, 3900
        target_avg = (target_min + target_max) / 2

        if content_length <= target_avg:
            # Short articles: take up to 95%
            ratio = 0.95
        else:
            # Long articles: calculate ratio to reach target_avg
            ratio = target_avg / content_length

        # Keep ratio between content_ratio and 95%
        ratio = min(0.95, max(self.content_ratio, ratio))

        result = int(content_length * ratio)

        # Ensure minimum length for long articles
        if content_length > target_max and result < target_min:
            result = target_min

        return min(result, self.max_symbols)

    def _truncate_at_sentence(self, text: str, max_length: int) -> str:
        """Truncate text at sentence boundary"""
        if len(text) <= max_length:
            return text

        truncated = text[:max_length]

        # Find last sentence ending
        cut_point = -1
        for char in '.!?':
            pos = truncated.rfind(char)
            if pos > cut_point:
                cut_point = pos

        if cut_point > max_length * 0.7:
            return truncated[:cut_point + 1]

        return truncated.rstrip() + '...'
