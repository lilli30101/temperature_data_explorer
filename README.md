# Temperature Data Explorer

Temperature Data Explorer ist eine containerisierte FastAPI-Webanwendung zur Suche, Analyse und Visualisierung historischer Temperaturdaten. Die Anwendung greift auf NOAA-GHCN-Daten zu, sucht Wetterstationen in einem frei wählbaren Umkreis und bereitet Temperaturverläufe übersichtlich in Karte, Diagramm und Tabelle auf.

## Was die Anwendung bietet

- Suche nach Wetterstationen über Breitengrad, Längengrad und Radius
- Auswahl mehrerer Stationen in einem definierten Suchgebiet
- Auswertung historischer Temperaturdaten über frei wählbare Zeiträume
- Visualisierung der Ergebnisse in Karte, Diagramm und Tabelle
- Containerisierte Bereitstellung mit Docker
- Automatisiertes Bauen und Veröffentlichen über GitHub Actions

## Voraussetzungen

Für den einfachsten Start werden nur diese Programme benötigt:

- Git
- Docker Desktop

## Schnellstart mit Git und Docker

### 1. Repository klonen

```powershell
git clone https://github.com/lilli30101/temperature_data_explorer.git
cd temperature_data_explorer
```

### 2. Anwendung starten

Variante A: Vorgefertigtes Container-Image aus der GitHub Container Registry verwenden

```powershell
docker compose -f compose.yaml up -d
```

Variante B: Image lokal selbst bauen

```powershell
docker compose up --build
```

### 3. Anwendung im Browser öffnen

- Anwendung: http://localhost:8000/
- API-Dokumentation: http://localhost:8000/docs

### 4. Anwendung wieder stoppen

```powershell
docker compose -f compose.yaml down
```

Wenn die Anwendung mit lokalem Build gestartet wurde, kann sie alternativ auch so gestoppt werden:

```powershell
docker compose down
```

## Lokale Entwicklung ohne Docker

Falls die Anwendung lokal ohne Container ausgeführt werden soll:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Danach ist die Anwendung ebenfalls unter `http://localhost:8000/` erreichbar.

## Installationsvarianten

### compose.yaml

`compose.yaml` verwendet das bereits veröffentlichte Container-Image aus der GitHub Container Registry. Diese Variante ist besonders geeignet, wenn andere Personen die Anwendung schnell starten sollen, ohne sie lokal neu zu bauen.

### docker-compose.yml

`docker-compose.yml` baut das Image lokal aus dem Quellcode. Diese Variante eignet sich für Entwicklung, Anpassungen oder Tests mit aktuellen lokalen Änderungen.

## Projektstruktur

```text
app/                    Anwendungscode und API
app/api/                Routen und Endpunkte
app/services/           Fachlogik und Auswertung
app/static/             CSS und JavaScript
app/templates/          HTML-Oberfläche
data/                   Lokale Daten, Caches und Stationsindex
scripts/                Hilfsskripte
tests/                  Automatisierte Tests
.github/workflows/      CI/CD-Pipeline mit GitHub Actions
compose.yaml            Start über veröffentlichtes Registry-Image
docker-compose.yml      Start mit lokalem Build
Dockerfile              Container-Beschreibung
```

## Datenhaltung

Die Anwendung nutzt lokale Dateien zur Zwischenspeicherung und benötigt keine separate Datenbank.

Wichtige Datenpfade:

- `data/stations.json` für den lokalen Stationsindex
- `data/by_station/` für geladene Stationsdaten je Wetterstation
- `data/summaries/` für vorberechnete Auswertungen
- `data/raw/` für Rohdaten und temporäre Ablagen

## CI/CD

Die CI/CD-Pipeline liegt unter `.github/workflows/ci-cd.yml`.

Sie übernimmt automatisch:

- Ausführen der Tests bei Push und Pull Request
- Bauen des Container-Images
- Veröffentlichen des Images in der GitHub Container Registry bei Push auf `main`

## Verwendete Technologien

- Python 3.12
- FastAPI
- Uvicorn
- Docker und Docker Compose
- GitHub Actions
- GitHub Container Registry
- Chart.js
- Leaflet

## Datenquelle

Die Anwendung basiert auf NOAA GHCN Daily.

Verwendete Quellen:

- https://www.ncei.noaa.gov/pub/data/ghcn/daily
- https://noaa-ghcn-pds.s3.amazonaws.com

## Hinweise zur Nutzung

- Im Browser muss `http://localhost:8000/` geöffnet werden, nicht nur `localhost`.
- Das Projekt sollte nicht in geschützte Windows-Ordner wie `C:\Windows\System32` geklont werden, da dort Zugriffsprobleme bei gemounteten Datenordnern auftreten können.
- Falls Port 8000 bereits belegt ist, muss der belegende Prozess beendet oder das Port-Mapping in der Compose-Datei angepasst werden.

## Testen

Die Tests können lokal mit folgendem Befehl ausgeführt werden:

```powershell
pytest
```

## Autoren

Malte Ade
Lilli Franz
Madeleine Notheis
Katharina Raible
