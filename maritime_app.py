import requests
import websocket
import json
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import networkx as nx
from typing import List, Dict, Any, Optional
import threading
import queue
import math
from dataclasses import dataclass
from enum import Enum
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# DETECTIVE WORK: COLLECTING CLUES (DATA FETCHING)
# ==========================================
"""
This section is like collecting evidence at a crime scene.
We gather data from multiple sources to understand the maritime environment.
"""

# API Keys - Replace with your actual keys
AISSTREAM_API_KEY = "911f6137097e02a129da0e1a60a5999e193f45b3"  # Get from aisstream.io
TOMORROW_IO_API_KEY = "xHCjSZ79QhO9KWq3Lubr9wb081zzrgK1"  # Get from tomorrow.io

# Bounding box for San Francisco Bay (expanded to capture more vessels)
SF_BAY_BOUNDS = {
    "north": 38.5,
    "south": 36.5,
    "east": -121.5,
    "west": -123.5
}

# Test location for weather data
TEST_LAT = 37.5
TEST_LON = -122.5

class AISDataCollector:
    """Handles AIS data collection from WebSocket stream"""
    
    def __init__(self, api_key: str, bounds: Dict[str, float], max_vessels: int = 10):
        self.api_key = api_key
        self.bounds = bounds
        self.max_vessels = max_vessels
        self.vessel_data = []
        self.data_queue = queue.Queue()
        self.connection_active = False
        self.debug_count = 0
        
    def on_message(self, ws, message):
        """Process incoming AIS messages"""
        try:
            data = json.loads(message)
            
            # Debug: Print message type
            msg_type = data.get('MessageType', 'Unknown')
            print(f"📡 Received {msg_type} message")
            
            # Only process if connection is active
            if not self.connection_active:
                return
            
            # Check if it's a position report
            if msg_type == 'PositionReport':
                # Extract data from nested structure
                position_data = data.get('Message', {}).get('PositionReport', {})
                metadata = data.get('MetaData', {})
                
                # Try different possible field names for MMSI
                mmsi = metadata.get('MMSI') or position_data.get('MMSI') or data.get('UserID')
                
                vessel_info = {
                    'mmsi': mmsi,
                    'latitude': position_data.get('Latitude'),
                    'longitude': position_data.get('Longitude'),
                    'speed': position_data.get('Sog', 0),  # Speed Over Ground
                    'course': position_data.get('Cog', 0),  # Course Over Ground
                    'timestamp': datetime.now().isoformat(),
                    'vessel_name': metadata.get('VesselName', 'Unknown')
                }
                
                # Debug: Show vessel coordinates and raw data structure (limit to first 3 messages)
                if self.debug_count < 3:
                    print(f"🚢 Vessel {vessel_info['mmsi']}: Lat {vessel_info['latitude']}, Lon {vessel_info['longitude']}")
                    print(f"   Bounds: Lat {self.bounds['south']}-{self.bounds['north']}, Lon {self.bounds['west']}-{self.bounds['east']}")
                    print(f"   Raw data keys: {list(data.keys())}")
                    print(f"   Raw data sample: {str(data)[:200]}...")
                    self.debug_count += 1
                
                # Check if vessel is within our bounding box (handle None values)
                if (vessel_info['latitude'] is not None and vessel_info['longitude'] is not None and
                    self.bounds['south'] <= vessel_info['latitude'] <= self.bounds['north'] and
                    self.bounds['west'] <= vessel_info['longitude'] <= self.bounds['east']):
                    
                    self.data_queue.put(vessel_info)
                    print(f"✅ COLLECTED AIS data for vessel {vessel_info['mmsi']} - {vessel_info['vessel_name']}")
                    
                    # Stop if we have enough vessels
                    if len(self.vessel_data) >= self.max_vessels:
                        self.connection_active = False
                        ws.close()
                else:
                    print(f"❌ Vessel {vessel_info['mmsi']} outside bounds")
                        
        except Exception as e:
            print(f"Error processing AIS message: {e}")
    
    def on_error(self, ws, error):
        print(f"AIS WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("AIS WebSocket connection closed")
    
    def on_open(self, ws):
        """Subscribe to AIS data for our bounding box"""
        subscription_message = {
            "APIKey": self.api_key,
            "BoundingBoxes": [[
                [self.bounds['south'], self.bounds['west']],
                [self.bounds['north'], self.bounds['east']]
            ]]
        }
        print(f"🔑 Sending subscription with API key: {self.api_key[:10]}...{self.api_key[-10:]}")
        print(f"📍 Bounding box: {self.bounds}")
        ws.send(json.dumps(subscription_message))
        print("✓ Subscribed to AIS data stream")
    
    def collect_data(self, duration_seconds: int = 30) -> List[Dict]:
        """Collect AIS data for specified duration"""
        try:
            websocket.enableTrace(False)
            ws = websocket.WebSocketApp(
                "wss://stream.aisstream.io/v0/stream",
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # Use a flag to control the connection
            self.connection_active = True
            
            print("⏳ Connecting to AIS stream...")
            
            # Run WebSocket in a thread with timeout
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for the specified duration
            print(f"📡 Collecting AIS data for {duration_seconds} seconds...")
            time.sleep(duration_seconds)
            
            # Stop collecting
            self.connection_active = False
            ws.close()
            
            # Wait for thread to finish
            ws_thread.join(timeout=5)
            
            # Get collected data from queue
            while not self.data_queue.empty():
                self.vessel_data.append(self.data_queue.get())
            
            print(f"✓ Collected {len(self.vessel_data)} vessels from AIS stream")
            return self.vessel_data[:self.max_vessels]
            
        except Exception as e:
            print(f"Error collecting AIS data: {e}")
            return []

def fetch_open_meteo_weather(lat: float, lon: float, hours: int = 24) -> pd.DataFrame:
    """Fetch marine weather data from Open-Meteo (free, no API key needed)"""
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
        
        # Create DataFrame
        df = pd.DataFrame({
            'time': pd.to_datetime(hourly_data.get('time', [])),
            'wave_height_m': hourly_data.get('wave_height', []),
            'wave_direction_deg': hourly_data.get('wave_direction', []),
            'wind_wave_height_m': hourly_data.get('wind_wave_height', []),
            'ocean_current_velocity_ms': hourly_data.get('ocean_current_velocity', []),
            'ocean_current_direction_deg': hourly_data.get('ocean_current_direction', [])
        })
        
        print(f"✓ Collected {len(df)} hours of weather data from Open-Meteo")
        return df
        
    except Exception as e:
        print(f"Error fetching Open-Meteo data: {e}")
        return pd.DataFrame()

def fetch_tomorrow_io_weather(lat: float, lon: float, api_key: str, hours: int = 24) -> pd.DataFrame:
    """Fetch weather data from Tomorrow.io (free tier, API key required)"""
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
        
        df = pd.DataFrame(weather_data)
        print(f"✓ Collected {len(df)} hours of weather data from Tomorrow.io")
        return df
        
    except Exception as e:
        print(f"Error fetching Tomorrow.io data: {e}")
        return pd.DataFrame()

# ==========================================
# ENHANCED MARITIME ROUTE OPTIMIZATION WITH ML
# ==========================================

class RouteObjective(Enum):
    """Route optimization objectives"""
    MINIMIZE_FUEL = "minimize_fuel"
    MINIMIZE_TIME = "minimize_time"
    BALANCED = "balanced"
    SCHEDULE_CRITICAL = "schedule_critical"

@dataclass
class RouteConstraints:
    """Constraints for route planning"""
    max_deviation_degrees: float = 15.0
    max_delay_hours: float = 24.0
    min_safety_margin: float = 0.5
    max_wave_height: float = 4.0
    max_wind_speed: float = 25.0
    fuel_capacity: float = 1000.0
    current_fuel: float = 800.0
    vessel_speed_range: tuple = (5.0, 20.0)

@dataclass
class ScheduleRequirement:
    """Schedule requirements for route planning"""
    departure_time: datetime
    arrival_deadline: datetime
    priority: int = 1
    cargo_type: str = "general"
    port_restrictions: List[str] = None

class MaritimeUnits:
    """Handle all unit conversions for maritime operations"""

    @staticmethod
    def ms_to_kts(ms: float) -> float:
        """Convert meters per second to knots"""
        return ms * 1.94384

    @staticmethod
    def kts_to_ms(kts: float) -> float:
        """Convert knots to meters per second"""
        return kts / 1.94384

class EnhancedSailingCalculator:
    """Enhanced sailing calculations with proper maritime units"""

    @staticmethod
    def great_circle_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great circle distance between two points in nautical miles"""
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (math.sin(dlat/2)**2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))

        earth_radius_nm = 3440.065
        return earth_radius_nm * c

    @staticmethod
    def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate initial bearing between two points in degrees"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)

        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad))

        bearing_rad = math.atan2(y, x)
        bearing_deg = math.degrees(bearing_rad)

        return (bearing_deg + 360) % 360

    @staticmethod
    def calculate_waypoints(start_lat: float, start_lon: float,
                           end_lat: float, end_lon: float,
                           num_waypoints: int = 20) -> List[tuple]:
        """Generate waypoints along great circle route"""
        waypoints = []

        for i in range(num_waypoints + 1):
            fraction = i / num_waypoints

            lat = start_lat + (end_lat - start_lat) * fraction

            if abs(end_lon - start_lon) > 180:
                if end_lon > start_lon:
                    lon = start_lon + (end_lon - start_lon - 360) * fraction
                else:
                    lon = start_lon + (end_lon - start_lon + 360) * fraction
            else:
                lon = start_lon + (end_lon - start_lon) * fraction

            lon = (lon + 180) % 360 - 180
            waypoints.append((lat, lon))

        return waypoints

class MaritimeMLDataProcessor:
    """Enhanced ML data processing for maritime route optimization"""

    def __init__(self, weather_df: pd.DataFrame, ais_df: pd.DataFrame):
        self.weather_df = weather_df
        self.ais_df = ais_df
        self.units = MaritimeUnits()

    def prepare_ml_training_data(self) -> tuple:
        """Prepare comprehensive training data for maritime ML models"""

        print("🤖 Preparing ML training data for maritime optimization...")

        features = []
        targets = []
        route_metadata = []

        # Generate synthetic route data for training
        training_routes = self.generate_training_routes()

        for route in training_routes:
            waypoints = route['waypoints']

            for i, (lat, lon) in enumerate(waypoints):
                # Get weather conditions
                weather = self.get_weather_at_position(lat, lon, route['timestamp'])

                # Calculate course and speed
                if i < len(waypoints) - 1:
                    next_lat, next_lon = waypoints[i + 1]
                    course = self.calculate_bearing(lat, lon, next_lat, next_lon)
                    distance_nm = self.calculate_distance(lat, lon, next_lat, next_lon)
                else:
                    course = 0
                    distance_nm = 0

                # Create feature vector (maritime units)
                feature_vector = [
                    lat,                                    # Latitude
                    lon,                                    # Longitude
                    course,                                 # Course (degrees)
                    weather['wind_speed_kts'],              # Wind speed (kts)
                    weather['wind_direction_deg'],          # Wind direction (deg)
                    weather['wave_height_m'],               # Wave height (m)
                    weather['ocean_current_speed_kts'],     # Current speed (kts)
                    weather['ocean_current_direction_deg'], # Current direction (deg)
                    weather['temperature_c'],               # Temperature (°C)
                    distance_nm,                            # Distance to next waypoint (nm)
                    route['vessel_type'],                   # Vessel type (encoded)
                    route['cargo_type'],                    # Cargo type (encoded)
                    route['priority']                       # Schedule priority
                ]

                # Calculate optimal speed based on conditions
                optimal_speed = self.calculate_optimal_speed(
                    weather, course, distance_nm, route
                )

                # Calculate fuel efficiency
                fuel_efficiency = self.calculate_fuel_efficiency(
                    optimal_speed, weather, route
                )

                # Calculate safety score
                safety_score = self.calculate_safety_score(weather, route)

                features.append(feature_vector)
                targets.append([optimal_speed, fuel_efficiency, safety_score])

                route_metadata.append({
                    'route_id': route['id'],
                    'waypoint_index': i,
                    'timestamp': route['timestamp']
                })

        X = np.array(features)
        y = np.array(targets)

        print(f"✓ Prepared {len(X)} training samples")
        print(f"   Features: {X.shape[1]} dimensions")
        print(f"   Targets: {y.shape[1]} outputs (speed, fuel, safety)")

        return X, y, route_metadata

    def generate_training_routes(self) -> List[Dict]:
        """Generate diverse training routes for ML model"""

        routes = []
        base_time = datetime.now()

        # Define common maritime routes
        route_definitions = [
            {
                'name': 'SF to LA',
                'start': (37.7749, -122.4194),
                'end': (34.0522, -118.2437),
                'vessel_type': 1,  # Container ship
                'cargo_type': 1,   # General cargo
                'priority': 1      # High priority
            },
            {
                'name': 'SF to Seattle',
                'start': (37.7749, -122.4194),
                'end': (47.6062, -122.3321),
                'vessel_type': 2,  # Tanker
                'cargo_type': 2,   # Oil
                'priority': 2      # Medium priority
            }
        ]

        for i, route_def in enumerate(route_definitions):
            # Generate waypoints
            waypoints = self.calculate_waypoints(
                route_def['start'][0], route_def['start'][1],
                route_def['end'][0], route_def['end'][1],
                num_waypoints=20
            )

            # Create multiple time variations
            for hour_offset in range(0, 24, 6):  # Every 6 hours
                route = {
                    'id': f"{route_def['name']}_{hour_offset}h",
                    'name': route_def['name'],
                    'start': route_def['start'],
                    'end': route_def['end'],
                    'waypoints': waypoints,
                    'timestamp': base_time + timedelta(hours=hour_offset),
                    'vessel_type': route_def['vessel_type'],
                    'cargo_type': route_def['cargo_type'],
                    'priority': route_def['priority']
                }
                routes.append(route)

        return routes

    def get_weather_at_position(self, lat: float, lon: float, timestamp: datetime) -> Dict[str, float]:
        """Get weather conditions at specific position and time in maritime units"""
        if self.weather_df.empty:
            return {
                'wave_height_m': 1.0,
                'wind_speed_kts': 10.0,
                'wind_direction_deg': 180.0,
                'ocean_current_speed_kts': 1.0,
                'ocean_current_direction_deg': 180.0,
                'temperature_c': 20.0
            }

        # Find closest weather data by time
        weather_subset = self.weather_df.copy()
        weather_subset['time'] = pd.to_datetime(weather_subset['time'])
        weather_subset['time_diff'] = abs(weather_subset['time'] - timestamp)

        closest_time_idx = weather_subset['time_diff'].idxmin()
        closest_weather = weather_subset.loc[closest_time_idx]

        # Convert wind speed from m/s to knots
        wind_speed_ms = closest_weather.get('wind_speed_ms', 5.0)
        wind_speed_kts = self.units.ms_to_kts(wind_speed_ms)

        # Convert current speed from m/s to knots
        current_speed_ms = closest_weather.get('ocean_current_velocity_ms', 0.5)
        current_speed_kts = self.units.ms_to_kts(current_speed_ms)

        return {
            'wave_height_m': closest_weather.get('wave_height_m', 1.0),
            'wind_speed_kts': wind_speed_kts,
            'wind_direction_deg': closest_weather.get('wind_direction_deg', 180.0),
            'ocean_current_speed_kts': current_speed_kts,
            'ocean_current_direction_deg': closest_weather.get('ocean_current_direction_deg', 180.0),
            'temperature_c': closest_weather.get('temperature_c', 20.0)
        }

    def calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing between two points"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)

        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad))

        bearing_rad = math.atan2(y, x)
        bearing_deg = math.degrees(bearing_rad)

        return (bearing_deg + 360) % 360

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in nautical miles"""
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (math.sin(dlat/2)**2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))

        earth_radius_nm = 3440.065
        return earth_radius_nm * c

    def calculate_waypoints(self, start_lat: float, start_lon: float,
                           end_lat: float, end_lon: float,
                           num_waypoints: int = 20) -> List[tuple]:
        """Generate waypoints along route"""
        waypoints = []

        for i in range(num_waypoints + 1):
            fraction = i / num_waypoints

            lat = start_lat + (end_lat - start_lat) * fraction

            if abs(end_lon - start_lon) > 180:
                if end_lon > start_lon:
                    lon = start_lon + (end_lon - start_lon - 360) * fraction
                else:
                    lon = start_lon + (end_lon - start_lon + 360) * fraction
            else:
                lon = start_lon + (end_lon - start_lon) * fraction

            lon = (lon + 180) % 360 - 180
            waypoints.append((lat, lon))

        return waypoints

    def calculate_optimal_speed(self, weather: Dict, course: float,
                              distance_nm: float, route: Dict) -> float:
        """Calculate optimal speed based on weather and route conditions"""

        base_speed = 15.0  # Base speed in knots

        # Wind impact
        wind_angle = abs(course - weather['wind_direction_deg'])
        if wind_angle > 180:
            wind_angle = 360 - wind_angle

        if wind_angle <= 90:  # Headwind
            wind_factor = math.cos(math.radians(wind_angle))
            wind_impact = -weather['wind_speed_kts'] * wind_factor * 0.1
        else:  # Tailwind
            wind_factor = math.cos(math.radians(180 - wind_angle))
            wind_impact = weather['wind_speed_kts'] * wind_factor * 0.05

        # Wave impact
        wave_impact = -weather['wave_height_m'] * 0.5

        # Current impact
        current_angle = abs(course - weather['ocean_current_direction_deg'])
        if current_angle > 180:
            current_angle = 360 - current_angle

        current_factor = math.cos(math.radians(current_angle))
        current_impact = weather['ocean_current_speed_kts'] * current_factor * 0.8

        # Vessel type adjustments
        vessel_speed_multiplier = {
            1: 1.0,   # Container ship
            2: 0.9,   # Tanker (slower)
            3: 1.2    # Ferry (faster)
        }.get(route['vessel_type'], 1.0)

        # Calculate optimal speed
        optimal_speed = base_speed + wind_impact + wave_impact + current_impact
        optimal_speed *= vessel_speed_multiplier

        # Apply constraints
        optimal_speed = max(optimal_speed, 6.0)   # Minimum 6 knots
        optimal_speed = min(optimal_speed, 20.0)  # Maximum 20 knots

        return optimal_speed

    def calculate_fuel_efficiency(self, speed_kts: float, weather: Dict,
                                route: Dict) -> float:
        """Calculate fuel efficiency score (0-1, higher is better)"""

        # Base fuel consumption rate
        base_rate = 40.0  # L/hr at 15 knots

        # Speed factor (exponential increase with speed)
        speed_factor = (speed_kts / 15.0) ** 2.5

        # Weather factors
        wave_factor = 1.0 + (weather['wave_height_m'] - 1.0) * 0.1
        wind_factor = 1.0 + (weather['wind_speed_kts'] - 10.0) * 0.02

        # Calculate efficiency (inverse of fuel consumption)
        fuel_rate = base_rate * speed_factor * wave_factor * wind_factor
        efficiency = 1.0 / (1.0 + fuel_rate / 100.0)  # Normalize to 0-1

        return efficiency

    def calculate_safety_score(self, weather: Dict, route: Dict) -> float:
        """Calculate safety score (0-1, higher is safer)"""

        safety_score = 1.0

        # Wave height impact
        if weather['wave_height_m'] > 4.0:
            safety_score *= 0.3  # Critical
        elif weather['wave_height_m'] > 3.0:
            safety_score *= 0.6  # Dangerous
        elif weather['wave_height_m'] > 2.0:
            safety_score *= 0.8  # Moderate risk

        # Wind speed impact
        if weather['wind_speed_kts'] > 35.0:
            safety_score *= 0.3  # Critical
        elif weather['wind_speed_kts'] > 25.0:
            safety_score *= 0.6  # Dangerous
        elif weather['wind_speed_kts'] > 15.0:
            safety_score *= 0.8  # Moderate risk

        # Cargo type safety requirements
        cargo_safety_multiplier = {
            1: 1.0,   # General cargo
            2: 0.8,   # Oil (more sensitive)
            3: 0.9    # Passengers (safety critical)
        }.get(route['cargo_type'], 1.0)

        safety_score *= cargo_safety_multiplier

        return min(safety_score, 1.0)

# ==========================================
# DETECTIVE WORK: ORGANIZING EVIDENCE (DATA STORAGE)
# ==========================================
"""
This section organizes the collected clues into a structured database.
Like organizing evidence in folders, we store data in tables for easy access.
"""

def combine_weather_data(open_meteo_df: pd.DataFrame, tomorrow_df: pd.DataFrame) -> pd.DataFrame:
    """Combine weather data from both sources using outer join on time"""
    try:
        if open_meteo_df.empty and tomorrow_df.empty:
            return pd.DataFrame()
        
        if open_meteo_df.empty:
            return tomorrow_df
        if tomorrow_df.empty:
            return open_meteo_df
        
        # Normalize timezone for both DataFrames
        open_meteo_df['time'] = pd.to_datetime(open_meteo_df['time']).dt.tz_localize(None)
        tomorrow_df['time'] = pd.to_datetime(tomorrow_df['time']).dt.tz_localize(None)
        
        # Merge on time column
        combined_df = pd.merge(
            open_meteo_df, 
            tomorrow_df, 
            on='time', 
            how='outer',
            suffixes=('_openmeteo', '_tomorrow')
        )
        
        print(f"✓ Combined weather data: {len(combined_df)} records")
        return combined_df
        
    except Exception as e:
        print(f"Error combining weather data: {e}")
        return pd.DataFrame()

def setup_database(db_name: str = 'maritime.db'):
    """Create database tables if they don't exist"""
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # Create weather table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather (
                time TEXT PRIMARY KEY,
                wave_height_m REAL,
                wave_direction_deg REAL,
                wind_wave_height_m REAL,
                ocean_current_velocity_ms REAL,
                ocean_current_direction_deg REAL,
                temperature_c REAL,
                wind_speed_ms REAL,
                precipitation_intensity REAL,
                humidity_percent REAL,
                wave_significant_height_m REAL,
                sea_current_speed_ms REAL,
                sea_current_direction_deg REAL
            )
        ''')
        
        # Create AIS table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mmsi INTEGER,
                latitude REAL,
                longitude REAL,
                speed REAL,
                course REAL,
                timestamp TEXT,
                vessel_name TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✓ Database setup complete")
        
    except Exception as e:
        print(f"Error setting up database: {e}")

def store_weather_data(df: pd.DataFrame, db_name: str = 'maritime.db'):
    """Store combined weather data in database"""
    try:
        if df.empty:
            print("No weather data to store")
            return
        
        conn = sqlite3.connect(db_name)
        
        # Convert datetime to string for SQLite
        df_copy = df.copy()
        df_copy['time'] = df_copy['time'].astype(str)
        
        df_copy.to_sql('weather', conn, if_exists='replace', index=False)
        conn.close()
        
        print(f"✓ Stored {len(df)} weather records in database")
        
    except Exception as e:
        print(f"Error storing weather data: {e}")

def store_ais_data(vessel_list: List[Dict], db_name: str = 'maritime.db'):
    """Store AIS vessel data in database"""
    try:
        if not vessel_list:
            print("No AIS data to store")
            return
        
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        for vessel in vessel_list:
            cursor.execute('''
                INSERT INTO ais (mmsi, latitude, longitude, speed, course, timestamp, vessel_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                vessel.get('mmsi'),
                vessel.get('latitude'),
                vessel.get('longitude'),
                vessel.get('speed'),
                vessel.get('course'),
                vessel.get('timestamp'),
                vessel.get('vessel_name')
            ))
        
        conn.commit()
        conn.close()
        
        print(f"✓ Stored {len(vessel_list)} AIS records in database")
        
    except Exception as e:
        print(f"Error storing AIS data: {e}")

