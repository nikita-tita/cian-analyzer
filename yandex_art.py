"""
YandexART Integration for Blog Cover Generation

Generates black-and-white cover images in unified style:
- Hand-drawn pencil sketch + Pixar-like 3D objects
- 16:9 aspect ratio
- No text or symbols
"""

import os
import time
import base64
import random
import requests
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class YandexART:
    """
    Cover image generator using YandexART API

    Uses same credentials as YandexGPT:
    - YANDEX_API_KEY
    - YANDEX_FOLDER_ID
    """

    # Prompt must be under 500 chars total (including title)
    # Template ~220 chars + title ~150 chars max = ~370 chars
    PROMPT_TEMPLATE = '''"{title}" Black and white pencil sketch + Pixar 3D illustration. Modern buildings with soft volume, grayscale pencil shading, market trend arrows. 16:9 wide format. No text or letters. Clean background, high detail.'''

    def __init__(self, covers_dir: str = "static/blog/covers"):
        """
        Args:
            covers_dir: Directory for saving covers (relative to project root)
        """
        self.api_key = os.getenv('YANDEX_API_KEY')
        self.folder_id = os.getenv('YANDEX_FOLDER_ID')

        # API endpoints
        self.generation_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
        self.operations_url = "https://llm.api.cloud.yandex.net/operations"

        # Settings
        self.enabled = os.getenv('YANDEX_ART_ENABLED', 'true').lower() == 'true'
        self.timeout = int(os.getenv('YANDEX_ART_TIMEOUT', '60'))
        self.poll_interval = 2  # seconds between status checks

        # Covers directory
        self.covers_dir = Path(covers_dir)

        if self.enabled and (not self.api_key or not self.folder_id):
            logger.warning("YandexART: YANDEX_API_KEY or YANDEX_FOLDER_ID not set, disabling")
            self.enabled = False

    def ensure_covers_dir(self):
        """Create covers directory if not exists"""
        self.covers_dir.mkdir(parents=True, exist_ok=True)

    def generate_cover(
        self,
        title: str,
        slug: str,
        force: bool = False
    ) -> Optional[str]:
        """
        Generate cover image for article

        Args:
            title: Article title (used in prompt)
            slug: URL slug (used as filename)
            force: Overwrite if file exists

        Returns:
            Relative path to cover ("/static/blog/covers/<slug>.png")
            or None on error/disabled
        """
        if not self.enabled:
            logger.debug("YandexART disabled, skipping cover generation")
            return None

        self.ensure_covers_dir()

        # Check if file exists
        filepath = self.covers_dir / f"{slug}.png"
        if filepath.exists() and not force:
            logger.info(f"Cover already exists: {filepath}")
            return f"/static/blog/covers/{slug}.png"

        try:
            logger.info(f"Generating cover for: {title[:50]}...")

            # 1. Start generation
            operation_id = self._start_generation(title)
            if not operation_id:
                return None

            # 2. Wait for result
            image_base64 = self._wait_for_result(operation_id)
            if not image_base64:
                return None

            # 3. Save file
            return self._save_image(image_base64, slug)

        except requests.exceptions.Timeout:
            logger.error(f"YandexART request timeout for '{title[:30]}...'")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"YandexART request error: {e}")
            return None
        except Exception as e:
            logger.error(f"YandexART unexpected error: {e}")
            return None

    def _start_generation(self, title: str) -> Optional[str]:
        """
        Send image generation request

        Returns:
            operation_id for tracking or None on error
        """
        prompt = self.PROMPT_TEMPLATE.format(title=title)

        payload = {
            "modelUri": f"art://{self.folder_id}/yandex-art/latest",
            "generationOptions": {
                "seed": random.randint(1, 1_000_000),
                "aspectRatio": {
                    "widthRatio": 16,
                    "heightRatio": 9
                }
            },
            "messages": [
                {
                    "weight": 1,
                    "text": prompt
                }
            ]
        }

        response = requests.post(
            self.generation_url,
            headers={
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"YandexART API error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()
        operation_id = data.get("id")

        if not operation_id:
            logger.error(f"YandexART: no operation_id in response: {data}")
            return None

        logger.debug(f"YandexART generation started: {operation_id}")
        return operation_id

    def _wait_for_result(self, operation_id: str) -> Optional[str]:
        """
        Wait for generation completion (polling)

        Returns:
            base64-encoded image or None on error/timeout
        """
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            response = requests.get(
                f"{self.operations_url}/{operation_id}",
                headers={"Authorization": f"Api-Key {self.api_key}"},
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"YandexART status check failed: {response.status_code}")
                return None

            data = response.json()

            if data.get("done"):
                # Check for generation error
                if "error" in data:
                    error = data["error"]
                    logger.error(f"YandexART generation failed: {error.get('message', error)}")
                    return None

                # Extract image
                image_base64 = data.get("response", {}).get("image")
                if image_base64:
                    elapsed = time.time() - start_time
                    logger.info(f"YandexART generation completed in {elapsed:.1f}s")
                    return image_base64
                else:
                    logger.error("YandexART: no image in response")
                    return None

            time.sleep(self.poll_interval)

        logger.warning(f"YandexART generation timeout after {self.timeout}s")
        return None

    def _save_image(self, image_base64: str, slug: str) -> str:
        """
        Save base64 image to file

        Returns:
            Relative path for HTML/DB usage
        """
        image_data = base64.b64decode(image_base64)

        filename = f"{slug}.png"
        filepath = self.covers_dir / filename

        with open(filepath, "wb") as f:
            f.write(image_data)

        relative_path = f"/static/blog/covers/{filename}"
        logger.info(f"Saved cover: {relative_path} ({len(image_data) / 1024:.1f} KB)")

        return relative_path

    def cover_exists(self, slug: str) -> bool:
        """Check if cover exists"""
        return (self.covers_dir / f"{slug}.png").exists()

    def get_cover_path(self, slug: str) -> Optional[str]:
        """Get cover path if exists"""
        if self.cover_exists(slug):
            return f"/static/blog/covers/{slug}.png"
        return None
