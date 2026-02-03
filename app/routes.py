"""
API routes for the satellite data download service.
"""

import os
import uuid
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.models import (
    DownloadRequest,
    ErrorResponse,
    AvailableAssetsResponse,
)
from app.download import download_tile, cleanup_file, DownloadError
from app.collections import get_all_collections, COLLECTION_ASSETS, is_collection_disabled
from app.utils import generate_filename
from app.middleware import tracker
from app.turnstile import verify_turnstile_token
from app.s3_utils import upload_to_s3


router = APIRouter()
logger = logging.getLogger(__name__)


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
    as a GeoTIFF via S3 presigned URL.
    
    Note: File size is only known after download completes (MPC doesn't 
    provide size estimates for partial/clipped downloads).
    """
    # Get client IP for tracking
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    logger.info(f"\n{'='*60}")
    logger.info(f"[REQUEST] NEW DOWNLOAD REQUEST from {client_ip}")
    logger.info(f"[REQUEST] Collection: {request.collection}")
    logger.info(f"[REQUEST] Asset: {request.asset_key}")
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
        
        # Generate download filename (always GeoTIFF)
        filename = generate_filename(
            request.collection,
            request.item_id,
            request.asset_key,
            "geotiff",
        )
        
        # Track download size
        tracker.record_download(client_ip, tif_size)
        logger.info(f"[TRACKING] Recorded {tif_size / (1024*1024):.2f} MB download for {client_ip}")
        
        # Upload GeoTIFF to S3 and get presigned URL
        logger.info(f"[RESPONSE] Uploading GeoTIFF to S3: {filename}")
        s3_key = f"downloads/{uuid.uuid4()}/{filename}"
        presigned_url = upload_to_s3(output_tif, s3_key)
        
        # Clean up local file
        cleanup_file(output_tif)
        
        return JSONResponse({
            "download_url": presigned_url,
            "filename": filename,
            "size_bytes": tif_size,
            "expires_in_seconds": 600
        })
            
    except DownloadError as e:
        # Clean up any partial files
        if output_tif:
            cleanup_file(output_tif)
            
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        if output_tif:
            cleanup_file(output_tif)
            
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
