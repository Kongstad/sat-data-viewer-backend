"""
Collection configuration - mirrors the frontend's collections.js.
Defines available assets/bands for each supported satellite collection.
"""

# Available assets for each collection that users can download
# These match the bands exposed in the sat-data-viewer frontend
COLLECTION_ASSETS = {
    "sentinel-2-l2a": {
        "name": "Sentinel-2 Level-2A",
        "assets": {
            "visual": "True Color (RGB)",
            "B02": "Blue (490nm)",
            "B03": "Green (560nm)",
            "B04": "Red (665nm)",
            "B05": "Red Edge (705nm)",
            "B08": "NIR (842nm)",
            "B11": "SWIR (1610nm)",
            "SCL": "Scene Classification",
        }
    },
    "landsat-c2-l2": {
        "name": "Landsat Collection 2 Level-2",
        "assets": {
            "red": "Red",
            "green": "Green",
            "blue": "Blue",
            "nir08": "NIR",
            "swir16": "SWIR 1.6μm",
            "lwir11": "Thermal (LWIR 11μm)",
            "qa_pixel": "Quality Assessment",
        }
    },
    "sentinel-1-grd": {
        "name": "Sentinel-1 GRD",
        "disabled": True,
        "disabled_reason": "SAR tiles are too large (1.2 GB per band)",
        "assets": {
            "vv": "VV Polarization",
            "vh": "VH Polarization",
        }
    },
    "sentinel-1-rtc": {
        "name": "Sentinel-1 RTC",
        "disabled": True,
        "disabled_reason": "SAR tiles are too large (1.2 GB per band)",
        "assets": {
            "vv": "VV Polarization",
            "vh": "VH Polarization",
        }
    },
    "modis-09A1-061": {
        "name": "MODIS Surface Reflectance",
        "assets": {
            "sur_refl_b01": "Red (620-670nm)",
            "sur_refl_b02": "NIR (841-876nm)",
            "sur_refl_b03": "Blue (459-479nm)",
            "sur_refl_b04": "Green (545-565nm)",
        }
    },
    "modis-13Q1-061": {
        "name": "MODIS Vegetation Indices",
        "assets": {
            "250m_16_days_NDVI": "NDVI",
            "250m_16_days_EVI": "EVI",
        }
    },
    "cop-dem-glo-30": {
        "name": "Copernicus DEM 30m",
        "assets": {
            "data": "Elevation",
        }
    },
}


def get_collection_info(collection_id: str) -> dict | None:
    """Get collection information by ID."""
    return COLLECTION_ASSETS.get(collection_id)


def is_collection_disabled(collection_id: str) -> tuple[bool, str | None]:
    """Check if downloads are disabled for a collection.
    
    Returns:
        Tuple of (is_disabled, reason)
    """
    collection = COLLECTION_ASSETS.get(collection_id)
    if collection and collection.get("disabled"):
        return True, collection.get("disabled_reason", "Downloads disabled")
    return False, None


def get_available_assets(collection_id: str) -> list[str]:
    """Get list of available asset keys for a collection."""
    collection = COLLECTION_ASSETS.get(collection_id)
    if collection:
        return list(collection["assets"].keys())
    return []


def is_valid_asset(collection_id: str, asset_key: str) -> bool:
    """Check if an asset is valid for a given collection."""
    return asset_key in get_available_assets(collection_id)


def get_all_collections() -> list[dict]:
    """Get information about all supported collections."""
    return [
        {
            "id": coll_id,
            "name": info["name"],
            "available_assets": list(info["assets"].keys())
        }
        for coll_id, info in COLLECTION_ASSETS.items()
    ]
