"""
Core data models and enumerations for the Maritime Route Optimization Tool
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta


class RouteObjective(Enum):
    """Optimization objectives for route planning"""
    FUEL_EFFICIENCY = "fuel_efficiency"
    TIME_OPTIMIZATION = "time_optimization"
    SAFETY_FIRST = "safety_first"
    BALANCED = "balanced"


@dataclass
class RouteConstraints:
    """Constraints for route optimization"""
    max_speed_knots: float = 20.0
    min_speed_knots: float = 5.0
    max_wave_height_m: float = 4.0
    max_wind_speed_kts: float = 35.0
    avoid_storms: bool = True
    preferred_channels: bool = True
    safety_buffer_nm: float = 10.0
    vessel_draft_m: float = 10.5
    ukc_m: float = 0.6
    apply_squat: bool = True


@dataclass
class ScheduleRequirement:
    """Time-based schedule requirements"""
    departure_time: Optional[datetime] = None
    required_arrival: Optional[datetime] = None
    flexibility_hours: float = 2.0
    priority: str = "medium"  # "low", "medium", "high", "critical"


class MaritimeUnits:
    """Maritime unit conversion utilities"""

    @staticmethod
    def knots_to_kmh(speed_knots: float) -> float:
        """Convert knots to kilometers per hour"""
        return speed_knots * 1.852

    @staticmethod
    def kmh_to_knots(speed_kmh: float) -> float:
        """Convert kilometers per hour to knots"""
        return speed_kmh / 1.852

    @staticmethod
    def meters_to_feet(meters: float) -> float:
        """Convert meters to feet"""
        return meters * 3.28084

    @staticmethod
    def feet_to_meters(feet: float) -> float:
        """Convert feet to meters"""
        return feet / 3.28084

    @staticmethod
    def celsius_to_fahrenheit(celsius: float) -> float:
        """Convert Celsius to Fahrenheit"""
        return celsius * 9/5 + 32

    @staticmethod
    def fahrenheit_to_celsius(fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius"""
        return (fahrenheit - 32) * 5/9


@dataclass
class VesselData:
    """Vessel information data structure"""
    mmsi: int
    name: Optional[str] = None
    vessel_type: Optional[int] = None
    length: Optional[float] = None
    width: Optional[float] = None
    draft: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None
    course: Optional[float] = None
    heading: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class WeatherData:
    """Weather information data structure"""
    latitude: float
    longitude: float
    wave_height_m: Optional[float] = None
    wind_speed_kts: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    temperature_c: Optional[float] = None
    pressure_hpa: Optional[float] = None
    ocean_current_speed_kts: Optional[float] = None
    ocean_current_direction_deg: Optional[float] = None
    forecast_time: Optional[datetime] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Waypoint:
    """Waypoint data structure"""
    latitude: float
    longitude: float
    name: Optional[str] = None
    estimated_time: Optional[datetime] = None
    actual_time: Optional[datetime] = None
    speed_knots: Optional[float] = None
    course_deg: Optional[float] = None
    distance_to_next_nm: Optional[float] = None


@dataclass
class Route:
    """Complete route data structure"""
    waypoints: List[Waypoint]
    total_distance_nm: float
    estimated_duration_hours: float
    fuel_consumption_tonnes: float
    safety_score: float
    weather_impact_score: float
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    vessel_data: Optional[VesselData] = None
    constraints: Optional[RouteConstraints] = None


@dataclass
class RouteOptimizationResult:
    """Result of route optimization"""
    route: Route
    optimization_type: str
    fuel_consumption: float
    total_time: float
    safety_score: float
    eta_confidence: float
    weather_impact: Dict[str, Any]
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class NavigationParameters:
    """Navigation calculation parameters"""
    magnetic_variation_deg: float = 0.0
    compass_deviation_deg: float = 0.0
    current_set_knots: float = 0.0
    current_drift_deg: float = 0.0
    tidal_height_m: float = 0.0
    tidal_rate_knots: float = 0.0


@dataclass
class PerformanceMetrics:
    """Vessel performance tracking metrics"""
    mmsi: int
    waypoint_lat: float
    waypoint_lon: float
    predicted_arrival: datetime
    predicted_speed: float
    predicted_fuel: float
    actual_arrival: Optional[datetime] = None
    actual_speed: Optional[float] = None
    actual_fuel: Optional[float] = None
    weather_conditions: Dict[str, Any] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
