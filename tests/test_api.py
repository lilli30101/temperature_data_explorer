from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.cache_repository import CacheRepository
from app.services.noaa_client import NoaaClient

client = TestClient(app)


def _write_runtime_stations_index(tmp_path: Path) -> CacheRepository:
    repo = CacheRepository(
        stations_index_file=tmp_path / 'stations.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    repo.write_stations([
        {
            'id': 'GM000000001',
            'name': 'Test Station',
            'latitude': 48.5,
            'longitude': 8.4,
            'elevation': 700.0,
            'mindate': 2020,
            'maxdate': 2024,
        }
    ])
    return repo


class FakeNoaaClient(NoaaClient):
    def __init__(self):
        pass

    def stream_station_csv_to_cache(self, station_id: str, cache_file: Path) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            '\n'.join(
                [
                    'DATE,ELEMENT,DATA_VALUE',
                    '2022-01-01,TMIN,10',
                    '2022-01-01,TMAX,80',
                    '2022-01-02,TMIN,20',
                    '2022-12-15,TMAX,100',
                    '2023-06-01,TMIN,120',
                    '2023-06-01,TMAX,240',
                ]
            ),
            encoding='utf-8',
        )


def test_station_search_returns_results(tmp_path):
    repo = _write_runtime_stations_index(tmp_path)
    from app.api import routes
    routes.service.cache = repo
    response = client.get(
        '/api/stations',
        params={
            'latitude': 48.466,
            'longitude': 8.411,
            'radius_km': 50,
            'limit': 5,
            'start_year': 2022,
            'end_year': 2023,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['id'] == 'GM000000001'


def test_analysis_returns_values_for_sparse_years(tmp_path):
    repo = _write_runtime_stations_index(tmp_path)
    from app.api import routes
    routes.service.cache = repo
    routes.service.noaa = FakeNoaaClient()
    routes.service._analyze_station_cached.cache_clear()
    response = client.get('/api/stations/GM000000001/analysis', params={'start_year': 2022, 'end_year': 2023})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload['values']) == 2
    assert payload['values'][0]['has_data'] is True
    assert payload['values'][0]['tmin'] == 1.5
    assert payload['values'][0]['tmax'] == 9.0
    assert payload['values'][0]['annual_tmin_coverage'] > 0
    assert payload['values'][1]['has_data'] is True
    assert payload['values'][1]['summer_tmax'] == 24.0


def test_station_search_rejects_large_radius():
    response = client.get(
        '/api/stations',
        params={
            'latitude': 48.466,
            'longitude': 8.411,
            'radius_km': settings.max_search_radius_km + 1,
            'limit': 5,
            'start_year': 2022,
            'end_year': 2023,
        },
    )
    assert response.status_code == 422


def test_station_search_rejects_invalid_coordinate():
    response = client.get(
        '/api/stations',
        params={
            'latitude': 120,
            'longitude': 8.411,
            'radius_km': 50,
            'limit': 5,
            'start_year': 2022,
            'end_year': 2023,
        },
    )
    assert response.status_code == 422


def test_health_endpoint():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_analysis_parses_headerless_noaa_station_file(tmp_path):
    from app.api.routes import service

    service.cache.summary_cache_dir = tmp_path / "summaries"
    service.cache.summary_cache_dir.mkdir(parents=True, exist_ok=True)
    service.cache.station_cache_dir = tmp_path / "by_station"
    service.cache.station_cache_dir.mkdir(parents=True, exist_ok=True)

    station_id = "GME00120946"
    service.cache.write_station_data(
        station_id,
        "\n".join([
            "GME00120946,19490101,TMIN,-10,,,",
            "GME00120946,19490101,TMAX,50,,,",
            "GME00120946,19490102,TMIN,0,,,",
            "GME00120946,19490102,TMAX,70,,,",
        ]) + "\n",
    )

    response = client.get(f"/api/stations/{station_id}/analysis", params={"start_year": 1949, "end_year": 1949})
    assert response.status_code == 200
    payload = response.json()
    assert payload["values"][0]["has_data"] is True
    assert payload["values"][0]["tmin"] == -0.5
    assert payload["values"][0]["tmax"] == 6.0


def test_analysis_returns_404_when_station_index_missing(tmp_path):
    from app.api import routes
    routes.service.cache = CacheRepository(
        stations_index_file=tmp_path / 'missing.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    routes.service._analyze_station_cached.cache_clear()
    response = client.get('/api/stations/UNKNOWN/analysis', params={'start_year': 2022, 'end_year': 2023})
    assert response.status_code == 404
