# FastAPI Tile Server Backend

Backend service for serving COG (Cloud Optimized GeoTIFF) tiles for the Tree Cover Analysis application.

## 📁 Structure

```
backend/
├── __init__.py           # Package initialization
├── api.py                # FastAPI application
├── cog_registry.py       # COG dataset registry
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker configuration
└── README.md             # This file
```

## 🚀 Quick Start

### Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### Run the Server
```bash
# From project root
uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Or run directly:
```bash
# From project root
python -m backend.api
```

### Access API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📡 API Endpoints

### Health Check
```
GET /
```

### Tile Endpoint (XYZ)
```
GET /tiles/{year}/{z}/{x}/{y}.png
```

### Preview Image
```
GET /tiles/{year}/preview.png?width=512&height=512
```

### Dataset Info
```
GET /info/{year}
```

### Coverage Calculation
```
GET /coverage/{year}?west=-74.01&south=40.72&east=-74.00&north=40.73
```

## 🐳 Docker

### Build
```bash
cd backend
docker build -t tree-cover-api .
```

### Run
```bash
docker run -p 8000:8000 tree-cover-api
```

## 🧪 Testing

From project root:
```bash
python test_tile_server.py
```

## 📦 Dependencies

- **FastAPI** - Web framework
- **uvicorn** - ASGI server
- **rio-tiler** - COG tile generation
- **rasterio** - Raster I/O
- **Pillow** - Image processing
- **numpy** - Array operations

## 🔧 Configuration

COG URLs are configured in `cog_registry.py`:

```python
COG_URLS = {
    2010: "https://storage.googleapis.com/raster_datam/landcover_2010_nyc_05ft_cog.tif",
    2021: "https://storage.googleapis.com/raster_datam/landcover_nyc_2021_6in_cog.tif",
}
```

## 📝 License

Part of the Tree Cover Analysis project.

