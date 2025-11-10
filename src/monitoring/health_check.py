"""
Health Check System
Проверяет состояние всех критических компонентов системы
"""

import logging
import time
import psutil
import requests
from typing import Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Сервис проверки здоровья системы"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.checks_history = []
        self.max_history = 100  # Храним последние 100 проверок
        self.last_cian_check = None  # Кэш для проверки CIAN

    def check_all(self) -> Dict[str, Any]:
        """Выполняет все проверки здоровья системы"""
        start_time = time.time()

        results = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'checks': {},
            'errors': [],
            'warnings': []
        }

        # 1. Проверка системных ресурсов
        try:
            system_check = self._check_system_resources()
            results['checks']['system'] = system_check
            if not system_check['healthy']:
                results['warnings'].append(f"System resources: {system_check['message']}")
        except Exception as e:
            logger.error(f"System check failed: {e}")
            results['checks']['system'] = {'healthy': False, 'error': str(e)}
            results['errors'].append(f"System check error: {e}")

        # 2. Проверка Redis/Session Storage
        try:
            redis_check = self._check_redis()
            results['checks']['redis'] = redis_check
            if not redis_check['healthy']:
                results['errors'].append(f"Redis/Session storage: {redis_check['message']}")
        except Exception as e:
            logger.error(f"Redis check failed: {e}")
            results['checks']['redis'] = {'healthy': False, 'error': str(e)}
            results['errors'].append(f"Redis check error: {e}")

        # 3. Проверка парсера CIAN
        try:
            parser_check = self._check_parser()
            results['checks']['parser'] = parser_check
            if not parser_check['healthy']:
                results['errors'].append(f"Parser: {parser_check['message']}")
        except Exception as e:
            logger.error(f"Parser check failed: {e}")
            results['checks']['parser'] = {'healthy': False, 'error': str(e)}
            results['errors'].append(f"Parser check error: {e}")

        # 4. Проверка API endpoints
        try:
            api_check = self._check_api_endpoints()
            results['checks']['api'] = api_check
            if not api_check['healthy']:
                results['errors'].append(f"API endpoints: {api_check['message']}")
        except Exception as e:
            logger.error(f"API check failed: {e}")
            results['checks']['api'] = {'healthy': False, 'error': str(e)}
            results['errors'].append(f"API check error: {e}")

        # 5. Проверка аналитического движка
        try:
            analyzer_check = self._check_analyzer()
            results['checks']['analyzer'] = analyzer_check
            if not analyzer_check['healthy']:
                results['errors'].append(f"Analyzer: {analyzer_check['message']}")
        except Exception as e:
            logger.error(f"Analyzer check failed: {e}")
            results['checks']['analyzer'] = {'healthy': False, 'error': str(e)}
            results['errors'].append(f"Analyzer check error: {e}")

        # Определяем общий статус
        if results['errors']:
            results['status'] = 'unhealthy'
        elif results['warnings']:
            results['status'] = 'degraded'

        results['duration_ms'] = (time.time() - start_time) * 1000

        # Сохраняем в историю
        self.checks_history.append(results)
        if len(self.checks_history) > self.max_history:
            self.checks_history.pop(0)

        return results

    def _check_system_resources(self) -> Dict[str, Any]:
        """Проверяет системные ресурсы (CPU, RAM, Disk)"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        warnings = []

        if cpu_percent > 80:
            warnings.append(f"High CPU usage: {cpu_percent}%")
        if memory.percent > 85:
            warnings.append(f"High memory usage: {memory.percent}%")
        if disk.percent > 90:
            warnings.append(f"High disk usage: {disk.percent}%")

        return {
            'healthy': len(warnings) == 0,
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk.percent,
            'message': '; '.join(warnings) if warnings else 'OK',
            'warnings': warnings
        }

    def _check_redis(self) -> Dict[str, Any]:
        """Проверяет доступность Redis/Session Storage"""
        try:
            from src.utils.session_storage import session_storage

            # Пытаемся создать тестовую сессию
            test_key = f"health_check_{int(time.time())}"
            test_data = {'test': True, 'timestamp': time.time()}

            session_storage.set(test_key, test_data, ttl=60)
            retrieved = session_storage.get(test_key)
            session_storage.delete(test_key)

            if retrieved and retrieved.get('test'):
                return {
                    'healthy': True,
                    'message': 'OK',
                    'storage_type': session_storage.__class__.__name__
                }
            else:
                return {
                    'healthy': False,
                    'message': 'Session storage read/write failed'
                }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Session storage error: {str(e)}'
            }

    def _check_parser(self) -> Dict[str, Any]:
        """
        Проверяет работу парсера CIAN

        ВАЖНО: Это только проверка инициализации парсера.
        НЕ делает реальных запросов в CIAN - только создаёт браузер и закрывает его.
        Это безопасно и не приведёт к блокировке.
        """
        try:
            from src.parsers.parser import Parser

            # Быстрая проверка - просто создаём парсер
            # НЕ делает запросов в CIAN, только проверяет что браузер может инициализироваться
            start_time = time.time()
            parser = Parser(headless=True, delay=0.5)
            parser.close()
            duration = (time.time() - start_time) * 1000

            return {
                'healthy': True,
                'message': 'OK (no requests made)',
                'init_time_ms': duration
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Parser initialization failed: {str(e)}'
            }

    def _check_cian_availability(self, force: bool = False) -> Dict[str, Any]:
        """
        Проверяет реальную доступность CIAN (ОПЦИОНАЛЬНО)

        ВАЖНО: Используйте эту проверку РЕДКО (раз в час), чтобы не перегружать CIAN.
        По умолчанию кэшируется на 1 час.

        Args:
            force: Принудительная проверка, игнорируя кэш

        Returns:
            Dict с результатами проверки
        """
        import requests
        from datetime import datetime, timedelta

        # Проверяем кэш (1 час)
        if not force and self.last_cian_check:
            age = (datetime.now() - self.last_cian_check['timestamp']).total_seconds()
            if age < 3600:  # 1 час
                return {
                    'healthy': self.last_cian_check['healthy'],
                    'message': f"Cached ({int(age/60)} min ago): {self.last_cian_check['message']}",
                    'cached': True
                }

        # Реальная проверка - делаем ЛЕГКИЙ запрос к главной странице CIAN
        try:
            response = requests.get(
                'https://www.cian.ru/',
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 (health check)'}
            )

            is_ok = response.status_code == 200

            result = {
                'healthy': is_ok,
                'message': 'CIAN is available' if is_ok else f'CIAN returned {response.status_code}',
                'status_code': response.status_code,
                'cached': False,
                'timestamp': datetime.now()
            }

            # Сохраняем в кэш
            self.last_cian_check = result

            return result

        except Exception as e:
            result = {
                'healthy': False,
                'message': f'CIAN check failed: {str(e)}',
                'cached': False,
                'timestamp': datetime.now()
            }
            self.last_cian_check = result
            return result

    def _check_api_endpoints(self) -> Dict[str, Any]:
        """Проверяет доступность критических API endpoints"""
        endpoints_to_check = [
            ('GET', '/api/status'),
            ('GET', '/api/health'),
        ]

        results = []
        all_healthy = True

        for method, endpoint in endpoints_to_check:
            try:
                url = f"{self.base_url}{endpoint}"
                start_time = time.time()

                if method == 'GET':
                    response = requests.get(url, timeout=5)
                else:
                    response = requests.post(url, timeout=5)

                duration = (time.time() - start_time) * 1000

                is_ok = response.status_code in [200, 404]  # 404 OK если endpoint не существует

                results.append({
                    'endpoint': endpoint,
                    'status_code': response.status_code,
                    'response_time_ms': duration,
                    'healthy': is_ok
                })

                if not is_ok:
                    all_healthy = False

            except Exception as e:
                results.append({
                    'endpoint': endpoint,
                    'error': str(e),
                    'healthy': False
                })
                all_healthy = False

        return {
            'healthy': all_healthy,
            'message': 'OK' if all_healthy else 'Some endpoints failed',
            'endpoints': results
        }

    def _check_analyzer(self) -> Dict[str, Any]:
        """Проверяет аналитический движок"""
        try:
            from src.analytics.analyzer import RealEstateAnalyzer

            # Просто создаём экземпляр
            analyzer = RealEstateAnalyzer()

            return {
                'healthy': True,
                'message': 'OK'
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Analyzer initialization failed: {str(e)}'
            }

    def get_health_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Возвращает сводку по здоровью системы за последние N часов"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        recent_checks = [
            check for check in self.checks_history
            if datetime.fromisoformat(check['timestamp']) > cutoff_time
        ]

        if not recent_checks:
            return {
                'period_hours': hours,
                'checks_count': 0,
                'message': 'No recent checks'
            }

        total_checks = len(recent_checks)
        healthy_checks = sum(1 for check in recent_checks if check['status'] == 'healthy')
        degraded_checks = sum(1 for check in recent_checks if check['status'] == 'degraded')
        unhealthy_checks = sum(1 for check in recent_checks if check['status'] == 'unhealthy')

        # Собираем все ошибки
        all_errors = []
        for check in recent_checks:
            all_errors.extend(check.get('errors', []))

        # Группируем ошибки по типам
        error_types = {}
        for error in all_errors:
            error_types[error] = error_types.get(error, 0) + 1

        return {
            'period_hours': hours,
            'checks_count': total_checks,
            'healthy_count': healthy_checks,
            'degraded_count': degraded_checks,
            'unhealthy_count': unhealthy_checks,
            'uptime_percent': (healthy_checks / total_checks * 100) if total_checks > 0 else 0,
            'common_errors': sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5],
            'latest_status': recent_checks[-1]['status'] if recent_checks else 'unknown'
        }


# Глобальный экземпляр
health_service = HealthCheckService()
