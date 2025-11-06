#!/usr/bin/env python3
"""
Клиент для работы с IOPaint API
Отправляет запросы к запущенному IOPaint серверу
"""

import requests
import io
from PIL import Image
import numpy as np
import cv2
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class IOPaintClient:
    """
    Клиент для удаления водяных знаков через IOPaint API
    """

    def __init__(self, api_url='http://127.0.0.1:8080'):
        """
        Args:
            api_url: URL IOPaint сервера
        """
        self.api_url = api_url.rstrip('/')
        self.inpaint_endpoint = f'{self.api_url}/api/v1/inpaint'

    def check_availability(self) -> bool:
        """Проверить доступность IOPaint сервера"""
        try:
            response = requests.get(f'{self.api_url}/api/v1/model', timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"IOPaint недоступен: {e}")
            return False

    def create_watermark_mask(self, image: Image.Image, coverage_percent: float = 30) -> Image.Image:
        """
        Создать маску для нижней части изображения (где обычно водяной знак)

        Args:
            image: PIL Image
            coverage_percent: процент высоты изображения для маски

        Returns:
            PIL Image маска (белые области = удалить)
        """
        width, height = image.size

        # Создаем маску
        mask = np.zeros((height, width), dtype=np.uint8)

        # Нижняя область (водяной знак обычно там)
        mask_height = int(height * (coverage_percent / 100))
        mask[-mask_height:, :] = 255

        # Правый нижний угол (логотип)
        corner_h = min(100, int(height * 0.15))
        corner_w = min(250, int(width * 0.35))
        mask[-corner_h:, -corner_w:] = 255

        # Правый верхний угол (телефон)
        top_h = min(120, int(height * 0.15))
        top_w = min(300, int(width * 0.40))
        mask[:top_h, -top_w:] = 255

        return Image.fromarray(mask)

    def remove_watermark(
        self,
        image: Image.Image,
        mask: Optional[Image.Image] = None,
        coverage_percent: float = 30
    ) -> Optional[Image.Image]:
        """
        Удалить водяной знак используя IOPaint API

        Args:
            image: PIL Image (исходное изображение)
            mask: PIL Image (маска, белые области = удалить) или None для автоматической
            coverage_percent: процент покрытия для автоматической маски

        Returns:
            PIL Image (очищенное) или None при ошибке
        """
        try:
            # Создаем маску если не передана
            if mask is None:
                mask = self.create_watermark_mask(image, coverage_percent)

            # Конвертируем в bytes
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            mask_bytes = io.BytesIO()
            mask.save(mask_bytes, format='PNG')
            mask_bytes.seek(0)

            # Отправляем запрос к IOPaint
            files = {
                'image': ('image.png', img_bytes, 'image/png'),
                'mask': ('mask.png', mask_bytes, 'image/png')
            }

            data = {
                'ldmSteps': 25,  # Количество шагов (больше = лучше качество, но медленнее)
            }

            response = requests.post(
                self.inpaint_endpoint,
                files=files,
                data=data,
                timeout=60
            )

            if response.status_code == 200:
                result_image = Image.open(io.BytesIO(response.content))
                logger.info("✅ Водяной знак удален через IOPaint")
                return result_image
            else:
                logger.error(f"IOPaint вернул ошибку: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при обращении к IOPaint: {e}")
            return None

    def process_url(
        self,
        url: str,
        coverage_percent: float = 30
    ) -> Optional[Image.Image]:
        """
        Загрузить изображение по URL и удалить водяной знак

        Args:
            url: URL изображения
            coverage_percent: процент покрытия маской

        Returns:
            PIL Image или None
        """
        try:
            # Загружаем изображение
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Не удалось загрузить: {url}")
                return None

            image = Image.open(io.BytesIO(response.content))

            # Удаляем водяной знак
            return self.remove_watermark(image, coverage_percent=coverage_percent)

        except Exception as e:
            logger.error(f"Ошибка обработки {url}: {e}")
            return None

    def batch_process_urls(
        self,
        urls: list,
        coverage_percent: float = 30
    ) -> list:
        """
        Пакетная обработка нескольких URL

        Args:
            urls: список URL
            coverage_percent: процент покрытия маской

        Returns:
            список PIL Image (или None при ошибке)
        """
        results = []

        logger.info(f"🔄 Обработка {len(urls)} изображений через IOPaint...")

        for i, url in enumerate(urls):
            logger.info(f"  [{i+1}/{len(urls)}] {url[:50]}...")
            result = self.process_url(url, coverage_percent)
            results.append(result)

        success_count = sum(1 for r in results if r is not None)
        logger.info(f"✅ Обработано {success_count}/{len(urls)} изображений")

        return results


def demo():
    """Демонстрация работы IOPaint клиента"""

    # Проверяем доступность IOPaint
    client = IOPaintClient()

    print("=" * 80)
    print("🧪 ТЕСТ IOPAINT CLIENT")
    print("=" * 80)

    if not client.check_availability():
        print("\n❌ IOPaint сервер недоступен!")
        print("\nЗапустите IOPaint сервер в отдельном терминале:")
        print("  conda activate iopaint")
        print("  iopaint start --model=lama --port=8080")
        return

    print("✅ IOPaint сервер доступен")

    # Тестовое изображение с Cian
    test_url = "https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-1.jpg"

    print(f"\n📥 Загружаем: {test_url[:60]}...")

    result = client.process_url(test_url, coverage_percent=25)

    if result:
        import os
        os.makedirs('test_images', exist_ok=True)
        result.save('test_images/iopaint_cleaned.jpg')
        print(f"\n✅ Результат сохранен: test_images/iopaint_cleaned.jpg")
        print(f"   Размер: {result.size[0]}x{result.size[1]} px")
    else:
        print("\n❌ Ошибка обработки")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    demo()
