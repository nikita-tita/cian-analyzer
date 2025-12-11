"""
Telegram Publisher for Blog Posts
Publishes new articles to Telegram channel
Supports single image and media groups (galleries)
"""

import os
import json
import requests
import logging
from typing import Optional, List

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
        slug: str,
        telegram_content: Optional[str] = None
    ) -> bool:
        """
        Publish blog post to Telegram channel

        Args:
            title: Article title
            content: Full article content (fallback if telegram_content not provided)
            slug: URL slug for the article
            telegram_content: Pre-generated shortened content for Telegram (1200-1500 chars)

        Returns:
            True if published successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Telegram publishing skipped - no bot token")
            return False

        try:
            article_url = f"{self.site_url}/blog/{slug}"

            # Use telegram_content if available, otherwise truncate content as fallback
            if telegram_content:
                preview_text = telegram_content
            else:
                # Fallback: simple truncation (legacy behavior)
                preview_text = content[:self.max_symbols]
                if len(content) > self.max_symbols:
                    # Cut at sentence boundary
                    for char in '.!?':
                        pos = preview_text.rfind(char)
                        if pos > self.max_symbols * 0.7:
                            preview_text = preview_text[:pos + 1]
                            break

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

    def publish_post_with_image(
        self,
        title: str,
        content: str,
        slug: str,
        cover_image: Optional[str] = None,
        excerpt: Optional[str] = None,
        telegram_content: Optional[str] = None
    ) -> bool:
        """
        Publish blog post to Telegram channel with cover image

        Now uses two-message approach:
        1. Long text message (telegram_content or fallback)
        2. Photo without caption

        If cover_image is not provided or file not found,
        falls back to text-only publish_post().

        Args:
            title: Article title
            content: Full article content (fallback)
            slug: URL slug for the article
            cover_image: Path to cover image (e.g., "/static/blog/covers/slug.png")
            excerpt: Optional custom excerpt
            telegram_content: Pre-generated shortened content for Telegram (1200-1500 chars)

        Returns:
            True if published successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Telegram publishing skipped - no bot token")
            return False

        # If no cover - use text-only method
        if not cover_image:
            return self.publish_post(title, content, slug, telegram_content=telegram_content)

        # Check file exists
        image_path = cover_image.lstrip('/')  # "/static/..." -> "static/..."
        if not os.path.exists(image_path):
            logger.warning(f"Cover image not found: {image_path}, falling back to text")
            return self.publish_post(title, content, slug, telegram_content=telegram_content)

        # Delegate to the two-message method
        return self.publish_post_with_text_and_photos(
            title=title,
            content=content,
            slug=slug,
            images=[cover_image],
            excerpt=excerpt,
            telegram_content=telegram_content
        )

    def publish_post_with_text_and_photos(
        self,
        title: str,
        content: str,
        slug: str,
        images: List[str],
        excerpt: Optional[str] = None,
        telegram_content: Optional[str] = None
    ) -> bool:
        """
        Publish blog post as TWO messages: long text first, then photos

        This approach allows:
        - Text message: up to 4096 chars (telegram_content ~1200-1500 chars)
        - Photos: sent separately without caption limit

        Args:
            title: Article title
            content: Full article content (fallback)
            slug: URL slug for the article
            images: List of image paths
            excerpt: Optional custom excerpt
            telegram_content: Pre-generated shortened content for Telegram (1200-1500 chars)

        Returns:
            True if published successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Telegram publishing skipped - no bot token")
            return False

        # Filter existing images
        valid_images = []
        for img in images:
            img_path = img.lstrip('/')
            if os.path.exists(img_path):
                valid_images.append(img_path)
            else:
                logger.warning(f"Image not found: {img_path}")

        # If no valid images, fall back to text-only
        if not valid_images:
            logger.warning("No valid images, using text-only publish")
            return self.publish_post(title, content, slug, telegram_content=telegram_content)

        try:
            article_url = f"{self.site_url}/blog/{slug}"

            # Step 1: Send long text message (use telegram_content if available)
            if telegram_content:
                preview_text = telegram_content
            else:
                # Fallback: simple truncation (legacy behavior)
                preview_text = content[:self.max_symbols]
                if len(content) > self.max_symbols:
                    for char in '.!?':
                        pos = preview_text.rfind(char)
                        if pos > self.max_symbols * 0.7:
                            preview_text = preview_text[:pos + 1]
                            break

            message = f"<b>{title}</b>\n\n"
            message += f"{preview_text}\n\n"
            message += f'<a href="{article_url}">Читать полностью на сайте</a>'

            api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            text_response = requests.post(
                api_url,
                json={
                    "chat_id": self.channel_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True  # Disable preview since we send photos
                },
                timeout=30
            )

            if text_response.status_code != 200:
                logger.error(f"Failed to send text: {text_response.status_code}")
                return False

            text_result = text_response.json()
            if not text_result.get('ok'):
                logger.error(f"Telegram API error: {text_result.get('description')}")
                return False

            logger.info(f"Sent text message for: {title[:50]}... ({len(preview_text)} chars)")

            # Step 2: Send photos (single or media group)
            # Limit to 10 images (Telegram limit)
            if len(valid_images) > 10:
                valid_images = valid_images[:10]

            if len(valid_images) == 1:
                # Single photo - use sendPhoto without caption
                photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
                with open(valid_images[0], 'rb') as photo:
                    photo_response = requests.post(
                        photo_url,
                        data={"chat_id": self.channel_id},
                        files={"photo": photo},
                        timeout=60
                    )
            else:
                # Multiple photos - use sendMediaGroup without captions
                media = []
                files = {}

                for i, img_path in enumerate(valid_images):
                    file_key = f"photo{i}"
                    media.append({
                        "type": "photo",
                        "media": f"attach://{file_key}"
                    })
                    files[file_key] = open(img_path, 'rb')

                photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendMediaGroup"
                photo_response = requests.post(
                    photo_url,
                    data={
                        "chat_id": self.channel_id,
                        "media": json.dumps(media)
                    },
                    files=files,
                    timeout=120
                )

                # Close all file handles
                for f in files.values():
                    f.close()

            if photo_response.status_code == 200:
                photo_result = photo_response.json()
                if photo_result.get('ok'):
                    logger.info(f"Published {len(valid_images)} photo(s) to Telegram: {title[:50]}...")
                    return True
                else:
                    logger.error(f"Photo upload error: {photo_result.get('description')}")
                    # Text was sent, photos failed - still partial success
                    return True
            else:
                logger.error(f"Photo upload HTTP error: {photo_response.status_code}")
                return True  # Text was sent successfully

        except Exception as e:
            logger.error(f"Failed to publish with text and photos: {e}")
            return self.publish_post(title, content, slug, telegram_content=telegram_content)

    def publish_post_with_gallery(
        self,
        title: str,
        content: str,
        slug: str,
        images: List[str],
        excerpt: Optional[str] = None,
        telegram_content: Optional[str] = None
    ) -> bool:
        """
        Publish blog post with multiple images as Telegram media group

        DEPRECATED: Use publish_post_with_text_and_photos() for longer text.
        This method is kept for backward compatibility but now delegates
        to the new two-message approach.

        Telegram sendMediaGroup:
        - Max 10 media items
        - Only first item can have caption (1024 chars)
        - All media must be same type (photos)

        Args:
            title: Article title
            content: Full article content
            slug: URL slug for the article
            images: List of image paths (e.g., ["/static/blog/covers/slug.jpg", ...])
            excerpt: Optional custom excerpt
            telegram_content: Pre-generated shortened content for Telegram (1200-1500 chars)

        Returns:
            True if published successfully, False otherwise
        """
        # Delegate to new two-message method for longer text support
        return self.publish_post_with_text_and_photos(
            title=title,
            content=content,
            slug=slug,
            images=images,
            excerpt=excerpt,
            telegram_content=telegram_content
        )

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