# ==========================================
# DETECTIVE WORK: INVESTIGATING (DATA ANALYSIS)
# ==========================================
"""
This section analyzes the evidence we've collected.
Like a detective piecing together clues, we look for patterns and insights.
"""

def load_data_from_db(db_name: str = 'maritime.db') -> tuple:
    """Load weather and AIS data from database"""
    try:
        conn = sqlite3.connect(db_name)
        
        # Load weather data
        weather_df = pd.read_sql_query("SELECT * FROM weather", conn)
        
        # Load AIS data
        ais_df = pd.read_sql_query("SELECT * FROM ais", conn)
        
        conn.close()
        
        print(f"✓ Loaded {len(weather_df)} weather records and {len(ais_df)} AIS records")
        return weather_df, ais_df
        
    except Exception as e:
        print(f"Error loading data from database: {e}")
        return pd.DataFrame(), pd.DataFrame()

def compute_averages(weather_df: pd.DataFrame, ais_df: pd.DataFrame):
    """Compute and display average values from our data"""
    try:
        print("\n📊 MARITIME DATA ANALYSIS REPORT")
        print("=" * 50)
        
        if not weather_df.empty:
            print("\n🌊 WEATHER CONDITIONS:")
            numeric_cols = weather_df.select_dtypes(include=[np.number]).columns
            
            for col in numeric_cols:
                if weather_df[col].notna().any():
                    avg_val = weather_df[col].mean()
                    print(f"  Average {col}: {avg_val:.2f}")
        
        if not ais_df.empty:
            print("\n🚢 VESSEL ACTIVITY:")
            print(f"  Total vessels tracked: {len(ais_df)}")
            
            if 'speed' in ais_df.columns:
                avg_speed = ais_df['speed'].mean()
                print(f"  Average vessel speed: {avg_speed:.2f} knots")
            
            if 'course' in ais_df.columns:
                avg_course = ais_df['course'].mean()
                print(f"  Average vessel course: {avg_course:.2f} degrees")
        
    except Exception as e:
        print(f"Error computing averages: {e}")

