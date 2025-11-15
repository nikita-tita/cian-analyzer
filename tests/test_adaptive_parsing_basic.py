"""
Базовые тесты для адаптивной системы парсинга

Эти тесты проверяют:
1. Импорт всех модулей
2. Создание оркестратора
3. Создание стратегий
4. Создание парсеров
5. Маппинг полей
"""

import pytest
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestImports:
    """Тесты импорта модулей"""

    def test_import_orchestrator(self):
        """Тест импорта оркестратора"""
        from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator
        assert AdaptiveParserOrchestrator is not None

    def test_import_strategies(self):
        """Тест импорта стратегий"""
        try:
            from parsers.strategies.base_strategy import BaseParsingStrategy
            assert BaseParsingStrategy is not None
        except ImportError as e:
            pytest.skip(f"Strategy import failed: {e}")

    def test_import_parsers(self):
        """Тест импорта парсеров"""
        from parsers.domclick_parser import DomClickParser
        from parsers.cian_parser_adapter import CianParser

        assert DomClickParser is not None
        assert CianParser is not None

    def test_import_avito_parser(self):
        """Тест импорта парсера Avito"""
        from parsers.avito_parser import AvitoParser
        assert AvitoParser is not None

    def test_import_yandex_parser(self):
        """Тест импорта парсера Yandex"""
        from parsers.yandex_realty_parser import YandexRealtyParser
        assert YandexRealtyParser is not None

    def test_import_field_mapper(self):
        """Тест импорта field mapper"""
        from parsers.field_mapper import get_field_mapper
        assert get_field_mapper is not None


class TestOrchestrator:
    """Тесты оркестратора"""

    def test_create_orchestrator(self):
        """Тест создания оркестратора"""
        from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator

        orchestrator = AdaptiveParserOrchestrator(enable_stats=True)
        assert orchestrator is not None
        assert orchestrator.enable_stats is True

    def test_detect_source(self):
        """Тест определения источника по URL"""
        from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator

        orchestrator = AdaptiveParserOrchestrator()

        # Тестируем разные URL
        assert orchestrator._detect_source('https://www.cian.ru/sale/flat/12345/') == 'cian'
        assert orchestrator._detect_source('https://domclick.ru/card/sale__flat__12345') == 'domclick'
        assert orchestrator._detect_source('https://www.avito.ru/sankt-peterburg/kvartiry/123') == 'avito'
        assert orchestrator._detect_source('https://realty.yandex.ru/offer/12345/') == 'yandex'
        assert orchestrator._detect_source('https://example.com') == 'unknown'

    def test_source_strategy_map(self):
        """Тест маппинга стратегий для источников"""
        from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator

        orchestrator = AdaptiveParserOrchestrator()

        # Проверяем, что все источники имеют стратегии
        assert 'cian' in orchestrator.source_strategy_map
        assert 'domclick' in orchestrator.source_strategy_map
        assert 'avito' in orchestrator.source_strategy_map
        assert 'yandex' in orchestrator.source_strategy_map

        # Проверяем, что каждый источник имеет минимум 1 стратегию
        for source, strategies in orchestrator.source_strategy_map.items():
            assert len(strategies) >= 1, f"Source {source} should have at least 1 strategy"

    def test_get_stats(self):
        """Тест получения статистики"""
        from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator

        orchestrator = AdaptiveParserOrchestrator(enable_stats=True)
        stats = orchestrator.get_stats()

        assert 'strategies' in stats
        assert 'total_parsers_loaded' in stats
        assert isinstance(stats['strategies'], dict)


class TestStrategies:
    """Тесты стратегий парсинга"""

    def test_curl_cffi_strategy_available(self):
        """Тест доступности curl_cffi стратегии"""
        try:
            from parsers.strategies.curl_cffi_strategy import CurlCffiStrategy, CURL_CFFI_AVAILABLE

            if not CURL_CFFI_AVAILABLE:
                pytest.skip("curl_cffi not installed")

            strategy = CurlCffiStrategy()
            assert strategy.name == 'curl_cffi'

        except ImportError:
            pytest.skip("curl_cffi strategy not available")

    def test_httpx_strategy_available(self):
        """Тест доступности httpx стратегии"""
        try:
            from parsers.strategies.httpx_strategy import HttpxStrategy, HTTPX_AVAILABLE

            if not HTTPX_AVAILABLE:
                pytest.skip("httpx not installed")

            strategy = HttpxStrategy()
            assert strategy.name == 'httpx'

        except ImportError:
            pytest.skip("httpx strategy not available")

    def test_playwright_stealth_strategy_available(self):
        """Тест доступности Playwright-Stealth стратегии"""
        try:
            from parsers.strategies.playwright_stealth_strategy import PlaywrightStealthStrategy, PLAYWRIGHT_AVAILABLE

            if not PLAYWRIGHT_AVAILABLE:
                pytest.skip("Playwright not installed")

            strategy = PlaywrightStealthStrategy()
            assert strategy.name == 'playwright_stealth'

        except ImportError:
            pytest.skip("Playwright-Stealth strategy not available")

    def test_nodriver_strategy_available(self):
        """Тест доступности Nodriver стратегии"""
        try:
            from parsers.strategies.nodriver_strategy import NodriverStrategy, NODRIVER_AVAILABLE

            if not NODRIVER_AVAILABLE:
                pytest.skip("Nodriver not installed")

            strategy = NodriverStrategy()
            assert strategy.name == 'nodriver'

        except ImportError:
            pytest.skip("Nodriver strategy not available")


class TestParsers:
    """Тесты парсеров"""

    def test_create_domclick_parser(self):
        """Тест создания парсера Домклика"""
        from parsers.domclick_parser import DomClickParser

        parser = DomClickParser(region='spb', use_api=True)
        assert parser.get_source_name() == 'domclick'

    def test_create_cian_parser(self):
        """Тест создания парсера Циана"""
        from parsers.cian_parser_adapter import CianParser

        parser = CianParser(region='spb')
        assert parser.get_source_name() == 'cian'

    def test_create_avito_parser(self):
        """Тест создания парсера Авито"""
        from parsers.avito_parser import AvitoParser

        parser = AvitoParser(region='spb', use_mobile_api=True)
        assert parser.get_source_name() == 'avito'

    def test_create_yandex_parser(self):
        """Тест создания парсера Яндекс"""
        from parsers.yandex_realty_parser import YandexRealtyParser

        parser = YandexRealtyParser(region='spb', use_graphql=True)
        assert parser.get_source_name() == 'yandex'


class TestFieldMappers:
    """Тесты маппинга полей"""

    def test_get_cian_mapper(self):
        """Тест маппера Циана"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('cian')
        assert mapper.source_name == 'cian'

    def test_get_domclick_mapper(self):
        """Тест маппера Домклика"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('domclick')
        assert mapper.source_name == 'domclick'

    def test_get_avito_mapper(self):
        """Тест маппера Авито"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('avito')
        assert mapper.source_name == 'avito'

    def test_get_yandex_mapper(self):
        """Тест маппера Яндекс"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('yandex')
        assert mapper.source_name == 'yandex'

    def test_transform_data(self):
        """Тест трансформации данных"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('cian')

        source_data = {
            'title': 'Test Property',
            'price_raw': '10000000',
            'total_area': 50,
        }

        result = mapper.transform(source_data)

        assert 'source' in result
        assert result['source'] == 'cian'
        assert 'title' in result
        assert result['title'] == 'Test Property'


if __name__ == '__main__':
    # Запуск тестов
    pytest.main([__file__, '-v', '--tb=short'])
