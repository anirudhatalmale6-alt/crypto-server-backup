import json
import os
import datetime
import threading

class DailyJournal:
    """Tracks daily trading stats: max simultaneous, skipped by reason, per method."""

    def __init__(self, data_dir):
        self._file = os.path.join(data_dir, "daily_journal.json")
        self._lock = threading.Lock()
        self._data = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._file):
                with open(self._file) as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        try:
            with open(self._file, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def _today(self):
        return datetime.date.today().isoformat()

    def _get_day(self, date_str=None):
        d = date_str or self._today()
        if d not in self._data:
            self._data[d] = {
                "eur_max_simul": 0,
                "eur_skip_limit": 0,
                "eur_skip_funds": 0,
                "eur_skip_error": 0,
                "usdc_max_simul": 0,
                "usdc_skip_limit": 0,
                "usdc_skip_funds": 0,
                "usdc_skip_error": 0,
            }
        return self._data[d]

    def update_max_simul(self, eur_count, usdc_count):
        with self._lock:
            day = self._get_day()
            if eur_count > day["eur_max_simul"]:
                day["eur_max_simul"] = eur_count
            if usdc_count > day["usdc_max_simul"]:
                day["usdc_max_simul"] = usdc_count
            self._save()

    def record_skip(self, method, reason):
        """method: 'eur' or 'usdc', reason: 'limit', 'funds', 'error'"""
        with self._lock:
            day = self._get_day()
            key = f"{method}_skip_{reason}"
            if key in day:
                day[key] += 1
            self._save()

    def get_journal(self, last_n=30):
        with self._lock:
            sorted_dates = sorted(self._data.keys(), reverse=True)[:last_n]
            return {d: self._data[d] for d in sorted_dates}
