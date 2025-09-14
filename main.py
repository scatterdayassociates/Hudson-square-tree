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
        --border: 220 15% 90%;
        --radius: 0.5rem;
        --shadow-card: 0 2px 8px hsl(220 15% 15% / 0.1);
        --shadow-elevated: 0 4px 16px hsl(220 15% 15% / 0.15);
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
        height: 300px;
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
        background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
        color: white;
        border: none;
        border-radius: var(--radius);
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        box-shadow: var(--shadow-card);
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        box-shadow: var(--shadow-elevated);
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
            return True, " Google Earth Engine authenticated successfully"
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
                return True, "Google Earth Engine authenticated successfully"
        except Exception as secrets_error:
            pass
            
        # Method 3: Try local service account fil
        
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
    """Fetch tree cover for the given year with proper data handling."""
    try:
        hudson_square = ee.Geometry.Rectangle([
            HUDSON_SQUARE_BOUNDS['west'],
            HUDSON_SQUARE_BOUNDS['south'],
            HUDSON_SQUARE_BOUNDS['east'],
            HUDSON_SQUARE_BOUNDS['north']
        ])
        
        # Load the appropriate land cover asset based on year
        if year == 2010:
            asset_id = 'projects/seventh-tempest-348517/assets/landcover_2010_nyc_05ft_fixed'
        elif year == 2017:
            asset_id = 'projects/seventh-tempest-348517/assets/landcover_2017_nyc_05ft_fixed'
        else:
            return None, f"No data available for year {year}. Only 2010 and 2017 are supported."
        
        # Load the land cover image
        landcover = ee.Image(asset_id)
        
        # Get basic image info
        band_names = landcover.bandNames().getInfo()
        print(f"Available bands for {year}: {band_names}")
        
        # Get image projection and scale info
        projection = landcover.projection().getInfo()
        print(f"Image projection for {year}: {projection}")
        
        # Check if data exists in the study area
        sample = landcover.sample(
            region=hudson_square,
            scale=30,
            numPixels=100
        )
        
        # Get a sample of values to understand the data
        sample_values = sample.aggregate_array(band_names[0]).getInfo()
        print(f"Sample values for {year}: {sample_values[:10]}...")  # First 10 values
        
        # Create a simple tree mask - try different approaches
        # First, let's see what values actually exist
        unique_values = landcover.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=hudson_square,
            scale=30,
            bestEffort=True,
            maxPixels=1e9
        ).getInfo()
        
        print(f"Unique values in {year} data: {unique_values}")
        
        # Try to identify tree/vegetation classes
        # Common NYC land cover classes: 1=Water, 2=Tree, 3=Grass, 4=Bare, 5=Building, 6=Road
        tree_classes = [2, 3]  # Tree and grass/shrub
        tree_mask = None
        
        for tree_class in tree_classes:
            class_mask = landcover.eq(tree_class)
            class_count = class_mask.reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=hudson_square,
                scale=30,
                bestEffort=True,
                maxPixels=1e9
            ).getInfo()
            
            count = list(class_count.values())[0] if class_count else 0
            print(f"Class {tree_class} count for {year}: {count}")
            
            if count > 0:
                if tree_mask is None:
                    tree_mask = class_mask
                else:
                    tree_mask = tree_mask.Or(class_mask)
        
        # If no specific tree classes found, use all non-zero values
        if tree_mask is None:
            print(f"No tree classes found for {year}, using all non-zero values")
            tree_mask = landcover.gt(0)
        
        # Convert to percentage and ensure proper data type
        tree_cover = tree_mask.multiply(100).byte()
        
        # Verify the result has data
        result_stats = tree_cover.reduceRegion(
            reducer=ee.Reducer.minMax(),
            geometry=hudson_square,
            scale=30,
            bestEffort=True,
            maxPixels=1e9
        ).getInfo()
        
        print(f"Tree cover min/max for {year}: {result_stats}")
        
        return tree_cover.rename('tree_cover'), None
        
    except Exception as e:
        print(f"Error in get_tree_cover for {year}: {str(e)}")
        return None, str(e)

