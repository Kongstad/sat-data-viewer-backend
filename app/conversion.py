"""
Image conversion utilities - GeoTIFF to PNG conversion.
"""

import os
import numpy as np
from PIL import Image
import rasterio
from rasterio.plot import reshape_as_image
import matplotlib.pyplot as plt


class ConversionError(Exception):
    """Custom exception for conversion errors."""
    pass


def apply_colormap(data: np.ndarray, colormap: str = None, nodata_mask: np.ndarray = None) -> np.ndarray:
    """
    Apply a matplotlib colormap to single-band data.
    
    Args:
        data: Normalized array (0-255)
        colormap: Matplotlib colormap name
        nodata_mask: Boolean mask where True = nodata (will be black)
        
    Returns:
        RGB array (height, width, 3)
    """
    if colormap is None:
        # Return grayscale
        rgb = np.stack([data, data, data], axis=-1)
        if nodata_mask is not None:
            rgb[nodata_mask] = 0
        return rgb
    
    try:
        cmap = plt.get_cmap(colormap)
    except ValueError:
        # Try capitalizing common colormap names
        colormap_upper = colormap.replace('rdylgn', 'RdYlGn').replace('ylgnbu', 'YlGnBu').replace('ylorbr', 'YlOrBr')
        try:
            cmap = plt.get_cmap(colormap_upper)
        except ValueError:
            # Fallback to viridis if colormap not found
            cmap = plt.get_cmap('viridis')
    
    # Normalize to 0-1 range
    normalized = data / 255.0
    
    # Apply colormap (returns RGBA)
    colored = cmap(normalized)
    
    # Convert to RGB uint8
    rgb = (colored[:, :, :3] * 255).astype(np.uint8)
    
    # Set nodata pixels to black
    if nodata_mask is not None:
        rgb[nodata_mask] = 0
    
    return rgb


def rescale_array(arr: np.ndarray, rescale_range: str = None, nodata_value: float = 0) -> tuple[np.ndarray, np.ndarray]:
    """
    Rescale array based on specified range.
    
    Args:
        arr: Input array
        rescale_range: String like "0,4000" or "-2000,10000"
        nodata_value: Value to treat as nodata (default 0)
        
    Returns:
        Tuple of (rescaled array 0-255, nodata mask)
    """
    # Create nodata mask
    nodata_mask = np.isnan(arr) | (arr == nodata_value)
    
    if rescale_range is None:
        # Auto percentile scaling
        return normalize_array(arr, nodata_value=nodata_value)
    
    try:
        min_val, max_val = map(float, rescale_range.split(','))
    except:
        # Fallback to auto scaling
        return normalize_array(arr, nodata_value=nodata_value)
    
    # Clip to range
    clipped = np.clip(arr, min_val, max_val)
    
    # Scale to 0-255
    if max_val == min_val:
        return np.zeros_like(arr, dtype=np.uint8), nodata_mask
    
    scaled = ((clipped - min_val) / (max_val - min_val) * 255).astype(np.uint8)
    
    # Set nodata to 0 in output
    scaled[nodata_mask] = 0
    
    return scaled, nodata_mask


def normalize_array(arr: np.ndarray, percentile_clip: tuple = (2, 98), nodata_value: float = 0) -> tuple[np.ndarray, np.ndarray]:
    """
    Normalize array to 0-255 range with percentile clipping.
    
    Args:
        arr: Input numpy array
        percentile_clip: Tuple of (low, high) percentiles for clipping
        nodata_value: Value to treat as nodata (default 0)
        
    Returns:
        Tuple of (normalized uint8 array, nodata mask)
    """
    # Handle nodata/nan values
    nodata_mask = np.isnan(arr) | (arr == nodata_value)
    valid_mask = ~nodata_mask
    
    if not np.any(valid_mask):
        return np.zeros_like(arr, dtype=np.uint8), nodata_mask
    
    # Calculate percentiles on valid data
    low = np.percentile(arr[valid_mask], percentile_clip[0])
    high = np.percentile(arr[valid_mask], percentile_clip[1])
    
    if high == low:
        return np.zeros_like(arr, dtype=np.uint8), nodata_mask
    
    # Clip and normalize
    clipped = np.clip(arr, low, high)
    normalized = ((clipped - low) / (high - low) * 255).astype(np.uint8)
    
    # Set nodata to 0 in output
    normalized[nodata_mask] = 0
    
    return normalized, nodata_mask