def plot_vessel_positions(ais_df: pd.DataFrame, weather_df: pd.DataFrame):
    """Create visualization of vessel positions with speed-based coloring"""
    try:
        if ais_df.empty:
            print("No AIS data to plot")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot 1: Vessel positions colored by speed
        scatter = ax1.scatter(
            ais_df['longitude'], 
            ais_df['latitude'],
            c=ais_df['speed'],
            cmap='viridis',
            s=100,
            alpha=0.7
        )
        
        ax1.set_title('Vessel Positions (Colored by Speed)')
        ax1.set_xlabel('Longitude')
        ax1.set_ylabel('Latitude')
        ax1.grid(True, alpha=0.3)
        
        # Add colorbar
        plt.colorbar(scatter, ax=ax1, label='Speed (knots)')
        
        # Add vessel names as labels
        for idx, row in ais_df.iterrows():
            ax1.annotate(
                row['vessel_name'][:10],  # Truncate long names
                (row['longitude'], row['latitude']),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=8,
                alpha=0.8
            )
        
        # Plot 2: Weather conditions over time (if available)
        if not weather_df.empty and 'time' in weather_df.columns:
            weather_df['time'] = pd.to_datetime(weather_df['time'])
            weather_df = weather_df.sort_values('time')
            
            ax2.plot(weather_df['time'], weather_df.get('wave_height_m', 0), 
                    label='Wave Height (m)', color='blue')
            ax2.plot(weather_df['time'], weather_df.get('wind_speed_ms', 0), 
                    label='Wind Speed (m/s)', color='red')
            ax2.plot(weather_df['time'], weather_df.get('ocean_current_velocity_ms', 0), 
                    label='Current Velocity (m/s)', color='green')
            
            ax2.set_title('Weather Conditions Over Time')
            ax2.set_xlabel('Time')
            ax2.set_ylabel('Value')
            ax2.legend()
            ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig('maritime_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print("✓ Generated maritime analysis plots (saved as maritime_analysis.png)")
        
    except Exception as e:
        print(f"Error creating plots: {e}")

# ==========================================
# DETECTIVE WORK: CONCLUDING (ROUTE OPTIMIZATION)
# ==========================================
"""
This section draws conclusions from our investigation.
Like a detective solving the case, we use ML to optimize maritime routes.
"""

def prepare_ml_data(weather_df: pd.DataFrame, ais_df: pd.DataFrame) -> tuple:
    """Prepare data for machine learning route optimization"""
    try:
        if weather_df.empty or ais_df.empty:
            print("Insufficient data for ML training")
            return None, None
        
        # Create features for route optimization
        features = []
        targets = []
        
        for idx, vessel in ais_df.iterrows():
            # Find corresponding weather conditions
            vessel_time = pd.to_datetime(vessel['timestamp'])
            
            # Get weather data closest to vessel timestamp
            weather_subset = weather_df.copy()
            weather_subset['time'] = pd.to_datetime(weather_subset['time'])
            weather_subset['time_diff'] = abs(weather_subset['time'] - vessel_time)
            
            closest_weather = weather_subset.loc[weather_subset['time_diff'].idxmin()]
            
            # Create feature vector
            feature_vector = [
                vessel['latitude'],
                vessel['longitude'],
                vessel['speed'],
                vessel['course'],
                closest_weather.get('wave_height_m', 0),
                closest_weather.get('wind_speed_ms', 0),
                closest_weather.get('ocean_current_velocity_ms', 0),
                closest_weather.get('ocean_current_direction_deg', 0),
                closest_weather.get('temperature_c', 20),
                closest_weather.get('humidity_percent', 50)
            ]
            
            # Target: optimal speed (higher in favorable conditions)
            optimal_speed = vessel['speed']
            
            # Adjust based on conditions
            if closest_weather.get('wave_height_m', 0) > 2:  # High waves
                optimal_speed *= 0.8  # Reduce speed
            elif closest_weather.get('wind_speed_ms', 0) < 5:  # Light winds
                optimal_speed *= 1.1  # Increase speed
            
            features.append(feature_vector)
            targets.append(optimal_speed)
        
        X = np.array(features)
        y = np.array(targets)
        
        print(f"✓ Prepared {len(X)} data points for ML training")
        return X, y
        
    except Exception as e:
        print(f"Error preparing ML data: {e}")
        return None, None

def train_route_optimization_model(X: np.ndarray, y: np.ndarray):
    """Train a Random Forest model for route optimization"""
    try:
        if X is None or y is None:
            return None, None
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train Random Forest model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train_scaled, y_train)
        
        # Evaluate model
        train_score = model.score(X_train_scaled, y_train)
        test_score = model.score(X_test_scaled, y_test)
        
        print(f"✓ ML Model trained - Train Score: {train_score:.3f}, Test Score: {test_score:.3f}")
        return model, scaler
        
    except Exception as e:
        print(f"Error training ML model: {e}")
        return None, None

