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

    def publish_post_with_image(
        self,
        title: str,
        content: str,
        slug: str,
        cover_image: Optional[str] = None,
        excerpt: Optional[str] = None
    ) -> bool:
        """
        Publish blog post to Telegram channel with cover image

        Now uses two-message approach:
        1. Long text message (3/4 of content)
        2. Photo without caption

        If cover_image is not provided or file not found,
        falls back to text-only publish_post().

        Args:
            title: Article title
            content: Full article content
            slug: URL slug for the article
            cover_image: Path to cover image (e.g., "/static/blog/covers/slug.png")
            excerpt: Optional custom excerpt

        Returns:
            True if published successfully, False otherwise
        """
        if not self.bot_token:
            logger.warning("Telegram publishing skipped - no bot token")
            return False

        # If no cover - use text-only method
        if not cover_image:
            return self.publish_post(title, content, slug)

        # Check file exists
        image_path = cover_image.lstrip('/')  # "/static/..." -> "static/..."
        if not os.path.exists(image_path):
            logger.warning(f"Cover image not found: {image_path}, falling back to text")
            return self.publish_post(title, content, slug)

        # Delegate to the two-message method
        return self.publish_post_with_text_and_photos(
            title=title,
            content=content,
            slug=slug,
            images=[cover_image],
            excerpt=excerpt
        )

    def publish_post_with_text_and_photos(
        self,
        title: str,
        content: str,
        slug: str,
        images: List[str],
        excerpt: Optional[str] = None
    ) -> bool:
        """
        Publish blog post as TWO messages: long text first, then photos

        This approach allows:
        - Text message: up to 4096 chars (we use 3/4 of content = ~1500+ chars)
        - Photos: sent separately without caption limit

        Args:
            title: Article title
            content: Full article content
            slug: URL slug for the article
            images: List of image paths
            excerpt: Optional custom excerpt

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
            return self.publish_post(title, content, slug)

        try:
            article_url = f"{self.site_url}/blog/{slug}"

            # Step 1: Send long text message (3/4 of content)
            preview_text = self._generate_preview(content)

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
            return self.publish_post(title, content, slug)

    def publish_post_with_gallery(
        self,
        title: str,
        content: str,
        slug: str,
        images: List[str],
        excerpt: Optional[str] = None
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

        Returns:
            True if published successfully, False otherwise
        """
        # Delegate to new two-message method for longer text support
        return self.publish_post_with_text_and_photos(
            title=title,
            content=content,
            slug=slug,
            images=images,
            excerpt=excerpt
        )

    def _build_photo_caption(
        self,
        title: str,
        content: str,
        excerpt: Optional[str],
        article_url: str
    ) -> str:
        """
        Build caption for photo post with 1020 char limit

        Structure:
        <b>Title</b>

        Preview text truncated at sentence boundary...

        <a href="url">Читать полностью на сайте</a>
        """
        MAX_CAPTION = 1020  # Safe limit (Telegram: 1024)

        # Fixed parts
        link_text = f'<a href="{article_url}">Читать полностью на сайте</a>'
        title_formatted = f"<b>{title}</b>"

        # Calculate available space for preview
        fixed_length = len(title_formatted) + len(link_text) + 4  # 4 = two "\n\n"
        max_preview_length = MAX_CAPTION - fixed_length

        # Get preview
        if excerpt and len(excerpt) <= max_preview_length:
            preview = excerpt
        else:
            preview = self._generate_short_preview(content, max_preview_length)

        # Build caption
        caption = f"{title_formatted}\n\n{preview}\n\n{link_text}"

        # Final length check
        if len(caption) > MAX_CAPTION:
            overflow = len(caption) - MAX_CAPTION
            preview = preview[:len(preview) - overflow - 3] + "..."
            caption = f"{title_formatted}\n\n{preview}\n\n{link_text}"

        return caption

    def _generate_short_preview(self, content: str, max_length: int) -> str:
        """
        Generate short preview for photo caption

        - Removes promotional content (HOUSLER mentions, CTAs)
        - Truncates at sentence boundary
        - Max length enforced
        """
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        if not paragraphs:
            return content[:max_length]

        # Filter promo content
        skip_words = [
            'housler', 'оставьте заявку', 'свяжется с вами',
            'агентство', '[оставьте заявку]', 'эксперт свяжется'
        ]

        content_paragraphs = []
        for paragraph in paragraphs:
            if any(word in paragraph.lower() for word in skip_words):
                continue
            content_paragraphs.append(paragraph)

        if not content_paragraphs:
            content_paragraphs = paragraphs[:2]

        # Build text up to limit
        result = ''
        for paragraph in content_paragraphs:
            test_result = result + ('\n\n' if result else '') + paragraph

            if len(test_result) > max_length:
                remaining = max_length - len(result) - (2 if result else 0)
                if remaining > 50:
                    partial = paragraph[:remaining]
                    # Find sentence end
                    for char in '.!?':
                        pos = partial.rfind(char)
                        if pos > remaining * 0.5:
                            result += ('\n\n' if result else '') + partial[:pos + 1]
                            break
                    else:
                        last_space = partial.rfind(' ')
                        if last_space > remaining * 0.5:
                            result += ('\n\n' if result else '') + partial[:last_space] + '...'
                break
            else:
                result = test_result

        return result.strip() or content[:max_length]

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
