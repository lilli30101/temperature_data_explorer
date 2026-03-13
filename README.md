# Temperature Data Explorer

Dieses Projekt stellt historische Temperaturdaten über eine FastAPI-Webanwendung bereit. Die Anwendung ist containerisiert und kann lokal über Docker Compose oder automatisiert über GitHub Actions gebaut und veröffentlicht werden.

## Lokaler Start ohne Container

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Danach im Browser öffnen:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

## Lokaler Start mit Docker Compose

```powershell
docker compose up --build
```

## Installation über Container Registry

Sobald die GitHub Actions Pipeline erfolgreich gelaufen ist, steht das Container-Image in der GitHub Container Registry bereit.

```powershell
docker compose up -d
```

Die Installationskonfiguration dafür liegt in `compose.yaml`.

## CI/CD

Die Pipeline liegt unter `.github/workflows/ci-cd.yml` und führt bei jedem Push oder Pull Request automatisiert Tests aus. Bei einem Push auf `main` wird zusätzlich ein Container-Image gebaut und nach `ghcr.io/lilli30101/temperature_data_explorer` veröffentlicht.

## Architektur

- `data/stations.json`: vorgebauter lokaler NOAA-Metadatenindex
- `data/by_station/<id>.csv`: lokaler Cache für on-demand geladene Stationsdaten
- `data/summaries/*.json`: lokaler Cache für Auswertungen
- keine Datenbank

## Datenquelle

- NOAA GHCN Daily
- primär: `https://www.ncei.noaa.gov/pub/data/ghcn/daily`
- sekundär: `https://noaa-ghcn-pds.s3.amazonaws.com`
