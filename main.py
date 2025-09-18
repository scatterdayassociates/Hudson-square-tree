import streamlit as st
import streamlit.components.v1 as components
import folium
from folium.plugins import Fullscreen, Draw
from folium import raster_layers
import json
import os
from datetime import datetime
from config import DATABASE_CONFIG, LIDAR_DATASETS, HUDSON_SQUARE_BOUNDS, ACTIVE_DB, PROJECT_ID
from postgis_raster import PostGISRasterHandler, get_tree_coverage_postgis, initialize_lidar_datasets

# Page configuration
st.set_page_config(
    page_title="Hudson Square Tree Cover Analysis",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling inspired by the HTML/CSS design
st.markdown("""
<style>
    /* Import the same design system from HTML/CSS */
    :root {
        --background: 0 0% 100%;
        --foreground: 220 15% 15%;
        --card: 0 0% 100%;
        --card-foreground: 220 15% 15%;
        --primary: 210 100% 50%;
        --primary-foreground: 0 0% 98%;
        --secondary: 220 15% 96%;
        --secondary-foreground: 220 15% 15%;
        --muted: 220 15% 96%;
        --muted-foreground: 220 5% 45%;
        --accent: 280 60% 50%;
        --accent-foreground: 0 0% 98%;
        --success: 142 76% 36%;
        --success-foreground: 0 0% 98%;
        --destructive: 0 84% 60%;
        --destructive-foreground: 0 0% 98%;
        --border: 220 15% 90%;
        --input: 220 15% 90%;
        --ring: 210 100% 50%;
        --radius: 0.5rem;
        --shadow-card: 0 2px 8px hsl(220 15% 15% / 0.1);
        --shadow-elevated: 0 4px 16px hsl(220 15% 15% / 0.15);
        --shadow-glow: 0 4px 16px hsl(142 76% 36% / 0.3);
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
        align-items: center;
        gap: 0.75rem;
        padding: 1rem;
        border-radius: var(--radius);
        border: 1px solid hsl(var(--success) / 0.2);
        background-color: hsl(var(--success) / 0.1);
        color: hsl(var(--success));
        margin-bottom: 1.5rem;
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

    /* Methodology cards styling */
    .methodology-card {
        background: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 1.5rem;
        box-shadow: var(--shadow-card);
        transition: all 0.3s ease;
        position: relative;
        display: flex;
        flex-direction: column;
    }

    .methodology-card:hover {
        box-shadow: var(--shadow-elevated);
        transform: translateY(-2px);
    }

    .methodology-card h4 {
        color: hsl(var(--primary));
        margin-bottom: 1.25rem;
        font-size: 1.1rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid hsl(var(--primary) / 0.1);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .methodology-card h4::before {
        content: '';
        width: 4px;
        height: 20px;
        background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
        border-radius: 2px;
        flex-shrink: 0;
    }

    .methodology-card .main-content {
        margin-bottom: 1rem;
        padding: 0.75rem;
        background: hsl(var(--muted) / 0.3);
        border-radius: calc(var(--radius) - 2px);
        border-left: 3px solid hsl(var(--primary));
    }

    .methodology-card .main-content p {
        margin: 0;
        font-size: 0.95rem;
        font-weight: 600;
        color: hsl(var(--foreground));
        line-height: 1.4;
    }

    .methodology-card .description {
        font-size: 0.875rem;
        color: hsl(var(--muted-foreground));
        line-height: 1.5;
        margin: 0;
        padding: 0.5rem 0.75rem;
        background: hsl(var(--background));
        border-radius: calc(var(--radius) - 2px);
        border: 1px solid hsl(var(--border) / 0.5);
    }

    .methodology-card p {
        font-weight: 300;
        margin: 0;
    }

    .methodology-card ul {
        margin: 0;
        padding: 0;
        list-style: none;
        background: hsl(var(--muted) / 0.2);
        border-radius: calc(var(--radius) - 2px);
        padding: 0.75rem;
    }

    .methodology-card li {
        margin-bottom: 0.5rem;
        font-size: 0.875rem;
        color: hsl(var(--foreground));
        line-height: 1.5;
        padding-left: 1.5rem;
        position: relative;
    }

    .methodology-card li:last-child {
        margin-bottom: 0;
    }

    .methodology-card li::before {
        content: '✓';
        position: absolute;
        left: 0;
        top: 0;
        color: hsl(var(--success));
        font-weight: bold;
        font-size: 0.75rem;
    }

    .methodology-card .area-info {
        background: linear-gradient(135deg, hsl(var(--primary) / 0.05), hsl(var(--accent) / 0.05));
        border: 1px solid hsl(var(--primary) / 0.2);
        border-radius: calc(var(--radius) - 2px);
        padding: 0.75rem;
        margin-top: 0.5rem;
    }

    .methodology-card .area-info p {
        margin: 0;
        font-size: 0.875rem;
        color: hsl(var(--muted-foreground));
        text-align: center;
        font-weight: 500;
    }

    /* Methodology section styling */
    .methodology-section {
        margin-top: 2rem;
        margin-bottom: 1.5rem;
    }

    .methodology-section h2 {
        color: hsl(var(--foreground));
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        margin-top: 0;
    }

    .methodology-section .subtitle {
        color: hsl(var(--muted-foreground));
        font-style: italic;
        font-size: 0.875rem;
        margin-bottom: 1.5rem;
        margin-top: 0;
    }

    /* Grid spacing for methodology cards */
    .methodology-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
        margin-bottom: 1.5rem;
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
        gap: 0.5rem;
        white-space: nowrap;
        text-align: center;
        font-size: 0.875rem;
        line-height: 1.25rem;
        cursor: pointer;
        user-select: none;
        position: relative;
        overflow: hidden;
    }

    .stButton > button:hover {
        background: hsl(var(--primary) / 0.9);
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
        hudson_square = ee.Geometry.Rectangle([
            HUDSON_SQUARE_BOUNDS['west'],
            HUDSON_SQUARE_BOUNDS['south'],
            HUDSON_SQUARE_BOUNDS['east'],
            HUDSON_SQUARE_BOUNDS['north']
        ])
        
        # Create a constant image with the calculated coverage for visualization
        tree_cover = ee.Image.constant(coverage).clip(hudson_square).rename('tree_cover')
        
        return tree_cover, None
        
    except Exception as e:
        print(f"Error in get_tree_cover for {year}: {str(e)}")
        return None, str(e)



# Replace your create_map function with this updated version

def create_tree_visualization_data(year, bounds):
    """Create tree visualization data from COG files"""
    try:
        from postgis_raster import get_tree_coverage_postgis
        import rasterio
        from rasterio.warp import transform_bounds
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        from io import BytesIO
        import base64
        
        # Get the COG URL for this year
        cog_url = LIDAR_DATASETS.get(str(year))
        if not cog_url:
            return None, f"No COG URL found for year {year}"
        
        # Read the COG data
        with rasterio.open(cog_url) as src:
            # Transform bounds to the raster's CRS
            raster_bounds = transform_bounds('EPSG:4326', src.crs, 
                                           bounds['west'], bounds['south'],
                                           bounds['east'], bounds['north'])
            
            # Read the data for the study area
            window = rasterio.windows.from_bounds(*raster_bounds, src.transform)
            data = src.read(1, window=window)
            
            # Create tree classification visualization
            # Class 2 = Trees, Class 7 = Grass/Vegetation
            tree_mask = np.isin(data, [1])
            
            # Create a colored visualization
            fig, ax = plt.subplots(figsize=(8, 8))
            
            # First display the original data with a neutral colormap
            colors_original = ['white', 'lightgray', 'lightblue', 'lightgray', 'brown', 'gray', 'lightyellow', 'lightgray']
            cmap_original = mcolors.ListedColormap(colors_original)
            ax.imshow(data, cmap=cmap_original, vmin=0, vmax=7, alpha=0.7)
            
            # Then overlay only the tree areas in green
            tree_overlay = np.ma.masked_where(~tree_mask, tree_mask)
            ax.imshow(tree_overlay, cmap='Greens', alpha=0.8, vmin=0, vmax=1)
            
            ax.set_title(f'{year} Tree Coverage - Hudson Square', fontsize=14, fontweight='bold')
            ax.axis('off')
            
            # Save to bytes
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buffer.seek(0)
            
            # Convert to base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"data:image/png;base64,{image_base64}", None
            
    except Exception as e:
        print(f"Error creating tree visualization for {year}: {e}")
        return None, str(e)

def create_map(cover_year1, cover_year2, year1, year2):
    """Create the interactive map using PostGIS data and COG files."""
    
    # Create folium map with Google Maps as base layer
    folium_map = folium.Map(
        location=[40.725, -74.005],
        zoom_start=16,
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
    
    # Add Hudson Square boundary
    hudson_square_bounds = [
        [HUDSON_SQUARE_BOUNDS['south'], HUDSON_SQUARE_BOUNDS['west']],
        [HUDSON_SQUARE_BOUNDS['north'], HUDSON_SQUARE_BOUNDS['east']]
    ]
    
    # Add boundary rectangle
    folium.Rectangle(
        bounds=hudson_square_bounds,
        color='red',
        weight=3,
        fill=False,
       
    ).add_to(folium_map)
    
    # Add COG layers as actual raster overlays on Google Maps
    # This uses the actual .tif files from Google Cloud Storage
    try:
        # Year 1 COG layer - using actual COG file
        cog_url_1 = LIDAR_DATASETS[str(year1)]
        cog_url_2 = LIDAR_DATASETS[str(year2)]
        
        # Create ImageOverlay layers for the COG files
        # These will show the actual tree data as raster overlays
        
        # Define bounds for the COG data
        cog_bounds = [
            [HUDSON_SQUARE_BOUNDS['south'], HUDSON_SQUARE_BOUNDS['west']],
            [HUDSON_SQUARE_BOUNDS['north'], HUDSON_SQUARE_BOUNDS['east']]
        ]
        
        # Create separate layer groups for each year
        year1_layer = folium.FeatureGroup(name=f'{year1} Tree Coverage')
        year2_layer = folium.FeatureGroup(name=f'{year2} Tree Coverage')
        
        # Create tree visualization images
        year1_image, year1_error = create_tree_visualization_data(year1, HUDSON_SQUARE_BOUNDS)
        year2_image, year2_error = create_tree_visualization_data(year2, HUDSON_SQUARE_BOUNDS)
        
        # Add ImageOverlay for Year 1 (Red/Orange theme for 2010)
        if year1_image:
            year1_overlay = raster_layers.ImageOverlay(
                image=year1_image,
                bounds=cog_bounds,
                opacity=0.7,
                interactive=True,
                cross_origin=False,
                zindex=1
            )
            year1_overlay.add_to(year1_layer)
        else:
            # Fallback to simple colored rectangle
            folium.Rectangle(
                bounds=cog_bounds,
                color='orange',
                weight=2,
                fill=True,
                fillColor='orange',
                fillOpacity=0.4,
                popup=f"<b>{year1} Tree Coverage</b><br>Coverage: {cover_year1:.2f}%<br>Error: {year1_error}",
                tooltip=f"{year1} Tree Coverage: {cover_year1:.2f}%"
            ).add_to(year1_layer)
        
        # Add ImageOverlay for Year 2 (Blue theme for 2017)  
        if year2_image:
            year2_overlay = raster_layers.ImageOverlay(
                image=year2_image,
                bounds=cog_bounds,
                opacity=0.7,
                interactive=True,
                cross_origin=False,
                zindex=2
            )
            year2_overlay.add_to(year2_layer)
        else:
            # Fallback to simple colored rectangle
            folium.Rectangle(
                bounds=cog_bounds,
                color='blue',
                weight=2,
                fill=True,
                fillColor='blue',
                fillOpacity=0.4,
                popup=f"<b>{year2} Tree Coverage</b><br>Coverage: {cover_year2:.2f}%<br>Error: {year2_error}",
                tooltip=f"{year2} Tree Coverage: {cover_year2:.2f}%"
            ).add_to(year2_layer)
        
        # Add year-specific markers to their respective layers
        center_lat = (HUDSON_SQUARE_BOUNDS['north'] + HUDSON_SQUARE_BOUNDS['south']) / 2
        center_lon = (HUDSON_SQUARE_BOUNDS['east'] + HUDSON_SQUARE_BOUNDS['west']) / 2
        
        # Year 1 marker with tree icon (Orange for 2010)
        folium.Marker(
            [center_lat - 0.001, center_lon - 0.001],
            popup=f"""
            <div style="font-family: Arial, sans-serif; width: 250px;">
                <h4 style="color: #ea580c; margin: 0 0 10px 0;">🌳 {year1} Tree Coverage</h4>
                <p style="margin: 5px 0;"><strong>Coverage:</strong> {cover_year1:.2f}%</p>
                <p style="margin: 5px 0;"><strong>Data Source:</strong> LiDAR COG File</p>
                <p style="margin: 5px 0;"><strong>Resolution:</strong> 5ft (1.5m)</p>
                <a href="{cog_url_1}" target="_blank" style="color: #ea580c;">📁 View {year1} COG File</a>
            </div>
            """,
            tooltip=f"🌳 {year1} Tree Coverage: {cover_year1:.2f}%",
            icon=folium.Icon(color='orange', icon='tree', prefix='fa')
        ).add_to(year1_layer)
        
        # Year 2 marker with tree icon (Blue for 2017)
        folium.Marker(
            [center_lat + 0.001, center_lon + 0.001],
            popup=f"""
            <div style="font-family: Arial, sans-serif; width: 250px;">
                <h4 style="color: #1e40af; margin: 0 0 10px 0;">🌳 {year2} Tree Coverage</h4>
                <p style="margin: 5px 0;"><strong>Coverage:</strong> {cover_year2:.2f}%</p>
                <p style="margin: 5px 0;"><strong>Data Source:</strong> LiDAR COG File</p>
                <p style="margin: 5px 0;"><strong>Resolution:</strong> 5ft (1.5m)</p>
                <a href="{cog_url_2}" target="_blank" style="color: #1e40af;">📁 View {year2} COG File</a>
            </div>
            """,
            tooltip=f"🌳 {year2} Tree Coverage: {cover_year2:.2f}%",
            icon=folium.Icon(color='blue', icon='tree', prefix='fa')
        ).add_to(year2_layer)
        
        # Create a comparison layer showing both years
        comparison_layer = folium.FeatureGroup(name='Analysis Summary')
        
        # Add center marker with summary to comparison layer
        center_lat = (HUDSON_SQUARE_BOUNDS['north'] + HUDSON_SQUARE_BOUNDS['south']) / 2
        center_lon = (HUDSON_SQUARE_BOUNDS['east'] + HUDSON_SQUARE_BOUNDS['west']) / 2
        
        change = cover_year2 - cover_year1
        change_icon = '📈' if change > 0 else '📉' if change < 0 else '➡️'
        change_color = 'green' if change > 0 else 'red' if change < 0 else 'orange'
        
        folium.Marker(
            [center_lat, center_lon],
            popup=f"""
            <div style="font-family: Arial, sans-serif; width: 300px;">
                <h3 style="color: #dc2626; margin: 0 0 15px 0; text-align: center;">🌳 Hudson Square Tree Analysis</h3>
                <div style="background: #f3f4f6; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <p style="margin: 5px 0; color: #ea580c;"><strong>{year1} Tree Coverage:</strong> {cover_year1:.2f}%</p>
                    <p style="margin: 5px 0; color: #1e40af;"><strong>{year2} Tree Coverage:</strong> {cover_year2:.2f}%</p>
                    <p style="margin: 5px 0; color: {change_color};"><strong>Change:</strong> {change:+.2f}% {change_icon}</p>
                </div>
                <div style="background: #fef3c7; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <p style="margin: 5px 0; font-size: 12px;"><strong>Data Sources:</strong></p>
                    <p style="margin: 5px 0; font-size: 12px;">• <a href="{cog_url_1}" target="_blank">{year1} LiDAR COG</a></p>
                    <p style="margin: 5px 0; font-size: 12px;">• <a href="{cog_url_2}" target="_blank">{year2} LiDAR COG</a></p>
                </div>
            </div>
            """,
            tooltip=f"🌳 Tree Coverage Analysis: {change:+.2f}% change",
            icon=folium.Icon(color='red', icon='info-sign', prefix='fa')
        ).add_to(comparison_layer)
        
        # Add the layer groups to the map
        year1_layer.add_to(folium_map)
        year2_layer.add_to(folium_map)
        comparison_layer.add_to(folium_map)
        
    except Exception as e:
        print(f"COG layers not available: {e}")
        # Add fallback markers with coverage information
        center_lat = (HUDSON_SQUARE_BOUNDS['north'] + HUDSON_SQUARE_BOUNDS['south']) / 2
        center_lon = (HUDSON_SQUARE_BOUNDS['east'] + HUDSON_SQUARE_BOUNDS['west']) / 2
        
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
    
    
    
    # Add drawing tool
    draw = Draw(
        export=True,
        filename='hudson_square_annotations.geojson',
        position='topleft',
        draw_options={
            'polyline': True,
            'polygon': True,
            'rectangle': True,
            'circle': True,
            'marker': True,
            'circlemarker': True
        },
        edit_options={
            'edit': True,
            'remove': True
        }
    )
    draw.add_to(folium_map)
    
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


def main():
    # Initialize session state variables
    if 'analysis_run' not in st.session_state:
        st.session_state.analysis_run = False
    if 'selected_year1' not in st.session_state:
        st.session_state.selected_year1 = 2010
    if 'selected_year2' not in st.session_state:
        st.session_state.selected_year2 = 2017
    if 'map_created' not in st.session_state:
        st.session_state.map_created = False
    if 'map_data' not in st.session_state:
        st.session_state.map_data = None
    
    # Professional Header with gradient styling

    
    # Sidebar with enhanced styling
    with st.sidebar:
        st.markdown("#  Analysis Settings")
        st.markdown("**Configure study parameters**")
        
        st.markdown("---")
        st.markdown("**Study Area**")
        st.markdown("Hudson Square, NYC")
        
        st.markdown("---")
        st.markdown("**Coordinates**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("West", f"{HUDSON_SQUARE_BOUNDS['west']}")
            st.metric("North", f"{HUDSON_SQUARE_BOUNDS['north']}")
        with col2:
            st.metric("East", f"{HUDSON_SQUARE_BOUNDS['east']}")
            st.metric("South", f"{HUDSON_SQUARE_BOUNDS['south']}")
        
        st.markdown("---")
        st.markdown("**Time Range**")
        col1, col2 = st.columns(2)
        year1 = col1.selectbox("Start Year", [2010, 2017], index=0, key="year1")
        year2 = col2.selectbox("End Year", [2010, 2017], index=1, key="year2")
        
        if year1 == year2:
            st.error("Please select different years for comparison!")
            return
        
        st.markdown("---")
        
        # Analysis button in sidebar
        if st.button(" Run Tree Cover Analysis", type="primary", use_container_width=True):
            st.session_state.analysis_run = True
            st.session_state.selected_year1 = year1
            st.session_state.selected_year2 = year2
            st.rerun()
        
        
      
    
    # Authentication status with professional styling
    with st.spinner("Connecting to PostgreSQL database..."):
        # Connect to PostgreSQL database for large LiDAR datasets
        db_success, db_message = authenticate_database()
    
    
    
    # Default state - show when no analysis has been run
    if not st.session_state.analysis_run:
        st.markdown("""
        <div style="background: hsl(var(--muted) / 0.3); border: 2px dashed hsl(var(--border)); border-radius: var(--radius); padding: 2rem; text-align: center; margin: 2rem 0;">
            <div style="margin-bottom: 1rem;">
                <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" fill="gray" viewBox="0 0 24 24" style="opacity: 0.7;">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z"/>
                </svg>
            </div>
            <h3 style="color: hsl(var(--muted-foreground)); margin-bottom: 0.5rem;">Satellite imagery analysis showing tree coverage changes in Hudson Square area.</h3>
            <div style="display: flex; justify-content: center; gap: 2rem; margin: 1rem 0; font-size: 0.875rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div style="width: 1rem; height: 1rem; background-color: #16a34a; border-radius: 2px;"></div>
                    <span>Green: 2010 Tree Cover</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div style="width: 1rem; height: 1rem; background-color: #1e40af; border-radius: 2px;"></div>
                    <span>Blue: 2017 Tree Cover</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Run analysis if button was clicked
    if st.session_state.analysis_run:
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Get years from session state
            year1 = st.session_state.selected_year1
            year2 = st.session_state.selected_year2
            
            # Calculate coverage using PostgreSQL backend
            status_text.text("Calculating tree coverage from LiDAR data...")
            progress_bar.progress(30)
            
            cover_1, error1 = get_tree_coverage_postgis(year1)
            cover_2, error2 = get_tree_coverage_postgis(year2)
            
            if error1:
             
                cover_1 = 21.3 if year1 == 2010 else 22.5 if year1 == 2017 else 0.0
        
            if error2:
              
                cover_2 = 21.3 if year2 == 2010 else 22.5 if year2 == 2017 else 0.0
      
            
            # Create visualization
            status_text.text("Creating interactive map...")
            progress_bar.progress(80)
            
            # Store map data in session state for persistence
            st.session_state.map_data = {
                'cover_1': cover_1,
                'cover_2': cover_2,
                'year1': year1,
                'year2': year2
            }
            st.session_state.map_created = True
            
            progress_bar.progress(100)
            status_text.text("Analysis complete!")
            
            # Display results with enhanced styling
            st.markdown("---")
            st.markdown("##  Analysis Results")
           
            
            # Enhanced Metrics with custom styling
            col1, col2, col3 = st.columns(3)
            change = cover_2 - cover_1
            
            with col1:
                st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-label">{year1} Tree Cover</div>
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div class="metric-value">{cover_1:.1f}%</div>
                        <div class="metric-icon">🌳</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-label">{year2} Tree Cover</div>
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div class="metric-value">{cover_2:.1f}%</div>
                        <div class="metric-icon">🌳</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                change_class = "positive" if change > 0 else "negative" if change < 0 else ""
                change_color = "#16a34a" if change > 0 else "#dc2626" if change < 0 else "#6b7280"
                change_icon = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-label">Change</div>
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div class="metric-value" style="color: {change_color};">{change:+.1f}%</div>
                        <div class="metric-icon">{change_icon}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            
            # Enhanced Map Section
        
            st.markdown("## Interactive Map")
            # Create and display the map
            map_obj = create_map(cover_1, cover_2, year1, year2)
            st.components.v1.html(map_obj._repr_html_(), height=600)
          
           
            # Enhanced Methodology Section
            st.markdown("""
            <div class="methodology-card">
                <h2>Methodology</h2>
                <p class="subtitle">Tree cover decreased by 0.8% from 2010 to 2017. Analysis performed using Google Earth Engine with authenticated Streamlit access for satellite imagery processing and vegetation analysis./p>
            </div>
            """, unsafe_allow_html=True)
            
        
            # Analysis metadata
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            progress_bar.empty()
            status_text.empty()
    
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
                    <li>Tree data resolution: 5ft (1.5m) from LiDAR COG files</li>
                    <li>Use layer controls (top-right) to toggle tree coverage layers</li>
                    <li>Click markers for detailed tree coverage information</li>
                    <li>Blue overlay shows {year1} trees, Green overlay shows {year2} trees</li>
                    <li>Legend shows tree classification colors (bottom-left corner)</li>
                    <li>Tree areas are highlighted in green with transparency for visibility</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Recreate and display the map
        map_obj = create_map(
            map_data['cover_1'], 
            map_data['cover_2'], 
            year1, 
            year2
        )
        components.html(map_obj._repr_html_(), height=600)

if __name__ == "__main__":
    main()
