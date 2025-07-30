import streamlit as st
import ee
import geemap.foliumap as geemap
import folium
from folium.plugins import Fullscreen
import json
import os
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Hudson Square Tree Cover Analysis",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants - Your project ID
PROJECT_ID = 'seventh-tempest-348517'

# Hudson Square coordinates
HUDSON_SQUARE_BOUNDS = {
    'west': -74.008,
    'south': 40.722,
    'east': -74.002,
    'north': 40.728
}

@st.cache_resource
def authenticate_ee():
    """
    Authenticate Google Earth Engine for both local and cloud deployment.
    Priority: Local credentials -> Streamlit secrets -> Service account file
    """
    try:
        # Method 1: Try local authentication first (for development)
        try:
            ee.Initialize(project=PROJECT_ID)
            return True, "✅ Using existing local Earth Engine authentication"
        except Exception as local_error:
            pass
        
        # Method 2: Try Streamlit secrets (for cloud deployment)
        try:
            if hasattr(st, 'secrets') and 'gee_service_account' in st.secrets:
                service_account_info = dict(st.secrets["gee_service_account"])
                credentials = ee.ServiceAccountCredentials(
                    service_account_info['client_email'], 
                    key_data=json.dumps(service_account_info)
                )
                ee.Initialize(credentials, project=PROJECT_ID)
                return True, "✅ Authenticated via Streamlit secrets"
        except Exception as secrets_error:
            pass
            
        # Method 3: Try local service account file
        if os.path.exists('private-key.json'):
            try:
                credentials = ee.ServiceAccountCredentials(None, 'private-key.json')
                ee.Initialize(credentials, project=PROJECT_ID)
                return True, "✅ Authenticated via local service account (private-key.json)"
            except Exception as sa_error:
                pass
                
        # Method 4: Try environment variable
        if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
            try:
                credentials_path = os.environ['GOOGLE_APPLICATION_CREDENTIALS']
                credentials = ee.ServiceAccountCredentials(None, credentials_path)
                ee.Initialize(credentials, project=PROJECT_ID)
                return True, f"✅ Authenticated via environment variable: {credentials_path}"
            except Exception as env_error:
                pass
        
        # Method 5: Try force re-authentication (local only)
        try:
            ee.Authenticate()
            ee.Initialize(project=PROJECT_ID)
            return True, f"✅ Re-authenticated with project: {PROJECT_ID}"
        except Exception as auth_error:
            pass
        
        # If all methods fail
        return False, """
        ❌ Could not authenticate with Earth Engine. 
        
        **For Local Development:**
        1. Run: `earthengine authenticate --force`
        2. Run: `earthengine set_project seventh-tempest-348517`
        3. Restart this app
        
        **For Streamlit Cloud:**
        1. Create a service account in Google Cloud Console
        2. Add the JSON content to Streamlit secrets as `gee_service_account`
        """
            
    except Exception as e:
        return False, f"❌ Authentication failed: {str(e)}"

def get_tree_cover(year):
    """Fetch tree cover for the given year using Sentinel-2 data (June to August)."""
    try:
        hudson_square = ee.Geometry.Rectangle([
            HUDSON_SQUARE_BOUNDS['west'],
            HUDSON_SQUARE_BOUNDS['south'],
            HUDSON_SQUARE_BOUNDS['east'],
            HUDSON_SQUARE_BOUNDS['north']
        ])
        
        sentinel2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterDate(f'{year}-06-01', f'{year}-08-31') \
            .filterBounds(hudson_square) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
            .median()

        ndvi = sentinel2.normalizedDifference(['B8', 'B4']).rename('NDVI')
        tree_cover = ndvi.expression(
            '((NDVI > 0.3) ? (NDVI - 0.3) * 142.857 : 0)',
            {'NDVI': ndvi}
        ).rename('tree_cover')

        return tree_cover, None
    except Exception as e:
        return None, str(e)

def calculate_coverage(image, geometry, band_name='tree_cover'):
    """Calculate average tree cover percentage within the specified geometry."""
    if image is None:
        return 0.0, "No image data"

    try:
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=30,
            bestEffort=True,
            maxPixels=1e10
        )

        result = stats.get(band_name).getInfo()
        return (result if result is not None else 0.0), None
    except Exception as e:
        return 0.0, str(e)

def create_map(tree_2021, tree_2023, cover_2021, cover_2023):
    """Create the interactive map with tree cover layers."""
    hudson_square = ee.Geometry.Rectangle([
        HUDSON_SQUARE_BOUNDS['west'],
        HUDSON_SQUARE_BOUNDS['south'],
        HUDSON_SQUARE_BOUNDS['east'],
        HUDSON_SQUARE_BOUNDS['north']
    ])
    
    # Initialize the map
    Map = geemap.Map(
        center=[40.725, -74.005], 
        zoom=16, 
        width='100%', 
        height='600px'
    )

    # Clip the tree cover layers to Hudson Square
    tree_2021_clipped = tree_2021.clip(hudson_square)
    tree_2023_clipped = tree_2023.clip(hudson_square)

    # Visualization parameters
    vis_params_2021 = {'min': 0, 'max': 100, 'palette': ['white', 'lightgreen', 'darkgreen']}
    vis_params_2023 = {'min': 0, 'max': 100, 'palette': ['white', 'lightblue', 'darkblue']}

    # Add layers to map
    Map.addLayer(tree_2023_clipped, vis_params_2023, '2023 Tree Cover', opacity=0.7)
    Map.addLayer(tree_2021_clipped, vis_params_2021, '2021 Tree Cover', opacity=0.7)
    Map.addLayer(hudson_square, {'color': 'red', 'fillColor': 'transparent'}, 'Hudson Square Boundary')

    # Center the map
    Map.centerObject(hudson_square, 16)

    return Map

