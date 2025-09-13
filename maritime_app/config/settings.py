"""
Configuration settings for the Maritime Route Optimization Tool using Pydantic.
Loads from .env file and provides validated, type-safe settings.
"""
import os
from typing import Dict, Any, Callable
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Set the base directory to the project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    # Load .env file from the project root
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', env_file_encoding='utf-8')

    # API Keys
    AISSTREAM_API_KEY: str
    TOMORROW_IO_API_KEY: str
    OPEN_METEO_API_KEY: str = ""

    # Database settings
    DATABASE_PATH: str = "maritime.db"
    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.DATABASE_PATH}"

    # Web application settings
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000
    DEBUG: bool = False

    # AIS Data Collection settings
    AIS_BOUNDS: Dict[str, float] = {
        "north": 38.5, "south": 36.5, "east": -121.5, "west": -123.5
    }

    # Default test location
    DEFAULT_LAT: float = 37.5
    DEFAULT_LON: float = -122.5

    # ML Model settings
    RANDOM_STATE: int = 42
    TEST_SIZE: float = 0.2
    ML_MODEL_PATH: str = "models/"

    # Weather API settings
    WEATHER_FORECAST_HOURS: int = 72
    WEATHER_UPDATE_INTERVAL: int = 3600  # 1 hour

    # Navigation settings
    EARTH_RADIUS_NM: float = 3440.065
    KNOTS_TO_KMH: float = 1.852

    @property
    def KMH_TO_KNOTS(self) -> float:
        return 1 / self.KNOTS_TO_KMH

    # Safety thresholds
    MAX_WAVE_HEIGHT_M: float = 4.0
    MAX_WIND_SPEED_KTS: float = 35.0
    MIN_SAFETY_SCORE: float = 0.6

    # Performance settings
    MAX_VESSELS_PER_REQUEST: int = 100
    CACHE_TIMEOUT: int = 300  # 5 minutes
    MAX_WORKERS: int = 4

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "maritime_app.log"

    # Maritime units conversion factors
    UNITS: Dict[str, Any] = {
        "meters_to_feet": 3.28084,
        "feet_to_meters": 1 / 3.28084,
        "celsius_to_fahrenheit": lambda c: c * 9/5 + 32,
        "fahrenheit_to_celsius": lambda f: (f - 32) * 5/9,
    }

    # Vessel & Cargo type mappings
    VESSEL_TYPES: Dict[int, str] = {
        0: "Not available", 20: "Wing in ground", 30: "Fishing", 31: "Towing",
        36: "Sailing", 37: "Pleasure craft", 40: "High-speed craft", 50: "Pilot vessel",
        52: "Tug", 60: "Passenger", 62: "Cargo", 64: "Tanker", 66: "Other"
    }
    CARGO_TYPES: Dict[str, str] = {
        "bulk": "Bulk carrier", "container": "Container ship", "tanker": "Oil/Chemical tanker",
        "lng": "LNG carrier", "passenger": "Passenger vessel", "other": "Other"
    }

# Instantiate the settings object to be used throughout the application
settings = Settings()
