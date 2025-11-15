"""
Детектор дубликатов объявлений недвижимости

Определяет одинаковые объекты, размещенные на разных площадках.
Проблема: один и тот же объект может быть на ЦИАН, Авито, Яндекс с разными ценами.

Алгоритм:
1. Строгий дубликат (100%) - адрес, площадь, комнаты, этаж идентичны, цена ±2%
2. Вероятный дубликат (90-99%) - то же самое, но цена ±10%
3. Возможный дубликат (70-90%) - похожий адрес, площадь ±1м², цена ±15%

Использование:
    >>> detector = DuplicateDetector()
    >>> is_dup, score = detector.is_duplicate(obj1, obj2)
    >>> duplicates = detector.find_duplicates(property_obj, comparables_list)
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """
    Информация о найденном дубликате

    Attributes:
        index: Индекс объекта в списке аналогов
        confidence: Уверенность в дубликате (0-100%)
        duplicate_type: Тип дубликата ('strict', 'probable', 'possible')
        differences: Словарь отличий {field: (value1, value2)}
        recommendation: Рекомендация действия ('skip', 'warn', 'keep')
    """
    index: int
    confidence: float
    duplicate_type: str
    differences: Dict[str, Tuple]
    recommendation: str

    def to_dict(self):
        """Преобразование в словарь для JSON"""
        return {
            'index': self.index,
            'confidence': self.confidence,
            'type': self.duplicate_type,
            'differences': {k: {'current': v[0], 'existing': v[1]} for k, v in self.differences.items()},
            'recommendation': self.recommendation
        }


class DuplicateDetector:
    """
    Детектор дубликатов объявлений недвижимости

    Сравнивает объекты по ключевым параметрам и определяет вероятность дубликата.
    """

    def __init__(
        self,
        strict_price_tolerance: float = 0.02,     # ±2% для строгого дубликата
        probable_price_tolerance: float = 0.10,   # ±10% для вероятного
        possible_price_tolerance: float = 0.15,   # ±15% для возможного
        area_tolerance: float = 0.5,              # ±0.5 м² погрешность измерения
        possible_area_tolerance: float = 1.0      # ±1 м² для возможного дубликата
    ):
        self.strict_price_tolerance = strict_price_tolerance
        self.probable_price_tolerance = probable_price_tolerance
        self.possible_price_tolerance = possible_price_tolerance
        self.area_tolerance = area_tolerance
        self.possible_area_tolerance = possible_area_tolerance

    def normalize_address(self, address: str) -> str:
        """
        Нормализация адреса для сравнения

        Убирает аббревиатуры, приводит к нижнему регистру, убирает лишние пробелы

        Args:
            address: Исходный адрес

        Returns:
            Нормализованный адрес
        """
        if not address:
            return ""

        # Приводим к нижнему регистру
        normalized = address.lower()

        # Убираем стандартные аббревиатуры
        replacements = {
            r'\bг\.?\s*': '',           # г. Санкт-Петербург → Санкт-Петербург
            r'\bул\.?\s*': '',          # ул. Ленина → Ленина
            r'\bд\.?\s*': 'дом ',       # д. 10 → дом 10
            r'\bк\.?\s*': 'корпус ',    # к. 2 → корпус 2
            r'\bстр\.?\s*': 'строение ',
            r'\bпр\.?\s*': 'проспект ',
            r'\bпер\.?\s*': 'переулок ',
            r'\bш\.?\s*': 'шоссе ',
            r'\bпл\.?\s*': 'площадь ',
            r'\bб-р\.?\s*': 'бульвар ',
            r'\bнаб\.?\s*': 'набережная ',
        }

        for pattern, replacement in replacements.items():
            normalized = re.sub(pattern, replacement, normalized)

        # Убираем лишние пробелы
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def extract_address_components(self, address: str) -> Dict[str, str]:
        """
        Извлечение компонентов адреса

        Args:
            address: Адрес

        Returns:
            Словарь {street, house, corpus, etc.}
        """
        normalized = self.normalize_address(address)

        components = {
            'full': normalized,
            'street': '',
            'house': '',
            'corpus': '',
        }

        # Извлекаем номер дома (первая цифра)
        house_match = re.search(r'\b(\d+[а-яa-z]?)\b', normalized)
        if house_match:
            components['house'] = house_match.group(1)

        # Извлекаем корпус
        corpus_match = re.search(r'корпус\s+(\d+)', normalized)
        if corpus_match:
            components['corpus'] = corpus_match.group(1)

        # Улица - все до первой цифры
        if house_match:
            components['street'] = normalized[:house_match.start()].strip()
        else:
            components['street'] = normalized

        return components

    def compare_addresses(self, addr1: str, addr2: str) -> float:
        """
        Сравнение адресов с учетом нормализации

        Args:
            addr1: Первый адрес
            addr2: Второй адрес

        Returns:
            Оценка совпадения 0-100%
        """
        if not addr1 or not addr2:
            return 0.0

        comp1 = self.extract_address_components(addr1)
        comp2 = self.extract_address_components(addr2)

        # Улица и дом ДОЛЖНЫ совпадать
        if comp1['street'] != comp2['street']:
            # Пытаемся найти общую часть
            if comp1['street'] in comp2['street'] or comp2['street'] in comp1['street']:
                street_match = 0.8
            else:
                return 0.0  # Разные улицы - точно не дубликат
        else:
            street_match = 1.0

        if comp1['house'] != comp2['house']:
            return 0.0  # Разные дома - точно не дубликат

        # Корпус может отличаться (разные подъезды)
        if comp1['corpus'] and comp2['corpus']:
            corpus_match = 1.0 if comp1['corpus'] == comp2['corpus'] else 0.5
        else:
            corpus_match = 0.8  # Один не указан

        # Итоговая оценка
        score = (street_match * 0.6 + corpus_match * 0.4) * 100
        return score

    def compare_areas(self, area1: float, area2: float, strict: bool = True) -> bool:
        """
        Сравнение площадей с учетом погрешности

        Args:
            area1: Первая площадь
            area2: Вторая площадь
            strict: Строгое сравнение (±0.5) или мягкое (±1.0)

        Returns:
            True если площади совпадают в пределах погрешности
        """
        if not area1 or not area2:
            return False

        tolerance = self.area_tolerance if strict else self.possible_area_tolerance
        return abs(area1 - area2) <= tolerance

    def compare_prices(self, price1: float, price2: float) -> Tuple[bool, float]:
        """
        Сравнение цен с разной степенью толерантности

        Args:
            price1: Первая цена
            price2: Вторая цена

        Returns:
            (совпадают_ли, процент_отличия)
        """
        if not price1 or not price2:
            return False, 100.0

        diff_percent = abs(price1 - price2) / min(price1, price2)

        return diff_percent <= self.possible_price_tolerance, diff_percent

    def extract_floor(self, floor_str: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Извлечение этажа и этажности из строки

        Args:
            floor_str: Строка вида "5/10" или "5 из 10" или "5"

        Returns:
            (этаж, этажность) или (None, None)
        """
        if not floor_str:
            return None, None

        # Пытаемся найти паттерн "число/число" или "число из число"
        match = re.search(r'(\d+)\s*[/из]\s*(\d+)', str(floor_str))
        if match:
            return int(match.group(1)), int(match.group(2))

        # Только число
        match = re.search(r'(\d+)', str(floor_str))
        if match:
            return int(match.group(1)), None

        return None, None

    def is_duplicate(
        self,
        obj1: Dict,
        obj2: Dict,
        check_source: bool = True
    ) -> Tuple[bool, float, str, Dict]:
        """
        Проверка двух объектов на дубликат

        Args:
            obj1: Первый объект
            obj2: Второй объект
            check_source: Проверять ли разные источники (если False, считаем дубликатом только из разных источников)

        Returns:
            (is_duplicate, confidence, duplicate_type, differences)
        """
        # Если это один и тот же источник И одинаковый URL - пропускаем
        if check_source and obj1.get('source') == obj2.get('source'):
            if obj1.get('url') == obj2.get('url'):
                return True, 100.0, 'exact', {}

        differences = {}

        # 1. Сравнение адресов (критично)
        address_score = self.compare_addresses(
            obj1.get('address', ''),
            obj2.get('address', '')
        )

        if address_score < 80.0:
            return False, 0.0, 'not_duplicate', {}

        # 2. Сравнение площади (критично)
        area1 = obj1.get('total_area') or obj1.get('area')
        area2 = obj2.get('total_area') or obj2.get('area')

        # Пытаемся извлечь число из строки если нужно
        if isinstance(area1, str):
            match = re.search(r'(\d+(?:\.\d+)?)', area1)
            area1 = float(match.group(1)) if match else None
        if isinstance(area2, str):
            match = re.search(r'(\d+(?:\.\d+)?)', area2)
            area2 = float(match.group(1)) if match else None

        if not self.compare_areas(area1, area2, strict=False):
            return False, 0.0, 'not_duplicate', {}

        strict_area = self.compare_areas(area1, area2, strict=True)
        if not strict_area:
            differences['area'] = (area1, area2)

        # 3. Сравнение комнат (критично)
        rooms1 = str(obj1.get('rooms', '')).strip()
        rooms2 = str(obj2.get('rooms', '')).strip()

        if rooms1 != rooms2:
            # Разное количество комнат - не дубликат
            return False, 0.0, 'not_duplicate', {}

        # 4. Сравнение этажа (важно)
        floor1, floors1 = self.extract_floor(obj1.get('floor', ''))
        floor2, floors2 = self.extract_floor(obj2.get('floor', ''))

        if floor1 and floor2 and floor1 != floor2:
            # Разные этажи - скорее всего не дубликат
            return False, 0.0, 'not_duplicate', {}

        if floors1 and floors2 and floors1 != floors2:
            differences['floors'] = (floors1, floors2)

        # 5. Сравнение цены (может отличаться!)
        price1 = obj1.get('price_raw') or obj1.get('price')
        price2 = obj2.get('price_raw') or obj2.get('price')

        if isinstance(price1, str):
            match = re.search(r'(\d+(?:\s*\d+)*)', price1.replace(' ', ''))
            price1 = float(match.group(1)) if match else None
        if isinstance(price2, str):
            match = re.search(r'(\d+(?:\s*\d+)*)', price2.replace(' ', ''))
            price2 = float(match.group(1)) if match else None

        price_match, price_diff = self.compare_prices(price1, price2)
        if not price_match:
            differences['price'] = (price1, price2)

        # Определяем тип дубликата и confidence
        if address_score >= 95 and strict_area and price_diff <= self.strict_price_tolerance:
            # Строгий дубликат (100%)
            return True, 100.0, 'strict', differences

        elif address_score >= 90 and strict_area and price_diff <= self.probable_price_tolerance:
            # Вероятный дубликат (90-99%)
            confidence = 90 + (10 * (1 - price_diff / self.probable_price_tolerance))
            return True, confidence, 'probable', differences

        elif address_score >= 80 and price_diff <= self.possible_price_tolerance:
            # Возможный дубликат (70-90%)
            confidence = 70 + (20 * address_score / 100)
            return True, confidence, 'possible', differences

        return False, 0.0, 'not_duplicate', {}

    def find_duplicates(
        self,
        new_obj: Dict,
        existing_objects: List[Dict]
    ) -> List[DuplicateMatch]:
        """
        Поиск дубликатов нового объекта среди существующих

        Args:
            new_obj: Новый объект для проверки
            existing_objects: Список существующих объектов

        Returns:
            Список найденных дубликатов с информацией
        """
        duplicates = []

        for idx, existing_obj in enumerate(existing_objects):
            is_dup, confidence, dup_type, differences = self.is_duplicate(new_obj, existing_obj)

            if is_dup:
                # Определяем рекомендацию
                if dup_type == 'strict':
                    recommendation = 'skip'  # НЕ добавлять
                elif dup_type == 'probable':
                    recommendation = 'warn'  # Предупредить пользователя
                else:
                    recommendation = 'keep'  # Добавить, но с меткой

                match = DuplicateMatch(
                    index=idx,
                    confidence=confidence,
                    duplicate_type=dup_type,
                    differences=differences,
                    recommendation=recommendation
                )
                duplicates.append(match)

                logger.info(
                    f"Найден дубликат: {dup_type} (confidence: {confidence:.1f}%), "
                    f"отличия: {list(differences.keys())}"
                )

        return duplicates

    def deduplicate_list(
        self,
        objects: List[Dict],
        keep_best_price: bool = True
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Удаление дубликатов из списка объектов

        Стратегия: оставляем объект с лучшей ценой среди дубликатов

        Args:
            objects: Список объектов
            keep_best_price: Оставлять объект с лучшей (минимальной) ценой

        Returns:
            (уникальные_объекты, удаленные_дубликаты)
        """
        unique_objects = []
        removed_duplicates = []

        for obj in objects:
            # Ищем дубликаты среди уже добавленных уникальных
            duplicates = self.find_duplicates(obj, unique_objects)

            if not duplicates:
                # Нет дубликатов - добавляем
                unique_objects.append(obj)
            else:
                # Есть дубликаты
                strict_duplicates = [d for d in duplicates if d.duplicate_type == 'strict']

                if strict_duplicates:
                    # Строгий дубликат найден
                    strict_dup = strict_duplicates[0]
                    existing_obj = unique_objects[strict_dup.index]

                    if keep_best_price:
                        # Сравниваем цены
                        new_price = obj.get('price_raw') or obj.get('price') or float('inf')
                        existing_price = existing_obj.get('price_raw') or existing_obj.get('price') or float('inf')

                        if new_price < existing_price:
                            # Новый объект дешевле - заменяем
                            logger.info(f"Заменяем дубликат на объект с лучшей ценой: {new_price} < {existing_price}")
                            removed_duplicates.append(existing_obj)
                            unique_objects[strict_dup.index] = obj
                        else:
                            # Оставляем старый
                            logger.info(f"Пропускаем дубликат, существующий дешевле: {existing_price} <= {new_price}")
                            removed_duplicates.append(obj)
                    else:
                        # Просто пропускаем новый
                        removed_duplicates.append(obj)
                else:
                    # Только вероятные/возможные дубликаты - добавляем с меткой
                    obj['possible_duplicate'] = True
                    obj['duplicate_info'] = duplicates[0].to_dict()
                    unique_objects.append(obj)

        logger.info(f"Дедупликация: было {len(objects)}, осталось {len(unique_objects)}, удалено {len(removed_duplicates)}")

        return unique_objects, removed_duplicates
