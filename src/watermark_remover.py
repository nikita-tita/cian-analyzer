#!/usr/bin/env python3
"""
Модуль для удаления водяных знаков с фото недвижимости
Использует OpenCV inpainting для быстрой и качественной очистки
"""

import cv2
import numpy as np
from PIL import Image
import requests
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WatermarkRemover:
    """
    Удаление водяных знаков с фотографий
    """

    def __init__(self, method='telea'):
        """
        Args:
            method: 'telea' или 'ns' (Navier-Stokes)
        """
        self.method = method

    def detect_watermark_region(self, image: np.ndarray, position='bottom-right') -> Optional[np.ndarray]:
        """
        Автоматическое определение области водяного знака

        Args:
            image: изображение в формате numpy array (BGR)
            position: 'bottom-right', 'bottom-left', 'top-right', 'top-left', 'center'

        Returns:
            Маска области водяного знака
        """
        height, width = image.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)

        # Типичные позиции водяных знаков на Cian
        if position == 'bottom-right':
            # Правый нижний угол (логотип Cian)
            # Обычно 150x60 px в правом нижнем углу
            x1, y1 = max(0, width - 200), max(0, height - 80)
            x2, y2 = width, height
            mask[y1:y2, x1:x2] = 255

        elif position == 'bottom-left':
            # Левый нижний угол
            x1, y1 = 0, max(0, height - 80)
            x2, y2 = 200, height
            mask[y1:y2, x1:x2] = 255

        elif position == 'top-right':
            # Правый верхний угол (телефон)
            x1, y1 = max(0, width - 250), 0
            x2, y2 = width, 100
            mask[y1:y2, x1:x2] = 255

        elif position == 'center':
            # Центр изображения (иногда бывает)
            center_x, center_y = width // 2, height // 2
            x1, y1 = max(0, center_x - 150), max(0, center_y - 50)
            x2, y2 = min(width, center_x + 150), min(height, center_y + 50)
            mask[y1:y2, x1:x2] = 255

        return mask

    def detect_watermark_by_color(self, image: np.ndarray, target_color='white', tolerance=30) -> np.ndarray:
        """
        Определение водяного знака по цвету

        Args:
            image: изображение в BGR формате
            target_color: 'white', 'black', 'logo' (зеленый Cian)
            tolerance: допуск цвета

        Returns:
            Маска водяного знака
        """
        if target_color == 'white':
            # Белые/светлые надписи
            lower = np.array([200, 200, 200])
            upper = np.array([255, 255, 255])
        elif target_color == 'black':
            # Черные надписи
            lower = np.array([0, 0, 0])
            upper = np.array([tolerance, tolerance, tolerance])
        elif target_color == 'logo':
            # Зеленый логотип Cian (примерно)
            lower = np.array([0, 100, 0])
            upper = np.array([100, 255, 100])
        else:
            raise ValueError(f"Unknown color: {target_color}")

        mask = cv2.inRange(image, lower, upper)

        # Морфология для улучшения маски
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)

        return mask

    def detect_transparent_watermark(self, image: np.ndarray) -> np.ndarray:
        """
        Обнаружение полупрозрачных водяных знаков через анализ текстур

        Args:
            image: изображение в BGR формате

        Returns:
            Маска водяного знака
        """
        # Конвертируем в grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Применяем адаптивный порог для выделения текста
        # Это помогает найти полупрозрачный текст
        adaptive_thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # Также ищем очень светлые области (полупрозрачный белый текст)
        _, light_mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)

        # Комбинируем обе маски
        combined = cv2.bitwise_or(adaptive_thresh, light_mask)

        # Морфология для очистки шума
        kernel = np.ones((2, 2), np.uint8)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)

        # Убираем мелкие области (шум)
        # Оставляем только значительные регионы
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mask = np.zeros_like(combined)

        for contour in contours:
            area = cv2.contourArea(contour)
            # Только если область больше 100px (фильтруем шум)
            if area > 100:
                cv2.drawContours(mask, [contour], -1, 255, -1)

        return mask

    def remove_watermark(
        self,
        image: np.ndarray,
        mask: Optional[np.ndarray] = None,
        auto_detect_positions: list = None
    ) -> np.ndarray:
        """
        Удаление водяного знака с изображения

        Args:
            image: исходное изображение (BGR)
            mask: маска водяного знака (если None - автоопределение)
            auto_detect_positions: список позиций для автопоиска

        Returns:
            Очищенное изображение
        """
        if mask is None:
            # Автоматическое определение
            if auto_detect_positions is None:
                auto_detect_positions = ['bottom-right']

            # Создаем комбинированную маску
            combined_mask = np.zeros(image.shape[:2], dtype=np.uint8)
            for pos in auto_detect_positions:
                pos_mask = self.detect_watermark_region(image, position=pos)
                combined_mask = cv2.bitwise_or(combined_mask, pos_mask)

            mask = combined_mask

        # Inpainting - магия удаления
        if self.method == 'telea':
            result = cv2.inpaint(image, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
        else:  # ns
            result = cv2.inpaint(image, mask, inpaintRadius=3, flags=cv2.INPAINT_NS)

        return result

    def process_url(
        self,
        url: str,
        auto_detect_positions: list = ['bottom-right']
    ) -> Optional[Image.Image]:
        """
        Загрузка и обработка изображения по URL

        Args:
            url: URL изображения
            auto_detect_positions: позиции для автопоиска водяных знаков

        Returns:
            PIL Image или None при ошибке
        """
        try:
            # Загрузка
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to download: {url}")
                return None

            # Конвертация в OpenCV формат
            pil_image = Image.open(io.BytesIO(response.content))
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            # Удаление водяных знаков
            cleaned = self.remove_watermark(
                cv_image,
                auto_detect_positions=auto_detect_positions
            )

            # Обратно в PIL
            cleaned_rgb = cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB)
            result = Image.fromarray(cleaned_rgb)

            logger.info(f"✅ Watermark removed from {url[:50]}...")
            return result

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            return None

    def batch_process_urls(
        self,
        urls: list,
        auto_detect_positions: list = ['bottom-right'],
        max_concurrent: int = 5
    ) -> list:
        """
        Пакетная обработка нескольких URL

        Args:
            urls: список URL изображений
            auto_detect_positions: позиции для автопоиска
            max_concurrent: максимум одновременных загрузок

        Returns:
            список PIL Image (или None при ошибке)
        """
        results = []

        logger.info(f"🔄 Processing {len(urls)} images...")

        for i, url in enumerate(urls):
            logger.info(f"  [{i+1}/{len(urls)}] {url[:50]}...")
            result = self.process_url(url, auto_detect_positions)
            results.append(result)

        success_count = sum(1 for r in results if r is not None)
        logger.info(f"✅ Successfully processed {success_count}/{len(urls)} images")

        return results


def demo():
    """Демонстрация работы"""

    # Тестовый URL с Cian
    test_url = "https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-1.jpg"

    print("=" * 80)
    print("🧪 ДЕМОНСТРАЦИЯ УДАЛЕНИЯ ВОДЯНЫХ ЗНАКОВ")
    print("=" * 80)

    remover = WatermarkRemover(method='telea')

    print(f"\n📥 Загружаем: {test_url[:60]}...")

    # Обработка
    result = remover.process_url(
        test_url,
        auto_detect_positions=['bottom-right', 'top-right', 'bottom-left']
    )

    if result:
        # Сохранение
        import os
        os.makedirs('test_images', exist_ok=True)
        result.save('test_images/cleaned.jpg')
        print("\n✅ Результат сохранен: test_images/cleaned.jpg")
        print(f"   Размер: {result.size[0]}x{result.size[1]} px")
    else:
        print("\n❌ Ошибка обработки")

    print("\n" + "=" * 80)
    print("💡 СОВЕТ: Откройте test_images/cleaned.jpg чтобы увидеть результат!")
    print("=" * 80)


if __name__ == '__main__':
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    demo()
