from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from functools import lru_cache

from app.core.config import settings
from app.models.schemas import ClimateAnalysisResponse, ClimateSeriesPoint, Station, StationSearchRequest
from app.repositories.cache_repository import CacheRepository
from app.services.noaa_client import NoaaClient

NORTHERN_SEASON_MONTHS = {
    'spring': {3, 4, 5},
    'summer': {6, 7, 8},
    'autumn': {9, 10, 11},
    'winter': {12, 1, 2},
}

SOUTHERN_SEASON_MONTHS = {
    'spring': {9, 10, 11},
    'summer': {12, 1, 2},
    'autumn': {3, 4, 5},
    'winter': {6, 7, 8},
}


class ClimateService:
    def __init__(self, cache_repository: CacheRepository | None = None, noaa_client: NoaaClient | None = None):
        self.cache = cache_repository or CacheRepository()
        self.noaa = noaa_client or NoaaClient()

    def search_stations(self, request: StationSearchRequest) -> list[Station]:
        if request.start_year > request.end_year:
            raise ValueError('start_year darf nicht größer als end_year sein.')
        if request.radius_km > settings.max_search_radius_km:
            raise ValueError(f'radius_km darf maximal {settings.max_search_radius_km} km sein.')
        result = self._search_stations_cached(
            round(request.latitude, 4),
            round(request.longitude, 4),
            request.radius_km,
            min(request.limit, settings.max_station_limit),
            request.start_year,
            request.end_year,
        )
        return [Station(**item) for item in result]

    def analyze_station(self, station_id: str, start_year: int, end_year: int) -> ClimateAnalysisResponse:
        if start_year > end_year:
            raise ValueError('start_year darf nicht größer als end_year sein.')

        cached_summary = self.cache.read_summary(station_id, start_year, end_year)
        if cached_summary:
            return ClimateAnalysisResponse(**cached_summary)

        response = self._analyze_station_cached(station_id, start_year, end_year)
        self.cache.write_summary(station_id, start_year, end_year, response.model_dump())
        return response

    @lru_cache(maxsize=settings.in_memory_search_cache_size)
    def _search_stations_cached(
        self,
        latitude: float,
        longitude: float,
        radius_km: int,
        limit: int,
        start_year: int,
        end_year: int,
    ) -> tuple[dict, ...]:
        results: list[dict] = []
        min_lat, max_lat, min_lon, max_lon = self._bounding_box(latitude, longitude, radius_km)
        for raw_station in self._get_station_index():
            if not (start_year >= raw_station['mindate'] and end_year <= raw_station['maxdate']):
                continue
            station_lat = raw_station['latitude']
            station_lon = raw_station['longitude']
            if not (min_lat <= station_lat <= max_lat and min_lon <= station_lon <= max_lon):
                continue
            distance = self._haversine_km(latitude, longitude, station_lat, station_lon)
            if distance <= radius_km:
                entry = dict(raw_station)
                entry['distance_km'] = round(distance, 2)
                results.append(entry)
        results.sort(key=lambda item: item['distance_km'])
        return tuple(results[:limit])

    @lru_cache(maxsize=settings.in_memory_summary_cache_size)
    def _analyze_station_cached(self, station_id: str, start_year: int, end_year: int) -> ClimateAnalysisResponse:
        rows = self._get_or_fetch_station_rows(station_id)
        station_latitude = self._get_station_latitude(station_id)
        values = self._aggregate(rows, start_year, end_year, station_latitude)
        return ClimateAnalysisResponse(
            station_id=station_id,
            start_year=start_year,
            end_year=end_year,
            missing_data_rule=(
                'Sobald für ein Jahr bzw. eine Saison NOAA-Daten vorliegen, wird ein Mittelwert angezeigt. '
                'Lücken im Diagramm bedeuten, dass für diesen Zeitraum gar keine TMIN- bzw. TMAX-Werte vorlagen. '
            ),
            values=values,
        )

    def _get_station_index(self) -> list[dict]:
        cached = self.cache.read_stations()
        if cached:
            return cached
        raise FileNotFoundError('stations.json fehlt. Das Projekt wird mit vorgebautem NOAA-Stationsindex ausgeliefert.')

    def _get_or_fetch_station_rows(self, station_id: str):
        station_file = self.cache.station_file(station_id)
        if not station_file.exists():
            self.noaa.stream_station_csv_to_cache(station_id, station_file)
        csv_text = station_file.read_text(encoding='utf-8')
        return list(self.noaa.parse_station_csv(csv_text))

    def _aggregate(self, rows: list[dict], start_year: int, end_year: int, station_latitude: float | None = None) -> list[ClimateSeriesPoint]:
        season_months = self._season_months_for_latitude(station_latitude)

        annual_monthly_values: dict[int, dict] = defaultdict(lambda: defaultdict(lambda: {"tmin": [], "tmax": []}))
        seasonal_monthly_values: dict[int, dict] = defaultdict(
            lambda: {
                'spring': defaultdict(lambda: {'tmin': [], 'tmax': []}),
                'summer': defaultdict(lambda: {'tmin': [], 'tmax': []}),
                'autumn': defaultdict(lambda: {'tmin': [], 'tmax': []}),
                'winter': defaultdict(lambda: {'tmin': [], 'tmax': []}),
            }
        )
        yearly_counts: dict[int, dict] = defaultdict(
            lambda: {
                'year': {'tmin': 0, 'tmax': 0},
                'spring': {'tmin': 0, 'tmax': 0},
                'summer': {'tmin': 0, 'tmax': 0},
                'autumn': {'tmin': 0, 'tmax': 0},
                'winter': {'tmin': 0, 'tmax': 0},
            }
        )

        for row in rows:
            date_str = row.get('DATE')
            element = row.get('ELEMENT')
            value = row.get('DATA_VALUE')
            if element not in {'TMIN', 'TMAX'} or not date_str or value in {None, '', 'NA', '-9999'}:
                continue
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                numeric_value = int(value) / 10
            except ValueError:
                continue

            metric = element.lower()

            # Jahreswerte: immer nur Januar bis Dezember des tatsächlichen Jahres.
            if start_year <= date.year <= end_year:
                annual_monthly_values[date.year][date.month][metric].append(numeric_value)
                yearly_counts[date.year]['year'][metric] += 1

            # Saisonwerte: Frühling/Sommer/Herbst bleiben im gleichen Jahr.
            # Nur der Winter darf jahresübergreifend sein.
            for season, months in season_months.items():
                if date.month not in months:
                    continue

                if season == 'winter':
                    if station_latitude is not None and station_latitude < 0:
                        season_year = date.year
                    else:
                        season_year = date.year if date.month == 12 else date.year - 1
                elif season == 'summer' and station_latitude is not None and station_latitude < 0:
                    season_year = date.year if date.month == 12 else date.year - 1
                else:
                    season_year = date.year

                if not (start_year <= season_year <= end_year):
                    break

                month_key = (date.year, date.month)
                seasonal_monthly_values[season_year][season][month_key][metric].append(numeric_value)
                yearly_counts[season_year][season][metric] += 1
                break

        output: list[ClimateSeriesPoint] = []
        for year in range(start_year, end_year + 1):
            expected_days = 366 if self._is_leap_year(year) else 365

            year_tmin_count = yearly_counts[year]['year']['tmin']
            year_tmax_count = yearly_counts[year]['year']['tmax']
            annual_tmin_coverage = round((year_tmin_count / expected_days) * 100, 1) if year_tmin_count else 0.0
            annual_tmax_coverage = round((year_tmax_count / expected_days) * 100, 1) if year_tmax_count else 0.0

            tmin = self._mean_from_calendar_months(annual_monthly_values[year], 'tmin')
            tmax = self._mean_from_calendar_months(annual_monthly_values[year], 'tmax')
            spring_tmin = self._mean_from_months(seasonal_monthly_values[year]['spring'], 'tmin')
            spring_tmax = self._mean_from_months(seasonal_monthly_values[year]['spring'], 'tmax')
            summer_tmin = self._mean_from_months(seasonal_monthly_values[year]['summer'], 'tmin')
            summer_tmax = self._mean_from_months(seasonal_monthly_values[year]['summer'], 'tmax')
            autumn_tmin = self._mean_from_months(seasonal_monthly_values[year]['autumn'], 'tmin')
            autumn_tmax = self._mean_from_months(seasonal_monthly_values[year]['autumn'], 'tmax')
            winter_tmin = self._mean_from_months(seasonal_monthly_values[year]['winter'], 'tmin')
            winter_tmax = self._mean_from_months(seasonal_monthly_values[year]['winter'], 'tmax')

            output.append(ClimateSeriesPoint(
                year=year,
                has_data=any(
                    value is not None
                    for value in [tmin, tmax, spring_tmin, spring_tmax, summer_tmin, summer_tmax, autumn_tmin, autumn_tmax, winter_tmin, winter_tmax]
                ),
                tmin=tmin,
                tmax=tmax,
                spring_tmin=spring_tmin,
                spring_tmax=spring_tmax,
                summer_tmin=summer_tmin,
                summer_tmax=summer_tmax,
                autumn_tmin=autumn_tmin,
                autumn_tmax=autumn_tmax,
                winter_tmin=winter_tmin,
                winter_tmax=winter_tmax,
                annual_tmin_coverage=annual_tmin_coverage,
                annual_tmax_coverage=annual_tmax_coverage,
            ))
        return output


    def _get_station_latitude(self, station_id: str) -> float | None:
        for station in self._get_station_index():
            if station.get('id') == station_id:
                latitude = station.get('latitude')
                return float(latitude) if latitude is not None else None
        return None

    @staticmethod
    def _season_months_for_latitude(station_latitude: float | None) -> dict[str, set[int]]:
        if station_latitude is not None and station_latitude < 0:
            return SOUTHERN_SEASON_MONTHS
        return NORTHERN_SEASON_MONTHS

    def _mean_from_months(self, monthly_values: dict[tuple[int, int], dict[str, list[float]]], metric: str) -> float | None:
        month_means: list[float] = []
        for _, values_by_metric in sorted(monthly_values.items()):
            values = values_by_metric.get(metric, [])
            if values:
                month_means.append(sum(values) / len(values))
        return round(sum(month_means) / len(month_means), 1) if month_means else None

    def _mean_from_calendar_months(self, monthly_values: dict[int, dict[str, list[float]]], metric: str) -> float | None:
        month_means: list[float] = []
        for month in range(1, 13):
            values = monthly_values.get(month, {}).get(metric, [])
            if values:
                month_means.append(sum(values) / len(values))
        return round(sum(month_means) / len(month_means), 1) if month_means else None

    @staticmethod
    def _is_leap_year(year: int) -> bool:
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    @staticmethod
    def _bounding_box(latitude: float, longitude: float, radius_km: float) -> tuple[float, float, float, float]:
        lat_delta = radius_km / 111.0
        cos_lat = max(math.cos(math.radians(latitude)), 0.01)
        lon_delta = radius_km / (111.320 * cos_lat)
        return latitude - lat_delta, latitude + lat_delta, longitude - lon_delta, longitude + lon_delta

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return radius * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
