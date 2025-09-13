"""
Machine Learning Data Processing Module
Handles ML model training and prediction for maritime route optimization
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error
import matplotlib.pyplot as plt
import warnings
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from ...config.settings import settings
from ...core.models import RouteConstraints, WeatherData, VesselData
from ...utils.database import DatabaseManager


warnings.filterwarnings('ignore')


class MaritimeMLDataProcessor:
    """Handles ML model training and prediction for maritime optimization"""

    def __init__(self):
        self.speed_model = None
        self.fuel_model = None
        self.safety_model = None
        self.scaler = StandardScaler()
        self.models_trained = False
        self.db = DatabaseManager()

    def generate_synthetic_data(self, num_samples: int = 120) -> pd.DataFrame:
        """Generate synthetic maritime training data"""
        np.random.seed(settings.RANDOM_STATE)

        # Generate synthetic vessel and environmental data
        data = {
            'vessel_speed_knots': np.random.uniform(5, 25, num_samples),
            'wave_height_m': np.random.uniform(0.5, 6.0, num_samples),
            'wind_speed_kts': np.random.uniform(5, 40, num_samples),
            'wind_direction_deg': np.random.uniform(0, 360, num_samples),
            'current_speed_knots': np.random.uniform(0, 3, num_samples),
            'current_direction_deg': np.random.uniform(0, 360, num_samples),
            'temperature_c': np.random.uniform(5, 30, num_samples),
            'vessel_draft_m': np.random.uniform(3, 15, num_samples),
            'distance_to_coast_nm': np.random.uniform(1, 50, num_samples),
            'time_of_day': np.random.uniform(0, 24, num_samples),
            'season': np.random.randint(1, 5, num_samples),  # 1-4 for seasons
        }

        df = pd.DataFrame(data)

        # Calculate target variables (what we're trying to predict)
        df['optimal_speed_knots'] = self._calculate_optimal_speed(df)
        df['fuel_efficiency_score'] = self._calculate_fuel_efficiency(df)
        df['safety_score'] = self._calculate_safety_score(df)

        return df

    def _calculate_optimal_speed(self, df: pd.DataFrame) -> np.ndarray:
        """Calculate optimal speed based on conditions"""
        base_speed = 15.0

        # Adjust for wave conditions
        wave_penalty = df['wave_height_m'] * 0.5
        wave_penalty = np.clip(wave_penalty, 0, 5)

        # Adjust for wind conditions
        wind_factor = np.where(df['wind_speed_kts'] > 25, 0.8, 1.0)

        # Adjust for current
        current_factor = 1 + (df['current_speed_knots'] * 0.1)

        optimal_speed = base_speed - wave_penalty
        optimal_speed *= wind_factor
        optimal_speed *= current_factor

        return np.clip(optimal_speed, 5, 22)

    def _calculate_fuel_efficiency(self, df: pd.DataFrame) -> np.ndarray:
        """Calculate fuel efficiency score"""
        # Fuel efficiency decreases with speed and adverse conditions
        speed_efficiency = 1 - (df['vessel_speed_knots'] - 12) / 20
        wave_efficiency = 1 - df['wave_height_m'] / 10
        wind_efficiency = 1 - np.abs(df['wind_speed_kts'] - 15) / 40

        efficiency = (speed_efficiency + wave_efficiency + wind_efficiency) / 3
        return np.clip(efficiency, 0, 1)

    def _calculate_safety_score(self, df: pd.DataFrame) -> np.ndarray:
        """Calculate safety score based on conditions"""
        # Safety decreases with high waves and winds
        wave_safety = 1 - df['wave_height_m'] / 8
        wind_safety = 1 - df['wind_speed_kts'] / 50
        draft_safety = 1 - df['vessel_draft_m'] / 20
        coast_safety = df['distance_to_coast_nm'] / 50

        safety = (wave_safety + wind_safety + draft_safety + coast_safety) / 4
        return np.clip(safety, 0, 1)

    def prepare_training_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Prepare data for ML training"""
        # Feature columns
        feature_cols = [
            'vessel_speed_knots', 'wave_height_m', 'wind_speed_kts',
            'wind_direction_deg', 'current_speed_knots', 'current_direction_deg',
            'temperature_c', 'vessel_draft_m', 'distance_to_coast_nm',
            'time_of_day', 'season'
        ]

        X = df[feature_cols].values

        # Target variables
        y_targets = {
            'speed': df['optimal_speed_knots'].values,
            'fuel': df['fuel_efficiency_score'].values,
            'safety': df['safety_score'].values
        }

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        return X_scaled, y_targets

    def train_models(self, X: np.ndarray, y_targets: Dict[str, np.ndarray]) -> Dict[str, float]:
        """Train ML models for speed, fuel, and safety prediction"""
        print("🤖 Training ML models for maritime optimization...")

        results = {}

        # Train speed optimization model
        print("Training speed optimization model...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_targets['speed'], test_size=settings.TEST_SIZE, random_state=settings.RANDOM_STATE
        )
        self.speed_model = RandomForestRegressor(n_estimators=100, random_state=settings.RANDOM_STATE)
        self.speed_model.fit(X_train, y_train)

        speed_pred = self.speed_model.predict(X_test)
        speed_r2 = r2_score(y_test, speed_pred)
        results['speed_r2'] = speed_r2
        print(f"   Speed Model R²: {speed_r2:.4f}")

        # Train fuel efficiency model
        print("Training fuel efficiency model...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_targets['fuel'], test_size=settings.TEST_SIZE, random_state=settings.RANDOM_STATE
        )
        self.fuel_model = RandomForestRegressor(n_estimators=100, random_state=settings.RANDOM_STATE)
        self.fuel_model.fit(X_train, y_train)

        fuel_pred = self.fuel_model.predict(X_test)
        fuel_r2 = r2_score(y_test, fuel_pred)
        results['fuel_r2'] = fuel_r2
        print(f"   Fuel Model R²: {fuel_r2:.4f}")

        # Train safety assessment model
        print("Training safety assessment model...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_targets['safety'], test_size=settings.TEST_SIZE, random_state=settings.RANDOM_STATE
        )
        self.safety_model = RandomForestRegressor(n_estimators=100, random_state=settings.RANDOM_STATE)
        self.safety_model.fit(X_train, y_train)

        safety_pred = self.safety_model.predict(X_test)
        safety_r2 = r2_score(y_test, safety_pred)
        results['safety_r2'] = safety_r2
        print(f"   Safety Model R²: {safety_r2:.4f}")

        self.models_trained = True
        print("✅ All ML models trained successfully!")
        return results

    def predict_optimization(self, vessel_data: VesselData,
                           weather_data: List[WeatherData]) -> Dict[str, Any]:
        """Predict optimal speed, fuel efficiency, and safety for given conditions"""
        if not self.models_trained:
            raise ValueError("Models not trained yet. Call train_models() first.")

        # Prepare input features
        features = self._prepare_prediction_features(vessel_data, weather_data)
        features_scaled = self.scaler.transform([features])

        # Make predictions
        optimal_speed = self.speed_model.predict(features_scaled)[0]
        fuel_efficiency = self.fuel_model.predict(features_scaled)[0]
        safety_score = self.safety_model.predict(features_scaled)[0]

        return {
            'optimal_speed_knots': round(optimal_speed, 2),
            'fuel_efficiency_score': round(fuel_efficiency, 3),
            'safety_score': round(safety_score, 3),
            'confidence_level': self._calculate_confidence(features_scaled)
        }

    def _prepare_prediction_features(self, vessel: VesselData,
                                   weather_list: List[WeatherData]) -> List[float]:
        """Prepare features for ML prediction"""
        # Use the most recent weather data
        weather = weather_list[0] if weather_list else WeatherData(0, 0)

        return [
            vessel.speed or 12.0,  # Default speed
            weather.wave_height_m or 1.5,
            weather.wind_speed_kts or 15.0,
            weather.wind_direction_deg or 180.0,
            weather.ocean_current_speed_kts or 0.5,
            weather.ocean_current_direction_deg or 90.0,
            weather.temperature_c or 20.0,
            vessel.draft or 8.0,
            10.0,  # Default distance to coast
            datetime.now().hour,  # Current hour
            ((datetime.now().month - 1) // 3) + 1  # Current season
        ]

    def _calculate_confidence(self, features_scaled: np.ndarray) -> float:
        """Calculate prediction confidence based on feature values"""
        # Simple confidence calculation based on feature ranges
        confidence = 0.8  # Base confidence

        # Reduce confidence for extreme conditions
        if features_scaled[0][1] > 4:  # High waves
            confidence -= 0.1
        if features_scaled[0][2] > 30:  # High winds
            confidence -= 0.1

        return max(0.5, confidence)

    def save_models(self, path: str = None):
        """Save trained models to disk"""
        import joblib
        import os

        if path is None:
            path = settings.ML_MODEL_PATH

        if not self.models_trained:
            raise ValueError("No trained models to save")

        os.makedirs(path, exist_ok=True)

        joblib.dump(self.speed_model, f"{path}/speed_model.pkl")
        joblib.dump(self.fuel_model, f"{path}/fuel_model.pkl")
        joblib.dump(self.safety_model, f"{path}/safety_model.pkl")
        joblib.dump(self.scaler, f"{path}/scaler.pkl")

        print(f"✅ Models saved to {path}")

    def load_models(self, path: str = None):
        """Load trained models from disk"""
        import joblib

        if path is None:
            path = settings.ML_MODEL_PATH

        try:
            self.speed_model = joblib.load(f"{path}/speed_model.pkl")
            self.fuel_model = joblib.load(f"{path}/fuel_model.pkl")
            self.safety_model = joblib.load(f"{path}/safety_model.pkl")
            self.scaler = joblib.load(f"{path}/scaler.pkl")
            self.models_trained = True
            print(f"✅ Models loaded from {path}")
        except FileNotFoundError:
            print(f"❌ Models not found at {path}")
