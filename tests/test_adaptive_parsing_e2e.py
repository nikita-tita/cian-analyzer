"""
E2E тесты для адаптивной системы парсинга

Эти тесты проверяют полный цикл работы с реальными (или mock) URL
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@pytest.fixture
def orchestrator():
    """Фикстура для создания оркестратора"""
    from parsers.adaptive_orchestrator import AdaptiveParserOrchestrator
    return AdaptiveParserOrchestrator(enable_stats=True)


class TestCianE2E:
    """E2E тесты для Циан"""

    @pytest.mark.parametrize("url,expected_source", [
        ('https://www.cian.ru/sale/flat/12345/', 'cian'),
        ('https://cian.ru/sale/flat/67890/', 'cian'),
    ])
    def test_detect_cian_source(self, orchestrator, url, expected_source):
        """Тест определения источника Циан"""
        assert orchestrator._detect_source(url) == expected_source

    def test_cian_parser_creation(self, orchestrator):
        """Тест создания парсера Циан"""
        from parsers.adaptive_orchestrator import ParsingStrategy

        parser = orchestrator._get_parser('cian', ParsingStrategy.BROWSER_LIGHT)
        assert parser is not None
        assert parser.get_source_name() == 'cian'

    @pytest.mark.skip(reason="Requires real URL")
    def test_cian_full_parsing(self, orchestrator):
        """Полный тест парсинга Циан (требует реальный URL)"""
        # TODO: Заменить на реальный URL для тестирования
        test_url = 'https://www.cian.ru/sale/flat/TEST_ID/'

        result = orchestrator.parse_property(test_url)

        assert result.success
        assert result.data is not None
        assert 'title' in result.data
        assert 'price' in result.data


class TestDomclickE2E:
    """E2E тесты для Домклик"""

    @pytest.mark.parametrize("url,expected_source", [
        ('https://domclick.ru/card/sale__flat__12345', 'domclick'),
        ('https://www.domclick.ru/card/sale_flat_67890', 'domclick'),
    ])
    def test_detect_domclick_source(self, orchestrator, url, expected_source):
        """Тест определения источника Домклик"""
        assert orchestrator._detect_source(url) == expected_source

    def test_domclick_parser_creation(self, orchestrator):
        """Тест создания парсера Домклик"""
        from parsers.adaptive_orchestrator import ParsingStrategy

        parser = orchestrator._get_parser('domclick', ParsingStrategy.API_FIRST)
        assert parser is not None
        assert parser.get_source_name() == 'domclick'

    def test_domclick_extract_offer_id(self):
        """Тест извлечения ID из URL Домклик"""
        from parsers.domclick_parser import DomClickParser

        parser = DomClickParser()

        test_cases = [
            ('https://domclick.ru/card/sale__flat__1234567890', '1234567890'),
            ('https://domclick.ru/card/sale_flat_9876543210', '9876543210'),
        ]

        for url, expected_id in test_cases:
            assert parser._extract_offer_id(url) == expected_id


class TestAvitoE2E:
    """E2E тесты для Авито"""

    @pytest.mark.parametrize("url,expected_source", [
        ('https://www.avito.ru/sankt-peterburg/kvartiry/2-k._kvartira_1234567890', 'avito'),
        ('https://avito.ru/moskva/kvartiry/1234567890', 'avito'),
    ])
    def test_detect_avito_source(self, orchestrator, url, expected_source):
        """Тест определения источника Авито"""
        assert orchestrator._detect_source(url) == expected_source

    def test_avito_parser_creation(self, orchestrator):
        """Тест создания парсера Авито"""
        from parsers.adaptive_orchestrator import ParsingStrategy

        parser = orchestrator._get_parser('avito', ParsingStrategy.MOBILE_API)
        assert parser is not None
        assert parser.get_source_name() == 'avito'

    def test_avito_extract_offer_id(self):
        """Тест извлечения ID из URL Авито"""
        from parsers.avito_parser import AvitoParser

        parser = AvitoParser()

        test_cases = [
            ('https://www.avito.ru/sankt-peterburg/kvartiry/2-k._kvartira_56m_44et._1234567890', '1234567890'),
            ('https://m.avito.ru/sankt-peterburg/kvartiry/9876543210', '9876543210'),
        ]

        for url, expected_id in test_cases:
            offer_id = parser._extract_offer_id(url)
            assert offer_id == expected_id, f"Failed for {url}"


class TestYandexE2E:
    """E2E тесты для Яндекс"""

    @pytest.mark.parametrize("url,expected_source", [
        ('https://realty.yandex.ru/offer/1234567890/', 'yandex'),
        ('https://yandex.ru/realty/offer/9876543210', 'yandex'),
    ])
    def test_detect_yandex_source(self, orchestrator, url, expected_source):
        """Тест определения источника Яндекс"""
        assert orchestrator._detect_source(url) == expected_source

    def test_yandex_parser_creation(self, orchestrator):
        """Тест создания парсера Яндекс"""
        from parsers.adaptive_orchestrator import ParsingStrategy

        parser = orchestrator._get_parser('yandex', ParsingStrategy.API_FIRST)
        assert parser is not None
        assert parser.get_source_name() == 'yandex'

    def test_yandex_extract_offer_id(self):
        """Тест извлечения ID из URL Яндекс"""
        from parsers.yandex_realty_parser import YandexRealtyParser

        parser = YandexRealtyParser()

        test_cases = [
            ('https://realty.yandex.ru/offer/1234567890/', '1234567890'),
            ('https://realty.yandex.ru/offer/9876543210', '9876543210'),
        ]

        for url, expected_id in test_cases:
            assert parser._extract_offer_id(url) == expected_id


class TestFallbackChain:
    """Тесты cascading fallback механизма"""

    def test_fallback_chain_order(self, orchestrator):
        """Тест порядка стратегий в fallback chain"""
        # Домклик должен пробовать: API → Browser Light → Browser Heavy
        domclick_chain = orchestrator.source_strategy_map['domclick']

        from parsers.adaptive_orchestrator import ParsingStrategy

        assert domclick_chain[0] == ParsingStrategy.API_FIRST
        assert ParsingStrategy.BROWSER_LIGHT in domclick_chain
        assert ParsingStrategy.BROWSER_HEAVY in domclick_chain

    @patch('parsers.adaptive_orchestrator.AdaptiveParserOrchestrator._get_parser')
    def test_fallback_on_failure(self, mock_get_parser, orchestrator):
        """Тест переключения на fallback при неудаче"""
        # Mock парсер который всегда падает
        mock_parser = Mock()
        mock_parser.parse_detail_page.side_effect = Exception("Parser failed")
        mock_get_parser.return_value = mock_parser

        result = orchestrator.parse_property(
            'https://www.cian.ru/sale/flat/12345/',
            enable_fallback=True
        )

        # Должно быть несколько попыток (fallback chain)
        assert not result.success
        assert len(result.fallback_chain) > 1


class TestMultiSourceSearch:
    """Тесты поиска на нескольких источниках"""

    def test_multi_source_search_sources_parameter(self, orchestrator):
        """Тест указания источников для поиска"""
        target_property = {
            'price': 10_000_000,
            'total_area': 50,
            'rooms': 2,
        }

        # Mock search_similar для каждого парсера
        with patch.object(orchestrator, '_get_parser') as mock_get_parser:
            mock_parser = Mock()
            mock_parser.search_similar.return_value = [
                {'title': 'Test', 'price': 10_000_000, 'source': 'test'}
            ]
            mock_get_parser.return_value = mock_parser

            results = orchestrator.search_similar(
                target_property,
                sources=['cian', 'domclick'],
                limit=10
            )

            # Должно быть минимум 2 вызова (по одному на каждый источник)
            assert mock_parser.search_similar.call_count >= 2


class TestFieldMapping:
    """Тесты маппинга полей"""

    def test_domclick_field_mapping(self):
        """Тест маппинга полей Домклик"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('domclick')

        # Тестовые данные в формате Домклик
        source_data = {
            'title': 'Test Property',
            'totalArea': 50.5,
            'roomsCount': 2,
            'floorNumber': 5,
            'floorsCount': 10,
        }

        result = mapper.transform(source_data)

        assert result['source'] == 'domclick'
        assert result['title'] == 'Test Property'
        assert result['total_area'] == 50.5
        assert result['rooms'] == 2
        assert result['floor'] == 5
        assert result['floor_total'] == 10

    def test_avito_field_mapping(self):
        """Тест маппинга полей Авито"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('avito')

        source_data = {
            'title': 'Avito Property',
            'price': {'value': 10000000, 'currency': 'RUB'},
            'params': {
                'square': '50 м²',
                'rooms': '2',
                'floor': '5',
                'floors_total': '10',
            }
        }

        result = mapper.transform(source_data)

        assert result['source'] == 'avito'
        assert result['title'] == 'Avito Property'

    def test_yandex_field_mapping(self):
        """Тест маппинга полей Яндекс"""
        from parsers.field_mapper import get_field_mapper

        mapper = get_field_mapper('yandex')

        source_data = {
            'title': 'Yandex Property',
            'price': {'value': 10000000},
            'area': {'value': 50.5},
            'rooms': 2,
            'floor': 5,
            'floorsTotal': 10,
        }

        result = mapper.transform(source_data)

        assert result['source'] == 'yandex'
        assert result['title'] == 'Yandex Property'
        assert result['price'] == 10000000
        assert result['total_area'] == 50.5


class TestStatistics:
    """Тесты статистики"""

    def test_stats_tracking(self, orchestrator):
        """Тест отслеживания статистики"""
        initial_stats = orchestrator.get_stats()

        assert 'strategies' in initial_stats
        assert 'total_parsers_loaded' in initial_stats

    def test_stats_after_parsing(self, orchestrator):
        """Тест обновления статистики после парсинга"""
        from parsers.adaptive_orchestrator import ParsingStrategy

        # Mock успешный парсинг
        with patch.object(orchestrator, '_get_parser') as mock_get_parser:
            mock_parser = Mock()
            mock_parser.parse_detail_page.return_value = {
                'title': 'Test',
                'price': 10000000
            }
            mock_parser.get_source_name.return_value = 'test'
            mock_get_parser.return_value = mock_parser

            result = orchestrator.parse_property('https://test.com/12345')

            if result.success:
                stats = orchestrator.get_stats()
                strategy_stats = stats['strategies'][result.strategy_used.value]

                assert strategy_stats['total_attempts'] > 0
                assert strategy_stats['successful_attempts'] > 0


class TestErrorHandling:
    """Тесты обработки ошибок"""

    def test_unknown_source(self, orchestrator):
        """Тест обработки неизвестного источника"""
        result = orchestrator.parse_property('https://unknown-site.com/12345')

        assert not result.success
        assert 'unknown' in result.error.lower() or 'Unknown' in result.error

    def test_invalid_url(self, orchestrator):
        """Тест обработки невалидного URL"""
        result = orchestrator.parse_property('not-a-url')

        assert not result.success

    def test_parser_exception(self, orchestrator):
        """Тест обработки исключения в парсере"""
        with patch.object(orchestrator, '_get_parser') as mock_get_parser:
            mock_parser = Mock()
            mock_parser.parse_detail_page.side_effect = Exception("Critical error")
            mock_get_parser.return_value = mock_parser

            result = orchestrator.parse_property('https://www.cian.ru/sale/flat/12345/')

            assert not result.success
            assert result.error is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-k', 'not skip'])
