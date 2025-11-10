"""
Экспортер данных парсинга в простой TXT формат
"""

from typing import List, Dict
from datetime import datetime


class TxtExporter:
    """Экспортирует данные парсинга в простой текстовый файл"""

    @staticmethod
    def export_to_txt(results: List[Dict], filename: str = None) -> str:
        """
        Экспортирует результаты парсинга в TXT файл

        Args:
            results: Список результатов парсинга
            filename: Имя файла (если None, создается автоматически)

        Returns:
            Путь к созданному файлу
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cian_results_{timestamp}.txt"

        txt_content = TxtExporter._generate_txt(results)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(txt_content)

        return filename

    @staticmethod
    def _generate_txt(results: List[Dict]) -> str:
        """Генерирует TXT контент из результатов"""
        lines = []

        # Заголовок
        lines.append("=" * 80)
        lines.append("РЕЗУЛЬТАТЫ ПАРСИНГА CIAN.RU")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Дата парсинга: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append(f"Всего объявлений: {len(results)}")
        lines.append("")

        # Статистика
        successful = len([r for r in results if r.get('title')])
        lines.append("-" * 80)
        lines.append("СТАТИСТИКА")
        lines.append("-" * 80)
        lines.append(f"Успешно обработано: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
        lines.append("")

        # Содержание
        lines.append("-" * 80)
        lines.append("СОДЕРЖАНИЕ")
        lines.append("-" * 80)
        for i, result in enumerate(results, 1):
            if result.get('title'):
                title = result['title'][:70]
                lines.append(f"{i}. {title}")
        lines.append("")

        # Детальная информация по каждому объявлению
        for i, result in enumerate(results, 1):
            lines.extend(TxtExporter._format_listing(result, i))
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_listing(data: Dict, number: int) -> List[str]:
        """Форматирует одно объявление"""
        lines = []

        lines.append("=" * 80)
        lines.append(f"ОБЪЯВЛЕНИЕ {number}")
        lines.append("=" * 80)
        lines.append("")

        # Заголовок
        if data.get('title'):
            lines.append(data['title'])
            lines.append("")

        # Ссылка
        if data.get('url'):
            lines.append(f"Ссылка: {data['url']}")
            lines.append("")

        # Цена
        if data.get('price'):
            lines.append(f"ЦЕНА: {data['price']}")
            lines.append("")

        # Основная информация
        lines.append("-" * 80)
        lines.append("ОСНОВНАЯ ИНФОРМАЦИЯ")
        lines.append("-" * 80)

        if data.get('address'):
            lines.append(f"Адрес: {data['address']}")

        if data.get('metro'):
            metro_list = ', '.join(data['metro']) if isinstance(data['metro'], list) else data['metro']
            lines.append(f"Метро: {metro_list}")

        if data.get('area'):
            lines.append(f"Площадь: {data['area']}")

        if data.get('floor'):
            lines.append(f"Этаж: {data['floor']}")

        if data.get('rooms'):
            lines.append(f"Комнат: {data['rooms']}")

        lines.append("")

        # Описание
        if data.get('description'):
            lines.append("-" * 80)
            lines.append("ОПИСАНИЕ")
            lines.append("-" * 80)
            lines.append(data['description'])
            lines.append("")

        # Характеристики
        if data.get('characteristics'):
            lines.append("-" * 80)
            lines.append("ХАРАКТЕРИСТИКИ")
            lines.append("-" * 80)
            for key, value in data['characteristics'].items():
                if value:
                    lines.append(f"  {key}: {value}")
            lines.append("")

        # Похожие объявления
        if data.get('similar_listings'):
            lines.append("-" * 80)
            lines.append(f"ПОХОЖИЕ ОБЪЯВЛЕНИЯ ({len(data['similar_listings'])})")
            lines.append("-" * 80)
            for idx, similar in enumerate(data['similar_listings'][:5], 1):
                title = similar.get('title', 'Без названия')[:60]
                price = similar.get('price', 'Цена не указана')
                url = similar.get('url', '')
                lines.append(f"{idx}. {title}")
                lines.append(f"   Цена: {price}")
                if url:
                    lines.append(f"   Ссылка: {url}")
                lines.append("")

        # Изображения
        if data.get('images'):
            lines.append("-" * 80)
            lines.append(f"ИЗОБРАЖЕНИЯ ({len(data['images'])})")
            lines.append("-" * 80)
            lines.append("Ссылки на изображения:")
            for i, img in enumerate(data['images'], 1):
                lines.append(f"{i}. {img}")
            lines.append("")

            # Инструкция по водяным знакам
            if len(data['images']) > 0:
                lines.append("КАК СКАЧАТЬ БЕЗ ВОДЯНЫХ ЗНАКОВ:")
                lines.append("Замените в URL изображения:")
                lines.append("  /images/ --> /images-no-watermark/")
                lines.append("Или добавьте ?no-watermark=1 в конец URL")
                example_img = data['images'][0]
                no_wm_img = example_img.replace('/images/', '/images-no-watermark/')
                lines.append("Пример:")
                lines.append(f"  С водяным знаком:  {example_img}")
                lines.append(f"  Без водяного знака: {no_wm_img}")
                lines.append("")

        # Координаты
        if data.get('coordinates'):
            coords = data['coordinates']
            if coords.get('lat') and coords.get('lon'):
                lines.append("-" * 80)
                lines.append("РАСПОЛОЖЕНИЕ")
                lines.append("-" * 80)
                lines.append(f"Координаты: {coords['lat']}, {coords['lon']}")
                yandex_maps_url = f"https://yandex.ru/maps/?ll={coords['lon']},{coords['lat']}&z=16&pt={coords['lon']},{coords['lat']},pm2rdm"
                lines.append(f"Яндекс.Карты: {yandex_maps_url}")
                lines.append("")

        # Контакты
        if data.get('phone') or data.get('agent_name'):
            lines.append("-" * 80)
            lines.append("КОНТАКТЫ")
            lines.append("-" * 80)
            if data.get('agent_name'):
                lines.append(f"Агент: {data['agent_name']}")
            if data.get('phone'):
                lines.append(f"Телефон: {data['phone']}")
            lines.append("")

        # Дата публикации
        if data.get('published_date'):
            lines.append(f"Опубликовано: {data['published_date']}")
            lines.append("")

        # Ошибки
        if data.get('error'):
            lines.append("-" * 80)
            lines.append("ОШИБКА ПРИ ПАРСИНГЕ")
            lines.append("-" * 80)
            lines.append(data['error'])
            lines.append("")

        return lines


def save_results_as_txt(results: List[Dict], filename: str = None) -> str:
    """
    Удобная функция для сохранения результатов в TXT

    Args:
        results: Список результатов парсинга
        filename: Имя файла (опционально)

    Returns:
        Путь к созданному файлу
    """
    return TxtExporter.export_to_txt(results, filename)
