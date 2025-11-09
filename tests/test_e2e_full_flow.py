"""
E2E тесты полного пользовательского пути
Проверяет критические сценарии от лендинга до отчета
"""
import pytest
import requests
import time
from typing import Dict


BASE_URL = "https://housler.ru"
TEST_PROPERTY_URL = "https://www.cian.ru/sale/flat/322762697/"


class TestE2EFullFlow:
    """Полный E2E тест пользовательского пути"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Проверка доступности сервиса"""
        response = requests.get(BASE_URL, timeout=10)
        assert response.status_code == 200, "Сервис недоступен"

    def test_01_landing_page_loads(self):
        """Тест 1: Лендинг загружается"""
        response = requests.get(BASE_URL, timeout=10)

        assert response.status_code == 200
        assert "Housler" in response.text or "housler" in response.text.lower()
        print("✅ Лендинг загрузился успешно")

    def test_02_calculator_page_loads(self):
        """Тест 2: Страница калькулятора загружается"""
        response = requests.get(f"{BASE_URL}/calculator", timeout=10)

        assert response.status_code == 200
        assert "калькулятор" in response.text.lower() or "calculator" in response.text.lower()
        print("✅ Страница калькулятора загрузилась")

    def test_03_parse_property_url(self):
        """Тест 3: Парсинг объекта недвижимости"""
        response = requests.post(
            f"{BASE_URL}/api/parse",
            json={"url": TEST_PROPERTY_URL},
            timeout=60
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success", f"Ошибка парсинга: {data.get('message')}"
        assert "session_id" in data
        assert "data" in data

        # Проверяем что основные поля заполнены
        property_data = data["data"]
        assert property_data.get("price"), "Цена не заполнена"
        assert property_data.get("total_area"), "Площадь не заполнена"
        assert property_data.get("address"), "Адрес не заполнен"

        print(f"✅ Объект спарсен: {property_data.get('address')}")
        print(f"   Цена: {property_data.get('price'):,} ₽")
        print(f"   Площадь: {property_data.get('total_area')} м²")

        return data["session_id"]

    def test_04_find_similar_properties(self):
        """Тест 4: Поиск аналогов"""
        # Сначала парсим объект
        parse_response = requests.post(
            f"{BASE_URL}/api/parse",
            json={"url": TEST_PROPERTY_URL},
            timeout=60
        )
        session_id = parse_response.json()["session_id"]

        # Ищем аналоги
        response = requests.post(
            f"{BASE_URL}/api/find-similar",
            json={"session_id": session_id, "limit": 50},
            timeout=120  # Параллельный парсинг занимает время
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success", f"Ошибка поиска: {data.get('message')}"
        assert "comparables" in data
        assert data["count"] > 0, "Не найдено ни одного аналога"

        # Проверяем что у аналогов есть данные
        comparables = data["comparables"]
        assert len(comparables) >= 3, f"Слишком мало аналогов: {len(comparables)}"

        # Проверяем первый аналог
        first_comparable = comparables[0]
        assert first_comparable.get("url"), "У аналога нет URL"

        print(f"✅ Найдено {len(comparables)} аналогов")

        return session_id

    def test_05_run_analysis(self):
        """Тест 5: Запуск анализа"""
        # Парсим объект и находим аналоги
        parse_response = requests.post(
            f"{BASE_URL}/api/parse",
            json={"url": TEST_PROPERTY_URL},
            timeout=60
        )
        session_id = parse_response.json()["session_id"]

        # Находим аналоги
        requests.post(
            f"{BASE_URL}/api/find-similar",
            json={"session_id": session_id, "limit": 50},
            timeout=120
        )

        # Запускаем анализ
        response = requests.post(
            f"{BASE_URL}/api/analyze",
            json={"session_id": session_id},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success", f"Ошибка анализа: {data.get('message')}"
        assert "result" in data

        result = data["result"]

        # Проверяем критические поля отчета
        assert "fair_price_analysis" in result, "Нет анализа справедливой цены"
        assert "market_statistics" in result, "Нет рыночной статистики"
        assert "comparables" in result, "Нет аналогов в результате"

        # Проверяем что аналогов достаточно
        comparables_count = len(result["comparables"])
        assert comparables_count >= 3, f"Слишком мало аналогов в анализе: {comparables_count}"

        # Проверяем справедливую цену
        fair_price = result["fair_price_analysis"]
        assert fair_price.get("fair_price_total"), "Справедливая цена не рассчитана"
        assert fair_price["fair_price_total"] > 0, "Справедливая цена = 0"

        # Проверяем рыночную статистику
        market_stats = result["market_statistics"]["all"]
        assert market_stats.get("median"), "Медиана не рассчитана"
        assert market_stats["median"] > 0, "Медиана = 0"
        assert market_stats.get("count") > 0, "Нет аналогов в статистике"

        print(f"✅ Анализ выполнен успешно")
        print(f"   Аналогов в анализе: {comparables_count}")
        print(f"   Справедливая цена: {fair_price['fair_price_total']:,} ₽")
        print(f"   Медиана рынка: {market_stats['median']:,.0f} ₽/м²")

    def test_06_adjustments_work(self):
        """Тест 6: Корректировки применяются"""
        # Парсим объект и находим аналоги
        parse_response = requests.post(
            f"{BASE_URL}/api/parse",
            json={"url": TEST_PROPERTY_URL},
            timeout=60
        )
        session_id = parse_response.json()["session_id"]

        requests.post(
            f"{BASE_URL}/api/find-similar",
            json={"session_id": session_id, "limit": 50},
            timeout=120
        )

        # Первый анализ с базовыми параметрами
        response1 = requests.post(
            f"{BASE_URL}/api/analyze",
            json={"session_id": session_id},
            timeout=30
        )
        fair_price_1 = response1.json()["result"]["fair_price_analysis"]["fair_price_total"]

        # Обновляем параметры целевого объекта (улучшаем отделку)
        requests.post(
            f"{BASE_URL}/api/update-target",
            json={
                "session_id": session_id,
                "data": {
                    "repair_level": "премиум",
                    "window_type": "панорамные",
                    "view_type": "парк"
                }
            },
            timeout=10
        )

        # Второй анализ с улучшенными параметрами
        response2 = requests.post(
            f"{BASE_URL}/api/analyze",
            json={"session_id": session_id},
            timeout=30
        )
        fair_price_2 = response2.json()["result"]["fair_price_analysis"]["fair_price_total"]

        # Справедливая цена должна увеличиться
        assert fair_price_2 > fair_price_1, \
            f"Корректировки не работают! Цена до: {fair_price_1:,}, после: {fair_price_2:,}"

        price_diff_percent = ((fair_price_2 - fair_price_1) / fair_price_1) * 100

        print(f"✅ Корректировки работают")
        print(f"   Цена до улучшений: {fair_price_1:,} ₽")
        print(f"   Цена после улучшений: {fair_price_2:,} ₽")
        print(f"   Разница: +{price_diff_percent:.1f}%")

    def test_07_session_sharing_works(self):
        """Тест 7: Шаринг сессии работает"""
        # Парсим объект
        parse_response = requests.post(
            f"{BASE_URL}/api/parse",
            json={"url": TEST_PROPERTY_URL},
            timeout=60
        )
        session_id = parse_response.json()["session_id"]

        # Проверяем что сессия доступна по URL
        response = requests.get(f"{BASE_URL}/calculator?session={session_id}", timeout=10)

        assert response.status_code == 200
        assert session_id in response.text, "Session ID не найден на странице"

        print(f"✅ Шаринг сессии работает")
        print(f"   URL: {BASE_URL}/calculator?session={session_id}")


class TestAPICriticalEndpoints:
    """Тесты критических API эндпоинтов"""

    def test_health_check(self):
        """Проверка health endpoint"""
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        assert response.status_code == 200
        print("✅ Health check passed")

    def test_api_has_rate_limiting(self):
        """Проверка что rate limiting работает"""
        # Делаем много запросов быстро
        responses = []
        for i in range(20):
            response = requests.post(
                f"{BASE_URL}/api/parse",
                json={"url": "invalid"},
                timeout=5
            )
            responses.append(response.status_code)

        # Должен быть хотя бы один 429 (Too Many Requests)
        assert 429 in responses, "Rate limiting не работает"
        print("✅ Rate limiting работает")


class TestUIElements:
    """Тесты UI элементов (требует Playwright)"""

    def test_landing_buttons_present(self):
        """Проверка что основные кнопки присутствуют на лендинге"""
        response = requests.get(BASE_URL, timeout=10)
        html = response.text.lower()

        # Проверяем наличие ключевых элементов
        assert "калькулятор" in html or "calculator" in html, "Кнопка калькулятора не найдена"

        print("✅ Основные элементы лендинга присутствуют")


def run_full_test_suite():
    """Запуск полного набора тестов с отчетом"""
    import sys

    print("\n" + "="*70)
    print("🧪 ЗАПУСК ПОЛНОГО НАБОРА E2E ТЕСТОВ")
    print("="*70 + "\n")

    # Запускаем pytest с подробным выводом
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-s",  # Показывать print
        "--color=yes"
    ])

    if exit_code == 0:
        print("\n" + "="*70)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*70 + "\n")
    else:
        print("\n" + "="*70)
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("="*70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    run_full_test_suite()
