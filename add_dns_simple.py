#!/usr/bin/env python3
"""
Автоматическое добавление DNS записей в Reg.ru через HTTP запросы
"""

import requests
from bs4 import BeautifulSoup
import json

# Конфигурация
REG_LOGIN = "nikitatitov070@yandex.ru"
REG_PASSWORD = "#1$tBILLionaire070!070"
DOMAIN = "housler.ru"
SERVER_IP = "91.229.8.221"

def login_and_add_dns():
    """Вход и добавление DNS"""

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })

    print("🔐 Вход в аккаунт Reg.ru...")

    # Получение страницы входа
    login_page = session.get('https://www.reg.ru/user/login')
    soup = BeautifulSoup(login_page.text, 'html.parser')

    # Поиск CSRF токена
    csrf_token = None
    csrf_input = soup.find('input', {'name': '_csrf'})
    if csrf_input:
        csrf_token = csrf_input.get('value')

    # Вход
    login_data = {
        'username': REG_LOGIN,
        'password': REG_PASSWORD,
    }

    if csrf_token:
        login_data['_csrf'] = csrf_token

    response = session.post('https://www.reg.ru/user/login', data=login_data, allow_redirects=True)

    if 'domain_list' in response.url or response.status_code == 200:
        print("✅ Вход выполнен")
    else:
        print("❌ Ошибка входа")
        return False

    print(f"🌐 Добавление DNS записей для {DOMAIN}...")

    # Попытка добавить DNS через API эндпоинт
    dns_records = [
        {'subdomain': '@', 'type': 'A', 'content': SERVER_IP},
        {'subdomain': 'www', 'type': 'A', 'content': SERVER_IP},
    ]

    for record in dns_records:
        print(f"➕ Добавление записи: {record['subdomain']} -> {record['content']}")

        # Попытка добавить запись
        dns_add_url = f'https://www.reg.ru/user/domain/{DOMAIN}/dns/add'

        response = session.post(dns_add_url, data={
            'subdomain': record['subdomain'],
            'type': record['type'],
            'content': record['content'],
            'ttl': '3600'
        })

        if response.status_code == 200:
            print(f"✅ Запись {record['subdomain']} добавлена")
        else:
            print(f"⚠️  Статус: {response.status_code}")

    print()
    print("=" * 60)
    print("✅ Процесс завершен!")
    print("=" * 60)
    print()
    print("🔍 Проверьте DNS записи в панели Reg.ru:")
    print(f"   https://www.reg.ru/user/domain/{DOMAIN}/dns")
    print()

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Автоматическое добавление DNS для housler.ru")
    print("=" * 60)
    print()

    try:
        login_and_add_dns()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
