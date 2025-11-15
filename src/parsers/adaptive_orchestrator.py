"""
Адаптивный оркестратор парсинга - главный координатор всех стратегий

Этот модуль реализует:
1. Автоматический выбор оптимальной стратегии парсинга
2. Cascading fallback при неудаче
3. Tracking успешности стратегий
4. Адаптивное переключение между технологиями

Архитектура:
    Strategy Chain → API → Browser Light → Browser Heavy → Proxy Rotation
"""

import logging
import time
from typing import Optional, Dict, List, Tuple, Literal
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ParsingStrategy(Enum):
    """Типы стратегий парсинга"""
    API_FIRST = "api_first"                    # curl_cffi, httpx, requests
    BROWSER_LIGHT = "browser_light"            # Playwright + Stealth
    BROWSER_HEAVY = "browser_heavy"            # Nodriver, undetected-chrome
    PROXY_ROTATION = "proxy_rotation"          # Proxy pool + браузер
    MOBILE_API = "mobile_api"                  # Мобильное API (для Авито)


@dataclass
class StrategyStats:
    """Статистика успешности стратегии"""
    name: str
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    avg_response_time: float = 0.0
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        """Процент успешности"""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_attempts / self.total_attempts) * 100

    def record_success(self, response_time: float):
        """Записать успешную попытку"""
        self.total_attempts += 1
        self.successful_attempts += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()

        # Обновляем среднее время ответа (moving average)
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (self.avg_response_time * 0.8) + (response_time * 0.2)

    def record_failure(self):
        """Записать неудачную попытку"""
        self.total_attempts += 1
        self.failed_attempts += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()


@dataclass
class ParsedResult:
    """Результат парсинга"""
    success: bool
    data: Optional[Dict] = None
    strategy_used: Optional[ParsingStrategy] = None
    response_time: float = 0.0
    error: Optional[str] = None
    fallback_chain: List[str] = field(default_factory=list)


