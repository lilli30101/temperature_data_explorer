from pathlib import Path

import pytest

from app.models.schemas import ClimateAnalysisResponse, ClimateSeriesPoint, StationSearchRequest
from app.repositories.cache_repository import CacheRepository
from app.services.climate_service import ClimateService
from app.services.noaa_client import NoaaClient


class FakeNoaa(NoaaClient):
    def stream_station_csv_to_cache(self, station_id: str, cache_file: Path) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            "\n".join([
                "DATE,ELEMENT,DATA_VALUE",
                "2020-03-01,TMIN,10",
                "2020-03-01,TMAX,80",
                "2020-03-15,TMIN,20",
                "2020-03-15,TMAX,100",
                "2020-07-01,TMIN,100",
                "2020-07-01,TMAX,250",
                "2020-12-15,TMIN,-20",
                "2020-12-15,TMAX,30",
                "2021-01-15,TMIN,-10",
                "2021-01-15,TMAX,40",
                "2021-02-15,TMIN,0",
                "2021-02-15,TMAX,50",
            ]),
            encoding='utf-8',
        )


class SparseNoaa(NoaaClient):
    def stream_station_csv_to_cache(self, station_id: str, cache_file: Path) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            "\n".join([
                "DATE,ELEMENT,DATA_VALUE",
                "2020-01-01,TMIN,10",
                "2020-01-01,TMAX,50",
                "2020-07-01,TMIN,70",
                "2020-07-01,TMAX,150",
            ]),
            encoding='utf-8',
        )


def build_service(tmp_path: Path, noaa_client: NoaaClient | None = None) -> ClimateService:
    repo = CacheRepository(
        stations_index_file=tmp_path / 'stations.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    repo.write_stations([
        {
            'id': 'STATION1',
            'name': 'Alpha',
            'latitude': 48.0,
            'longitude': 8.0,
            'elevation': 700.0,
            'mindate': 2019,
            'maxdate': 2024,
        },
        {
            'id': 'STATION2',
            'name': 'Beta',
            'latitude': 48.6,
            'longitude': 8.0,
            'elevation': 705.0,
            'mindate': 2018,
            'maxdate': 2025,
        },
        {
            'id': 'SOUTH1',
            'name': 'South',
            'latitude': -33.0,
            'longitude': 18.0,
            'elevation': 10.0,
            'mindate': 2018,
            'maxdate': 2025,
        },
    ])
    return ClimateService(cache_repository=repo, noaa_client=noaa_client or FakeNoaa())


def test_search_stations_sorted_by_distance(tmp_path):
    service = build_service(tmp_path)
    result = service.search_stations(
        StationSearchRequest(latitude=48.1, longitude=8.0, radius_km=100, limit=5, start_year=2020, end_year=2021)
    )
    assert [station.id for station in result[:2]] == ['STATION1', 'STATION2']
    assert result[0].distance_km <= result[1].distance_km


def test_search_stations_rejects_invalid_year_range(tmp_path):
    service = build_service(tmp_path)
    request = StationSearchRequest(latitude=48.1, longitude=8.0, radius_km=100, limit=5, start_year=2022, end_year=2021)
    with pytest.raises(ValueError, match='start_year'):
        service.search_stations(request)


def test_search_stations_respects_limit(tmp_path):
    service = build_service(tmp_path)
    result = service.search_stations(
        StationSearchRequest(latitude=48.1, longitude=8.0, radius_km=100, limit=1, start_year=2020, end_year=2021)
    )
    assert len(result) == 1
    assert result[0].id == 'STATION1'


def test_analyze_station_writes_summary_cache(tmp_path):
    service = build_service(tmp_path)
    response = service.analyze_station('STATION1', 2020, 2021)
    assert response.values[0].summer_tmax == 25.0
    summary_files = list((tmp_path / 'summaries').glob('*.json'))
    assert summary_files


def test_analyze_station_reads_summary_cache_without_recomputing(tmp_path):
    service = build_service(tmp_path)
    expected = ClimateAnalysisResponse(
        station_id='STATION1',
        start_year=2020,
        end_year=2020,
        missing_data_rule='cached',
        values=[ClimateSeriesPoint(year=2020, has_data=True, tmin=1.0, tmax=2.0)],
    )
    service.cache.write_summary('STATION1', 2020, 2020, expected.model_dump())
    result = service.analyze_station('STATION1', 2020, 2020)
    assert result.missing_data_rule == 'cached'
    assert result.values[0].tmin == 1.0


def test_get_station_latitude_returns_value_and_none(tmp_path):
    service = build_service(tmp_path)
    assert service._get_station_latitude('STATION1') == 48.0
    assert service._get_station_latitude('UNKNOWN') is None


