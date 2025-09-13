"""
AIS Data Collection Module
Handles real-time AIS vessel data collection from WebSocket streams
"""
import websocket
import json
import threading
import queue
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from ...config.settings import settings
from ...core.models import VesselData


class AISDataCollector:
    """Handles AIS data collection from WebSocket stream"""

    def __init__(self, api_key: str = settings.AISSTREAM_API_KEY,
                 bounds: Dict[str, float] = settings.AIS_BOUNDS):
        self.api_key = api_key
        self.bounds = bounds
        self.vessels = []
        self.ws = None
        self.running = False
        self.data_queue = queue.Queue()
        self.collection_thread = None

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            if data.get('msg_type') == 'positions':
                vessels = data.get('positions', [])
                for vessel_data in vessels:
                    processed_vessel = self._process_vessel_data(vessel_data)
                    if processed_vessel:
                        self.data_queue.put(processed_vessel)
        except json.JSONDecodeError as e:
            print(f"Error parsing AIS message: {e}")
        except Exception as e:
            print(f"Error processing AIS message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"AIS WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        print(f"AIS WebSocket connection closed: {close_status_code} - {close_msg}")
        self.running = False

    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        print("AIS WebSocket connection opened")
        # Send subscription message
        subscription = {
            "msg_type": "subscribe",
            "api_key": self.api_key,
            "bounding_box": self.bounds
        }
        ws.send(json.dumps(subscription))
        print("AIS subscription sent")

    def _process_vessel_data(self, vessel_data: Dict[str, Any]) -> Optional[VesselData]:
        """Process raw AIS data into VesselData object"""
        try:
            # Filter out vessels without position data
            if not all(k in vessel_data for k in ['lat', 'lon']):
                return None

            # Create VesselData object
            vessel = VesselData(
                mmsi=vessel_data.get('mmsi'),
                name=vessel_data.get('name'),
                vessel_type=vessel_data.get('type'),
                length=vessel_data.get('length'),
                width=vessel_data.get('width'),
                draft=vessel_data.get('draught'),
                latitude=vessel_data.get('lat'),
                longitude=vessel_data.get('lon'),
                speed=vessel_data.get('speed'),
                course=vessel_data.get('course'),
                heading=vessel_data.get('heading'),
                timestamp=datetime.fromtimestamp(vessel_data.get('timestamp', time.time()))
            )

            return vessel
        except Exception as e:
            print(f"Error processing vessel data: {e}")
            return None

    def start_collection(self, duration_seconds: int = 30) -> List[VesselData]:
        """Start AIS data collection for specified duration"""
        print(f"Starting AIS data collection for {duration_seconds} seconds...")

        # WebSocket URL for aisstream.io
        ws_url = f"wss://stream.aisstream.io/v0/stream"

        # Create WebSocket connection
        websocket.enableTrace(False)  # Disable debug output
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )

        self.running = True
        collected_vessels = []

        def run_ws():
            """Run WebSocket in separate thread"""
            self.ws.run_forever()

        # Start WebSocket in background thread
        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()

        # Collect data for specified duration
        start_time = time.time()
        while time.time() - start_time < duration_seconds and self.running:
            try:
                # Non-blocking queue get with timeout
                vessel = self.data_queue.get(timeout=1.0)
                collected_vessels.append(vessel)
                print(f"Collected vessel: {vessel.name or 'Unknown'} (MMSI: {vessel.mmsi})")
            except queue.Empty:
                continue

        # Stop collection
        self.stop_collection()
        print(f"AIS collection complete. Collected {len(collected_vessels)} vessels.")

        return collected_vessels

    def stop_collection(self):
        """Stop AIS data collection"""
        self.running = False
        if self.ws:
            self.ws.close()

    def get_vessel_count(self) -> int:
        """Get count of collected vessels"""
        return len(self.vessels)

    def get_vessels_in_bounds(self, bounds: Dict[str, float]) -> List[VesselData]:
        """Get vessels within specified bounds"""
        filtered_vessels = []
        for vessel in self.vessels:
            if (bounds['south'] <= vessel.latitude <= bounds['north'] and
                bounds['west'] <= vessel.longitude <= bounds['east']):
                filtered_vessels.append(vessel)
        return filtered_vessels
