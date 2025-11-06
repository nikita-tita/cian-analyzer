#!/usr/bin/env python3
"""
Поиск информации об этаже на странице
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import json

url = "https://www.cian.ru/sale/flat/319271562/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(2)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'lxml')

print("=" * 80)
print("ПОИСК ЭТАЖА")
print("=" * 80)

# 1. JSON-LD
print("\n1. JSON-LD данные:")
json_ld_scripts = soup.find_all('script', type='application/ld+json')
for script in json_ld_scripts:
    try:
        data = json.loads(script.string)
        if 'floorLevel' in str(data):
            print(f"✓ Найдено floorLevel: {data}")
    except:
        pass

# 2. Ищем в тексте "6 из 7"
print("\n2. Поиск '6 из 7' или 'этаж' в тексте:")
for elem in soup.find_all(string=lambda s: s and ('6 из 7' in s or (('этаж' in s.lower() or 'floor' in s.lower()) and len(s) < 100))):
    parent = elem.parent
    text = elem.strip()
    if text:
        print(f"✓ Найдено: '{text}'")
        print(f"  Tag: {parent.name}, class: {parent.get('class')}, data-name: {parent.get('data-name')}")
        # Поднимаемся выше
        p2 = parent.parent if parent else None
        if p2:
            print(f"  Parent: tag={p2.name}, class={p2.get('class')}, data-name={p2.get('data-name')}")

# 3. OfferSummaryInfoItem (основной селектор для характеристик)
print("\n3. Проверяем OfferSummaryInfoItem:")
summary_items = soup.find_all('div', {'data-name': 'OfferSummaryInfoItem'})
print(f"Найдено OfferSummaryInfoItem: {len(summary_items)}")
for item in summary_items:
    text = item.get_text(strip=True)
    if 'этаж' in text.lower() or '6 из 7' in text:
        print(f"✓ Нашли этаж: {text}")
        print(f"  HTML: {str(item)[:200]}")

# 4. Title/заголовок
print("\n4. Title страницы:")
title = soup.find('title')
if title:
    print(f"  {title.get_text(strip=True)}")

# 5. Специальные селекторы для этажа
print("\n5. Специальные data-name атрибуты:")
floor_indicators = ['Floor', 'Этаж', 'Level']
for elem in soup.find_all(attrs={'data-name': True}):
    data_name = elem.get('data-name', '')
    if any(indicator.lower() in data_name.lower() for indicator in floor_indicators):
        print(f"✓ data-name='{data_name}': {elem.get_text(strip=True)[:100]}")
