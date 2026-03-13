from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.core.config import settings


class CacheRepository:
    def __init__(
        self,
        stations_index_file: Path | None = None,
        station_cache_dir: Path | None = None,
        summary_cache_dir: Path | None = None,
        raw_dir: Path | None = None,
    ):
        self.stations_index_file = stations_index_file or settings.stations_index_file
        self.station_cache_dir = station_cache_dir or settings.station_cache_dir
        self.summary_cache_dir = summary_cache_dir or settings.summary_cache_dir
        self.raw_dir = raw_dir or settings.raw_dir

        self.stations_index_file.parent.mkdir(parents=True, exist_ok=True)
        self.station_cache_dir.mkdir(parents=True, exist_ok=True)
        self.summary_cache_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def read_stations(self) -> list[dict]:
        if not self.stations_index_file.exists():
            return []
        return json.loads(self.stations_index_file.read_text(encoding="utf-8"))

    def write_stations(self, stations: list[dict]) -> None:
        self.stations_index_file.write_text(json.dumps(stations, separators=(",", ":")), encoding="utf-8")

    def station_file(self, station_id: str) -> Path:
        return self.station_cache_dir / f"{station_id}.csv"

    def has_station_data(self, station_id: str) -> bool:
        return self.station_file(station_id).exists()

    def read_station_data(self, station_id: str) -> str:
        return self.station_file(station_id).read_text(encoding="utf-8")

    def write_station_data(self, station_id: str, csv_text: str) -> None:
        self.station_file(station_id).write_text(csv_text, encoding="utf-8")

    def summary_file(self, station_id: str, start_year: int, end_year: int) -> Path:
        key = hashlib.sha1(f"v7:{station_id}:{start_year}:{end_year}".encode("utf-8")).hexdigest()[:16]
        return self.summary_cache_dir / f"{key}.json"

    def read_summary(self, station_id: str, start_year: int, end_year: int) -> dict | None:
        file = self.summary_file(station_id, start_year, end_year)
        if not file.exists():
            return None
        return json.loads(file.read_text(encoding="utf-8"))

    def write_summary(self, station_id: str, start_year: int, end_year: int, payload: dict) -> None:
        self.summary_file(station_id, start_year, end_year).write_text(
            json.dumps(payload, separators=(",", ":")),
            encoding="utf-8",
        )
