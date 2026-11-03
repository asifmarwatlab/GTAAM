"""rasterio is imported lazily so the rest of core works without it."""


def require_rasterio():
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover
        raise ImportError("rasterio is required for this operation: pip install rasterio") from exc
    return rasterio
