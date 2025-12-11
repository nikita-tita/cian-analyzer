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
        Publish blog post to Telegram channel with cover image as SINGLE message

        Uses sendPhoto with caption (limit 1024 chars).
        If cover_image is not provided or file not found,
        falls back to text-only publish_post() with full telegram_content.

        Args:
            title: Article title
            content: Full article content (fallback)
            slug: URL slug for the article
            cover_image: Path to cover image (e.g., "/static/blog/covers/slug.png")
            excerpt: Optional custom excerpt
            telegram_content: Pre-generated shortened content for Telegram

        Returns:
            True if published successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Telegram publishing skipped - no bot token")
            return False

        # If no cover - use text-only method (full telegram_content up to 4096)
        if not cover_image:
            return self.publish_post(title, content, slug, telegram_content=telegram_content)

        # Check file exists
        image_path = cover_image.lstrip('/')  # "/static/..." -> "static/..."
        if not os.path.exists(image_path):
            logger.warning(f"Cover image not found: {image_path}, falling back to text")
            return self.publish_post(title, content, slug, telegram_content=telegram_content)

        try:
            article_url = f"{self.site_url}/blog/{slug}"

            # Build caption (max 1024 chars for photo caption)
            caption = self._build_photo_caption(
                title=title,
                content=content,
                telegram_content=telegram_content,
                article_url=article_url
            )

            # Send photo with caption
            photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            with open(image_path, 'rb') as photo:
                response = requests.post(
                    photo_url,
                    data={
                        "chat_id": self.channel_id,
                        "caption": caption,
                        "parse_mode": "HTML"
                    },
                    files={"photo": photo},
                    timeout=60
                )

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info(f"Published photo with caption to Telegram: {title[:50]}... ({len(caption)} chars)")
                    return True
                else:
                    logger.error(f"Telegram API error: {result.get('description')}")
                    return False
            else:
                logger.error(f"Telegram API HTTP error: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to publish with image: {e}")
            # Fallback to text-only
            return self.publish_post(title, content, slug, telegram_content=telegram_content)

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
        Publish blog post with multiple photos as media group (single message)

        Uses sendMediaGroup with caption on first image (limit 1024 chars).
        For single image, delegates to publish_post_with_image.

        Args:
            title: Article title
            content: Full article content (fallback)
            slug: URL slug for the article
            images: List of image paths
            excerpt: Optional custom excerpt
            telegram_content: Pre-generated shortened content for Telegram

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

        # Single image - use simpler method
        if len(valid_images) == 1:
            return self.publish_post_with_image(
                title=title,
                content=content,
                slug=slug,
                cover_image=f"/{valid_images[0]}",
                telegram_content=telegram_content
            )

        try:
            article_url = f"{self.site_url}/blog/{slug}"

            # Build caption for first image (max 1024 chars)
            caption = self._build_photo_caption(
                title=title,
                content=content,
                telegram_content=telegram_content,
                article_url=article_url
            )

            # Limit to 10 images (Telegram limit)
            if len(valid_images) > 10:
                valid_images = valid_images[:10]

            # Build media group - caption only on first image
            media = []
            files = {}

            for i, img_path in enumerate(valid_images):
                file_key = f"photo{i}"
                media_item = {
                    "type": "photo",
                    "media": f"attach://{file_key}"
                }
                # Add caption only to first image
                if i == 0:
                    media_item["caption"] = caption
                    media_item["parse_mode"] = "HTML"
                media.append(media_item)
                files[file_key] = open(img_path, 'rb')

            photo_url = f"https://api.telegram.org/bot{self.bot_token}/sendMediaGroup"
            response = requests.post(
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

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info(f"Published {len(valid_images)} photos with caption to Telegram: {title[:50]}... ({len(caption)} chars)")
                    return True
                else:
                    logger.error(f"Media group error: {result.get('description')}")
                    return False
            else:
                logger.error(f"Media group HTTP error: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to publish media group: {e}")
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

    def _build_photo_caption(
        self,
        title: str,
        content: str,
        telegram_content: Optional[str],
        article_url: str
    ) -> str:
        """
        Build caption for photo post with 1024 char limit

        Structure:
        <b>Title</b>

        Preview text (truncated to fit)...

        <a href="url">Читать полностью на сайте</a>
        """
        MAX_CAPTION = 1020  # Safe limit (Telegram: 1024)

        # Fixed parts
        link_text = f'<a href="{article_url}">Читать полностью на сайте</a>'
        title_formatted = f"<b>{title}</b>"

        # Calculate available space for preview
        # Format: title + \n\n + preview + \n\n + link
        fixed_length = len(title_formatted) + len(link_text) + 4  # 4 = two "\n\n"
        max_preview_length = MAX_CAPTION - fixed_length

        # Use telegram_content if available, otherwise truncate content
        if telegram_content:
            preview = telegram_content
        else:
            preview = content

        # Truncate preview if needed
        if len(preview) > max_preview_length:
            preview = preview[:max_preview_length]
            # Try to cut at sentence boundary
            for char in '.!?':
                pos = preview.rfind(char)
                if pos > max_preview_length * 0.6:
                    preview = preview[:pos + 1]
                    break
            else:
                # Cut at word boundary
                last_space = preview.rfind(' ')
                if last_space > max_preview_length * 0.6:
                    preview = preview[:last_space] + '...'
                else:
                    preview = preview + '...'

        # Build caption
        caption = f"{title_formatted}\n\n{preview}\n\n{link_text}"

        # Final safety check
        if len(caption) > MAX_CAPTION:
            overflow = len(caption) - MAX_CAPTION
            preview = preview[:len(preview) - overflow - 3] + "..."
            caption = f"{title_formatted}\n\n{preview}\n\n{link_text}"

        return caption
