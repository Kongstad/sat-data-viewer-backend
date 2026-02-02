# Satellite Data Viewer Backend

A FastAPI backend for downloading satellite imagery from Microsoft Planetary Computer, deployed on AWS Lambda.

## Features

- Download satellite tiles as GeoTIFF or PNG
- Support for Sentinel-2, Landsat, Sentinel-1 SAR, MODIS, and Copernicus DEM
- Microsoft Planetary Computer STAC API integration
- AWS Lambda deployment (up to 1.5GB temporary storage)

## Supported Collections

| Collection | Bands Available |
|------------|-----------------|
| Sentinel-2 L2A | TCI (True Color), B04 (Red), B03 (Green), B02 (Blue), B08 (NIR), SCL (Scene Classification) |
| Landsat Collection 2 | Red, Green, Blue, NIR, SWIR16, QA |
| Sentinel-1 GRD | VV, VH |
| MODIS | Surface Reflectance bands |
| Copernicus DEM | Elevation |

## API Endpoints

### POST /download

Download a satellite tile in GeoTIFF or PNG format.

**Request Body:**
```json
{
  "collection": "sentinel-2-l2a",
  "item_id": "S2A_MSIL2A_20240101T...",
  "asset_key": "visual",
  "bbox": [10.0, 55.0, 10.5, 55.5],
  "format": "geotiff"
}
```

**Response:** Binary file stream with appropriate Content-Type header.

### GET /health

Health check endpoint.

## Local Development

```bash
# Install dependencies with UV
uv sync --link-mode=copy

# Run locally
uv run python run_local.py
```

Or using traditional pip:

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .

# Run locally
python run_local.py
```

## AWS Lambda Deployment

See [.github/workflows/deploy.yml](.github/workflows/deploy.yml) for automated deployment.

### Manual Deployment

1. Build Docker image:
```bash
docker build -t sat-data-viewer-backend .
```

2. Push to ECR and deploy to Lambda.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | `*` |
| `MAX_FILE_SIZE_MB` | Maximum file size in MB | `1500` |

## License

MIT
