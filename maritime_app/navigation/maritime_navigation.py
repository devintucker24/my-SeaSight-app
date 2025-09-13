"""
Maritime Navigation Calculations
===============================

Professional maritime navigation calculations for course planning and tracking.
Focuses on true course calculations without magnetic/compass conversions.

Author: Maritime Route Optimization Team
"""

import math
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config.settings import settings


@dataclass
class Position:
    """Represents a geographic position with latitude and longitude"""
    lat: float  # Latitude in decimal degrees
    lon: float  # Longitude in decimal degrees
    
    def __post_init__(self):
        # Validate latitude range
        if not -90 <= self.lat <= 90:
            raise ValueError(f"Latitude must be between -90 and 90 degrees, got {self.lat}")
        
        # Normalize longitude to -180 to 180
        self.lon = ((self.lon + 180) % 360) - 180


@dataclass
class CourseResult:
    """Result of course calculation"""
    true_course: float  # True course in degrees (0-360)
    distance_nm: float  # Distance in nautical miles
    calculation_type: str  # "great_circle" or "rhumb_line"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class CrossTrackError:
    """Cross track error calculation result"""
    error_nm: float  # Cross track error in nautical miles
    bearing_to_route: float  # Bearing to get back on route (degrees)
    distance_to_route: float  # Distance to get back on route (nm)
    position_on_route: Position  # Closest point on the route