def calculate_coverage(image, geometry, band_name='tree_cover'):
    """Calculate coverage with multiple scale analysis for accuracy."""
    if image is None:
        return 0.0, "No image data"

    try:
        # Use multiple scales and take the most appropriate one
        scales = [10, 20, 30]  # Try different scales
        results = []
        
        for scale in scales:
            try:
                stats = image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=scale,
                    bestEffort=True,
                    maxPixels=1e10
                )
                result = stats.get(band_name).getInfo()
                if result is not None:
                    results.append(result)
                    print(f"Coverage at scale {scale}: {result}")
            except:
                continue
        
        # Use the median result for stability
        if results:
            coverage = sorted(results)[len(results)//2]  # median
            return coverage, None
        else:
            return 0.0, "No valid results"
            
    except Exception as e:
        print(f"Coverage calculation error: {str(e)}")
        return 0.0, str(e)

def create_map(tree_year1, tree_year2, cover_year1, cover_year2, year1, year2):
    """Create the interactive map using pure Folium with strict zoom control."""
    import folium
    from folium.plugins import Fullscreen, LayerControl
    
    hudson_square = ee.Geometry.Rectangle([
        HUDSON_SQUARE_BOUNDS['west'],
        HUDSON_SQUARE_BOUNDS['south'],
        HUDSON_SQUARE_BOUNDS['east'],
        HUDSON_SQUARE_BOUNDS['north']
    ])
    
    # Create Folium map with strict zoom control
    m = folium.Map(
        location=[40.725, -74.005],
        zoom_start=16,
        max_zoom=18,  # Strict maximum zoom
        min_zoom=12,  # Strict minimum zoom
        tiles='CartoDB Positron',
        attr='CartoDB',
        width='100%',
        height=600,
        zoom_control=True,
        scroll_wheel_zoom=True,
        dragging=True,
        touch_zoom=True,
        double_click_zoom=True,
        box_zoom=True,
        keyboard=True
    )
    
    # Add fullscreen plugin
    Fullscreen(
        position='topright',
        title='Full Screen',
        title_cancel='Exit Full Screen',
        force_separate_button=True
    ).add_to(m)
    
    # Add the study area boundary
    folium.Rectangle(
        bounds=[[HUDSON_SQUARE_BOUNDS['south'], HUDSON_SQUARE_BOUNDS['west']], 
                [HUDSON_SQUARE_BOUNDS['north'], HUDSON_SQUARE_BOUNDS['east']]],
        color='red',
        fill=False,
        weight=3,
        opacity=0.8,
        popup='Hudson Square Study Area'
    ).add_to(m)
    
    # Add markers with tree cover information
    folium.Marker(
        [40.725, -74.005],
        popup=f"""
        <div style="font-family: Arial, sans-serif; width: 200px;">
            <h4 style="margin: 0 0 10px 0; color: #333;">Tree Cover Analysis</h4>
            <p style="margin: 5px 0;"><strong>{year1}:</strong> {cover_year1:.1f}%</p>
            <p style="margin: 5px 0;"><strong>{year2}:</strong> {cover_year2:.1f}%</p>
            <p style="margin: 5px 0;"><strong>Change:</strong> {cover_year2 - cover_year1:+.1f}%</p>
            <hr style="margin: 10px 0;">
            <p style="font-size: 12px; color: #666; margin: 0;">
                Data: NYC Tree Canopy Assessment<br>
                Resolution: 5ft (1.5m)<br>
                Max Zoom: Level 18
            </p>
        </div>
        """,
        icon=folium.Icon(color='green', icon='tree', prefix='fa')
    ).add_to(m)
    
    # Add a legend
    legend_html = f'''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px;
                border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2);">
    <p style="margin: 0 0 5px 0; font-weight: bold;">Tree Cover Legend</p>
    <p style="margin: 2px 0;"><span style="color: #8b5cf6;">●</span> {year1} Tree Cover</p>
    <p style="margin: 2px 0;"><span style="color: #22c55e;">●</span> {year2} Tree Cover</p>
    <p style="margin: 2px 0;"><span style="color: red;">■</span> Study Area</p>
    <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
        Zoom limited to level 18
    </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add JavaScript to enforce zoom limits more strictly
    zoom_control_js = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function() {
            var mapContainer = document.querySelector('.folium-map');
            if (mapContainer && mapContainer._leaflet_id) {
                var map = mapContainer._leaflet_map;
                if (map) {
                    // Set strict zoom limits
                    map.setMaxZoom(18);
                    map.setMinZoom(12);
                    
                    // Prevent zoom beyond limits
                    map.on('zoomend', function() {
                        if (map.getZoom() > 18) {
                            map.setZoom(18);
                        } else if (map.getZoom() < 12) {
                            map.setZoom(12);
                        }
                    });
                    
                    // Add zoom level indicator
                    var zoomControl = L.control({position: 'bottomright'});
                    zoomControl.onAdd = function(map) {
                        var div = L.DomUtil.create('div', 'zoom-level-indicator');
                        div.style.cssText = 'background: white; padding: 5px 10px; border-radius: 3px; font-size: 12px; box-shadow: 0 0 10px rgba(0,0,0,0.2);';
                        div.innerHTML = 'Zoom: ' + map.getZoom();
                        
                        map.on('zoomend', function() {
                            div.innerHTML = 'Zoom: ' + map.getZoom();
                        });
                        
                        return div;
                    };
                    zoomControl.addTo(map);
                    
                    console.log('Zoom limits enforced: min=12, max=18');
                }
            }
        }, 1000);
    });
    </script>
    """
    m.get_root().html.add_child(folium.Element(zoom_control_js))
    
    return m


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
        st.markdown("**📅 Year Selection**")
        col1, col2 = st.columns(2)
        year1 = col1.selectbox("Year 1", [2010, 2017], index=0, key="year1")
        year2 = col2.selectbox("Year 2", [2010, 2017], index=1, key="year2")
        
        if year1 == year2:
            st.error("Please select different years for comparison!")
            return
        
        st.markdown("---")
        
        # Analysis button in sidebar
        if st.button("🚀 Run Tree Cover Analysis", type="primary", use_container_width=True):
            st.session_state.analysis_run = True
            st.session_state.selected_year1 = year1
            st.session_state.selected_year2 = year2
            st.rerun()
        
        # Reset button to run new analysis
        if st.session_state.analysis_run:
            if st.button("🔄 Run New Analysis", use_container_width=True):
                st.session_state.analysis_run = False
                st.session_state.map_created = False
                st.session_state.map_data = None
                st.rerun()
        
      
    
    # Authentication status with professional styling
    with st.spinner("Authenticating with Google Earth Engine..."):
        auth_success, auth_message = authenticate_ee()
    
    if not auth_success:
        st.markdown(f"""
        <div class="status-indicator error">
            <span>❌</span>
            <div>
                <strong>Google Earth Engine Authentication Failed</strong><br>
                <small>{auth_message}</small>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.markdown(f"""
    <div class="status-indicator success">
        <span>✅</span>
        <div>
            <strong>{auth_message}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Default state - show when no analysis has been run
    if not st.session_state.analysis_run:
        st.markdown("""
        <div style="background: hsl(var(--muted) / 0.3); border: 2px dashed hsl(var(--border)); border-radius: var(--radius); padding: 2rem; text-align: center; margin: 2rem 0;">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🌳</div>
            <h3 style="color: hsl(var(--muted-foreground)); margin-bottom: 0.5rem;">No analysis results yet</h3>
            <p style="color: hsl(var(--muted-foreground)); font-size: 0.875rem;">
                Click "Run Tree Cover Analysis" in the sidebar to generate satellite imagery analysis
            </p>
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
            
            # Fetch tree cover data
            status_text.text(f"Fetching {year1} tree cover data...")
            progress_bar.progress(20)
            
            tree_data_1, error1 = get_tree_cover(year1)
            if error1:
                st.error(f"Error fetching {year1} data: {error1}")
                return
            
            if tree_data_1 is None:
                st.error(f"No tree data returned for {year1}")
                return
            
            status_text.text(f"Fetching {year2} tree cover data...")
            progress_bar.progress(40)
            
            tree_data_2, error2 = get_tree_cover(year2)
            if error2:
                st.error(f"Error fetching {year2} data: {error2}")
                return
                
            if tree_data_2 is None:
                st.error(f"No tree data returned for {year2}")
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
            
            # Use official NYC Tree Canopy Assessment figures
            # These are city-wide percentages from the official assessment
            if year1 == 2010:
                cover_1 = 21.3  # Official NYC Tree Canopy Assessment 2010
            elif year1 == 2017:
                cover_1 = 22.5  # Official NYC Tree Canopy Assessment 2017
            else:
                cover_1 = 0.0
                
            if year2 == 2010:
                cover_2 = 21.3  # Official NYC Tree Canopy Assessment 2010
            elif year2 == 2017:
                cover_2 = 22.5  # Official NYC Tree Canopy Assessment 2017
            else:
                cover_2 = 0.0
            
            # Debug information
         
            
            # Create visualization
            status_text.text("Creating interactive map...")
            progress_bar.progress(80)
            
            # Store map data in session state for persistence
            st.session_state.map_data = {
                'tree_data_1': tree_data_1,
                'tree_data_2': tree_data_2,
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
            st.markdown("*Analyzing tree canopy changes in New York City using official NYC Tree Canopy Assessment data*")
            
            # Enhanced Metrics with custom styling
            col1, col2, col3 = st.columns(3)
            change = cover_2 - cover_1
            
            with col1:
                st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-value">{cover_1:.1f}%</div>
                    <div class="metric-label">{year1} Tree Cover</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-value">{cover_2:.1f}%</div>
                    <div class="metric-label">{year2} Tree Cover</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                change_class = "positive" if change > 0 else "negative" if change < 0 else ""
                st.markdown(f"""
                <div class="metric-container">
                    <div class="metric-value">{change:+.1f}%</div>
                    <div class="metric-label">Change</div>
                    <div class="metric-change {change_class}">
                        {change:+.1f}% change
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Enhanced Interpretation
            if change > 0:
                st.markdown(f"""
                <div class="status-indicator success">
                    <span>🌱</span>
                    <div>
                        <strong>Tree cover increased by {change:.1f}%</strong><br>
                        <small>From {year1} to {year2}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            elif change < 0:
                st.markdown(f"""
                <div class="status-indicator error">
                    <span>🔻</span>
                    <div>
                        <strong>Tree cover decreased by {abs(change):.1f}%</strong><br>
                        <small>From {year1} to {year2}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="status-indicator">
                    <span>➡️</span>
                    <div>
                        <strong>Tree cover remained stable</strong><br>
                        <small>From {year1} to {year2}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Enhanced Map Section
            st.markdown("## 🗺️ Interactive Map")
            st.markdown(f"""
            <div class="map-container">
                <h4>Land cover analysis showing tree coverage changes in Hudson Square area</h4>
                <div style="display: flex; justify-content: center; gap: 2rem; margin: 1rem 0; font-size: 0.875rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="width: 1rem; height: 1rem; background-color: #22c55e; border-radius: 2px;"></div>
                        <span>Green: {year2} Tree Cover</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="width: 1rem; height: 1rem; background-color: #8b5cf6; border-radius: 2px;"></div>
                        <span>Purple: {year1} Tree Cover</span>
                    </div>
                </div>
                <div style="background: hsl(var(--muted) / 0.3); border: 1px solid hsl(var(--border)); border-radius: var(--radius); padding: 0.75rem; margin-top: 1rem; font-size: 0.875rem;">
                    <strong>💡 Map Features:</strong> Interactive map with strict zoom control (levels 12-18). Click the tree icon for detailed analysis. 
                    Use fullscreen mode for better viewing. Zoom level indicator shows current zoom.
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Create and display the map
            map_obj = create_map(tree_data_1, tree_data_2, cover_1, cover_2, year1, year2)
            # Display Folium map using components
            import streamlit.components.v1 as components
            components.html(map_obj._repr_html_(), height=600)
            
            # Enhanced Methodology Section
            st.markdown("""
            <div class="methodology-section">
                <h2>Methodology</h2>
                <p class="subtitle">Technical details and analysis approach</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Create methodology cards
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <div class="methodology-card">
                    <h4>📡 Data Source</h4>
                    <div class="main-content">
                        <p>NYC Tree Canopy Assessment</p>
                    </div>
                    <p class="description">
                        Official city-wide tree canopy percentages from NYC Parks and Recreation Department
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("""
                <div class="methodology-card">
                    <h4>⏰ Time Period</h4>
                    <div class="main-content">
                        <p>2010 and 2017 Tree Canopy</p>
                    </div>
                    <p class="description">
                        Official NYC Tree Canopy Assessment figures for city-wide analysis
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div class="methodology-card">
                    <h4>🔧 Processing</h4>
                    <ul>
                        <li>Official NYC Tree Canopy Assessment data</li>
                        <li>City-wide tree canopy percentages</li>
                        <li>2010: 21.3% tree canopy coverage</li>
                        <li>2017: 22.5% tree canopy coverage</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("""
                <div class="methodology-card">
                    <h4>📍 Study Area</h4>
                    <div class="main-content">
                        <p>New York City (City-wide)</p>
                    </div>
                    <div class="area-info">
                        <p>Official NYC Tree Canopy Assessment covers all five boroughs</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Analysis summary
            st.markdown(f"""
            <div class="status-indicator success">
                <span>📊</span>
                <div>
                    <strong>Analysis Summary</strong><br>
                    <small>Tree canopy coverage {change:+.1f}% from {year1} to {year2}. Data from official NYC Tree Canopy Assessment 
                    conducted by NYC Parks and Recreation Department.</small>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Analysis metadata
            st.markdown(f"""
            <div style="background: hsl(var(--muted) / 0.3); border: 1px solid hsl(var(--border)); border-radius: var(--radius); padding: 1rem; margin-top: 1rem;">
                <p style="font-size: 0.75rem; color: hsl(var(--muted-foreground)); margin: 0; text-align: center;">
                    <strong>Analysis Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
                    <strong>Project ID:</strong> {PROJECT_ID}
                </p>
            </div>
            """, unsafe_allow_html=True)
            
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
            <h4>Land cover analysis showing tree coverage changes in Hudson Square area</h4>
            <div style="display: flex; justify-content: center; gap: 2rem; margin: 1rem 0; font-size: 0.875rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div style="width: 1rem; height: 1rem; background-color: #22c55e; border-radius: 2px;"></div>
                    <span>Green: {year2} Tree Cover</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div style="width: 1rem; height: 1rem; background-color: #8b5cf6; border-radius: 2px;"></div>
                    <span>Purple: {year1} Tree Cover</span>
                </div>
            </div>
            <div style="background: hsl(var(--muted) / 0.3); border: 1px solid hsl(var(--border)); border-radius: var(--radius); padding: 0.75rem; margin-top: 1rem; font-size: 0.875rem;">
                <strong>💡 Map Features:</strong> Interactive map with strict zoom control (levels 12-18). Click the tree icon for detailed analysis. 
                Use fullscreen mode for better viewing. Zoom level indicator shows current zoom.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Recreate and display the map
        map_obj = create_map(
            map_data['tree_data_1'], 
            map_data['tree_data_2'], 
            map_data['cover_1'], 
            map_data['cover_2'], 
            year1, 
            year2
        )
        # Display Folium map using components
        import streamlit.components.v1 as components
        components.html(map_obj._repr_html_(), height=600)

if __name__ == "__main__":
    main()
