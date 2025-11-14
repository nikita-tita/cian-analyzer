"""Сервис автоматического получения рыночных ставок из открытых API."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


class MarketRatesService:
    """Получение и кеширование рыночных ставок из открытых источников.

    Сервис обращается сразу к нескольким источникам, чтобы построить
    бенчмарк альтернативной доходности:

    * ключевая ставка ЦБ РФ — ``https://www.cbr-xml-daily.ru/daily_json.js``;
    * доходность длинных ОФЗ — публичный API Московской биржи (ISS);
    * средняя ставка по рублёвым депозитам населения — CSV ЦБ.

    Все источники открытые и не требуют токена. Данные кешируются на диске,
    поэтому расчёты продолжают работать при временной недоступности API.
    """

    KEY_RATE_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
    MOEX_OFZ_URL = (
        "https://iss.moex.com/iss/engines/stock/markets/bonds/"
        "securities/SU26240RMFS.json?iss.only=marketdata&marketdata.columns=SECID,YIELD"
    )
    DEPOSIT_RATES_URL = "https://www.cbr.ru/vfs/statistics/credit_statistics/deposit_rates.csv"

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

    def _fetch_ofz_yield(self) -> Optional[float]:
        """Получает доходность эталонной ОФЗ через ISS MOEX."""
        response = self.session.get(self.MOEX_OFZ_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        marketdata = data.get("marketdata", {})
        columns = marketdata.get("columns", [])
        data_rows = marketdata.get("data", [])
        if not columns or not data_rows:
            return None

        try:
            yield_index = columns.index("YIELD")
        except ValueError:
            return None

        try:
            first_row = data_rows[0]
        except (IndexError, TypeError):
            return None

        try:
            return float(first_row[yield_index])
        except (TypeError, ValueError):
            return None

    def _fetch_deposit_rate(self) -> Optional[float]:
        """Парсит CSV ЦБ со средними ставками по депозитам населения."""
        response = self.session.get(self.DEPOSIT_RATES_URL, timeout=5)
        response.raise_for_status()
        decoded = response.content.decode("utf-8", errors="ignore")
        reader = csv.reader(decoded.splitlines())
        last_rate = None
        for row in reader:
            if not row:
                continue
            try:
                last_rate = float(row[-1].replace(",", "."))
            except (ValueError, AttributeError):
                continue
        return last_rate

    def refresh(self) -> None:
        try:
            key_rate = self._fetch_key_rate()
        except Exception as exc:
            logger.warning("Не удалось обновить ключевую ставку: %s", exc)
            return

        if key_rate is None:
            return

        deposit_rate = None
        ofz_yield = None

        try:
            ofz_yield = self._fetch_ofz_yield()
        except Exception as exc:  # pragma: no cover - защитный код
            logger.warning("Не удалось получить доходность ОФЗ: %s", exc)

        try:
            deposit_rate = self._fetch_deposit_rate()
        except Exception as exc:  # pragma: no cover - защитный код
            logger.warning("Не удалось получить ставку депозитов: %s", exc)

        self._cache = {
            "key_rate_percent": key_rate,
            "source": self.KEY_RATE_URL,
            "timestamp": datetime.utcnow().isoformat(),
            "ofz_yield_percent": ofz_yield,
            "ofz_source": self.MOEX_OFZ_URL,
            "deposit_rate_percent": deposit_rate,
            "deposit_source": self.DEPOSIT_RATES_URL,
        }
        self._save_cache()

    def get_rates(self) -> Dict[str, Optional[float]]:
        if not self._cache or self._is_cache_stale():
            self.refresh()
        return self._cache.copy()

    def get_opportunity_rate(
        self,
        horizon_months: int = 6,
        spread_percent: float = 2.0,
    ) -> Dict[str, Optional[float]]:
        """Возвращает ставку упущенной выгоды для заданного горизонта ожидания.

        Краткосрочные сценарии опираются на средние депозитные ставки,
        долгосрочные — на доходность ОФЗ, промежуточные получают
        взвешенную смесь всех каналов. При отсутствии конкретного источника
        используется формула ``ключевая + спред`` с фолбеком 8% годовых.
        """

        data = self.get_rates()
        key_rate_percent = data.get("key_rate_percent")
        spread = max(spread_percent, 0.0)
        deposit_rate_percent = data.get("deposit_rate_percent")
        ofz_yield_percent = data.get("ofz_yield_percent")

        sources = {
            "key_rate": data.get("source", self.KEY_RATE_URL),
            "deposit": data.get("deposit_source", self.DEPOSIT_RATES_URL),
            "ofz": data.get("ofz_source", self.MOEX_OFZ_URL),
        }

        instrument = "key_rate_spread"
        rate_percent: Optional[float] = None

        if horizon_months <= 3 and deposit_rate_percent:
            rate_percent = deposit_rate_percent
            instrument = "top_deposits"
        elif horizon_months >= 9 and ofz_yield_percent:
            rate_percent = ofz_yield_percent
            instrument = "ofz_long"
        elif deposit_rate_percent and ofz_yield_percent:
            weight = max(0.0, min(horizon_months / 12, 1.0))
            rate_percent = deposit_rate_percent * (1 - weight) + ofz_yield_percent * weight
            instrument = "blended_curve"
        elif key_rate_percent is not None:
            rate_percent = key_rate_percent + spread
        else:
            rate_percent = spread_percent + 6.0  # приводит к ≈8% годовых

        if rate_percent is None:
            # Фолбек на историческое допущение 8% годовых
            rate = 0.08
            source = "internal_default"
            timestamp = None
        else:
            rate = rate_percent / 100.0
            source = sources.get("key_rate")
            timestamp = data.get("timestamp")

        metadata = {
            "source": source,
            "updated_at": timestamp,
            "key_rate_percent": key_rate_percent,
            "spread_percent": spread,
            "deposit_rate_percent": deposit_rate_percent,
            "ofz_yield_percent": ofz_yield_percent,
            "instrument": instrument,
            "sources": sources,
        }

        return {
            "rate": rate,
            "key_rate_percent": key_rate_percent,
            "spread_percent": spread,
            "source": source,
            "timestamp": timestamp,
            "metadata": metadata,
        }


__all__ = ["MarketRatesService"]
