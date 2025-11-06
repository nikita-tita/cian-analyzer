#!/usr/bin/env python3
"""
Анализ структуры страниц Cian для поиска всех возможных источников данных
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import re
import time

def analyze_detail_page(url: str):
    """
    Глубокий анализ страницы объявления
    """
    print("=" * 80)
    print(f"АНАЛИЗ СТРАНИЦЫ: {url}")
    print("=" * 80)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Перехватываем все network запросы
        api_requests = []

        def handle_request(request):
            if 'api' in request.url or 'ajax' in request.url:
                api_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'headers': dict(request.headers)
                })

        page.on("request", handle_request)

        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)

        html = page.content()
        browser.close()

    print(f"\n📄 Размер HTML: {len(html)} символов")

    soup = BeautifulSoup(html, 'lxml')

    # 1. JSON-LD данные
    print("\n" + "=" * 80)
    print("1. JSON-LD ДАННЫЕ")
    print("=" * 80)

    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for i, script in enumerate(json_ld_scripts, 1):
        try:
            data = json.loads(script.string)
            print(f"\nJSON-LD блок {i}:")
            print(f"  @type: {data.get('@type')}")
            if data.get('@type') == 'Apartment':
                print(f"  name: {data.get('name', 'N/A')[:100]}")
                print(f"  address: {data.get('address', 'N/A')}")
                if 'geo' in data:
                    print(f"  coordinates: {data['geo']}")
                if 'offers' in data:
                    print(f"  price: {data['offers'].get('price')}")
        except:
            pass

    # 2. NextData (данные для React)
    print("\n" + "=" * 80)
    print("2. NEXT DATA (React State)")
    print("=" * 80)

    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data:
        try:
            data = json.loads(next_data.string)
            print("\n✅ Найден __NEXT_DATA__")

            # Ищем данные об объявлении
            props = data.get('props', {})
            initial_state = props.get('initialState', {})

            # Выводим структуру
            print(f"\nСтруктура данных:")
            for key in initial_state.keys():
                print(f"  - {key}")

            # Ищем offerData или похожее
            if 'offerData' in initial_state:
                offer = initial_state['offerData']
                print(f"\n📍 offerData найден!")
                print(f"  ID: {offer.get('id', 'N/A')}")
                print(f"  Тип: {offer.get('offerType', 'N/A')}")

                # Геоданные
                if 'geo' in offer:
                    geo = offer['geo']
                    print(f"\n🌍 Геоданные:")
                    print(f"  coordinates: {geo.get('coordinates', 'N/A')}")
                    print(f"  address: {geo.get('address', 'N/A')}")
                    if 'underground' in geo:
                        print(f"  метро: {geo.get('underground', [])[:2]}")

                # Здание
                if 'building' in offer:
                    building = offer['building']
                    print(f"\n🏢 Здание:")
                    print(f"  ID: {building.get('id', 'N/A')}")
                    print(f"  floorsCount: {building.get('floorsCount', 'N/A')}")
                    print(f"  buildYear: {building.get('buildYear', 'N/A')}")
                    print(f"  materialType: {building.get('materialType', 'N/A')}")

                # ЖК
                if 'newbuilding' in offer:
                    nb = offer['newbuilding']
                    print(f"\n🏗️ ЖК (Newbuilding):")
                    print(f"  ID: {nb.get('id', 'N/A')}")
                    print(f"  name: {nb.get('name', 'N/A')}")
                    print(f"  fullName: {nb.get('fullName', 'N/A')}")

                # Сохраняем полные данные
                with open('offer_data_full.json', 'w', encoding='utf-8') as f:
                    json.dump(offer, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Полные данные сохранены в offer_data_full.json")

        except Exception as e:
            print(f"❌ Ошибка парсинга __NEXT_DATA__: {e}")
    else:
        print("⚠️ __NEXT_DATA__ не найден")

    # 3. Мета-теги
    print("\n" + "=" * 80)
    print("3. МЕТА-ТЕГИ")
    print("=" * 80)

    meta_tags = {
        'og:title': soup.find('meta', property='og:title'),
        'og:url': soup.find('meta', property='og:url'),
        'og:description': soup.find('meta', property='og:description'),
        'cian:offer_id': soup.find('meta', {'name': 'cian:offer_id'}),
    }

    for name, tag in meta_tags.items():
        if tag and tag.get('content'):
            content = tag['content']
            print(f"  {name}: {content[:100]}")

    # 4. Data атрибуты
    print("\n" + "=" * 80)
    print("4. DATA АТРИБУТЫ")
    print("=" * 80)

    # Ищем элементы с data-* атрибутами
    data_attrs = set()
    for elem in soup.find_all(attrs={'data-name': True}):
        data_attrs.add(elem.get('data-name'))

    print(f"\nНайдено {len(data_attrs)} уникальных data-name:")
    for attr in sorted(data_attrs)[:20]:
        print(f"  - {attr}")

    # 5. API запросы
    print("\n" + "=" * 80)
    print("5. API ЗАПРОСЫ")
    print("=" * 80)

    if api_requests:
        print(f"\nПерехвачено {len(api_requests)} API запросов:")
        for req in api_requests[:10]:
            print(f"\n  {req['method']} {req['url'][:100]}")
    else:
        print("⚠️ API запросы не обнаружены")

    # 6. Breadcrumbs
    print("\n" + "=" * 80)
    print("6. BREADCRUMBS (хлебные крошки)")
    print("=" * 80)

    breadcrumbs = soup.find('div', {'data-name': 'Breadcrumbs'})
    if breadcrumbs:
        links = breadcrumbs.find_all('a')
        print(f"\nНайдено {len(links)} элементов:")
        for link in links:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            print(f"  - {text} → {href[:80]}")
    else:
        print("⚠️ Breadcrumbs не найдены")

    print("\n" + "=" * 80)
    print("АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 80)


def test_search_by_address():
    """
    Тестируем разные способы поиска по адресу
    """
    print("\n\n")
    print("=" * 80)
    print("ТЕСТ: Поиск по адресу")
    print("=" * 80)

    test_addresses = [
        "Санкт-Петербург, Светлановский проспект, 60",
        "Санкт-Петербург, Невский проспект",
        "улица Архивная, 3",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for address in test_addresses[:1]:  # Только первый для примера
            print(f"\n\n🔍 Поиск: {address}")
            print("-" * 80)

            # Вариант 1: Текстовый поиск
            import urllib.parse
            encoded = urllib.parse.quote(address)
            url = f"https://www.cian.ru/cat.php?deal_type=sale&offer_type=flat&engine_version=2&region=2&text={encoded}"

            print(f"\nURL: {url[:120]}...")

            page = browser.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)

            html = page.content()
            soup = BeautifulSoup(html, 'lxml')

            # Считаем результаты
            cards = soup.find_all('article', {'data-name': 'CardComponent'})
            print(f"✅ Найдено объявлений: {len(cards)}")

            if cards:
                print(f"\nПервые 3 результата:")
                for i, card in enumerate(cards[:3], 1):
                    title_elem = card.find('span', {'data-mark': 'OfferTitle'})
                    title = title_elem.get_text(strip=True) if title_elem else "N/A"

                    geo_labels = card.find_all('a', {'data-name': 'GeoLabel'})
                    addr = ', '.join([g.get_text(strip=True) for g in geo_labels]) if geo_labels else "N/A"

                    print(f"\n  {i}. {title[:60]}")
                    print(f"     Адрес: {addr[:100]}")

            page.close()

        browser.close()


if __name__ == '__main__':
    # Используйте реальный URL объявления для анализа
    test_url = "https://spb.cian.ru/sale/flat/309818461/"  # Замените на актуальный

    print("\n🚀 НАЧАЛО АНАЛИЗА СТРУКТУРЫ CIAN\n")

    # 1. Анализ страницы объявления
    analyze_detail_page(test_url)

    # 2. Тест поиска
    test_search_by_address()

    print("\n\n✅ АНАЛИЗ ЗАВЕРШЕН")
    print("\nПроверьте файл offer_data_full.json для детальных данных")
