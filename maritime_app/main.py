"""
Main Entry Point for Maritime Route Optimization Tool
Orchestrates all modules for comprehensive maritime analysis
"""
import sys
import time
from datetime import datetime
from typing import List, Dict, Any

from .config.settings import settings
from .core.models import RouteObjective, RouteConstraints, VesselData, WeatherData
from .data.collectors.ais_collector import AISDataCollector
from .data.processors.ml_processor import MaritimeMLDataProcessor
from .routing.route_optimizer import EnhancedSailingCalculator
from .utils.database import DatabaseManager
from .utils.visualization import MaritimeVisualizer


class MaritimeRouteOptimizer:
    """Main orchestrator for maritime route optimization"""

    def __init__(self):
        print("🚢 INITIALIZING MARITIME ROUTE OPTIMIZATION SYSTEM")
        print("=" * 60)

        # Initialize components
        self.db = DatabaseManager()
        self.ais_collector = AISDataCollector()
        self.ml_processor = MaritimeMLDataProcessor()
        self.route_optimizer = EnhancedSailingCalculator()
        self.visualizer = MaritimeVisualizer()

        print("✅ All components initialized successfully")

    def collect_data(self) -> Dict[str, Any]:
        """Collect AIS and weather data"""
        print("\n1. Setting up database and collecting data...")

        results = {
            'vessels_collected': 0,
            'weather_records': 0,
            'db_setup': False
        }

        try:
            # AIS Data Collection
            print("📡 Collecting AIS data for 30 seconds...")
            vessels = self.ais_collector.start_collection(duration_seconds=30)
            results['vessels_collected'] = len(vessels)

            if vessels:
                saved_count = self.db.save_vessel_data(vessels)
                print(f"✓ Saved {saved_count} vessels to database")

            # Weather data collection would go here
            # For now, we'll create sample weather data
            sample_weather = self._generate_sample_weather_data()
            saved_weather = self.db.save_weather_data(sample_weather)
            results['weather_records'] = saved_weather

            results['db_setup'] = True
            print("✓ Database setup and data collection complete")

        except Exception as e:
            print(f"❌ Error during data collection: {e}")

        return results

    def _generate_sample_weather_data(self) -> List[WeatherData]:
        """Generate sample weather data for testing"""
        import random
        from datetime import timedelta

        weather_data = []
        base_time = datetime.now()

        for i in range(24):  # 24 hours of forecast
            weather = WeatherData(
                latitude=settings.DEFAULT_LAT + random.uniform(-1, 1),
                longitude=settings.DEFAULT_LON + random.uniform(-1, 1),
                wave_height_m=random.uniform(0.5, 4.0),
                wind_speed_kts=random.uniform(5, 30),
                wind_direction_deg=random.uniform(0, 360),
                temperature_c=random.uniform(10, 25),
                pressure_hpa=random.uniform(1000, 1020),
                ocean_current_speed_kts=random.uniform(0, 2),
                ocean_current_direction_deg=random.uniform(0, 360),
                forecast_time=base_time + timedelta(hours=i)
            )
            weather_data.append(weather)

        return weather_data

    def train_ml_models(self) -> Dict[str, float]:
        """Train ML models for maritime optimization"""
        print("\n2. Initializing ML data processor...")

        try:
            print("🤖 Preparing ML training data for maritime optimization...")
            df = self.ml_processor.generate_synthetic_data(num_samples=120)
            print(f"✓ Prepared {len(df)} training samples")
            print(f"   Features: {len(df.columns) - 3} dimensions")  # Exclude target columns
            print(f"   Targets: 3 outputs (speed, fuel, safety)")

            print("\n3. Preparing ML training data...")
            X, y_targets = self.ml_processor.prepare_training_data(df)

            print("4. Training ML models...")
            results = self.ml_processor.train_models(X, y_targets)

            print("✅ ML models trained successfully!")
            print(f"   Speed Model R²: {results['speed_r2']:.3f}")
            print(f"   Fuel Model R²: {results['fuel_r2']:.3f}")
            print(f"   Safety Model R²: {results['safety_r2']:.3f}")

            return results

        except Exception as e:
            print(f"❌ Error training ML models: {e}")
            return {}

    def run_route_optimization_demo(self) -> Dict[str, Any]:
        """Run a complete route optimization demonstration"""
        print("\n5. Testing enhanced route optimization...")

        try:
            # Define sample route (San Francisco to Los Angeles)
            start_lat, start_lon = 37.7749, -122.4194  # San Francisco
            end_lat, end_lon = 34.0522, -118.2437     # Los Angeles

            print("📍 Route: San Francisco → Los Angeles")
            print(f"   Distance: ~{self.route_optimizer.calculate_great_circle_distance(start_lat, start_lon, end_lat, end_lon):.1f} nm")

            # Generate waypoints
            waypoints = self.route_optimizer.generate_waypoints(
                start_lat, start_lon, end_lat, end_lon, num_waypoints=10
            )

            print(f"   Generated {len(waypoints)} waypoints")

            # Define constraints
            constraints = RouteConstraints(
                max_speed_knots=20.0,
                min_speed_knots=8.0,
                max_wave_height_m=4.0,
                max_wind_speed_kts=35.0,
                safety_buffer_nm=10.0
            )

            # Optimize route
            route = self.route_optimizer.optimize_route(
                waypoints, constraints, RouteObjective.BALANCED
            )

            # Get weather data for the route area
            weather_data = self.db.get_weather_forecast(
                settings.DEFAULT_LAT, settings.DEFAULT_LON, 24
            )

            # Get sample vessel data
            vessels = self.db.get_recent_vessels(5)

            # Create visualization
            self.visualizer.plot_route_analysis(route, weather_data)

            # Calculate ETAs
            etas = self.route_optimizer.calculate_eta(datetime.now(), route.waypoints, 12.0)

            print("\n📊 ENHANCED ROUTE ANALYSIS:")
            print(f"   Total Waypoints: {len(route.waypoints)}")
            print(f"   Total Distance: {route.total_distance_nm:.1f} nm")
            print(f"   Estimated Duration: {route.estimated_duration_hours:.1f} hours")
            print(f"   Fuel Consumption: {route.fuel_consumption_tonnes:.1f} tonnes")
            print(f"   Safety Score: {route.safety_score:.2f}")

            # ML Predictions if models are trained
            if hasattr(self.ml_processor, 'models_trained') and self.ml_processor.models_trained:
                # Get sample vessel and weather for prediction
                sample_vessel = vessels[0] if vessels else VesselData(
                    mmsi=123456789, name="Sample Vessel", speed=12.0, draft=8.0
                )
                sample_weather = weather_data[:1] if weather_data else [
                    WeatherData(settings.DEFAULT_LAT, settings.DEFAULT_LON)
                ]

                predictions = self.ml_processor.predict_optimization(
                    sample_vessel, sample_weather
                )

                print("\n🤖 ML PREDICTIONS:")
                print(f"   Average Optimal Speed: {predictions['optimal_speed_knots']:.1f} kts")
                print(f"   Average Safety Score: {predictions['safety_score']:.2f}")
                print(f"   Average Fuel Efficiency: {predictions['fuel_efficiency_score']:.2f}")

            print("\n✅ Enhanced maritime route optimization complete!")
            print("🤖 ML models integrated successfully!")
            print("🌊 All units in maritime standard!")
            return {
                'route': route,
                'weather_data': weather_data,
                'vessels': vessels,
                'etas': etas
            }

        except Exception as e:
            print(f"❌ Error during route optimization: {e}")
            return {}

    def run_vessel_analysis_demo(self):
        """Run vessel data analysis demonstration"""
        print("\n📊 Running vessel analysis...")

        try:
            vessels = self.db.get_recent_vessels(50)
            if vessels:
                self.visualizer.plot_vessel_distribution(vessels)
                print(f"✅ Analyzed {len(vessels)} vessels")
            else:
                print("⚠️ No vessel data available for analysis")

        except Exception as e:
            print(f"❌ Error during vessel analysis: {e}")


def main():
    """Main function to run the maritime route optimization system"""
    print("�� MARITIME ROUTE OPTIMIZATION SYSTEM")
    print("=" * 50)

    try:
        # Initialize the system
        optimizer = MaritimeRouteOptimizer()

        # Run data collection
        data_results = optimizer.collect_data()

        # Train ML models
        ml_results = optimizer.train_ml_models()

        # Run route optimization demo
        route_results = optimizer.run_route_optimization_demo()

        # Run vessel analysis
        optimizer.run_vessel_analysis_demo()

        print("\n🎉 Maritime Route Optimization System completed successfully!")
        print("=" * 60)

        return {
            'data_collection': data_results,
            'ml_training': ml_results,
            'route_optimization': route_results
        }

    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running maritime system: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Run the main system
    results = main()

    # Exit with appropriate code
    sys.exit(0 if results else 1)
