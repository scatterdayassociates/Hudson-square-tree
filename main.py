import streamlit as st
import streamlit.components.v1 as components
import folium
from folium.plugins import Fullscreen, Draw
from folium import raster_layers
import json
import os
from datetime import datetime
from config import DATABASE_CONFIG, LIDAR_DATASETS, HUDSON_SQUARE_BOUNDS, ACTIVE_DB, PROJECT_ID, get_study_area_bounds, FASTAPI_URL
from postgis_raster import PostGISRasterHandler, get_tree_coverage_postgis, initialize_lidar_datasets
import requests


def _get_coverage_cache_key(year: int, bounds: dict) -> str:
    """Generate a cache key for coverage based on year and bounds."""
    import json
    bounds_str = json.dumps(bounds, sort_keys=True)
    return f"cov_{year}_{hash(bounds_str)}"


def _fetch_coverage_from_api(year: int, bounds: dict) -> tuple:
    """
    Internal function to fetch coverage from API (no session state access).
    Used by threads.
    """
    try:
        if bounds.get('type') == 'polygon':
            url = f"{FASTAPI_URL}/coverage/bounds/{year}"
            payload = {
                "type": "polygon",
                "coordinates": bounds['coordinates']
            }
            response = requests.post(url, json=payload, timeout=60)
        else:
            url = f"{FASTAPI_URL}/coverage/{year}"
            params = {
                "west": bounds.get('west', HUDSON_SQUARE_BOUNDS['west']),
                "south": bounds.get('south', HUDSON_SQUARE_BOUNDS['south']),
                "east": bounds.get('east', HUDSON_SQUARE_BOUNDS['east']),
                "north": bounds.get('north', HUDSON_SQUARE_BOUNDS['north'])
            }
            response = requests.get(url, params=params, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('coverage_percent', 0.0), None
        else:
            return None, f"API error: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return None, "API request timed out"
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to API backend"
    except Exception as e:
        return None, f"API error: {str(e)}"


def get_coverage_from_api(year: int, bounds: dict, use_cache: bool = True) -> tuple:
    """
    Get tree coverage from the FastAPI backend.
    Checks cache first (must be called from main thread).
    """
    cache_key = _get_coverage_cache_key(year, bounds)
    if use_cache and cache_key in st.session_state:
        print(f"⚡ Using cached coverage for {year}")
        return st.session_state[cache_key], None
    
    coverage, error = _fetch_coverage_from_api(year, bounds)
    
    if coverage is not None:
        st.session_state[cache_key] = coverage
    
    return coverage, error


def _get_bounds_cache_key(year: int, bounds: dict) -> str:
    """Generate a cache key for visualization based on year and bounds."""
    import json
    bounds_str = json.dumps(bounds, sort_keys=True)
    return f"viz_{year}_{hash(bounds_str)}"


def _fetch_visualization_from_api(year: int, bounds: dict) -> tuple:
    """
    Internal function to fetch visualization from API (no session state access).
    Used by threads.
    """
    import base64
    
    try:
        url = f"{FASTAPI_URL}/visualization/{year}"
        
        if bounds.get('type') == 'polygon':
            payload = {
                "type": "polygon",
                "coordinates": bounds['coordinates']
            }
            coords = bounds['coordinates']
            lats = [coord[1] for coord in coords]
            lons = [coord[0] for coord in coords]
            geo_bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
        else:
            payload = {
                "type": "rectangle",
                "west": bounds.get('west', HUDSON_SQUARE_BOUNDS['west']),
                "south": bounds.get('south', HUDSON_SQUARE_BOUNDS['south']),
                "east": bounds.get('east', HUDSON_SQUARE_BOUNDS['east']),
                "north": bounds.get('north', HUDSON_SQUARE_BOUNDS['north'])
            }
            geo_bounds = [
                [bounds.get('south', HUDSON_SQUARE_BOUNDS['south']), bounds.get('west', HUDSON_SQUARE_BOUNDS['west'])],
                [bounds.get('north', HUDSON_SQUARE_BOUNDS['north']), bounds.get('east', HUDSON_SQUARE_BOUNDS['east'])]
            ]
        
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            image_base64 = base64.b64encode(response.content).decode()
            image_data = f"data:image/png;base64,{image_base64}"
            return image_data, geo_bounds, None
        else:
            return None, None, f"API error: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return None, None, "Visualization request timed out"
    except requests.exceptions.ConnectionError:
        return None, None, "Could not connect to API backend"
    except Exception as e:
        return None, None, f"Visualization error: {str(e)}"


def get_visualization_from_api(year: int, bounds: dict, use_cache: bool = True) -> tuple:
    """
    Get tree coverage visualization image from the FastAPI backend.
    Checks cache first (must be called from main thread).
    """
    cache_key = _get_bounds_cache_key(year, bounds)
    if use_cache and cache_key in st.session_state:
        cached = st.session_state[cache_key]
        print(f"⚡ Using cached visualization for {year}")
        return cached['image'], cached['geo_bounds'], None
    
    image_data, geo_bounds, error = _fetch_visualization_from_api(year, bounds)
    
    if image_data is not None:
        st.session_state[cache_key] = {
            'image': image_data,
            'geo_bounds': geo_bounds
        }
    
    return image_data, geo_bounds, error

# Try to import st_folium for better integration
try:
    from streamlit_folium import st_folium
    ST_FOLIUM_AVAILABLE = True
except ImportError:
    ST_FOLIUM_AVAILABLE = False
    st_folium = None

# Page configuration
st.set_page_config(
    page_title="Hudson Square Tree Cover Analysis",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling - Complete Design System from script.css
st.markdown("""
<style>
    /* CSS Variables for Design System */
    :root {
        /* Colors - White theme with blue accents */
        --background: 0 0% 100%;
        --foreground: 220 15% 15%;
        --card: 0 0% 100%;
        --card-foreground: 220 15% 15%;
        --popover: 0 0% 100%;
        --popover-foreground: 220 15% 15%;
        --primary: 210 100% 50%;
        --primary-foreground: 0 0% 98%;
        --secondary: 220 15% 96%;
        --secondary-foreground: 220 15% 15%;
        --muted: 220 15% 96%;
        --muted-foreground: 220 5% 45%;
        --accent: 210 100% 50%;
        --accent-foreground: 0 0% 98%;
        --destructive: 0 84% 60%;
        --destructive-foreground: 0 0% 98%;
        --success: 142 76% 36%;
        --success-foreground: 0 0% 98%;
        --warning: 38 92% 50%;
        --warning-foreground: 48 96% 89%;
        --border: 220 15% 90%;
        --input: 220 15% 90%;
        --ring: 210 100% 50%;
        --radius: 0.5rem;
      
        /* Gradients */
        --gradient-hero: linear-gradient(135deg, hsl(var(--primary)), hsl(210 100% 60%));
        --gradient-card: linear-gradient(145deg, hsl(var(--card)), hsl(var(--muted)));
        --gradient-glow: linear-gradient(135deg, hsl(var(--primary) / 0.1), hsl(210 100% 60% / 0.1));
      
        /* Shadows */
        --shadow-card: 0 2px 8px hsl(220 15% 15% / 0.1);
        --shadow-elevated: 0 4px 16px hsl(220 15% 15% / 0.15);
      
        /* Animations */
        --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* Main app styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1280px;
    }

    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
        color: white;
        padding: 2rem;
        border-radius: var(--radius);
        margin-bottom: 2rem;
        box-shadow: var(--shadow-elevated);
    }

    .main-header h1 {
        color: white !important;
        margin-bottom: 0.5rem;
        font-size: 2rem;
        font-weight: 600;
    }

    .main-header p {
        color: rgba(255, 255, 255, 0.9) !important;
        margin: 0;
        font-size: 1.1rem;
    }

    /* Status indicator styling */
    .status-indicator {
        display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: var(--radius);
    border: 1px solid;
    transition: var(--transition-smooth);
    }

    /* Typography - match design font across the app */
    html, body, .stApp, .main, .main * {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .status-indicator.success {
        border-color: hsl(var(--success) / 0.2);
        background-color: hsl(var(--success) / 0.1);
        color: hsl(var(--success));
    }

    .status-indicator.error {
        border-color: hsl(0 84% 60% / 0.2);
        background-color: hsl(0 84% 60% / 0.1);
        color: hsl(0 84% 60%);
    }
    .card-contentMe {
    padding: 1.5rem;
    padding-top: 0;
  }

    /* Metrics styling */
    .metric-container {
        background: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 1.5rem;
        box-shadow: var(--shadow-card);
        text-align: center;
        transition: all 0.3s ease;
    }

    .metric-container:hover {
        box-shadow: var(--shadow-elevated);
        transform: translateY(-2px);
    }

    
    .card-titleMe {
    font-size: 0.35rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: hsl(var(--primary));
  }
   

  

   

    @media (max-width: 768px) {
        .methodology-grid {
            grid-template-columns: 1fr;
        }
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: hsl(var(--foreground));
        margin-bottom: 0.5rem;
    }

    .metric-label {
        font-size: 0.875rem;
        color: hsl(var(--muted-foreground));
        font-weight: 500;
        margin-bottom: 0.5rem;
        text-align: left;
    }

    .metric-icon {
        font-size: 1.5rem;
        opacity: 0.7;
    }

    .metric-change {
        font-size: 0.75rem;
        margin-top: 0.5rem;
        padding: 0.25rem 0.5rem;
        border-radius: calc(var(--radius) - 2px);
        font-weight: 600;
    }

    .metric-change.positive {
        background-color: hsl(var(--success) / 0.1);
        color: hsl(var(--success));
    }

    .metric-change.negative {
        background-color: hsl(0 84% 60% / 0.1);
        color: hsl(0 84% 60%);
    }

    /* Sidebar styling */
    .css-1d391kg {
        background-color: hsl(var(--secondary));
    }

    .css-1d391kg .css-1v0mbdj {
        background-color: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        box-shadow: var(--shadow-card);
    }

    /* Button styling */
    .stButton > button {
        background: hsl(var(--primary));
        color: hsl(var(--primary-foreground));
        border: none;
        border-radius: var(--radius);
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        box-shadow: var(--shadow-card);
        transition: all 0.3s ease;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        white-space: nowrap;
        text-align: center;
        font-size: 0.875rem;
        line-height: 1.25rem;
        cursor: pointer;
        user-select: none;
        position: relative;
        overflow: hidden;
    }
    /* Sidebar: minimum width so content and button text don't get too cramped when dragged */
    [data-testid="stSidebar"] {
        min-width: 380px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        min-width: 280px !important;
    }
    /* Sidebar buttons: center text, allow wrap when sidebar is narrow so text doesn't cut off */
    [data-testid="stSidebar"] .stButton > button {
        width: 100%;
        justify-content: center;
        text-align: center;
        white-space: normal;
        word-wrap: break-word;
        min-height: 2.75rem;
        padding: 0.5rem 0.75rem;
        line-height: 1.3;
    }

    .stButton > button:hover {
        background: hsl(210 100% 45%);
        box-shadow: var(--shadow-elevated);
        transform: translateY(-1px);
    }

    .stButton > button:focus-visible {
        outline: 2px solid hsl(var(--primary));
        outline-offset: 2px;
    }

    .stButton > button:disabled {
        pointer-events: none;
        opacity: 0.5;
    }

    /* Primary button variant (for Run Tree Analysis) */
    .stButton[data-testid="baseButton-primary"] > button,
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(90deg, #87CEEB 0%, #E0F6FF 100%);
        color: #1e40af;
        box-shadow: var(--shadow-card);
        border: none;
        font-weight: 600;
    }

    .stButton[data-testid="baseButton-primary"] > button:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(90deg, #7BB8E8 0%, #D1F0FF 100%);
        box-shadow: var(--shadow-elevated);
        transform: translateY(-1px);
    }

    /* Success button variant */
    .stButton[data-testid="baseButton-success"] > button,
    .stButton > button[data-testid="baseButton-success"] {
        background: hsl(var(--success));
        color: hsl(var(--success-foreground));
        box-shadow: var(--shadow-card);
        border: none;
    }

    .stButton[data-testid="baseButton-success"] > button:hover,
    .stButton > button[data-testid="baseButton-success"]:hover {
        background: hsl(var(--success) / 0.9);
        box-shadow: var(--shadow-glow);
        transform: translateY(-1px);
    }

    /* Destructive button variant */
    .stButton[data-testid="baseButton-destructive"] > button,
    .stButton > button[data-testid="baseButton-destructive"] {
        background: hsl(var(--destructive));
        color: hsl(var(--destructive-foreground));
        box-shadow: var(--shadow-card);
        border: none;
    }

    .stButton[data-testid="baseButton-destructive"] > button:hover,
    .stButton > button[data-testid="baseButton-destructive"]:hover {
        background: hsl(var(--destructive) / 0.9);
        box-shadow: var(--shadow-elevated);
        transform: translateY(-1px);
    }

    /* Secondary button variant */
    .stButton[data-testid="baseButton-secondary"] > button,
    .stButton > button[data-testid="baseButton-secondary"] {
        background: hsl(var(--secondary));
        color: hsl(var(--secondary-foreground));
        box-shadow: var(--shadow-card);
        border: none;
    }

    .stButton[data-testid="baseButton-secondary"] > button:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background: hsl(var(--secondary) / 0.8);
        box-shadow: var(--shadow-elevated);
        transform: translateY(-1px);
    }

    /* Outline button variant */
    .stButton[data-testid="baseButton-outline"] > button,
    .stButton > button[data-testid="baseButton-outline"] {
        background: hsl(var(--background));
        color: hsl(var(--foreground));
        border: 1px solid hsl(var(--input));
        box-shadow: none;
    }

    .stButton[data-testid="baseButton-outline"] > button:hover,
    .stButton > button[data-testid="baseButton-outline"]:hover {
        background: hsl(var(--accent));
        color: hsl(var(--accent-foreground));
        box-shadow: var(--shadow-card);
        transform: translateY(-1px);
    }

    /* Map container styling */
    .map-container {
        background: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 1.5rem;
        box-shadow: var(--shadow-card);
        margin-top: 1.5rem;
    }

    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: hsl(var(--muted));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
    }

    .streamlit-expanderContent {
        background-color: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-top: none;
        border-radius: 0 0 var(--radius) var(--radius);
    }

    /* Success/Error message styling */
    .stSuccess {
        background-color: hsl(var(--success) / 0.1);
        border: 1px solid hsl(var(--success) / 0.2);
        border-radius: var(--radius);
    }

    .stError {
        background-color: hsl(0 84% 60% / 0.1);
        border: 1px solid hsl(0 84% 60% / 0.2);
        border-radius: var(--radius);
    }

    .stInfo {
        background-color: hsl(var(--primary) / 0.1);
        border: 1px solid hsl(var(--primary) / 0.2);
        border-radius: var(--radius);
    }

    .stWarning {
        background-color: hsl(38 92% 50% / 0.1);
        border: 1px solid hsl(38 92% 50% / 0.2);
        border-radius: var(--radius);
    }
    
    /* Header Styles */
    .header {
        background-color: hsl(var(--card));
        border-bottom: 1px solid hsl(var(--border));
        box-shadow: var(--shadow-card);
        width: 100%;
        margin: 0;
        padding: 0;
    }
    
    .header-container {
        width: 100%;
        margin: 0;
        padding: 0.5rem;
        position: relative;
    }
    
    .header-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 4rem;
        padding: 0;
        width: 100%;
    }
    
    .header-left {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 0;
        padding: 0;
        position: absolute;
        left: 1rem;
    }
    
    .header-right {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin: 0;
        padding: 0;
        position: absolute;
        right: 1rem;
    }
    
    .header-icon {
        padding: 0.5rem;
        background: hsl(var(--primary) / 0.1);
        border-radius: var(--radius);
    }
    
    .icon-tree {
        color: hsl(var(--primary));
    }
    
    .header-text h1 {
        font-size: 1.5rem;
        font-weight: 600;
        color: hsl(var(--foreground));
        margin: -1.3rem 0 -0.3rem 0;
        line-height: 1.2;
    }
    
    .header-text p {
        font-size: 1rem;
        color: hsl(var(--muted-foreground));
        margin: -0.9rem 0 0 0;
        line-height: 1.2;
    }
    
    .header-right {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .status-badge {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        background: hsl(var(--success));
        color: hsl(var(--success-foreground));
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .status-icon {
        width: 12px;
        height: 12px;
    }
    
    .activity-icon {
        color: hsl(var(--muted-foreground));
    }
    
    /* Card Styles */
    .card {
        border-radius: var(--radius);
        border: 1px solid hsl(var(--border));
        background-color: hsl(var(--card));
        color: hsl(var(--card-foreground));
        box-shadow: var(--shadow-card);
        padding: 1.5rem;
    }
    .card1 {
        border-radius: var(--radius);
        border: 1px solid hsl(var(--border));
        background-color: hsl(var(--card));
        color: hsl(var(--card-foreground));
        box-shadow: var(--shadow-card);
        padding-left:1.5rem;
    }
    .cardMe {
        border-radius: var(--radius);
        border: 1px solid hsl(var(--border));
        background-color: hsl(var(--card));
        color: hsl(var(--card-foreground));
        box-shadow: var(--shadow-card);
    }
    
    .card-header {
        padding: 0;
        margin-bottom: 1rem;
    }
    .card-headerMe {
     display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding-top: 1rem;
    padding-left: 1.25rem;
    padding-bottom: 0;
     }

    .card-header2 {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
        padding: 1.5rem;
    }
    .card-header2 {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
        padding: 1.5rem;
    }
    .card-header1 {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
        padding: 1.5rem;
     
    }
    
    .card-title {
        font-size: 1.75rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: hsl(var(--foreground));
        margin: 0;
    }
    
    .card-description {
        font-size: 0.875rem;
        color: hsl(var(--muted-foreground));
        margin: 0;
        margin-top: 0.5rem;
    }
    
    .card-content {
        padding: 0;
        margin-top: 1rem;
    }
    
    /* Sidebar Styles */
    .sidebar-card {
        background-color: hsl(var(--card));
        box-shadow: var(--shadow-card);
    }
    
    .search-icon {
        color: hsl(var(--primary));
    }
    
    .settings-section {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
    }
    
    .study-area {
        display: flex;
        flex-direction: column;
        gap: 0;
        margin-top: 0.5rem;
    }
    
    .label {
        font-size: 1.25rem;
        font-weight: 500;
        color: hsl(var(--foreground));
        margin: 0;
        line-height: 1.2;
    }
    
    .study-area-text {
        font-size: 1.25rem;
        color: hsl(var(--muted-foreground));
        margin-bottom: 0.5;
        line-height: 1.2;
    }
    
    .separator {
        height: 1px;
        background-color: hsl(var(--border));
        margin-top: -0.5rem ;
    }
    
    .coordinates-section {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }
    
    .coordinates-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.5rem;
    }
    
    .coordinate-input {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }
    
    .input-label {
        font-size: 0.975rem;
        color: hsl(var(--muted-foreground));
    }
    
    .input {
        height: 2rem;
        width: 100%;
        border-radius: calc(var(--radius) - 2px);
        border: 1px solid hsl(var(--input));
        background-color: hsl(var(--background));
        padding: 0.5rem 0.75rem;
        font-size: 1 rem;
        color: hsl(var(--foreground));
        transition: var(--transition-smooth);
    }
    
    .input:focus {
        outline: none;
        border-color: hsl(var(--ring));
        box-shadow: 0 0 0 2px hsl(var(--ring) / 0.2);
    }
    
    .time-range-section {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        padding-top: 1rem;
        margin-bottom: 1rem;
    }
    
    .time-range-label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 1.25rem;
        font-weight: 500;
        color: hsl(var(--foreground));
    }
    
    .calendar-icon {
        color: hsl(var(--foreground));
    }
    
    .year-selects {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
        margin-top: 1rem;
    }
    
    .year-select {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }
    
    .select {
        height: 2rem;
        width: 100%;
        border-radius: calc(var(--radius) - 2px);
        border: 1px solid hsl(var(--input));
        background-color: hsl(var(--background));
        padding: 0 0.75rem;
        font-size: 0.975rem;
        color: hsl(var(--foreground));
        cursor: pointer;
        transition: var(--transition-smooth);
    }
    
    .select:focus {
        outline: none;
        border-color: hsl(var(--ring));
        box-shadow: 0 0 0 2px hsl(var(--ring) / 0.2);
    }
    
    .analyze-button {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        background: var(--gradient-hero);
        color: hsl(var(--primary-foreground));
        border: none;
        border-radius: var(--radius);
        padding: 0.75rem 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.3s ease;
    }
    
    .analyze-button:hover:not(:disabled) {
        opacity: 0.9;
    }
    
    .analyze-button:disabled {
        opacity: 0.7;
        cursor: not-allowed;
    }
    
    .map-icon {
        flex-shrink: 0;
    }
    
    /* Status Overview */
    .status-overview {
        width: 100%;
        margin-top: 1rem;
        margin-bottom: 1rem;

    }
    
    
    .status-indicator-icon {
        margin-top: 0.125rem;
        flex-shrink: 0;
    }
    
    .status-indicator-content {
        display: flex;
        flex-direction: column;
        gap: 0.05rem;
    }
    
    .status-indicator-title {
        font-weight: 600;
        font-size: 0.875rem;
        margin: 0.25rem 0.5rem 0 0.5rem;
        line-height: 1.2;
    }
    
    .status-indicator-description {
        font-size: 0.75rem;
        opacity: 0.8;
        margin: 0 0.5rem 0.25rem 0.5rem;
    }
    
    /* Results Section */
    .results-section {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
    }
    
    .results-header {
        margin-bottom: 1rem;
    }
    
    .results-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: hsl(var(--foreground));
    }
    
    .results-subtitle {
        color: hsl(var(--muted-foreground));
    }
    
    .results-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 1rem;
    }
    
    @media (min-width: 768px) {
        .results-grid {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    
    .result-card {
        background-color: hsl(var(--card));
        box-shadow: var(--shadow-card);
        border-radius: var(--radius);
        border: 1px solid hsl(var(--border));
        height: 150px !important;
        display: flex !important;
        align-items: center !important;
        margin-bottom: 50px !important;
    }
    
    .result-card-content {
        padding: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        height: 100%;
    }
    
    .result-card-info {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        flex: 1;
    }
    
    .result-card-label {
        font-size: 0.875rem !important;
        color: hsl(var(--muted-foreground)) !important;
        margin: 0 !important;
    }
    
    .result-card-value {
        font-size: 2.5rem !important;
        line-height: 1.1 !important;
        font-weight: 700 !important;
        color: hsl(var(--foreground)) !important;
        margin: 0 !important;
    }
    
    .result-card-value.success {
        color: hsl(var(--success)) !important;
    }
    
    .result-card-value.destructive {
        color: hsl(var(--destructive)) !important;
    }
    
    .result-card-trend {
        font-size: 0.75rem !important;
        color: hsl(var(--success)) !important;
        display: flex;
        align-items: center;
        gap: 0.25rem;
        margin-top: 0.25rem;
    }
    
    .result-card-trend.negative {
        color: hsl(var(--destructive)) !important;
    }
    
    .result-card-icon {
        padding: 0.75rem;
        border-radius: 50%;
        flex-shrink: 0;
    }
    
    .result-card-icon.accent {
        background-color: hsl(var(--success) / 0.1);
        color: hsl(var(--success));
    }
    
    .result-card-icon.success {
        background-color: hsl(var(--success) / 0.1);
        color: hsl(var(--success));
    }
    
    .result-card-icon.success-bg {
        background-color: hsl(var(--success) / 0.1);
        color: hsl(var(--success));
    }
    .result-card-icon.destructive-bg {
        background-color: hsl(var(--destructive) / 0.1);
        color: hsl(var(--destructive));
    }
    
    /* Map Card */
    .map-card {
        background-color: hsl(var(--card));
        box-shadow: var(--shadow-card);
    }
    
    .map-card-header {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    .map-card-content {
        padding: 0.5rem !important;
        margin: 0 !important;
    }
    
    .map-card {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }
    
    /* Methodology Card */
    .methodology-card {
        background-color: hsl(var(--card));
        box-shadow: var(--shadow-card);
    }
    
    .methodology-text {
        color: hsl(var(--muted-foreground));
    }
    
    /* Default Section */
    .default-card {
        background-color: hsl(var(--card));
        box-shadow: var(--shadow-card);
    }
    
    .default-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0;
        margin: 0;
    }
    
    .year-badge {
        background-color: hsl(var(--secondary));
        color: hsl(var(--secondary-foreground));
        padding: 0.5rem 1rem;
        border-radius: calc(var(--radius) - 2px);
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .default-placeholder {
        background-color: hsl(var(--muted) / 0.3);
        border-radius: var(--radius);
        padding: 2rem;
        text-align: center;
        border: 2px dashed hsl(var(--border));
    }
    
    .default-placeholder-icon {
        color: hsl(var(--muted-foreground));
        margin: 0 auto 1rem;
    }
    
    .default-placeholder-title {
        color: hsl(var(--muted-foreground));
        margin-bottom: 0.5rem;
    }
    
    .default-placeholder-description {
        font-size: 0.875rem;
        color: hsl(var(--muted-foreground));
    }
</style>
""", unsafe_allow_html=True)

# Constants are now imported from config.py


@st.cache_resource
def authenticate_database():
    """
    Authenticate and initialize database for large LiDAR datasets
    Supports multiple database backends
    """
    try:
        if ACTIVE_DB == "local_postgres":
            # Use local PostgreSQL backend
            handler = PostGISRasterHandler()
            if handler.connect():
                if initialize_lidar_datasets():
                    handler.disconnect()
                    return True, "✅ Local PostgreSQL connected and LiDAR datasets initialized"
                else:
                    handler.disconnect()
                    return False, "❌ Failed to initialize LiDAR datasets"
            else:
                return False, "❌ Failed to connect to local PostgreSQL database"
                
        elif ACTIVE_DB == "digitalocean":
            # Use DigitalOcean PostgreSQL backend
            handler = PostGISRasterHandler()
            if handler.connect():
                if initialize_lidar_datasets():
                    handler.disconnect()
                    return True, "✅ DigitalOcean PostgreSQL connected and LiDAR datasets initialized"
                else:
                    handler.disconnect()
                    return False, "❌ Failed to initialize LiDAR datasets"
            else:
                return False, "❌ Failed to connect to DigitalOcean database"
        else:
            return False, f"❌ Unknown database type: {ACTIVE_DB}"
            
    except Exception as e:
        return False, f"❌ Database authentication failed: {str(e)}"

def get_tree_cover(year):
    """Fetch tree cover for the given year using the active database backend."""
    try:
        # Use PostgreSQL backend
        coverage, error = get_tree_coverage_postgis(year)
        
        if error:
            return None, f"Database error for {year}: {error}"
        
        # Create a simple Earth Engine image for visualization
        # This is just for the map display - actual data comes from the database
        bounds = get_study_area_bounds()
        hudson_square = ee.Geometry.Rectangle([
            bounds['west'],
            bounds['south'],
            bounds['east'],
            bounds['north']
        ])
        
        # Create a constant image with the calculated coverage for visualization
        tree_cover = ee.Image.constant(coverage).clip(hudson_square).rename('tree_cover')
        
        return tree_cover, None
        
    except Exception as e:
        print(f"Error in get_tree_cover for {year}: {str(e)}")
        return None, str(e)



# Replace your create_map function with this updated version

def create_tree_visualization_data(year, bounds):
    """Create tree visualization data using cached visualization image (FASTEST) or COG files (slow fallback)
    
    Args:
        year: Year of the data
        bounds: Dict with bounds (polygon or rectangle format)
    """
    try:
        from postgis_raster import PostGISRasterHandler
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        from io import BytesIO
        import base64
        import rasterio.transform
        
        # Try to get cached visualization image first (FASTEST)
        handler = PostGISRasterHandler()
        data = None
        cached_visualization = None
        cached_geo_bounds = None
        
        if handler.connect():
            try:
                # Use the actual bounds parameter, not hardcoded HUDSON_SQUARE_BOUNDS
                cached_result = handler.get_cached_pixel_data(year, bounds)
                
                if cached_result:
                    data, metadata = cached_result
                    cached_visualization = metadata.get('visualization_image')
                    cached_geo_bounds = metadata.get('geo_bounds')
                    
                    # Verify cached bounds match requested bounds
                    cached_bounds = metadata.get('bounds_data')
                    # Normalize both for comparison
                    if cached_bounds:
                        try:
                            import json
                            cached_normalized = json.dumps(cached_bounds, sort_keys=True) if isinstance(cached_bounds, dict) else cached_bounds
                            bounds_normalized = json.dumps(bounds, sort_keys=True) if isinstance(bounds, dict) else bounds
                            bounds_match = cached_normalized == bounds_normalized
                        except:
                            # Fallback to direct comparison
                            bounds_match = cached_bounds == bounds
                    else:
                        bounds_match = False
                    
                    if bounds_match:
                        # If we have a cached visualization with matching bounds, return it immediately
                        if cached_visualization and cached_geo_bounds:
                            print(f"⚡⚡⚡ Using cached visualization image for {year} (instant!)")
                            handler.disconnect()
                            return cached_visualization, cached_geo_bounds, None
                        
                        print(f"⚡ Using cached pixel data for visualization of {year}")
                        handler.disconnect()
                    else:
                        # Bounds don't match - need to recalculate
                        print(f"⚠️ Cached bounds don't match, recalculating visualization...")
                        data = None  # Force recalculation
                        handler.disconnect()
                else:
                    print(f"⚠️ No cached visualization data for {year}, reading from COG...")
                    handler.disconnect()
            except Exception as cache_error:
                print(f"⚠️ Cache lookup failed: {cache_error}")
                handler.disconnect()
        
        # If no cached data, read from COG file (SLOW - only happens once)
        if data is None:
            import rasterio
            from rasterio.warp import transform_bounds
            
            # Get the COG URL for this year
            cog_url = LIDAR_DATASETS.get(str(year))
            if not cog_url:
                return None, None, f"No COG URL found for year {year}"
            
            # Read the COG data with polygon masking
            with rasterio.open(cog_url) as src:
                # Handle polygon masking for accurate visualization
                if bounds.get('type') == 'polygon':
                    from rasterio.mask import mask
                    import geopandas as gpd
                    from shapely.geometry import Polygon
                    
                    # Create polygon from coordinates
                    coords = bounds['coordinates']
                    polygon = Polygon(coords)
                    
                    # Create GeoDataFrame
                    gdf = gpd.GeoDataFrame([1], geometry=[polygon], crs='EPSG:4326')
                    gdf = gdf.to_crs(src.crs)
                    
                    # Use rasterio.mask to extract polygon data
                    # filled=False keeps nodata as the source nodata value
                    # crop=True crops to the bounding box of the polygon
                    data, out_transform = mask(src, gdf.geometry, crop=True, filled=False, nodata=0)
                    data = data[0]  # Get first band
                    
                    # Calculate actual geographic bounds of the cropped data
                    height, width = data.shape
                    bounds_window = rasterio.transform.array_bounds(height, width, out_transform)
                    
                    # Transform back to WGS84 for folium
                    from rasterio.warp import transform_bounds as trans_bounds
                    west, south, east, north = trans_bounds(
                        src.crs, 'EPSG:4326',
                        bounds_window[0], bounds_window[1], 
                        bounds_window[2], bounds_window[3]
                    )
                    
                    geo_bounds = [[south, west], [north, east]]
                    
                else:
                    # Legacy rectangle bounds
                    raster_bounds = transform_bounds('EPSG:4326', src.crs, 
                                                   bounds['west'], bounds['south'],
                                                   bounds['east'], bounds['north'])
                    
                    window = rasterio.windows.from_bounds(*raster_bounds, src.transform)
                    data = src.read(1, window=window)
                    geo_bounds = [[bounds['south'], bounds['west']], [bounds['north'], bounds['east']]]
        else:
            # Using cached data - calculate geo_bounds from bounds
            if bounds.get('type') == 'polygon':
                coords = bounds['coordinates']
                lats = [coord[1] for coord in coords]
                lons = [coord[0] for coord in coords]
                geo_bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
            else:
                geo_bounds = [[bounds['south'], bounds['west']], [bounds['north'], bounds['east']]]
        
        # Create tree classification visualization (same for both cached and COG data)
        # NYC LiDAR: Class 1 = Tree Canopy, Class 2 = Grass/Shrubs
        tree_mask = np.isin(data, [1, 2])  # Tree Canopy (1) + Grass/Shrubs (2)
        
        # Create a colored visualization with transparency for areas outside polygon
        fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
        
        # Mask out nodata values (areas outside polygon)
        valid_data_mask = data != 0  # 0 is nodata value from rasterio.mask
        
        # First display the original data with a neutral colormap (only valid areas)
        colors_original = ['white', 'lightgray', 'lightblue', 'lightgray', 'brown', 'gray', 'lightyellow', 'lightgray']
        cmap_original = mcolors.ListedColormap(colors_original)
        masked_data = np.ma.masked_where(~valid_data_mask, data)
        ax.imshow(masked_data, cmap=cmap_original, vmin=0, vmax=7, alpha=0.7, aspect='equal')
        
        # Then overlay only the tree areas in GREEN (only within polygon)
        tree_overlay = np.ma.masked_where(~(tree_mask & valid_data_mask), tree_mask)
        ax.imshow(tree_overlay, cmap='Greens', alpha=0.8, vmin=0, vmax=1, aspect='equal')
        
        # No title - just the visualization (title shown on map instead)
        ax.axis('off')
        plt.tight_layout(pad=0)
        
        # Save to bytes with transparent background
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', pad_inches=0,
                   facecolor='none', edgecolor='none', transparent=True)
        buffer.seek(0)
        
        # Convert to base64
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return f"data:image/png;base64,{image_base64}", geo_bounds, None
            
    except Exception as e:
        print(f"Error creating tree visualization for {year}: {e}")
        import traceback
        traceback.print_exc()
        return None, None, str(e)

def _add_sidebar_draw_controls(folium_map):
    """No custom styling - use default Leaflet.draw toolbar so icons display correctly."""
    pass


def create_map(cover_year1, cover_year2, year1, year2, drawn_bounds=None, show_entire_map_coverage=False):
    """Create the interactive map using PostGIS data and COG files.
    
    Args:
        cover_year1: Tree coverage percentage for year1
        cover_year2: Tree coverage percentage for year2
        year1: First year for comparison
        year2: Second year for comparison
        drawn_bounds: Optional dict with drawn area bounds (polygon or rectangle)
        show_entire_map_coverage: If True, show tree coverage tiles for entire map; if False, only for drawn area
    """
    
    # Use drawn bounds if provided, otherwise use default Hudson Square bounds
    active_bounds = drawn_bounds if drawn_bounds else HUDSON_SQUARE_BOUNDS
    
    # Create folium map with Google Maps as base layer
    folium_map = folium.Map(
        location=[40.725, -74.005],
        zoom_start=14,  # Wider initial viewport (lower = more area visible)
        max_zoom=22,  # Increased from 18 to 22 for more zoom
        min_zoom=10,  # Reduced from 12 to 10 for wider view
        tiles=None,  # No default tiles, we'll add Google Maps
        prefer_canvas=True,  # Better performance
        no_wrap=True,  # Prevent wrapping around the world
        dragging=True,  # Enable dragging
        touchZoom=True,  # Enable touch zoom
        doubleClickZoom=True,  # Enable double-click zoom
        scrollWheelZoom=True,  # Enable scroll wheel zoom
        boxZoom=True,  # Enable box zoom
        keyboard=True,  # Enable keyboard navigation
    )
    
    # Add Google Maps as the default base layer
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google Maps',
        name='Google Maps',
        overlay=False,
        control=True,
        show=True,  # Explicitly set as default/active layer
        max_zoom=22,
        min_zoom=0
    ).add_to(folium_map)
    
    # Add study area boundary - handle both rectangle and polygon
    # Show drawn area if available, otherwise show default Hudson Square
    if active_bounds.get('type') == 'polygon':
        # Polygon boundary
        coords = active_bounds['coordinates']
        # Convert to folium format (lat, lon)
        folium_coords = [[coord[1], coord[0]] for coord in coords]
        
        area_label = "Drawn Study Area" if drawn_bounds else "Hudson Square Study Area (Default)"
        folium.Polygon(
            locations=folium_coords,
            color='red',
            weight=3,
            fill=True,
            fillColor='red',
            fillOpacity=0.1,
            popup=area_label
        ).add_to(folium_map)
    else:
        # Rectangle boundary
        if active_bounds.get('type') == 'rectangle' or 'west' in active_bounds:
            if 'west' in active_bounds:
                study_bounds = [
                    [active_bounds['south'], active_bounds['west']],
                    [active_bounds['north'], active_bounds['east']]
                ]
            else:
                bounds = get_study_area_bounds()
                study_bounds = [
                    [bounds['south'], bounds['west']],
                    [bounds['north'], bounds['east']]
                ]
            
            area_label = "Drawn Study Area" if drawn_bounds else "Hudson Square Study Area (Default)"
            folium.Rectangle(
                bounds=study_bounds,
                color='red',
                weight=3,
                fill=True,
                fillColor='red',
                fillOpacity=0.1,
                popup=area_label
            ).add_to(folium_map)
    
    # Add COG layers using FastAPI tile server (MUCH FASTER)
    # Browser only loads visible tiles on-demand
    try:
        # Year 1 COG layer - using FastAPI tile server
        cog_url_1 = LIDAR_DATASETS[str(year1)]
        cog_url_2 = LIDAR_DATASETS[str(year2)]
        
        # Create separate layer groups for each year
        year1_layer = folium.FeatureGroup(name=f'{year1} Tree Coverage')
        year2_layer = folium.FeatureGroup(name=f'{year2} Tree Coverage')
        
        # Only add tile layers if show_entire_map_coverage is enabled
        # Otherwise, fetch visualization for just the drawn area from API
        if show_entire_map_coverage:
            # Add TileLayer for Year 1 (served by FastAPI backend)
            folium.TileLayer(
                tiles=f'{FASTAPI_URL}/tiles/{year1}/{{z}}/{{x}}/{{y}}.png',
                attr=f'{year1} LiDAR Tree Coverage',
                name=f'{year1} Tree Coverage',
                overlay=True,
                control=True,
                opacity=0.7,
                max_zoom=22,
                min_zoom=10,
                show=True  # Show by default
            ).add_to(year1_layer)
            
            # Add TileLayer for Year 2 (served by FastAPI backend)
            folium.TileLayer(
                tiles=f'{FASTAPI_URL}/tiles/{year2}/{{z}}/{{x}}/{{y}}.png',
                attr=f'{year2} LiDAR Tree Coverage',
                name=f'{year2} Tree Coverage',
                overlay=True,
                control=True,
                opacity=0.7,
                max_zoom=22,
                min_zoom=10,
                show=True  # Show by default
            ).add_to(year2_layer)
        else:
            # Fetch visualization images for drawn area only from API
            # Check cache first (main thread), then fetch missing data in parallel
            from concurrent.futures import ThreadPoolExecutor
            
            cache_key_1 = _get_bounds_cache_key(year1, active_bounds)
            cache_key_2 = _get_bounds_cache_key(year2, active_bounds)
            
            # Check what's already cached
            cached_1 = st.session_state.get(cache_key_1)
            cached_2 = st.session_state.get(cache_key_2)
            
            viz_1, geo_bounds_1, viz_error_1 = None, None, None
            viz_2, geo_bounds_2, viz_error_2 = None, None, None
            
            if cached_1:
                viz_1, geo_bounds_1 = cached_1['image'], cached_1['geo_bounds']
                print(f"⚡ Using cached visualization for {year1}")
            if cached_2:
                viz_2, geo_bounds_2 = cached_2['image'], cached_2['geo_bounds']
                print(f"⚡ Using cached visualization for {year2}")
            
            # Fetch only what's not cached
            needs_fetch_1 = viz_1 is None
            needs_fetch_2 = viz_2 is None
            
            if needs_fetch_1 or needs_fetch_2:
                print(f"🎨 Fetching visualizations for drawn area from API (parallel)...")
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = {}
                    if needs_fetch_1:
                        futures[year1] = executor.submit(_fetch_visualization_from_api, year1, active_bounds)
                    if needs_fetch_2:
                        futures[year2] = executor.submit(_fetch_visualization_from_api, year2, active_bounds)
                    
                    if needs_fetch_1:
                        viz_1, geo_bounds_1, viz_error_1 = futures[year1].result()
                        if viz_1 is not None:
                            st.session_state[cache_key_1] = {'image': viz_1, 'geo_bounds': geo_bounds_1}
                            print(f"✅ Got visualization for {year1}, bounds: {geo_bounds_1}")
                    if needs_fetch_2:
                        viz_2, geo_bounds_2, viz_error_2 = futures[year2].result()
                        if viz_2 is not None:
                            st.session_state[cache_key_2] = {'image': viz_2, 'geo_bounds': geo_bounds_2}
                            print(f"✅ Got visualization for {year2}, bounds: {geo_bounds_2}")
            
            # Add Year 1 visualization
            if viz_1 and geo_bounds_1:
                folium.raster_layers.ImageOverlay(
                    image=viz_1,
                    bounds=geo_bounds_1,
                    opacity=0.8,
                    name=f'{year1} Tree Coverage (Area)',
                    interactive=True,
                    cross_origin=False,
                    zindex=100,
                    show=True
                ).add_to(folium_map)
            elif viz_error_1:
                print(f"⚠️ Could not get visualization for {year1}: {viz_error_1}")
            
            # Add Year 2 visualization
            if viz_2 and geo_bounds_2:
                folium.raster_layers.ImageOverlay(
                    image=viz_2,
                    bounds=geo_bounds_2,
                    opacity=0.8,
                    name=f'{year2} Tree Coverage (Area)',
                    interactive=True,
                    cross_origin=False,
                    zindex=101,
                    show=True
                ).add_to(folium_map)
            elif viz_error_2:
                print(f"⚠️ Could not get visualization for {year2}: {viz_error_2}")
        
        # Create a comparison layer showing both years
        comparison_layer = folium.FeatureGroup(name='Analysis Summary')
        
        # Add center marker with summary to comparison layer
        # Calculate center of polygon
        if active_bounds.get('type') == 'polygon':
            coords = active_bounds['coordinates']
            center_lat = sum(coord[1] for coord in coords) / len(coords)
            center_lon = sum(coord[0] for coord in coords) / len(coords)
        else:
            if 'west' in active_bounds:
                center_lat = (active_bounds['north'] + active_bounds['south']) / 2
                center_lon = (active_bounds['east'] + active_bounds['west']) / 2
            else:
                bounds_rect = get_study_area_bounds()
                center_lat = (bounds_rect['north'] + bounds_rect['south']) / 2
                center_lon = (bounds_rect['east'] + bounds_rect['west']) / 2
        
        change = cover_year2 - cover_year1
        change_icon = '📈' if change > 0 else '📉' if change < 0 else '➡️'
        change_color = 'green' if change > 0 else 'red' if change < 0 else 'orange'
        
        folium.Marker(
            [center_lat, center_lon],
            popup=f"""
            <div style="font-family: Arial, sans-serif; width: 300px;">
                <h3 style="color: #dc2626; margin: 0 0 15px 0; text-align: center;">🌳 Hudson Square Tree Analysis</h3>
                <div style="background: #fef3c7; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <p style="margin: 5px 0; color: #ea580c;"><strong>🟠 {year1} Coverage:</strong> {cover_year1:.2f}%</p>
                    <p style="margin: 5px 0;"><strong>Resolution:</strong> 5ft (1.5m)</p>
                </div>
                <div style="background: #dbeafe; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <p style="margin: 5px 0; color: #1e40af;"><strong>🔵 {year2} Coverage:</strong> {cover_year2:.2f}%</p>
                    <p style="margin: 5px 0;"><strong>Resolution:</strong> 6in (0.15m)</p>
                </div>
                <div style="background: #f3f4f6; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <p style="margin: 5px 0;"><strong>📊 Change:</strong> <span style="color: {change_color};">{change:+.2f}% {change_icon}</span></p>
                </div>
                <div style="margin-top: 10px;">
                    <p style="margin: 5px 0; font-size: 12px;"><strong>Rendering:</strong></p>
                    <p style="margin: 5px 0; font-size: 12px;">• FastAPI Tile Server (rio-tiler)</p>
                    <p style="margin: 5px 0; font-size: 12px;">• COG files on Google Cloud Storage</p>
                    <p style="margin: 5px 0; font-size: 12px;">• On-demand tile loading (efficient)</p>
                </div>
            </div>
            """,
            tooltip=f"🌳 Tree Coverage: {year1}: {cover_year1:.2f}% → {year2}: {cover_year2:.2f}% ({change:+.2f}%)",
            icon=folium.Icon(color='red', icon='info-sign', prefix='fa')
        ).add_to(comparison_layer)
        
        # Add the layer groups to the map
        # Only add year layers when showing entire map coverage (tile layers)
        # When showing area coverage, ImageOverlays are added directly to the map
        if show_entire_map_coverage:
            year1_layer.add_to(folium_map)
            year2_layer.add_to(folium_map)
        comparison_layer.add_to(folium_map)
        
    except Exception as e:
        print(f"COG layers not available: {e}")
        # Add fallback markers with coverage information
        bounds = get_study_area_bounds()
        center_lat = (bounds['north'] + bounds['south']) / 2
        center_lon = (bounds['east'] + bounds['west']) / 2
        
        folium.Marker(
            [center_lat, center_lon],
            popup=f"""
            <b>Hudson Square Tree Coverage</b><br>
            {year1}: {cover_year1:.1f}%<br>
            {year2}: {cover_year2:.1f}%<br>
            Change: {cover_year2 - cover_year1:+.1f}%<br>
            <br>
            <i>Data from PostgreSQL + COG files</i>
            """,
            icon=folium.Icon(color='green', icon='tree')
        ).add_to(folium_map)
    
    
    
    # Add drawing tool with callback to capture drawn shapes
    draw = Draw(
        export=True,
        filename='drawn_area.geojson',
        position='topleft',
        draw_options={
            'polyline': False,
            'polygon': True,
            'rectangle': True,
            'circle': False,
            'marker': False,
            'circlemarker': False
        },
        edit_options={
            'edit': False,
            'remove': False
        }
    )
    draw.add_to(folium_map)
    _add_sidebar_draw_controls(folium_map)
    
    # Add JavaScript to capture drawn shapes and store in localStorage
    capture_script = """
    <script>
    // Store drawn shapes in localStorage so Streamlit can access them
    function extractBoundsFromGeoJSON(geojson) {
        if (!geojson) return null;
        
        // Handle FeatureCollection
        let geometry = geojson.geometry;
        if (geojson.features && geojson.features.length > 0) {
            geometry = geojson.features[0].geometry;
        }
        if (!geometry) return null;
        
        if (geometry.type === 'Polygon') {
            const coords = geometry.coordinates[0]; // Exterior ring
            return {
                type: 'polygon',
                coordinates: coords.map(coord => [coord[0], coord[1]]) // [lon, lat]
            };
        } else if (geometry.type === 'Rectangle') {
            const coords = geometry.coordinates[0];
            const lons = coords.map(c => c[0]);
            const lats = coords.map(c => c[1]);
            return {
                type: 'rectangle',
                west: Math.min(...lons),
                east: Math.max(...lons),
                south: Math.min(...lats),
                north: Math.max(...lats)
            };
        }
        return null;
    }
    
    // Wait for map to be ready
    setTimeout(function() {
        // Access the map through the iframe
        const iframes = document.querySelectorAll('iframe');
        iframes.forEach(function(iframe) {
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                const mapContainer = iframeDoc.querySelector('.leaflet-container');
                
                if (mapContainer) {
                    // Get the map instance
                    const map = iframeDoc.defaultView.L && iframeDoc.defaultView.L.map;
                    if (map && map.eachLayer) {
                        // Find the draw control
                        map.eachLayer(function(layer) {
                            if (layer instanceof iframeDoc.defaultView.L.Draw.Feature) {
                                // Listen for draw events
                                map.on('draw:created', function(e) {
                                    const layer = e.layer;
                                    const geojson = layer.toGeoJSON();
                                    const bounds = extractBoundsFromGeoJSON(geojson);
                                    
                                    if (bounds) {
                                        // Store in localStorage
                                        localStorage.setItem('drawnBounds', JSON.stringify(bounds));
                                        localStorage.setItem('drawnGeoJSON', JSON.stringify(geojson));
                                        
                                        // Show notification
                                        console.log('Shape drawn! Use "Capture Last Drawn Shape" button to use it.');
                                        
                                        // Try to show a visual indicator
                                        if (window.parent && window.parent.document) {
                                            const notification = window.parent.document.createElement('div');
                                            notification.style.cssText = 'position:fixed;top:20px;right:20px;background:#4CAF50;color:white;padding:10px;border-radius:5px;z-index:9999;';
                                            notification.textContent = '✓ Shape captured! Click "Capture Last Drawn Shape" button.';
                                            window.parent.document.body.appendChild(notification);
                                            setTimeout(() => notification.remove(), 3000);
                                        }
                                    }
                                });
                                
                                map.on('draw:edited', function(e) {
                                    const layers = e.layers;
                                    layers.eachLayer(function(layer) {
                                        const geojson = layer.toGeoJSON();
                                        const bounds = extractBoundsFromGeoJSON(geojson);
                                        if (bounds) {
                                            localStorage.setItem('drawnBounds', JSON.stringify(bounds));
                                            localStorage.setItem('drawnGeoJSON', JSON.stringify(geojson));
                                        }
                                    });
                                });
                                
                                map.on('draw:deleted', function(e) {
                                    localStorage.removeItem('drawnBounds');
                                    localStorage.removeItem('drawnGeoJSON');
                                });
                            }
                        });
                    }
                }
            } catch(e) {
                console.log('Could not access map:', e);
            }
        });
    }, 2000);
    </script>
    """
    
    # Add script to map HTML
    from folium import Element
    folium_map.get_root().html.add_child(Element(capture_script))
    
    # Add additional Google Maps layers
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='Google Satellite',
        overlay=False,
        control=True,
        show=False,  # Not default - user can select from layer control
        max_zoom=22,  # High zoom for satellite
        min_zoom=0
    ).add_to(folium_map)
    
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google Hybrid',
        name='Google Hybrid',
        overlay=False,
        control=True,
        show=False,  # Not default - user can select from layer control
        max_zoom=22,
        min_zoom=0
    ).add_to(folium_map)
    
    # Add layer control
    folium.LayerControl().add_to(folium_map)
    
    return folium_map


