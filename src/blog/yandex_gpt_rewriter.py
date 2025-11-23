"""
Интеграция с Яндекс GPT для рерайтинга статей
"""

import os
import logging
import requests
from typing import Optional
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class YandexGPTRewriter:
    """Рерайтер статей через Яндекс GPT"""

    def __init__(self, api_key: Optional[str] = None, folder_id: Optional[str] = None):
        """
        Args:
            api_key: API ключ Яндекс Cloud (или из переменной окружения YANDEX_API_KEY)
            folder_id: ID каталога Яндекс Cloud (или из переменной окружения YANDEX_FOLDER_ID)
        """
        self.api_key = api_key or os.getenv('YANDEX_API_KEY')
        self.folder_id = folder_id or os.getenv('YANDEX_FOLDER_ID')
        self.api_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        if not self.api_key or not self.folder_id:
            logger.warning(
                "Яндекс GPT API ключ или folder_id не настроены. "
                "Установите переменные окружения YANDEX_API_KEY и YANDEX_FOLDER_ID"
            )

    def rewrite_article(
        self,
        original_content: str,
        title: str,
        preserve_html: bool = True,
        style: str = "professional"
    ) -> str:
        """
        Рерайтит статью через Яндекс GPT

        Args:
            original_content: Оригинальный текст статьи (может содержать HTML)
            title: Заголовок статьи
            preserve_html: Сохранять HTML разметку
            style: Стиль рерайта (professional, casual, technical)

        Returns:
            Рерайченный текст с HTML разметкой
        """
        if not self.api_key or not self.folder_id:
            logger.warning("Яндекс GPT не настроен, возвращаем оригинальный текст с базовой разметкой")
            return self._format_original_content(original_content)

        try:
            # Очищаем HTML для передачи в GPT
            clean_text = self._clean_html(original_content)

            # Создаем промпт для рерайта
            prompt = self._create_rewrite_prompt(clean_text, title, style, preserve_html)

            # Отправляем запрос к Яндекс GPT
            response = self._call_yandex_gpt(prompt)

            if response:
                # Постобработка: добавляем HTML разметку если её нет
                formatted_response = self._ensure_html_formatting(response)
                return formatted_response
            else:
                logger.warning("Пустой ответ от Яндекс GPT, возвращаем оригинал")
                return self._format_original_content(original_content)

        except Exception as e:
            logger.error(f"Ошибка рерайта через Яндекс GPT: {e}")
            return self._format_original_content(original_content)

    def _clean_html(self, html_content: str) -> str:
        """Убирает HTML теги, оставляя только текст"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Удаляем скрипты и стили
        for script in soup(['script', 'style']):
            script.decompose()

        # Получаем текст
        text = soup.get_text()

        # Убираем лишние пробелы и переносы
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text

    def _create_rewrite_prompt(
        self,
        content: str,
        title: str,
        style: str,
        preserve_html: bool
    ) -> str:
        """Создает промпт для рерайта"""

        style_instructions = {
            "professional": "профессионально и экспертно, с акцентом на факты и полезность",
            "casual": "легко и понятно, как разговор с другом",
            "technical": "технически подробно, с терминологией для специалистов"
        }

        style_desc = style_instructions.get(style, style_instructions["professional"])

        prompt = f"""Ты - профессиональный копирайтер для сайта о недвижимости Housler.

Твоя задача: переписать следующую статью "{title}" так, чтобы:

1. Текст был ПОЛНОСТЬЮ уникальным (никаких прямых цитат из оригинала)
2. Сохранилась вся ключевая информация и факты
3. Стиль был {style_desc}
4. Текст был хорошо структурирован с подзаголовками
5. Использовалась HTML разметка: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>
6. Объем текста был примерно таким же или немного больше
7. Текст был полезным и интересным для читателей

ВАЖНО:
- НЕ используй фразы типа "в статье говорится", "автор пишет" и т.п.
- Пиши от лица эксперта, который делится знаниями
- Добавь практические советы где уместно
- Используй подзаголовки для структуры (теги <h2>, <h3>)
- Каждый абзац оборачивай в тег <p>
- Списки оформляй через <ul><li>

Оригинальный текст для рерайта:
{content}

Напиши ТОЛЬКО рерайченный текст с HTML разметкой, без комментариев и пояснений:"""

        return prompt

    def _call_yandex_gpt(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """Отправляет запрос к Яндекс GPT API"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.api_key}"
        }

        data = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": 8000
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=120
            )

            response.raise_for_status()
            result = response.json()

            # Извлекаем текст ответа
            if 'result' in result and 'alternatives' in result['result']:
                alternatives = result['result']['alternatives']
                if alternatives and len(alternatives) > 0:
                    return alternatives[0]['message']['text']

            logger.warning(f"Неожиданный формат ответа от Яндекс GPT: {result}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка HTTP запроса к Яндекс GPT: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при вызове Яндекс GPT: {e}")
            return None

    def _ensure_html_formatting(self, text: str) -> str:
        """Проверяет наличие HTML разметки и добавляет её если нужно"""

        # Если уже есть HTML теги, возвращаем как есть
        if '<p>' in text or '<h2>' in text or '<ul>' in text:
            return text

        # Если нет - добавляем базовую разметку
        lines = text.split('\n\n')
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Если строка короткая и выглядит как заголовок
            if len(line) < 100 and line[0].isupper() and not line.endswith('.'):
                formatted_lines.append(f'<h2>{line}</h2>')
            # Если строка начинается с маркера списка
            elif line.startswith('- ') or line.startswith('• '):
                items = line.split('\n')
                list_html = '<ul>\n'
                for item in items:
                    clean_item = item.lstrip('- •').strip()
                    if clean_item:
                        list_html += f'  <li>{clean_item}</li>\n'
                list_html += '</ul>'
                formatted_lines.append(list_html)
            # Обычный параграф
            else:
                formatted_lines.append(f'<p>{line}</p>')

        return '\n'.join(formatted_lines)

    def _format_original_content(self, content: str) -> str:
        """Форматирует оригинальный контент с базовой HTML разметкой (fallback)"""

        # Если уже есть HTML, возвращаем как есть
        if '<p>' in content or '<h2>' in content:
            return content

        # Очищаем и форматируем
        clean_text = self._clean_html(content)
        return self._ensure_html_formatting(clean_text)


# Convenience функция
def rewrite_article(
    content: str,
    title: str,
    api_key: Optional[str] = None,
    folder_id: Optional[str] = None
) -> str:
    """
    Рерайтит статью через Яндекс GPT

    Args:
        content: Оригинальный контент
        title: Заголовок статьи
        api_key: API ключ (опционально, можно использовать переменную окружения)
        folder_id: Folder ID (опционально, можно использовать переменную окружения)

    Returns:
        Рерайченный текст с HTML разметкой
    """
    rewriter = YandexGPTRewriter(api_key=api_key, folder_id=folder_id)
    return rewriter.rewrite_article(content, title)
