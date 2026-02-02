"""
COG Registry - Central registry for all Cloud Optimized GeoTIFF datasets
"""

# COG URLs on Google Cloud Storage
COG_URLS = {
    2010: "https://storage.googleapis.com/raster_datam/landcover_2010_nyc_05ft_cog.tif",
    2021: "https://storage.googleapis.com/raster_datam/landcover_nyc_2021_6in_cog.tif",
}

# NYC LiDAR classification system (8-class)
LAND_COVER_CLASSES = {
    0: {"name": "Nodata", "color": [255, 255, 255, 0]},  # Transparent
    1: {"name": "Tree Canopy", "color": [34, 139, 34, 200]},  # Forest green
    2: {"name": "Grass/Shrubs", "color": [144, 238, 144, 180]},  # Light green
    3: {"name": "Bare Soil", "color": [205, 133, 63, 150]},  # Peru brown
    4: {"name": "Water", "color": [65, 105, 225, 180]},  # Royal blue
    5: {"name": "Buildings", "color": [128, 128, 128, 180]},  # Gray
    6: {"name": "Roads", "color": [64, 64, 64, 180]},  # Dark gray
    7: {"name": "Other Impervious", "color": [169, 169, 169, 150]},  # Light gray
    8: {"name": "Railroads", "color": [112, 128, 144, 180]},  # Slate gray
}

# Tree classes for analysis (Tree Canopy + Grass/Shrubs)
TREE_CLASSES = [1]

# Color scheme for tree visualization
TREE_COLORMAP = {
    "name": "trees",
    "colors": {
        0: [255, 255, 255, 0],  # Nodata - transparent
        1: [34, 139, 34, 255],   # Tree Canopy - dark green
    }
}

