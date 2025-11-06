#!/usr/bin/env python3
"""
Поиск адреса и метро на странице
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import re

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
print("ПОИСК АДРЕСА")
print("=" * 80)

# Ищем текст "Петроградский, Петровский, проезд Петровская коса, 6к1"
for elem in soup.find_all(string=lambda s: s and 'проезд Петровская коса' in s):
    parent = elem.parent
    print(f"\n✓ Найден в тексте: {elem.strip()}")
    print(f"  Parent tag: {parent.name}, class: {parent.get('class')}, data-name: {parent.get('data-name')}")

    # Смотрим выше на 3 уровня
    for i in range(3):
        parent = parent.parent if parent else None
        if parent:
            print(f"  Level {i+1}: tag={parent.name}, class={parent.get('class')}, data-name={parent.get('data-name')}")

print("\n" + "=" * 80)
print("ПОИСК МЕТРО")
print("=" * 80)

# Ищем станции метро по тексту
metro_stations = ["Крестовский остров", "Василеостровская", "Зенит"]
for station in metro_stations:
    for elem in soup.find_all(string=lambda s: s and station in s):
        parent = elem.parent
        print(f"\n✓ Найдена станция: {station}")
        print(f"  Текст: {elem.strip()}")
        print(f"  Parent tag: {parent.name}, class: {parent.get('class')}, data-name: {parent.get('data-name')}")

        # Смотрим выше
        for i in range(2):
            parent = parent.parent if parent else None
            if parent:
                print(f"  Level {i+1}: tag={parent.name}, class={parent.get('class')}, data-name={parent.get('data-name')}")
        break  # Только первое вхождение

print("\n" + "=" * 80)
print("АЛЬТЕРНАТИВНЫЙ ПОИСК - по href='/geo/'")
print("=" * 80)

# Ссылки на районы/улицы обычно имеют /geo/
geo_links = soup.find_all('a', href=lambda h: h and '/geo/' in h)
print(f"\n✓ Найдено ссылок с /geo/: {len(geo_links)}")
for i, link in enumerate(geo_links[:10], 1):
    print(f"{i}. {link.get_text(strip=True)} → {link.get('href')[:80]}")
