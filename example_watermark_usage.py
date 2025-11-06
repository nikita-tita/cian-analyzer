#!/usr/bin/env python3
"""
Примеры использования модуля удаления водяных знаков
"""

from src.watermark_remover import WatermarkRemover
from PIL import Image


def example_1_single_url():
    """Пример 1: Обработка одного изображения по URL"""
    print("=" * 80)
    print("ПРИМЕР 1: Обработка одного URL")
    print("=" * 80)

    # Создаем ремувер
    remover = WatermarkRemover(method='telea')

    # URL фото с Cian
    url = "https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-1.jpg"

    # Обрабатываем (водяные знаки обычно в правом нижнем и верхнем углу)
    cleaned_image = remover.process_url(
        url=url,
        auto_detect_positions=['bottom-right', 'top-right']
    )

    if cleaned_image:
        cleaned_image.save('example_cleaned_1.jpg')
        print(f"✅ Сохранено: example_cleaned_1.jpg")

    print()


def example_2_batch_urls():
    """Пример 2: Пакетная обработка нескольких URL"""
    print("=" * 80)
    print("ПРИМЕР 2: Пакетная обработка")
    print("=" * 80)

    remover = WatermarkRemover(method='telea')

    # Список URL
    urls = [
        "https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-1.jpg",
        "https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-2.jpg",
    ]

    # Обрабатываем все сразу
    results = remover.batch_process_urls(
        urls=urls,
        auto_detect_positions=['bottom-right', 'top-right', 'bottom-left']
    )

    # Сохраняем результаты
    for i, img in enumerate(results):
        if img:
            img.save(f'example_batch_{i+1}.jpg')
            print(f"✅ Сохранено: example_batch_{i+1}.jpg")

    print()


def example_3_custom_mask():
    """Пример 3: Использование своей маски"""
    print("=" * 80)
    print("ПРИМЕР 3: Кастомная маска")
    print("=" * 80)

    import cv2
    import numpy as np
    import requests
    import io

    remover = WatermarkRemover(method='telea')

    # Загружаем изображение
    url = "https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-1.jpg"
    response = requests.get(url, timeout=10)
    pil_image = Image.open(io.BytesIO(response.content))
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    height, width = cv_image.shape[:2]

    # Создаем свою маску (нижние 20% изображения)
    custom_mask = np.zeros((height, width), dtype=np.uint8)
    bottom_height = int(height * 0.20)
    custom_mask[-bottom_height:, :] = 255  # Белая область = удалить

    # Применяем inpainting с нашей маской
    cleaned = remover.remove_watermark(cv_image, mask=custom_mask)

    # Сохраняем
    cleaned_rgb = cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB)
    result = Image.fromarray(cleaned_rgb)
    result.save('example_custom_mask.jpg')

    print(f"✅ Сохранено: example_custom_mask.jpg")
    print()


def example_4_integrate_with_parser():
    """Пример 4: Интеграция с парсером Cian"""
    print("=" * 80)
    print("ПРИМЕР 4: Интеграция с парсером")
    print("=" * 80)

    # Представим, что у нас есть результат парсинга
    # с массивом URL фотографий

    parsed_data = {
        'images': [
            'https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-1.jpg',
            'https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-2.jpg',
        ],
        'similar_listings': [
            {
                'images': [
                    'https://images.cdn-cian.ru/images/kvartira-sanktpeterburg-svetlanovskiy-prospekt-2440029683-3.jpg',
                ]
            }
        ]
    }

    # Создаем ремувер
    remover = WatermarkRemover(method='telea')

    # Собираем все URL фотографий
    all_image_urls = parsed_data['images'].copy()
    for listing in parsed_data['similar_listings']:
        all_image_urls.extend(listing.get('images', []))

    print(f"📊 Всего фотографий: {len(all_image_urls)}")

    # Обрабатываем все фото
    cleaned_images = remover.batch_process_urls(
        urls=all_image_urls,
        auto_detect_positions=['bottom-right', 'top-right']
    )

    # Сохраняем
    import os
    os.makedirs('cleaned_photos', exist_ok=True)

    for i, img in enumerate(cleaned_images):
        if img:
            img.save(f'cleaned_photos/photo_{i+1}.jpg')

    print(f"✅ Обработано и сохранено в: cleaned_photos/")
    print()


if __name__ == '__main__':
    print("\n" + "🧪 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ WATERMARK REMOVER\n")

    # Запускаем примеры
    example_1_single_url()
    example_2_batch_urls()
    example_3_custom_mask()
    example_4_integrate_with_parser()

    print("=" * 80)
    print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ!")
    print("=" * 80)
    print("\n📂 Проверьте созданные файлы:")
    print("   • example_cleaned_1.jpg")
    print("   • example_batch_*.jpg")
    print("   • example_custom_mask.jpg")
    print("   • cleaned_photos/")
    print()
