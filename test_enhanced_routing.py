#!/usr/bin/env python3
"""
Test script for enhanced maritime routing system
Tests land avoidance, TSS enforcement, and pilotage snapping
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from maritime_app.routing.route_optimizer import EnhancedSailingCalculator
from maritime_app.core.models import RouteConstraints, RouteObjective, VesselData
from maritime_app.config.settings import settings

def test_basic_routing():
    """Test basic routing functionality"""
    print("🧭 Testing Basic Routing")
    print("=" * 50)
    
    calc = EnhancedSailingCalculator(settings)
    
    # Test SF to LA route (should snap to sea buoys if in pilotage)
    start_lat, start_lon = 37.8044, -122.2712  # SF (inside pilotage zone)
    end_lat, end_lon = 33.7701, -118.1937      # LA/LB (inside pilotage zone)
    
    print(f"Original route: SF ({start_lat}, {start_lon}) → LA ({end_lat}, {end_lon})")
    
    # Generate waypoints
    waypoints = calc.generate_waypoints(start_lat, start_lon, end_lat, end_lon, num_waypoints=8)
    
    print(f"\nGenerated {len(waypoints)} waypoints:")
    for i, wp in enumerate(waypoints):
        print(f"  {i+1:2d}. {wp.name:15s} ({wp.latitude:8.4f}, {wp.longitude:9.4f})")
    
    # Test distance calculation
    total_distance = 0
    for i in range(len(waypoints) - 1):
        wp1, wp2 = waypoints[i], waypoints[i + 1]
        distance = calc.calculate_great_circle_distance(
            wp1.latitude, wp1.longitude, wp2.latitude, wp2.longitude
        )
        total_distance += distance
        wp1.distance_to_next_nm = distance
    
    print(f"\nTotal route distance: {total_distance:.1f} nm")
    
    return waypoints

def test_chart_loading():
    """Test chart data loading"""
    print("\n🗺️  Testing Chart Loading")
    print("=" * 50)
    
    calc = EnhancedSailingCalculator(settings)
    
    # Check what data was loaded
    print(f"Charts directory: {calc.charts_dir}")
    print(f"Coastlines file: {calc.coastlines_path} (exists: {calc.coastlines_path.exists()})")
    print(f"Maritime data file: {calc.mdata_path} (exists: {calc.mdata_path.exists()})")
    print(f"Shapely available: {hasattr(calc, '_land_union') and calc._land_union is not None}")
    print(f"Pilotage zones loaded: {len(calc._pilotage_zones)}")
    print(f"Sea buoys loaded: {len(calc._sea_buoys)}")
    print(f"TSS corridors loaded: {len(calc._tss_corridors)}")
    
    # List loaded data
    if calc._sea_buoys:
        print("\nSea buoys:")
        for buoy in calc._sea_buoys[:5]:  # Show first 5
            print(f"  - {buoy['name']} ({buoy['latitude']:.4f}, {buoy['longitude']:.4f})")
    
    if calc._tss_corridors:
        print("\nTSS corridors:")
        for corridor in calc._tss_corridors:
            print(f"  - {corridor['name']} ({corridor['direction']}, {corridor['corridor_width_nm']} nm)")

def test_route_optimization():
    """Test full route optimization"""
    print("\n⚡ Testing Route Optimization")
    print("=" * 50)
    
    calc = EnhancedSailingCalculator(settings)
    
    # Create test constraints
    constraints = RouteConstraints(
        max_speed_knots=18.0,
        min_speed_knots=12.0,
        vessel_draft_m=10.5,
        ukc_m=0.6,
        apply_squat=True
    )
    
    # Generate waypoints
    waypoints = calc.generate_waypoints(37.8044, -122.2712, 33.7701, -118.1937, num_waypoints=10)
    
    # Optimize route
    route = calc.optimize_route(waypoints, constraints, RouteObjective.BALANCED)
    
    print(f"Route optimization complete:")
    print(f"  Total distance: {route.total_distance_nm:.1f} nm")
    print(f"  Estimated duration: {route.estimated_duration_hours:.1f} hours")
    print(f"  Fuel consumption: {route.fuel_consumption_tonnes:.1f} tonnes")
    print(f"  Safety score: {route.safety_score:.3f}")
    
    return route

def test_squat_calculation():
    """Test squat calculation"""
    print("\n🌊 Testing Squat Calculation")
    print("=" * 50)
    
    calc = EnhancedSailingCalculator(settings)
    
    # Test different vessel types and speeds
    test_cases = [
        (VesselData(mmsi=123456, vessel_type=64, draft=10.5), 12.0, "Tanker at 12 kts"),
        (VesselData(mmsi=123457, vessel_type=62, draft=8.5), 15.0, "Cargo at 15 kts"),
        (VesselData(mmsi=123458, vessel_type=60, draft=6.0), 20.0, "Passenger at 20 kts"),
        (VesselData(mmsi=123459, vessel_type=0, draft=5.0), 14.0, "Unknown vessel at 14 kts")
    ]
    
    for vessel, speed, description in test_cases:
        squat = calc._estimate_squat_m(vessel, speed)
        required_depth = calc._required_depth_m(vessel, speed, 0.6)
        print(f"  {description:25s}: squat={squat:.2f}m, required_depth={required_depth:.1f}m")

def main():
    """Run all tests"""
    print("🚢 Maritime Route Optimization - Enhanced Testing")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Min offing: {settings.MIN_OFFING_NM} nm")
    print(f"  Default draft: {settings.DEFAULT_VESSEL_DRAFT_M} m")
    print(f"  Default UKC: {settings.UKC_DEFAULT_M} m")
    print(f"  TSS enforcement: {settings.TSS_ENFORCEMENT}")
    print(f"  Optimize in pilotage: {settings.OPTIMIZE_INSIDE_PILOTAGE}")
    
    try:
        # Run tests
        test_chart_loading()
        test_basic_routing()
        test_squat_calculation()
        route = test_route_optimization()
        
        print("\n✅ All tests completed successfully!")
        print(f"Final route has {len(route.waypoints)} waypoints covering {route.total_distance_nm:.1f} nm")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
