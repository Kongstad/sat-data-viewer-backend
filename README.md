# Satellite Data Viewer Backend

FastAPI service for downloading satellite imagery from Microsoft Planetary Computer. Deployed serverless on AWS Lambda with Docker.

> **Note:** Download functionality operates in controlled mode - the backend is enabled during demonstrations to manage AWS costs. Files are automatically deleted from S3 after 10 minutes for security and cost optimization.

## Quick Start

```bash
# Local development
uv sync --link-mode=copy
uv run python run_local.py

# Visit http://localhost:8000/docs for API documentation
```

## Features

- Download satellite tiles as GeoTIFF
- Support for Sentinel-2, Landsat, HLS, MODIS, DEM
- Cloudflare Turnstile bot protection
- Rate limiting (10 req/min per IP)
- Download quotas (5 GB/hour)
- AWS Lambda with up to 1.5GB storage
- Auto-deletion of files (10 min via EventBridge, 1 day S3 lifecycle backup)

## Supported Collections

| Collection | Bands Available |
|------------|-----------------|
| Sentinel-2 L2A | TCI (True Color), B04 (Red), B03 (Green), B02 (Blue), B08 (NIR), B05 (Red Edge), SCL (Scene Classification) |
| Landsat Collection 2 | Red, Green, Blue, NIR, SWIR16, SWIR22, Thermal, QA |
| Sentinel-1 GRD | VV, VH (downloads disabled due to file size) |
| HLS (Harmonized Landsat Sentinel-2) | Red, Green, Blue, NIR, SWIR |
| MODIS | Surface Reflectance bands |
| Copernicus DEM | Elevation |

## API

### `POST /download`

Download satellite tiles as GeoTIFF.

```json
{
  "collection": "sentinel-2-l2a",
  "item_id": "S2A_MSIL2A_20240101T104441_R008_T32UNF",
  "asset_key": "B04",
  "turnstile_token": "<cloudflare_turnstile_token>"
}
```

### `GET /health`

Health check returning `{"status":"healthy","version":"0.1.0"}`.

### `GET /collections`

List all supported collections and available bands.

## Protection

- **Bot Protection**: Cloudflare Turnstile verification
- **Rate Limiting**: 10 requests/minute per IP
- **Download Quotas**: 5 GB/hour per IP
- **File Size Limit**: 1.5 GB max
- **Auto-Cleanup**: Files deleted after 10 minutes (S3 lifecycle backup at 1 day)

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

## Deployment

### AWS Lambda

```bash
# Build and tag
docker build -t sat-data-viewer-backend .
docker tag sat-data-viewer-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/sat-data-viewer-backend:latest

# Push to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker push <account>.dkr.ecr.<region>.amazonaws.com/sat-data-viewer-backend:latest

# Get platform-specific digest
aws ecr batch-get-image --repository-name sat-data-viewer-backend --region <region> \
  --image-ids imageTag=latest --accepted-media-types "application/vnd.oci.image.index.v1+json" \
  --query 'images[0].imageManifest' --output text
```

Use the `amd64` digest when updating Lambda (not the multi-platform manifest).

**Lambda Config:**
- Memory: 3008 MB
- Timeout: 180s
- Ephemeral storage: 1536 MB
- Environment: `TURNSTILE_SECRET_KEY`

**Function URL CORS:**
- Origin: `https://kongstad.github.io`
- Methods: GET, POST
- Headers: `*`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TURNSTILE_SECRET_KEY` | `""` | Cloudflare Turnstile secret |
| `ALLOWED_ORIGINS` | `*` | CORS origins (comma-separated) |
| `MAX_FILE_SIZE_MB` | `1500` | Max file size limit |

## Tech Stack

- **FastAPI** - Web framework with async support
- **Mangum** - ASGI adapter for Lambda
- **Rasterio** - Geospatial data processing (GDAL)
- **Boto3** - AWS S3 uploads and EventBridge scheduling
- **HTTPX** - Async STAC API client

## License

MIT - See [LICENSE](LICENSE)
