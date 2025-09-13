# Maritime Route Optimization - Documentation

## Overview
A professional web application for maritime route optimization, weather intelligence, and fleet awareness. Backend: FastAPI. Frontend: HTML/JS with Leaflet. Real-time: WebSockets. Now features advanced land avoidance, adherence to TSS, UKC and squat calculations, and avoidance of various coastal hazards using pre-downloaded GeoJSON nautical chart data.

## Quick Start
1. Create environment file:
```bash
cp .env.example .env
# Edit .env with your API keys
```
2. Install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
3. Run the web app:
```bash
python3 run_web_app.py
# or
uvicorn web_app:app --host 0.0.0.0 --port 8000
```

## Configuration (Pydantic Settings)
All configuration is centralized in `maritime_app/config/settings.py` and loaded from `.env`.

Required keys in `.env`:
```env
AISSTREAM_API_KEY="..."
TOMORROW_IO_API_KEY="..."
OPEN_METEO_API_KEY=""
```
Important settings and defaults:
- `DATABASE_PATH` (default: `maritime.db`)
- `WEB_HOST` (default: `0.0.0.0`), `WEB_PORT` (default: `8000`)
- `DEFAULT_LAT`, `DEFAULT_LON` (demo map center)
- `EARTH_RADIUS_NM` (3440.065)
- `WEATHER_FORECAST_HOURS` (72)
- `MIN_OFFING_NM` (3.0)
- `DEFAULT_VESSEL_DRAFT_M` (10.5)
- `UKC_DEFAULT_M` (0.6)
- `TSS_ENFORCEMENT` ("enforce" | "prefer")
- `OPTIMIZE_INSIDE_PILOTAGE` (False)
- `CHARTS_DIR` (default: `maritime_app/charts`)
- `MARITIME_DATA_JSON` (default: `maritime_data.json`)
- `COASTLINES_GEOJSON` (default: `ne_10m_coastline.json`)
- `CACHED_LAND_BUFFER_GEOJSON` (default: `_cached_land_buffer.json`)
- `TSS_CORRIDORS_GEOJSON` (default: `noaa_tss_corridors.json`)
- `SEA_BUOYS_GEOJSON` (default: `noaa_sea_buoys.json`)
- `PILOTAGE_ZONES_GEOJSON` (default: `noaa_pilotage_zones.json`)
- `RESTRICTED_AREAS_GEOJSON` (default: `noaa_restricted_areas.json`)
- `DEPTH_AREAS_GEOJSON` (default: `noaa_depth_areas.json`)
- `WRECKS_OBSTRUCTIONS_GEOJSON` (default: `noaa_wrecks_obstructions.json`)
- `PIPELINES_CABLES_GEOJSON` (default: `noaa_pipelines_cables.json`)
- `SAFETY_DEPTH_MARGIN_M` (2.0)

Access in code:
```python
from maritime_app.config.settings import settings
print(settings.AISSTREAM_API_KEY)
```

## REST API
Base URL: `http://localhost:8000`

### GET `/` (HTML)
- Returns the main web UI.

### GET `/api/health`
- Returns system health and basic counters.
- Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-13T12:34:56",
  "models_loaded": true,
  "weather_data_points": 1200,
  "ais_vessels": 44
}
```

### POST `/api/routes/optimize`
- Optimize a maritime route.
- Body (JSON):
```json
{
  "start_lat": 37.7749,
  "start_lon": -122.4194,
  "end_lat": 34.0522,
  "end_lon": -118.2437,
  "priority": "balanced"
}
```
- Response:
```json
{
  "route": [[37.7,-122.4], [36.9,-121.8], ...],
  "total_distance_nm": 347.2,
  "estimated_time_hours": 23.1,
  "estimated_fuel_tons": 8.7,
  "waypoints_count": 16,
  "optimization_priority": "balanced",
  "timestamp": "2025-09-13T12:34:56"
}
```

### GET `/api/weather/current`
- Query params: `lat`, `lon` (defaults from settings)
- Returns nearest weather sample or a fallback sample.

### GET `/api/vessels/nearby`
- Query params: `lat`, `lon`, `radius_nm` (default: 50)
- Returns vessels near the point with approximate distances.

### POST `/api/data/refresh`
- Refresh AIS and weather data, retrain ML if possible, and broadcast updates.
- Response includes counts.

### GET `/api/performance/metrics`
- Returns model/training and system metrics.

## WebSocket API
URL: `ws://localhost:8000/ws/updates`

- Messages broadcast by server:
  - `{"type":"route_optimized","data":{...}}`
  - `{"type":"data_refreshed","timestamp":"...","weather_points":123,"ais_vessels":44}`

- Example client:
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/updates");
ws.onmessage = (e) => console.log("WS:", e.data);
ws.onopen = () => ws.send("hello"); // echo test
```

## Data & Models
- Database: default SQLite at `DATABASE_PATH`.
- ML: RandomForest models trained during startup/refresh if data exists.
- Routing: Great-circle fallback via `EnhancedSailingCalculator` when ML not available. Now leverages pre-downloaded GeoJSON nautical chart data for enhanced land avoidance, TSS adherence, UKC/squat calculations, and avoidance of restricted areas, shallow depths, wrecks, obstructions, pipelines, and cables.

## Security
- No secrets in code. Use `.env` (not committed).
- Settings validated via Pydantic.
- Implemented secure configuration management. Future steps include security headers, auth (Google OAuth), and enhanced logging and testing.

## Troubleshooting
- If `uvicorn` not found: `pip install -r requirements.txt`
- If startup fails due to missing keys: ensure `.env` exists and is loaded.
- Health check: `curl http://localhost:8000/api/health`
- If chart data loading issues occur: verify `maritime_app/charts/maritime_data.json` exists and references valid GeoJSON files. Ensure `_cached_land_buffer.json` is present or can be generated.

## License
TBD.
