"""
Maritime Route Optimization Package
==================================

Professional maritime route optimization and weather intelligence platform.
"""

# Import main classes
from .main import MaritimeRouteOptimizer
from .core.models import (
    RouteObjective, RouteConstraints, VesselData, WeatherData, 
    Waypoint, Route, RouteOptimizationResult, NavigationParameters, PerformanceMetrics,
    MaritimeUnits
)
from .data.collectors.ais_collector import AISDataCollector
from .data.processors.ml_processor import MaritimeMLDataProcessor
from .routing.route_optimizer import EnhancedSailingCalculator
from .utils.database import DatabaseManager
from .utils.visualization import MaritimeVisualizer
from .config.settings import settings # Import settings

# Weather API functions (stub implementations)
def fetch_open_meteo_weather(lat, lon, hours=24):
    """Fetch weather from Open-Meteo API"""
    import requests
    import pandas as pd
    try:
        url = "https://marine-api.open-meteo.com/v1/marine"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ["wave_height", "wave_direction", "wind_wave_height", 
                      "ocean_current_velocity", "ocean_current_direction"],
            "forecast_hours": hours
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        hourly_data = data.get('hourly', {})
        
        df = pd.DataFrame({
            'time': pd.to_datetime(hourly_data.get('time', [])),
            'wave_height_m': hourly_data.get('wave_height', []),
            'wave_direction_deg': hourly_data.get('wave_direction', []),
            'wind_wave_height_m': hourly_data.get('wind_wave_height', []),
            'ocean_current_velocity_ms': hourly_data.get('ocean_current_velocity', []),
            'ocean_current_direction_deg': hourly_data.get('ocean_current_direction', [])
        })
        return df
    except Exception as e:
        print(f"Error fetching Open-Meteo data: {e}")
        return pd.DataFrame()

