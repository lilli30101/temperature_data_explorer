from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path
from typing import Iterable

import requests

from app.core.config import settings


class NoaaClient:
    def __init__(self, timeout: int | None = None):
        self.base_urls = [
            settings.noaa_primary_base_url.rstrip('/'),
            settings.noaa_secondary_base_url.rstrip('/'),
        ]
        self.timeout = timeout or settings.request_timeout_seconds

    def _iter_candidate_urls(self, station_id: str) -> list[str]:
        candidates = []
        for base_url in self.base_urls:
            candidates.extend(
                [
                    f'{base_url}/by_station/{station_id}.csv.gz',
                    f'{base_url}/by_station/{station_id}.csv',
                    f'{base_url}/csv.gz/by_station/{station_id}.csv.gz',
                    f'{base_url}/csv/by_station/{station_id}.csv',
                ]
            )
        return candidates

    @staticmethod
    def _normalize_row(row: dict[str, str]) -> dict[str, str]:
        normalized = {str(key).strip().upper().replace(' ', '_'): value for key, value in row.items() if key is not None}
        date_value = normalized.get('DATE') or normalized.get('YEAR/MONTH/DAY')
        if date_value and len(date_value) == 8 and date_value.isdigit():
            date_value = f'{date_value[0:4]}-{date_value[4:6]}-{date_value[6:8]}'
        return {
            'DATE': date_value or '',
            'ELEMENT': (normalized.get('ELEMENT') or '').strip(),
            'DATA_VALUE': normalized.get('DATA_VALUE') or normalized.get('DATA VALUE') or '',
            'M_FLAG': normalized.get('M_FLAG') or normalized.get('M-FLAG') or '',
            'Q_FLAG': normalized.get('Q_FLAG') or normalized.get('Q-FLAG') or '',
            'S_FLAG': normalized.get('S_FLAG') or normalized.get('S-FLAG') or '',
            'OBS_TIME': normalized.get('OBS_TIME') or normalized.get('OBS-TIME') or '',
        }

    @staticmethod
    def parse_station_csv(csv_text: str) -> Iterable[dict[str, str]]:
        reader = csv.reader(io.StringIO(csv_text))
        header_map: dict[str, int] | None = None

        for row in reader:
            if not row:
                continue
            cells = [str(cell).strip() for cell in row]
            upper_cells = [cell.upper().replace(' ', '_') for cell in cells]

            if header_map is None and ('ELEMENT' in upper_cells or 'YEAR/MONTH/DAY' in upper_cells or 'DATE' in upper_cells):
                header_map = {name: index for index, name in enumerate(upper_cells)}
                continue

            if header_map is not None:
                mapped = {key: cells[index] for key, index in header_map.items() if index < len(cells)}
                yield NoaaClient._normalize_row(mapped)
                continue

            # NOAA readme-by_station format without header:
            # ID,YEAR/MONTH/DAY,ELEMENT,DATA_VALUE,M_FLAG,Q_FLAG,S_FLAG,OBS_TIME
            yield NoaaClient._normalize_row({
                'ID': cells[0] if len(cells) > 0 else '',
                'YEAR/MONTH/DAY': cells[1] if len(cells) > 1 else '',
                'ELEMENT': cells[2] if len(cells) > 2 else '',
                'DATA_VALUE': cells[3] if len(cells) > 3 else '',
                'M_FLAG': cells[4] if len(cells) > 4 else '',
                'Q_FLAG': cells[5] if len(cells) > 5 else '',
                'S_FLAG': cells[6] if len(cells) > 6 else '',
                'OBS_TIME': cells[7] if len(cells) > 7 else '',
            })

    def stream_station_csv_to_cache(self, station_id: str, cache_file: Path) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for url in self._iter_candidate_urls(station_id):
            try:
                with requests.get(url, timeout=self.timeout, stream=True) as response:
                    response.raise_for_status()
                    is_gzip = url.endswith('.gz') or response.headers.get('Content-Encoding', '').lower() == 'gzip'
                    if is_gzip:
                        with gzip.GzipFile(fileobj=response.raw) as gz_stream, cache_file.open('w', encoding='utf-8', newline='') as out:
                            for chunk in io.TextIOWrapper(gz_stream, encoding='utf-8'):
                                out.write(chunk)
                    else:
                        with cache_file.open('w', encoding='utf-8', newline='') as out:
                            for chunk in response.iter_content(chunk_size=1024 * 128, decode_unicode=True):
                                if chunk:
                                    out.write(chunk)
                return
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    last_error = exc
                    continue
                raise
        raise FileNotFoundError(f'Für Station {station_id} wurden keine NOAA-CSV-Daten gefunden.') from last_error
