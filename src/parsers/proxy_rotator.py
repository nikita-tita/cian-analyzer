"""
Proxy Rotator для Housler Parser
Управление пулом прокси и их ротацией
"""

import logging
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


@dataclass
class ProxyStats:
    """Статистика использования прокси"""
    success: int = 0
    failed: int = 0
    captcha: int = 0
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None
    total_requests: int = 0
    avg_response_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Процент успешных запросов"""
        if self.total_requests == 0:
            return 0.0
        return (self.success / self.total_requests) * 100
    
    @property
    def is_healthy(self) -> bool:
        """Прокси считается здоровым если успешность > 50%"""
        return self.success_rate >= 50.0 or self.total_requests < 5


@dataclass
class ProxyInfo:
    """Информация о прокси"""
    server: str
    username: Optional[str] = None
    password: Optional[str] = None
    country: str = 'RU'
    city: Optional[str] = None
    stats: ProxyStats = field(default_factory=ProxyStats)
    is_active: bool = True
    cooldown_until: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Конвертация в словарь для Playwright"""
        proxy_dict = {'server': self.server}
        if self.username:
            proxy_dict['username'] = self.username
        if self.password:
            proxy_dict['password'] = self.password
        return proxy_dict
    
    def is_available(self) -> bool:
        """Проверка доступности прокси"""
        if not self.is_active:
            return False
        
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        
        return self.stats.is_healthy
    
    def set_cooldown(self, seconds: int = 300):
        """Установить период охлаждения для прокси"""
        self.cooldown_until = datetime.now() + timedelta(seconds=seconds)
        logger.warning(f"Прокси {self.server} в cooldown на {seconds}с")


