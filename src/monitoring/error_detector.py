"""
Error Detection and Auto-Reporting System
Автоматически обнаруживает ошибки и создаёт задачи для исправления
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from .health_check import health_service
from .log_analyzer import log_analyzer
from .test_runner import test_runner

logger = logging.getLogger(__name__)


class ErrorDetector:
    """Обнаруживает ошибки и генерирует отчёты"""

    def __init__(self, reports_dir: str = "/home/user/cian-analyzer/error_reports"):
        self.reports_dir = reports_dir
        Path(self.reports_dir).mkdir(exist_ok=True)

    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Запускает полную диагностику системы"""
        logger.info("🔍 Running full system diagnostic...")

        diagnostic = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'health_check': None,
            'log_analysis': None,
            'test_results': None,
            'detected_issues': [],
            'recommendations': []
        }

        # 1. Health Check
        try:
            logger.info("Running health check...")
            health_check = health_service.check_all()
            diagnostic['health_check'] = health_check

            if health_check['status'] != 'healthy':
                diagnostic['overall_status'] = 'unhealthy'
                diagnostic['detected_issues'].extend([
                    {'source': 'health_check', 'issue': error}
                    for error in health_check.get('errors', [])
                ])
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            diagnostic['detected_issues'].append({
                'source': 'health_check',
                'issue': f'Health check failed: {str(e)}'
            })

        # 2. Log Analysis
        try:
            logger.info("Analyzing logs...")
            log_analysis = log_analyzer.analyze_recent_logs(hours=1)
            diagnostic['log_analysis'] = log_analysis

            if log_analysis.get('critical_issues'):
                diagnostic['overall_status'] = 'unhealthy'
                diagnostic['detected_issues'].extend([
                    {'source': 'logs', 'issue': issue}
                    for issue in log_analysis['critical_issues']
                ])
        except Exception as e:
            logger.error(f"Log analysis failed: {e}", exc_info=True)
            diagnostic['detected_issues'].append({
                'source': 'log_analysis',
                'issue': f'Log analysis failed: {str(e)}'
            })

        # 3. Test Results (используем последние, не запускаем новые чтобы не замедлять)
        try:
            logger.info("Checking test results...")
            test_results = test_runner.get_latest_results()
            diagnostic['test_results'] = test_results

            if test_results.get('status') == 'failed':
                diagnostic['overall_status'] = 'unhealthy'
                diagnostic['detected_issues'].extend([
                    {'source': 'tests', 'issue': failure}
                    for failure in test_results.get('failures', [])
                ])
        except Exception as e:
            logger.error(f"Failed to get test results: {e}", exc_info=True)
            diagnostic['detected_issues'].append({
                'source': 'tests',
                'issue': f'Failed to get test results: {str(e)}'
            })

        # 4. Генерируем рекомендации
        diagnostic['recommendations'] = self._generate_recommendations(diagnostic)

        # 5. Сохраняем отчёт
        self._save_diagnostic_report(diagnostic)

        logger.info(f"✓ Diagnostic completed. Status: {diagnostic['overall_status']}, "
                   f"Issues: {len(diagnostic['detected_issues'])}")

        return diagnostic

    def _generate_recommendations(self, diagnostic: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации на основе диагностики"""
        recommendations = []

        # Анализируем health check
        health = diagnostic.get('health_check', {})
        if health:
            if not health.get('checks', {}).get('parser', {}).get('healthy'):
                recommendations.append(
                    "🔧 Parser is failing - check browser dependencies and CIAN availability"
                )

            if not health.get('checks', {}).get('redis', {}).get('healthy'):
                recommendations.append(
                    "🔧 Session storage is failing - check Redis connection or use in-memory fallback"
                )

            system = health.get('checks', {}).get('system', {})
            if system and system.get('cpu_percent', 0) > 80:
                recommendations.append(
                    "⚠️ High CPU usage - consider scaling or optimizing performance"
                )

        # Анализируем логи
        logs = diagnostic.get('log_analysis', {})
        if logs:
            for issue in logs.get('critical_issues', []):
                if issue['type'] == 'connection_errors':
                    recommendations.append(
                        "🌐 High connection error rate - implement retry logic and better timeout handling"
                    )
                elif issue['type'] == 'parsing_errors':
                    recommendations.append(
                        "🔍 Parser errors detected - CIAN HTML structure may have changed, update selectors"
                    )
                elif issue['type'] == 'endpoint_failures':
                    recommendations.append(
                        f"🚨 Endpoint {issue.get('endpoint')} is failing - investigate handler code"
                    )

        # Анализируем тесты
        tests = diagnostic.get('test_results', {})
        if tests and tests.get('status') == 'failed':
            recommendations.append(
                f"⚠️ {tests.get('tests_failed', 0)} tests failing - review test failures and fix broken functionality"
            )

        if not recommendations:
            recommendations.append("✅ No critical issues detected - system is healthy")

        return recommendations

    def _save_diagnostic_report(self, diagnostic: Dict[str, Any]):
        """Сохраняет диагностический отчёт"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.reports_dir}/diagnostic_{timestamp}.json"

        try:
            with open(filename, 'w') as f:
                json.dump(diagnostic, f, indent=2)
            logger.info(f"Diagnostic report saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save diagnostic report: {e}")

    def create_issue_report(self, diagnostic: Dict[str, Any]) -> str:
        """Создаёт текстовый отчёт для создания issue"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        report = f"""# Automated Error Report
**Generated:** {timestamp}
**Status:** {diagnostic['overall_status'].upper()}

## Summary
- **Detected Issues:** {len(diagnostic['detected_issues'])}
- **Health Status:** {diagnostic.get('health_check', {}).get('status', 'unknown')}
- **Error Count (1h):** {diagnostic.get('log_analysis', {}).get('error_count', 0)}
- **Test Status:** {diagnostic.get('test_results', {}).get('status', 'unknown')}

"""

        # Добавляем обнаруженные проблемы
        if diagnostic['detected_issues']:
            report += "## Detected Issues\n\n"
            for idx, issue in enumerate(diagnostic['detected_issues'], 1):
                source = issue.get('source', 'unknown')
                issue_data = issue.get('issue', {})

                if isinstance(issue_data, dict):
                    report += f"### {idx}. {issue_data.get('type', 'Unknown')} (from {source})\n"
                    report += f"- **Severity:** {issue_data.get('severity', 'unknown')}\n"
                    report += f"- **Message:** {issue_data.get('message', 'No message')}\n"
                    if 'recommendation' in issue_data:
                        report += f"- **Recommendation:** {issue_data['recommendation']}\n"
                else:
                    report += f"### {idx}. Issue from {source}\n"
                    report += f"- {issue_data}\n"

                report += "\n"

        # Добавляем рекомендации
        if diagnostic['recommendations']:
            report += "## Recommendations\n\n"
            for rec in diagnostic['recommendations']:
                report += f"- {rec}\n"
            report += "\n"

        # Добавляем детали health check
        health = diagnostic.get('health_check', {})
        if health:
            report += "## Health Check Details\n\n"
            for check_name, check_data in health.get('checks', {}).items():
                status = "✅" if check_data.get('healthy') else "❌"
                report += f"- **{check_name}:** {status} {check_data.get('message', '')}\n"
            report += "\n"

        # Добавляем топ ошибок из логов
        logs = diagnostic.get('log_analysis', {})
        if logs and logs.get('error_types'):
            report += "## Top Error Types (Last Hour)\n\n"
            for error_type, count in sorted(logs['error_types'].items(), key=lambda x: x[1], reverse=True)[:5]:
                report += f"- **{error_type}:** {count} occurrences\n"
            report += "\n"

        return report


# Глобальный экземпляр
error_detector = ErrorDetector()
