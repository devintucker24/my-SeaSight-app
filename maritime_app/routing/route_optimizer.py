"""
Route Optimization Module
Handles sailing calculations and route optimization algorithms
"""
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json

from ..config.settings import settings
from ..core.models import Waypoint, Route, RouteConstraints, RouteObjective, WeatherData, VesselData
from ..utils.database import DatabaseManager

# Optional geospatial support (graceful fallback if unavailable)
try:
    from shapely.geometry import Point, shape, LineString, Polygon, MultiPolygon
    from shapely.ops import unary_union, nearest_points
    from shapely.strtree import STRtree
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


class EnhancedSailingCalculator:
    """Enhanced sailing calculations for maritime route optimization"""

    def __init__(self, settings_obj):
        self.db = DatabaseManager()
        self.settings = settings_obj  # Store the settings object
        self.earth_radius = self.settings.EARTH_RADIUS_NM  # Nautical miles
        
        # Charts and policy
        self.charts_dir = Path(self.settings.CHARTS_DIR)
        self.coastlines_path = self._resolve_coastline_path()
        self.mdata_path = self.charts_dir / self.settings.MARITIME_DATA_JSON
        self.min_offing_nm = self.settings.MIN_OFFING_NM
        self.min_offing_deg = self.min_offing_nm / 60.0  # approx conversion
        self.tss_enforcement = self.settings.TSS_ENFORCEMENT
        self.optimize_inside_pilotage = self.settings.OPTIMIZE_INSIDE_PILOTAGE
        
        # Loaded geodata
        self._land_union: Optional[MultiPolygon] = None
        self._pilotage_zones: List[Polygon] = []
        self._sea_buoys: List[Dict[str, Any]] = []
        self._tss_corridors: List[Dict[str, Any]] = []
        # New NOAA ENC layers
        self._restricted_areas: List[Dict[str, Any]] = []
        self._depth_areas: List[Dict[str, Any]] = [] # polygons with min/max depth
        self._wrecks_obstructions: List[Dict[str, Any]] = []
        self._pipelines_cables: List[Dict[str, Any]] = []
        
        # Spatial indices for quick lookups
        self._restricted_tree = None
        self._depth_tree = None
        self._hazards_tree = None

        self._load_charts()
        
    def _resolve_coastline_path(self) -> Path:
        """Find coastline file with fallbacks to common names"""
        p = self.charts_dir / self.settings.COASTLINES_GEOJSON
        if p.exists():
            return p
        # fallbacks (e.g., Natural Earth file names)
        for cand in self.charts_dir.glob("*coastline*.json"):
            return cand
        for cand in self.charts_dir.glob("*land*.geojson"):
            return cand
        for cand in self.charts_dir.glob("*land*.json"):
            return cand
        return p

    def _parse_geojson_features(self, file_path: Path) -> List[Any]:
        """Helper to parse GeoJSON and return shapely geometries."""
        geoms = []
        if not file_path.exists():
            return geoms
        try:
            with open(file_path, "r") as f:
                geo = json.load(f)
            if "features" in geo:
                for feat in geo.get("features", []):
                    if feat.get("geometry"):
                        geoms.append(shape(feat["geometry"]))
            elif geo.get("geometry"):
                geoms.append(shape(geo["geometry"]))
        except Exception as e:
            print(f"Error loading GeoJSON from {file_path}: {e}")
        return geoms

    def _load_geojson_with_properties(self, file_path: Path) -> List[Dict[str, Any]]:
        """Helper to load GeoJSON features (geometry + properties)."""
        features_data = []
        if not file_path.exists():
            return features_data
        try:
            with open(file_path, "r") as f:
                geo = json.load(f)
            
            features_list = []
            if isinstance(geo, dict) and "features" in geo:
                features_list = geo.get("features", [])
            elif isinstance(geo, list):
                features_list = geo

            for feat in features_list:
                if feat.get("geometry"):
                    features_data.append({
                        "geometry": shape(feat["geometry"]),
                        "properties": feat.get("properties", {})
                    })
        except Exception as e:
            print(f"Error loading GeoJSON features from {file_path}: {e}")
        return features_data

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
        # Snap endpoints: no optimization inside pilotage (per policy)
        s_lat, s_lon = start_lat, start_lon
        e_lat, e_lon = end_lat, end_lon
        if not self.optimize_inside_pilotage:
            s_lat, s_lon = self._snap_to_sea_buoy_if_in_pilotage(start_lat, start_lon)
            e_lat, e_lon = self._snap_to_sea_buoy_if_in_pilotage(end_lat, end_lon)

        waypoints: List[Waypoint] = [Waypoint(latitude=s_lat, longitude=s_lon, name="Departure")]

        # Generate intermediate waypoints
        for i in range(1, num_waypoints + 1):
            fraction = i / (num_waypoints + 1)
            lat, lon = self._interpolate_great_circle(s_lat, s_lon, e_lat, e_lon, fraction)
            waypoints.append(Waypoint(latitude=lat, longitude=lon, name=f"WP{i}"))

        waypoints.append(Waypoint(latitude=e_lat, longitude=e_lon, name="Destination"))

        # Apply avoidance and preference rules (order matters)
        # 1. Land avoidance (high priority)
        waypoints = self.avoid_land_waypoints(waypoints)
        # 2. Restricted areas (enforce avoidance)
        waypoints = self._avoid_restricted_areas_waypoints(waypoints)
        # 3. Shallow depths (enforce avoidance)
        # Note: We need a VesselData object for depth calculations. For waypoint generation,
        # we can use a placeholder or assume average vessel characteristics.
        # This will be refined when a full vessel profile is available.
        # For now, let's assume a default vessel based on settings for initial depth checks.
        default_vessel_for_depth = VesselData(mmsi=0, vessel_type=0, draft=self.settings.DEFAULT_VESSEL_DRAFT_M)
        constraints_for_depth = RouteConstraints(ukc_m=self.settings.UKC_DEFAULT_M)
        waypoints = self._avoid_shallow_depths_waypoints(waypoints, default_vessel_for_depth, constraints_for_depth)
        # 4. Point hazards (wrecks, obstructions) (enforce avoidance)
        waypoints = self._avoid_point_hazards_waypoints(waypoints)
        # 5. TSS preference (bias routing)
        waypoints = self._prefer_tss_corridors(waypoints)
        
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

    def avoid_land_waypoints(self, waypoints: List[Waypoint]) -> List[Waypoint]:
        """Adjust waypoints to avoid land masses and maintain minimum offing."""
        if not SHAPELY_AVAILABLE or self._land_union is None:
            # Fallback to legacy simple checks
            adjusted = []
            for wp in waypoints:
                if self._is_on_land(wp.latitude, wp.longitude):
                    adjusted.append(self._move_offshore(wp))
                else:
                    adjusted.append(wp)
            return adjusted

        adjusted: List[Waypoint] = []
        for wp in waypoints:
            p = Point(wp.longitude, wp.latitude)
            # if inside land or within offing buffer -> push seaward
            if self._point_in_land_buffer(p):
                adjusted.append(self._move_offshore_geo(wp))
            else:
                adjusted.append(wp)
        return adjusted

    def _point_in_land_buffer(self, p: Point) -> bool:
        """Check if point is within land buffer (offing distance)"""
        return p.within(self._land_union.buffer(self.min_offing_deg))

    def _move_offshore_geo(self, waypoint: Waypoint) -> Waypoint:
        """Move waypoint seaward: away from nearest land boundary by required offing."""
        p = Point(waypoint.longitude, waypoint.latitude)
        # nearest point on land to p
        nearest_on_land, _ = nearest_points(self._land_union, p)
        vx = p.x - nearest_on_land.x
        vy = p.y - nearest_on_land.y
        norm = math.hypot(vx, vy) or 1e-6
        # push to just outside buffer with a small extra margin
        needed = self.min_offing_deg + 1e-3
        new_x = nearest_on_land.x + vx / norm * needed
        new_y = nearest_on_land.y + vy / norm * needed
        return Waypoint(
            latitude=new_y,
            longitude=new_x,
            name=f"{waypoint.name} (Offshore)" if waypoint.name else "Offshore Waypoint",
            distance_to_next_nm=waypoint.distance_to_next_nm,
            estimated_time=waypoint.estimated_time
        )
    
    def _is_on_land(self, lat: float, lon: float) -> bool:
        """Simple check if coordinates are on land (coastal areas)"""
        # Check for common land areas in California coast
        
        # San Francisco Bay area - check if too close to shore
        if 37.7 <= lat <= 37.9 and -122.6 <= lon <= -122.3:
            # Check if in the bay (water) or on land
            if lat > 37.8 or lon > -122.4:
                return True
        
        # Los Angeles area - check if too close to shore
        if 33.6 <= lat <= 34.0 and -118.6 <= lon <= -118.0:
            # Check if in the bay (water) or on land
            if lat > 33.8 or lon > -118.3:
                return True
        
        # Santa Barbara area
        if 34.3 <= lat <= 34.5 and -119.8 <= lon <= -119.6:
            if lat > 34.4 or lon > -119.7:
                return True
        
        return False
    
    def _move_offshore(self, waypoint: Waypoint) -> Waypoint:
        """Move waypoint offshore to avoid land"""
        lat, lon = waypoint.latitude, waypoint.longitude
        
        # Move offshore by approximately 0.05 degrees (~3 nautical miles)
        offshore_distance = 0.05
        
        # Determine direction to move offshore based on location
        if 37.7 <= lat <= 37.9 and -122.6 <= lon <= -122.3:
            # San Francisco Bay - move west
            new_lon = lon - offshore_distance
            new_lat = lat
        elif 33.6 <= lat <= 34.0 and -118.6 <= lon <= -118.0:
            # Los Angeles - move south
            new_lat = lat - offshore_distance
            new_lon = lon
        else:
            # Default - move west
            new_lon = lon - offshore_distance
            new_lat = lat
        
        # Create new waypoint with offshore position
        return Waypoint(
            latitude=new_lat,
            longitude=new_lon,
            name=f"{waypoint.name} (Offshore)" if waypoint.name else "Offshore Waypoint",
            distance_to_next_nm=waypoint.distance_to_next_nm,
            estimated_time=waypoint.estimated_time
        )

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

    # --- Chart loading and TSS preference ---

    def _load_charts(self):
        """Load coastlines (land union), pilotage zones, sea buoys, and TSS corridors if available."""
        if not SHAPELY_AVAILABLE:
            return
        try:
            if self.coastlines_path.exists():
                cached_land_buffer_path = self.charts_dir / self.settings.CACHED_LAND_BUFFER_GEOJSON

                if cached_land_buffer_path.exists():
                    with open(cached_land_buffer_path, "r") as f:
                        self._land_union = shape(json.load(f))
                else:
                    with open(self.coastlines_path, "r") as f:
                        geo = json.load(f)
                    geoms = []
                    if "features" in geo:
                        for feat in geo.get("features", []):
                            try:
                                # Ensure geometries are valid and not None before appending
                                geom = shape(feat["geometry"])
                                if geom and not geom.is_empty:
                                    geoms.append(geom)
                            except Exception as parse_err:
                                print(f"Error parsing geometry from feature: {parse_err}")
                                continue
                    elif geo.get("geometry"):
                        # FeatureCollection-less single geometry
                        try:
                            geom = shape(geo.get("geometry", geo))
                            if geom and not geom.is_empty:
                                geoms.append(geom)
                        except Exception as parse_err:
                            print(f"Error parsing geometry from single feature: {parse_err}")
                            pass
                    
                    if geoms:
                        unbuffered_land_union = unary_union(geoms)
                        self._land_union = unbuffered_land_union.buffer(self.min_offing_deg)
                        if self._land_union and not self._land_union.is_empty:
                            with open(cached_land_buffer_path, "w") as f:
                                json.dump(self._land_union.__geo_interface__, f)
                            print(f"Cached buffered land union to {cached_land_buffer_path}")
                        else:
                            print("Warning: Buffered land union is empty or invalid after generation.")
                    else:
                        print("Warning: No valid geometries found in coastlines file.")
            else:
                print(f"Coastlines file not found at {self.coastlines_path}. Land avoidance may be limited.")

            if self.mdata_path.exists():
                with open(self.mdata_path, "r") as f:
                    mdata = json.load(f)

                # Load TSS corridors
                tss_file = mdata.get("tss_corridors_file")
                if tss_file:
                    tss_features = self._load_geojson_with_properties(self.charts_dir / tss_file)
                    for c in tss_features:
                        if c["geometry"].geom_type == "LineString":
                            self._tss_corridors.append({
                                "name": c["properties"].get("name"),
                                "line": c["geometry"],
                                "direction": c["properties"].get("direction", "either"),
                                "corridor_width_nm": float(c["properties"].get("corridor_width_nm", 1.0))
                            })

                # Load Sea Buoys
                sea_buoys_file = mdata.get("sea_buoys_file")
                if sea_buoys_file:
                    self._sea_buoys = self._load_geojson_with_properties(self.charts_dir / sea_buoys_file)

                # Load Pilotage Zones
                pilotage_file = mdata.get("pilotage_zones_file")
                if pilotage_file:
                    pilotage_features = self._load_geojson_with_properties(self.charts_dir / pilotage_file)
                    for z in pilotage_features:
                        if z["geometry"].geom_type == "Polygon":
                            self._pilotage_zones.append(z["geometry"])

                # Load new NOAA ENC layers from dedicated files referenced in maritime_data.json
                restricted_areas_file = mdata.get("restricted_areas_file")
                if restricted_areas_file:
                    self._restricted_areas = self._load_geojson_with_properties(self.charts_dir / restricted_areas_file)
                
                depth_areas_file = mdata.get("depth_areas_file")
                if depth_areas_file:
                    self._depth_areas = self._load_geojson_with_properties(self.charts_dir / depth_areas_file)
                
                wrecks_obstructions_file = mdata.get("wrecks_obstructions_file")
                if wrecks_obstructions_file:
                    self._wrecks_obstructions = self._load_geojson_with_properties(self.charts_dir / wrecks_obstructions_file)
                
                pipelines_cables_file = mdata.get("pipelines_cables_file")
                if pipelines_cables_file:
                    self._pipelines_cables = self._load_geojson_with_properties(self.charts_dir / pipelines_cables_file)

            # Initialize spatial indices
            if self._restricted_areas:
                self._restricted_tree = STRtree([f["geometry"] for f in self._restricted_areas])
            if self._depth_areas:
                self._depth_tree = STRtree([f["geometry"] for f in self._depth_areas])
            if self._wrecks_obstructions:
                self._hazards_tree = STRtree([f["geometry"] for f in self._wrecks_obstructions])
        except Exception as e:
            print(f"Chart load warning: {e}")

    def _snap_to_sea_buoy_if_in_pilotage(self, lat: float, lon: float) -> Tuple[float, float]:
        """If inside a pilotage zone, snap to nearest sea buoy; otherwise return unchanged."""
        if not SHAPELY_AVAILABLE or not self._pilotage_zones or not self._sea_buoys:
            return lat, lon
        p = Point(lon, lat)
        if not any(p.within(poly) for poly in self._pilotage_zones):
            return lat, lon
        # find nearest buoy by GC distance
        best = (lat, lon, float("inf"))
        for b in self._sea_buoys:
            blat, blon = b.get("latitude"), b.get("longitude")
            if blat is None or blon is None:
                continue
            d = self.calculate_great_circle_distance(lat, lon, blat, blon)
            if d < best[2]:
                best = (blat, blon, d)
        return best[0], best[1]

    def _prefer_tss_corridors(self, waypoints: List[Waypoint]) -> List[Waypoint]:
        """Bias near-approach segments to corridor centerlines; optionally enforce one-way."""
        if not SHAPELY_AVAILABLE or not self._tss_corridors:
            return waypoints
        result: List[Waypoint] = [waypoints[0]]
        for i in range(len(waypoints) - 1):
            a, b = waypoints[i], waypoints[i + 1]
            seg = LineString([(a.longitude, a.latitude), (b.longitude, b.latitude)])
            inserted = False
            for c in self._tss_corridors:
                width_deg = float(c["corridor_width_nm"]) / 60.0
                line: LineString = c["line"]
                # If segment passes near the corridor
                if seg.distance(line) <= width_deg:
                    # project midpoint to corridor centerline
                    mid = seg.interpolate(0.5, normalized=True)
                    proj_dist = line.project(mid)
                    proj_pt = line.interpolate(proj_dist)
                    # simple direction preference check
                    if self.tss_enforcement == "enforce":
                        # skip if reverse direction (very coarse check via bearings)
                        corridor_bearing = self._bearing_along_line(line)
                        seg_bearing = self.calculate_bearing(a.latitude, a.longitude, b.latitude, b.longitude)
                        if self._bearing_opposed(seg_bearing, corridor_bearing):
                            # If enforcing, try skipping this near-corridor adjustment
                            continue
                    # insert projected waypoint
                    result.append(Waypoint(latitude=proj_pt.y, longitude=proj_pt.x, name="TSS WP"))
                    inserted = True
                    break
            if not inserted:
                result.append(b)
            else:
                result.append(b)
        return result

    def _bearing_along_line(self, line: LineString) -> float:
        """Approximate overall bearing of corridor line (start->end)."""
        (x1, y1) = line.coords[0]
        (x2, y2) = line.coords[-1]
        return self.calculate_bearing(y1, x1, y2, x2)

    def _bearing_opposed(self, b1: float, b2: float) -> bool:
        """True if bearings roughly opposite (>120 deg apart)."""
        diff = abs(((b1 - b2 + 180) % 360) - 180)
        return diff > 120

    def _avoid_restricted_areas_waypoints(self, waypoints: List[Waypoint]) -> List[Waypoint]:
        """Adjust waypoints to avoid restricted areas."""
        if not SHAPELY_AVAILABLE or not self._restricted_tree:
            return waypoints

        adjusted_waypoints: List[Waypoint] = []
        for wp in waypoints:
            p = Point(wp.longitude, wp.latitude)
            if self._is_in_restricted_area(p):
                # Move waypoint away from the nearest restricted area
                # This is a simplified approach, a more advanced method would consider the boundary.
                new_lat, new_lon = self._move_away_from_polygon(p, self._restricted_tree, self._restricted_areas, self.min_offing_deg)
                adjusted_waypoints.append(Waypoint(latitude=new_lat, longitude=new_lon, name=f"{wp.name} (Avoid Restricted)"))
            else:
                adjusted_waypoints.append(wp)
        return adjusted_waypoints

    def _avoid_shallow_depths_waypoints(self, waypoints: List[Waypoint], vessel: Optional[VesselData], constraints: RouteConstraints) -> List[Waypoint]:
        """Adjust waypoints to avoid areas shallower than the required depth."""
        if not SHAPELY_AVAILABLE or not self._depth_tree:
            return waypoints

        adjusted_waypoints: List[Waypoint] = []
        for wp in waypoints:
            p = Point(wp.longitude, wp.latitude)
            # We use a default speed for this check if not available from waypoint, or from constraints
            segment_speed = wp.speed_knots or (constraints.max_speed_knots + constraints.min_speed_knots) / 2

            if self._is_over_shallow_depth(p, vessel, segment_speed, constraints.ukc_m):
                # Move waypoint to deeper water - this is a complex problem.
                # For now, a simple outward move, or a more sophisticated pathfinding around shallowest point.
                new_lat, new_lon = self._move_away_from_shallow(p, vessel, segment_speed, constraints.ukc_m, self.min_offing_deg) # Re-using offing buffer for avoidance
                adjusted_waypoints.append(Waypoint(latitude=new_lat, longitude=new_lon, name=f"{wp.name} (Avoid Shallow)"))
            else:
                adjusted_waypoints.append(wp)
        return adjusted_waypoints

    def _avoid_point_hazards_waypoints(self, waypoints: List[Waypoint]) -> List[Waypoint]:
        """Adjust waypoints to avoid point hazards (wrecks, obstructions)."""
        if not SHAPELY_AVAILABLE or not self._hazards_tree:
            return waypoints

        adjusted_waypoints: List[Waypoint] = []
        hazard_buffer_deg = self.settings.MIN_OFFING_NM / 60.0 # Use offing as buffer for hazards

        for wp in waypoints:
            p = Point(wp.longitude, wp.latitude)
            if self._is_near_hazard(p, hazard_buffer_deg):
                new_lat, new_lon = self._move_away_from_point_hazard(p, self._hazards_tree, self._wrecks_obstructions, hazard_buffer_deg)
                adjusted_waypoints.append(Waypoint(latitude=new_lat, longitude=new_lon, name=f"{wp.name} (Avoid Hazard)"))
            else:
                adjusted_waypoints.append(wp)
        return adjusted_waypoints

    def _move_away_from_polygon(self, p: Point, tree: STRtree, features: List[Dict[str, Any]], buffer_deg: float) -> Tuple[float, float]:
        """Move a point away from the nearest polygon feature in a given spatial tree."""
        nearest_geoms = tree.query(p.buffer(buffer_deg))
        if not nearest_geoms: # No nearby polygons, return original point
            return p.y, p.x

        min_dist = float('inf')
        closest_point_on_feature = None

        for idx in nearest_geoms:
            feature_geom = features[idx]["geometry"]
            if feature_geom.intersects(p): # If inside or touching
                closest_point_on_feature = nearest_points(feature_geom, p)[0] # Point on boundary
                break
            dist = p.distance(feature_geom)
            if dist < min_dist:
                min_dist = dist
                closest_point_on_feature = nearest_points(feature_geom, p)[0]
        
        if closest_point_on_feature: # Push point away from the closest boundary point
            vx = p.x - closest_point_on_feature.x
            vy = p.y - closest_point_on_feature.y
            norm = math.hypot(vx, vy) or 1e-6
            # Push slightly beyond the buffer
            push_distance = buffer_deg + 1e-4 # small margin
            new_x = closest_point_on_feature.x + vx / norm * push_distance
            new_y = closest_point_on_feature.y + vy / norm * push_distance
            return new_y, new_x
        
        return p.y, p.x # Fallback
    
    def _move_away_from_shallow(self, p: Point, vessel: Optional[VesselData], speed_knots: float, ukc_m: float, buffer_deg: float, max_attempts: int = 10) -> Tuple[float, float]:
        """Move a point away from shallow water into deeper water by iteratively checking surrounding depths."""
        current_lat, current_lon = p.y, p.x
        best_lat, best_lon = current_lat, current_lon
        best_depth = self._get_min_depth_at_point(p)
        
        if best_depth is None: # If no depth data at current point, can't make an informed decision.
            return current_lat, current_lon # Fallback

        # Define small step size for exploring surrounding points (e.g., 0.1 nm)
        step_size_deg = 0.1 / 60.0 
        
        # Try moving in various directions to find deeper water
        for attempt in range(max_attempts):
            found_deeper = False
            for angle_deg in np.arange(0, 360, 45): # Check 8 directions
                angle_rad = math.radians(angle_deg)
                test_lon = current_lon + step_size_deg * math.cos(angle_rad)
                test_lat = current_lat + step_size_deg * math.sin(angle_rad)
                test_p = Point(test_lon, test_lat)

                if not self._is_over_shallow_depth(test_p, vessel, speed_knots, ukc_m):
                    test_depth = self._get_min_depth_at_point(test_p)
                    if test_depth is not None and test_depth > best_depth:
                        best_lat, best_lon = test_lat, test_lon
                        best_depth = test_depth
                        found_deeper = True
                        break # Found a better spot, move there and re-evaluate
            
            if found_deeper:
                current_lat, current_lon = best_lat, best_lon
            else:
                break # Can't find a deeper spot in this iteration, or reached max attempts
        
        return best_lat, best_lon

    def _move_away_from_point_hazard(self, p: Point, tree: STRtree, features: List[Dict[str, Any]], buffer_deg: float) -> Tuple[float, float]:
        """Move a point away from the nearest point hazard (wreck/obstruction)."""
        nearest_hazards_indices = tree.query(p.buffer(buffer_deg)) # Query for nearby hazards
        if not nearest_hazards_indices: # No nearby hazards, return original point
            return p.y, p.x

        # Find the closest actual hazard
        min_dist = float('inf')
        closest_hazard_geom = None

        for idx in nearest_hazards_indices:
            hazard_geom = features[idx]["geometry"]
            dist = p.distance(hazard_geom)
            if dist < min_dist:
                min_dist = dist
                closest_hazard_geom = hazard_geom
        
        if closest_hazard_geom: # Push point away from the closest hazard
            vx = p.x - closest_hazard_geom.x
            vy = p.y - closest_hazard_geom.y
            norm = math.hypot(vx, vy) or 1e-6
            push_distance = buffer_deg + 1e-4 # push slightly beyond the buffer
            new_x = closest_hazard_geom.x + vx / norm * push_distance
            new_y = closest_hazard_geom.y + vy / norm * push_distance
            return new_y, new_x
        
        return p.y, p.x # Fallback

    def _estimate_squat_m(self, vessel: Optional[VesselData], speed_knots: float) -> float:
        """
        Conservative open-water squat estimate:
        squat = coeff * (V^2) / 100  (V in knots)
        coeff by vessel type (broad rule-of-thumb):
          - Tanker/Bulk: 1.0
          - Container/General cargo: 0.8
          - Passenger/HS: 0.6
          - Fallback: 0.7
        """
        v = max(0.0, speed_knots or 0.0)
        if vessel is None:
            vt = 0 # Default to unknown vessel type
        else:
            vt = (vessel.vessel_type or 0)
        
        if vt in (62, 64):        # cargo, tanker
            coeff = 1.0
        elif vt in (60, 40):      # passenger, HSC
            coeff = 0.6
        else:
            coeff = 0.8 if vt else 0.7
        return coeff * (v * v) / 100.0

    def _required_depth_m(self, vessel: Optional[VesselData], speed_knots: float, ukc_m: float) -> float:
        """Calculate required depth including draft, UKC, and squat"""
        if vessel is None:
            draft = getattr(self.settings, "DEFAULT_VESSEL_DRAFT_M", 10.5)
        else:
            draft = vessel.draft if vessel.draft else getattr(self.settings, "DEFAULT_VESSEL_DRAFT_M", 10.5)
            
        squat = self._estimate_squat_m(vessel, speed_knots)
        margin = max(ukc_m, squat)
        return draft + margin

    def _calculate_safety_depth_m(self, vessel: Optional[VesselData], speed_knots: float, 
                                  ukc_m: float, tide_height_m: float = 0.0) -> float:
        """Calculate the shallow contour depth (absolute danger of grounding)"""
        draft = vessel.draft if vessel and vessel.draft else getattr(self.settings, "DEFAULT_VESSEL_DRAFT_M", 10.5)
        squat = self._estimate_squat_m(vessel, speed_knots) if (vessel and getattr(vessel, 'apply_squat', True)) else 0.0
        # shallow contour = max static draft + UKC + squat - tide (for safety, we assume tide = 0 for min depth)
        # For calculation of shallow contour, we take worst case (0 tide for depth below vessel)
        return draft + ukc_m + squat - tide_height_m # tide_height_m is expected to be a future input

    def _get_safety_contour_m(self, shallow_contour_m: float) -> float:
        """Determine the safety contour depth based on the shallow contour and a safety margin"""
        return shallow_contour_m + self.settings.SAFETY_DEPTH_MARGIN_M

    def _is_in_restricted_area(self, p: Point) -> bool:
        """Check if a point is within any restricted area."""
        if not SHAPELY_AVAILABLE or not self._restricted_tree:
            return False
        # Query the STRtree for intersecting restricted areas
        for idx in self._restricted_tree.query(p):
            if self._restricted_areas[idx]["geometry"].contains(p):
                return True
        return False

    def _get_min_depth_at_point(self, p: Point) -> Optional[float]:
        """Get the minimum depth in meters at a given point from loaded depth areas."""
        if not SHAPELY_AVAILABLE or not self._depth_tree:
            return None
        # Find all depth areas that contain the point
        containing_depth_areas = []
        for idx in self._depth_tree.query(p):
            depth_area = self._depth_areas[idx]
            if depth_area["geometry"].contains(p):
                containing_depth_areas.append(depth_area)
        
        if not containing_depth_areas:
            # If no specific depth area is found, assume deep water or unknown
            return 9999.0 # Effectively infinite depth

        # Get the shallowest max_depth_m (DRVAL2) from containing areas
        min_depth = float('inf')
        for area in containing_depth_areas:
            max_depth_m = area["properties"].get("DRVAL2") # Shallowest value in depth range (ECDIS convention)
            if max_depth_m is not None:
                min_depth = min(min_depth, max_depth_m)
        
        return min_depth if min_depth != float('inf') else None

    def _is_over_shallow_depth(self, p: Point, vessel: Optional[VesselData], speed_knots: float, ukc_m: float) -> bool:
        """Check if a point is over water shallower than the required depth (shallow contour)."""
        if not SHAPELY_AVAILABLE or not self._depth_tree:
            return False
        
        required_depth = self._required_depth_m(vessel, speed_knots, ukc_m) # This includes draft, UKC, squat
        available_depth = self._get_min_depth_at_point(p)

        if available_depth is None: # Assume safe if no depth data for that point, or handle as unknown/unsafe
            return False # For now, assume safe if no data

        return available_depth < required_depth

    def _is_near_hazard(self, p: Point, buffer_deg: float = 0.01) -> bool:
        """Check if a point is too close to a wreck or obstruction."""
        if not SHAPELY_AVAILABLE or not self._hazards_tree:
            return False
        # Query the STRtree for hazards within a buffer (e.g., 0.01 degrees ~ 0.6 nm)
        for idx in self._hazards_tree.query(p.buffer(buffer_deg)):
            hazard_geom = self._wrecks_obstructions[idx]["geometry"]
            if p.distance(hazard_geom) < buffer_deg: # Check actual distance
                return True
        return False