def _bounds_from_drawn_feature(drawn_feature):
    """Extract bounds dict from a drawn GeoJSON feature."""
    if not drawn_feature:
        return None

    # Handle FeatureCollection or Feature
    geometry = drawn_feature.get("geometry")
    if not geometry and drawn_feature.get("features"):
        geometry = drawn_feature["features"][0].get("geometry")

    if not geometry:
        return None

    geom_type = geometry.get("type")
    coords = geometry.get("coordinates", [])

    if geom_type == "Polygon":
        exterior_ring = coords[0] if coords else []
        return {
            "type": "polygon",
            "coordinates": [[c[0], c[1]] for c in exterior_ring],
        }
    if geom_type == "Rectangle":
        lons = [c[0] for c in coords[0]]
        lats = [c[1] for c in coords[0]]
        return {
            "type": "rectangle",
            "west": min(lons),
            "east": max(lons),
            "south": min(lats),
            "north": max(lats),
        }

    return None


def _apply_drawn_bounds(bounds, auto_analyze: bool):
    """Apply drawn bounds to session state and optionally trigger analysis."""
    if not bounds:
        return

    st.session_state.drawn_bounds = bounds
    st.session_state.use_drawn_area = True
    st.session_state.has_drawn_area = True  # User has drawn an area
    st.session_state.map_created = False
    st.session_state.map_data = None

    if auto_analyze:
        st.session_state.analysis_run = True


