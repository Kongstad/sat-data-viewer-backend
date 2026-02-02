# Satellite Data Viewer Backend

A FastAPI backend for downloading satellite imagery from Microsoft Planetary Computer, deployed on AWS Lambda.

## Features

- Download satellite tiles as GeoTIFF or PNG
- Support for Sentinel-2, Landsat, Sentinel-1 SAR, HLS, MODIS, and Copernicus DEM
- Microsoft Planetary Computer STAC API integration
- Cloudflare Turnstile bot protection
- Rate limiting (1 request/minute per IP)
- Download quotas (5000 MB/hour)
- AWS Lambda deployment (up to 1.5GB temporary storage)

## Supported Collections

| Collection | Bands Available |
|------------|-----------------|
| Sentinel-2 L2A | TCI (True Color), B04 (Red), B03 (Green), B02 (Blue), B08 (NIR), B05 (Red Edge), SCL (Scene Classification) |
| Landsat Collection 2 | Red, Green, Blue, NIR, SWIR16, SWIR22, Thermal, QA |
| Sentinel-1 GRD | VV, VH (downloads disabled due to file size) |
| HLS (Harmonized Landsat Sentinel-2) | Red, Green, Blue, NIR, SWIR |
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
  "format": "geotiff",
  "rescale": "0,4000",
  "colormap": "viridis",
  "turnstile_token": "..."
}
```

**Parameters:**
- `collection`: STAC collection ID
- `item_id`: STAC item ID
- `asset_key`: Asset/band name
- `bbox`: Optional bounding box [minLon, minLat, maxLon, maxLat]
- `format`: `geotiff` or `png`
- `rescale`: Optional rescale range for PNG (e.g., "0,4000")
- `colormap`: Optional matplotlib colormap for single-band PNG
- `turnstile_token`: Cloudflare Turnstile token (required for bot protection)

**Response:** Binary file stream with appropriate Content-Type header.

### GET /health

Health check endpoint. Returns `{"status":"healthy","version":"0.1.0"}`.

### GET /collections

Get list of all supported collections and their available assets.

## Protection & Rate Limiting

- **Cloudflare Turnstile**: Bot protection on all download requests
- **Rate Limiting**: 1 request per minute per IP address
- **Download Quotas**: 5000 MB per hour per IP address
- **File Size Limit**: 1500 MB maximum per file

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

Deployed via Docker container image to AWS Lambda with Function URL.

### Manual Deployment

1. **Build Docker image:**
```bash
docker build -t sat-data-viewer-backend .
```

2. **Tag for ECR:**
```bash
docker tag sat-data-viewer-backend:latest <account-id>.dkr.ecr.<region>.amazonaws.com/sat-data-viewer-backend:latest
```

3. **Push to ECR:**
```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/sat-data-viewer-backend:latest
```

4. **Get amd64 digest for Lambda:**
```bash
aws ecr batch-get-image --repository-name sat-data-viewer-backend --region <region> --image-ids imageTag=latest --accepted-media-types "application/vnd.oci.image.index.v1+json" --query 'images[0].imageManifest' --output text
```

5. **Update Lambda:** Use the amd64 digest (not the multi-platform manifest) from the output.

### Lambda Configuration

- **Memory**: 3008 MB
- **Timeout**: 180 seconds (3 minutes)
- **Ephemeral Storage**: 1536 MB
- **Environment Variables**:
  - `TURNSTILE_SECRET_KEY`: Cloudflare Turnstile secret key
  - `ALLOWED_ORIGINS`: CORS origins (optional)

### Function URL CORS

Configure CORS on the Lambda Function URL:
- **Allow origin**: `https://kongstad.github.io`
- **Allow methods**: GET, POST
- **Allow headers**: `*`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | `*` |
| `MAX_FILE_SIZE_MB` | Maximum file size in MB | `1500` |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret key | `""` |
| `MPC_STAC_URL` | Microsoft Planetary Computer STAC URL | `https://planetarycomputer.microsoft.com/api/stac/v1` |

## Architecture

- **FastAPI**: Web framework with async support
- **Mangum**: ASGI adapter for AWS Lambda
- **Rasterio**: Geospatial data processing
- **Matplotlib**: Colormap support for PNG visualization
- **HTTPX**: Async HTTP client for STAC API
- **Microsoft Planetary Computer**: Free satellite data source

## License

MIT
