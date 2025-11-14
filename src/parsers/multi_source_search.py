"""
Мультиисточниковый поиск аналогов недвижимости

Этот модуль реализует стратегии поиска по нескольким источникам одновременно:
- Циан
- Домклик
- Другие площадки

Паттерн: Strategy + Facade
"""

import logging
from typing import List, Dict, Optional, Literal
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .parser_registry import ParserRegistry, get_global_registry
from .base_real_estate_parser import BaseRealEstateParser

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """
    Конфигурация поиска

    Attributes:
        sources: Список источников для поиска ('cian', 'domclick', 'all')
        strategy: Стратегия поиска
        limit_per_source: Лимит результатов на источник
        parallel: Искать параллельно
        merge_duplicates: Объединять дубликаты
        sort_by: Поле для сортировки ('price', 'similarity', 'source')
    """
    sources: List[str] = None
    strategy: Literal['same_building', 'same_area', 'citywide'] = 'citywide'
    limit_per_source: int = 20
    parallel: bool = True
    merge_duplicates: bool = True
    sort_by: str = 'price'

    def __post_init__(self):
        if self.sources is None:
            self.sources = ['cian']  # По умолчанию только Циан


class MultiSourceSearchStrategy:
    """
    Стратегия поиска по нескольким источникам

    Объединяет результаты из разных парсеров и предоставляет
    унифицированный интерфейс для поиска аналогов.

    Examples:
        >>> strategy = MultiSourceSearchStrategy()
        >>> results = strategy.search(
        ...     target_property={'price': 5000000, 'total_area': 50},
        ...     config=SearchConfig(sources=['cian', 'domclick'])
        ... )
    """

    def __init__(self, registry: Optional[ParserRegistry] = None, cache=None):
        """
        Args:
            registry: Реестр парсеров (если None, используется глобальный)
            cache: Объект кэша для парсеров
        """
        self.registry = registry or get_global_registry(cache=cache)
        self.cache = cache

    def search(
        self,
        target_property: Dict,
        config: Optional[SearchConfig] = None
    ) -> List[Dict]:
        """
        Поиск аналогов по нескольким источникам

        Args:
            target_property: Целевой объект (эталон)
            config: Конфигурация поиска

        Returns:
            Список аналогов со всех источников
        """
        if config is None:
            config = SearchConfig()

        # Определяем источники
        sources = self._resolve_sources(config.sources)

        logger.info(f"Мультиисточниковый поиск: источники={sources}, стратегия={config.strategy}")

        # Параллельный или последовательный поиск
        if config.parallel and len(sources) > 1:
            results = self._search_parallel(target_property, sources, config)
        else:
            results = self._search_sequential(target_property, sources, config)

        # Пост-обработка
        if config.merge_duplicates:
            results = self._merge_duplicates(results)

        results = self._sort_results(results, config.sort_by)

        logger.info(f"✓ Найдено {len(results)} аналогов из {len(sources)} источников")

        return results

    def _resolve_sources(self, sources: List[str]) -> List[str]:
        """
        Разрешить список источников

        Args:
            sources: Список источников или ['all']

        Returns:
            Список конкретных источников
        """
        if 'all' in sources:
            return self.registry.get_all_sources()

        # Фильтруем только зарегистрированные источники
        available_sources = self.registry.get_all_sources()
        return [s for s in sources if s in available_sources]

    def _search_parallel(
        self,
        target_property: Dict,
        sources: List[str],
        config: SearchConfig
    ) -> List[Dict]:
        """
        Параллельный поиск по источникам

        Args:
            target_property: Целевой объект
            sources: Список источников
            config: Конфигурация

        Returns:
            Объединенные результаты
        """
        all_results = []

        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            # Создаем задачи
            futures = {
                executor.submit(
                    self._search_in_source,
                    source,
                    target_property,
                    config
                ): source
                for source in sources
            }

            # Собираем результаты
            for future in as_completed(futures):
                source = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.info(f"✓ [{source}] найдено {len(results)} объектов")
                except Exception as e:
                    logger.error(f"✗ [{source}] ошибка поиска: {e}")

        return all_results

    def _search_sequential(
        self,
        target_property: Dict,
        sources: List[str],
        config: SearchConfig
    ) -> List[Dict]:
        """
        Последовательный поиск по источникам

        Args:
            target_property: Целевой объект
            sources: Список источников
            config: Конфигурация

        Returns:
            Объединенные результаты
        """
        all_results = []

        for source in sources:
            try:
                results = self._search_in_source(source, target_property, config)
                all_results.extend(results)
                logger.info(f"✓ [{source}] найдено {len(results)} объектов")
            except Exception as e:
                logger.error(f"✗ [{source}] ошибка поиска: {e}")

        return all_results

    def _search_in_source(
        self,
        source: str,
        target_property: Dict,
        config: SearchConfig
    ) -> List[Dict]:
        """
        Поиск в конкретном источнике

        Args:
            source: Имя источника
            target_property: Целевой объект
            config: Конфигурация

        Returns:
            Результаты из источника
        """
        parser = self.registry.get_parser(source_name=source)

        if not parser:
            logger.warning(f"Парсер для источника '{source}' не найден")
            return []

        # Проверяем возможности парсера
        capabilities = parser.get_capabilities()
        if not capabilities.supports_search:
            logger.warning(f"Парсер '{source}' не поддерживает поиск")
            return []

        # Выполняем поиск
        results = parser.search_similar(
            target_property=target_property,
            limit=config.limit_per_source,
            strategy=config.strategy
        )

        return results

    def _merge_duplicates(self, results: List[Dict]) -> List[Dict]:
        """
        Объединить дубликаты (по адресу или ID)

        Args:
            results: Список результатов

        Returns:
            Список без дубликатов
        """
        seen = set()
        unique_results = []

        for result in results:
            # Создаем ключ для идентификации (адрес + площадь)
            key = (
                result.get('address', '').lower().strip(),
                result.get('total_area'),
                result.get('floor')
            )

            if key not in seen and key[0]:  # Пропускаем если нет адреса
                seen.add(key)
                unique_results.append(result)

        removed = len(results) - len(unique_results)
        if removed > 0:
            logger.info(f"Удалено дубликатов: {removed}")

        return unique_results

    def _sort_results(self, results: List[Dict], sort_by: str) -> List[Dict]:
        """
        Сортировка результатов

        Args:
            results: Список результатов
            sort_by: Поле для сортировки

        Returns:
            Отсортированный список
        """
        if sort_by == 'price':
            return sorted(results, key=lambda x: x.get('price') or float('inf'))
        elif sort_by == 'total_area':
            return sorted(results, key=lambda x: x.get('total_area') or 0, reverse=True)
        elif sort_by == 'source':
            return sorted(results, key=lambda x: x.get('source', ''))

        return results

    def get_sources_stats(self) -> Dict[str, Dict]:
        """
        Получить статистику по всем источникам

        Returns:
            Словарь {source: stats}
        """
        return self.registry.get_all_parsers_info()


# === УДОБНЫЕ ФУНКЦИИ ===

def search_across_sources(
    target_property: Dict,
    sources: List[str] = None,
    strategy: str = 'citywide',
    limit_per_source: int = 20,
    parallel: bool = True
) -> List[Dict]:
    """
    Удобная функция для поиска по нескольким источникам

    Args:
        target_property: Целевой объект
        sources: Список источников (по умолчанию ['cian'])
        strategy: Стратегия поиска
        limit_per_source: Лимит на источник
        parallel: Параллельный поиск

    Returns:
        Список аналогов

    Examples:
        >>> results = search_across_sources(
        ...     {'price': 5000000, 'total_area': 50},
        ...     sources=['cian', 'domclick'],
        ...     limit_per_source=30
        ... )
    """
    if sources is None:
        sources = ['cian']

    config = SearchConfig(
        sources=sources,
        strategy=strategy,
        limit_per_source=limit_per_source,
        parallel=parallel
    )

    strategy_obj = MultiSourceSearchStrategy()
    return strategy_obj.search(target_property, config)