def test_season_months_switch_by_hemisphere(tmp_path):
    service = build_service(tmp_path)
    assert service._season_months_for_latitude(48.0)['winter'] == {12, 1, 2}
    assert service._season_months_for_latitude(-20.0)['summer'] == {12, 1, 2}


def test_aggregate_northern_winter_uses_december_and_following_jan_feb(tmp_path):
    service = build_service(tmp_path)
    response = service.analyze_station('STATION1', 2020, 2021)
    values_by_year = {item.year: item for item in response.values}
    assert values_by_year[2020].winter_tmin == -1.0
    assert values_by_year[2020].winter_tmax == 4.0


def test_aggregate_southern_summer_crosses_year_boundary(tmp_path):
    repo = CacheRepository(
        stations_index_file=tmp_path / 'stations.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    repo.write_stations([
        {
            'id': 'SOUTH1',
            'name': 'South',
            'latitude': -33.0,
            'longitude': 18.0,
            'elevation': 10.0,
            'mindate': 2020,
            'maxdate': 2023,
        }
    ])
    repo.write_station_data(
        'SOUTH1',
        "\n".join([
            'DATE,ELEMENT,DATA_VALUE',
            '2020-12-15,TMIN,100',
            '2020-12-15,TMAX,300',
            '2021-01-15,TMIN,120',
            '2021-01-15,TMAX,320',
            '2021-02-15,TMIN,140',
            '2021-02-15,TMAX,340',
        ]),
    )
    service = ClimateService(cache_repository=repo, noaa_client=FakeNoaa())
    response = service.analyze_station('SOUTH1', 2020, 2021)
    values_by_year = {item.year: item for item in response.values}
    assert values_by_year[2020].summer_tmin == 12.0
    assert values_by_year[2020].summer_tmax == 32.0


def test_year_mean_uses_month_means_not_all_daily_values(tmp_path):
    repo = CacheRepository(
        stations_index_file=tmp_path / 'stations.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    repo.write_stations([
        {
            'id': 'STATION1',
            'name': 'Alpha',
            'latitude': 48.0,
            'longitude': 8.0,
            'elevation': 700.0,
            'mindate': 2020,
            'maxdate': 2020,
        }
    ])
    repo.write_station_data(
        'STATION1',
        "\n".join([
            'DATE,ELEMENT,DATA_VALUE',
            '2020-01-01,TMIN,0',
            '2020-01-02,TMIN,0',
            '2020-01-03,TMIN,100',
            '2020-02-01,TMIN,200',
            '2020-01-01,TMAX,100',
            '2020-01-02,TMAX,100',
            '2020-01-03,TMAX,200',
            '2020-02-01,TMAX,300',
        ]),
    )
    service = ClimateService(cache_repository=repo, noaa_client=FakeNoaa())
    response = service.analyze_station('STATION1', 2020, 2020)
    value = response.values[0]
    assert value.tmin == 11.7
    assert value.tmax == 21.7


def test_missing_months_leave_empty_season_but_keep_annual_value(tmp_path):
    service = build_service(tmp_path, noaa_client=SparseNoaa())
    response = service.analyze_station('STATION1', 2020, 2020)
    value = response.values[0]
    assert value.has_data is True
    assert value.spring_tmin is None
    assert value.spring_tmax is None
    assert value.autumn_tmin is None
    assert value.autumn_tmax is None
    assert value.tmin == 4.0
    assert value.tmax == 10.0


def test_bounding_box_contains_origin_radius(tmp_path):
    service = build_service(tmp_path)
    min_lat, max_lat, min_lon, max_lon = service._bounding_box(48.0, 8.0, 50)
    assert min_lat < 48.0 < max_lat
    assert min_lon < 8.0 < max_lon


def test_haversine_km_is_zero_for_same_point(tmp_path):
    service = build_service(tmp_path)
    assert service._haversine_km(48.0, 8.0, 48.0, 8.0) == 0.0


def test_get_or_fetch_station_rows_uses_cache_before_downloading(tmp_path):
    class ExplodingNoaa(NoaaClient):
        def stream_station_csv_to_cache(self, station_id: str, cache_file: Path) -> None:
            raise AssertionError('download should not happen')

    service = build_service(tmp_path, noaa_client=ExplodingNoaa())
    service.cache.write_station_data('STATION1', 'DATE,ELEMENT,DATA_VALUE\n2020-01-01,TMIN,10\n')
    rows = service._get_or_fetch_station_rows('STATION1')
    assert rows[0]['ELEMENT'] == 'TMIN'
