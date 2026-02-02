"""
Configuration file for the mapping project
Contains database and storage settings
Reads from Streamlit secrets when available, falls back to environment variables or defaults
"""

import os
from typing import Dict, Any

# Try to import streamlit for secrets access
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    st = None


def _get_secret(key_path: str, default: Any = None) -> Any:
    """
    Get value from Streamlit secrets, environment variable, or default.
    key_path: dot-separated path like 'database.digitalocean.user'
    """
    if HAS_STREAMLIT:
        try:
            # Navigate nested secrets using dot notation
            keys = key_path.split('.')
            value = st.secrets
            for key in keys:
                value = value[key]
            return value
        except (KeyError, AttributeError):
            pass
    
    # Fall back to environment variable
    env_key = key_path.upper().replace('.', '_')
    return os.getenv(env_key, default)


# Database configuration options
# Read from Streamlit secrets if available, otherwise use defaults
DATABASE_CONFIGS = {
    "digitalocean": {
        "dbname": _get_secret("database.digitalocean.dbname", "defaultdb"),
        "user": _get_secret("database.digitalocean.user", "doadmin"),
        "password": _get_secret("database.digitalocean.password", "AVNS_tOw1EdQTU-OwMnbMvNn"),
        "host": _get_secret("database.digitalocean.host", "db-postgresql-nyc3-47709-do-user-19616823-0.k.db.ondigitalocean.com"),
        "port": int(_get_secret("database.digitalocean.port", 25060)),
        "sslmode": _get_secret("database.digitalocean.sslmode", "require"),
        "connect_timeout": int(_get_secret("database.digitalocean.connect_timeout", 10)),
        "options": _get_secret("database.digitalocean.options", "-c statement_timeout=30000")
    },
}

# Active database configuration (change this to switch databases)
ACTIVE_DB = _get_secret("database.active_db", "digitalocean")
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
PROJECT_ID = _get_secret("gcp.project_id", "seventh-tempest-348517")

# FastAPI backend URL for tile serving
FASTAPI_URL = _get_secret("api.fastapi_url", "https://raster-image-3863265067.us-central1.run.app")

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


def get_gcp_service_account() -> Dict[str, Any]:
    """
    Get GCP service account credentials from Streamlit secrets.
    Returns a dictionary compatible with Google Cloud client libraries.
    Falls back to None if not available (for non-Streamlit contexts).
    """
    if not HAS_STREAMLIT:
        return None
    
    try:
        sa = st.secrets["gcp"]["service_account"]
        return {
            "type": sa.get("type", "service_account"),
            "project_id": sa.get("project_id", PROJECT_ID),
            "private_key_id": sa.get("private_key_id"),
            "private_key": sa.get("private_key"),
            "client_email": sa.get("client_email"),
            "client_id": sa.get("client_id"),
            "auth_uri": sa.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": sa.get("token_uri", "https://oauth2.googleapis.com/token"),
            "auth_provider_x509_cert_url": sa.get("auth_provider_x509_cert_url"),
            "client_x509_cert_url": sa.get("client_x509_cert_url"),
            "universe_domain": sa.get("universe_domain", "googleapis.com")
        }
    except (KeyError, AttributeError):
        return None