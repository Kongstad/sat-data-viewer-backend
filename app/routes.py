"""
API routes for the satellite data download service.
"""

import os
from typing import Generator
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models import (
    DownloadRequest,
    DownloadResponse,
    ErrorResponse,
    AvailableAssetsResponse,
    OutputFormat,
)
from app.download import download_tile, cleanup_file, DownloadError
from app.conversion import geotiff_to_png, ConversionError
from app.collections import get_all_collections, COLLECTION_ASSETS, is_collection_disabled
from app.utils import get_content_type, generate_filename, format_file_size
from app.middleware import tracker
from app.turnstile import verify_turnstile_token


router = APIRouter()

# Chunk size for streaming (64KB)
CHUNK_SIZE = 64 * 1024


def file_iterator(file_path: str, cleanup: bool = True) -> Generator[bytes, None, None]:
    """
    Generator that streams file contents in chunks.
    Optionally cleans up the file after streaming.
    """
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk
    finally:
        if cleanup and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass  # Best effort cleanup


@router.get(
    "/collections",
    response_model=AvailableAssetsResponse,
    summary="Get available collections and assets",
)
async def get_collections():
    """
    Get list of all supported collections and their available assets.
    This helps the frontend know what bands can be downloaded.
    """
    collections = get_all_collections()
    return AvailableAssetsResponse(collections=[
        {
            "id": c["id"],
            "name": c["name"],
            "available_assets": c["available_assets"]
        }
        for c in collections
    ])


@router.get(
    "/collections/{collection_id}/assets",
    summary="Get available assets for a collection",
)
async def get_collection_assets(collection_id: str):
    """
    Get detailed asset information for a specific collection.
    """
    if collection_id not in COLLECTION_ASSETS:
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_id}' not found"
        )
    
    collection = COLLECTION_ASSETS[collection_id]
    return {
        "collection_id": collection_id,
        "name": collection["name"],
        "assets": collection["assets"]
    }


