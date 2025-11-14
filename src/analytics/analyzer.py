"""
Улучшенный аналитический движок с валидацией
"""

import statistics
import math
import logging
from typing import Any, Dict, List, Tuple
from datetime import datetime
from functools import lru_cache
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

from ..models.property import (
    ComparableProperty,
    AnalysisRequest,
    PriceScenario,
    AnalysisResult
)
from ..utils.market_rates import MarketRatesService

try:
    from .property_tracker import get_tracker, EventType
    TRACKING_ENABLED = True
except ImportError:
    TRACKING_ENABLED = False
    logger.warning("Property tracking not available")

# Новая логика расчета справедливой цены
from .fair_price_calculator import calculate_fair_price_with_medians

# Новые модули аналитики
from .price_range import calculate_price_range
from .attractiveness_index import calculate_attractiveness_index
from .time_forecast import forecast_time_to_sell, forecast_at_different_prices
from .recommendations import RecommendationEngine
from .liquidity_profile import build_liquidity_profile

# Импорт валидатора данных
try:
    from .data_validator import (
        filter_valid_comparables,
        get_validation_summary,
        check_minimum_comparables
    )
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    logger.warning("⚠️ Модуль валидации недоступен")

# Импорт статистического анализа
try:
    from .statistical_analysis import (
        detect_outliers_iqr,
        calculate_data_quality,
        check_data_sufficiency
    )
    STATISTICAL_ANALYSIS_AVAILABLE = True
except ImportError:
    STATISTICAL_ANALYSIS_AVAILABLE = False
    logger.warning("⚠️ Модуль статистического анализа недоступен")


