"""Сервис автоматического получения рыночных ставок из открытых API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


class MarketRatesService:
    """Получение и кеширование ключевой ставки ЦБ РФ и производных метрик.

    Источник данных — https://www.cbr-xml-daily.ru/daily_json.js (не требует токена).
    Сервис обновляет данные не чаще раза в 12 часов и хранит их на диске,
    чтобы расчеты работали даже при недоступности внешнего API.
    """

    KEY_RATE_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
    CACHE_TTL = timedelta(hours=12)

    def __init__(self, cache_path: Optional[Path] = None, session: Optional[requests.Session] = None):
        self.cache_path = cache_path or Path(__file__).resolve().parents[1] / "cache" / "market_rates.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self._cache: Dict[str, Optional[float]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            self._cache = json.loads(self.cache_path.read_text())
        except Exception as exc:  # pragma: no cover - защитный код
            logger.warning("Не удалось прочитать кеш ставок: %s", exc)
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2))
        except Exception as exc:  # pragma: no cover - защитный код
            logger.warning("Не удалось сохранить кеш ставок: %s", exc)

    def _is_cache_stale(self) -> bool:
        timestamp = self._cache.get("timestamp")
        if not timestamp:
            return True
        try:
            last_update = datetime.fromisoformat(timestamp)
        except ValueError:
            return True
        return datetime.utcnow() - last_update > self.CACHE_TTL

    def _fetch_key_rate(self) -> Optional[float]:
        response = self.session.get(self.KEY_RATE_URL, timeout=5)
        response.raise_for_status()
        payload = response.json()
        key_rate = payload.get("KeyRate")
        try:
            return float(key_rate)
        except (TypeError, ValueError):
            return None

    def refresh(self) -> None:
        try:
            key_rate = self._fetch_key_rate()
        except Exception as exc:
            logger.warning("Не удалось обновить ключевую ставку: %s", exc)
            return

        if key_rate is None:
            return

        self._cache = {
            "key_rate_percent": key_rate,
            "source": self.KEY_RATE_URL,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._save_cache()

    def get_rates(self) -> Dict[str, Optional[float]]:
        if not self._cache or self._is_cache_stale():
            self.refresh()
        return self._cache.copy()

    def get_opportunity_rate(self, spread_percent: float = 2.0) -> Dict[str, Optional[float]]:
        """Возвращает ставку упущенной выгоды как key_rate + spread."""
        data = self.get_rates()
        key_rate_percent = data.get("key_rate_percent")
        spread = max(spread_percent, 0.0)

        if key_rate_percent is None:
            # Фолбек на историческое допущение 8% годовых
            rate = 0.08
            source = "internal_default"
            timestamp = None
        else:
            rate = (key_rate_percent + spread) / 100.0
            source = data.get("source", self.KEY_RATE_URL)
            timestamp = data.get("timestamp")

        return {
            "rate": rate,
            "key_rate_percent": key_rate_percent,
            "spread_percent": spread,
            "source": source,
            "timestamp": timestamp
        }


__all__ = ["MarketRatesService"]