@router.post(
    "/download",
    summary="Download a satellite tile",
    responses={
        200: {"description": "File download"},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def download(request: DownloadRequest, http_request: Request):
    """
    Download a satellite tile from Microsoft Planetary Computer.
    
    The tile is fetched from MPC, optionally clipped to bbox, and returned
    as either GeoTIFF or PNG format.
    
    Note: File size is only known after download completes (MPC doesn't 
    provide size estimates for partial/clipped downloads).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Get client IP for tracking
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    logger.info(f"\n{'='*60}")
    logger.info(f"[REQUEST] NEW DOWNLOAD REQUEST from {client_ip}")
    logger.info(f"[REQUEST] Collection: {request.collection}")
    logger.info(f"[REQUEST] Asset: {request.asset_key}")
    logger.info(f"[REQUEST] Format: {request.format.value}")
    if request.rescale:
        logger.info(f"[REQUEST] Rescale: {request.rescale}")
    if request.colormap:
        logger.info(f"[REQUEST] Colormap: {request.colormap}")
    logger.info(f"{'='*60}")
    
    # Verify Turnstile token (bot protection)
    if not await verify_turnstile_token(request.turnstile_token, client_ip):
        logger.warning(f"[REJECTED] Turnstile verification failed for {client_ip}")
        raise HTTPException(status_code=403, detail="Security verification failed. Please refresh and try again.")
    
    # Check if collection is disabled
    disabled, reason = is_collection_disabled(request.collection)
    if disabled:
        logger.warning(f"[REJECTED] Collection {request.collection} is disabled: {reason}")
        raise HTTPException(status_code=400, detail=reason)
    
    output_tif = None
    output_png = None
    
    try:
        # Check if client disconnected before starting
        if await http_request.is_disconnected():
            logger.info(f"[CANCELLED] Client disconnected before download started")
            return None
        
        # Download the tile as GeoTIFF
        output_tif, tif_size = await download_tile(
            collection=request.collection,
            item_id=request.item_id,
            asset_key=request.asset_key,
            bbox=request.bbox,
        )
        
        # Check if client disconnected after download
        if await http_request.is_disconnected():
            logger.info(f"[CANCELLED] Client disconnected after download, cleaning up")
            cleanup_file(output_tif)
            return None
        
        # Generate download filename
        filename = generate_filename(
            request.collection,
            request.item_id,
            request.asset_key,
            request.format.value,
        )
        
        if request.format == OutputFormat.PNG:
            # Check before conversion (can be slow)
            if await http_request.is_disconnected():
                logger.info(f"[CANCELLED] Client disconnected before PNG conversion, cleaning up")
                cleanup_file(output_tif)
                return None
            
            # Convert to PNG
            output_png, png_size = geotiff_to_png(
                output_tif,
                rescale=request.rescale,
                colormap=request.colormap
            )
            
            # Track download size
            tracker.record_download(client_ip, png_size)
            logger.info(f"[TRACKING] Recorded {png_size / (1024*1024):.2f} MB download for {client_ip}")
            
            # Clean up the intermediate GeoTIFF
            cleanup_file(output_tif)
            
            # Final check before sending
            if await http_request.is_disconnected():
                logger.info(f"[CANCELLED] Client disconnected after conversion, cleaning up")
                cleanup_file(output_png)
                return None
            
            logger.info(f"[RESPONSE] Streaming PNG to client: {filename}")
            # Stream PNG with cleanup
            return StreamingResponse(
                file_iterator(output_png, cleanup=True),
                media_type="image/png",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(png_size),
                }
            )
        else:
            # Track download size
            tracker.record_download(client_ip, tif_size)
            logger.info(f"[TRACKING] Recorded {tif_size / (1024*1024):.2f} MB download for {client_ip}")
            
            # Stream GeoTIFF with cleanup
            logger.info(f"[RESPONSE] Streaming GeoTIFF to client: {filename}")
            return StreamingResponse(
                file_iterator(output_tif, cleanup=True),
                media_type="image/tiff",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(tif_size),
                }
            )
            
    except DownloadError as e:
        # Clean up any partial files
        if output_tif:
            cleanup_file(output_tif)
        if output_png:
            cleanup_file(output_png)
            
        raise HTTPException(status_code=400, detail=str(e))
        
    except ConversionError as e:
        if output_tif:
            cleanup_file(output_tif)
        if output_png:
            cleanup_file(output_png)
            
        raise HTTPException(status_code=500, detail=str(e))
        
    except Exception as e:
        if output_tif:
            cleanup_file(output_tif)
        if output_png:
            cleanup_file(output_png)
            
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@router.post(
    "/download/info",
    response_model=DownloadResponse,
    summary="Download a tile and get file info",
)
async def download_info(request: DownloadRequest):
    """
    Download a tile and return file information without streaming.
    Useful for getting file size after download completes.
    
    Note: This still performs the full download - file size cannot be
    estimated before downloading from MPC.
    """
    output_tif = None
    output_png = None
    
    try:
        output_tif, tif_size = await download_tile(
            collection=request.collection,
            item_id=request.item_id,
            asset_key=request.asset_key,
            bbox=request.bbox,
        )
        
        filename = generate_filename(
            request.collection,
            request.item_id,
            request.asset_key,
            request.format.value,
        )
        
        if request.format == OutputFormat.PNG:
            output_png, final_size = geotiff_to_png(output_tif)
            cleanup_file(output_tif)
            content_type = "image/png"
        else:
            final_size = tif_size
            content_type = "image/tiff"
        
        return DownloadResponse(
            filename=filename,
            content_type=content_type,
            file_size_bytes=final_size,
            file_size_mb=round(final_size / (1024 * 1024), 2),
        )
        
    finally:
        # Clean up temporary files
        if output_tif and os.path.exists(output_tif):
            cleanup_file(output_tif)
        if output_png and os.path.exists(output_png):
            cleanup_file(output_png)
