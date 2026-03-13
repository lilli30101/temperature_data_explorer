from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Climate Data Analyzer"
    debug: bool = False

    data_dir: Path = BASE_DIR / "data"
    cache_dir: Path = BASE_DIR / "data"
    stations_index_file: Path = BASE_DIR / "data" / "stations.json"
    station_cache_dir: Path = BASE_DIR / "data" / "by_station"
    summary_cache_dir: Path = BASE_DIR / "data" / "summaries"
    raw_dir: Path = BASE_DIR / "data" / "raw"

    bundled_stations_index_file: Path = BASE_DIR / "data" / "stations.json"

    noaa_primary_base_url: str = "https://www.ncei.noaa.gov/pub/data/ghcn/daily"
    noaa_secondary_base_url: str = "https://noaa-ghcn-pds.s3.amazonaws.com"
    request_timeout_seconds: int = 20

    max_station_limit: int = 75
    max_search_radius_km: int = 100
    default_missing_coverage_ratio: float = 0.8

    in_memory_search_cache_size: int = 128
    in_memory_summary_cache_size: int = 256

    model_config = SettingsConfigDict(env_prefix="CLIMATE_", extra="ignore")


settings = Settings()
