"""
Быстрый тест парсера Домклика (без зависимостей)
"""

import requests
import json
import re


def test_domclick_page():
    """Тестируем доступность и структуру страницы Домклика"""

    url = "https://domclick.ru/pokupka/kvartiry/vtorichka?from=topline2020"

    print("="*80)
    print("🧪 БЫСТРЫЙ ТЕСТ ДОМКЛИКА")
    print("="*80)
    print(f"\n📍 URL: {url}")

    # Настраиваем заголовки как в нашем парсере
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://domclick.ru/',
    }

    try:
        print("\n🔄 Запрос к странице...")
        response = requests.get(url, headers=headers, timeout=30)

        print(f"✓ Статус: {response.status_code}")
        print(f"✓ Размер ответа: {len(response.text)} байт")
        print(f"✓ Content-Type: {response.headers.get('Content-Type', 'N/A')}")

        if response.status_code == 200:
            html = response.text

            print(f"\n🔍 Анализ содержимого...")

            # Проверяем наличие JSON данных
            patterns = [
                (r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});', '__INITIAL_STATE__'),
                (r'<script id="__NEXT_DATA__"[^>]*>(\{.+?\})</script>', '__NEXT_DATA__'),
                (r'window\.__PRELOADED_STATE__\s*=\s*(\{.+?\});', '__PRELOADED_STATE__'),
            ]

            found_data = False
            for pattern, name in patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                if matches:
                    try:
                        data = json.loads(matches[0])
                        print(f"✓ Найден {name}!")
                        print(f"  Ключи верхнего уровня: {list(data.keys())[:10]}")

                        # Сохраняем для анализа
                        filename = f'/tmp/{name.lower()}.json'
                        with open(filename, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"  💾 Сохранено в {filename}")

                        found_data = True

                        # Пытаемся найти офферы внутри
                        print(f"\n  🔎 Поиск данных офферов...")
                        def find_offers(obj, path=""):
                            """Рекурсивно ищем офферы"""
                            if isinstance(obj, dict):
                                # Проверяем ключи, которые могут содержать офферы
                                for key in ['offers', 'items', 'results', 'cards', 'data']:
                                    if key in obj:
                                        value = obj[key]
                                        if isinstance(value, list) and len(value) > 0:
                                            print(f"    ✓ Найдено {len(value)} элементов в {path}.{key}")
                                            # Показываем первый элемент
                                            if value and isinstance(value[0], dict):
                                                print(f"      Ключи первого элемента: {list(value[0].keys())[:10]}")
                                                return value
                                        elif isinstance(value, dict):
                                            result = find_offers(value, f"{path}.{key}")
                                            if result:
                                                return result
                                for key, value in obj.items():
                                    if isinstance(value, (dict, list)) and key not in ['offers', 'items', 'results', 'cards', 'data']:
                                        result = find_offers(value, f"{path}.{key}" if path else key)
                                        if result:
                                            return result
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj):
                                    result = find_offers(item, f"{path}[{i}]")
                                    if result:
                                        return result
                            return None

                        offers = find_offers(data)
                        if offers:
                            print(f"\n  📋 Найдено офферов: {len(offers)}")

                    except json.JSONDecodeError as e:
                        print(f"  ⚠️ Ошибка парсинга JSON: {e}")

            if not found_data:
                print("⚠️ JSON данные не найдены в стандартных местах")

            # Ищем ссылки на карточки
            print(f"\n🔗 Поиск ссылок на объявления...")
            card_patterns = [
                r'href="(/card/[^"]+)"',
                r'href="(https://domclick\.ru/card/[^"]+)"',
            ]

            all_links = set()
            for pattern in card_patterns:
                links = re.findall(pattern, html)
                all_links.update(links)

            if all_links:
                print(f"✓ Найдено {len(all_links)} ссылок на объявления")
                print(f"  Примеры:")
                for link in list(all_links)[:5]:
                    if not link.startswith('http'):
                        link = f"https://domclick.ru{link}"
                    print(f"    - {link}")

                # Пробуем загрузить первое объявление
                first_link = list(all_links)[0]
                if not first_link.startswith('http'):
                    first_link = f"https://domclick.ru{first_link}"

                print(f"\n🎯 Тестируем детальную страницу: {first_link}")
                test_detail_page(first_link, headers)
            else:
                print("⚠️ Ссылки на объявления не найдены")

            # Проверяем API endpoints
            print(f"\n🔍 Проверка возможных API endpoints...")
            test_api_endpoints(headers)

        elif response.status_code == 403:
            print("❌ Доступ запрещен (403)")
            print("  Возможные причины:")
            print("    - Блокировка по IP")
            print("    - Требуется более сложный User-Agent или cookies")
            print("    - Нужен браузер (Playwright)")
        else:
            print(f"❌ Неожиданный статус: {response.status_code}")

    except requests.exceptions.Timeout:
        print("❌ Таймаут запроса")
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка соединения")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def test_detail_page(url, headers):
    """Тест детальной страницы"""
    try:
        print(f"  🔄 Загрузка...")
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            print(f"  ✓ Статус: {response.status_code}")

            # Пытаемся найти JSON данные объявления
            patterns = [
                (r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});', '__INITIAL_STATE__'),
                (r'<script id="__NEXT_DATA__"[^>]*>(\{.+?\})</script>', '__NEXT_DATA__'),
            ]

            for pattern, name in patterns:
                matches = re.findall(pattern, response.text, re.DOTALL)
                if matches:
                    try:
                        data = json.loads(matches[0])
                        print(f"  ✓ Найден {name} с данными объявления")

                        # Ищем данные оффера
                        def extract_offer_info(obj, depth=0, max_depth=5):
                            if depth > max_depth:
                                return None

                            if isinstance(obj, dict):
                                # Ищем признаки оффера
                                has_price = 'price' in obj or 'priceValue' in obj
                                has_area = 'area' in obj or 'totalArea' in obj
                                has_title = 'title' in obj or 'name' in obj

                                if has_price and (has_area or has_title):
                                    return obj

                                # Рекурсивно проверяем вложенные объекты
                                for key in ['offer', 'card', 'property', 'data']:
                                    if key in obj:
                                        result = extract_offer_info(obj[key], depth + 1, max_depth)
                                        if result:
                                            return result

                                # Проверяем все ключи
                                for value in obj.values():
                                    if isinstance(value, dict):
                                        result = extract_offer_info(value, depth + 1, max_depth)
                                        if result:
                                            return result

                            return None

                        offer = extract_offer_info(data)
                        if offer:
                            print(f"\n  📋 Данные объявления:")
                            print(f"    Заголовок: {offer.get('title') or offer.get('name', 'N/A')}")
                            print(f"    Цена: {offer.get('price') or offer.get('priceValue', 'N/A')}")
                            print(f"    Площадь: {offer.get('totalArea') or offer.get('area', 'N/A')}")
                            print(f"    Комнат: {offer.get('roomsCount') or offer.get('rooms', 'N/A')}")

                            # Сохраняем
                            with open('/tmp/domclick_offer.json', 'w', encoding='utf-8') as f:
                                json.dump(offer, f, ensure_ascii=False, indent=2)
                            print(f"    💾 Полные данные в /tmp/domclick_offer.json")
                            return

                    except json.JSONDecodeError:
                        pass

            print(f"  ⚠️ Не удалось извлечь структурированные данные")
        else:
            print(f"  ❌ Статус: {response.status_code}")

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")


