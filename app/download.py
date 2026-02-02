"""
Download service - handles fetching tiles from Microsoft Planetary Computer.
"""

import os
import uuid
import httpx
import rasterio
from rasterio.windows import from_bounds
from rasterio.crs import CRS
import numpy as np

import planetary_computer as pc
from pystac_client import Client

from app.config import settings
from app.collections import is_valid_asset, get_collection_info


class DownloadError(Exception):
    """Custom exception for download errors."""
    pass


async def get_stac_item(collection: str, item_id: str) -> dict:
    """
    Fetch a STAC item from Microsoft Planetary Computer.
    
    Args:
        collection: STAC collection ID
        item_id: STAC item ID
        
    Returns:
        Signed STAC item dictionary
    """
    catalog = Client.open(
        settings.mpc_stac_url,
        modifier=pc.sign_inplace,
    )
    
    try:
        # Get the item directly
        item = catalog.get_collection(collection).get_item(item_id)
        if item is None:
            raise DownloadError(f"Item '{item_id}' not found in collection '{collection}'")
        return item.to_dict()
    except Exception as e:
        raise DownloadError(f"Failed to fetch STAC item: {str(e)}")


def get_signed_asset_url(item: dict, asset_key: str) -> str:
    """
    Get the signed URL for an asset.
    
    Args:
        item: STAC item dictionary (already signed)
        asset_key: Asset key to get URL for
        
    Returns:
        Signed URL string
    """
    if asset_key not in item.get("assets", {}):
        available = list(item.get("assets", {}).keys())
        raise DownloadError(
            f"Asset '{asset_key}' not found. Available assets: {available}"
        )
    
    return item["assets"][asset_key]["href"]


async def download_tile(
    collection: str,
    item_id: str,
    asset_key: str,
    bbox: list[float] | None = None,
    progress_callback = None,
) -> tuple[str, int]:
    """
    Download a satellite tile from Microsoft Planetary Computer.
    
    Args:
        collection: STAC collection ID
        item_id: STAC item ID
        asset_key: Asset/band to download
        bbox: Optional bounding box [minLon, minLat, maxLon, maxLat].
              If provided, clips the tile to this extent.
              If None, downloads the FULL tile (recommended for complete downloads).
              
              NOTE: For downloading complete tiles, pass None or the tile's 
              own bbox from the STAC item. Do NOT pass the search viewport
              bbox, as that would only get a small clip of the tile.
        progress_callback: Optional callback function(progress, step) for tracking
        
    Returns:
        Tuple of (output file path, file size in bytes)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if progress_callback:
        progress_callback(5, "Validating request...")
    
    # Validate asset
    if not is_valid_asset(collection, asset_key):
        collection_info = get_collection_info(collection)
        if collection_info:
            available = list(collection_info["assets"].keys())
            raise DownloadError(
                f"Asset '{asset_key}' not available for {collection}. "
                f"Available: {available}"
            )
        else:
            raise DownloadError(f"Unknown collection: {collection}")
    
    # Get signed STAC item
    if progress_callback:
        progress_callback(10, "Fetching STAC metadata...")
    logger.info(f"[STAC] Fetching item from Microsoft Planetary Computer...")
    item = await get_stac_item(collection, item_id)
    
    # Get signed URL for the asset
    if progress_callback:
        progress_callback(15, "Getting signed URL...")
    logger.info(f"[STAC] Getting signed URL for asset: {asset_key}")
    asset_url = get_signed_asset_url(item, asset_key)
    logger.info(f"[STAC] Signed URL obtained")
    
    # Generate output filename
    output_id = str(uuid.uuid4())[:8]
    output_filename = f"{collection}_{item_id}_{asset_key}_{output_id}.tif"
    output_path = os.path.join(settings.tmp_dir, output_filename)
    
    # Download and optionally clip the raster
    if progress_callback:
        progress_callback(20, "Opening raster from MPC...")
    logger.info(f"[RASTER] Starting download from MPC...")
    try:
        with rasterio.open(asset_url) as src:
            logger.info(f"[RASTER] Info: {src.width}x{src.height} pixels, {src.count} band(s), CRS: {src.crs}")
            
            if progress_callback:
                progress_callback(30, "Reading raster data...")
            if bbox:
                logger.info(f"[RASTER] Clipping to bounding box: {bbox}")
                # Transform bbox to raster CRS if needed
                dst_crs = src.crs
                
                # Create window from bounds (assuming bbox is in EPSG:4326)
                # Transform bbox to source CRS
                from rasterio.warp import transform_bounds
                
                src_bounds = transform_bounds(
                    CRS.from_epsg(4326),
                    dst_crs,
                    *bbox
                )
                
                # Get window for the bounds
                window = from_bounds(*src_bounds, src.transform)
                
                # Read the windowed data
                logger.info(f"[RASTER] Reading windowed data...")
                data = src.read(window=window)
                
                if progress_callback:
                    progress_callback(60, "Processing clipped data...")
                
                # Update transform for the window
                transform = rasterio.windows.transform(window, src.transform)
                
                # Write clipped raster
                profile = src.profile.copy()
                profile.update(
                    height=data.shape[1],
                    width=data.shape[2],
                    transform=transform,
                    driver="GTiff",
                    compress="deflate",
                )
                
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(data)
            else:
                # Download full tile
                logger.info(f"[RASTER] Downloading full tile (no clipping)")
                data = src.read()
                
                if progress_callback:
                    progress_callback(60, "Processing full tile data...")
                
                profile = src.profile.copy()
                profile.update(
                    driver="GTiff",
                    compress="deflate",
                )
                
                if progress_callback:
                    progress_callback(70, "Saving GeoTIFF...")
                
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(data)
        
        # Get file size
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"[FILE] GeoTIFF saved: {file_size_mb:.2f} MB")
        
        if progress_callback:
            progress_callback(80, "Verifying file...")
        
        # Check file size limit
        max_size = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            logger.warning(f"[FILE] Too large: {file_size_mb:.1f} MB (max: {settings.max_file_size_mb} MB)")
            os.remove(output_path)
            raise DownloadError(
                f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds "
                f"maximum allowed ({settings.max_file_size_mb} MB)"
            )
        
        logger.info(f"[DOWNLOAD] Complete: {output_filename}")
        return output_path, file_size
        
    except rasterio.errors.RasterioError as e:
        raise DownloadError(f"Failed to process raster: {str(e)}")
    except Exception as e:
        if "DownloadError" in type(e).__name__:
            raise
        raise DownloadError(f"Download failed: {str(e)}")


def cleanup_file(file_path: str) -> None:
    """Remove a temporary file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass  # Ignore cleanup errors
