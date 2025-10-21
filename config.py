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
        "sslmode": "require",
        "connect_timeout": 10,  # Connection timeout in seconds
        "options": "-c statement_timeout=30000"  # Query timeout: 30 seconds
    },

}

# Active database configuration (change this to switch databases)
ACTIVE_DB = "digitalocean"  # Options: "digitalocean", "local_postgres"
DATABASE_CONFIG = DATABASE_CONFIGS[ACTIVE_DB]

# GCP Storage URLs for LiDAR datasets
LIDAR_DATASETS = {
    "2010": "https://storage.googleapis.com/raster_datam/landcover_2010_nyc_05ft_cog.tif",
    "2021": "https://storage.googleapis.com/raster_datam/landcover_nyc_2021_6in_cog.tif"
}

# Hudson Square study area bounds - 8-point polygon
HUDSON_SQUARE_BOUNDS = {
    'type': 'polygon',
    'coordinates': [ 
        [-74.01052092337208,40.72982892345051],  # Point 1: Canal & West (SW)
        [-74.00472530882296, 40.729355986854266],  # Point 2: Canal & 6th Ave (SE)
        [-74.00478302321119, 40.72905955348878],  # Point 3: Vandam & 6th Ave
        [-74.00453720266869, 40.72905307405622],  # Point 4: Vandam & Varick
        [-74.00454789051835,40.72863352945419],  # Point 5: Clarkson & Varick (NE)
        [-74.00286231971523,40.72833519406047],   # Point 6: Clarkson & West (NW)
        [-74.00540521626658,40.72193973323825],   # Point 7: 
        [-74.01094328685865,40.72583000053755]   # Point 8
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
