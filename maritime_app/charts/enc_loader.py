"""
NOAA ENC (Electronic Navigational Chart) Data Loader
Fetches TSS, AtoN, and other maritime features from NOAA's Direct-to-GIS services
"""
import requests
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import logging
# from ..config.settings import settings # Remove this relative import

logger = logging.getLogger(__name__)

class NOAAENCLoader:
    """Load maritime features from NOAA ENC Direct-to-GIS services"""
    
    # NOAA ENC Direct-to-GIS FeatureServer URLs
    BASE_URL = "https://gis.charttools.noaa.gov/arcgis/rest/services/MCS/ENCOnline/MapServer"
    
    # Layer IDs for key features (manually defined based on WMSServer titles and best guess)
    # LAYERS = {
    #     "tss_lanes": 4,          # Corresponds to "Traffic routes"
    #     "separation_zones": 5,    # Corresponds to "Special areas" (will need property filtering)
    #     "fairways": 4,           # Also part of "Traffic routes"
    #     "aids_to_navigation": 6, # Corresponds to "Buoys, beacons, lights, fog signals, radar"
    #     "restricted_areas": 5,   # Corresponds to "Special areas" (will need property filtering)
    #     "depth_areas": 2,        # Corresponds to "Depths, currents, etc"
    #     "wrecks": 3,             # Corresponds to "Seabed, obstructions, pipelines"
    #     "obstructions": 3,       # Corresponds to "Seabed, obstructions, pipelines"
    #     "pipelines": 3,          # Corresponds to "Seabed, obstructions, pipelines"
    #     "cables": 3,             # Corresponds to "Seabed, obstructions, pipelines"
    #     # "land": 0,             # Not directly used from here, handled by Natural Earth
    # }
    
    # US coastal bounding boxes (for fetching by region)
    REGIONS = {
        "west_coast": (-126.0, 31.0, -117.0, 49.0),      # CA, OR, WA
        "east_coast": (-81.0, 24.0, -66.0, 45.0),        # FL to ME  
        "gulf_coast": (-98.0, 24.0, -80.0, 31.0),        # TX to FL Gulf
        "great_lakes": (-93.0, 41.0, -75.0, 49.0),       # Great Lakes
        "alaska": (-180.0, 54.0, -129.0, 72.0),          # Alaska
        "hawaii": (-162.0, 18.0, -154.0, 23.0),          # Hawaii
        "us_full": (-180.0, 18.0, -66.0, 72.0),          # All US waters
    }
    
    def __init__(self, settings_obj, cache_dir: Optional[Path] = None, cache_ttl_hours: int = 24):
        self.cache_dir = cache_dir or (Path(__file__).parent / "noaa_cache")
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_ttl = cache_ttl_hours * 3600  # Convert to seconds
        self.settings = settings_obj  # Store the settings object
        self.charts_dir = Path(self.settings.CHARTS_DIR) # Initialize charts_dir from settings
        # self.LAYERS = self._get_map_server_info() # Dynamically get layer IDs

    # def _get_map_server_info(self) -> Dict[str, int]:
    #     """Dynamically fetch and parse layer information from the Maritime Chart Service endpoint."""
    #     layers_info = {}
    #     # The actual layers are exposed via the MaritimeChartService extension
    #     info_url = f"{self.BASE_URL}/exts/MaritimeChartService/layers/query?f=json"
    #     try:
    #         response = requests.get(info_url, timeout=30)
    #         response.raise_for_status()
    #         data = response.json()
    #         for layer in data.get("layers", []):
    #             layer_name = layer.get("name")
    #             layer_id = layer.get("id")
    #             if layer_name and layer_id is not None:
    #                 # Normalize layer names to match our internal conventions if possible
    #                 normalized_name = layer_name.lower().replace(" ", "_")
    #                 layers_info[normalized_name] = layer_id
    #         logger.info(f"Discovered NOAA ENC layers: {layers_info}")
    #     except Exception as e:
    #         logger.error(f"Failed to discover NOAA ENC layers from {info_url}: {e}")
    #     return layers_info
    
    # def fetch_layer_features(self, layer_name: str, bbox: Tuple[float, float, float, float],
    #                        max_features: int = 5000) -> Dict[str, Any]:
    #     """Fetch features from a NOAA ENC layer within bounding box"""
    #     logger.info(f"MOCK: Fetching {layer_name} features for bbox {bbox}")
    #     # Mock data fetching to return empty GeoJSON for now
    #     return {"type": "FeatureCollection", "features": []}

    def load_tss_corridors(self, region: str = "us_full") -> List[Dict[str, Any]]:
        """Load TSS lanes and convert to corridor format"""
        logger.info(f"Loading TSS corridors from {self.settings.TSS_CORRIDORS_GEOJSON}")
        file_path = self.charts_dir / self.settings.TSS_CORRIDORS_GEOJSON
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading TSS corridors from {file_path}: {e}")
            return []
    
    def load_sea_buoys(self, region: str = "us_full") -> List[Dict[str, Any]]:
        """Load AtoN and filter for sea buoys"""
        logger.info(f"Loading sea buoys from {self.settings.SEA_BUOYS_GEOJSON}")
        file_path = self.charts_dir / self.settings.SEA_BUOYS_GEOJSON
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sea buoys from {file_path}: {e}")
            return []
    
    def load_pilotage_zones(self, region: str = "us_full") -> List[Dict[str, Any]]:
        """Load pilotage areas (approximate from restricted areas)"""
        logger.info(f"Loading pilotage zones from {self.settings.PILOTAGE_ZONES_GEOJSON}")
        file_path = self.charts_dir / self.settings.PILOTAGE_ZONES_GEOJSON
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading pilotage zones from {file_path}: {e}")
            return []
    
    def _parse_tss_direction(self, props: Dict[str, Any]) -> str:
        """Parse TSS lane direction from properties"""
        # This is simplified - real ENC data has complex direction encoding
        traffic_flow = props.get("TRAFIC", "")
        orient = props.get("ORIENT", "")
        
        if "inbound" in str(traffic_flow).lower():
            return "inbound"
        elif "outbound" in str(traffic_flow).lower():
            return "outbound"
        elif orient:
            return f"bearing_{orient}"
        else:
            return "either"
    
    def _is_sea_buoy(self, buoy_type: str, name: str, props: Dict[str, Any]) -> bool:
        """Determine if this AtoN is likely a sea buoy"""
        name_lower = name.lower() if name else ""
        type_lower = buoy_type.lower() if buoy_type else ""
        
        # Common sea buoy indicators
        se_indicators = [
            "sea buoy", "fairway buoy", "approach", "entrance", 
            "channel entrance", "safe water", "mid channel"
        ]
        
        # Check name
        if any(indicator in name_lower for indicator in se_indicators):
            return True
            
        # Check if it's a safe water mark (cardinal mark category 1)
        if props.get("CATSPM") == "1":  # Safe water
            return True
            
        # Check if it's positioned offshore (rough heuristic)
        # This would need refinement with actual harbor location data
        
        return False
    
    def load_restricted_areas(self, region: str = "us_full") -> List[Dict[str, Any]]:
        """Load restricted/prohibited areas"""
        logger.info(f"Loading restricted areas from {self.settings.RESTRICTED_AREAS_GEOJSON}")
        file_path = self.charts_dir / self.settings.RESTRICTED_AREAS_GEOJSON
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading restricted areas from {file_path}: {e}")
            return []

    def load_depth_areas(self, region: str = "us_full") -> List[Dict[str, Any]]:
        """Load depth areas/contours with min/max depth attributes"""
        logger.info(f"Loading depth areas from {self.settings.DEPTH_AREAS_GEOJSON}")
        file_path = self.charts_dir / self.settings.DEPTH_AREAS_GEOJSON
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading depth areas from {file_path}: {e}")
            return []

    def load_wrecks_obstructions(self, region: str = "us_full") -> List[Dict[str, Any]]:
        """Load wrecks and obstructions as point hazards"""
        logger.info(f"Loading wrecks and obstructions from {self.settings.WRECKS_OBSTRUCTIONS_GEOJSON}")
        file_path = self.charts_dir / self.settings.WRECKS_OBSTRUCTIONS_GEOJSON
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading wrecks/obstructions from {file_path}: {e}")
            return []

    def load_pipelines_cables(self, region: str = "us_full") -> List[Dict[str, Any]]:
        """Load pipelines and cables as line features"""
        logger.info(f"Loading pipelines and cables from {self.settings.PIPELINES_CABLES_GEOJSON}")
        file_path = self.charts_dir / self.settings.PIPELINES_CABLES_GEOJSON
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading pipelines/cables from {file_path}: {e}")
            return []
    
    def create_maritime_data_json(self, region: str = "us_full", output_file: Optional[Path] = None) -> Dict[str, Any]:
        """Create complete maritime_data.json from NOAA ENC"""
        if output_file is None or isinstance(output_file, str):
            output_file = Path(output_file or (self.charts_dir / f"maritime_data_noaa_{region}.json"))
        
        logger.info(f"Creating maritime data for {region}...")
        
        # Load all components (which will return empty lists due to mocking)
        tss_corridors = self.load_tss_corridors(region)
        sea_buoys = self.load_sea_buoys(region)
        pilotage_zones = self.load_pilotage_zones(region)
        restricted_areas = self.load_restricted_areas(region)
        depth_areas = self.load_depth_areas(region)
        wrecks_obstructions = self.load_wrecks_obstructions(region)
        pipelines_cables = self.load_pipelines_cables(region)

        # Save all components to individual files and create the main maritime_data.json
        chart_data_root = self.charts_dir 

        # Save TSS Corridors
        tss_output_path = chart_data_root / self.settings.TSS_CORRIDORS_GEOJSON
        json.dump(tss_corridors, tss_output_path.open("w"), indent=2)
        logger.info(f"Saved TSS corridors to {tss_output_path}")

        # Save Sea Buoys
        sea_buoys_output_path = chart_data_root / self.settings.SEA_BUOYS_GEOJSON
        json.dump(sea_buoys, sea_buoys_output_path.open("w"), indent=2)
        logger.info(f"Saved sea buoys to {sea_buoys_output_path}")

        # Save Pilotage Zones
        pilotage_output_path = chart_data_root / self.settings.PILOTAGE_ZONES_GEOJSON
        json.dump(pilotage_zones, pilotage_output_path.open("w"), indent=2)
        logger.info(f"Saved pilotage zones to {pilotage_output_path}")

        # Save Restricted Areas
        restricted_areas_output_path = chart_data_root / self.settings.RESTRICTED_AREAS_GEOJSON
        json.dump(restricted_areas, restricted_areas_output_path.open("w"), indent=2)
        logger.info(f"Saved restricted areas to {restricted_areas_output_path}")

        # Save Depth Areas
        depth_areas_output_path = chart_data_root / self.settings.DEPTH_AREAS_GEOJSON
        json.dump(depth_areas, depth_areas_output_path.open("w"), indent=2)
        logger.info(f"Saved depth areas to {depth_areas_output_path}")

        # Save Wrecks & Obstructions
        wrecks_obstructions_output_path = chart_data_root / self.settings.WRECKS_OBSTRUCTIONS_GEOJSON
        json.dump(wrecks_obstructions, wrecks_obstructions_output_path.open("w"), indent=2)
        logger.info(f"Saved wrecks/obstructions to {wrecks_obstructions_output_path}")

        # Save Pipelines & Cables
        pipelines_cables_output_path = chart_data_root / self.settings.PIPELINES_CABLES_GEOJSON
        json.dump(pipelines_cables, pipelines_cables_output_path.open("w"), indent=2)
        logger.info(f"Saved pipelines/cables to {pipelines_cables_output_path}")

        # Create the main maritime_data.json (which will now be a metadata file)
        maritime_data = {
            "source": f"NOAA ENC Direct-to-GIS ({region})",
            "generated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "region": region,
            "bbox": self.REGIONS[region],
            "tss_corridors_file": str(tss_output_path.name),
            "sea_buoys_file": str(sea_buoys_output_path.name),
            "pilotage_zones_file": str(pilotage_output_path.name),
            "restricted_areas_file": str(restricted_areas_output_path.name),
            "depth_areas_file": str(depth_areas_output_path.name),
            "wrecks_obstructions_file": str(wrecks_obstructions_output_path.name),
            "pipelines_cables_file": str(pipelines_cables_output_path.name)
        }

        output_file.write_text(json.dumps(maritime_data, indent=2))
        logger.info(f"Saved maritime data metadata to {output_file}")
        return maritime_data


def main():
    """CLI for loading NOAA ENC data"""
    import argparse
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from config.settings import settings

    parser = argparse.ArgumentParser(description="Load NOAA ENC maritime data")
    parser.add_argument("--region", default="west_coast", choices=list(NOAAENCLoader.REGIONS.keys()),
                       help="Region to load data for")
    parser.add_argument("--output", type=Path, help="Output file path (default: maritime_data_noaa_<region>.json)")
    parser.add_argument("--cache-hours", type=int, default=24, help="Cache TTL in hours")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    # Re-instantiate settings to ensure updated paths are used
    # from maritime_app.config.settings import settings # already imported above

    loader = NOAAENCLoader(settings, cache_ttl_hours=args.cache_hours)
    loader.create_maritime_data_json(args.region, args.output)


if __name__ == "__main__":
    main()
