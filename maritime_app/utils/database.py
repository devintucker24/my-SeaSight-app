"""
Database Utilities Module
Handles database connections and operations for maritime data
"""
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

from ..config.settings import settings
from ..core.models import VesselData, WeatherData, RouteOptimizationResult


class DatabaseManager:
    """Manages database connections and operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DATABASE_PATH
        self._init_database()

    def _init_database(self):
        """Initialize database with required tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create vessels table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vessels (
                    mmsi INTEGER PRIMARY KEY,
                    name TEXT,
                    vessel_type INTEGER,
                    length REAL,
                    width REAL,
                    draft REAL,
                    engine_curves TEXT,
                    fuel_consumption_rates TEXT,
                    performance_characteristics TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create vessel_positions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vessel_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mmsi INTEGER,
                    latitude REAL,
                    longitude REAL,
                    speed REAL,
                    course REAL,
                    heading REAL,
                    sog REAL,
                    stw REAL,
                    timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (mmsi) REFERENCES vessels (mmsi)
                )
            ''')

            # Create weather_forecasts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weather_forecasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    latitude REAL,
                    longitude REAL,
                    forecast_time TIMESTAMP,
                    wave_height_m REAL,
                    wind_speed_kts REAL,
                    wind_direction_deg REAL,
                    temperature_c REAL,
                    pressure_hpa REAL,
                    ocean_current_speed_kts REAL,
                    ocean_current_direction_deg REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create routes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    start_lat REAL,
                    start_lon REAL,
                    end_lat REAL,
                    end_lon REAL,
                    waypoints TEXT,
                    course_data TEXT,
                    eta_data TEXT,
                    fuel_estimates TEXT,
                    safety_scores TEXT,
                    weather_forecast TEXT,
                    optimized_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create route_optimization_results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS route_optimization_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_id INTEGER,
                    optimization_type TEXT,
                    fuel_consumption REAL,
                    total_time REAL,
                    safety_score REAL,
                    eta_confidence REAL,
                    weather_impact TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (route_id) REFERENCES routes (id)
                )
            ''')

            # Create vessel_performance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vessel_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mmsi INTEGER,
                    waypoint_lat REAL,
                    waypoint_lon REAL,
                    predicted_arrival TIMESTAMP,
                    actual_arrival TIMESTAMP,
                    predicted_speed REAL,
                    actual_speed REAL,
                    predicted_fuel REAL,
                    actual_fuel REAL,
                    weather_conditions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (mmsi) REFERENCES vessels (mmsi)
                )
            ''')

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_vessel_data(self, vessels: List[VesselData]) -> int:
        """Save vessel data to database"""
        saved_count = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for vessel in vessels:
                try:
                    # Insert or update vessel info
                    cursor.execute('''
                        INSERT OR REPLACE INTO vessels
                        (mmsi, name, vessel_type, length, width, draft, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        vessel.mmsi, vessel.name, vessel.vessel_type,
                        vessel.length, vessel.width, vessel.draft,
                        datetime.now()
                    ))

                    # Insert position data
                    cursor.execute('''
                        INSERT INTO vessel_positions
                        (mmsi, latitude, longitude, speed, course, heading,
                         sog, stw, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        vessel.mmsi, vessel.latitude, vessel.longitude,
                        vessel.speed, vessel.course, vessel.heading,
                        vessel.speed, vessel.speed,  # SOG and STW placeholder
                        vessel.timestamp
                    ))

                    saved_count += 1

                except Exception as e:
                    print(f"Error saving vessel {vessel.mmsi}: {e}")

            conn.commit()

        return saved_count

    def save_weather_data(self, weather_data: List[WeatherData]) -> int:
        """Save weather data to database"""
        saved_count = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for weather in weather_data:
                try:
                    cursor.execute('''
                        INSERT INTO weather_forecasts
                        (latitude, longitude, forecast_time, wave_height_m,
                         wind_speed_kts, wind_direction_deg, temperature_c,
                         pressure_hpa, ocean_current_speed_kts,
                         ocean_current_direction_deg)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        weather.latitude, weather.longitude,
                        weather.forecast_time, weather.wave_height_m,
                        weather.wind_speed_kts, weather.wind_direction_deg,
                        weather.temperature_c, weather.pressure_hpa,
                        weather.ocean_current_speed_kts,
                        weather.ocean_current_direction_deg
                    ))

                    saved_count += 1

                except Exception as e:
                    print(f"Error saving weather data: {e}")

            conn.commit()

        return saved_count

    def save_route_result(self, result: RouteOptimizationResult) -> int:
        """Save route optimization result to database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert route data
            cursor.execute('''
                INSERT INTO routes
                (name, start_lat, start_lon, end_lat, end_lon, waypoints,
                 course_data, eta_data, fuel_estimates, safety_scores,
                 weather_forecast, optimized_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f"Route_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                result.route.waypoints[0].latitude if result.route.waypoints else 0,
                result.route.waypoints[0].longitude if result.route.waypoints else 0,
                result.route.waypoints[-1].latitude if result.route.waypoints else 0,
                result.route.waypoints[-1].longitude if result.route.waypoints else 0,
                str([{'lat': wp.latitude, 'lon': wp.longitude} for wp in result.route.waypoints]),
                "{}", "{}", "{}", "{}", "{}", datetime.now()
            ))

            route_id = cursor.lastrowid

            # Insert optimization result
            cursor.execute('''
                INSERT INTO route_optimization_results
                (route_id, optimization_type, fuel_consumption, total_time,
                 safety_score, eta_confidence, weather_impact)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                route_id, result.optimization_type, result.fuel_consumption,
                result.total_time, result.safety_score, result.eta_confidence,
                str(result.weather_impact)
            ))

            conn.commit()
            return route_id

    def get_recent_vessels(self, limit: int = 50) -> List[VesselData]:
        """Get recent vessel data from database"""
        vessels = []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT v.*, vp.latitude, vp.longitude, vp.speed, vp.course,
                       vp.heading, vp.timestamp
                FROM vessels v
                JOIN vessel_positions vp ON v.mmsi = vp.mmsi
                ORDER BY vp.timestamp DESC
                LIMIT ?
            ''', (limit,))

            for row in cursor.fetchall():
                vessel = VesselData(
                    mmsi=row['mmsi'],
                    name=row['name'],
                    vessel_type=row['vessel_type'],
                    length=row['length'],
                    width=row['width'],
                    draft=row['draft'],
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    speed=row['speed'],
                    course=row['course'],
                    heading=row['heading'],
                    timestamp=datetime.fromisoformat(row['timestamp']) if row['timestamp'] else None
                )
                vessels.append(vessel)

        return vessels

    def get_weather_forecast(self, lat: float, lon: float,
                           hours_ahead: int = 24) -> List[WeatherData]:
        """Get weather forecast for location"""
        weather_data = []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM weather_forecasts
                WHERE latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                  AND forecast_time >= datetime('now')
                  AND forecast_time <= datetime('now', '+{hours_ahead} hours')
                ORDER BY forecast_time
            ''', (lat-1, lat+1, lon-1, lon+1))

            for row in cursor.fetchall():
                weather = WeatherData(
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    wave_height_m=row['wave_height_m'],
                    wind_speed_kts=row['wind_speed_kts'],
                    wind_direction_deg=row['wind_direction_deg'],
                    temperature_c=row['temperature_c'],
                    pressure_hpa=row['pressure_hpa'],
                    ocean_current_speed_kts=row['ocean_current_speed_kts'],
                    ocean_current_direction_deg=row['ocean_current_direction_deg'],
                    forecast_time=datetime.fromisoformat(row['forecast_time']) if row['forecast_time'] else None
                )
                weather_data.append(weather)

        return weather_data

    def get_vessel_performance_history(self, mmsi: int,
                                     limit: int = 100) -> List[Dict[str, Any]]:
        """Get vessel performance history"""
        history = []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM vessel_performance
                WHERE mmsi = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (mmsi, limit))

            for row in cursor.fetchall():
                record = dict(row)
                history.append(record)

        return history

    def cleanup_old_data(self, days_old: int = 30):
        """Clean up old data from database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete old vessel positions
            cursor.execute('''
                DELETE FROM vessel_positions
                WHERE timestamp < datetime('now', '-{days_old} days')
            ''')

            # Delete old weather data
            cursor.execute('''
                DELETE FROM weather_forecasts
                WHERE created_at < datetime('now', '-{days_old} days')
            ''')

            # Delete old performance data
            cursor.execute('''
                DELETE FROM vessel_performance
                WHERE created_at < datetime('now', '-{days_old} days')
            ''')

            conn.commit()

            deleted_count = cursor.rowcount
            print(f"🧹 Cleaned up {deleted_count} old records")