def test_api_endpoints(headers):
    """Проверяем возможные API endpoints"""

    endpoints = [
        "https://domclick.ru/api/search/v1/offers?region=78000000000&limit=5",
        "https://domclick.ru/api/v1/search/offers?region=78000000000&limit=5",
        "https://domclick.ru/api/offers/search?region=78000000000&limit=5",
    ]

    for endpoint in endpoints:
        try:
            print(f"  Пробуем: {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=10)
            print(f"    Статус: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"    ✓ Получен JSON!")
                    print(f"    Ключи: {list(data.keys())[:10]}")

                    # Сохраняем
                    filename = f"/tmp/domclick_api_{endpoint.split('/')[-1].split('?')[0]}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"    💾 Сохранено в {filename}")
                    return  # Нашли рабочий endpoint
                except:
                    print(f"    ⚠️ Ответ не является JSON")

        except Exception as e:
            print(f"    ❌ {e}")

    print(f"  ⚠️ Рабочие API endpoints не найдены")


if __name__ == '__main__':
    test_domclick_page()

    print("\n" + "="*80)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("="*80)
    print("\nРезультаты:")
    print("- Проверили доступность страницы")
    print("- Проанализировали структуру данных")
    print("- Протестировали API endpoints")
    print("\nJSON файлы сохранены в /tmp/ для анализа")
    print()