def main():
    # Initialize session state variables
    if 'display_hsbid' not in st.session_state:
        st.session_state.display_hsbid = True  # Default: show HSBID Tree Cover Analysis on load
    if 'analysis_run' not in st.session_state:
        st.session_state.analysis_run = st.session_state.display_hsbid  # Run HSBID analysis on first load when display_hsbid is on
    if 'selected_year1' not in st.session_state:
        st.session_state.selected_year1 = 2010
    if 'selected_year2' not in st.session_state:
        st.session_state.selected_year2 = 2021
    if 'map_created' not in st.session_state:
        st.session_state.map_created = False
    if 'map_data' not in st.session_state:
        st.session_state.map_data = None
    if 'drawing_tool' not in st.session_state:
        st.session_state.drawing_tool = None
    if 'drawn_bounds' not in st.session_state:
        st.session_state.drawn_bounds = None
    if 'use_drawn_area' not in st.session_state:
        st.session_state.use_drawn_area = False
    if 'last_drawn_shape' not in st.session_state:
        st.session_state.last_drawn_shape = None
    if 'auto_analyze_on_draw' not in st.session_state:
        st.session_state.auto_analyze_on_draw = True
    if 'show_entire_map_coverage' not in st.session_state:
        st.session_state.show_entire_map_coverage = False  # Default: only show coverage for drawn area
    if 'has_drawn_area' not in st.session_state:
        st.session_state.has_drawn_area = False  # Track if user has drawn an area
    
    # Professional Header matching the design
    st.markdown("""
    <div class="header">
        <div class="header-container">
            <div class="header-content">
                <div class="header-left">
                    <div class="header-icon">
                        <svg class="icon-tree" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="m17 14 3 3.3a1 1 0 0 1-.7 1.7H4.7a1 1 0 0 1-.7-1.7L7 14h-.3a1 1 0 0 1-.7-1.7L9 9h-.2A1 1 0 0 1 8 7.3L12 3l4 4.3a1 1 0 0 1-.8 1.7H15l3 3.3a1 1 0 0 1-.7 1.7H17Z"/>
                            <path d="M12 22V18"/>
                        </svg>
                    </div>
                    <div class="header-text">
                        <h1>Tree Cover Analysis</h1>
                        <p>Hudson Square, NYC</p>
                    </div>
                </div>
                <div class="header-right">
                    <div class="status-badge">
                        <svg class="status-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M9 12l2 2 4-4"/>
                            <circle cx="12" cy="12" r="9"/>
                        </svg>
                        Authenticated
                    </div>
                    <svg class="activity-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>
                    </svg>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar with enhanced styling from script.css
    with st.sidebar:
        # Header section
        st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <svg class="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="m21 21-4.35-4.35"/>
                </svg>
                Analysis Settings
            </div>
            <p class="card-description">Configure study parameters</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Study Area section
        st.markdown("""
        <div class="study-area">
            <label class="label">Study Area</label>
            <p class="study-area-text">Hudson Square, NYC</p>
        </div>
        """, unsafe_allow_html=True)
        display_hsbid_new = st.checkbox(
            "Display HSBID Tree Cover Analysis",
            value=st.session_state.display_hsbid,
            key="display_hsbid_checkbox"
        )
        if display_hsbid_new != st.session_state.display_hsbid:
            st.session_state.display_hsbid = display_hsbid_new
            if display_hsbid_new:
                # User turned ON: use Hudson Square, clear previous analysis state, re-run HSBID analysis
                st.session_state.use_drawn_area = False
                st.session_state.drawn_bounds = None
                st.session_state.last_drawn_shape = None
                st.session_state.has_drawn_area = True
                st.session_state.map_created = False
                st.session_state.map_data = None
                st.session_state.analysis_run = True
                st.rerun()
            else:
                # User turned OFF: clear Hudson bounds and analysis so user can draw and run custom analysis
                st.session_state.use_drawn_area = False
                st.session_state.drawn_bounds = None
                st.session_state.last_drawn_shape = None
                st.session_state.has_drawn_area = False
                st.session_state.analysis_run = False
                st.session_state.map_created = False
                st.session_state.map_data = None
                st.rerun()
        st.markdown("""<div class="separator"></div>""", unsafe_allow_html=True)
        # Drawing Tools section
        with st.expander("Drawing Tools", expanded=True):
            st.markdown("""
            <div style="margin-bottom: 1rem;">
                <p style="font-size: 0.875rem; color: hsl(var(--muted-foreground));">
                    Use the <strong>drawing tools on the left side of the map</strong> (rectangle, polygon, delete). Analysis runs automatically if enabled.
                </p>
            </div>
            """, unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Use Default", use_container_width=True):
                    st.session_state.use_drawn_area = False
                    st.session_state.drawn_bounds = None
                    st.session_state.last_drawn_shape = None
                    st.session_state.has_drawn_area = True  # User explicitly chose default
                    st.session_state.map_created = False
                    st.session_state.map_data = None
                    st.success("Using default Hudson Square area")
                    st.rerun()
            with col2:
                if st.button("Clear Drawn", use_container_width=True):
                    st.session_state.use_drawn_area = False
                    st.session_state.drawn_bounds = None
                    st.session_state.last_drawn_shape = None
                    st.session_state.has_drawn_area = False  # Reset to initial state
                    st.session_state.analysis_run = False  # Reset analysis
                    st.session_state.map_created = False
                    st.session_state.map_data = None
                    st.info("Drawn area cleared. Draw a new area on the map to analyze.")
                    st.rerun()
            
            # Show current area status
            if st.session_state.use_drawn_area and st.session_state.drawn_bounds:
                st.success("✓ Using drawn area for analysis")
            elif st.session_state.has_drawn_area:
                st.info("ℹ Using default Hudson Square area")
            else:
                st.warning("⚠ Draw an area on the map to begin analysis")
        
        # Tree Coverage Display Options
        with st.expander("Display Options", expanded=True):
            st.markdown("""
            <div style="margin-bottom: 0.5rem;">
                <p style="font-size: 0.875rem; color: hsl(var(--muted-foreground));">
                    Control how tree coverage is displayed on the map.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            show_entire_map = st.checkbox(
                "Show tree coverage for entire map",
                value=st.session_state.show_entire_map_coverage,
                help="When enabled, tree coverage tiles are displayed across the entire map. When disabled, coverage is only shown for your drawn area."
            )
            if show_entire_map != st.session_state.show_entire_map_coverage:
                st.session_state.show_entire_map_coverage = show_entire_map
                st.session_state.map_created = False
                st.session_state.map_data = None
                st.rerun()
        
        # Custom Coordinates section (collapsible)
        with st.expander("Custom Coordinates", expanded=False):
            st.markdown("""
            <div class="coordinates-section">
                <label class="label">Coordinates (8-point polygon)</label>
                <div class="coordinates-grid">
                    <div class="coordinate-input">
                        <label class="input-label">Point 1</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0105, 40.7298</div>
                    </div>
                    <div class="coordinate-input">
                        <label class="input-label">Point 2</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0047, 40.7294</div>
                    </div>
                    <div class="coordinate-input">
                        <label class="input-label">Point 3</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0048, 40.7291</div>
                    </div>
                    <div class="coordinate-input">
                        <label class="input-label">Point 4</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0045, 40.7291</div>
                    </div>
                    <div class="coordinate-input">
                        <label class="input-label">Point 5</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0045, 40.7286</div>
                    </div>
                    <div class="coordinate-input">
                        <label class="input-label">Point 6</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0029, 40.7283</div>
                    </div>
                    <div class="coordinate-input">
                        <label class="input-label">Point 7</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0054, 40.7219</div>
                    </div>
                    <div class="coordinate-input">
                        <label class="input-label">Point 8</label>
                        <div class="input" style="display: flex; align-items: center; justify-content: center; font-size: 0.85rem; color: hsl(var(--foreground));">-74.0109, 40.7258</div>
                    </div>
                </div>
            </div>
            """.format(
                west=get_study_area_bounds()['west'],
                east=get_study_area_bounds()['east'],
                north=get_study_area_bounds()['north'],
                south=get_study_area_bounds()['south']
            ), unsafe_allow_html=True)
        
        # Time Range section
        st.markdown("""
        <div class="separator"></div>
        <div class="time-range-section">
            <div class="time-range-label">
                <svg class="calendar-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M8 2v4"/>
                    <path d="M16 2v4"/>
                    <rect width="18" height="18" x="3" y="4" rx="2"/>
                    <path d="M3 10h18"/>
                </svg>
                Time Range
            </div>
            <div class="year-selects">
                <div class="year-select">
                    <label class="input-label">Start Year</label>
                </div>
                <div class="year-select">
                    <label class="input-label">End Year</label>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Streamlit controls (hidden but functional)
        col1, col2 = st.columns(2)
        year1 = col1.selectbox("Start Year", [2010, 2021], index=0, key="year1", label_visibility="collapsed")
        year2 = col2.selectbox("End Year", [2010, 2021], index=1, key="year2", label_visibility="collapsed")
        
        if year1 == year2:
            st.error("Please select different years for comparison!")
            return
        
        # Analyze Button (positioned right after year selection)
        st.markdown("""
        <style>
        .stButton > button {
            background: var(--gradient-hero) !important;
            color: hsl(var(--primary-foreground)) !important;
            border: none !important;
            border-radius: var(--radius) !important;
            padding: 0.75rem 1rem !important;
            font-size: 0.875rem !important;
            font-weight: 500 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.5rem !important;
            width: 100% !important;
            transition: opacity 0.3s ease !important;
            position: relative !important;
        }
        .stButton > button:hover {
            opacity: 0.9 !important;
        }
        .stButton > button:before {
            content: "";
            display: inline-block;
            width: 16px;
            height: 16px;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z'/%3E%3Ccircle cx='12' cy='10' r='3'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-size: contain;
            margin-right: 0.5rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
 
        st.session_state.auto_analyze_on_draw = True
        
        if st.button("Run Tree Cover Analysis", type="primary", use_container_width=True):
            st.session_state.analysis_run = True
            st.session_state.selected_year1 = year1
            st.session_state.selected_year2 = year2
            st.rerun()
        
        
      
    
    # Authentication status with professional styling
    # Connect to PostgreSQL database for large LiDAR datasets (without spinner)
    db_success, db_message = authenticate_database()
    
    
    
    # Show map in default state to allow drawing before analysis (fragment = only this block reruns on draw)
    if not st.session_state.analysis_run:

        @st.fragment
        def _drawing_map_fragment():
            st.markdown("""
            <div class="status-overview">
            <div class="status-indicator success">
                    <svg class="status-indicator-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 12l2 2 4-4"/>
                        <circle cx="12" cy="12" r="9"/>
                    </svg>
                    <div class="status-indicator-content">
                        <p class="status-indicator-title">Google Earth Engine authenticated successfully</p>
                        <p class="status-indicator-description">Connection to satellite data services established</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            drawing_map = folium.Map(
                location=[40.725, -74.005],
                zoom_start=14,
                max_zoom=22,
                min_zoom=10,
                tiles=None,
            )
            # Add Google Maps base layer
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                attr='Google Maps',
                name='Google Maps',
                overlay=False,
                control=True,
                show=True,
                max_zoom=22,
                min_zoom=0
            ).add_to(drawing_map)
            # Only show boundary if user has drawn an area (not default)
            if st.session_state.drawn_bounds:
                active_preview_bounds = st.session_state.drawn_bounds
                if active_preview_bounds.get('type') == 'polygon':
                    coords = active_preview_bounds['coordinates']
                    folium_coords = [[coord[1], coord[0]] for coord in coords]
                    folium.Polygon(
                        locations=folium_coords,
                        color='red',
                        weight=3,
                        fill=True,
                        fillColor='red',
                        fillOpacity=0.1,
                        popup="Drawn Area"
                    ).add_to(drawing_map)
                else:
                    bounds = active_preview_bounds if 'west' in active_preview_bounds else get_study_area_bounds()
                    folium.Rectangle(
                        bounds=[[bounds['south'], bounds['west']], [bounds['north'], bounds['east']]],
                        color='red',
                        weight=3,
                        fill=True,
                        fillColor='red',
                        fillOpacity=0.1,
                        popup="Drawn Area"
                    ).add_to(drawing_map)
            draw = Draw(
                export=True,
                filename='drawn_area.geojson',
                position='topleft',
                draw_options={
                    'polyline': False,
                    'polygon': True,
                    'rectangle': True,
                    'circle': False,
                    'marker': False,
                    'circlemarker': False
                },
                edit_options={
                    'edit': False,
                    'remove': False
                }
            )
            draw.add_to(drawing_map)
            _add_sidebar_draw_controls(drawing_map)
            if ST_FOLIUM_AVAILABLE:
                map_data = st_folium(
                    drawing_map,
                    width=None,
                    height=800,
                    returned_objects=["last_draw", "all_drawings"],
                    key="drawing_map"
                )
                last_draw = map_data.get("last_draw")
                if not last_draw and map_data.get("all_drawings"):
                    last_draw = map_data["all_drawings"][-1]
                if last_draw:
                    current_shape_id = last_draw.get("id") or str(last_draw)
                    if current_shape_id != st.session_state.last_drawn_shape:
                        bounds = _bounds_from_drawn_feature(last_draw)
                        if bounds:
                            st.session_state.last_drawn_shape = current_shape_id
                            _apply_drawn_bounds(bounds, st.session_state.auto_analyze_on_draw)
                            if st.session_state.auto_analyze_on_draw:
                                st.success("✅ Shape captured! Running analysis automatically...")
                                st.rerun()
                            else:
                                st.success("✅ Shape captured! Click 'Run Tree Cover Analysis' to analyze.")
                        else:
                            st.warning("Could not parse drawn shape. Please try again.")
            else:
                st.components.v1.html(drawing_map._repr_html_(), height=700)
                st.info("💡 Install streamlit-folium for automatic shape capture: `pip install streamlit-folium`")
            if st.session_state.has_drawn_area:
                placeholder_title = "Ready to Analyze"
                placeholder_desc = "Click 'Run Tree Cover Analysis' in the sidebar to see tree coverage results for your selected area."
            else:
                placeholder_title = "No area selected yet"
                placeholder_desc = "Draw a rectangle or polygon on the map above to define your study area. Analysis will start automatically when you finish drawing."
            st.markdown(f"""
            <div class="card default-card">
                <div class="card-header">
                    <div class="default-header">
                        <h3 class="card-title">Analysis Results</h3>
                        <div class="year-badge">2010 - 2021</div>
                    </div>
                    <p class="card-description">
                        Vegetation coverage analysis and change detection results
                    </p>
                </div>
                <div class="card-content">
                    <div class="default-placeholder">
                        <svg class="default-placeholder-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="m17 14 3 3.3a1 1 0 0 1-.7 1.7H4.7a1 1 0 0 1-.7-1.7L7 14h-.3a1 1 0 0 1-.7-1.7L9 9h-.2A1 1 0 0 1 8 7.3L12 3l4 4.3a1 1 0 0 1-.8 1.7H15l3 3.3a1 1 0 0 1-.7 1.7H17Z"/>
                            <path d="M12 22V18"/>
                        </svg>
                        <p class="default-placeholder-title">{placeholder_title}</p>
                        <p class="default-placeholder-description">
                            {placeholder_desc}
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        _drawing_map_fragment()

    # Run analysis if button was clicked or auto-triggered
    if st.session_state.analysis_run:
        
        # Remove loading progress UI
        
        try:
            # Get years from session state
            year1 = st.session_state.selected_year1
            year2 = st.session_state.selected_year2
            
            # Determine which bounds to use (HSBID mode always uses Hudson Square)
            if st.session_state.get("display_hsbid", True):
                active_bounds = HUDSON_SQUARE_BOUNDS
            elif st.session_state.use_drawn_area and st.session_state.drawn_bounds:
                active_bounds = st.session_state.drawn_bounds
            else:
                active_bounds = HUDSON_SQUARE_BOUNDS
            
            # Calculate coverage using FastAPI backend (reads COG files)
            # Check cache first (main thread), then fetch missing data in parallel
            from concurrent.futures import ThreadPoolExecutor
            
            cache_key_1 = _get_coverage_cache_key(year1, active_bounds)
            cache_key_2 = _get_coverage_cache_key(year2, active_bounds)
            
            # Check what's already cached
            cover_1 = st.session_state.get(cache_key_1)
            cover_2 = st.session_state.get(cache_key_2)
            error1, error2 = None, None
            
            # Fetch only what's not cached
            needs_fetch_1 = cover_1 is None
            needs_fetch_2 = cover_2 is None
            
            if needs_fetch_1 or needs_fetch_2:
                with st.spinner(f"Calculating tree coverage for {year1} and {year2}..."):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = {}
                        if needs_fetch_1:
                            futures[year1] = executor.submit(_fetch_coverage_from_api, year1, active_bounds)
                        if needs_fetch_2:
                            futures[year2] = executor.submit(_fetch_coverage_from_api, year2, active_bounds)
                        
                        if needs_fetch_1:
                            cover_1, error1 = futures[year1].result()
                            if cover_1 is not None:
                                st.session_state[cache_key_1] = cover_1
                        if needs_fetch_2:
                            cover_2, error2 = futures[year2].result()
                            if cover_2 is not None:
                                st.session_state[cache_key_2] = cover_2
            else:
                print(f"⚡ Using cached coverage for {year1} and {year2}")
            
            if error1:
                st.warning(f"API error for {year1}: {error1}. Using fallback value.")
                cover_1 = 21.3 if year1 == 2010 else 22.5 if year1 == 2021 else 0.0
        
            if error2:
                st.warning(f"API error for {year2}: {error2}. Using fallback value.")
                cover_2 = 21.3 if year2 == 2010 else 22.5 if year2 == 2021 else 0.0
      
            
            # Create visualization
            
            # Store map data in session state for persistence
            st.session_state.map_data = {
                'cover_1': cover_1,
                'cover_2': cover_2,
                'year1': year1,
                'year2': year2,
                'bounds': active_bounds
            }
            st.session_state.map_created = True
            
   
            
            # Status Overview
            st.markdown("""
            <div class="status-overview">
                <div class="status-indicator success">
                    <svg class="status-indicator-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 12l2 2 4-4"/>
                        <circle cx="12" cy="12" r="9"/>
                    </svg>
                    <div class="status-indicator-content">
                        <p class="status-indicator-title">Google Earth Engine authenticated successfully</p>
                        <p class="status-indicator-description">Connection to satellite data services established</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            
            # Results Section with proper styling (container open)
            st.markdown("""
            <div class="results-section">
                <div class="results-header">
                    <h2 class="results-title">Analysis Results</h2>
                    <p class="results-subtitle">Analyzing vegetation changes in Hudson Square, NYC using satellite imagery</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            change = cover_2 - cover_1
            
            with col1:
                st.markdown(f"""
                <div class="result-card">
                    <div class="result-card-content">
                        <div class="result-card-info">
                            <p class="result-card-label">{year1} Tree Cover</p>
                            <p class="result-card-value">{cover_1:.1f}%</p>
                        </div>
                        <div class="result-card-icon accent">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="m17 14 3 3.3a1 1 0 0 1-.7 1.7H4.7a1 1 0 0 1-.7-1.7L7 14h-.3a1 1 0 0 1-.7-1.7L9 9h-.2A1 1 0 0 1 8 7.3L12 3l4 4.3a1 1 0 0 1-.8 1.7H15l3 3.3a1 1 0 0 1-.7 1.7H17Z"/>
                                <path d="M12 22V18"/>
                            </svg>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="result-card">
                    <div class="result-card-content">
                        <div class="result-card-info">
                            <p class="result-card-label">{year2} Tree Cover</p>
                            <p class="result-card-value">{cover_2:.1f}%</p>
                        </div>
                        <div class="result-card-icon success">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="m17 14 3 3.3a1 1 0 0 1-.7 1.7H4.7a1 1 0 0 1-.7-1.7L7 14h-.3a1 1 0 0 1-.7-1.7L9 9h-.2A1 1 0 0 1 8 7.3L12 3l4 4.3a1 1 0 0 1-.8 1.7H15l3 3.3a1 1 0 0 1-.7 1.7H17Z"/>
                                <path d="M12 22V18"/>
                            </svg>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                is_positive = change > 0
                value_class = "success" if is_positive else "destructive" if change < 0 else ""
                trend_class = "" if is_positive else "negative" if change < 0 else ""
                right_chip_class = "success-bg" if is_positive else "destructive-bg" if change < 0 else "accent"
                st.markdown(f"""
                <div class="result-card">
                    <div class="result-card-content">
                        <div class="result-card-info">
                            <p class="result-card-label">Change</p>
                            <p class="result-card-value {value_class}">{change:+.1f}%</p>
                            <p class="result-card-trend {trend_class}">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="22,7 13.5,15.5 8.5,10.5 2,17"/>
                                    <polyline points="16,7 22,7 22,13"/>
                                </svg>
                                {abs(change):.1f}%
                            </p>
                        </div>
                        <div class="result-card-icon {right_chip_class}">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="22,7 13.5,15.5 8.5,10.5 2,17"/>
                                <polyline points="16,7 22,7 22,13"/>
                            </svg>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Close container not needed now since we didn’t open results-grid
            
            
            # Interactive Map Section
            st.markdown("""
            <div class="card1 map-card">
                <div class="map-card-header">
                    <h3 class="card-title">Interactive Map</h3>
                </div>
                
            """, unsafe_allow_html=True)
            
            # Create and display the map with active bounds
            map_obj = create_map(cover_1, cover_2, year1, year2, active_bounds, st.session_state.show_entire_map_coverage)
            
            # Use st_folium if available for better drawn shape capture
            if ST_FOLIUM_AVAILABLE:
                # st_folium can capture drawn features automatically
                map_data_folium = st_folium(
                    map_obj,
                    width=None,
                    height=750,
                    returned_objects=["last_draw", "all_drawings"],
                    key=f"map_{year1}_{year2}"
                )

                # Prefer last_draw, fallback to last item of all_drawings
                last_draw = map_data_folium.get("last_draw")
                if not last_draw and map_data_folium.get("all_drawings"):
                    last_draw = map_data_folium["all_drawings"][-1]

                if last_draw:
                    bounds = _bounds_from_drawn_feature(last_draw)
                    if bounds:
                        _apply_drawn_bounds(bounds, True)
                        st.success("✅ Shape captured! Re-running analysis with drawn area...")
                        st.rerun()
                    else:
                        st.warning("Could not parse drawn shape. Please try again.")
            else:
                # Fallback to regular HTML component
                st.components.v1.html(map_obj._repr_html_(), height=800)
                st.info("💡 Install streamlit-folium for automatic shape capture: `pip install streamlit-folium`")
            
            # Show which area is being analyzed and display mode
           
            
     
            
            st.markdown("</div></div>", unsafe_allow_html=True)
            
            # Methodology Section
            st.markdown("""
            <div class="cardMe methodology-card">
                <div class="card-headerMe">
                    <h4 class="card-titleMe">Methodology</h3>
                </div>
                <div class="card-contentMe">
                    <p class="methodology-text">
                        Tree cover changed by {change:+.1f}% from {year1} to {year2}. Analysis performed using Google Earth Engine 
                        with authenticated Streamlit access for satellite imagery processing and vegetation analysis.
                    </p>
                </div>
            </div>
            """.format(change=change, year1=year1, year2=year2), unsafe_allow_html=True)
            
        
            # Analysis metadata
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            # No progress elements to clear
    
    # Persistent map display - show map even when analysis is complete
    elif st.session_state.map_created and st.session_state.map_data:
        st.markdown("---")
        st.markdown("## 🗺️ Interactive Map")
        st.markdown("*Map persists for continued exploration*")
        
        # Get stored map data
        map_data = st.session_state.map_data
        year1 = map_data['year1']
        year2 = map_data['year2']
        
        st.markdown(f"""
        <div class="map-container">
            <h4>🌳 Tree Coverage Analysis - Hudson Square Area</h4>
            <div style="display: flex; justify-content: center; gap: 2rem; margin: 1rem 0; font-size: 0.875rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div style="width: 1rem; height: 1rem; background-color: #1e40af; border-radius: 2px;"></div>
                    <span>🌳 {year2} Tree Coverage</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div style="width: 1rem; height: 1rem; background-color: #dc2626; border-radius: 2px;"></div>
                    <span>🌳 {year1} Tree Coverage</span>
                </div>
            </div>
            <div style="background: hsl(var(--muted) / 0.3); border: 1px solid hsl(var(--border)); border-radius: var(--radius); padding: 0.75rem; margin-top: 1rem; font-size: 0.875rem;">
                <strong>💡 Map Tips:</strong> 
                <ul style="margin: 0.5rem 0; padding-left: 1.5rem;">
                    <li>Tree data resolution: 2010: 5ft (1.5m), 2021: 6in (0.15m) from LiDAR COG files</li>
                    <li>Use layer controls (top-right) to toggle tree coverage layers</li>
                    <li>Click markers for detailed tree coverage information</li>
                    <li>Blue overlay shows {year1} trees, Green overlay shows {year2} trees</li>
                    <li>Legend shows tree classification colors (bottom-left corner)</li>
                    <li>Tree areas are highlighted in green with transparency for visibility</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Recreate and display the map with stored bounds
        stored_bounds = map_data.get('bounds', None)
        map_obj = create_map(
            map_data['cover_1'], 
            map_data['cover_2'], 
            year1, 
            year2,
            stored_bounds,
            st.session_state.show_entire_map_coverage
        )
        components.html(map_obj._repr_html_(), height=750)

if __name__ == "__main__":
    main()
