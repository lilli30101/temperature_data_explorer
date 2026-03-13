import gzip
import io
from pathlib import Path

import pytest
import requests

from app.services.noaa_client import NoaaClient


def test_parse_station_csv_with_header():
    rows = list(NoaaClient.parse_station_csv("DATE,ELEMENT,DATA_VALUE\n2020-01-01,TMIN,10\n"))
    assert rows[0]['DATE'] == '2020-01-01'
    assert rows[0]['ELEMENT'] == 'TMIN'
    assert rows[0]['DATA_VALUE'] == '10'


def test_parse_station_csv_without_header():
    rows = list(NoaaClient.parse_station_csv("STATION1,20200101,TMAX,80,,,\n"))
    assert rows[0]['DATE'] == '2020-01-01'
    assert rows[0]['ELEMENT'] == 'TMAX'
    assert rows[0]['DATA_VALUE'] == '80'


def test_normalize_row_maps_alternative_date_field():
    row = NoaaClient._normalize_row({'YEAR/MONTH/DAY': '20200131', 'ELEMENT': 'TMIN', 'DATA VALUE': '12'})
    assert row['DATE'] == '2020-01-31'
    assert row['DATA_VALUE'] == '12'


def test_iter_candidate_urls_contains_multiple_fallbacks():
    client = NoaaClient(timeout=1)
    urls = client._iter_candidate_urls('STATION1')
    assert any(url.endswith('/by_station/STATION1.csv.gz') for url in urls)
    assert any('/csv.gz/by_station/' in url for url in urls)
    assert any(url.endswith('/by_station/STATION1.csv') for url in urls)


class DummyResponse:
    def __init__(self, *, raw_bytes: bytes = b'', text_chunks=None, status_code: int = 200, headers=None):
        self.raw = io.BytesIO(raw_bytes)
        self._text_chunks = text_chunks or []
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f'status {self.status_code}')
            err.response = self
            raise err

    def iter_content(self, chunk_size=0, decode_unicode=False):
        yield from self._text_chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_stream_station_csv_to_cache_reads_plain_response(tmp_path, monkeypatch):
    client = NoaaClient(timeout=1)

    def fake_get(url, timeout, stream):
        if url.endswith('.gz'):
            return DummyResponse(status_code=404)
        return DummyResponse(text_chunks=['DATE,ELEMENT,DATA_VALUE\n', '2020-01-01,TMIN,10\n'])

    monkeypatch.setattr(requests, 'get', fake_get)
    out = tmp_path / 'station.csv'
    client.stream_station_csv_to_cache('STATION1', out)
    assert '2020-01-01,TMIN,10' in out.read_text(encoding='utf-8')


def test_stream_station_csv_to_cache_reads_gzip_response(tmp_path, monkeypatch):
    client = NoaaClient(timeout=1)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb') as gz:
        gz.write(b'DATE,ELEMENT,DATA_VALUE\n2020-01-01,TMAX,20\n')

    def fake_get(url, timeout, stream):
        return DummyResponse(raw_bytes=buf.getvalue(), headers={'Content-Encoding': 'gzip'})

    monkeypatch.setattr(requests, 'get', fake_get)
    out = tmp_path / 'station.csv'
    client.stream_station_csv_to_cache('STATION1', out)
    assert '2020-01-01,TMAX,20' in out.read_text(encoding='utf-8')


def test_stream_station_csv_to_cache_raises_file_not_found_after_all_404s(tmp_path, monkeypatch):
    client = NoaaClient(timeout=1)

    def fake_get(url, timeout, stream):
        return DummyResponse(status_code=404)

    monkeypatch.setattr(requests, 'get', fake_get)
    with pytest.raises(FileNotFoundError):
        client.stream_station_csv_to_cache('STATION1', tmp_path / 'station.csv')
