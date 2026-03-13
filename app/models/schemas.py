from typing import Literal

from pydantic import BaseModel, Field


class Station(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    elevation: float | None = None
    mindate: int
    maxdate: int
    distance_km: float | None = None


class StationSearchRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: int = Field(ge=1, le=100)
    limit: int = Field(gt=0, le=25)
    start_year: int = Field(ge=1700, le=2100)
    end_year: int = Field(ge=1700, le=2100)


class ClimateSeriesPoint(BaseModel):
    year: int
    has_data: bool = False
    tmin: float | None = None
    tmax: float | None = None
    spring_tmin: float | None = None
    spring_tmax: float | None = None
    summer_tmin: float | None = None
    summer_tmax: float | None = None
    autumn_tmin: float | None = None
    autumn_tmax: float | None = None
    winter_tmin: float | None = None
    winter_tmax: float | None = None
    annual_tmin_coverage: float = 0.0
    annual_tmax_coverage: float = 0.0


class ClimateAnalysisResponse(BaseModel):
    station_id: str
    start_year: int
    end_year: int
    missing_data_rule: str
    values: list[ClimateSeriesPoint]


class HealthResponse(BaseModel):
    status: Literal['ok']