def fetch_tomorrow_io_weather(lat, lon, api_key, hours=24):
    """Fetch weather from Tomorrow.io API"""
    import requests
    import pandas as pd
    try:
        url = f"https://api.tomorrow.io/v4/timelines"
        params = {
            "location": f"{lat},{lon}",
            "fields": ["temperature", "windSpeed", "precipitationIntensity", "humidity",
                      "waveSignificantHeight", "seaCurrentSpeed", "seaCurrentDirection"],
            "timesteps": "1h",
            "units": "metric",
            "apikey": api_key
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        intervals = data.get('data', {}).get('timelines', [{}])[0].get('intervals', [])
        
        weather_data = []
        for interval in intervals[:hours]:
            values = interval.get('values', {})
            weather_data.append({
                'time': pd.to_datetime(interval.get('startTime')),
                'temperature_c': values.get('temperature'),
                'wind_speed_ms': values.get('windSpeed'),
                'precipitation_intensity': values.get('precipitationIntensity'),
                'humidity_percent': values.get('humidity'),
                'wave_significant_height_m': values.get('waveSignificantHeight'),
                'sea_current_speed_ms': values.get('seaCurrentSpeed'),
                'sea_current_direction_deg': values.get('seaCurrentDirection')
            })
        return pd.DataFrame(weather_data)
    except Exception as e:
        print(f"Error fetching Tomorrow.io data: {e}")
        return pd.DataFrame()

def load_data_from_db():
    """Load data from database"""
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    
    db = DatabaseManager()
    weather_data = db.get_weather_forecast(37.5, -122.5, 24)
    ais_data = db.get_recent_vessels(10)
    
    # Convert to DataFrames if they're lists
    if isinstance(weather_data, list):
        if weather_data:
            # Convert list of WeatherData objects to DataFrame
            weather_dicts = []
            for w in weather_data:
                weather_dicts.append({
                    'latitude': w.latitude,
                    'longitude': w.longitude,
                    'wave_height_m': w.wave_height_m,
                    'wind_speed_kts': w.wind_speed_kts,
                    'wind_direction_deg': w.wind_direction_deg,
                    'temperature_c': w.temperature_c,
                    'ocean_current_speed_kts': w.ocean_current_speed_kts,
                    'ocean_current_direction_deg': w.ocean_current_direction_deg,
                    'timestamp': w.timestamp
                })
            weather_data = pd.DataFrame(weather_dicts)
        else:
            # Create sample weather data
            weather_data = pd.DataFrame({
                'latitude': [37.5] * 24,
                'longitude': [-122.5] * 24,
                'wave_height_m': np.random.uniform(0.5, 3.0, 24),
                'wind_speed_kts': np.random.uniform(5, 25, 24),
                'wind_direction_deg': np.random.uniform(0, 360, 24),
                'temperature_c': np.random.uniform(15, 25, 24),
                'ocean_current_speed_kts': np.random.uniform(0.2, 2.0, 24),
                'ocean_current_direction_deg': np.random.uniform(0, 360, 24),
                'timestamp': [datetime.now() + timedelta(hours=i) for i in range(24)]
            })
    
    if isinstance(ais_data, list):
        if ais_data:
            # Convert list of VesselData objects to DataFrame
            vessel_dicts = []
            for v in ais_data:
                vessel_dicts.append({
                    'mmsi': v.mmsi,
                    'name': v.name,
                    'latitude': v.latitude,
                    'longitude': v.longitude,
                    'speed': v.speed,
                    'course': v.course,
                    'heading': v.heading,
                    'timestamp': v.timestamp
                })
            ais_data = pd.DataFrame(vessel_dicts)
        else:
            # Create sample AIS data
            ais_data = pd.DataFrame({
                'mmsi': [123456789, 987654321, 456789123],
                'name': ['Cargo Ship Alpha', 'Tanker Beta', 'Ferry Gamma'],
                'latitude': [37.7749, 37.7849, 37.7649],
                'longitude': [-122.4194, -122.4094, -122.4294],
                'speed': [12.5, 8.2, 15.8],
                'course': [45.0, 90.0, 180.0],
                'heading': [45.0, 90.0, 180.0],
                'timestamp': [datetime.now()] * 3
            })
    
    return weather_data, ais_data

def optimize_route(start_lat, start_lon, end_lat, end_lon, model, scaler, weather_data):
    """Optimize route using ML model or fallback to basic calculation"""
    calc = EnhancedSailingCalculator(settings)
    waypoints = calc.generate_waypoints(start_lat, start_lon, end_lat, end_lon, 15)
    
    # Apply land avoidance to generated waypoints
    waypoints = calc.avoid_land_waypoints(waypoints)
    
    return [(wp.latitude, wp.longitude) for wp in waypoints]

def prepare_ml_data(weather_data, ais_data):
    """Prepare data for ML training"""
    if weather_data.empty or ais_data.empty:
        return None, None
    
    # Simple feature preparation
    features = []
    targets = []
    
    for idx, vessel in ais_data.iterrows():
        feature_vector = [
            vessel.get('latitude', 0),
            vessel.get('longitude', 0),
            vessel.get('speed', 0),
            vessel.get('course', 0)
        ]
        features.append(feature_vector)
        targets.append(vessel.get('speed', 10))  # Target: optimal speed
    
    import numpy as np
    return np.array(features), np.array(targets)

def train_route_optimization_model(X, y):
    """Train ML model for route optimization"""
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    
    if X is None or y is None:
        return None, None
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = RandomForestRegressor(n_estimators=100, random_state=settings.RANDOM_STATE)
    model.fit(X_scaled, y)
    
    return model, scaler

def combine_weather_data(open_meteo, tomorrow):
    """Combine weather data from both sources"""
    import pandas as pd
    
    if open_meteo.empty and tomorrow.empty:
        return pd.DataFrame()
    if open_meteo.empty:
        return tomorrow
    if tomorrow.empty:
        return open_meteo
    
    # Simple merge on time
    open_meteo['time'] = pd.to_datetime(open_meteo['time']).dt.tz_localize(None)
    tomorrow['time'] = pd.to_datetime(tomorrow['time']).dt.tz_localize(None)
    
    combined = pd.merge(open_meteo, tomorrow, on='time', how='outer', suffixes=('_openmeteo', '_tomorrow'))
    return combined

def store_weather_data(weather_data):
    """Store weather data in database"""
    db = DatabaseManager()
    if not weather_data.empty:
        for _, row in weather_data.iterrows():
            weather = WeatherData(
                latitude=row.get('latitude', 37.5),
                longitude=row.get('longitude', -122.5),
                wave_height_m=row.get('wave_height_m', 1.0),
                wind_speed_kts=row.get('wind_speed_ms', 5.0) * 1.944,  # Convert m/s to knots
                wind_direction_deg=row.get('wind_direction_deg', 180.0),
                temperature_c=row.get('temperature_c', 20.0),
                ocean_current_speed_kts=row.get('ocean_current_velocity_ms', 0.5) * 1.944,
                ocean_current_direction_deg=row.get('ocean_current_direction_deg', 180.0)
            )
            db.save_weather_data([weather])
    return True

def store_ais_data(ais_data):
    """Store AIS data in database"""
    db = DatabaseManager()
    if ais_data:
        for vessel in ais_data:
            vessel_data = VesselData(
                mmsi=vessel.get('mmsi', 0),
                name=vessel.get('name', 'Unknown'),
                latitude=vessel.get('latitude', 0),
                longitude=vessel.get('longitude', 0),
                speed=vessel.get('speed', 0),
                course=vessel.get('course', 0),
                heading=vessel.get('heading', 0),
                timestamp=vessel.get('timestamp', '2024-01-01T00:00:00')
            )
            db.save_vessel_data([vessel_data])
    return True

def setup_database():
    """Setup database tables"""
    db = DatabaseManager()
    return True

def plot_optimized_route(route, vessels):
    """Plot optimized route"""
    import matplotlib.pyplot as plt
    
    if not route:
        return
    
    plt.figure(figsize=(10, 8))
    
    # Plot route
    route_lats, route_lons = zip(*route)
    plt.plot(route_lons, route_lats, 'b-', linewidth=3, alpha=0.8, label='Optimized Route')
    plt.scatter(route_lons, route_lats, c='blue', s=100, alpha=1.0, label='Waypoints')
    
    # Plot vessels if available
    if vessels and not vessels.empty:
        plt.scatter(vessels['longitude'], vessels['latitude'], 
                   c='red', s=50, alpha=0.6, label='Vessels')
    
    plt.title('Optimized Maritime Route')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

def compute_averages(weather_data, ais_data):
    """Compute data averages"""
    print("\n📊 MARITIME DATA ANALYSIS REPORT")
    print("=" * 50)
    
    if not weather_data.empty:
        print("\n🌊 WEATHER CONDITIONS:")
        numeric_cols = weather_data.select_dtypes(include=['number']).columns
        for col in numeric_cols:
            if weather_data[col].notna().any():
                avg_val = weather_data[col].mean()
                print(f"  Average {col}: {avg_val:.2f}")
    
    if not ais_data.empty:
        print("\n🚢 VESSEL ACTIVITY:")
        print(f"  Total vessels tracked: {len(ais_data)}")
        if 'speed' in ais_data.columns:
            avg_speed = ais_data['speed'].mean()
            print(f"  Average vessel speed: {avg_speed:.2f} knots")

def plot_vessel_positions(ais_data, weather_data):
    """Plot vessel positions"""
    import matplotlib.pyplot as plt
    
    if ais_data.empty:
        print("No AIS data to plot")
        return
    
    plt.figure(figsize=(12, 8))
    scatter = plt.scatter(
        ais_data['longitude'], 
        ais_data['latitude'],
        c=ais_data.get('speed', 10),
        cmap='viridis',
        s=100,
        alpha=0.7
    )
    
    plt.title('Vessel Positions (Colored by Speed)')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.colorbar(scatter, label='Speed (knots)')
    plt.grid(True, alpha=0.3)
    plt.show()
