"""
Initialize Pixel Data Cache for Tree Analysis

This script reads the COG files once and caches the pixel data in PostgreSQL.
Run this once before deploying to Streamlit Cloud to avoid timeouts.

Usage:
    python initialize_cache.py
"""

import sys
from postgis_raster import PostGISRasterHandler, initialize_lidar_datasets
from config import HUDSON_SQUARE_BOUNDS, LIDAR_DATASETS

def main():
    """Initialize the pixel data cache"""
    print("=" * 60)
    print("Initializing Pixel Data Cache")
    print("=" * 60)
    print()
    
    # Initialize database and create tables
    print("Step 1: Initializing database and creating tables...")
    if not initialize_lidar_datasets():
        print("❌ Failed to initialize database")
        return False
    
    print()
    print("✅ Cache initialization complete!")
    print()
    print("Cache Status:")
    print("-" * 60)
    
    # Verify cache contents
    handler = PostGISRasterHandler()
    if handler.connect():
        try:
            for year in [2010, 2017]:
                bounds_type = HUDSON_SQUARE_BOUNDS.get('type', 'rectangle')
                result = handler.get_cached_pixel_data(year, bounds_type)
                
                if result:
                    data, metadata = result
                    print(f"Year {year}:")
                    print(f"  ✓ Cached {metadata['total_pixels']:,} pixels")
                    print(f"  ✓ Tree coverage: {metadata['coverage_percent']:.2f}%")
                    print(f"  ✓ Tree pixels: {metadata['tree_pixels']:,}")
                    print(f"  ✓ Data shape: {data.shape}")
                else:
                    print(f"Year {year}: ❌ No cached data found")
                print()
        finally:
            handler.disconnect()
    
    print("=" * 60)
    print("Next steps:")
    print("  1. Your pixel data is now cached in PostgreSQL")
    print("  2. The app will now load instantly from cached data")
    print("  3. Deploy to Streamlit Cloud without timeout issues")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