def optimize_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, 
                  model, scaler, weather_df: pd.DataFrame) -> List[tuple]:
    """Generate an optimized route using the trained model"""
    try:
        if model is None:
            return []
        
        # Create a simple route using NetworkX
        G = nx.Graph()
        
        # Generate waypoints between start and end
        num_waypoints = 10
        lats = np.linspace(start_lat, end_lat, num_waypoints)
        lons = np.linspace(start_lon, end_lon, num_waypoints)
        
        waypoints = list(zip(lats, lons))
        
        # Add nodes to graph
        for i, (lat, lon) in enumerate(waypoints):
            G.add_node(i, pos=(lat, lon))
        
        # Add edges with weights based on predicted optimal speed
        for i in range(len(waypoints) - 1):
            for j in range(i + 1, len(waypoints)):
                # Calculate distance
                dist = np.sqrt((waypoints[j][0] - waypoints[i][0])**2 + 
                              (waypoints[j][1] - waypoints[i][1])**2)
                
                # Get weather conditions for midpoint
                mid_lat = (waypoints[i][0] + waypoints[j][0]) / 2
                mid_lon = (waypoints[i][1] + waypoints[j][1]) / 2
                
                # Find closest weather data
                weather_subset = weather_df.copy()
                if not weather_df.empty:
                    weather_subset['dist'] = np.sqrt(
                        (weather_subset.get('latitude', mid_lat) - mid_lat)**2 +
                        (weather_subset.get('longitude', mid_lon) - mid_lon)**2
                    )
                    closest_weather = weather_subset.loc[weather_subset['dist'].idxmin()]
                else:
                    closest_weather = {}
                
                # Create feature vector for prediction
                features = np.array([[
                    mid_lat, mid_lon, 10, 0,  # Default speed and course
                    closest_weather.get('wave_height_m', 1),
                    closest_weather.get('wind_speed_ms', 5),
                    closest_weather.get('ocean_current_velocity_ms', 0.5),
                    closest_weather.get('ocean_current_direction_deg', 180),
                    closest_weather.get('temperature_c', 20),
                    closest_weather.get('humidity_percent', 60)
                ]])
                
                # Scale features and predict optimal speed
                features_scaled = scaler.transform(features)
                predicted_speed = model.predict(features_scaled)[0]
                
                # Weight = distance / speed (lower is better)
                weight = dist / max(predicted_speed, 0.1)
                
                G.add_edge(i, j, weight=weight)
        
        # Find shortest path
        path = nx.shortest_path(G, 0, len(waypoints) - 1, weight='weight')
        optimized_route = [waypoints[i] for i in path]
        
        print(f"✓ Generated optimized route with {len(optimized_route)} waypoints")
        return optimized_route
        
    except Exception as e:
        print(f"Error optimizing route: {e}")
        return []