class ProxyRotator:
    """
    Ротатор прокси для распределения нагрузки и защиты от блокировок
    
    Поддерживает:
    - Круговую ротацию (round-robin)
    - Случайный выбор
    - Выбор по статистике (лучший прокси)
    - Автоматическое исключение неработающих прокси
    - Cooldown для заблокированных прокси
    """
    
    def __init__(
        self,
        proxies: List[Dict],
        strategy: str = 'round_robin',  # round_robin, random, best_performance
        max_failures: int = 3,
        cooldown_seconds: int = 300
    ):
        """
        Инициализация ротатора
        
        Args:
            proxies: Список прокси в формате dict
            strategy: Стратегия выбора прокси
            max_failures: Максимум ошибок подряд перед cooldown
            cooldown_seconds: Время охлаждения для проблемных прокси
        """
        self.proxies = [ProxyInfo(**p) for p in proxies]
        self.strategy = strategy
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self.current_idx = 0
        
        logger.info(f"✓ ProxyRotator инициализирован: {len(self.proxies)} прокси, стратегия={strategy}")
    
    def get_next_proxy(self) -> Tuple[ProxyInfo, int]:
        """
        Получить следующий доступный прокси
        
        Returns:
            (ProxyInfo, index): Прокси и его индекс
        
        Raises:
            RuntimeError: Если нет доступных прокси
        """
        if self.strategy == 'round_robin':
            return self._get_round_robin()
        elif self.strategy == 'random':
            return self._get_random()
        elif self.strategy == 'best_performance':
            return self._get_best_performance()
        else:
            raise ValueError(f"Неизвестная стратегия: {self.strategy}")
    
    def _get_round_robin(self) -> Tuple[ProxyInfo, int]:
        """Круговая ротация"""
        attempts = 0
        
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_idx]
            idx = self.current_idx
            self.current_idx = (self.current_idx + 1) % len(self.proxies)
            
            if proxy.is_available():
                logger.debug(f"Выбран прокси #{idx}: {proxy.server}")
                return proxy, idx
            
            attempts += 1
        
        # Если все в cooldown, берем с наименьшим cooldown
        return self._get_least_cooldown()
    
    def _get_random(self) -> Tuple[ProxyInfo, int]:
        """Случайный выбор"""
        available = [(i, p) for i, p in enumerate(self.proxies) if p.is_available()]
        
        if not available:
            return self._get_least_cooldown()
        
        idx, proxy = random.choice(available)
        logger.debug(f"Выбран случайный прокси #{idx}: {proxy.server}")
        return proxy, idx
    
    def _get_best_performance(self) -> Tuple[ProxyInfo, int]:
        """Выбор прокси с лучшей статистикой"""
        available = [(i, p) for i, p in enumerate(self.proxies) if p.is_available()]
        
        if not available:
            return self._get_least_cooldown()
        
        # Сортируем по успешности и скорости ответа
        best = max(
            available,
            key=lambda x: (
                x[1].stats.success_rate,
                -x[1].stats.avg_response_time if x[1].stats.avg_response_time > 0 else 0
            )
        )
        
        idx, proxy = best
        logger.debug(f"Выбран лучший прокси #{idx}: {proxy.server} (success={proxy.stats.success_rate:.1f}%)")
        return proxy, idx
    
    def _get_least_cooldown(self) -> Tuple[ProxyInfo, int]:
        """Получить прокси с наименьшим временем cooldown"""
        in_cooldown = [
            (i, p) for i, p in enumerate(self.proxies)
            if p.cooldown_until and datetime.now() < p.cooldown_until
        ]
        
        if not in_cooldown:
            # Все прокси неактивны, берем первый
            logger.warning("⚠️ Все прокси неактивны, используем первый")
            return self.proxies[0], 0
        
        # Берем с минимальным временем ожидания
        idx, proxy = min(in_cooldown, key=lambda x: x[1].cooldown_until)
        wait_seconds = (proxy.cooldown_until - datetime.now()).total_seconds()
        logger.warning(f"⏳ Ждем {wait_seconds:.0f}с пока прокси #{idx} выйдет из cooldown")
        time.sleep(wait_seconds + 1)
        
        proxy.cooldown_until = None
        return proxy, idx
    
    def mark_success(self, proxy_idx: int, response_time: float = 0.0):
        """
        Отметить успешное использование прокси
        
        Args:
            proxy_idx: Индекс прокси
            response_time: Время ответа в секундах
        """
        proxy = self.proxies[proxy_idx]
        proxy.stats.success += 1
        proxy.stats.total_requests += 1
        proxy.stats.last_used = datetime.now()
        proxy.stats.last_success = datetime.now()
        
        # Обновляем среднее время ответа
        if response_time > 0:
            if proxy.stats.avg_response_time == 0:
                proxy.stats.avg_response_time = response_time
            else:
                proxy.stats.avg_response_time = (
                    proxy.stats.avg_response_time * 0.7 + response_time * 0.3
                )
        
        # Сбрасываем cooldown при успехе
        if proxy.cooldown_until:
            proxy.cooldown_until = None
            logger.info(f"✓ Прокси #{proxy_idx} восстановлен")
        
        logger.debug(f"✓ Прокси #{proxy_idx} успех (rate={proxy.stats.success_rate:.1f}%)")
    
    def mark_failed(self, proxy_idx: int, reason: str = 'unknown'):
        """
        Отметить неудачное использование прокси
        
        Args:
            proxy_idx: Индекс прокси
            reason: Причина ошибки
        """
        proxy = self.proxies[proxy_idx]
        proxy.stats.failed += 1
        proxy.stats.total_requests += 1
        proxy.stats.last_used = datetime.now()
        
        logger.warning(f"✗ Прокси #{proxy_idx} ошибка: {reason} (rate={proxy.stats.success_rate:.1f}%)")
        
        # Проверяем на необходимость cooldown
        recent_failures = proxy.stats.failed - proxy.stats.success
        if recent_failures >= self.max_failures:
            proxy.set_cooldown(self.cooldown_seconds)
    
    def mark_captcha(self, proxy_idx: int):
        """
        Отметить обнаружение капчи
        
        Args:
            proxy_idx: Индекс прокси
        """
        proxy = self.proxies[proxy_idx]
        proxy.stats.captcha += 1
        proxy.stats.failed += 1
        proxy.stats.total_requests += 1
        proxy.stats.last_used = datetime.now()
        
        logger.warning(f"🔒 Прокси #{proxy_idx} получил капчу")
        
        # Капча = длинный cooldown
        proxy.set_cooldown(self.cooldown_seconds * 2)
    
    def get_stats(self) -> Dict:
        """
        Получить общую статистику по всем прокси
        
        Returns:
            Словарь со статистикой
        """
        total_requests = sum(p.stats.total_requests for p in self.proxies)
        total_success = sum(p.stats.success for p in self.proxies)
        active_count = sum(1 for p in self.proxies if p.is_available())
        
        return {
            'total_proxies': len(self.proxies),
            'active_proxies': active_count,
            'inactive_proxies': len(self.proxies) - active_count,
            'total_requests': total_requests,
            'total_success': total_success,
            'overall_success_rate': (total_success / total_requests * 100) if total_requests > 0 else 0,
            'proxies': [
                {
                    'index': i,
                    'server': p.server,
                    'country': p.country,
                    'city': p.city,
                    'is_active': p.is_active,
                    'is_available': p.is_available(),
                    'in_cooldown': p.cooldown_until is not None,
                    'cooldown_seconds_left': (
                        max(0, (p.cooldown_until - datetime.now()).total_seconds())
                        if p.cooldown_until else 0
                    ),
                    'stats': {
                        'success': p.stats.success,
                        'failed': p.stats.failed,
                        'captcha': p.stats.captcha,
                        'total_requests': p.stats.total_requests,
                        'success_rate': p.stats.success_rate,
                        'avg_response_time': p.stats.avg_response_time,
                        'last_used': p.stats.last_used.isoformat() if p.stats.last_used else None,
                        'last_success': p.stats.last_success.isoformat() if p.stats.last_success else None,
                    }
                }
                for i, p in enumerate(self.proxies)
            ]
        }
    
    def reset_stats(self):
        """Сбросить всю статистику"""
        for proxy in self.proxies:
            proxy.stats = ProxyStats()
            proxy.cooldown_until = None
        logger.info("📊 Статистика прокси сброшена")
    
    def disable_proxy(self, proxy_idx: int):
        """Отключить прокси"""
        self.proxies[proxy_idx].is_active = False
        logger.warning(f"🔴 Прокси #{proxy_idx} отключен")
    
    def enable_proxy(self, proxy_idx: int):
        """Включить прокси"""
        self.proxies[proxy_idx].is_active = True
        self.proxies[proxy_idx].cooldown_until = None
        logger.info(f"🟢 Прокси #{proxy_idx} включен")

