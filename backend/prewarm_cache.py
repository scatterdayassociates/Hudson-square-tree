"""
Pre-warm tile cache for common viewing areas
Generates and caches tiles ahead of time for instant loading
"""

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BACKEND_URL = "http://localhost:8000"
YEARS = [2010, 2021]

# Hudson Square area - common zoom levels
ZOOM_LEVELS = [13, 14, 15, 16]  # Most commonly viewed

def latlon_to_tile(lat, lon, zoom):
    """Convert lat/lon to tile coordinates"""
    import math
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def get_tiles_for_bbox(west, south, east, north, zoom):
    """Get all tile coordinates for a bounding box"""
    nw_x, nw_y = latlon_to_tile(north, west, zoom)
    se_x, se_y = latlon_to_tile(south, east, zoom)
    
    tiles = []
    for x in range(nw_x, se_x + 1):
        for y in range(nw_y, se_y + 1):
            tiles.append((x, y))
    return tiles

def fetch_tile(year, z, x, y):
    """Fetch a single tile (will be cached by backend)"""
    url = f"{BACKEND_URL}/tiles/{year}/{z}/{x}/{y}.png"
    try:
        response = requests.get(url, timeout=30)
        cache_status = response.headers.get('X-Cache', 'UNKNOWN')
        return (year, z, x, y, response.status_code, cache_status)
    except Exception as e:
        return (year, z, x, y, 'ERROR', str(e))

def prewarm_area(west, south, east, north, name="Area"):
    """Pre-warm cache for a specific area"""
    print(f"\n🔥 Pre-warming cache for {name}")
    print(f"   Bounds: W={west}, S={south}, E={east}, N={north}")
    print(f"   Zoom levels: {ZOOM_LEVELS}")
    print(f"   Years: {YEARS}\n")
    
    total_tiles = 0
    all_tasks = []
    
    # Calculate all tiles needed
    for year in YEARS:
        for zoom in ZOOM_LEVELS:
            tiles = get_tiles_for_bbox(west, south, east, north, zoom)
            for x, y in tiles:
                all_tasks.append((year, zoom, x, y))
            print(f"   Year {year}, Zoom {zoom}: {len(tiles)} tiles")
            total_tiles += len(tiles)
    
    print(f"\n   Total tiles to generate: {total_tiles}")
    print(f"   Starting parallel tile generation...\n")
    
    # Fetch tiles in parallel
    start_time = time.time()
    completed = 0
    hits = 0
    misses = 0
    errors = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks
        futures = {
            executor.submit(fetch_tile, year, z, x, y): (year, z, x, y)
            for year, z, x, y in all_tasks
        }
        
        # Process results as they complete
        for future in as_completed(futures):
            year, z, x, y, status, cache_status = future.result()
            completed += 1
            
            if status == 200:
                if cache_status == 'HIT':
                    hits += 1
                else:
                    misses += 1
            else:
                errors += 1
                if errors <= 5:  # Only show first 5 errors
                    print(f"   ❌ Error: {year}/{z}/{x}/{y} - {cache_status}")
            
            # Progress update every 10 tiles
            if completed % 10 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total_tiles - completed) / rate if rate > 0 else 0
                print(f"   Progress: {completed}/{total_tiles} tiles "
                      f"({hits} cached, {misses} new, {errors} errors) "
                      f"- {rate:.1f} tiles/sec - ETA: {eta:.1f}s")
    
    elapsed = time.time() - start_time
    print(f"\n✅ Pre-warming complete!")
    print(f"   Total time: {elapsed:.2f} seconds")
    print(f"   Average: {elapsed/total_tiles:.2f} seconds/tile")
    print(f"   Cache hits: {hits} (already cached)")
    print(f"   Cache misses: {misses} (newly generated)")
    print(f"   Errors: {errors}")
    print(f"\n   Next time you view this area, it will load instantly! ⚡\n")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Tile Cache Pre-warmer")
    print("="*60)
    
    # Hudson Square default area
    HUDSON_SQUARE = {
        "west": -74.0109,
        "south": 40.7219,
        "east": -74.0029,
        "north": 40.7298,
        "name": "Hudson Square"
    }
    
    # Pre-warm Hudson Square
    prewarm_area(
        west=HUDSON_SQUARE["west"],
        south=HUDSON_SQUARE["south"],
        east=HUDSON_SQUARE["east"],
        north=HUDSON_SQUARE["north"],
        name=HUDSON_SQUARE["name"]
    )
    
    # Get final cache stats
    print("\n📊 Final Cache Statistics:")
    try:
        response = requests.get(f"{BACKEND_URL}/cache/stats")
        stats = response.json()
        print(f"   Total cached tiles: {stats['total_tiles']}")
        print(f"   Total cache size: {stats['total_size_mb']:.2f} MB")
        print(f"   Cache directory: {stats['cache_dir']}")
        print(f"   Memory cache hits: {stats['memory_cache_info']['hits']}")
        print(f"   Memory cache misses: {stats['memory_cache_info']['misses']}")
    except Exception as e:
        print(f"   Could not fetch stats: {e}")
    
    print("\n" + "="*60)
    print("✨ Your tiles are now cached and ready for instant loading!")
    print("="*60 + "\n")