class AdaptiveParserOrchestrator:
    """
    Главный оркестратор адаптивного парсинга

    Возможности:
    1. Автоматический выбор стратегии на основе:
       - Истории успешности
       - Характера сайта (защита)
       - Требуемой скорости
    2. Cascading fallback при неудаче
    3. Обучение на результатах (success rate tracking)
    4. Интеграция всех парсеров (Cian, Domclick, Avito, Yandex)
    """

    def __init__(self, cache=None, enable_stats: bool = True):
        """
        Args:
            cache: Redis cache instance
            enable_stats: Включить tracking статистики
        """
        self.cache = cache
        self.enable_stats = enable_stats

        # Статистика по каждой стратегии
        self.stats: Dict[str, StrategyStats] = {}
        for strategy in ParsingStrategy:
            self.stats[strategy.value] = StrategyStats(name=strategy.value)

        # Карта источников и их предпочтительных стратегий
        self.source_strategy_map = {
            'domclick': [
                ParsingStrategy.API_FIRST,         # REST API
                ParsingStrategy.BROWSER_LIGHT,     # Playwright
                ParsingStrategy.BROWSER_HEAVY,     # Nodriver
            ],
            'cian': [
                ParsingStrategy.BROWSER_LIGHT,     # Playwright-Stealth (JSON-LD)
                ParsingStrategy.API_FIRST,         # Скрытые JSON endpoints
                ParsingStrategy.BROWSER_HEAVY,     # Nodriver
            ],
            'avito': [
                ParsingStrategy.MOBILE_API,        # Мобильное API
                ParsingStrategy.BROWSER_HEAVY,     # Nodriver (обход DataDome)
                ParsingStrategy.PROXY_ROTATION,    # Ротация прокси
            ],
            'yandex': [
                ParsingStrategy.API_FIRST,         # GraphQL API
                ParsingStrategy.BROWSER_LIGHT,     # Playwright
                ParsingStrategy.BROWSER_HEAVY,     # Fallback
            ],
        }

        # Парсеры (ленивая инициализация)
        self._parsers = {}
        self._strategy_implementations = {}

        logger.info("✓ AdaptiveParserOrchestrator инициализирован")

    def _detect_source(self, url: str) -> str:
        """
        Определить источник по URL

        Args:
            url: URL объявления

        Returns:
            Название источника ('cian', 'domclick', 'avito', 'yandex')
        """
        url_lower = url.lower()

        if 'cian.ru' in url_lower:
            return 'cian'
        elif 'domclick.ru' in url_lower:
            return 'domclick'
        elif 'avito.ru' in url_lower:
            return 'avito'
        elif 'realty.yandex.ru' in url_lower or 'yandex.ru/realty' in url_lower:
            return 'yandex'
        else:
            logger.warning(f"Неизвестный источник: {url}")
            return 'unknown'

    def _get_parser(self, source: str, strategy: ParsingStrategy):
        """
        Получить парсер для заданного источника и стратегии

        Args:
            source: Название источника
            strategy: Стратегия парсинга

        Returns:
            Экземпляр парсера или None
        """
        key = f"{source}_{strategy.value}"

        if key in self._parsers:
            return self._parsers[key]

        # Ленивая инициализация парсера
        try:
            if source == 'cian':
                parser = self._create_cian_parser(strategy)
            elif source == 'domclick':
                parser = self._create_domclick_parser(strategy)
            elif source == 'avito':
                parser = self._create_avito_parser(strategy)
            elif source == 'yandex':
                parser = self._create_yandex_parser(strategy)
            else:
                logger.error(f"Неподдерживаемый источник: {source}")
                return None

            self._parsers[key] = parser
            return parser

        except Exception as e:
            logger.error(f"Ошибка создания парсера {source}/{strategy.value}: {e}")
            return None

    def _create_cian_parser(self, strategy: ParsingStrategy):
        """Создать парсер Циана для заданной стратегии"""
        from .cian_parser_adapter import CianParser

        if strategy == ParsingStrategy.BROWSER_LIGHT:
            # Существующий Playwright парсер
            return CianParser(cache=self.cache)
        elif strategy == ParsingStrategy.API_FIRST:
            # TODO: JSON endpoints парсер
            logger.warning("Cian API parser not implemented yet, using browser")
            return CianParser(cache=self.cache)
        elif strategy == ParsingStrategy.BROWSER_HEAVY:
            # TODO: Nodriver парсер
            logger.warning("Cian Nodriver parser not implemented yet, using browser")
            return CianParser(cache=self.cache)

        return CianParser(cache=self.cache)

    def _create_domclick_parser(self, strategy: ParsingStrategy):
        """Создать парсер Домклика для заданной стратегии"""
        from .domclick_parser import DomClickParser

        if strategy == ParsingStrategy.API_FIRST:
            # API-first режим
            return DomClickParser(cache=self.cache, use_api=True)
        elif strategy == ParsingStrategy.BROWSER_LIGHT:
            # Playwright режим
            return DomClickParser(cache=self.cache, use_api=False)
        elif strategy == ParsingStrategy.BROWSER_HEAVY:
            # TODO: Nodriver режим
            logger.warning("Domclick Nodriver parser not implemented yet, using Playwright")
            return DomClickParser(cache=self.cache, use_api=False)

        return DomClickParser(cache=self.cache, use_api=True)

    def _create_avito_parser(self, strategy: ParsingStrategy):
        """Создать парсер Авито для заданной стратегии"""
        # TODO: Implement Avito parser
        logger.error("Avito parser not implemented yet")
        return None

    def _create_yandex_parser(self, strategy: ParsingStrategy):
        """Создать парсер Яндекса для заданной стратегии"""
        # TODO: Implement Yandex parser
        logger.error("Yandex parser not implemented yet")
        return None

    def parse_property(
        self,
        url: str,
        preferred_strategy: Optional[ParsingStrategy] = None,
        enable_fallback: bool = True
    ) -> ParsedResult:
        """
        Парсинг объявления с адаптивным выбором стратегии

        Args:
            url: URL объявления
            preferred_strategy: Предпочтительная стратегия (опционально)
            enable_fallback: Включить fallback на другие стратегии

        Returns:
            ParsedResult с результатом парсинга
        """
        logger.info("=" * 80)
        logger.info(f"🚀 ADAPTIVE PARSING: {url}")
        logger.info("=" * 80)

        # Определяем источник
        source = self._detect_source(url)
        logger.info(f"📍 Источник: {source}")

        if source == 'unknown':
            return ParsedResult(
                success=False,
                error="Unknown source",
                fallback_chain=[]
            )

        # Получаем цепочку стратегий для этого источника
        strategy_chain = self.source_strategy_map.get(source, [])

        # Если указана предпочтительная стратегия, ставим её первой
        if preferred_strategy and preferred_strategy in strategy_chain:
            strategy_chain = [preferred_strategy] + [s for s in strategy_chain if s != preferred_strategy]

        logger.info(f"🔗 Цепочка стратегий: {[s.value for s in strategy_chain]}")

        # Пробуем каждую стратегию по порядку
        fallback_chain = []

        for i, strategy in enumerate(strategy_chain):
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 Попытка #{i+1}: {strategy.value}")
            logger.info(f"{'='*60}")

            start_time = time.time()

            try:
                # Получаем парсер для этой стратегии
                parser = self._get_parser(source, strategy)

                if not parser:
                    logger.warning(f"⚠️ Парсер не доступен для {source}/{strategy.value}")
                    fallback_chain.append(f"{strategy.value} (not available)")
                    continue

                # Выполняем парсинг
                logger.info(f"🔄 Парсинг через {strategy.value}...")
                data = parser.parse_detail_page(url)

                response_time = time.time() - start_time

                # Проверяем успешность
                if data and data.get('title'):
                    logger.info(f"✅ УСПЕХ через {strategy.value} ({response_time:.2f}s)")
                    logger.info(f"   Название: {data.get('title', '')[:60]}...")
                    logger.info(f"   Цена: {data.get('price', 'N/A')}")
                    logger.info(f"   Площадь: {data.get('total_area', 'N/A')} м²")

                    # Записываем успех
                    if self.enable_stats:
                        self.stats[strategy.value].record_success(response_time)

                    fallback_chain.append(f"{strategy.value} (success)")

                    return ParsedResult(
                        success=True,
                        data=data,
                        strategy_used=strategy,
                        response_time=response_time,
                        fallback_chain=fallback_chain
                    )
                else:
                    logger.warning(f"⚠️ Парсинг вернул пустые данные")
                    fallback_chain.append(f"{strategy.value} (empty data)")

                    if self.enable_stats:
                        self.stats[strategy.value].record_failure()

            except Exception as e:
                response_time = time.time() - start_time
                logger.error(f"❌ Ошибка {strategy.value}: {e}")
                fallback_chain.append(f"{strategy.value} (error: {str(e)[:50]})")

                if self.enable_stats:
                    self.stats[strategy.value].record_failure()

            # Если это последняя стратегия или fallback отключен, выходим
            if not enable_fallback or i == len(strategy_chain) - 1:
                break

            logger.info(f"🔄 Переключаюсь на следующую стратегию...")

        # Все стратегии провалились
        logger.error("❌ ВСЕ СТРАТЕГИИ ПРОВАЛИЛИСЬ")
        logger.error(f"Fallback chain: {' → '.join(fallback_chain)}")

        return ParsedResult(
            success=False,
            error="All strategies failed",
            fallback_chain=fallback_chain
        )

    def search_similar(
        self,
        target_property: Dict,
        sources: List[str] = None,
        limit: int = 20,
        strategy: Literal['same_building', 'same_area', 'citywide'] = 'citywide'
    ) -> List[Dict]:
        """
        Поиск аналогов на нескольких источниках

        Args:
            target_property: Целевой объект
            sources: Список источников для поиска (по умолчанию все)
            limit: Лимит результатов с каждого источника
            strategy: Стратегия поиска

        Returns:
            Объединенный список аналогов со всех источников
        """
        logger.info("=" * 80)
        logger.info(f"🔍 MULTI-SOURCE SEARCH")
        logger.info("=" * 80)

        if sources is None:
            sources = ['cian', 'domclick', 'avito', 'yandex']

        all_results = []

        for source in sources:
            logger.info(f"\n{'='*60}")
            logger.info(f"📍 Поиск на {source}")
            logger.info(f"{'='*60}")

            try:
                # Получаем парсер для этого источника (используем первую стратегию)
                strategy_chain = self.source_strategy_map.get(source, [])
                if not strategy_chain:
                    logger.warning(f"⚠️ Нет стратегий для {source}")
                    continue

                parser = self._get_parser(source, strategy_chain[0])

                if not parser:
                    logger.warning(f"⚠️ Парсер не доступен для {source}")
                    continue

                # Выполняем поиск
                results = parser.search_similar(target_property, limit=limit, strategy=strategy)

                logger.info(f"✓ Найдено {len(results)} результатов на {source}")

                # Добавляем source к каждому результату
                for result in results:
                    result['source'] = source

                all_results.extend(results)

            except Exception as e:
                logger.error(f"❌ Ошибка поиска на {source}: {e}")

        logger.info("=" * 80)
        logger.info(f"🏁 ИТОГО: Найдено {len(all_results)} аналогов со всех источников")
        logger.info("=" * 80)

        return all_results

    def get_stats(self) -> Dict:
        """Получить статистику работы оркестратора"""
        stats_dict = {}

        for strategy_name, stats in self.stats.items():
            stats_dict[strategy_name] = {
                'total_attempts': stats.total_attempts,
                'successful_attempts': stats.successful_attempts,
                'failed_attempts': stats.failed_attempts,
                'success_rate': round(stats.success_rate, 2),
                'avg_response_time': round(stats.avg_response_time, 2),
                'consecutive_failures': stats.consecutive_failures,
            }

        return {
            'strategies': stats_dict,
            'total_parsers_loaded': len(self._parsers),
        }

    def print_stats(self):
        """Вывести статистику в красивом виде"""
        print("\n" + "=" * 80)
        print("📊 СТАТИСТИКА АДАПТИВНОГО ПАРСИНГА")
        print("=" * 80)

        for strategy_name, stats in self.stats.items():
            if stats.total_attempts == 0:
                continue

            print(f"\n🎯 {strategy_name}:")
            print(f"   ├─ Попыток: {stats.total_attempts}")
            print(f"   ├─ Успешных: {stats.successful_attempts}")
            print(f"   ├─ Неудачных: {stats.failed_attempts}")
            print(f"   ├─ Success Rate: {stats.success_rate:.1f}%")
            print(f"   ├─ Среднее время: {stats.avg_response_time:.2f}s")
            print(f"   └─ Последовательных провалов: {stats.consecutive_failures}")

        print("\n" + "=" * 80)
