"""
PostgreSQL Manager для хранения исторических данных анализа недвижимости
Поддерживает сохранение всех анализов, метрики, тренды
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    from psycopg2.pool import SimpleConnectionPool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

logger = logging.getLogger(__name__)


class PostgresManager:
    """
    Менеджер для работы с PostgreSQL

    Features:
    - Connection pooling
    - Автоматическое создание схемы
    - Сохранение анализов
    - Историческая статистика
    - Тренды рынка
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None,
        min_conn: int = 1,
        max_conn: int = 10
    ):
        """
        Инициализация PostgreSQL клиента

        Args:
            host: PostgreSQL host (default: localhost или POSTGRES_HOST)
            port: PostgreSQL port (default: 5432 или POSTGRES_PORT)
            database: Database name (default: cian_analyzer или POSTGRES_DB)
            user: PostgreSQL user (default: postgres или POSTGRES_USER)
            password: PostgreSQL password (из env POSTGRES_PASSWORD)
            min_conn: Минимальное кол-во соединений в пуле
            max_conn: Максимальное кол-во соединений в пуле
        """
        if not POSTGRES_AVAILABLE:
            raise ImportError(
                "psycopg2 не установлен. Установите: pip install psycopg2-binary"
            )

        self.host = host or os.getenv('POSTGRES_HOST', 'localhost')
        self.port = int(port or os.getenv('POSTGRES_PORT', 5432))
        self.database = database or os.getenv('POSTGRES_DB', 'cian_analyzer')
        self.user = user or os.getenv('POSTGRES_USER', 'postgres')
        self.password = password or os.getenv('POSTGRES_PASSWORD', '')

        self.connection_pool = None
        self._initialize_pool(min_conn, max_conn)
        self._create_schema()

    def _initialize_pool(self, min_conn: int, max_conn: int):
        """Инициализация пула соединений"""
        try:
            self.connection_pool = SimpleConnectionPool(
                min_conn,
                max_conn,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"✅ PostgreSQL подключен: {self.host}:{self.port}/{self.database}")

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к PostgreSQL: {e}")
            raise

    def _get_connection(self):
        """Получение соединения из пула"""
        return self.connection_pool.getconn()

    def _put_connection(self, conn):
        """Возврат соединения в пул"""
        self.connection_pool.putconn(conn)

    def _create_schema(self):
        """Создание схемы БД если не существует"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Таблица анализов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Целевой объект
                    target_url TEXT NOT NULL,
                    target_price BIGINT,
                    target_area DECIMAL(10, 2),
                    target_rooms INTEGER,
                    target_floor INTEGER,
                    target_total_floors INTEGER,
                    target_address TEXT,
                    target_metro TEXT,
                    target_data JSONB,

                    -- Результаты анализа
                    fair_price BIGINT,
                    fair_price_per_sqm INTEGER,
                    median_price_per_sqm INTEGER,
                    comparables_count INTEGER,
                    filtered_comparables_count INTEGER,

                    -- Рекомендации
                    recommendations JSONB,
                    recommendations_count INTEGER,

                    -- Сценарии
                    price_scenarios JSONB,

                    -- Полный анализ (backup)
                    analysis_result JSONB,

                    -- Метаданные
                    user_ip VARCHAR(45),
                    user_agent TEXT,
                    duration_seconds DECIMAL(10, 2)
                );
            """)

            # Индексы для быстрого поиска
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_session_id
                ON analyses(session_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_created_at
                ON analyses(created_at DESC);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_target_url
                ON analyses(target_url);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_target_address
                ON analyses USING gin(to_tsvector('russian', target_address));
            """)

            # Таблица ценовых данных по рынку (для трендов)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Локация
                    city VARCHAR(100),
                    district VARCHAR(200),
                    metro VARCHAR(200),

                    -- Параметры
                    rooms INTEGER,
                    area_min DECIMAL(10, 2),
                    area_max DECIMAL(10, 2),

                    -- Статистика
                    median_price_per_sqm INTEGER,
                    mean_price_per_sqm INTEGER,
                    std_dev INTEGER,
                    sample_size INTEGER,

                    -- Метаданные
                    source VARCHAR(50) DEFAULT 'cian',
                    data JSONB
                );
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_data_recorded_at
                ON market_data(recorded_at DESC);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_data_location
                ON market_data(city, district, metro);
            """)

            # Таблица парсированных объектов (кэш)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parsed_properties (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Основные данные
                    price BIGINT,
                    price_per_sqm INTEGER,
                    total_area DECIMAL(10, 2),
                    rooms INTEGER,
                    floor INTEGER,
                    total_floors INTEGER,

                    -- Полные данные
                    property_data JSONB,

                    -- TTL для кэша (опционально)
                    expires_at TIMESTAMP,

                    -- Метрики парсинга
                    parse_duration_seconds DECIMAL(10, 2),
                    parser_type VARCHAR(50)
                );
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parsed_properties_url
                ON parsed_properties(url);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parsed_properties_expires_at
                ON parsed_properties(expires_at);
            """)

            conn.commit()
            logger.info("✅ Схема БД создана/проверена")

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Ошибка создания схемы: {e}")
            raise
        finally:
            if conn:
                self._put_connection(conn)

    def save_analysis(
        self,
        session_id: str,
        target_property: Dict,
        analysis_result: Dict,
        metadata: Optional[Dict] = None
    ) -> Optional[int]:
        """
        Сохранение результатов анализа

        Args:
            session_id: ID сессии
            target_property: Данные целевого объекта
            analysis_result: Результаты анализа
            metadata: Доп. метаданные (user_ip, user_agent, duration)

        Returns:
            ID записи или None при ошибке
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            metadata = metadata or {}

            # Извлекаем ключевые поля
            fair_price_data = analysis_result.get('fair_price_analysis', {})
            market_stats = analysis_result.get('market_statistics', {})
            recommendations = analysis_result.get('recommendations', [])
            price_scenarios = analysis_result.get('price_scenarios', [])

            cursor.execute("""
                INSERT INTO analyses (
                    session_id,
                    target_url, target_price, target_area, target_rooms,
                    target_floor, target_total_floors, target_address, target_metro,
                    target_data,
                    fair_price, fair_price_per_sqm, median_price_per_sqm,
                    comparables_count, filtered_comparables_count,
                    recommendations, recommendations_count,
                    price_scenarios,
                    analysis_result,
                    user_ip, user_agent, duration_seconds
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (session_id) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP,
                    analysis_result = EXCLUDED.analysis_result,
                    fair_price = EXCLUDED.fair_price,
                    recommendations = EXCLUDED.recommendations
                RETURNING id;
            """, (
                session_id,
                target_property.get('url'),
                target_property.get('price'),
                target_property.get('total_area'),
                target_property.get('rooms'),
                target_property.get('floor'),
                target_property.get('total_floors'),
                target_property.get('address'),
                ','.join(target_property.get('metro', [])) if isinstance(target_property.get('metro'), list) else target_property.get('metro'),
                Json(target_property),
                fair_price_data.get('final_fair_price'),
                fair_price_data.get('final_fair_price_per_sqm'),
                market_stats.get('median_price_per_sqm'),
                len(analysis_result.get('comparables', [])),
                len(analysis_result.get('filtered_comparables', [])),
                Json(recommendations),
                len(recommendations),
                Json(price_scenarios),
                Json(analysis_result),
                metadata.get('user_ip'),
                metadata.get('user_agent'),
                metadata.get('duration_seconds')
            ))

            analysis_id = cursor.fetchone()[0]
            conn.commit()

            logger.info(f"✅ Анализ сохранен: ID={analysis_id}, session={session_id}")
            return analysis_id

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Ошибка сохранения анализа: {e}")
            return None
        finally:
            if conn:
                self._put_connection(conn)

    def get_analysis(self, session_id: str) -> Optional[Dict]:
        """
        Получение анализа по session_id

        Args:
            session_id: ID сессии

        Returns:
            Данные анализа или None
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT * FROM analyses WHERE session_id = %s;
            """, (session_id,))

            result = cursor.fetchone()
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"❌ Ошибка получения анализа: {e}")
            return None
        finally:
            if conn:
                self._put_connection(conn)

    def get_recent_analyses(self, limit: int = 50) -> List[Dict]:
        """
        Получение последних анализов

        Args:
            limit: Количество записей

        Returns:
            Список анализов
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    id, session_id, created_at,
                    target_url, target_price, target_area, target_rooms,
                    target_address, target_metro,
                    fair_price, fair_price_per_sqm, median_price_per_sqm,
                    comparables_count, recommendations_count
                FROM analyses
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))

            results = cursor.fetchall()
            return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"❌ Ошибка получения анализов: {e}")
            return []
        finally:
            if conn:
                self._put_connection(conn)

    def search_analyses(
        self,
        city: str = None,
        district: str = None,
        metro: str = None,
        rooms: int = None,
        date_from: datetime = None,
        date_to: datetime = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Поиск анализов по критериям

        Args:
            city: Город
            district: Район
            metro: Метро
            rooms: Количество комнат
            date_from: Дата от
            date_to: Дата до
            limit: Лимит результатов

        Returns:
            Список анализов
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = "SELECT * FROM analyses WHERE 1=1"
            params = []

            if city:
                query += " AND target_address ILIKE %s"
                params.append(f"%{city}%")

            if district:
                query += " AND target_address ILIKE %s"
                params.append(f"%{district}%")

            if metro:
                query += " AND target_metro ILIKE %s"
                params.append(f"%{metro}%")

            if rooms:
                query += " AND target_rooms = %s"
                params.append(rooms)

            if date_from:
                query += " AND created_at >= %s"
                params.append(date_from)

            if date_to:
                query += " AND created_at <= %s"
                params.append(date_to)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"❌ Ошибка поиска анализов: {e}")
            return []
        finally:
            if conn:
                self._put_connection(conn)

    def save_market_data(
        self,
        city: str,
        district: str,
        metro: str,
        rooms: int,
        area_range: tuple,
        statistics: Dict
    ) -> bool:
        """
        Сохранение рыночных данных для трендов

        Args:
            city: Город
            district: Район
            metro: Станция метро
            rooms: Количество комнат
            area_range: (min_area, max_area)
            statistics: Статистика (median, mean, std_dev, sample_size)

        Returns:
            True если успешно
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO market_data (
                    city, district, metro, rooms,
                    area_min, area_max,
                    median_price_per_sqm, mean_price_per_sqm,
                    std_dev, sample_size,
                    data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                city,
                district,
                metro,
                rooms,
                area_range[0],
                area_range[1],
                statistics.get('median_price_per_sqm'),
                statistics.get('mean_price_per_sqm'),
                statistics.get('std_dev'),
                statistics.get('sample_size'),
                Json(statistics)
            ))

            conn.commit()
            logger.debug(f"📊 Рыночные данные сохранены: {city}, {district}, {metro}")
            return True

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Ошибка сохранения рыночных данных: {e}")
            return False
        finally:
            if conn:
                self._put_connection(conn)

    def get_market_trends(
        self,
        city: str,
        district: str = None,
        metro: str = None,
        rooms: int = None,
        days: int = 30
    ) -> List[Dict]:
        """
        Получение трендов рынка за период

        Args:
            city: Город
            district: Район (опционально)
            metro: Метро (опционально)
            rooms: Кол-во комнат (опционально)
            days: Период в днях

        Returns:
            Список данных с трендами
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT * FROM market_data
                WHERE city = %s
                AND recorded_at >= %s
            """
            params = [city, datetime.now() - timedelta(days=days)]

            if district:
                query += " AND district = %s"
                params.append(district)

            if metro:
                query += " AND metro = %s"
                params.append(metro)

            if rooms:
                query += " AND rooms = %s"
                params.append(rooms)

            query += " ORDER BY recorded_at ASC"

            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"❌ Ошибка получения трендов: {e}")
            return []
        finally:
            if conn:
                self._put_connection(conn)

    def cache_parsed_property(
        self,
        url: str,
        property_data: Dict,
        ttl_hours: int = 24,
        parser_type: str = 'playwright',
        duration: float = None
    ) -> bool:
        """
        Кэширование парсированного объекта

        Args:
            url: URL объекта
            property_data: Данные объекта
            ttl_hours: Время жизни кэша в часах
            parser_type: Тип парсера
            duration: Длительность парсинга в секундах

        Returns:
            True если успешно
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            expires_at = datetime.now() + timedelta(hours=ttl_hours)

            cursor.execute("""
                INSERT INTO parsed_properties (
                    url, price, price_per_sqm, total_area, rooms,
                    floor, total_floors, property_data, expires_at,
                    parser_type, parse_duration_seconds
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP,
                    property_data = EXCLUDED.property_data,
                    expires_at = EXCLUDED.expires_at;
            """, (
                url,
                property_data.get('price'),
                property_data.get('price_per_sqm'),
                property_data.get('total_area'),
                property_data.get('rooms'),
                property_data.get('floor'),
                property_data.get('total_floors'),
                Json(property_data),
                expires_at,
                parser_type,
                duration
            ))

            conn.commit()
            logger.debug(f"💾 Объект закэширован: {url}")
            return True

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Ошибка кэширования объекта: {e}")
            return False
        finally:
            if conn:
                self._put_connection(conn)

    def get_cached_property(self, url: str) -> Optional[Dict]:
        """
        Получение закэшированного объекта

        Args:
            url: URL объекта

        Returns:
            Данные объекта или None если не найден/истек
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT property_data, parsed_at
                FROM parsed_properties
                WHERE url = %s
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP);
            """, (url,))

            result = cursor.fetchone()
            if result:
                logger.debug(f"💾 Объект получен из кэша: {url}")
                return result['property_data']
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения кэша: {e}")
            return None
        finally:
            if conn:
                self._put_connection(conn)

    def cleanup_expired_cache(self) -> int:
        """
        Очистка истекшего кэша

        Returns:
            Количество удаленных записей
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM parsed_properties
                WHERE expires_at IS NOT NULL
                AND expires_at < CURRENT_TIMESTAMP;
            """)

            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(f"🧹 Удалено истекших объектов: {deleted_count}")
            return deleted_count

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Ошибка очистки кэша: {e}")
            return 0
        finally:
            if conn:
                self._put_connection(conn)

    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики БД

        Returns:
            Словарь со статистикой
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            stats = {}

            # Количество анализов
            cursor.execute("SELECT COUNT(*) as count FROM analyses;")
            stats['total_analyses'] = cursor.fetchone()['count']

            # Количество за последние 24 часа
            cursor.execute("""
                SELECT COUNT(*) as count FROM analyses
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';
            """)
            stats['analyses_24h'] = cursor.fetchone()['count']

            # Количество рыночных данных
            cursor.execute("SELECT COUNT(*) as count FROM market_data;")
            stats['market_data_count'] = cursor.fetchone()['count']

            # Количество закэшированных объектов
            cursor.execute("""
                SELECT COUNT(*) as count FROM parsed_properties
                WHERE expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL;
            """)
            stats['cached_properties'] = cursor.fetchone()['count']

            # Средняя длительность парсинга
            cursor.execute("""
                SELECT AVG(parse_duration_seconds) as avg_duration
                FROM parsed_properties
                WHERE parse_duration_seconds IS NOT NULL;
            """)
            result = cursor.fetchone()
            stats['avg_parse_duration'] = float(result['avg_duration'] or 0)

            return stats

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}
        finally:
            if conn:
                self._put_connection(conn)

    def close(self):
        """Закрытие всех соединений"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("🔌 PostgreSQL соединения закрыты")


# Singleton instance
_postgres_manager: Optional[PostgresManager] = None


def get_postgres_manager(
    host: str = None,
    port: int = None,
    database: str = None,
    user: str = None,
    password: str = None
) -> PostgresManager:
    """
    Получение singleton instance PostgreSQL менеджера

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        database: Database name
        user: PostgreSQL user
        password: PostgreSQL password

    Returns:
        PostgresManager instance
    """
    global _postgres_manager

    if _postgres_manager is None:
        _postgres_manager = PostgresManager(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

    return _postgres_manager
