"""
Экспортер данных парсинга в красивый Markdown формат
"""

from typing import List, Dict
from datetime import datetime


class MarkdownExporter:
    """Экспортирует данные парсинга в читаемый Markdown файл"""

    @staticmethod
    def export_to_markdown(results: List[Dict], filename: str = None) -> str:
        """
        Экспортирует результаты парсинга в Markdown файл

        Args:
            results: Список результатов парсинга
            filename: Имя файла (если None, создается автоматически)

        Returns:
            Путь к созданному файлу
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cian_results_{timestamp}.md"

        md_content = MarkdownExporter._generate_markdown(results)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md_content)

        return filename

    @staticmethod
    def _generate_markdown(results: List[Dict]) -> str:
        """Генерирует Markdown контент из результатов"""
        lines = []

        # Заголовок
        lines.append("# Результаты парсинга Cian.ru")
        lines.append("")
        lines.append(f"**Дата парсинга:** {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append(f"**Всего объявлений:** {len(results)}")
        lines.append("")

        # Статистика
        successful = len([r for r in results if r.get('title')])
        lines.append("## 📊 Статистика")
        lines.append("")
        lines.append(f"- ✅ Успешно обработано: **{successful}/{len(results)}** ({successful/len(results)*100:.1f}%)")
        lines.append("")

        # Содержание
        lines.append("## 📑 Содержание")
        lines.append("")
        for i, result in enumerate(results, 1):
            if result.get('title'):
                title = result['title'][:80]
                lines.append(f"{i}. [{title}](#объявление-{i})")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Детальная информация по каждому объявлению
        for i, result in enumerate(results, 1):
            lines.extend(MarkdownExporter._format_listing(result, i))
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_listing(data: Dict, number: int) -> List[str]:
        """Форматирует одно объявление"""
        lines = []

        lines.append(f"## Объявление {number}")
        lines.append("")

        # Заголовок и основная информация
        if data.get('title'):
            lines.append(f"### {data['title']}")
            lines.append("")

        # Ссылка на объявление
        if data.get('url'):
            lines.append(f"🔗 **Ссылка:** {data['url']}")
            lines.append("")

        # Цена
        if data.get('price'):
            lines.append(f"### 💰 {data['price']}")
            lines.append("")

        # Основные характеристики
        lines.append("### 📋 Основные характеристики")
        lines.append("")

        if data.get('address'):
            lines.append(f"- **📍 Адрес:** {data['address']}")

        if data.get('metro'):
            metro_list = ', '.join(data['metro'])
            lines.append(f"- **🚇 Метро:** {metro_list}")

        if data.get('area'):
            lines.append(f"- **📏 Площадь:** {data['area']}")

        if data.get('floor'):
            lines.append(f"- **🏢 Этаж:** {data['floor']}")

        if data.get('rooms'):
            lines.append(f"- **🚪 Комнат:** {data['rooms']}")

        lines.append("")

        # Описание
        if data.get('description'):
            lines.append("### 📝 Описание")
            lines.append("")
            lines.append(data['description'])
            lines.append("")

        # Дополнительные характеристики
        if data.get('characteristics'):
            lines.append("### 🔍 Дополнительные характеристики")
            lines.append("")
            for key, value in data['characteristics'].items():
                if value:
                    lines.append(f"- **{key}:** {value}")
            lines.append("")

        # Похожие объявления
        if data.get('similar_listings'):
            lines.append("### 🏘️ Похожие объявления")
            lines.append("")
            for similar in data['similar_listings'][:5]:  # Первые 5
                title = similar.get('title', 'Без названия')[:70]
                price = similar.get('price', 'Цена не указана')
                url = similar.get('url', '#')
                lines.append(f"- [{title}]({url}) — {price}")
            lines.append("")

        # Изображения
        if data.get('images'):
            lines.append("### 📷 Изображения")
            lines.append("")
            lines.append(f"**Всего изображений:** {len(data['images'])}")
            lines.append("")

            # Показываем первые 3 изображения
            if len(data['images']) > 0:
                lines.append("#### Превью изображений")
                lines.append("")
                for img in data['images'][:3]:
                    # Встраиваем изображение в Markdown (будет отображаться в превью)
                    lines.append(f"![Изображение]({img})")
                lines.append("")

            # Остальные в выпадающем списке
            lines.append("<details>")
            lines.append("<summary>Показать все ссылки на изображения</summary>")
            lines.append("")
            for j, img in enumerate(data['images'], 1):
                lines.append(f"{j}. {img}")
            lines.append("")
            lines.append("</details>")
            lines.append("")

            # Инструкция по скачиванию изображений без водяных знаков
            if len(data['images']) > 0:
                lines.append("<details>")
                lines.append("<summary>💡 Как скачать изображения без водяных знаков</summary>")
                lines.append("")
                lines.append("Замените в URL изображения:")
                lines.append("- `/images/` на `/images-no-watermark/`")
                lines.append("- Или добавьте `?no-watermark=1` в конец URL")
                lines.append("")
                lines.append("Пример:")
                lines.append("```")
                if data['images']:
                    example_img = data['images'][0]
                    no_wm_img = example_img.replace('/images/', '/images-no-watermark/')
                    lines.append(f"С водяным знаком:  {example_img}")
                    lines.append(f"Без водяного знака: {no_wm_img}")
                lines.append("```")
                lines.append("</details>")
                lines.append("")

        # Геолокация
        if data.get('coordinates'):
            coords = data['coordinates']
            if coords.get('lat') and coords.get('lon'):
                lines.append("### 🗺️ Расположение")
                lines.append("")
                lines.append(f"- **Координаты:** {coords['lat']}, {coords['lon']}")
                # Добавляем ссылку на Яндекс.Карты
                yandex_maps_url = f"https://yandex.ru/maps/?ll={coords['lon']},{coords['lat']}&z=16&pt={coords['lon']},{coords['lat']},pm2rdm"
                lines.append(f"- **[Открыть на Яндекс.Картах]({yandex_maps_url})**")
                lines.append("")

        # Контакты
        if data.get('phone') or data.get('agent_name'):
            lines.append("### 📞 Контакты")
            lines.append("")
            if data.get('agent_name'):
                lines.append(f"- **Агент:** {data['agent_name']}")
            if data.get('phone'):
                lines.append(f"- **Телефон:** {data['phone']}")
            lines.append("")

        # Дата публикации
        if data.get('published_date'):
            lines.append(f"**📅 Опубликовано:** {data['published_date']}")
            lines.append("")

        # Ошибки (если есть)
        if data.get('error'):
            lines.append("### ⚠️ Ошибка при парсинге")
            lines.append("")
            lines.append("```")
            lines.append(data['error'])
            lines.append("```")
            lines.append("")

        return lines


def save_results_as_markdown(results: List[Dict], filename: str = None) -> str:
    """
    Удобная функция для сохранения результатов в Markdown

    Args:
        results: Список результатов парсинга
        filename: Имя файла (опционально)

    Returns:
        Путь к созданному файлу
    """
    return MarkdownExporter.export_to_markdown(results, filename)