class MaritimeNavigation:
    """
    Professional maritime navigation calculations.
    
    Provides true course calculations, distance measurements, and navigation
    tracking without magnetic/compass conversions.
    """
    
    def __init__(self):
        self.earth_radius_nm = settings.EARTH_RADIUS_NM
        self.earth_radius_m = self.earth_radius_nm * 1852  # Convert to meters
        
    def degrees_to_radians(self, degrees: float) -> float:
        """Convert degrees to radians"""
        return degrees * math.pi / 180
    
    def radians_to_degrees(self, radians: float) -> float:
        """Convert radians to degrees"""
        return radians * 180 / math.pi
    
    def normalize_bearing(self, bearing: float) -> float:
        """Normalize bearing to 0-360 degrees"""
        return (bearing % 360 + 360) % 360
    
    def great_circle_distance(self, pos1: Position, pos2: Position) -> float:
        """
        Calculate great circle distance between two positions.
        
        Uses the haversine formula for accurate distance calculation.
        """
        lat1_rad = self.degrees_to_radians(pos1.lat)
        lon1_rad = self.degrees_to_radians(pos1.lon)
        lat2_rad = self.degrees_to_radians(pos2.lat)
        lon2_rad = self.degrees_to_radians(pos2.lon)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        return self.earth_radius_nm * c
    
    def great_circle_course(self, pos1: Position, pos2: Position) -> float:
        """
        Calculate true course between two positions using great circle.
        """
        lat1_rad = self.degrees_to_radians(pos1.lat)
        lon1_rad = self.degrees_to_radians(pos1.lon)
        lat2_rad = self.degrees_to_radians(pos2.lat)
        lon2_rad = self.degrees_to_radians(pos2.lon)
        
        dlon = lon2_rad - lon1_rad
        
        y = math.sin(dlon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))
        
        course_rad = math.atan2(y, x)
        course_deg = self.radians_to_degrees(course_rad)
        
        return self.normalize_bearing(course_deg)
    
    def calculate_course(self, pos1: Position, pos2: Position, 
                        use_great_circle: bool = True) -> CourseResult:
        """
        Calculate course and distance between two positions.
        """
        if use_great_circle:
            course = self.great_circle_course(pos1, pos2)
            distance = self.great_circle_distance(pos1, pos2)
            calc_type = "great_circle"
        else:
            # Simple rhumb line calculation
            lat1_rad = self.degrees_to_radians(pos1.lat)
            lon1_rad = self.degrees_to_radians(pos1.lon)
            lat2_rad = self.degrees_to_radians(pos2.lat)
            lon2_rad = self.degrees_to_radians(pos2.lon)
            
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            
            course_rad = math.atan2(dlon, dlat)
            course = self.normalize_bearing(self.radians_to_degrees(course_rad))
            
            distance = math.sqrt(dlat**2 + (dlon * math.cos(lat1_rad))**2) * self.earth_radius_nm
            calc_type = "rhumb_line"
        
        return CourseResult(
            true_course=course,
            distance_nm=distance,
            calculation_type=calc_type
        )
    
    def cross_track_error(self, current_pos: Position, 
                         route_start: Position, route_end: Position) -> CrossTrackError:
        """
        Calculate cross track error from current position to a route.
        """
        # Calculate course from route start to end
        route_course = self.great_circle_course(route_start, route_end)
        route_distance = self.great_circle_distance(route_start, route_end)
        
        # Calculate course from route start to current position
        to_current_course = self.great_circle_course(route_start, current_pos)
        to_current_distance = self.great_circle_distance(route_start, current_pos)
        
        # Calculate angle between route and line to current position
        angle_diff = to_current_course - route_course
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360
        
        # Calculate cross track error
        error_nm = to_current_distance * math.sin(self.degrees_to_radians(angle_diff))
        
        # Calculate bearing to get back on route
        if error_nm >= 0:
            bearing_to_route = self.normalize_bearing(route_course + 90)
        else:
            bearing_to_route = self.normalize_bearing(route_course - 90)
        
        # Calculate position on route (closest point)
        along_route_distance = to_current_distance * math.cos(self.degrees_to_radians(angle_diff))
        
        if along_route_distance <= 0:
            position_on_route = route_start
        elif along_route_distance >= route_distance:
            position_on_route = route_end
        else:
            # Interpolate position along route
            fraction = along_route_distance / route_distance
            lat = route_start.lat + fraction * (route_end.lat - route_start.lat)
            lon = route_start.lon + fraction * (route_end.lon - route_start.lon)
            position_on_route = Position(lat, lon)
        
        return CrossTrackError(
            error_nm=abs(error_nm),
            bearing_to_route=bearing_to_route,
            distance_to_route=abs(error_nm),
            position_on_route=position_on_route
        )
    
    def course_made_good(self, start_pos: Position, current_pos: Position, 
                        target_pos: Position) -> Dict[str, Any]:
        """
        Calculate course made good and related navigation data.
        """
        # Course made good from start to current position
        cmg = self.great_circle_course(start_pos, current_pos)
        distance_made_good = self.great_circle_distance(start_pos, current_pos)
        
        # Course to target from current position
        course_to_target = self.great_circle_course(current_pos, target_pos)
        distance_to_target = self.great_circle_distance(current_pos, target_pos)
        
        # Total distance from start to target
        total_distance = self.great_circle_distance(start_pos, target_pos)
        
        # Progress percentage
        progress_percent = (distance_made_good / total_distance) * 100 if total_distance > 0 else 0
        
        return {
            "course_made_good": cmg,
            "distance_made_good_nm": distance_made_good,
            "course_to_target": course_to_target,
            "distance_to_target_nm": distance_to_target,
            "total_distance_nm": total_distance,
            "progress_percent": progress_percent,
            "timestamp": datetime.now()
        }
    
    def generate_waypoints(self, start_pos: Position, end_pos: Position, 
                          num_waypoints: int = 10, 
                          use_great_circle: bool = True) -> List[Position]:
        """
        Generate waypoints between start and end positions.
        """
        if num_waypoints < 2:
            return [start_pos, end_pos]
        
        waypoints = [start_pos]
        
        for i in range(1, num_waypoints - 1):
            fraction = i / (num_waypoints - 1)
            
            # Interpolate latitude
            lat = start_pos.lat + fraction * (end_pos.lat - start_pos.lat)
            
            # Interpolate longitude
            dlon = end_pos.lon - start_pos.lon
            if dlon > 180:
                dlon -= 360
            elif dlon < -180:
                dlon += 360
            
            lon = start_pos.lon + fraction * dlon
            
            waypoints.append(Position(lat, lon))
        
        waypoints.append(end_pos)
        return waypoints
    
    def calculate_eta(self, current_pos: Position, target_pos: Position, 
                     speed_knots: float) -> datetime:
        """
        Calculate estimated time of arrival.
        """
        if speed_knots <= 0:
            raise ValueError("Speed must be greater than 0")
        
        distance = self.great_circle_distance(current_pos, target_pos)
        hours = distance / speed_knots
        
        return datetime.now() + timedelta(hours=hours)
