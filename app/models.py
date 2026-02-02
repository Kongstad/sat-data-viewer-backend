"""
Pydantic models for API requests and responses.
"""

from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """Supported output formats."""
    GEOTIFF = "geotiff"
    PNG = "png"


class DownloadRequest(BaseModel):
    """Request model for downloading a satellite tile."""
    
    collection: str = Field(
        ...,
        description="STAC collection ID (e.g., 'sentinel-2-l2a', 'landsat-c2-l2')",
        examples=["sentinel-2-l2a"]
    )
    item_id: str = Field(
        ...,
        description="STAC item ID",
        examples=["S2A_MSIL2A_20240101T104441_N0510_R008_T32UNF_20240101T134135"]
    )
    asset_key: str = Field(
        ...,
        description="Asset key/band name to download",
        examples=["visual", "B04", "B08"]
    )
    bbox: Optional[List[float]] = Field(
        None,
        description="Bounding box [minLon, minLat, maxLon, maxLat] for clipping",
        examples=[[10.0, 55.0, 10.5, 55.5]]
    )
    format: OutputFormat = Field(
        OutputFormat.GEOTIFF,
        description="Output format (geotiff or png)"
    )
    rescale: Optional[str] = Field(
        None,
        description="Rescale range for PNG visualization (e.g., '0,4000')",
        examples=["0,4000", "-2000,10000"]
    )
    colormap: Optional[str] = Field(
        None,
        description="Colormap name for PNG visualization (e.g., 'viridis', 'inferno')",
        examples=["viridis", "inferno", "rdylgn"]
    )
    turnstile_token: Optional[str] = Field(
        None,
        description="Cloudflare Turnstile token for bot protection"
    )


class DownloadResponse(BaseModel):
    """Response model with download information."""
    
    filename: str
    content_type: str
    file_size_bytes: int
    file_size_mb: float


class ErrorResponse(BaseModel):
    """Error response model."""
    
    detail: str
    error_type: Optional[str] = None


class CollectionInfo(BaseModel):
    """Information about a supported collection."""
    
    id: str
    name: str
    available_assets: List[str]


class AvailableAssetsResponse(BaseModel):
    """Response with available assets for download."""
    
    collections: List[CollectionInfo]
