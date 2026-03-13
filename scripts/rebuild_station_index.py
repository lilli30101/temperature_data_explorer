"""Optionales Hilfsskript zum Neuerzeugen von data/stations.json aus NOAA-Metadaten.
Es ist für den Betrieb nicht nötig, weil die Anwendung den fertigen Index bereits mitliefert.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

BASE_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "stations.json"


def fetch_text(name: str) -> str:
    response = requests.get(f"{BASE_URL}/{name}", timeout=60)
    response.raise_for_status()
    return response.text


def parse() -> list[dict]:
    stations_text = fetch_text("ghcnd-stations.txt")
    inventory_text = fetch_text("ghcnd-inventory.txt")

    inventory_map: dict[str, dict[str, int]] = {}
    for line in inventory_text.splitlines():
        if not line.strip():
            continue
        element = line[31:35].strip()
        if element not in {"TMIN", "TMAX"}:
            continue
        station_id = line[0:11].strip()
        first_year = int(line[36:40].strip())
        last_year = int(line[41:45].strip())
        target = inventory_map.setdefault(station_id, {"mindate": 9999, "maxdate": 0})
        target["mindate"] = min(target["mindate"], first_year)
        target["maxdate"] = max(target["maxdate"], last_year)

    merged: list[dict] = []
    for line in stations_text.splitlines():
        if not line.strip():
            continue
        station_id = line[0:11].strip()
        inv = inventory_map.get(station_id)
        if not inv:
            continue
        elevation = line[31:37].strip()
        merged.append(
            {
                "id": station_id,
                "name": line[41:71].strip(),
                "latitude": float(line[12:20].strip()),
                "longitude": float(line[21:30].strip()),
                "elevation": None if not elevation or elevation == "-999.9" else float(elevation),
                "mindate": inv["mindate"],
                "maxdate": inv["maxdate"],
            }
        )
    return merged


def rebuild_station_index() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(parse(), separators=(",", ":")), encoding="utf-8")
    return OUT


if __name__ == "__main__":
    out = rebuild_station_index()
    print(f"geschrieben: {out}")
