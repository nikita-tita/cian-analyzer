#!/usr/bin/env python3
"""
Анализ HTML структуры для понимания где находятся данные
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

url = "https://www.cian.ru/sale/flat/319271562/"

print(f"Анализ HTML структуры: {url}\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(2)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'lxml')

print("=" * 80)
print("1. АДРЕС И ГЕО")
print("=" * 80)

# GeoLabel - адрес
geo_labels = soup.find_all('a', {'data-name': 'GeoLabel'})
print(f"\nGeoLabel элементов: {len(geo_labels)}")
for i, label in enumerate(geo_labels[:5], 1):
    print(f"  {i}. {label.get_text(strip=True)}")

# Метро
metro_labels = soup.find_all('a', {'data-name': 'UndergroundLabel'})
print(f"\nUndergroundLabel элементов: {len(metro_labels)}")
for i, label in enumerate(metro_labels[:5], 1):
    print(f"  {i}. {label.get_text(strip=True)}")

print("\n" + "=" * 80)
print("2. ХАРАКТЕРИСТИКИ")
print("=" * 80)

# Характеристики - пробуем разные селекторы
selectors_to_try = [
    ('data-name', 'OfferFactItem'),
    ('data-name', 'OfferSummaryInfoItem'),
    ('class', 'a10a3f92e9--item'),
    ('data-testid', 'object-summary-description-info'),
]

for attr, value in selectors_to_try:
    if attr == 'class':
        items = soup.find_all('div', class_=lambda x: x and value in str(x))
    else:
        items = soup.find_all('div', {attr: value})

    if items:
        print(f"\n✅ Найдено {len(items)} элементов с {attr}='{value}':")
        for i, item in enumerate(items[:3], 1):
            print(f"  {i}. {item.get_text(strip=True)[:100]}")

# Ищем все элементы с data-name
print("\n" + "=" * 80)
print("3. ВСЕ data-name АТРИБУТЫ")
print("=" * 80)

data_names = set()
for elem in soup.find_all(attrs={'data-name': True}):
    data_names.add(elem.get('data-name'))

print(f"\nВсего уникальных data-name: {len(data_names)}")
print("\nСвязанные с характеристиками:")
for name in sorted(data_names):
    if any(keyword in name.lower() for keyword in ['offer', 'fact', 'info', 'summary', 'object', 'item']):
        print(f"  - {name}")

print("\n" + "=" * 80)
print("4. ТЕСТИРУЕМ КОНКРЕТНЫЕ ПОЛЯ")
print("=" * 80)

# Площадь
print("\nПлощадь (площад, м², square, area):")
for elem in soup.find_all(string=lambda s: s and any(w in s.lower() for w in ['площад', 'м²', 'м2'])):
    parent = elem.parent
    if parent and len(elem.strip()) < 100:
        print(f"  - {elem.strip()[:80]} (tag: {parent.name}, class: {parent.get('class')})")

# Этаж
print("\nЭтаж (этаж, floor):")
for elem in soup.find_all(string=lambda s: s and 'этаж' in s.lower() and len(s) < 50):
    parent = elem.parent
    print(f"  - {elem.strip()[:80]} (tag: {parent.name})")

print("\n" + "=" * 80)
print("АНАЛИЗ ЗАВЕРШЕН")
print("=" * 80)
