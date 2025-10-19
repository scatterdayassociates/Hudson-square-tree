"""
Configuration file for the mapping project
Contains database and storage settings
"""

import os
from typing import Dict, Any

# Database configuration options
DATABASE_CONFIGS = {
    "digitalocean": {
        "dbname": "defaultdb",
        "user": "doadmin", 
        "password": "AVNS_tOw1EdQTU-OwMnbMvNn",
        "host": "db-postgresql-nyc3-47709-do-user-19616823-0.k.db.ondigitalocean.com",
        "port": 25060,
        "sslmode": "require"
    },

}

# Active database configuration (change this to switch databases)
ACTIVE_DB = "digitalocean"  # Options: "digitalocean", "local_postgres"
DATABASE_CONFIG = DATABASE_CONFIGS[ACTIVE_DB]

# GCP Storage URLs for LiDAR datasets
LIDAR_DATASETS = {
    "2010": "https://storage.googleapis.com/raster_datam/landcover_2010_nyc_05ft_cog.tif",
    "2017": "https://storage.googleapis.com/raster_datam/NYC_2017_LiDAR_LandCover_cog.tif"
}

# Hudson Square study area bounds - 6-point polygon
HUDSON_SQUARE_BOUNDS = {
    'type': 'polygon',
    'coordinates': [
        [-74.008700, 40.718700],  # Point 1: Canal & West (SW)
        [-73.997000, 40.718700],  # Point 2: Canal & 6th Ave (SE)
        [-73.997000, 40.726200],  # Point 3: Vandam & 6th Ave
        [-74.003900, 40.726200],  # Point 4: Vandam & Varick
        [-74.005800, 40.735800],  # Point 5: Clarkson & Varick (NE)
        [-74.008700, 40.735800]   # Point 6: Clarkson & West (NW)
    ]
}

# Google Earth Engine project ID
PROJECT_ID = 'seventh-tempest-348517'

# Map configuration
MAP_CONFIG = {
    "center": [40.726900,-74.003517],
    "zoom": 16,
    "min_zoom": 12,
    "max_zoom": 18,
    "height": 600
}

# Raster processing configuration
RASTER_CONFIG = {
    "tile_size": 512,
    "overview_levels": [2, 4, 8, 16],
    "compression": "lzw",
    "nodata": 0
}

def get_database_url() -> str:
    """Generate database connection URL"""
    config = DATABASE_CONFIG
    return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['dbname']}?sslmode={config['sslmode']}"

def get_lidar_url(year: int) -> str:
    """Get LiDAR dataset URL for given year"""
    return LIDAR_DATASETS.get(str(year), "")

def get_study_area_bounds() -> Dict[str, float]:
    """Get Hudson Square study area bounds"""
    if HUDSON_SQUARE_BOUNDS.get('type') == 'polygon':
        coords = HUDSON_SQUARE_BOUNDS['coordinates']
        return {
            'west': min(coord[0] for coord in coords),
            'east': max(coord[0] for coord in coords),
            'north': max(coord[1] for coord in coords),
            'south': min(coord[1] for coord in coords)
        }
    else:
        return HUDSON_SQUARE_BOUNDS.copy()