class RealEstateAnalyzer:
    """
    Анализатор недвижимости с улучшенной эффективностью

    Улучшения:
    - Валидация через Pydantic
    - Кеширование расчетов
    - Конфигурируемые параметры
    - Метрики производительности
    """

    # Константы для расчетов (вынесены из кода)
    LARGE_APARTMENT_THRESHOLD = 150  # м², среднее по СПб для премиум
    LARGE_SIZE_MULTIPLIER = 0.10  # Коэффициент из исследования ЦИАН 2023
    MAX_LARGE_SIZE_BONUS = 1.05  # Максимум +5%

    DESIGN_COEFFICIENT = 1.08  # +8% за дизайнерскую отделку
    PANORAMIC_VIEWS_COEFFICIENT = 1.07  # +7% за панорамные виды
    PREMIUM_LOCATION_COEFFICIENT = 1.06  # +6% за премиум локацию

    def __init__(self, config: Dict = None, property_id: str = None, enable_tracking: bool = True):
        """
        Args:
            config: Конфигурация анализатора
            property_id: ID объекта для трекинга
            enable_tracking: Включить детальное логирование
        """
        self.config = config or {}
        self.request: AnalysisRequest = None
        self.filtered_comparables: List[ComparableProperty] = []
        self.data_quality: Dict = {}  # Результаты статистического анализа
        self.market_profile: Dict[str, Any] = {}

        # Трекинг
        self.property_id = property_id
        self.enable_tracking = enable_tracking and TRACKING_ENABLED
        self.tracker = get_tracker() if self.enable_tracking else None
        self.property_log = None

        # Метрики
        self.metrics = {
            'calculation_time_ms': 0,
            'comparables_filtered': 0,
            'cache_hits': 0
        }

        try:
            self.market_rates_service = MarketRatesService()
        except Exception as exc:  # pragma: no cover - защитный код
            logger.warning("Не удалось инициализировать сервис рыночных ставок: %s", exc)
            self.market_rates_service = None

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Полный анализ объекта недвижимости

        Args:
            request: Запрос на анализ (валидированный)

        Returns:
            Результат анализа
        """
        start_time = datetime.now()

        self.request = request
        self.market_profile = {}

        # Инициализация трекинга
        if self.enable_tracking and self.property_id:
            self.property_log = self.tracker.start_tracking(
                property_id=self.property_id,
                url=getattr(request.target_property, 'url', None)
            )
            self.property_log.property_info = {
                'price': request.target_property.price,
                'total_area': request.target_property.total_area,
                'rooms': request.target_property.rooms,
                'floor': request.target_property.floor,
                'total_floors': request.target_property.total_floors,
                'address': getattr(request.target_property, 'address', None)
            }
            self._log_event(EventType.ANALYSIS_STARTED, "Начат анализ объекта", {
                'comparables_count': len(request.comparables),
                'filter_outliers': request.filter_outliers
            })

        # === ВАЛИДАЦИЯ КАЧЕСТВА ДАННЫХ (ФАЗА 1) ===
        if VALIDATION_AVAILABLE:
            logger.info("=" * 60)
            logger.info("ШАГ 1: ВАЛИДАЦИЯ КАЧЕСТВА ДАННЫХ")
            logger.info("=" * 60)

            # Сводка качества данных
            validation_summary = get_validation_summary(request.comparables)
            logger.info(
                f"Качество данных: {validation_summary['valid']}/{validation_summary['total']} "
                f"валидных ({validation_summary['valid_percentage']:.1f}%)"
            )

            # Фильтрация невалидных
            comparables_to_process, excluded_reports = filter_valid_comparables(
                request.comparables,
                verbose=True
            )

            # Логируем трекинг
            if self.enable_tracking:
                excluded_count = len(excluded_reports)
                if excluded_count > 0:
                    self._log_event(
                        EventType.OUTLIERS_FILTERED,
                        f"Валидация исключила {excluded_count} некачественных аналогов",
                        {
                            'excluded_count': excluded_count,
                            'validation_summary': validation_summary
                        }
                    )
        else:
            # Без валидации - используем все
            comparables_to_process = request.comparables
            logger.info("⚠️ Валидация отключена - используются все аналоги")

        # === СТАТИСТИЧЕСКИЙ АНАЛИЗ И IQR-ФИЛЬТР (ФАЗА 2) ===
        if STATISTICAL_ANALYSIS_AVAILABLE:
            logger.info("=" * 60)
            logger.info("ШАГ 2: СТАТИСТИЧЕСКИЙ АНАЛИЗ ДАННЫХ")
            logger.info("=" * 60)

            # Оценка качества данных
            data_quality = calculate_data_quality(comparables_to_process)
            logger.info(f"Коэффициент вариации (CV): {data_quality['cv']:.1%}")
            desc = data_quality.get('description', '')
            if desc:
                logger.info(f"Качество данных: {data_quality['quality']} ({desc})")
            else:
                logger.info(f"Качество данных: {data_quality['quality']}")
            logger.info(f"Оценка качества: {data_quality['quality_score']}/100")

            # PATCH 3: АДАПТИВНАЯ IQR-фильтрация выбросов (только если n >= 5)
            n = len(comparables_to_process)
            if n >= 5:
                comparables_after_iqr, iqr_outliers = detect_outliers_iqr(comparables_to_process)

                if len(iqr_outliers) > 0:
                    logger.info(f"IQR фильтр исключил {len(iqr_outliers)} статистических выбросов")

                    if self.enable_tracking:
                        self._log_event(
                            EventType.OUTLIERS_FILTERED,
                            f"IQR фильтр исключил {len(iqr_outliers)} выбросов",
                            {
                                'outliers_count': len(iqr_outliers),
                                'data_quality': data_quality
                            }
                        )
            else:
                # Слишком мало данных для IQR - используем все аналоги
                logger.info(f"⚠️ IQR пропущен: только {n} аналог(ов), нужно минимум 5")
                comparables_after_iqr = comparables_to_process

            # Проверка достаточности данных
            is_sufficient, sufficiency_reason = check_data_sufficiency(comparables_after_iqr)

            if not is_sufficient:
                logger.warning(f"⚠️ ПРЕДУПРЕЖДЕНИЕ: {sufficiency_reason}")

                if self.enable_tracking:
                    self._log_event(
                        EventType.ANALYSIS_COMPLETED,
                        f"Предупреждение о недостаточности данных: {sufficiency_reason}",
                        {'data_quality': data_quality}
                    )

            comparables_to_process = comparables_after_iqr

            # Сохраняем результаты статистического анализа
            self.data_quality = data_quality
        else:
            data_quality = {'quality': 'unknown', 'cv': 0, 'quality_score': 50}
            self.data_quality = data_quality
            logger.info("⚠️ Статистический анализ отключен")

        # Фильтруем выбросы (применяется к уже валидным данным)
        if request.filter_outliers:
            self.filtered_comparables = self._filter_outliers(comparables_to_process)
            self.metrics['comparables_filtered'] = len(comparables_to_process) - len(self.filtered_comparables)

            if self.enable_tracking:
                self._log_event(EventType.OUTLIERS_FILTERED,
                    f"Статистическая фильтрация выбросов: {self.metrics['comparables_filtered']}",
                    {'filtered_count': self.metrics['comparables_filtered'],
                     'remaining_count': len(self.filtered_comparables)})
        else:
            self.filtered_comparables = [c for c in comparables_to_process if not c.excluded]

        # Сохраняем аналоги в лог
        if self.enable_tracking and self.property_log:
            self.property_log.comparables_data = [
                {'price': c.price, 'total_area': c.total_area, 'price_per_sqm': c.price_per_sqm}
                for c in self.filtered_comparables
            ]

        # PATCH 3: Снижаем порог с 3 до 1 (graceful degradation)
        min_comparables_required = 1
        if len(self.filtered_comparables) < min_comparables_required:
            error_msg = (
                f"Недостаточно аналогов для анализа: найдено {len(self.filtered_comparables)}, "
                f"требуется минимум {min_comparables_required}. "
                f"Попробуйте расширить критерии поиска или выбрать другой объект."
            )
            if self.enable_tracking:
                self._log_event(EventType.ANALYSIS_COMPLETED,
                    f"Анализ прерван: {error_msg}",
                    {'error': 'insufficient_comparables'})
                self.tracker.complete_property(self.property_id, "failed")

            raise ValueError(error_msg)

        # Расчеты
        market_stats = self.calculate_market_statistics()
        fair_price = self.calculate_fair_price()
        scenarios = self.generate_price_scenarios()
        strengths_weaknesses = self.calculate_strengths_weaknesses()
        comparison_chart = self.generate_comparison_chart_data()
        box_plot = self.generate_box_plot_data()

        # НОВЫЕ РАСЧЕТЫ
        # 1. Диапазон справедливой цены
        price_range = calculate_price_range(
            fair_price=fair_price.get('fair_price_total', 0),
            confidence_interval=fair_price.get('confidence_interval_95'),
            overpricing_percent=fair_price.get('overpricing_percent', 0),
            market_stats=market_stats
        )

        # 2. Индекс привлекательности
        attractiveness = calculate_attractiveness_index(
            target=request.target_property,
            fair_price_analysis=fair_price,
            market_stats=market_stats
        )

        # 3. Прогноз времени продажи
        time_forecast = forecast_time_to_sell(
            current_price=request.target_property.price or 0,
            fair_price=fair_price.get('fair_price_total', 0),
            attractiveness_index=attractiveness.get('total_index', 50),
            market_stats=market_stats
        )

        # 4. Анализ чувствительности к цене
        price_sensitivity = forecast_at_different_prices(
            fair_price=fair_price.get('fair_price_total', 0),
            attractiveness_index=attractiveness.get('total_index', 50)
        )

        # Метрики
        end_time = datetime.now()
        self.metrics['calculation_time_ms'] = int((end_time - start_time).total_seconds() * 1000)

        # Генерация рекомендаций
        try:
            rec_engine = RecommendationEngine({
                'target_property': request.target_property.model_dump(),
                'fair_price_analysis': fair_price,
                'price_scenarios': scenarios,
                'comparables': [c.model_dump() for c in self.filtered_comparables],
                'market_statistics': market_stats,
                'market_profile': self.market_profile
            })
            recommendations_objects = rec_engine.generate()
            recommendations = [rec.to_dict() for rec in recommendations_objects]
        except Exception as e:
            logger.warning(f"Не удалось сгенерировать рекомендации: {e}")
            recommendations = []

        # Завершение трекинга
        if self.enable_tracking and self.property_log:
            self.property_log.metrics = self.metrics
            # Сохраняем новые метрики
            self.property_log.price_range = price_range
            self.property_log.attractiveness_index = attractiveness
            self.property_log.time_forecast = time_forecast
            self.property_log.price_sensitivity = price_sensitivity
            self._log_event(EventType.ANALYSIS_COMPLETED,
                f"Анализ завершён за {self.metrics['calculation_time_ms']} мс")
            self.tracker.complete_property(self.property_id, "completed")

        return AnalysisResult(
            timestamp=start_time,
            target_property=request.target_property,
            comparables=self.filtered_comparables,
            market_statistics=market_stats,
            market_profile=self.market_profile,
            fair_price_analysis=fair_price,
            price_scenarios=scenarios,
            strengths_weaknesses=strengths_weaknesses,
            comparison_chart_data=comparison_chart,
            box_plot_data=box_plot,
            # Новые метрики
            price_range=price_range,
            attractiveness_index=attractiveness,
            time_forecast=time_forecast,
            price_sensitivity=price_sensitivity,
            # Рекомендации
            recommendations=recommendations
        )

    def _filter_outliers(self, comparables: List[ComparableProperty]) -> List[ComparableProperty]:
        """
        Фильтрация выбросов по правилу ±3σ

        Args:
            comparables: Список аналогов

        Returns:
            Отфильтрованный список
        """
        # Debug logging - before filtering
        logger.info(f"🔍 DEBUG _filter_outliers: Input {len(comparables)} comparables")

        if len(comparables) < 2:
            return comparables

        # Собираем цены за кв.м для статистического анализа
        prices_per_sqm = [c.price_per_sqm for c in comparables if c.price_per_sqm and not c.excluded]

        if len(prices_per_sqm) < 2:
            # Если нет достаточно данных для статистики, возвращаем все не excluded
            result = [c for c in comparables if not c.excluded]
            logger.info(f"🔍 DEBUG _filter_outliers: Not enough price data, returning {len(result)} non-excluded")
            return result

        mean = statistics.mean(prices_per_sqm)
        stdev = statistics.stdev(prices_per_sqm)

        # Фильтруем выбросы, но СОХРАНЯЕМ объявления без price_per_sqm
        filtered = []
        outliers_count = 0
        no_price_count = 0

        for c in comparables:
            if c.excluded:
                continue  # Пропускаем уже excluded

            if not c.price_per_sqm:
                # Нет price_per_sqm - сохраняем (может быть полезно для других характеристик)
                filtered.append(c)
                no_price_count += 1
            elif abs(c.price_per_sqm - mean) <= 3 * stdev:
                # В пределах ±3σ - сохраняем
                filtered.append(c)
            else:
                # Отбрасываем как выброс
                outliers_count += 1

        # Debug logging - after filtering
        logger.info(f"🔍 DEBUG _filter_outliers: Output {len(filtered)} comparables (kept {no_price_count} without price, removed {outliers_count} outliers)")

        return filtered

    def _calculate_confidence_interval(
        self,
        data: List[float],
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Расчет доверительного интервала для среднего

        Args:
            data: Список значений
            confidence: Уровень доверия (0.95 = 95%)

        Returns:
            (нижняя граница, верхняя граница)
        """
        if not data or len(data) < 2:
            return (0.0, 0.0)

        n = len(data)
        mean = statistics.mean(data)
        stdev = statistics.stdev(data)

        # t-распределение Стьюдента для малых выборок (n < 30)
        # Для больших выборок (n >= 30) можно использовать нормальное
        if n < 30:
            # Степени свободы
            df = n - 1
            # t-критерий для заданного уровня доверия
            t_critical = scipy_stats.t.ppf((1 + confidence) / 2, df)
            margin = t_critical * (stdev / math.sqrt(n))
        else:
            # z-критерий для нормального распределения
            z_critical = scipy_stats.norm.ppf((1 + confidence) / 2)
            margin = z_critical * (stdev / math.sqrt(n))

        lower = mean - margin
        upper = mean + margin

        return (lower, upper)

    @lru_cache(maxsize=128)
    def calculate_market_statistics(self) -> Dict:
        """
        Рыночная статистика по аналогам

        Returns:
            Словарь со статистикой
        """
        filtered = self.filtered_comparables

        if not filtered:
            return {}

        prices_per_sqm = [c.price_per_sqm for c in filtered if c.price_per_sqm]

        # Разделить по типу отделки
        with_design = [c for c in filtered if c.has_design]
        without_design = [c for c in filtered if not c.has_design]

        prices_with_design = [c.price_per_sqm for c in with_design if c.price_per_sqm]
        prices_without_design = [c.price_per_sqm for c in without_design if c.price_per_sqm]

        # Расчет доверительных интервалов (95%)
        ci_95_lower, ci_95_upper = self._calculate_confidence_interval(
            prices_per_sqm, confidence=0.95
        ) if len(prices_per_sqm) >= 3 else (0, 0)

        stats = {
            'all': {
                'mean': statistics.mean(prices_per_sqm) if prices_per_sqm else 0,
                'median': statistics.median(prices_per_sqm) if prices_per_sqm else 0,
                'min': min(prices_per_sqm) if prices_per_sqm else 0,
                'max': max(prices_per_sqm) if prices_per_sqm else 0,
                'stdev': statistics.stdev(prices_per_sqm) if len(prices_per_sqm) > 1 else 0,
                'count': len(prices_per_sqm),
                'filtered_out': self.metrics['comparables_filtered'],
                # Доверительные интервалы
                'confidence_interval_95': {
                    'lower': ci_95_lower,
                    'upper': ci_95_upper,
                    'margin': (ci_95_upper - ci_95_lower) / 2 if ci_95_upper > 0 else 0
                }
            },
            'with_design': {
                'mean': statistics.mean(prices_with_design) if prices_with_design else 0,
                'median': statistics.median(prices_with_design) if prices_with_design else 0,
                'count': len(with_design)
            },
            'without_design': {
                'mean': statistics.mean(prices_without_design) if prices_without_design else 0,
                'median': statistics.median(prices_without_design) if prices_without_design else 0,
                'count': len(without_design)
            }
        }

        # Логирование статистики
        if self.enable_tracking and self.property_log:
            self.property_log.market_stats = stats
            self._log_event(EventType.MARKET_STATS_CALCULATED,
                f"Рассчитана рыночная статистика ({stats['all']['count']} аналогов)",
                {'median': stats['all']['median'], 'mean': stats['all']['mean']})

        return stats

    def calculate_fair_price(self) -> Dict:
        """
        Справедливая цена методом корректировок с учетом медиан

        НОВАЯ ЛОГИКА:
        1. Рассчитываем медианы по ПЕРЕМЕННЫМ параметрам
        2. Применяем коэффициенты ТОЛЬКО за ОТЛИЧИЯ от медианы
        3. Если целевой = медиане → коэфф = 1.0

        Returns:
            Словарь с расчетом справедливой цены
        """
        market_stats = self.calculate_market_statistics()

        if not market_stats or not self.request:
            return {}

        target = self.request.target_property

        # Используем МЕДИАНУ (более устойчива к выбросам)
        if self.request.use_median:
            base_price_per_sqm = market_stats['all']['median']
            method = 'median'
        else:
            base_price_per_sqm = market_stats['all']['mean']
            method = 'mean'

        # НОВЫЙ ПОДХОД: используем функцию с медианами
        result = calculate_fair_price_with_medians(
            target=target,
            comparables=self.filtered_comparables,
            base_price_per_sqm=base_price_per_sqm,
            method=method
        )

        # Сохраняем для использования в calculate_strengths_weaknesses()
        self.fair_price_result = result

        # Добавляем доверительные интервалы для справедливой цены
        if target.total_area and len(self.filtered_comparables) >= 3:
            # Получаем цены/м² аналогов
            prices_per_sqm = [c.price_per_sqm for c in self.filtered_comparables if c.price_per_sqm]

            # Рассчитываем CI для базовой цены/м²
            ci_lower_sqm, ci_upper_sqm = self._calculate_confidence_interval(prices_per_sqm, confidence=0.95)

            # Применяем тот же multiplier к границам интервала
            multiplier = result.get('final_multiplier', 1.0)
            area = target.total_area

            fair_price_ci_lower = ci_lower_sqm * multiplier * area
            fair_price_ci_upper = ci_upper_sqm * multiplier * area
            fair_price_margin = (fair_price_ci_upper - fair_price_ci_lower) / 2

            result['confidence_interval_95'] = {
                'lower': fair_price_ci_lower,
                'upper': fair_price_ci_upper,
                'margin': fair_price_margin,
                'margin_percent': (fair_price_margin / result['fair_price_total'] * 100) if result['fair_price_total'] > 0 else 0,
                'description': f"{result['fair_price_total']:,.0f} ± {fair_price_margin:,.0f} ₽ (95% доверия)"
            }

            logger.info(
                f"Доверительный интервал 95%: "
                f"{fair_price_ci_lower:,.0f} - {fair_price_ci_upper:,.0f} ₽ "
                f"(±{fair_price_margin:,.0f} ₽)"
            )

        # Логирование справедливой цены
        if self.enable_tracking and self.property_log:
            self.property_log.adjustments = result.get('adjustments', {})
            self.property_log.fair_price_result = result

            # Логируем медианы
            if 'medians' in result:
                self._log_event(EventType.MARKET_STATS_CALCULATED,
                    f"Рассчитаны медианы по {len(result['medians'])} параметрам",
                    {'medians': result['medians']})

            # Логируем сравнение
            if 'comparison' in result:
                equals_count = sum(1 for c in result['comparison'].values() if c['equals_median'])
                differs_count = len(result['comparison']) - equals_count
                self._log_event(EventType.FAIR_PRICE_CALCULATED,
                    f"Сравнение: {equals_count} параметров = медиане, {differs_count} отличаются",
                    {'comparison_summary': {
                        'equals_median': equals_count,
                        'differs': differs_count
                    }})

            self._log_event(EventType.FAIR_PRICE_CALCULATED,
                f"Справедливая цена: {result['fair_price_total']:,.0f} ₽ (multiplier: {result['final_multiplier']:.4f})",
                {
                    'fair_price': result['fair_price_total'],
                    'current_price': result['current_price'],
                    'price_diff_percent': result['price_diff_percent'],
                    'is_overpriced': result['is_overpriced'],
                    'is_underpriced': result['is_underpriced']
                })

            # Логируем каждую корректировку
            for adj_name, adj_data in result.get('adjustments', {}).items():
                if isinstance(adj_data, dict):
                    self._log_event(EventType.ADJUSTMENT_APPLIED,
                        f"Применена корректировка: {adj_data.get('description', adj_name)}",
                        {'adjustment': adj_name, 'value': adj_data.get('value', 1.0)})

        return result

    def calculate_fair_price_old(self) -> Dict:
        """
        СТАРАЯ логика справедливой цены (оставлена для совместимости)

        ⚠️ УСТАРЕЛО: применяет коэффициенты ко ВСЕМ параметрам,
        даже если они совпадают с аналогами

        Returns:
            Словарь с расчетом справедливой цены
        """
        market_stats = self.calculate_market_statistics()

        if not market_stats or not self.request:
            return {}

        target = self.request.target_property

        # Используем МЕДИАНУ (более устойчива к выбросам)
        if self.request.use_median:
            base_price_per_sqm = market_stats['with_design']['median']
            if base_price_per_sqm == 0:
                base_price_per_sqm = market_stats['all']['median']
            method = 'median'
        else:
            base_price_per_sqm = market_stats['with_design']['mean']
            if base_price_per_sqm == 0:
                base_price_per_sqm = market_stats['all']['mean']
            method = 'mean'

        # Корректировки
        adjustments = {}
        multiplier = 1.0

        # === ПОЛОЖИТЕЛЬНЫЕ КОРРЕКТИРОВКИ ===

        # 1. Размер квартиры (ГЛАВНЫЙ КОЭФФИЦИЕНТ - применяется ВСЕГДА!)
        # Используем среднюю площадь аналогов для расчета коэффициента
        if target.total_area and self.filtered_comparables:
            avg_area = statistics.mean([c.total_area for c in self.filtered_comparables if c.total_area])
            if avg_area > 0:
                area_ratio = target.total_area / avg_area
                # Коэффициент площади: если больше средней - бонус до +5%, если меньше - штраф
                area_coef = 1 + (area_ratio - 1) * 0.10
                # Ограничиваем диапазон: от 0.90 до 1.10
                area_coef = max(0.90, min(area_coef, 1.10))
                adjustments['area'] = {'value': area_coef, 'description': f'Корректировка площади ({target.total_area:.1f} м² vs {avg_area:.1f} м² средняя)'}
                multiplier *= area_coef

        # 2. Дизайнерская отделка
        if target.has_design:
            adjustments['design'] = {'value': self.DESIGN_COEFFICIENT, 'description': 'Дизайнерская отделка'}
            multiplier *= self.DESIGN_COEFFICIENT

        # 3. Вид из окон
        if target.panoramic_views:
            adjustments['panoramic_views'] = {'value': self.PANORAMIC_VIEWS_COEFFICIENT, 'description': 'Панорамные виды'}
            multiplier *= self.PANORAMIC_VIEWS_COEFFICIENT

        # 4. Расстояние до метро
        if target.metro_distance_min:
            if target.metro_distance_min <= 7:
                # Бонус за близость к метро (до +6%)
                coef = 1 + (7 - target.metro_distance_min) / 7 * 0.06
                adjustments['metro_proximity'] = {'value': coef, 'description': f'Близко к метро ({target.metro_distance_min} мин)'}
                multiplier *= coef
            elif target.metro_distance_min > 15:
                # Штраф за удаленность от метро (до -10%)
                penalty = min((target.metro_distance_min - 15) / 30, 0.1)
                coef = 1 - penalty
                adjustments['metro_distance'] = {'value': coef, 'description': f'Далеко от метро ({target.metro_distance_min} мин)'}
                multiplier *= coef

        # 5. Премиум локация
        if target.premium_location:
            adjustments['premium_location'] = {'value': self.PREMIUM_LOCATION_COEFFICIENT, 'description': 'Премиум локация'}
            multiplier *= self.PREMIUM_LOCATION_COEFFICIENT

        # 6. Тип дома
        if target.house_type:
            if target.house_type == 'монолит':
                coef = 1.05
                adjustments['house_type'] = {'value': coef, 'description': 'Монолитный дом'}
                multiplier *= coef
            elif target.house_type == 'панель':
                coef = 0.95
                adjustments['house_type'] = {'value': coef, 'description': 'Панельный дом'}
                multiplier *= coef

        # 7. Парковка
        if target.parking:
            if target.parking == 'подземная':
                coef = 1.04
                adjustments['parking'] = {'value': coef, 'description': 'Подземная парковка'}
                multiplier *= coef
            elif target.parking == 'закрытая':
                coef = 1.03
                adjustments['parking'] = {'value': coef, 'description': 'Закрытая парковка'}
                multiplier *= coef

        # 8. Высота потолков
        if target.ceiling_height and target.ceiling_height >= 3.0:
            coef = 1 + (target.ceiling_height - 2.7) / 0.5 * 0.03
            adjustments['ceiling_height'] = {'value': coef, 'description': f'Высокие потолки ({target.ceiling_height} м)'}
            multiplier *= coef

        # 9. Охрана 24/7
        if target.security_247:
            coef = 1.03
            adjustments['security'] = {'value': coef, 'description': 'Охрана 24/7'}
            multiplier *= coef

        # 10. Лифт
        if target.has_elevator:
            coef = 1.03
            adjustments['elevator'] = {'value': coef, 'description': 'Наличие лифта'}
            multiplier *= coef

        # 11. Высокий процент жилой площади (БОНУС если жилая площадь > 50%)
        if target.living_area and target.total_area:
            living_percent = (target.living_area / target.total_area) * 100
            if living_percent > 50:
                # Бонус до +8% если жилая площадь составляет 70%+
                bonus_percent = min((living_percent - 50) / 20, 1.0)  # от 0 до 1
                coef = 1 + bonus_percent * 0.08
                adjustments['high_living_area'] = {'value': coef, 'description': f'Высокий процент жилой площади ({living_percent:.1f}%)'}
                multiplier *= coef

        # 12. Этаж (средние этажи лучше первого и последнего)
        if target.floor and target.total_floors and target.total_floors >= 5:
            floor_ratio = target.floor / target.total_floors
            # Оптимальный диапазон: 30-70% от высоты дома
            if 0.3 <= floor_ratio <= 0.7:
                # Бонус до +4% для средних этажей
                coef = 1.04
                adjustments['middle_floor'] = {'value': coef, 'description': f'Средний этаж ({target.floor}/{target.total_floors})'}
                multiplier *= coef
            elif floor_ratio < 0.15:  # Первые этажи
                coef = 0.97
                adjustments['low_floor'] = {'value': coef, 'description': f'Низкий этаж ({target.floor}/{target.total_floors})'}
                multiplier *= coef
            elif floor_ratio > 0.85:  # Последние этажи
                coef = 0.98
                adjustments['top_floor'] = {'value': coef, 'description': f'Верхний этаж ({target.floor}/{target.total_floors})'}
                multiplier *= coef

        # === НЕГАТИВНЫЕ КОРРЕКТИРОВКИ ===

        # 14. Низкий процент жилой площади (применяется только если НЕ был бонус)
        if target.living_area and target.total_area and 'high_living_area' not in adjustments:
            living_percent = (target.living_area / target.total_area) * 100
            if living_percent < 30:
                coef = 1 - (30 - living_percent) / 30 * 0.08
                coef = max(coef, 0.92)
                adjustments['low_living_area'] = {'value': coef, 'description': f'Низкий процент жилой площади ({living_percent:.1f}%)'}
                multiplier *= coef

        # 15. Количество спален (если заявлено больше, чем есть на самом деле)
        if target.rooms and target.living_area and target.total_area:
            # Если жилая площадь слишком мала для заявленного числа комнат
            expected_living_area = target.rooms * 12  # минимум 12 м² на комнату
            if target.living_area < expected_living_area:
                coef = 0.95  # штраф 5%
                adjustments['bedrooms_mismatch'] = {'value': coef, 'description': 'Несоответствие кол-ва комнат жилой площади'}
                multiplier *= coef

        # 16. Возраст дома
        if target.build_year:
            current_year = datetime.now().year
            age = current_year - target.build_year
            if age > 10:
                coef = 1 - (age - 10) / 100 * 0.05
                coef = max(coef, 0.95)
                adjustments['building_age'] = {'value': coef, 'description': f'Возраст дома ({age} лет)'}
                multiplier *= coef

        # 17. Неликвидность (очень высокая цена)
        if target.price and target.price > 150_000_000:
            coef = 0.96
            adjustments['high_price'] = {'value': coef, 'description': 'Очень высокая цена (низкая ликвидность)'}
            multiplier *= coef

        # 18. Рендеры вместо фото
        if target.renders_only:
            coef = 0.97
            adjustments['renders_only'] = {'value': coef, 'description': 'Только рендеры (нет реальных фото)'}
            multiplier *= coef

        # Валидация итогового multiplier (должен быть в разумных пределах)
        if multiplier < 0.7:
            logger.warning(f"Multiplier слишком низкий: {multiplier:.3f}, ограничен до 0.7")
            adjustments['multiplier_limit'] = {'value': 0.7 / multiplier, 'description': f'Ограничение слишком низкого multiplier ({multiplier:.3f} → 0.7)'}
            multiplier = 0.7
        elif multiplier > 1.4:
            logger.warning(f"Multiplier слишком высокий: {multiplier:.3f}, ограничен до 1.4")
            adjustments['multiplier_limit'] = {'value': 1.4 / multiplier, 'description': f'Ограничение слишком высокого multiplier ({multiplier:.3f} → 1.4)'}
            multiplier = 1.4

        fair_price_per_sqm = base_price_per_sqm * multiplier
        fair_price_total = fair_price_per_sqm * (target.total_area or 0)

        current_price = target.price or 0
        price_diff_amount = current_price - fair_price_total
        price_diff_percent = (price_diff_amount / fair_price_total * 100) if fair_price_total > 0 else 0

        # Определяем статус оценки
        is_overpriced = price_diff_percent > 5  # Переоценен более чем на 5%
        is_underpriced = price_diff_percent < -5  # Недооценен более чем на 5%
        is_fair = -5 <= price_diff_percent <= 5  # Справедливая цена (±5%)

        result = {
            'base_price_per_sqm': base_price_per_sqm,
            'adjustments': adjustments,
            'final_multiplier': multiplier,
            'fair_price_per_sqm': fair_price_per_sqm,
            'fair_price_total': fair_price_total,
            'current_price': current_price,
            'price_diff_amount': price_diff_amount,
            'price_diff_percent': price_diff_percent,
            'is_overpriced': is_overpriced,
            'is_underpriced': is_underpriced,
            'is_fair': is_fair,
            # Оставляем для обратной совместимости
            'overpricing_amount': price_diff_amount,
            'overpricing_percent': price_diff_percent,
            'method': method
        }

        # Логирование справедливой цены
        if self.enable_tracking and self.property_log:
            self.property_log.adjustments = adjustments
            self.property_log.fair_price_result = result
            self._log_event(EventType.FAIR_PRICE_CALCULATED,
                f"Справедливая цена: {fair_price_total:,.0f} ₽ (multiplier: {multiplier:.4f})",
                {
                    'fair_price': fair_price_total,
                    'current_price': current_price,
                    'price_diff_percent': price_diff_percent,
                    'is_overpriced': is_overpriced,
                    'is_underpriced': is_underpriced
                })

            # Логируем каждую корректировку
            for adj_name, adj_data in adjustments.items():
                if isinstance(adj_data, dict):
                    self._log_event(EventType.ADJUSTMENT_APPLIED,
                        f"Применена корректировка: {adj_data.get('description', adj_name)}",
                        {'adjustment': adj_name, 'value': adj_data.get('value', 1.0)})

        return result

    def generate_price_scenarios(self) -> List[PriceScenario]:
        """
        Генерация ценовых сценариев продажи

        Returns:
            Список сценариев
        """
        target = self.request.target_property
        current_price = target.price or 0
        fair_price_data = self.calculate_fair_price()
        fair_price = fair_price_data.get('fair_price_total', current_price)
        market_profile = self._build_market_profile()

        # ИСПРАВЛЕНО: Реалистичные сценарии с адекватным торгом (3-5%)
        scenarios_config = [
            {
                'name': 'Быстрая продажа',
                'type': 'fast',
                'description': 'Небольшой запас на торг для быстрой реализации (1-2 месяца)',
                'start_price_pct': 1.02,
                'expected_final_pct': 0.98,
                'time_months': 2,
                'base_probability': 85,
                'reduction_rate': 0.008
            },
            {
                'name': 'Оптимальная продажа',
                'type': 'optimal',
                'description': 'Рекомендуемая стратегия с балансом цены и времени (3-4 месяца)',
                'start_price_pct': 1.06,
                'expected_final_pct': 1.02,
                'time_months': 4,
                'base_probability': 75,
                'reduction_rate': 0.010
            },
            {
                'name': 'Стандартная продажа',
                'type': 'standard',
                'description': 'Средние сроки с умеренным торгом (5-6 месяцев)',
                'start_price_pct': 1.08,
                'expected_final_pct': 1.01,
                'time_months': 6,
                'base_probability': 65,
                'reduction_rate': 0.012
            },
            {
                'name': 'Попытка максимума',
                'type': 'maximum',
                'description': 'Ставка на максимальную цену (9-12 месяцев, высокий риск)',
                'start_price_pct': 1.15,
                'expected_final_pct': 0.97,
                'time_months': 10,
                'base_probability': 30,
                'reduction_rate': 0.020
            }
        ]

        price_multiplier = market_profile.get('pricing_bias', 1.0)
        probability_multiplier = market_profile.get('probability_multiplier', 1.0)
        time_multiplier = market_profile.get('time_multiplier', 1.0)
        reduction_multiplier = market_profile.get('price_pressure_multiplier', 1.0)
        segment_label = market_profile.get('segment_label')

        scenarios = []
        for config in scenarios_config:
            adaptive_config = config.copy()
            start_price = fair_price * adaptive_config.pop('start_price_pct') * price_multiplier
            expected_price = fair_price * adaptive_config.pop('expected_final_pct') * price_multiplier
            time_months = max(1, round(adaptive_config['time_months'] * time_multiplier))
            base_probability = max(5, min(95, adaptive_config['base_probability'] * probability_multiplier))
            reduction_rate = max(0.004, adaptive_config['reduction_rate'] * reduction_multiplier)

            adaptive_config.update({
                'start_price': start_price,
                'expected_final_price': expected_price,
                'time_months': time_months,
                'base_probability': round(base_probability, 1),
                'reduction_rate': reduction_rate
            })

            if segment_label:
                adaptive_config['description'] = (
                    f"{adaptive_config['description']} — сегмент: {segment_label}."
                )

            scenario = PriceScenario(**adaptive_config)

            # Траектория цен
            scenario.price_trajectory = self._calculate_price_trajectory(
                scenario.start_price,
                scenario.reduction_rate,
                14
            )

            # Месячная вероятность
            scenario.monthly_probability = self._calculate_monthly_probability(
                scenario.type,
                fair_price,
                scenario.start_price
            )

            # Кумулятивная вероятность
            scenario.cumulative_probability = self._calculate_cumulative_probability(
                scenario.monthly_probability
            )

            # Финансовый расчет с вероятностью
            tax_context = self._get_tax_context(scenario.expected_final_price)
            opportunity_context = self._get_opportunity_context(scenario.time_months)
            scenario.financials = self._calculate_financials(
                scenario.expected_final_price,
                scenario.time_months,
                base_probability=scenario.base_probability,
                tax_rate=tax_context['tax_rate'],
                tax_base=tax_context['tax_base'],
                tax_note=tax_context['note'],
                tax_holding_years=tax_context['holding_years'],
                opportunity_rate=opportunity_context['rate'],
                opportunity_note=opportunity_context['note'],
                opportunity_metadata=opportunity_context['metadata']
            )

            scenarios.append(scenario)

        # НОВОЕ: Автоматический выбор оптимального сценария по максимальному ожидаемому доходу
        best_scenario = max(scenarios, key=lambda s: s.financials.get('expected_value', 0))
        best_scenario_index = scenarios.index(best_scenario)

        # Добавляем флаг "рекомендуется" к лучшему сценарию
        for i, scenario in enumerate(scenarios):
            scenario.is_recommended = (i == best_scenario_index)
            # Обновляем описание для рекомендуемого сценария
            if scenario.is_recommended:
                scenario.description = f"⭐ РЕКОМЕНДУЕТСЯ: {scenario.description}"
                scenario.recommendation_reason = (
                    f"Этот сценарий даёт максимальный ожидаемый доход "
                    f"{scenario.financials.get('expected_value', 0):,.0f} ₽ с учётом вероятности продажи. "
                    f"Математически это лучший выбор."
                )

        # Логирование сценариев
        if self.enable_tracking and self.property_log:
            self.property_log.scenarios = [
                {
                    'name': s.name,
                    'type': s.type,
                    'start_price': s.start_price,
                    'expected_final_price': s.expected_final_price,
                    'time_months': s.time_months,
                    'financials': s.financials
                }
                for s in scenarios
            ]
            self._log_event(EventType.SCENARIOS_GENERATED,
                f"Сгенерировано {len(scenarios)} сценариев продажи")

        return scenarios

    def _build_market_profile(self) -> Dict[str, Any]:
        """Строит профиль ликвидности и кеширует его для анализа."""
        if self.market_profile:
            return self.market_profile

        try:
            profile = build_liquidity_profile(self.request.target_property, self.filtered_comparables)
        except Exception as exc:  # pragma: no cover - защитный код
            logger.warning("Не удалось построить профиль ликвидности: %s", exc)
            profile = {
                'segment': 'unknown',
                'segment_label': 'неопределённый сегмент',
                'liquidity_score': 1.0,
                'probability_multiplier': 1.0,
                'time_multiplier': 1.0,
                'pricing_bias': 1.0,
                'price_pressure_multiplier': 1.0,
                'expected_dom_months': 4,
                'notes': []
            }

        self.market_profile = profile

        if self.enable_tracking and self.property_log:
            self.property_log.market_profile = profile

        return profile

    def _calculate_price_trajectory(self, start_price: float, reduction_rate: float, months: int = 14) -> List[Dict]:
        """Расчет траектории цены"""
        trajectory = []
        for month in range(months):
            price = start_price * math.pow(1 - reduction_rate, month)
            trajectory.append({
                'month': month,
                'price': price
            })
        return trajectory

    def _calculate_monthly_probability(self, scenario_type: str, fair_price: float, start_price: float) -> List[float]:
        """Расчет месячной вероятности продажи"""
        price_ratio = start_price / fair_price if fair_price > 0 else 1.0

        if scenario_type == 'fast':
            base_prob = [0.45, 0.70, 0.75, 0.75, 0.73, 0.70, 0.68, 0.65, 0.62, 0.60, 0.58, 0.55, 0.53, 0.50]
        elif scenario_type == 'optimal':
            base_prob = [0.40, 0.65, 0.70, 0.72, 0.70, 0.68, 0.65, 0.62, 0.60, 0.57, 0.55, 0.52, 0.50, 0.48]
        elif scenario_type == 'standard':
            base_prob = [0.35, 0.55, 0.60, 0.65, 0.63, 0.60, 0.57, 0.54, 0.51, 0.48, 0.45, 0.42, 0.40, 0.38]
        elif scenario_type == 'maximum':
            base_prob = [0.15, 0.20, 0.20, 0.18, 0.15, 0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.05, 0.04, 0.04]
        else:
            base_prob = [0.50] * 14

        # Корректировка по отклонению цены
        if price_ratio > 1.1:
            adjustment = 0.7
        elif price_ratio > 1.05:
            adjustment = 0.85
        elif price_ratio < 0.95:
            adjustment = 1.15
        else:
            adjustment = 1.0

        return [min(p * adjustment, 0.98) for p in base_prob]

    def _calculate_cumulative_probability(self, monthly_probabilities: List[float]) -> List[float]:
        """Расчет кумулятивной вероятности"""
        cumulative = []
        remaining = 1.0

        for p in monthly_probabilities:
            cumulative_p = 1 - (remaining * (1 - p))
            cumulative.append(cumulative_p)
            remaining *= (1 - p)

        return cumulative

    def _get_opportunity_context(self, months_waited: int) -> Dict[str, Any]:
        """Получить ставку упущенной выгоды и пояснение из рыночных данных."""
        default_rate = 0.08
        base_note = (
            f'Упущенная выгода {default_rate * 100:.1f}% годовых за {months_waited} мес '
            f'(фиксированное допущение).'
        )
        metadata = {
            'source': 'internal_default',
            'updated_at': None,
            'key_rate_percent': None,
            'spread_percent': None
        }

        if not self.market_rates_service:
            return {'rate': default_rate, 'note': base_note, 'metadata': metadata}

        market_info = self.market_rates_service.get_opportunity_rate()
        rate = market_info.get('rate', default_rate)
        metadata.update({
            'source': market_info.get('source'),
            'updated_at': market_info.get('timestamp'),
            'key_rate_percent': market_info.get('key_rate_percent'),
            'spread_percent': market_info.get('spread_percent')
        })

        timestamp = market_info.get('timestamp')
        if timestamp:
            try:
                updated_dt = datetime.fromisoformat(timestamp)
                updated_text = updated_dt.strftime('%d.%m.%Y')
            except ValueError:
                updated_text = timestamp
        else:
            updated_text = 'ранее'

        key_rate_percent = market_info.get('key_rate_percent')
        spread_percent = market_info.get('spread_percent')

        if key_rate_percent is not None:
            note = (
                f"Ставка упущенной выгоды = ключевая ставка ЦБ {key_rate_percent:.2f}% + "
                f"{spread_percent:.1f} п.п. (депозиты/ОФЗ) = {rate * 100:.2f}% годовых. "
                f"Данные обновлены {updated_text}, расчёт для ожидания {months_waited} мес."
            )
        else:
            note = base_note

        return {'rate': rate, 'note': note, 'metadata': metadata}

    def _get_tax_context(self, sale_price: float) -> Dict[str, Any]:
        """Определить ставку и базу НДФЛ исходя из срока владения и цены покупки."""
        target = getattr(self.request, 'target_property', None)
        default_context = {
            'tax_rate': 0.0,
            'tax_base': 0.0,
            'note': 'Нет данных о покупке — налог не удержан.',
            'holding_years': None
        }

        if not target:
            return default_context

        purchase_date = getattr(target, 'purchase_date', None)
        purchase_price = getattr(target, 'purchase_price', None)
        owner_residency = (getattr(target, 'owner_residency', 'resident') or 'resident').lower()
        primary_residence = bool(getattr(target, 'primary_residence', False))

        if not purchase_date:
            return default_context

        holding_years = (datetime.now() - purchase_date).days / 365.25
        min_period = 3 if primary_residence else 5

        if holding_years >= min_period:
            return {
                'tax_rate': 0.0,
                'tax_base': 0.0,
                'note': (
                    f'Владение {holding_years:.1f} лет ≥ {min_period} лет — налоговая льгота, '
                    'НДФЛ не удерживается.'
                ),
                'holding_years': holding_years
            }

        tax_rate = 0.30 if owner_residency == 'non_resident' else 0.13
        fallback_purchase = sale_price * 0.7
        effective_purchase_price = purchase_price or fallback_purchase
        profit_base = max(sale_price - effective_purchase_price, 0)

        if profit_base <= 0:
            note = (
                f'Срок владения {holding_years:.1f} года, но прибыли нет — налог не удержан.'
            )
            return {
                'tax_rate': 0.0,
                'tax_base': 0.0,
                'note': note,
                'holding_years': holding_years
            }

        note_parts = [
            f'Срок владения {holding_years:.1f} года (< {min_period} лет).',
            f"Ставка НДФЛ {'30' if owner_residency == 'non_resident' else '13'}%."
        ]
        if not purchase_price:
            note_parts.append('Нет цены покупки — использовано 70% от цены продажи (кадастровый минимум).')

        note = ' '.join(note_parts)

        return {
            'tax_rate': tax_rate,
            'tax_base': profit_base,
            'note': note,
            'holding_years': holding_years
        }

    def _calculate_financials(
        self,
        sale_price: float,
        months_waited: int,
        base_probability: float = 0.0,  # НОВОЕ: вероятность продажи для расчета expected value
        commission_rate: float = 0.02,
        tax_rate: float = 0.00,  # ИСПРАВЛЕНО: По умолчанию 0% (предполагаем владение > 5 лет)
        tax_base: float = None,
        tax_note: str = 'Налог 0% при владении > 5 лет или единственное жилье',
        tax_holding_years: float = None,
        other_expenses: float = 0.001,  # ИСПРАВЛЕНО: 0.1% вместо 1% (реалистичные расходы ~150 тыс)
        opportunity_rate: float = 0.08,
        opportunity_note: str = None,
        opportunity_metadata: Dict[str, Any] = None
    ) -> Dict:
        """
        Финансовый расчет с корректными налогами и расходами

        ИСПРАВЛЕНИЯ:
        - tax_rate = 0% (предполагаем владение > 5 лет или единственное жилье)
        - other_expenses = 0.1% (~150 тыс: юрист, регистрация, оценка)
        - НОВОЕ: Добавлен расчет ожидаемого дохода (expected_value)

        Если нужно учесть налог:
        - Только если владели < 5 лет
        - Только с прибыли (продажа - покупка), а не со всей суммы!
        """
        commission = sale_price * commission_rate
        tax_base_amount = sale_price if tax_base is None else max(tax_base, 0)
        taxes = tax_base_amount * tax_rate  # 0% по умолчанию или считанный профит
        other = sale_price * other_expenses  # 0.1% (~150 тыс)
        opportunity_cost = sale_price * opportunity_rate * (months_waited / 12)

        net_income = sale_price - commission - taxes - other
        net_after_opportunity = net_income - opportunity_cost

        effective_yield = (net_after_opportunity / sale_price * 100) if sale_price > 0 else 0

        # НОВОЕ: Расчет ожидаемого дохода (expected value)
        # Учитывает вероятность продажи: expected_value = net_after_opportunity × probability
        expected_value = net_after_opportunity * (base_probability / 100.0) if base_probability > 0 else 0

        return {
            'gross_price': sale_price,
            'commission': commission,
            'commission_rate_percent': commission_rate * 100,
            'taxes': taxes,
            'tax_rate_percent': tax_rate * 100,
            'tax_base': tax_base_amount,
            'tax_note': tax_note,
            'tax_holding_years': tax_holding_years,
            'other_expenses': other,
            'other_expenses_note': 'Юрист, регистрация, оценка (~150 тыс ₽)',
            'opportunity_cost': opportunity_cost,
            'opportunity_note': opportunity_note or (
                f'Упущенная выгода {opportunity_rate*100:.0f}% годовых за {months_waited} мес'
            ),
            'opportunity_metadata': opportunity_metadata or {},
            'opportunity_rate': opportunity_rate,
            'opportunity_explanation': (
                f'Упущенная выгода — это деньги, которые вы могли бы заработать, '
                f'инвестируя {sale_price:,.0f} ₽ под {opportunity_rate*100:.0f}% годовых '
                f'в течение {months_waited} месяцев вместо ожидания продажи. '
                f'Например, в облигации, депозит или недвижимость.'
            ),
            'net_income': net_income,
            'net_income_note': 'Чистый доход после всех расходов (комиссия, налоги, прочее)',
            'net_after_opportunity': net_after_opportunity,
            'net_after_opportunity_note': (
                'Чистый доход с учетом упущенной выгоды — реальная выгода от продажи. '
                'Это та сумма, которую вы получите "на руки" после вычета всех расходов '
                'и альтернативной стоимости ожидания.'
            ),
            'expected_value': expected_value,
            'expected_value_note': (
                f'Ожидаемый доход = {net_after_opportunity:,.0f} ₽ × {base_probability}% вероятность = '
                f'{expected_value:,.0f} ₽. Это математическое ожидание — реальная выгода '
                f'с учетом риска не продать.'
            ),
            'effective_yield': effective_yield,
            'months_waited': months_waited
        }

    def calculate_strengths_weaknesses(self) -> Dict:
        """
        Рассчитать сильные и слабые стороны НА ОСНОВЕ РЕАЛЬНЫХ КОЭФФИЦИЕНТОВ

        НОВАЯ ЛОГИКА (после исправления):
        - Берем примененные коэффициенты из расчета справедливой цены
        - Показываем только ЗНАЧИМЫЕ отклонения (>5% от медианы)
        - Все сравнивается с МЕДИАНОЙ аналогов, а не с абсолютными значениями
        - Исключены абсурдные факторы типа "премиум локация" (все аналоги в той же локации!)

        Returns:
            Словарь с сильными/слабыми сторонами
        """
        strengths = []
        weaknesses = []

        # Получаем примененные коэффициенты из расчета
        if not hasattr(self, 'fair_price_result') or not self.fair_price_result:
            # Fallback: если нет результата расчета, возвращаем пустое
            return {
                'strengths': [],
                'weaknesses': [],
                'total_premium_percent': 0,
                'total_discount_percent': 0,
                'net_adjustment': 0
            }

        adjustments = self.fair_price_result.get('adjustments', {})

        # Порог значимости: показываем только коэффициенты с отклонением >5%
        THRESHOLD = 0.05

        # Человекочитаемые названия параметров
        FACTOR_NAMES = {
            'floor': 'Этаж',
            'total_area': 'Площадь квартиры',
            'repair_level': 'Уровень ремонта',
            'ceiling_height': 'Высота потолков',
            'window_type': 'Тип окон',
            'view_type': 'Вид из окон',
            'elevator_count': 'Количество лифтов',
            'living_area_percent': 'Процент жилой площади',
            'bathrooms': 'Количество санузлов',
            'photo_type': 'Качество фотографий',
            'object_status': 'Статус объекта',
            'build_year': 'Возраст дома',
            # НОВЫЕ ПОЛЯ (2025-01-12)
            'material_quality': 'Качество материалов',
            'ownership_status': 'Статус собственности'
        }

        # Анализируем каждый коэффициент
        for factor_key, adjustment_info in adjustments.items():
            if not isinstance(adjustment_info, dict):
                continue

            coef = adjustment_info.get('value', 1.0)
            description = adjustment_info.get('description', '')
            adj_type = adjustment_info.get('type', 'fixed')

            # Пропускаем коэффициенты близкие к 1.0 (незначимые)
            if 1.0 - THRESHOLD <= coef <= 1.0 + THRESHOLD:
                continue

            # Рассчитываем процентное отклонение
            percent_diff = (coef - 1.0) * 100
            abs_percent = abs(percent_diff)

            # Название фактора
            factor_name = FACTOR_NAMES.get(factor_key, factor_key.replace('_', ' ').title())

            # Добавляем маркер адаптивного коэффициента
            if adj_type == 'adaptive':
                factor_name = f"✨ {factor_name}"

            # Формируем описание
            item = {
                'factor': factor_name,
                'impact': min(10, int(abs_percent)),
                'description': description
            }

            # Добавляем в strengths или weaknesses
            if coef > 1.0:
                # Премия - округляем до 2 знаков
                item['premium_percent'] = round(abs_percent, 2)
                strengths.append(item)
            else:
                # Скидка - округляем до 2 знаков
                item['discount_percent'] = round(abs_percent, 2)
                weaknesses.append(item)

        # Сортируем по значимости (больше процент = важнее)
        strengths.sort(key=lambda x: x['premium_percent'], reverse=True)
        weaknesses.sort(key=lambda x: x['discount_percent'], reverse=True)

        # Ограничиваем топ-5 для удобства восприятия
        strengths = strengths[:5]
        weaknesses = weaknesses[:5]

        total_premium = sum(s['premium_percent'] for s in strengths)
        total_discount = sum(w['discount_percent'] for w in weaknesses)

        return {
            'strengths': strengths,
            'weaknesses': weaknesses,
            'total_premium_percent': round(total_premium, 2),
            'total_discount_percent': round(total_discount, 2),
            'net_adjustment': round(total_premium - total_discount, 2)
        }

    def generate_comparison_chart_data(self) -> Dict:
        """Генерация данных для графика сравнения"""
        target = self.request.target_property
        all_properties = [target] + self.filtered_comparables

        labels = []
        prices_per_sqm = []
        colors = []

        for i, prop in enumerate(all_properties):
            if i == 0:
                labels.append('ЦЕЛЕВОЙ')
                colors.append('rgba(255, 99, 132, 0.8)')
            else:
                label = f"{prop.rooms or '?'}-комн {prop.total_area or '?'}м²"
                labels.append(label)

                if prop.has_design:
                    colors.append('rgba(75, 192, 192, 0.8)')
                else:
                    colors.append('rgba(201, 203, 207, 0.8)')

            prices_per_sqm.append((prop.price_per_sqm or 0) / 1_000_000)

        return {
            'labels': labels,
            'datasets': [{
                'label': 'Цена за м² (млн ₽)',
                'data': prices_per_sqm,
                'backgroundColor': colors,
                'borderColor': [c.replace('0.8', '1') for c in colors],
                'borderWidth': 2
            }]
        }

    def generate_box_plot_data(self) -> Dict:
        """Генерация данных для box-plot"""
        prices = [
            c.price_per_sqm / 1_000_000
            for c in self.filtered_comparables
            if c.price_per_sqm
        ]

        if not prices:
            return {}

        prices.sort()
        n = len(prices)

        q1_index = n // 4
        n // 2
        q3_index = 3 * n // 4

        target = self.request.target_property

        return {
            'min': min(prices),
            'q1': prices[q1_index] if q1_index < n else prices[0],
            'median': statistics.median(prices),
            'q3': prices[q3_index] if q3_index < n else prices[-1],
            'max': max(prices),
            'target': (target.price_per_sqm or 0) / 1_000_000
        }

    def get_metrics(self) -> Dict:
        """Получить метрики производительности"""
        return self.metrics.copy()

    def _log_event(self, event_type: EventType, message: str, details: Dict = None):
        """Добавить событие в лог (если трекинг включен)"""
        if self.enable_tracking and self.property_log:
            self.property_log.add_event(event_type, message, details or {})
