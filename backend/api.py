"""
FastAPI backend for serving COG tiles
Uses rio-tiler for efficient tile generation from Cloud Optimized GeoTIFFs
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from rio_tiler.io import Reader
from rio_tiler.colormap import cmap
from rio_tiler.models import ImageData
import numpy as np
from typing import Optional
import logging
from cog_registry import COG_URLS, LAND_COVER_CLASSES, TREE_CLASSES
from PIL import Image
from io import BytesIO
from functools import lru_cache
import hashlib
from pathlib import Path
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create disk cache directory
CACHE_DIR = Path("tile_cache")
CACHE_DIR.mkdir(exist_ok=True)
logger.info(f"Tile cache directory: {CACHE_DIR.absolute()}")

# Memory cache size (number of tiles to keep in memory)
MEMORY_CACHE_SIZE = 500

# COG Reader connection pool (keeps connections alive)
@lru_cache(maxsize=10)
def get_cog_reader(cog_url: str):
    """
    Get a cached COG reader connection
    Reusing connections speeds up tile generation significantly
    """
    return Reader(cog_url)

# Initialize FastAPI app
app = FastAPI(
    title="Tree Cover Analysis Tile Server",
    description="Serves map tiles from COG files for tree cover analysis",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Streamlit domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def create_tree_colormap():
    """Create a colormap highlighting tree areas (classes 1 and 2) in green"""
    colormap = {}
    
    for class_id, class_info in LAND_COVER_CLASSES.items():
        if class_id in TREE_CLASSES:
            # Tree classes - vibrant green with full opacity
            colormap[class_id] = class_info["color"]
        elif class_id == 0:
            # Nodata - transparent
            colormap[class_id] = [255, 255, 255, 0]
        else:
            # Non-tree classes - muted gray with transparency
            colormap[class_id] = [200, 200, 200, 100]
    
    return colormap


def get_tile_cache_path(year: int, z: int, x: int, y: int) -> Path:
    """Get the file path for a cached tile"""
    # Organize cache by year and zoom level
    cache_subdir = CACHE_DIR / str(year) / str(z) / str(x)
    cache_subdir.mkdir(parents=True, exist_ok=True)
    return cache_subdir / f"{y}.png"


@lru_cache(maxsize=MEMORY_CACHE_SIZE)
def get_cached_tile_bytes(year: int, z: int, x: int, y: int) -> Optional[bytes]:
    """
    Get cached tile from disk (with memory cache)
    Returns None if not cached
    """
    cache_path = get_tile_cache_path(year, z, x, y)
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to read cache file {cache_path}: {e}")
            return None
    return None


def save_tile_to_cache(year: int, z: int, x: int, y: int, tile_bytes: bytes):
    """Save generated tile to disk cache"""
    try:
        cache_path = get_tile_cache_path(year, z, x, y)
        with open(cache_path, 'wb') as f:
            f.write(tile_bytes)
        # Also store in memory cache
        get_cached_tile_bytes(year, z, x, y)  # This will cache it in LRU
    except Exception as e:
        logger.warning(f"Failed to save tile to cache: {e}")


def apply_colormap(data: np.ndarray, colormap: dict) -> np.ndarray:
    """
    Apply a colormap to classification data
    
    Args:
        data: 2D numpy array with class values (0-8)
        colormap: dict mapping class_id -> [R, G, B, A]
    
    Returns:
        4D RGBA image array (height, width, 4)
    """
    height, width = data.shape
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    
    for class_id, color in colormap.items():
        mask = data == class_id
        rgba[mask] = color
    
    return rgba


@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "healthy",
        "service": "Tree Cover Tile Server",
        "available_years": list(COG_URLS.keys()),
        "cache_enabled": True,
        "cache_dir": str(CACHE_DIR.absolute()),
        "memory_cache_size": MEMORY_CACHE_SIZE
    }


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    total_tiles = 0
    total_size_bytes = 0
    
    for year_dir in CACHE_DIR.iterdir():
        if year_dir.is_dir():
            for zoom_dir in year_dir.iterdir():
                if zoom_dir.is_dir():
                    for x_dir in zoom_dir.iterdir():
                        if x_dir.is_dir():
                            for tile_file in x_dir.glob("*.png"):
                                total_tiles += 1
                                total_size_bytes += tile_file.stat().st_size
    
    total_size_mb = total_size_bytes / (1024 * 1024)
    
    return {
        "total_tiles": total_tiles,
        "total_size_mb": round(total_size_mb, 2),
        "cache_dir": str(CACHE_DIR.absolute()),
        "memory_cache_info": get_cached_tile_bytes.cache_info()._asdict()
    }


@app.delete("/cache/clear")
async def clear_cache():
    """Clear all cached tiles"""
    try:
        import shutil
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            CACHE_DIR.mkdir(exist_ok=True)
        
        # Clear memory cache
        get_cached_tile_bytes.cache_clear()
        
        return {
            "status": "success",
            "message": "Cache cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")


@app.get("/tiles/{year}/{z}/{x}/{y}.png")
async def get_tile(year: int, z: int, x: int, y: int, colormap_name: Optional[str] = "trees"):
    """
    Serve a map tile from COG file (with disk + memory caching)
    
    Args:
        year: Dataset year (2010 or 2021)
        z: Zoom level
        x: Tile X coordinate
        y: Tile Y coordinate
        colormap_name: Colormap to apply (default: trees)
    
    Returns:
        PNG image tile
    """
    try:
        # Validate year
        if year not in COG_URLS:
            raise HTTPException(
                status_code=404,
                detail=f"Year {year} not found. Available years: {list(COG_URLS.keys())}"
            )
        
        # Check cache first (super fast - disk + memory)
        cached_bytes = get_cached_tile_bytes(year, z, x, y)
        if cached_bytes:
            return Response(
                content=cached_bytes,
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=2592000",  # 30 days
                    "Access-Control-Allow-Origin": "*",
                    "X-Cache": "HIT"
                }
            )
        
        cog_url = COG_URLS[year]
        logger.info(f"Generating tile: year={year}, z={z}, x={x}, y={y}")
        
        # Use pooled COG reader for faster connections
        cog = get_cog_reader(cog_url)
        
        try:
            # Read tile data
            img: ImageData = cog.tile(x, y, z)
            
            # Get the classification data (first band)
            data = img.data[0]  # Shape: (height, width)
            
            # Apply tree colormap
            tree_colormap = create_tree_colormap()
            rgba_data = apply_colormap(data, tree_colormap)
            
            # Convert to PIL Image
            img_pil = Image.fromarray(rgba_data, mode='RGBA')
            
            # Save to bytes
            buf = BytesIO()
            img_pil.save(buf, format='PNG', optimize=True)
            buf.seek(0)
            tile_bytes = buf.getvalue()
            
            # Save to cache for next time
            save_tile_to_cache(year, z, x, y, tile_bytes)
            
            return Response(
                content=tile_bytes,
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=2592000",  # 30 days
                    "Access-Control-Allow-Origin": "*",
                    "X-Cache": "MISS"
                }
            )
            
        except Exception as tile_error:
            logger.warning(f"Tile outside bounds or no data: {tile_error}")
            # Return transparent tile for out-of-bounds requests
            transparent = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            buf = BytesIO()
            transparent.save(buf, format='PNG')
            buf.seek(0)
            tile_bytes = buf.getvalue()
            
            # Cache transparent tiles too (saves network requests)
            save_tile_to_cache(year, z, x, y, tile_bytes)
            
            return Response(content=tile_bytes, media_type="image/png")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating tile: {e}")
        raise HTTPException(status_code=500, detail=f"Tile generation failed: {str(e)}")


@app.get("/tiles/{year}/preview.png")
async def get_preview(year: int, width: int = 512, height: int = 512):
    """
    Generate a preview image of the entire dataset
    
    Args:
        year: Dataset year
        width: Preview width in pixels
        height: Preview height in pixels
    
    Returns:
        PNG preview image
    """
    try:
        if year not in COG_URLS:
            raise HTTPException(
                status_code=404,
                detail=f"Year {year} not found"
            )
        
        cog_url = COG_URLS[year]
        logger.info(f"Generating preview for year {year}")
        
        # Use pooled reader
        cog = get_cog_reader(cog_url)
        
        # Get preview at specified resolution
        img: ImageData = cog.preview(width=width, height=height)
        data = img.data[0]
        
        # Apply colormap
        tree_colormap = create_tree_colormap()
        rgba_data = apply_colormap(data, tree_colormap)
        
        # Convert to PIL Image
        img_pil = Image.fromarray(rgba_data, mode='RGBA')
        
        # Save to bytes
        buf = BytesIO()
        img_pil.save(buf, format='PNG', optimize=True)
        buf.seek(0)
        
        return Response(
            content=buf.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"}
        )
            
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info/{year}")
async def get_dataset_info(year: int):
    """
    Get metadata about a dataset
    
    Args:
        year: Dataset year
    
    Returns:
        Dataset metadata
    """
    try:
        if year not in COG_URLS:
            raise HTTPException(status_code=404, detail=f"Year {year} not found")
        
        cog_url = COG_URLS[year]
        
        # Use pooled reader
        cog = get_cog_reader(cog_url)
        info = cog.info()
        
        return {
            "year": year,
            "url": cog_url,
            "bounds": info.bounds,
            "minzoom": info.minzoom,
            "maxzoom": info.maxzoom,
            "band_count": info.count,
            "dtype": str(info.dtype),
            "width": info.width,
            "height": info.height,
            "colorinterp": info.colorinterp,
            "nodata": info.nodata_value
        }
            
    except Exception as e:
        logger.error(f"Error getting dataset info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/coverage/{year}")
async def calculate_coverage(
    year: int,
    west: float,
    south: float,
    east: float,
    north: float
):
    """
    Calculate tree coverage percentage for a bounding box
    
    Args:
        year: Dataset year
        west, south, east, north: Bounding box coordinates (EPSG:4326)
    
    Returns:
        Tree coverage statistics
    """
    try:
        if year not in COG_URLS:
            raise HTTPException(status_code=404, detail=f"Year {year} not found")
        
        cog_url = COG_URLS[year]
        
        # Use pooled reader
        cog = get_cog_reader(cog_url)
        
        # Read data for bounding box
        img: ImageData = cog.part(
            bbox=[west, south, east, north],
            max_size=2048  # Limit resolution for performance
        )
        
        data = img.data[0]
        
        # Calculate tree coverage
        valid_pixels = np.sum(data > 0)  # Exclude nodata
        tree_pixels = np.sum(np.isin(data, TREE_CLASSES))
        
        coverage_percent = (tree_pixels / valid_pixels * 100) if valid_pixels > 0 else 0.0
        
        return {
            "year": year,
            "bounds": {"west": west, "south": south, "east": east, "north": north},
            "total_pixels": int(valid_pixels),
            "tree_pixels": int(tree_pixels),
            "coverage_percent": round(coverage_percent, 2),
            "resolution": "5ft (1.5m)" if year == 2010 else "6in (0.15m)"
        }
            
    except Exception as e:
        logger.error(f"Error calculating coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel
from typing import List, Tuple

class PolygonRequest(BaseModel):
    """Request body for polygon-based operations"""
    coordinates: List[List[float]]  # [[lon, lat], [lon, lat], ...]
    
class BoundsRequest(BaseModel):
    """Request body for bounds-based operations (rectangle or polygon)"""
    type: str  # "polygon" or "rectangle"
    coordinates: Optional[List[List[float]]] = None  # For polygon: [[lon, lat], ...]
    west: Optional[float] = None  # For rectangle
    south: Optional[float] = None
    east: Optional[float] = None
    north: Optional[float] = None


@app.post("/coverage/polygon/{year}")
async def calculate_polygon_coverage(year: int, polygon: PolygonRequest):
    """
    Calculate tree coverage percentage for a polygon area
    
    Args:
        year: Dataset year
        polygon: Polygon coordinates as [[lon, lat], [lon, lat], ...]
    
    Returns:
        Tree coverage statistics
    """
    try:
        if year not in COG_URLS:
            raise HTTPException(status_code=404, detail=f"Year {year} not found")
        
        from rasterio.features import geometry_mask
        from shapely.geometry import Polygon, mapping
        import rasterio
        from rasterio.warp import transform_bounds
        
        cog_url = COG_URLS[year]
        coords = polygon.coordinates
        
        logger.info(f"Calculating polygon coverage for year {year} with {len(coords)} vertices")
        
        # Create shapely polygon
        poly = Polygon(coords)
        
        # Get bounding box for initial data read
        minx, miny, maxx, maxy = poly.bounds
        
        # Use pooled reader
        cog = get_cog_reader(cog_url)
        
        # Read data for bounding box
        img: ImageData = cog.part(
            bbox=[minx, miny, maxx, maxy],
            max_size=4096  # Higher resolution for polygon
        )
        
        data = img.data[0]
        
        # Create mask from polygon
        # We need to transform polygon to pixel coordinates
        height, width = data.shape
        
        # Create affine transform from bounds to pixel coords
        from rasterio.transform import from_bounds
        transform = from_bounds(minx, miny, maxx, maxy, width, height)
        
        # Create mask (True = outside polygon, False = inside)
        mask = geometry_mask(
            [mapping(poly)],
            out_shape=(height, width),
            transform=transform,
            invert=True  # True = inside polygon
        )
        
        # Apply mask to data
        masked_data = data[mask]
        
        # Calculate tree coverage
        valid_pixels = np.sum(masked_data > 0)  # Exclude nodata
        tree_pixels = np.sum(np.isin(masked_data, TREE_CLASSES))
        
        coverage_percent = (tree_pixels / valid_pixels * 100) if valid_pixels > 0 else 0.0
        
        logger.info(f"Polygon coverage for {year}: {coverage_percent:.2f}%")
        
        return {
            "year": year,
            "bounds": {"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy},
            "polygon_vertices": len(coords),
            "total_pixels": int(valid_pixels),
            "tree_pixels": int(tree_pixels),
            "coverage_percent": round(coverage_percent, 2),
            "resolution": "5ft (1.5m)" if year == 2010 else "6in (0.15m)"
        }
            
    except Exception as e:
        logger.error(f"Error calculating polygon coverage: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/visualization/{year}")
async def get_polygon_visualization(year: int, bounds: BoundsRequest):
    """
    Generate a tree coverage visualization image for a polygon or rectangle
    
    Args:
        year: Dataset year
        bounds: Polygon or rectangle bounds
    
    Returns:
        PNG image with tree coverage visualization
    """
    try:
        if year not in COG_URLS:
            raise HTTPException(status_code=404, detail=f"Year {year} not found")
        
        from shapely.geometry import Polygon, mapping
        from rasterio.features import geometry_mask
        from rasterio.transform import from_bounds
        
        cog_url = COG_URLS[year]
        cog = get_cog_reader(cog_url)
        
        # Determine bounds based on type
        if bounds.type == "polygon" and bounds.coordinates:
            coords = bounds.coordinates
            poly = Polygon(coords)
            minx, miny, maxx, maxy = poly.bounds
            use_polygon_mask = True
            logger.info(f"Generating polygon visualization for year {year}")
        else:
            # Rectangle bounds
            minx, miny, maxx, maxy = bounds.west, bounds.south, bounds.east, bounds.north
            use_polygon_mask = False
            logger.info(f"Generating rectangle visualization for year {year}")
        
        # Read data for bounding box
        img: ImageData = cog.part(
            bbox=[minx, miny, maxx, maxy],
            max_size=2048  # Good resolution for visualization
        )
        
        data = img.data[0]
        height, width = data.shape
        
        # Apply polygon mask if needed
        if use_polygon_mask:
            transform = from_bounds(minx, miny, maxx, maxy, width, height)
            mask = geometry_mask(
                [mapping(poly)],
                out_shape=(height, width),
                transform=transform,
                invert=True  # True = inside polygon
            )
        else:
            mask = np.ones((height, width), dtype=bool)  # All valid
        
        # Create RGBA visualization
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Apply tree colormap with polygon mask
        tree_colormap = create_tree_colormap()
        for class_id, color in tree_colormap.items():
            class_mask = (data == class_id) & mask
            rgba[class_mask] = color
        
        # Set areas outside polygon to transparent
        rgba[~mask] = [0, 0, 0, 0]
        
        # Convert to PIL Image
        img_pil = Image.fromarray(rgba, mode='RGBA')
        
        # Save to bytes
        buf = BytesIO()
        img_pil.save(buf, format='PNG', optimize=True)
        buf.seek(0)
        
        # Calculate coverage stats
        masked_data = data[mask]
        valid_pixels = np.sum(masked_data > 0)
        tree_pixels = np.sum(np.isin(masked_data, TREE_CLASSES))
        coverage = (tree_pixels / valid_pixels * 100) if valid_pixels > 0 else 0.0
        
        return Response(
            content=buf.getvalue(),
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
                "X-Coverage-Percent": str(round(coverage, 2)),
                "X-Bounds": f"{minx},{miny},{maxx},{maxy}"
            }
        )
            
    except Exception as e:
        logger.error(f"Error generating visualization: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/coverage/bounds/{year}")
async def calculate_bounds_coverage(year: int, bounds: BoundsRequest):
    """
    Calculate tree coverage for either polygon or rectangle bounds
    
    Args:
        year: Dataset year
        bounds: BoundsRequest with type "polygon" or "rectangle"
    
    Returns:
        Tree coverage statistics
    """
    try:
        if year not in COG_URLS:
            raise HTTPException(status_code=404, detail=f"Year {year} not found")
        
        if bounds.type == "polygon" and bounds.coordinates:
            # Use polygon endpoint
            polygon_req = PolygonRequest(coordinates=bounds.coordinates)
            return await calculate_polygon_coverage(year, polygon_req)
        else:
            # Use rectangle endpoint
            return await calculate_coverage(
                year=year,
                west=bounds.west,
                south=bounds.south,
                east=bounds.east,
                north=bounds.north
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating bounds coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