def geotiff_to_png(
    input_path: str,
    output_path: str | None = None,
    bands: list[int] | None = None,
    rescale: str | None = None,
    colormap: str | None = None,
    progress_callback = None,
) -> tuple[str, int]:
    """
    Convert a GeoTIFF to PNG format with optional colormap.
    
    Args:
        input_path: Path to input GeoTIFF
        output_path: Optional output path (auto-generated if None)
        bands: Optional list of band indices to use (1-indexed)
        rescale: Rescale range as string (e.g., "0,4000")
        colormap: Matplotlib colormap name for single-band data
        progress_callback: Optional callback function(progress, step) for tracking
               
    Returns:
        Tuple of (output path, file size in bytes)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if progress_callback:
        progress_callback(82, "Converting to PNG...")
    
    logger.info(f"[CONVERT] Converting GeoTIFF to PNG (rescale={rescale}, colormap={colormap})...")
    
    if output_path is None:
        output_path = input_path.replace(".tif", ".png")
    
    try:
        with rasterio.open(input_path) as src:
            # Determine which bands to use
            num_bands = src.count
            
            if bands:
                # Use specified bands
                data = src.read(bands)
            elif num_bands >= 3:
                # Assume RGB (first 3 bands)
                data = src.read([1, 2, 3])
            else:
                # Single band
                data = src.read(1)
            
            # Get nodata value from source
            nodata_value = src.nodata if src.nodata is not None else 0
            
            # Process based on number of bands
            if len(data.shape) == 3 and data.shape[0] >= 3:
                # Multi-band RGB - normalize each band
                image_data = reshape_as_image(data)
                normalized = np.zeros_like(image_data, dtype=np.uint8)
                
                # Create combined nodata mask (any band has nodata)
                combined_nodata = np.zeros(image_data.shape[:2], dtype=bool)
                
                if rescale:
                    # Apply same rescale to all bands
                    for i in range(min(3, image_data.shape[2])):
                        norm_band, mask = rescale_array(image_data[:, :, i], rescale, nodata_value)
                        normalized[:, :, i] = norm_band
                        combined_nodata |= mask
                else:
                    # Auto normalize each band
                    for i in range(min(3, image_data.shape[2])):
                        norm_band, mask = normalize_array(image_data[:, :, i], nodata_value=nodata_value)
                        normalized[:, :, i] = norm_band
                        combined_nodata |= mask
                
                # Set nodata pixels to black
                normalized[combined_nodata] = 0
                
                # Create RGB image
                img = Image.fromarray(normalized[:, :, :3], mode="RGB")
                
            else:
                # Single band - apply colormap
                if rescale:
                    normalized, nodata_mask = rescale_array(data, rescale, nodata_value)
                else:
                    normalized, nodata_mask = normalize_array(data, nodata_value=nodata_value)
                
                if colormap:
                    # Apply colormap to get RGB, preserving nodata as black
                    rgb_data = apply_colormap(normalized, colormap, nodata_mask)
                    img = Image.fromarray(rgb_data, mode="RGB")
                else:
                    # Grayscale
                    img = Image.fromarray(normalized, mode="L")
            
            if progress_callback:
                progress_callback(92, "Saving PNG file...")
            
            # Save as PNG
            img.save(output_path, "PNG", optimize=True)
            
            file_size = os.path.getsize(output_path)
            file_size_mb = file_size / (1024 * 1024)
            logger.info(f"[CONVERT] PNG complete: {file_size_mb:.2f} MB")
            return output_path, file_size
            
    except Exception as e:
        raise ConversionError(f"Failed to convert to PNG: {str(e)}")
