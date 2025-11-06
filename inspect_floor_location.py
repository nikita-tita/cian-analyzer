#!/usr/bin/env python3
"""
Детальная инспекция где находится информация об этаже
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

url = "https://www.cian.ru/sale/flat/319271562/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(2)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'lxml')

# Находим элемент с "6 из 7"
elem = soup.find(string=lambda s: s and '6 из 7' == s.strip())
if elem:
    print("Нашли '6 из 7'!")
    print(f"Текст: '{elem.strip()}'")
    print()

    # Поднимаемся по дереву и смотрим структуру
    current = elem.parent
    level = 0
    while current and level < 10:
        print(f"Level {level}: {current.name}")
        print(f"  class: {current.get('class')}")
        print(f"  data-name: {current.get('data-name')}")
        print(f"  text: {current.get_text(strip=True)[:100]}")

        # Ищем соседние элементы (siblings)
        if level == 2:  # Обычно на уровне 2-3 находится контейнер
            print(f"\n  Siblings:")
            for sib in current.find_previous_siblings():
                if sib.name:
                    print(f"    prev: {sib.name}, class={sib.get('class')}, text={sib.get_text(strip=True)[:50]}")
                    break
            for sib in current.find_next_siblings():
                if sib.name:
                    print(f"    next: {sib.name}, class={sib.get('class')}, text={sib.get_text(strip=True)[:50]}")
                    break

        print()
        current = current.parent
        level += 1

# Также ищем элемент с "Этаж"
print("=" * 80)
elem_label = soup.find(string=lambda s: s and s.strip() == 'Этаж')
if elem_label:
    print("Нашли 'Этаж' (метку)!")
    print(f"Текст: '{elem_label.strip()}'")
    print()

    # Смотрим на родителя и его siblings
    parent = elem_label.parent
    print(f"Parent: {parent.name}, class={parent.get('class')}")

    # Ищем соседний элемент где должно быть значение "6 из 7"
    grandparent = parent.parent
    if grandparent:
        print(f"\nGrandparent: {grandparent.name}, class={grandparent.get('class')}, data-name={grandparent.get('data-name')}")
        print(f"Весь текст: {grandparent.get_text(strip=True)}")
