#!/usr/bin/env python3
"""
Test script for Maritime Navigation Calculations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from maritime_app.navigation.maritime_navigation import MaritimeNavigation, Position

def test_navigation_calculations():
    """Test the navigation calculations"""
    print("🧭 Testing Maritime Navigation Calculations")
    print("=" * 50)
    
    # Initialize navigation calculator
    nav = MaritimeNavigation()
    
    # Test positions (San Francisco Bay area)
    sf_pos = Position(37.7749, -122.4194)  # San Francisco
    oak_pos = Position(37.8044, -122.2711)  # Oakland
    sj_pos = Position(37.3382, -121.8863)   # San Jose
    
    print(f"📍 Test Positions:")
    print(f"  San Francisco: {sf_pos.lat:.4f}, {sf_pos.lon:.4f}")
    print(f"  Oakland: {oak_pos.lat:.4f}, {oak_pos.lon:.4f}")
    print(f"  San Jose: {sj_pos.lat:.4f}, {sj_pos.lon:.4f}")
    
    # Test 1: Great Circle Course SF to Oakland
    print(f"\n🧭 Test 1: Great Circle Course (SF → Oakland)")
    course_result = nav.calculate_course(sf_pos, oak_pos, use_great_circle=True)
    print(f"  True Course: {course_result.true_course:.1f}°")
    print(f"  Distance: {course_result.distance_nm:.2f} nm")
    print(f"  Calculation: {course_result.calculation_type}")
    
    # Test 2: Rhumb Line Course SF to Oakland
    print(f"\n🧭 Test 2: Rhumb Line Course (SF → Oakland)")
    course_result = nav.calculate_course(sf_pos, oak_pos, use_great_circle=False)
    print(f"  True Course: {course_result.true_course:.1f}°")
    print(f"  Distance: {course_result.distance_nm:.2f} nm")
    print(f"  Calculation: {course_result.calculation_type}")
    
    # Test 3: Cross Track Error
    print(f"\n🧭 Test 3: Cross Track Error")
    current_pos = Position(37.7899, -122.3456)  # Somewhere between SF and Oakland
    cte = nav.cross_track_error(current_pos, sf_pos, oak_pos)
    print(f"  Current Position: {current_pos.lat:.4f}, {current_pos.lon:.4f}")
    print(f"  Cross Track Error: {cte.error_nm:.2f} nm")
    print(f"  Bearing to Route: {cte.bearing_to_route:.1f}°")
    print(f"  Position on Route: {cte.position_on_route.lat:.4f}, {cte.position_on_route.lon:.4f}")
    
    # Test 4: Course Made Good
    print(f"\n🧭 Test 4: Course Made Good")
    cmg_data = nav.course_made_good(sf_pos, current_pos, sj_pos)
    print(f"  Course Made Good: {cmg_data['course_made_good']:.1f}°")
    print(f"  Distance Made Good: {cmg_data['distance_made_good_nm']:.2f} nm")
    print(f"  Course to Target: {cmg_data['course_to_target']:.1f}°")
    print(f"  Distance to Target: {cmg_data['distance_to_target_nm']:.2f} nm")
    print(f"  Progress: {cmg_data['progress_percent']:.1f}%")
    
    # Test 5: Generate Waypoints
    print(f"\n🧭 Test 5: Generate Waypoints (SF → San Jose)")
    waypoints = nav.generate_waypoints(sf_pos, sj_pos, num_waypoints=5)
    print(f"  Generated {len(waypoints)} waypoints:")
    for i, wp in enumerate(waypoints):
        print(f"    {i+1}. {wp.lat:.4f}, {wp.lon:.4f}")
    
    # Test 6: ETA Calculation
    print(f"\n🧭 Test 6: ETA Calculation")
    speed = 15.0  # 15 knots
    eta = nav.calculate_eta(sf_pos, sj_pos, speed)
    print(f"  Speed: {speed} knots")
    print(f"  ETA: {eta.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n✅ All navigation tests completed successfully!")

if __name__ == "__main__":
    test_navigation_calculations()
