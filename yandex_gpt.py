"""
Yandex GPT Integration for Article Rewriting
"""

import requests
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class YandexGPT:
    def __init__(self):
        self.api_key = os.getenv('YANDEX_API_KEY')
        self.folder_id = os.getenv('YANDEX_FOLDER_ID')
        self.api_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        if not self.api_key or not self.folder_id:
            raise ValueError("YANDEX_API_KEY and YANDEX_FOLDER_ID must be set")

    def rewrite_article(
        self,
        original_title: str,
        original_content: str,
        original_excerpt: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Rewrite article using Yandex GPT
        Returns dict with keys: title, content, excerpt
        """

        prompt = f"""Ты - профессиональный копирайтер агентства недвижимости HOUSLER в Санкт-Петербурге.

Твоя задача: ПОЛНОСТЬЮ ПЕРЕПИСАТЬ статью своими словами с оригинальностью не менее 90%.

ОРИГИНАЛЬНАЯ СТАТЬЯ:
Заголовок: {original_title}

Текст:
{original_content}

СТРОГИЕ ТРЕБОВАНИЯ:

1. ОРИГИНАЛЬНОСТЬ 90%+:
   - Полностью измени все формулировки
   - Перестрой структуру и порядок мыслей
   - Используй синонимы и другие речевые обороты
   - НЕ копируй предложения из оригинала

2. ЗАПРЕЩЕНО упоминать:
   - CIAN, Циан, cian.ru
   - RBC, РБК, rbc.ru
   - Любые другие источники, сайты, издания
   - Слова: "по данным", "согласно исследованию", "как сообщает"

3. СТРУКТУРА статьи:
   - Заголовок: яркий, цепляющий, с пользой для читателя
   - Excerpt: 1-2 предложения, интрига + польза
   - Контент:
     * Вводный абзац (зацепить проблемой/вопросом)
     * Основная часть (конкретные советы, факты, примеры)
     * Промежуточные выводы между разделами
     * Заключительный абзац

4. СТИЛЬ письма:
   - Профессионально, но простым языком
   - Без воды и канцелярита
   - Конкретные цифры и примеры из Санкт-Петербурга
   - Обращайся к читателю на "вы"
   - Короткие абзацы (3-5 предложений)

5. ОБЯЗАТЕЛЬНО в конце статьи добавь:

---

**Нужна помощь с недвижимостью в Санкт-Петербурге?**

Агентство HOUSLER поможет купить, продать или арендовать квартиру. Оставьте заявку — наш эксперт свяжется с вами в течение часа.

👉 [Оставить заявку на консультацию](https://housler.ru/calculator)

ФОРМАТ ОТВЕТА (строго соблюдай):

TITLE: [новый заголовок без упоминания источников]

EXCERPT: [краткое описание в 1-2 предложениях]

CONTENT:
[Полный переписанный текст статьи]

[В конце обязательно блок с CTA]"""

        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Api-Key {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "modelUri": f"gpt://{self.folder_id}/yandexgpt",
                    "completionOptions": {
                        "stream": False,
                        "temperature": 0.8,
                        "maxTokens": 4000
                    },
                    "messages": [
                        {
                            "role": "user",
                            "text": prompt
                        }
                    ]
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            # Извлекаем текст ответа
            result_text = data['result']['alternatives'][0]['message']['text']

            # Парсим ответ
            return self._parse_gpt_response(result_text, original_title, original_excerpt)

        except Exception as e:
            logger.error(f"Failed to rewrite article: {e}")
            # Возвращаем оригинал в случае ошибки
            return {
                'title': original_title,
                'excerpt': original_excerpt or original_content[:200] + '...',
                'content': original_content
            }

    def _parse_gpt_response(
        self,
        response_text: str,
        fallback_title: str,
        fallback_excerpt: Optional[str]
    ) -> Dict[str, str]:
        """Parse GPT response into title, excerpt, content"""

        title = fallback_title
        excerpt = fallback_excerpt or ""
        content = response_text

        try:
            lines = response_text.strip().split('\n')
            current_section = None
            content_lines = []

            for line in lines:
                line = line.strip()

                if line.startswith('TITLE:'):
                    title = line.replace('TITLE:', '').strip()
                    current_section = 'title'
                elif line.startswith('EXCERPT:'):
                    excerpt = line.replace('EXCERPT:', '').strip()
                    current_section = 'excerpt'
                elif line.startswith('CONTENT:'):
                    current_section = 'content'
                    continue
                elif current_section == 'content' and line:
                    content_lines.append(line)
                elif current_section == 'excerpt' and line and not line.startswith('CONTENT:'):
                    excerpt += ' ' + line

            if content_lines:
                content = '\n\n'.join(content_lines)

        except Exception as e:
            logger.warning(f"Failed to parse GPT response: {e}")

        return {
            'title': title,
            'excerpt': excerpt[:300] if len(excerpt) > 300 else excerpt,
            'content': content
        }
