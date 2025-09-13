"""
Route Optimization Module
Handles sailing calculations and route optimization algorithms
"""
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta

from ..config.settings import settings
from ..core.models import Waypoint, Route, RouteConstraints, RouteObjective, WeatherData, VesselData
from ..utils.database import DatabaseManager


class EnhancedSailingCalculator:
    """Enhanced sailing calculations for maritime route optimization"""

    def __init__(self):
        self.db = DatabaseManager()
        self.earth_radius = settings.EARTH_RADIUS_NM  # Nautical miles

    def calculate_great_circle_distance(self, lat1: float, lon1: float,
                                      lat2: float, lon2: float) -> float:
        """Calculate great circle distance between two points in nautical miles"""
        # Convert to radians
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
        lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return self.earth_radius * c

    def calculate_bearing(self, lat1: float, lon1: float,
                         lat2: float, lon2: float) -> float:
        """Calculate initial bearing from point 1 to point 2 in degrees"""
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
        lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

        dlon = lon2_rad - lon1_rad

        x = math.sin(dlon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)

        bearing_rad = math.atan2(x, y)
        bearing_deg = math.degrees(bearing_rad)

        # Normalize to 0-360 degrees
        return (bearing_deg + 360) % 360

    def calculate_rhumb_line_distance(self, lat1: float, lon1: float,
                                    lat2: float, lon2: float) -> float:
        """Calculate rhumb line distance (constant bearing) in nautical miles"""
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
        lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # Adjust longitude for crossing the date line
        if abs(dlon) > math.pi:
            dlon = dlon - (2 * math.pi * dlon / abs(dlon))

        # Calculate distance along rhumb line
        delta = math.log(math.tan(lat2_rad/2 + math.pi/4) / math.tan(lat1_rad/2 + math.pi/4))

        if abs(lat2_rad - lat1_rad) < 1e-10:
            q = math.cos(lat1_rad)
        else:
            q = (lat2_rad - lat1_rad) / delta

        distance = math.sqrt(dlat**2 + q**2 * dlon**2) * self.earth_radius

        return distance

    def calculate_cross_track_error(self, current_lat: float, current_lon: float,
                                  start_lat: float, start_lon: float,
                                  end_lat: float, end_lon: float) -> float:
        """Calculate cross track error (distance from path) in nautical miles"""
        # Calculate distances
        dist_to_end = self.calculate_great_circle_distance(current_lat, current_lon, end_lat, end_lon)
        bearing_to_end = self.calculate_bearing(current_lat, current_lon, end_lat, end_lon)
        bearing_path = self.calculate_bearing(start_lat, start_lon, end_lat, end_lon)

        # Calculate angle difference
        angle_diff = bearing_to_end - bearing_path
        angle_diff = (angle_diff + 180) % 360 - 180  # Normalize to -180 to 180

        # Cross track error
        xte = dist_to_end * math.sin(math.radians(angle_diff))

        return xte

    def generate_waypoints(self, start_lat: float, start_lon: float,
                          end_lat: float, end_lon: float,
                          num_waypoints: int = 10) -> List[Waypoint]:
        """Generate waypoints along great circle route"""
        waypoints = []

        # Add starting waypoint
        waypoints.append(Waypoint(
            latitude=start_lat,
            longitude=start_lon,
            name="Departure"
        ))

        # Generate intermediate waypoints
        for i in range(1, num_waypoints + 1):
            fraction = i / (num_waypoints + 1)

            # Interpolate position along great circle
            lat, lon = self._interpolate_great_circle(
                start_lat, start_lon, end_lat, end_lon, fraction
            )

            waypoints.append(Waypoint(
                latitude=lat,
                longitude=lon,
                name=f"WP{i}"
            ))

        # Add ending waypoint
        waypoints.append(Waypoint(
            latitude=end_lat,
            longitude=end_lon,
            name="Destination"
        ))

        return waypoints

    def _interpolate_great_circle(self, lat1: float, lon1: float,
                                lat2: float, lon2: float,
                                fraction: float) -> Tuple[float, float]:
        """Interpolate position along great circle path"""
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
        lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

        d = self.calculate_great_circle_distance(lat1, lon1, lat2, lon2)
        angular_distance = d / self.earth_radius

        a = math.sin((1 - fraction) * angular_distance) / math.sin(angular_distance)
        b = math.sin(fraction * angular_distance) / math.sin(angular_distance)

        x = a * math.cos(lat1_rad) * math.cos(lon1_rad) + b * math.cos(lat2_rad) * math.cos(lon2_rad)
        y = a * math.cos(lat1_rad) * math.sin(lon1_rad) + b * math.cos(lat2_rad) * math.sin(lon2_rad)
        z = a * math.sin(lat1_rad) + b * math.sin(lat2_rad)

        lat_rad = math.atan2(z, math.sqrt(x**2 + y**2))
        lon_rad = math.atan2(y, x)

        return math.degrees(lat_rad), math.degrees(lon_rad)

    def optimize_route(self, waypoints: List[Waypoint],
                      constraints: RouteConstraints,
                      objective: RouteObjective = RouteObjective.BALANCED) -> Route:
        """Optimize route based on constraints and objectives"""
        print(f"🧭 Optimizing route with {objective.value} objective...")

        # Calculate total distance
        total_distance = 0
        for i in range(len(waypoints) - 1):
            wp1, wp2 = waypoints[i], waypoints[i + 1]
            distance = self.calculate_great_circle_distance(
                wp1.latitude, wp1.longitude, wp2.latitude, wp2.longitude
            )
            wp1.distance_to_next_nm = distance
            total_distance += distance

        # Calculate estimated duration and fuel consumption
        estimated_duration, fuel_consumption = self._calculate_route_metrics(
            waypoints, constraints, objective
        )

        # Calculate safety score
        safety_score = self._calculate_route_safety(waypoints, constraints)

        # Create route object
        route = Route(
            waypoints=waypoints,
            total_distance_nm=total_distance,
            estimated_duration_hours=estimated_duration,
            fuel_consumption_tonnes=fuel_consumption,
            safety_score=safety_score,
            weather_impact_score=0.8,  # Placeholder
            constraints=constraints
        )

        print("✅ Route optimization complete!")
        return route

    def _calculate_route_metrics(self, waypoints: List[Waypoint],
                               constraints: RouteConstraints,
                               objective: RouteObjective) -> Tuple[float, float]:
        """Calculate route duration and fuel consumption"""
        total_time = 0
        total_fuel = 0

        for i in range(len(waypoints) - 1):
            wp1, wp2 = waypoints[i], waypoints[i + 1]
            distance = wp1.distance_to_next_nm or 0

            # Determine speed based on objective
            if objective == RouteObjective.FUEL_EFFICIENCY:
                speed = constraints.min_speed_knots + (constraints.max_speed_knots - constraints.min_speed_knots) * 0.7
            elif objective == RouteObjective.TIME_OPTIMIZATION:
                speed = constraints.max_speed_knots
            elif objective == RouteObjective.SAFETY_FIRST:
                speed = constraints.max_speed_knots * 0.8
            else:  # BALANCED
                speed = (constraints.min_speed_knots + constraints.max_speed_knots) / 2

            # Calculate time and fuel
            time_hours = distance / speed
            fuel_tonnes = distance * 0.02  # Rough estimate: 20 tonnes per 1000 nm

            total_time += time_hours
            total_fuel += fuel_tonnes

        return total_time, total_fuel

    def _calculate_route_safety(self, waypoints: List[Waypoint],
                              constraints: RouteConstraints) -> float:
        """Calculate overall route safety score"""
        # Placeholder safety calculation
        # In real implementation, this would consider weather, traffic, etc.
        base_safety = 0.8

        # Reduce safety for long routes
        route_length_penalty = min(len(waypoints) / 20, 0.2)

        safety_score = base_safety - route_length_penalty
        return max(0.1, safety_score)

    def calculate_eta(self, start_time: datetime, waypoints: List[Waypoint],
                     speed_knots: float) -> List[datetime]:
        """Calculate estimated time of arrival for each waypoint"""
        etas = [start_time]
        current_time = start_time

        for i in range(len(waypoints) - 1):
            wp1, wp2 = waypoints[i], waypoints[i + 1]
            distance = self.calculate_great_circle_distance(
                wp1.latitude, wp1.longitude, wp2.latitude, wp2.longitude
            )

            # Calculate travel time
            travel_time_hours = distance / speed_knots
            travel_time = timedelta(hours=travel_time_hours)

            current_time += travel_time
            etas.append(current_time)

        return etas
