from app.repositories.cache_repository import CacheRepository


def test_repository_reads_and_writes_station_index(tmp_path):
    repo = CacheRepository(
        stations_index_file=tmp_path / 'stations.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    payload = [{'id': 'A', 'latitude': 1.0, 'longitude': 2.0, 'mindate': 2000, 'maxdate': 2020, 'name': 'A'}]
    repo.write_stations(payload)
    assert repo.read_stations() == payload


def test_repository_station_data_helpers(tmp_path):
    repo = CacheRepository(
        stations_index_file=tmp_path / 'stations.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    assert repo.has_station_data('A') is False
    repo.write_station_data('A', 'x,y,z')
    assert repo.has_station_data('A') is True
    assert repo.read_station_data('A') == 'x,y,z'


def test_repository_summary_helpers_use_stable_file(tmp_path):
    repo = CacheRepository(
        stations_index_file=tmp_path / 'stations.json',
        station_cache_dir=tmp_path / 'by_station',
        summary_cache_dir=tmp_path / 'summaries',
        raw_dir=tmp_path / 'raw',
    )
    file_a = repo.summary_file('A', 2020, 2021)
    file_b = repo.summary_file('A', 2020, 2021)
    assert file_a == file_b
    repo.write_summary('A', 2020, 2021, {'ok': True})
    assert repo.read_summary('A', 2020, 2021) == {'ok': True}