def main():
    # Header
    st.title("🌳 Hudson Square Tree Cover Analysis")
    st.markdown("**Analyzing vegetation changes in Hudson Square, NYC using satellite imagery**")
    
    # Sidebar
    st.sidebar.header("Analysis Settings")
    st.sidebar.markdown("### Study Area: Hudson Square, NYC")
    st.sidebar.markdown(f"**Coordinates:**")
    st.sidebar.markdown(f"- West: {HUDSON_SQUARE_BOUNDS['west']}")
    st.sidebar.markdown(f"- East: {HUDSON_SQUARE_BOUNDS['east']}")
    st.sidebar.markdown(f"- North: {HUDSON_SQUARE_BOUNDS['north']}")
    st.sidebar.markdown(f"- South: {HUDSON_SQUARE_BOUNDS['south']}")
    
    # Analysis years
    col1, col2 = st.sidebar.columns(2)
    year1 = col1.selectbox("Start Year", [2019, 2020, 2021, 2022], index=2)
    year2 = col2.selectbox("End Year", [2021, 2022, 2023, 2024], index=2)
    
    if year1 >= year2:
        st.sidebar.error("End year must be after start year!")
        return
    
    # Authentication status
    with st.spinner("Authenticating with Google Earth Engine..."):
        auth_success, auth_message = authenticate_ee()
    
    if not auth_success:
        st.error("❌ Google Earth Engine Authentication Failed")
        st.error(auth_message)
        return
    
    st.success(f"✅ Google Earth Engine authenticated successfully")
    st.info(f"ℹ️ {auth_message}")
    
    # Analysis button
    if st.button("🚀 Run Tree Cover Analysis", type="primary"):
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Fetch tree cover data
            status_text.text(f"Fetching {year1} tree cover data...")
            progress_bar.progress(20)
            
            tree_data_1, error1 = get_tree_cover(year1)
            if error1:
                st.error(f"Error fetching {year1} data: {error1}")
                return
            
            status_text.text(f"Fetching {year2} tree cover data...")
            progress_bar.progress(40)
            
            tree_data_2, error2 = get_tree_cover(year2)
            if error2:
                st.error(f"Error fetching {year2} data: {error2}")
                return
            
            # Calculate coverage
            status_text.text("Calculating coverage percentages...")
            progress_bar.progress(60)
            
            hudson_square = ee.Geometry.Rectangle([
                HUDSON_SQUARE_BOUNDS['west'],
                HUDSON_SQUARE_BOUNDS['south'],
                HUDSON_SQUARE_BOUNDS['east'],
                HUDSON_SQUARE_BOUNDS['north']
            ])
            
            cover_1, error_calc1 = calculate_coverage(tree_data_1, hudson_square)
            cover_2, error_calc2 = calculate_coverage(tree_data_2, hudson_square)
            
            if error_calc1 or error_calc2:
                st.error(f"Coverage calculation errors: {error_calc1}, {error_calc2}")
                return
            
            # Create visualization
            status_text.text("Creating interactive map...")
            progress_bar.progress(80)
            
            map_obj = create_map(tree_data_1, tree_data_2, cover_1, cover_2)
            
            progress_bar.progress(100)
            status_text.text("Analysis complete!")
            
            # Display results
            st.markdown("---")
            st.subheader("📊 Analysis Results")
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    label=f"{year1} Tree Cover",
                    value=f"{cover_1:.1f}%"
                )
            
            with col2:
                st.metric(
                    label=f"{year2} Tree Cover",
                    value=f"{cover_2:.1f}%"
                )
            
            with col3:
                change = cover_2 - cover_1
                st.metric(
                    label="Change",
                    value=f"{change:+.1f}%",
                    delta=f"{change:+.1f}%"
                )
            
            # Interpretation
            if change > 0:
                st.success(f"🌱 Tree cover increased by {change:.1f}% from {year1} to {year2}")
            elif change < 0:
                st.warning(f"🔻 Tree cover decreased by {abs(change):.1f}% from {year1} to {year2}")
            else:
                st.info(f"➡️ Tree cover remained stable from {year1} to {year2}")
            
            # Display map
            st.subheader("🗺️ Interactive Map")
            st.markdown(f"""
            **Legend:**
            - 🟢 Green: {year1} Tree Cover
            - 🔵 Blue: {year2} Tree Cover  
            - 🔴 Red boundary: Hudson Square area
            """)
            
            map_obj.to_streamlit(height=600)
            
            # Additional info
            with st.expander("ℹ️ Methodology"):
                st.markdown(f"""
                **Data Source:** Sentinel-2 Surface Reflectance (Harmonized)
                
                **Time Period:** June-August (summer months for optimal vegetation detection)
                
                **Processing:**
                - Cloud filtering: < 10% cloud coverage
                - NDVI calculation: (NIR - Red) / (NIR + Red)
                - Tree cover threshold: NDVI > 0.3
                - Spatial resolution: 30m
                
                **Study Area:** Hudson Square, Manhattan, NYC
                - Area: ~{abs(HUDSON_SQUARE_BOUNDS['east'] - HUDSON_SQUARE_BOUNDS['west']) * abs(HUDSON_SQUARE_BOUNDS['north'] - HUDSON_SQUARE_BOUNDS['south']) * 111000 * 111000:.0f} m²
                
                **Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """)
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            progress_bar.empty()
            status_text.empty()

if __name__ == "__main__":
    main()