# Climate Data Analyzer

Diese Version enthält bereits einen vorgebauten `stations.json`-Index auf Basis der offiziellen NOAA-GHCN-Metadaten für `TMIN` und `TMAX`.
Dadurch entfällt der langsame Erstaufbau des Stations-Caches. Es wird weiterhin keine Datenbank verwendet.

## Starten

```powershell
cd generated_climate_project
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Dann im Browser öffnen:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

## Architektur

- `data/stations.json`: vorgebauter lokaler NOAA-Metadatenindex
- `data/by_station/<id>.csv`: lokaler Cache für on-demand geladene Stationsdaten
- `data/summaries/*.json`: lokaler Cache für Auswertungen
- keine Datenbank

## Warum diese Lösung schneller ist

Die Stationssuche arbeitet direkt auf dem lokal mitgelieferten `stations.json`-Index.
Nur bei der eigentlichen Auswertung einer ausgewählten Station werden Tagesdaten von NOAA geladen und lokal gespeichert.

## Datenquelle

- NOAA GHCN Daily
- primär: `https://www.ncei.noaa.gov/pub/data/ghcn/daily`
- sekundär: `https://noaa-ghcn-pds.s3.amazonaws.com`
