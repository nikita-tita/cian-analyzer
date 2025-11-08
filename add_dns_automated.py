#!/usr/bin/env python3
"""
Автоматическое добавление DNS записей в Reg.ru через Selenium
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

# Конфигурация
REG_LOGIN = "nikitatitov070@yandex.ru"
REG_PASSWORD = "#1$tBILLionaire070!070"
DOMAIN = "housler.ru"
SERVER_IP = "91.229.8.221"

def setup_driver():
    """Настройка Chrome драйвера"""
    options = Options()
    # options.add_argument('--headless')  # Раскомментируйте для работы без GUI
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=options)
    return driver

def login_to_reg(driver):
    """Вход в аккаунт Reg.ru"""
    print("🔐 Вход в аккаунт Reg.ru...")

    driver.get("https://www.reg.ru/user/login")
    time.sleep(2)

    # Ввод email
    email_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, "username"))
    )
    email_input.send_keys(REG_LOGIN)

    # Ввод пароля
    password_input = driver.find_element(By.NAME, "password")
    password_input.send_keys(REG_PASSWORD)

    # Клик на кнопку входа
    login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    login_button.click()

    time.sleep(5)
    print("✅ Вход выполнен")

def navigate_to_dns_zone(driver):
    """Переход к управлению DNS зоной"""
    print(f"🌐 Открытие управления DNS для {DOMAIN}...")

    # Переход к списку доменов
    driver.get("https://www.reg.ru/user/domain_list")
    time.sleep(3)

    # Поиск домена и клик по управлению
    try:
        # Ищем ссылку на домен
        domain_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, DOMAIN))
        )
        domain_link.click()
        time.sleep(3)

        # Переход к DNS записям
        dns_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "DNS"))
        )
        dns_link.click()
        time.sleep(3)

        print("✅ Открыто управление DNS")
    except Exception as e:
        print(f"❌ Ошибка при переходе к DNS: {e}")
        # Пробуем прямую ссылку
        driver.get(f"https://www.reg.ru/user/domain/{DOMAIN}/dns")
        time.sleep(3)

def add_dns_record(driver, subdomain, ip):
    """Добавление DNS A-записи"""
    print(f"➕ Добавление записи: {subdomain} -> {ip}")

    try:
        # Клик на кнопку добавления записи
        add_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Добавить запись')]")
        add_button.click()
        time.sleep(2)

        # Выбор типа записи A
        record_type = driver.find_element(By.NAME, "type")
        record_type.send_keys("A")

        # Ввод поддомена
        subdomain_input = driver.find_element(By.NAME, "subdomain")
        subdomain_input.clear()
        if subdomain != "@":
            subdomain_input.send_keys(subdomain)

        # Ввод IP адреса
        ip_input = driver.find_element(By.NAME, "content")
        ip_input.clear()
        ip_input.send_keys(ip)

        # Сохранение
        save_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Сохранить')]")
        save_button.click()
        time.sleep(2)

        print(f"✅ Запись {subdomain} добавлена")

    except Exception as e:
        print(f"❌ Ошибка при добавлении записи {subdomain}: {e}")
        print("Попробуйте добавить вручную через интерфейс")

def main():
    """Основная функция"""
    driver = None

    try:
        print("=" * 60)
        print("🚀 Автоматическое добавление DNS записей для housler.ru")
        print("=" * 60)
        print()

        driver = setup_driver()

        # Вход
        login_to_reg(driver)

        # Переход к DNS
        navigate_to_dns_zone(driver)

        # Добавление записей
        add_dns_record(driver, "@", SERVER_IP)
        time.sleep(2)
        add_dns_record(driver, "www", SERVER_IP)

        print()
        print("=" * 60)
        print("✅ DNS записи добавлены!")
        print("=" * 60)
        print()
        print("⏱️  DNS записи начнут работать через 5-30 минут")
        print(f"🌐 Сайт будет доступен: http://{DOMAIN}")
        print()

        # Оставить браузер открытым для проверки
        input("Нажмите Enter чтобы закрыть браузер...")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
