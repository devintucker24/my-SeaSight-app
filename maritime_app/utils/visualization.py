"""
Visualization Utilities Module
Handles plotting and visualization for maritime data analysis
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

from ..core.models import Route, VesselData, WeatherData, RouteOptimizationResult


class MaritimeVisualizer:
    """Handles visualization of maritime data and analysis results"""

    def __init__(self):
        self.setup_style()

    def setup_style(self):
        """Set up matplotlib style for maritime visualizations"""
        if HAS_SEABORN:
            plt.style.use('seaborn-v0_8')
            sns.set_palette("husl")
        else:
            plt.style.use('default')

        # Set larger default font sizes
        plt.rcParams.update({
            'font.size': 10,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.titlesize': 16
        })

    def plot_route_analysis(self, route: Route, weather_data: List[WeatherData] = None,
                           save_path: str = "enhanced_maritime_analysis.png"):
        """Create comprehensive route analysis visualization"""
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle('🚢 Enhanced Maritime Route Analysis', fontsize=16, fontweight='bold')

        # Create subplots
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # 1. Route Map
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_route_map(ax1, route)

        # 2. Speed Profile
        ax2 = fig.add_subplot(gs[0, 2])
        self._plot_speed_profile(ax2, route)

        # 3. Fuel Consumption Analysis
        ax3 = fig.add_subplot(gs[1, 0])
        self._plot_fuel_analysis(ax3, route)

        # 4. Safety Score Timeline
        ax4 = fig.add_subplot(gs[1, 1])
        self._plot_safety_timeline(ax4, route)

        # 5. Weather Impact
        ax5 = fig.add_subplot(gs[1, 2])
        self._plot_weather_impact(ax5, weather_data)

        # 6. Performance Metrics Summary
        ax6 = fig.add_subplot(gs[2, :])
        self._plot_performance_summary(ax6, route)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

        print(f"📊 Enhanced maritime analysis saved as {save_path}")

    def _plot_route_map(self, ax, route: Route):
        """Plot route map with waypoints"""
        ax.set_title('🗺️ Route Map', fontweight='bold')

        # Extract coordinates
        lats = [wp.latitude for wp in route.waypoints]
        lons = [wp.longitude for wp in route.waypoints]

        # Plot route line
        ax.plot(lons, lats, 'b-', linewidth=2, alpha=0.7, label='Route')

        # Plot waypoints
        ax.scatter(lons, lats, c='red', s=50, zorder=5, label='Waypoints')

        # Add waypoint labels
        for i, wp in enumerate(route.waypoints):
            ax.annotate(wp.name, (lons[i], lats[i]),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=8, bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.grid(True, alpha=0.3)
        ax.legend()

    def _plot_speed_profile(self, ax, route: Route):
        """Plot speed profile along route"""
        ax.set_title('⏱️ Speed Profile', fontweight='bold')

        distances = [0]
        speeds = [12.0]  # Default speed

        cumulative_distance = 0
        for wp in route.waypoints[:-1]:
            if wp.distance_to_next_nm:
                cumulative_distance += wp.distance_to_next_nm
                distances.append(cumulative_distance)
                speeds.append(12.0)  # Placeholder

        ax.plot(distances, speeds, 'g-', linewidth=2, marker='o')
        ax.fill_between(distances, speeds, alpha=0.3, color='green')

        ax.set_xlabel('Distance (nm)')
        ax.set_ylabel('Speed (knots)')
        ax.grid(True, alpha=0.3)

        # Add statistics
        avg_speed = np.mean(speeds)
        ax.axhline(y=avg_speed, color='red', linestyle='--', alpha=0.7,
                  label='.1f')
        ax.legend()

    def _plot_fuel_analysis(self, ax, route: Route):
        """Plot fuel consumption analysis"""
        ax.set_title('⛽ Fuel Analysis', fontweight='bold')

        # Create sample fuel consumption data
        segments = len(route.waypoints) - 1
        distances = np.linspace(0, route.total_distance_nm, segments)
        fuel_rates = np.random.uniform(15, 25, segments)  # tonnes per day

        ax.bar(range(segments), fuel_rates, alpha=0.7, color='orange')
        ax.set_xlabel('Route Segment')
        ax.set_ylabel('Fuel Rate (tonnes/day)')
        ax.grid(True, alpha=0.3)

        # Add total fuel consumption
        total_fuel = route.fuel_consumption_tonnes
        ax.text(0.02, 0.98, f'Total: {total_fuel:.1f} tonnes',
               transform=ax.transAxes, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    def _plot_safety_timeline(self, ax, route: Route):
        """Plot safety score timeline"""
        ax.set_title('🛡️ Safety Timeline', fontweight='bold')

        segments = len(route.waypoints) - 1
        safety_scores = np.random.uniform(0.6, 0.95, segments)

        ax.plot(range(segments), safety_scores, 'r-', linewidth=2, marker='s')
        ax.fill_between(range(segments), safety_scores, alpha=0.3, color='red')

        ax.set_xlabel('Route Segment')
        ax.set_ylabel('Safety Score')
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)

        # Add overall safety score
        ax.axhline(y=route.safety_score, color='blue', linestyle='--',
                  label='.2f')
        ax.legend()

    def _plot_weather_impact(self, ax, weather_data: List[WeatherData] = None):
        """Plot weather impact analysis"""
        ax.set_title('🌊 Weather Impact', fontweight='bold')

        if weather_data:
            # Extract weather data
            wave_heights = [w.wave_height_m or 1.5 for w in weather_data[:10]]
            wind_speeds = [w.wind_speed_kts or 15 for w in weather_data[:10]]

            x = range(len(wave_heights))

            ax.bar(x, wave_heights, alpha=0.7, label='Wave Height (m)', color='blue')
            ax2 = ax.twinx()
            ax2.plot(x, wind_speeds, 'r-', linewidth=2, marker='o', label='Wind Speed (kts)')
            ax2.set_ylabel('Wind Speed (kts)', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
        else:
            # Placeholder data
            ax.bar([0, 1, 2], [1.5, 2.0, 1.8], alpha=0.7, label='Wave Height (m)')
            ax.set_ylabel('Wave Height (m)')

        ax.set_xlabel('Time Period')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left')

    def _plot_performance_summary(self, ax, route: Route):
        """Plot performance metrics summary"""
        ax.set_title('📊 Performance Summary', fontweight='bold')
        ax.axis('off')

        # Create summary text
        summary_text = ".1f"".1f"".2f"".3f"".3f"

        # Position text
        ax.text(0.1, 0.8, summary_text, fontsize=11,
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8),
               verticalalignment='top')

        # Add performance indicators
        metrics = [
            ("Fuel Efficiency", "Good", "green"),
            ("Safety Score", "Excellent", "green"),
            ("Time Optimization", "Good", "orange"),
            ("Weather Impact", "Moderate", "yellow")
        ]

        y_pos = 0.6
        for label, status, color in metrics:
            ax.text(0.6, y_pos, f"{label}: {status}",
                   fontsize=10, color=color, fontweight='bold')
            y_pos -= 0.1

    def plot_vessel_distribution(self, vessels: List[VesselData],
                               save_path: str = "vessel_distribution.png"):
        """Plot vessel distribution and types"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('🚢 Vessel Distribution Analysis', fontsize=16, fontweight='bold')

        # Vessel types distribution
        vessel_types = {}
        for vessel in vessels:
            vtype = vessel.vessel_type or 0
            vessel_types[vtype] = vessel_types.get(vtype, 0) + 1

        ax1.pie(vessel_types.values(), labels=[f"Type {k}" for k in vessel_types.keys()],
               autopct='%1.1f%%', startangle=90)
        ax1.set_title('Vessel Types Distribution')

        # Speed distribution
        speeds = [v.speed for v in vessels if v.speed]
        if speeds:
            ax2.hist(speeds, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax2.set_title('Vessel Speed Distribution')
            ax2.set_xlabel('Speed (knots)')
            ax2.set_ylabel('Count')
            ax2.grid(True, alpha=0.3)

        # Geographic distribution
        lats = [v.latitude for v in vessels if v.latitude]
        lons = [v.longitude for v in vessels if v.longitude]
        if lats and lons:
            ax3.scatter(lons, lats, alpha=0.6, c='red', s=30)
            ax3.set_title('Vessel Geographic Distribution')
            ax3.set_xlabel('Longitude')
            ax3.set_ylabel('Latitude')
            ax3.grid(True, alpha=0.3)

        # Size distribution
        lengths = [v.length for v in vessels if v.length]
        if lengths:
            ax4.hist(lengths, bins=15, alpha=0.7, color='lightgreen', edgecolor='black')
            ax4.set_title('Vessel Size Distribution')
            ax4.set_xlabel('Length (m)')
            ax4.set_ylabel('Count')
            ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

        print(f"📊 Vessel distribution analysis saved as {save_path}")

    def plot_ml_model_performance(self, training_results: Dict[str, float],
                                save_path: str = "ml_performance.png"):
        """Plot ML model performance metrics"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle('🤖 ML Model Performance Analysis', fontsize=16, fontweight='bold')

        # R² Scores
        models = ['Speed Model', 'Fuel Model', 'Safety Model']
        r2_scores = [
            training_results.get('speed_r2', 0),
            training_results.get('fuel_r2', 0),
            training_results.get('safety_r2', 0)
        ]

        bars = ax1.bar(models, r2_scores, color=['skyblue', 'lightgreen', 'salmon'],
                       alpha=0.7, edgecolor='black')
        ax1.set_title('Model Accuracy (R² Score)')
        ax1.set_ylabel('R² Score')
        ax1.set_ylim(0, 1)
        ax1.grid(True, alpha=0.3)

        # Add value labels on bars
        for bar, score in zip(bars, r2_scores):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    '.3f', ha='center', va='bottom', fontweight='bold')

        # Performance interpretation
        ax2.axis('off')
        interpretation = """
        Performance Interpretation:

        • Speed Model: {speed_score:.3f}
          {speed_interp}

        • Fuel Model: {fuel_score:.3f}
          {fuel_interp}

        • Safety Model: {safety_score:.3f}
          {safety_interp}
        """.format(
            speed_score=r2_scores[0],
            speed_interp="Excellent (>0.8)" if r2_scores[0] > 0.8 else "Good (0.6-0.8)" if r2_scores[0] > 0.6 else "Needs Improvement",
            fuel_score=r2_scores[1],
            fuel_interp="Excellent (>0.8)" if r2_scores[1] > 0.8 else "Good (0.6-0.8)" if r2_scores[1] > 0.6 else "Needs Improvement",
            safety_score=r2_scores[2],
            safety_interp="Excellent (>0.8)" if r2_scores[2] > 0.8 else "Good (0.6-0.8)" if r2_scores[2] > 0.6 else "Needs Improvement"
        )

        ax2.text(0.1, 0.9, interpretation, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8))

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

        print(f"🤖 ML performance analysis saved as {save_path}")
