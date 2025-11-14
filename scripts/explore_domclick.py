"""
Тестовый скрипт для изучения структуры DomClick

Цель: Понять структуру страниц и API для парсинга
"""

import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


def explore_domclick():
    """Исследование структуры DomClick"""

    # Тестовые URL (примеры для СПб)
    test_urls = [
        # Страница поиска
        "https://domclick.ru/search/buy/flat?region=70000000000",
        # Детальная страница (нужно будет взять реальный ID)
    ]

    with sync_playwright() as p:
        print("🚀 Запуск браузера...")
        browser = p.chromium.launch(headless=False)  # headless=False чтобы видеть
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        page = context.new_page()

        # Перехватываем API запросы
        api_requests = []

        def log_request(route, request):
            if '/api/' in request.url or 'search' in request.url:
                api_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'headers': dict(request.headers),
                    'post_data': request.post_data
                })
                print(f"📡 API: {request.method} {request.url}")
            route.continue_()

        page.route("**/*", log_request)

        # Загружаем страницу поиска
        print("\n" + "="*80)
        print("📄 Загрузка страницы поиска...")
        print("="*80)

        try:
            page.goto(test_urls[0], wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)  # Ждем полной загрузки

            # Сохраняем HTML
            html = page.content()
            with open('/tmp/domclick_search.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("✅ HTML сохранен в /tmp/domclick_search.html")

            # Ищем JSON данные в странице
            print("\n" + "="*80)
            print("🔍 Поиск JSON данных в странице...")
            print("="*80)

            # Паттерны для поиска JSON
            patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});',
                r'window\.__NEXT_DATA__\s*=\s*(\{.+?\})</script>',
                r'window\.DOMCLICK_DATA\s*=\s*(\{.+?\});',
                r'window\.__data\s*=\s*(\{.+?\});',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                if matches:
                    try:
                        data = json.loads(matches[0])
                        print(f"✅ Найдены данные по паттерну: {pattern[:50]}...")
                        print(f"   Ключи верхнего уровня: {list(data.keys())[:10]}")

                        # Сохраняем JSON
                        filename = f"/tmp/domclick_data_{len(api_requests)}.json"
                        with open(filename, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"   Сохранено в {filename}")
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Ошибка парсинга JSON: {e}")

            # Проверяем наличие объявлений на странице
            print("\n" + "="*80)
            print("🏠 Анализ объявлений на странице...")
            print("="*80)

            soup = BeautifulSoup(html, 'lxml')

            # Ищем карточки объявлений
            possible_selectors = [
                'div[class*="card"]',
                'div[class*="offer"]',
                'div[class*="item"]',
                'article',
                'a[href*="/card/"]',
            ]

            for selector in possible_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"✅ Найдено {len(elements)} элементов по селектору: {selector}")
                    if len(elements) > 0:
                        print(f"   Пример HTML:\n{str(elements[0])[:500]}...")

            # Пробуем кликнуть на первое объявление
            print("\n" + "="*80)
            print("🔍 Попытка открыть детальную страницу...")
            print("="*80)

            # Ждем появления карточек
            try:
                page.wait_for_selector('a[href*="/card/"]', timeout=5000)
                links = page.locator('a[href*="/card/"]').all()

                if links:
                    first_url = links[0].get_attribute('href')
                    if not first_url.startswith('http'):
                        first_url = 'https://domclick.ru' + first_url

                    print(f"📍 Открываем: {first_url}")

                    page.goto(first_url, wait_until='networkidle', timeout=30000)
                    page.wait_for_timeout(3000)

                    # Сохраняем детальную страницу
                    detail_html = page.content()
                    with open('/tmp/domclick_detail.html', 'w', encoding='utf-8') as f:
                        f.write(detail_html)
                    print("✅ HTML детальной страницы сохранен в /tmp/domclick_detail.html")

                    # Ищем JSON на детальной странице
                    for pattern in patterns:
                        matches = re.findall(pattern, detail_html, re.DOTALL)
                        if matches:
                            try:
                                data = json.loads(matches[0])
                                print(f"✅ JSON детальной страницы найден")
                                print(f"   Ключи: {list(data.keys())[:10]}")

                                with open('/tmp/domclick_detail_data.json', 'w', encoding='utf-8') as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                print(f"   Сохранено в /tmp/domclick_detail_data.json")

                                # Пытаемся найти данные объявления
                                if 'offer' in data:
                                    print("\n📋 Найдены данные объявления:")
                                    offer = data['offer']
                                    print(f"   Ключи offer: {list(offer.keys())}")

                            except json.JSONDecodeError as e:
                                print(f"⚠️ Ошибка парсинга JSON: {e}")

            except Exception as e:
                print(f"⚠️ Не удалось открыть детальную страницу: {e}")

            # Выводим все перехваченные API запросы
            print("\n" + "="*80)
            print(f"📡 Перехвачено {len(api_requests)} API запросов:")
            print("="*80)

            for req in api_requests:
                print(f"\n{req['method']} {req['url']}")
                if req['post_data']:
                    print(f"Body: {req['post_data'][:200]}")

            # Сохраняем API запросы
            with open('/tmp/domclick_api_requests.json', 'w', encoding='utf-8') as f:
                json.dump(api_requests, f, ensure_ascii=False, indent=2)
            print("\n✅ API запросы сохранены в /tmp/domclick_api_requests.json")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

        finally:
            print("\n" + "="*80)
            print("🏁 Завершение...")
            print("="*80)
            input("Нажмите Enter чтобы закрыть браузер...")
            browser.close()


if __name__ == '__main__':
    explore_domclick()
