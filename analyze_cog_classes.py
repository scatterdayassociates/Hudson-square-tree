"""
Analyze COG File Land Cover Classes

This script reads your COG files and shows you:
- What pixel values exist in your data
- How many pixels of each class
- Percentage breakdown by class

This helps you identify which values represent trees.
"""

import rasterio
import numpy as np
from config import LIDAR_DATASETS, HUDSON_SQUARE_BOUNDS

def analyze_cog_classes(year):
    """Analyze land cover classes in COG file"""
    print(f"\n{'='*70}")
    print(f"Analyzing Year {year} COG File")
    print(f"{'='*70}")
    
    cog_url = LIDAR_DATASETS.get(str(year))
    print(f"URL: {cog_url}")
    print()
    
    try:
        with rasterio.open(cog_url) as src:
            # Handle polygon masking
            if HUDSON_SQUARE_BOUNDS.get('type') == 'polygon':
                from rasterio.mask import mask
                import geopandas as gpd
                from shapely.geometry import Polygon
                
                coords = HUDSON_SQUARE_BOUNDS['coordinates']
                polygon = Polygon(coords)
                gdf = gpd.GeoDataFrame([1], geometry=[polygon], crs='EPSG:4326')
                gdf = gdf.to_crs(src.crs)
                
                data, transform = mask(src, gdf.geometry, crop=True, filled=False, nodata=0)
                data = data[0]
            else:
                from rasterio.warp import transform_bounds
                bounds = HUDSON_SQUARE_BOUNDS
                raster_bounds = transform_bounds('EPSG:4326', src.crs, 
                                               bounds['west'], bounds['south'],
                                               bounds['east'], bounds['north'])
                window = rasterio.windows.from_bounds(*raster_bounds, src.transform)
                data = src.read(1, window=window)
        
        print(f"Data shape: {data.shape}")
        print(f"Total pixels: {data.size:,}")
        print()
        
        # Get unique values and their counts
        unique, counts = np.unique(data, return_counts=True)
        
        # Calculate valid pixels (excluding 0 = nodata)
        valid_mask = data != 0
        total_valid = np.sum(valid_mask)
        
        print(f"Valid pixels (excluding nodata): {total_valid:,}")
        print()
        print("-" * 70)
        print(f"{'Class':<10} {'Count':<15} {'% of Valid':<15} {'Bar Chart'}")
        print("-" * 70)
        
        for value, count in zip(unique, counts):
            if value == 0:
                print(f"{value:<10} {count:>12,}   (nodata - outside polygon)")
            else:
                percentage = (count / total_valid) * 100
                bar_length = int(percentage / 2)  # Scale to fit
                bar = "█" * bar_length
                print(f"{value:<10} {count:>12,}   {percentage:>6.2f}%      {bar}")
        
        print("-" * 70)
        print()
        
        # Analysis hints
        print("💡 Analysis Hints:")
        print("-" * 70)
        
        # Find the dominant class (excluding nodata)
        valid_values = unique[unique != 0]
        valid_counts = counts[unique != 0]
        
        if len(valid_values) > 0:
            dominant_idx = np.argmax(valid_counts)
            dominant_class = valid_values[dominant_idx]
            dominant_pct = (valid_counts[dominant_idx] / total_valid) * 100
            
            print(f"• Dominant class: {dominant_class} ({dominant_pct:.2f}% of area)")
            print()
            
            print("Common LiDAR classifications:")
            print("  Class 1: Often Unclassified/Ground or Trees (depends on dataset)")
            print("  Class 2: Often Ground or Trees (depends on dataset)")
            print("  Class 3-4: Often Low/Medium Vegetation")
            print("  Class 5: Often Buildings")
            print("  Class 6: Often Roads/Pavement")
            print("  Class 7: Often High Vegetation or Grass")
            print()
            
            print("🌳 For NYC LiDAR data, typical tree/vegetation classes are:")
            print("  • NYC 2010 (5ft): Class 2 = Tree Canopy, Class 7 = Grass/Shrubs")
            print("  • NYC 2021 (6in): Class 2 = Tree Canopy, Class 7 = Grass/Shrubs")
            print()
            
            print(f"Based on your data:")
            if dominant_class == 1 and dominant_pct > 20:
                print(f"  ⚠️  Class 1 dominates ({dominant_pct:.1f}%) - this might be Ground/Pavement")
                print(f"      OR it could be Trees if this is a custom classification")
            if any(v in valid_values for v in [2, 7]):
                print(f"  ✓ Classes 2 and/or 7 exist - typically trees in NYC LiDAR")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("\n" + "="*70)
    print("COG FILE LAND COVER CLASS ANALYZER")
    print("="*70)
    print("\nThis script analyzes your LiDAR data to show what pixel values")
    print("exist and help you identify which ones represent trees.")
    
    for year in [2010, 2021]:
        analyze_cog_classes(year)
    
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    print("\nTo determine which classes are trees:")
    print("1. Look at the percentages above")
    print("2. For NYC, Classes 2 and 7 are standard for trees/vegetation")
    print("3. If you see different results, check the dataset documentation")
    print("4. Update tree_classes in postgis_raster.py accordingly")
    print("\nCurrent code uses: tree_classes = [2, 7]")
    print("If your data is different, update this value!")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

