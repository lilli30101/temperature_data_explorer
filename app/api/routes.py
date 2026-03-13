from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.models.schemas import ClimateAnalysisResponse, HealthResponse, Station, StationSearchRequest
from app.services.climate_service import ClimateService

router = APIRouter()
service = ClimateService()


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status='ok')


@router.get('/stations', response_model=list[Station])
def search_stations(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: int = Query(100, gt=0, le=settings.max_search_radius_km),
    limit: int = Query(10, gt=0, le=settings.max_station_limit),
    start_year: int = Query(..., ge=1700, le=2100),
    end_year: int = Query(..., ge=1700, le=2100),
) -> list[Station]:
    try:
        request = StationSearchRequest(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
            start_year=start_year,
            end_year=end_year,
        )
        return service.search_stations(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/stations/{station_id}/analysis', response_model=ClimateAnalysisResponse)
def analyze_station(
    station_id: str,
    start_year: int = Query(..., ge=1700, le=2027),
    end_year: int = Query(..., ge=1700, le=2027),
) -> ClimateAnalysisResponse:
    try:
        return service.analyze_station(station_id, start_year, end_year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
