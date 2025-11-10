"""
Log Analyzer
Анализирует логи приложения и обнаруживает проблемы
"""

import re
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LogAnalyzer:
    """Анализирует логи и обнаруживает аномалии"""

    def __init__(self, log_file: str = "/home/user/cian-analyzer/app.log"):
        self.log_file = log_file
        self.error_patterns = [
            r'ERROR',
            r'CRITICAL',
            r'Exception',
            r'Traceback',
            r'failed',
            r'timeout',
            r'connection.*error',
            r'не удалось',
            r'ошибка',
        ]

        self.warning_patterns = [
            r'WARNING',
            r'WARN',
            r'deprecated',
            r'предупреждение',
        ]

    def analyze_recent_logs(self, hours: int = 1) -> Dict[str, Any]:
        """Анализирует логи за последние N часов"""
        logger.info(f"📊 Analyzing logs for the last {hours} hour(s)...")

        cutoff_time = datetime.now() - timedelta(hours=hours)

        results = {
            'period_hours': hours,
            'analysis_time': datetime.now().isoformat(),
            'errors': [],
            'warnings': [],
            'error_count': 0,
            'warning_count': 0,
            'error_types': defaultdict(int),
            'error_endpoints': defaultdict(int),
            'critical_issues': [],
        }

        try:
            if not Path(self.log_file).exists():
                results['message'] = f'Log file not found: {self.log_file}'
                return results

            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Парсим timestamp из лога
                    log_time = self._extract_timestamp(line)
                    if log_time and log_time < cutoff_time:
                        continue

                    # Ищем ошибки
                    if self._is_error_line(line):
                        results['errors'].append({
                            'time': log_time.isoformat() if log_time else 'unknown',
                            'message': line.strip()
                        })
                        results['error_count'] += 1

                        # Классифицируем ошибку
                        error_type = self._classify_error(line)
                        results['error_types'][error_type] += 1

                        # Извлекаем endpoint если есть
                        endpoint = self._extract_endpoint(line)
                        if endpoint:
                            results['error_endpoints'][endpoint] += 1

                    # Ищем предупреждения
                    elif self._is_warning_line(line):
                        results['warnings'].append({
                            'time': log_time.isoformat() if log_time else 'unknown',
                            'message': line.strip()
                        })
                        results['warning_count'] += 1

            # Определяем критические проблемы
            results['critical_issues'] = self._identify_critical_issues(results)

            # Конвертируем defaultdict в обычный dict для JSON
            results['error_types'] = dict(results['error_types'])
            results['error_endpoints'] = dict(results['error_endpoints'])

        except Exception as e:
            logger.error(f"Failed to analyze logs: {e}", exc_info=True)
            results['message'] = f'Analysis failed: {str(e)}'

        return results

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Извлекает timestamp из строки лога"""
        # Пытаемся найти timestamp в разных форматах
        patterns = [
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',  # 2025-11-10 15:30:45
            r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})',  # 10/11/2025 15:30:45
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    timestamp_str = match.group(1)
                    # Пробуем разные форматы парсинга
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']:
                        try:
                            return datetime.strptime(timestamp_str, fmt)
                        except ValueError:
                            continue
                except Exception:
                    pass

        return None

    def _is_error_line(self, line: str) -> bool:
        """Проверяет, является ли строка ошибкой"""
        line_lower = line.lower()
        return any(re.search(pattern, line_lower) for pattern in self.error_patterns)

    def _is_warning_line(self, line: str) -> bool:
        """Проверяет, является ли строка предупреждением"""
        line_lower = line.lower()
        return any(re.search(pattern, line_lower) for pattern in self.warning_patterns)

    def _classify_error(self, line: str) -> str:
        """Классифицирует ошибку по типу"""
        line_lower = line.lower()

        if 'connection' in line_lower or 'timeout' in line_lower:
            return 'connection_error'
        elif 'parse' in line_lower or 'parser' in line_lower:
            return 'parsing_error'
        elif 'validation' in line_lower or 'валидац' in line_lower:
            return 'validation_error'
        elif 'session' in line_lower or 'сессия' in line_lower:
            return 'session_error'
        elif 'redis' in line_lower or 'cache' in line_lower:
            return 'cache_error'
        elif 'analyz' in line_lower or 'анализ' in line_lower:
            return 'analysis_error'
        elif 'rate limit' in line_lower:
            return 'rate_limit_error'
        else:
            return 'other_error'

    def _extract_endpoint(self, line: str) -> Optional[str]:
        """Извлекает endpoint из строки лога"""
        # Ищем паттерны API endpoints
        match = re.search(r'/api/[\w-]+', line)
        if match:
            return match.group(0)
        return None

    def _identify_critical_issues(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Определяет критические проблемы на основе анализа"""
        issues = []

        # Если много ошибок подключения
        if results['error_types'].get('connection_error', 0) > 5:
            issues.append({
                'severity': 'high',
                'type': 'connection_errors',
                'count': results['error_types']['connection_error'],
                'message': 'High number of connection errors detected',
                'recommendation': 'Check network connectivity and CIAN availability'
            })

        # Если много ошибок парсинга
        if results['error_types'].get('parsing_error', 0) > 5:
            issues.append({
                'severity': 'high',
                'type': 'parsing_errors',
                'count': results['error_types']['parsing_error'],
                'message': 'High number of parsing errors detected',
                'recommendation': 'CIAN HTML structure may have changed, update parser'
            })

        # Если много ошибок валидации
        if results['error_types'].get('validation_error', 0) > 3:
            issues.append({
                'severity': 'medium',
                'type': 'validation_errors',
                'count': results['error_types']['validation_error'],
                'message': 'Multiple validation errors detected',
                'recommendation': 'Check data quality and validation rules'
            })

        # Если определённый endpoint часто падает
        for endpoint, count in results['error_endpoints'].items():
            if count > 5:
                issues.append({
                    'severity': 'high',
                    'type': 'endpoint_failures',
                    'endpoint': endpoint,
                    'count': count,
                    'message': f'Endpoint {endpoint} failing frequently',
                    'recommendation': f'Investigate {endpoint} handler and dependencies'
                })

        # Если слишком много ошибок в целом
        if results['error_count'] > 20:
            issues.append({
                'severity': 'critical',
                'type': 'high_error_rate',
                'count': results['error_count'],
                'message': 'Critically high error rate',
                'recommendation': 'Immediate investigation required - system may be unstable'
            })

        return issues

    def get_error_trends(self, days: int = 7) -> Dict[str, Any]:
        """Анализирует тренды ошибок за N дней"""
        # TODO: Можно реализовать более сложный анализ трендов
        # Пока возвращаем базовую информацию
        return {
            'days': days,
            'message': 'Trend analysis not yet implemented',
            'recent_analysis': self.analyze_recent_logs(hours=24)
        }


# Глобальный экземпляр
log_analyzer = LogAnalyzer()