def plot_optimized_route(route: List[tuple], ais_df: pd.DataFrame):
    """Plot the optimized route alongside vessel positions"""
    try:
        if not route:
            return

        plt.figure(figsize=(10, 8))

        # Plot vessel positions
        if not ais_df.empty:
            plt.scatter(ais_df['longitude'], ais_df['latitude'],
                       c='red', s=50, alpha=0.6, label='Vessels')

        # Plot optimized route
        route_lats, route_lons = zip(*route)
        plt.plot(route_lons, route_lats, 'b-', linewidth=3, alpha=0.8, label='Optimized Route')
        plt.scatter(route_lons, route_lats, c='blue', s=100, alpha=1.0, label='Waypoints')

        plt.title('Optimized Maritime Route')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.savefig('optimized_route.png', dpi=300, bbox_inches='tight')
        plt.show()

        print("✓ Generated optimized route visualization (saved as optimized_route.png)")

    except Exception as e:
        print(f"Error plotting optimized route: {e}")

def plot_enhanced_route_analysis(waypoints: List[tuple], predictions: List[Dict],
                               ais_df: pd.DataFrame, weather_df: pd.DataFrame):
    """Create enhanced route analysis visualization"""
    try:
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # Plot 1: Route with ML predictions
        route_lats, route_lons = zip(*waypoints)
        ax1.plot(route_lons, route_lats, 'b-', linewidth=3, alpha=0.8, label='ML-Optimized Route')
        ax1.scatter(route_lons, route_lats, c='blue', s=50, alpha=0.8, label='Waypoints')

        # Color waypoints by safety score
        safety_scores = [p['safety_score'] for p in predictions]
        scatter = ax1.scatter(route_lons, route_lats, c=safety_scores,
                             cmap='RdYlGn', s=100, alpha=0.7, label='Safety Score')
        plt.colorbar(scatter, ax=ax1, label='Safety Score')

        # Add vessel positions
        if not ais_df.empty:
            ax1.scatter(ais_df['longitude'], ais_df['latitude'],
                       c='gray', s=30, alpha=0.6, label='Other Vessels')

        ax1.set_title('ML-Enhanced Maritime Route Analysis')
        ax1.set_xlabel('Longitude')
        ax1.set_ylabel('Latitude')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Speed predictions
        speeds = [p['optimal_speed_kts'] for p in predictions]
        ax2.plot(range(len(speeds)), speeds, 'g-', linewidth=2, marker='o', markersize=4)
        ax2.set_title('ML-Predicted Optimal Speeds')
        ax2.set_xlabel('Waypoint')
        ax2.set_ylabel('Speed (kts)')
        ax2.grid(True, alpha=0.3)

        # Plot 3: Safety scores
        safety_scores = [p['safety_score'] for p in predictions]
        ax3.plot(range(len(safety_scores)), safety_scores, 'r-', linewidth=2, marker='s', markersize=4)
        ax3.axhline(y=0.7, color='orange', linestyle='--', label='Safety Threshold')
        ax3.set_title('Safety Scores Along Route')
        ax3.set_xlabel('Waypoint')
        ax3.set_ylabel('Safety Score')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Plot 4: Fuel efficiency
        fuel_scores = [p['fuel_efficiency'] for p in predictions]
        ax4.plot(range(len(fuel_scores)), fuel_scores, 'purple', linewidth=2, marker='^', markersize=4)
        ax4.set_title('Fuel Efficiency Along Route')
        ax4.set_xlabel('Waypoint')
        ax4.set_ylabel('Fuel Efficiency')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('enhanced_maritime_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()

        print("✓ Generated enhanced maritime analysis (saved as enhanced_maritime_analysis.png)")

    except Exception as e:
        print(f"Error creating enhanced analysis: {e}")

def enhanced_main():
    """Enhanced main function with ML integration"""
    print("🚢 ENHANCED MARITIME ROUTE OPTIMIZATION SYSTEM")
    print("=" * 60)
    print("🤖 ML-Enhanced + Safety-First + Maritime Units")
    print("=" * 60)

    # Step 1: Setup and data collection (existing functionality)
    print("\n1. Setting up database and collecting data...")
    setup_database()

    # Collect AIS data
    ais_collector = AISDataCollector(AISSTREAM_API_KEY, SF_BAY_BOUNDS, max_vessels=10)
    ais_data = ais_collector.collect_data(duration_seconds=30)

    # Collect weather data
    open_meteo_data = fetch_open_meteo_weather(TEST_LAT, TEST_LON, hours=24)
    tomorrow_data = fetch_tomorrow_io_weather(TEST_LAT, TEST_LON, TOMORROW_IO_API_KEY, hours=24)

    # Combine and store data
    combined_weather = combine_weather_data(open_meteo_data, tomorrow_data)
    store_weather_data(combined_weather)
    store_ais_data(ais_data)

    # Load data
    weather_df, ais_df = load_data_from_db()

    # Step 2: Initialize ML data processor
    print("\n2. Initializing ML data processor...")
    ml_processor = MaritimeMLDataProcessor(weather_df, ais_df)

    # Step 3: Prepare training data
    print("\n3. Preparing ML training data...")
    X, y, metadata = ml_processor.prepare_ml_training_data()

    # Step 4: Train ML models
    print("\n4. Training ML models...")
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train models
    speed_model = RandomForestRegressor(n_estimators=100, random_state=42)
    fuel_model = RandomForestRegressor(n_estimators=100, random_state=42)
    safety_model = RandomForestRegressor(n_estimators=100, random_state=42)

    speed_model.fit(X_train_scaled, y_train[:, 0])
    fuel_model.fit(X_train_scaled, y_train[:, 1])
    safety_model.fit(X_train_scaled, y_train[:, 2])

    # Evaluate models
    speed_score = speed_model.score(X_test_scaled, y_test[:, 0])
    fuel_score = fuel_model.score(X_test_scaled, y_test[:, 1])
    safety_score = safety_model.score(X_test_scaled, y_test[:, 2])

    print(f"✓ ML Models trained successfully!")
    print(f"   Speed Model R²: {speed_score:.3f}")
    print(f"   Fuel Model R²: {fuel_score:.3f}")
    print(f"   Safety Model R²: {safety_score:.3f}")

    # Step 5: Test route optimization
    print("\n5. Testing enhanced route optimization...")

    # Test route
    start_lat, start_lon = 37.7749, -122.4194  # San Francisco
    end_lat, end_lon = 34.0522, -118.2437      # Los Angeles

    # Generate waypoints
    sailing_calc = EnhancedSailingCalculator()
    waypoints = sailing_calc.calculate_waypoints(start_lat, start_lon, end_lat, end_lon, num_waypoints=25)

    # Get weather data along route
    weather_data = []
    current_time = datetime.now()

    for lat, lon in waypoints:
        weather = ml_processor.get_weather_at_position(lat, lon, current_time)
        weather_data.append(weather)

        # Estimate time to next waypoint
        if len(weather_data) < len(waypoints):
            next_lat, next_lon = waypoints[len(weather_data)]
            distance_nm = sailing_calc.great_circle_distance(lat, lon, next_lat, next_lon)
            current_time += timedelta(hours=distance_nm / 15.0)

    # Make ML predictions
    predictions = []
    for i, (lat, lon) in enumerate(waypoints):
        weather = weather_data[i] if i < len(weather_data) else weather_data[-1]

        course = 0
        if i < len(waypoints) - 1:
            next_lat, next_lon = waypoints[i + 1]
            course = sailing_calc.bearing(lat, lon, next_lat, next_lon)

        distance_nm = 0
        if i < len(waypoints) - 1:
            next_lat, next_lon = waypoints[i + 1]
            distance_nm = sailing_calc.great_circle_distance(lat, lon, next_lat, next_lon)

        # Prepare feature vector
        feature_vector = np.array([[
            lat, lon, course,
            weather['wind_speed_kts'],
            weather['wind_direction_deg'],
            weather['wave_height_m'],
            weather['ocean_current_speed_kts'],
            weather['ocean_current_direction_deg'],
            weather['temperature_c'],
            distance_nm,
            1,  # vessel_type (container ship)
            1,  # cargo_type (general cargo)
            1   # priority (high)
        ]])

        # Scale features
        feature_scaled = scaler.transform(feature_vector)

        # Make predictions
        optimal_speed = speed_model.predict(feature_scaled)[0]
        fuel_efficiency = fuel_model.predict(feature_scaled)[0]
        safety_score = safety_model.predict(feature_scaled)[0]

        predictions.append({
            'waypoint': (lat, lon),
            'optimal_speed_kts': optimal_speed,
            'fuel_efficiency': fuel_efficiency,
            'safety_score': safety_score,
            'weather': weather
        })

    # Display results
    print(f"\n�� ENHANCED ROUTE ANALYSIS:")
    print(f"   Total Waypoints: {len(waypoints)}")
    print(f"   Direct Distance: {sailing_calc.great_circle_distance(start_lat, start_lon, end_lat, end_lon):.1f} nm")

    avg_speed = np.mean([p['optimal_speed_kts'] for p in predictions])
    avg_safety = np.mean([p['safety_score'] for p in predictions])
    avg_fuel = np.mean([p['fuel_efficiency'] for p in predictions])

    print(f"\n�� ML PREDICTIONS:")
    print(f"   Average Optimal Speed: {avg_speed:.1f} kts")
    print(f"   Average Safety Score: {avg_safety:.2f}")
    print(f"   Average Fuel Efficiency: {avg_fuel:.2f}")

    # Create enhanced visualization
    plot_enhanced_route_analysis(waypoints, predictions, ais_df, weather_df)

    print(f"\n�� Enhanced maritime route optimization complete!")
    print(f"🤖 ML models integrated successfully!")
    print(f"🌊 All units in maritime standard!")

# ==========================================
# MAIN INVESTIGATION (ORCHESTRATE EVERYTHING)
# ==========================================

def main():
    """Main function to run the complete maritime analysis"""
    print("🚢 MARITIME ROUTE OPTIMIZATION APPLICATION")
    print("=" * 60)
    
    # Step 1: Setup database
    print("\n1. Setting up database...")
    setup_database()
    
    # Step 2: Collect AIS data
    print("\n2. Collecting AIS vessel data...")
    ais_collector = AISDataCollector(AISSTREAM_API_KEY, SF_BAY_BOUNDS, max_vessels=10)
    ais_data = ais_collector.collect_data(duration_seconds=30)
    
    # Step 3: Collect weather data
    print("\n3. Collecting weather data...")
    open_meteo_data = fetch_open_meteo_weather(TEST_LAT, TEST_LON, hours=24)
    tomorrow_data = fetch_tomorrow_io_weather(TEST_LAT, TEST_LON, TOMORROW_IO_API_KEY, hours=24)
    
    # Step 4: Combine and store data
    print("\n4. Organizing data...")
    combined_weather = combine_weather_data(open_meteo_data, tomorrow_data)
    store_weather_data(combined_weather)
    store_ais_data(ais_data)
    
    # Step 5: Analyze data
    print("\n5. Investigating patterns...")
    weather_df, ais_df = load_data_from_db()
    compute_averages(weather_df, ais_df)
    plot_vessel_positions(ais_df, weather_df)
    
    # Step 6: Route optimization
    print("\n6. Optimizing routes with ML...")
    X, y = prepare_ml_data(weather_df, ais_df)
    model, scaler = train_route_optimization_model(X, y)
    
    # Generate sample optimized route
    start_lat, start_lon = 37.2, -122.8  # Near San Francisco
    end_lat, end_lon = 37.8, -122.2      # Near Oakland
    
    optimized_route = optimize_route(start_lat, start_lon, end_lat, end_lon, 
                                   model, scaler, weather_df)
    plot_optimized_route(optimized_route, ais_df)
    
    print("\n🎉 Investigation complete! Check the generated plots and database.")
    print("💡 Remember to replace API keys with your actual keys for full functionality.")

# ==========================================
# TEST FUNCTION FOR ENHANCED FEATURES
# ==========================================

def test_enhanced_features():
    """Test the enhanced ML and maritime features"""
    print("🧪 TESTING ENHANCED MARITIME FEATURES")
    print("=" * 50)

    try:
        # Test MaritimeUnits conversion
        print("1. Testing MaritimeUnits conversions...")
        units = MaritimeUnits()
        ms_speed = 5.0
        kts_speed = units.ms_to_kts(ms_speed)
        back_to_ms = units.kts_to_ms(kts_speed)
        print(f"   ✓ {ms_speed} m/s = {kts_speed:.1f} kts = {back_to_ms:.1f} m/s")

        # Test EnhancedSailingCalculator
        print("\n2. Testing EnhancedSailingCalculator...")
        calc = EnhancedSailingCalculator()

        # Test great circle distance
        lat1, lon1 = 37.7749, -122.4194  # San Francisco
        lat2, lon2 = 34.0522, -118.2437  # Los Angeles
        distance = calc.great_circle_distance(lat1, lon1, lat2, lon2)
        print(f"   ✓ Distance SF to LA: {distance:.1f} nm")

        # Test bearing
        bearing = calc.bearing(lat1, lon1, lat2, lon2)
        print(f"   ✓ Bearing SF to LA: {bearing:.1f}°")

        # Test waypoints generation
        waypoints = calc.calculate_waypoints(lat1, lon1, lat2, lon2, num_waypoints=10)
        print(f"   ✓ Generated {len(waypoints)} waypoints")

        # Test MaritimeMLDataProcessor
        print("\n3. Testing MaritimeMLDataProcessor...")
        # Create sample weather and AIS data
        sample_weather = pd.DataFrame({
            'time': [datetime.now()],
            'wave_height_m': [1.5],
            'wind_speed_ms': [5.0],
            'wind_direction_deg': [180.0],
            'ocean_current_velocity_ms': [0.5],
            'ocean_current_direction_deg': [180.0],
            'temperature_c': [20.0]
        })

        sample_ais = pd.DataFrame({
            'mmsi': [123456789],
            'latitude': [37.7749],
            'longitude': [-122.4194],
            'speed': [12.5],
            'course': [180.0],
            'timestamp': [datetime.now().isoformat()],
            'vessel_name': ['Test Vessel']
        })

        ml_processor = MaritimeMLDataProcessor(sample_weather, sample_ais)
        weather_at_pos = ml_processor.get_weather_at_position(37.7749, -122.4194, datetime.now())
        print(f"   ✓ Weather at SF: {weather_at_pos['wind_speed_kts']:.1f} kts wind")

        # Test RouteObjective enum
        print("\n4. Testing RouteObjective enum...")
        for objective in RouteObjective:
            print(f"   ✓ {objective.value}")

        # Test RouteConstraints
        print("\n5. Testing RouteConstraints...")
        constraints = RouteConstraints()
        print(f"   ✓ Max deviation: {constraints.max_deviation_degrees}°")
        print(f"   ✓ Max delay: {constraints.max_delay_hours} hours")
        print(f"   ✓ Vessel speed range: {constraints.vessel_speed_range} knots")

        print("\n✅ ALL ENHANCED FEATURES TESTED SUCCESSFULLY!")
        return True

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run tests first
    print("Running enhanced feature tests...")
    if test_enhanced_features():
        print("\n" + "="*60)
        print("Proceeding to enhanced main application...")
        print("="*60)
        enhanced_main()
    else:
        print("\n❌ Enhanced features have issues. Please fix before running main application.")
