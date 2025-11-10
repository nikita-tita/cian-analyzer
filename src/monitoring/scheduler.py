"""
Monitoring Scheduler
Автоматически запускает мониторинг и тесты по расписанию
"""

import logging
import threading
import time
from datetime import datetime
from typing import Callable

from .health_check import health_service
from .test_runner import test_runner
from .log_analyzer import log_analyzer
from .error_detector import error_detector

logger = logging.getLogger(__name__)


class MonitoringScheduler:
    """Планировщик автоматического мониторинга"""

    def __init__(self):
        self.running = False
        self.thread = None
        self.last_health_check = None
        self.last_test_run = None
        self.last_log_analysis = None
        self.last_diagnostic = None

    def start(self):
        """Запускает планировщик в фоновом режиме"""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("✓ Monitoring scheduler started")

    def stop(self):
        """Останавливает планировщик"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("✓ Monitoring scheduler stopped")

    def _run_loop(self):
        """Основной цикл планировщика"""
        logger.info("Monitoring scheduler loop started")

        # Выполняем первую проверку сразу при старте
        self._run_health_check()
        self._run_log_analysis()

        while self.running:
            try:
                current_time = datetime.now()

                # Health check каждые 5 минут (БЕЗ реальных запросов в CIAN)
                if self._should_run(self.last_health_check, minutes=5):
                    self._run_health_check()
                    self.last_health_check = current_time

                # Анализ логов каждые 15 минут
                if self._should_run(self.last_log_analysis, minutes=15):
                    self._run_log_analysis()
                    self.last_log_analysis = current_time

                # Тесты каждый час
                if self._should_run(self.last_test_run, minutes=60):
                    self._run_tests()
                    self.last_test_run = current_time

                # Полная диагностика каждые 2 часа
                if self._should_run(self.last_diagnostic, minutes=120):
                    self._run_full_diagnostic()
                    self.last_diagnostic = current_time

                # Спим 30 секунд между итерациями
                time.sleep(30)

            except Exception as e:
                logger.error(f"Error in monitoring scheduler loop: {e}", exc_info=True)
                time.sleep(60)  # При ошибке ждём минуту

    def _should_run(self, last_run, minutes: int) -> bool:
        """Проверяет, пора ли запускать задачу"""
        if last_run is None:
            return True

        elapsed = (datetime.now() - last_run).total_seconds() / 60
        return elapsed >= minutes

    def _run_health_check(self):
        """Запускает health check"""
        try:
            logger.info("🏥 Running scheduled health check...")
            result = health_service.check_all()

            if result['status'] != 'healthy':
                logger.warning(f"⚠️ Health check status: {result['status']}, errors: {len(result.get('errors', []))}")
                self._handle_unhealthy_status(result)
            else:
                logger.info("✅ Health check passed")

        except Exception as e:
            logger.error(f"Scheduled health check failed: {e}", exc_info=True)

    def _run_log_analysis(self):
        """Запускает анализ логов"""
        try:
            logger.info("📊 Running scheduled log analysis...")
            result = log_analyzer.analyze_recent_logs(hours=1)

            if result.get('critical_issues'):
                logger.warning(f"⚠️ Found {len(result['critical_issues'])} critical issues in logs")
                self._handle_critical_log_issues(result)
            else:
                logger.info(f"✅ Log analysis completed: {result.get('error_count', 0)} errors, {result.get('warning_count', 0)} warnings")

        except Exception as e:
            logger.error(f"Scheduled log analysis failed: {e}", exc_info=True)

    def _run_tests(self):
        """Запускает автоматические тесты"""
        try:
            logger.info("🧪 Running scheduled tests...")
            result = test_runner.run_all_tests()

            if result['status'] == 'failed':
                logger.warning(f"⚠️ Tests failed: {result.get('tests_failed', 0)}/{result.get('tests_run', 0)}")
                self._handle_test_failures(result)
            elif result['status'] == 'passed':
                logger.info(f"✅ All tests passed: {result.get('tests_passed', 0)}/{result.get('tests_run', 0)}")
            else:
                logger.warning(f"⚠️ Tests status: {result['status']}")

        except Exception as e:
            logger.error(f"Scheduled test run failed: {e}", exc_info=True)

    def _run_full_diagnostic(self):
        """Запускает полную диагностику"""
        try:
            logger.info("🔍 Running scheduled full diagnostic...")
            result = error_detector.run_full_diagnostic()

            if result['overall_status'] != 'healthy':
                logger.warning(f"⚠️ Diagnostic status: {result['overall_status']}, issues: {len(result.get('detected_issues', []))}")
                self._handle_diagnostic_issues(result)
            else:
                logger.info("✅ Full diagnostic passed - system healthy")

        except Exception as e:
            logger.error(f"Scheduled diagnostic failed: {e}", exc_info=True)

    def _handle_unhealthy_status(self, health_check):
        """Обрабатывает нездоровый статус системы"""
        errors = health_check.get('errors', [])
        logger.error(f"🚨 SYSTEM UNHEALTHY - Errors detected:")
        for error in errors:
            logger.error(f"  - {error}")

        # TODO: Здесь можно добавить отправку уведомлений
        # - Email alerts
        # - Slack notifications
        # - Auto-create GitHub issues
        # - Trigger webhooks

    def _handle_critical_log_issues(self, log_analysis):
        """Обрабатывает критические проблемы в логах"""
        issues = log_analysis.get('critical_issues', [])
        logger.error(f"🚨 CRITICAL LOG ISSUES DETECTED:")
        for issue in issues:
            logger.error(f"  - {issue.get('type')}: {issue.get('message')} (count: {issue.get('count')})")
            logger.error(f"    Recommendation: {issue.get('recommendation')}")

        # TODO: Здесь можно добавить автоматическое создание issues

    def _handle_test_failures(self, test_results):
        """Обрабатывает падения тестов"""
        failures = test_results.get('failures', [])
        logger.error(f"🚨 TEST FAILURES DETECTED ({len(failures)} tests):")
        for failure in failures[:5]:  # Показываем первые 5
            logger.error(f"  - {failure.get('test')}")

        # TODO: Здесь можно добавить автоматическое создание issues

    def _handle_diagnostic_issues(self, diagnostic):
        """Обрабатывает проблемы из диагностики"""
        issues = diagnostic.get('detected_issues', [])
        logger.error(f"🚨 DIAGNOSTIC ISSUES DETECTED ({len(issues)} issues):")
        for issue in issues[:10]:  # Показываем первые 10
            logger.error(f"  - [{issue.get('source')}] {issue.get('issue')}")

        recommendations = diagnostic.get('recommendations', [])
        if recommendations:
            logger.info("💡 RECOMMENDATIONS:")
            for rec in recommendations[:5]:
                logger.info(f"  - {rec}")

        # TODO: Здесь можно добавить автоматическое создание detailed report

    def get_status(self):
        """Возвращает статус планировщика"""
        return {
            'running': self.running,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'last_test_run': self.last_test_run.isoformat() if self.last_test_run else None,
            'last_log_analysis': self.last_log_analysis.isoformat() if self.last_log_analysis else None,
            'last_diagnostic': self.last_diagnostic.isoformat() if self.last_diagnostic else None,
        }


# Глобальный экземпляр
monitoring_scheduler = MonitoringScheduler()
