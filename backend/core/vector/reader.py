"""Read vector files of the common formats and hand back GeoJSON in lon/lat (EPSG:4326).

Whatever the file is, the rest of the app always gets the same thing: a GeoJSON
FeatureCollection whose coordinates are longitude / latitude.

Read with the Python standard library only (nothing to install):
    .geojson .json      GeoJSON
    .kml .kmz           Google Earth
    .csv                a table with longitude / latitude columns (points)

Read with fiona (pip install fiona), which brings GDAL's readers:
    .shp                Shapefile (also a .zip that holds one)
    .gpkg               GeoPackage (first layer)
    .gpx                GPS tracks and waypoints
    .gml                GML
    .fgb                FlatGeobuf
    .tab .mif           MapInfo
"""
from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

BUILTIN = {".geojson", ".json", ".kml", ".kmz", ".csv"}
NEEDS_FIONA = {".shp", ".zip", ".gpkg", ".gpx", ".gml", ".fgb", ".tab", ".mif"}
SUPPORTED = sorted(BUILTIN | NEEDS_FIONA)

LON_NAMES = ("lon", "lng", "long", "longitude", "x", "easting")
LAT_NAMES = ("lat", "latitude", "y", "northing")
GEOJSON_TYPES = ("FeatureCollection", "Feature", "GeometryCollection")


def read_vector(path: str | Path) -> dict:
    """Read any supported vector file -> GeoJSON FeatureCollection in EPSG:4326."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".geojson", ".json"):
        data = _read_geojson(p)
    elif ext == ".kml":
        data = _kml_to_geojson(p.read_text(encoding="utf-8", errors="replace"))
    elif ext == ".kmz":
        data = _read_kmz(p)
    elif ext == ".csv":
        data = _read_csv(p)
    elif ext in NEEDS_FIONA:
        data = _read_with_fiona(p)
    else:
        raise ValueError(f"Unsupported vector format '{ext}'. Supported: {', '.join(SUPPORTED)}")
    if not data["features"] and ext not in (".geojson", ".json"):
        raise ValueError("The file was read, but it contains no features.")
    return data


# ---- GeoJSON ----------------------------------------------------------------
def _read_geojson(p: Path) -> dict:
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("type") not in GEOJSON_TYPES:
        raise ValueError("That file is not valid GeoJSON.")
    return _as_collection(data)


def _as_collection(data: dict) -> dict:
    if data["type"] == "FeatureCollection":
        return data
    if data["type"] == "Feature":
        return {"type": "FeatureCollection", "features": [data]}
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": g}
                         for g in data.get("geometries", [])]}


# ---- KML / KMZ --------------------------------------------------------------
def _read_kmz(p: Path) -> dict:
    with zipfile.ZipFile(p) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".kml")]
        if not names:
            raise ValueError("That KMZ file does not contain a .kml file.")
        text = z.read("doc.kml" if "doc.kml" in names else names[0]).decode("utf-8", errors="replace")
    return _kml_to_geojson(text)


def _tag(el) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _coords(text: str) -> list[list[float]]:
    out = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) >= 2:
            out.append([float(parts[0]), float(parts[1])] + ([float(parts[2])] if len(parts) > 2 and parts[2] else []))
    return out


def _kml_geometry(el) -> dict | None:
    kind = _tag(el)
    if kind == "Point":
        c = _coords(next((e.text for e in el.iter() if _tag(e) == "coordinates"), ""))
        return {"type": "Point", "coordinates": c[0]} if c else None
    if kind == "LineString":
        c = _coords(next((e.text for e in el.iter() if _tag(e) == "coordinates"), ""))
        return {"type": "LineString", "coordinates": c} if len(c) >= 2 else None
    if kind == "Polygon":
        rings = []
        for ring in el:
            if _tag(ring) in ("outerBoundaryIs", "innerBoundaryIs"):
                c = _coords(next((e.text for e in ring.iter() if _tag(e) == "coordinates"), ""))
                if len(c) >= 4:
                    rings.append(c)
        return {"type": "Polygon", "coordinates": rings} if rings else None
    if kind == "MultiGeometry":
        parts = [g for g in (_kml_geometry(c) for c in el
                             if _tag(c) in ("Point", "LineString", "Polygon", "MultiGeometry")) if g]
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else {"type": "GeometryCollection", "geometries": parts}
    return None


def _kml_to_geojson(text: str) -> dict:
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as exc:
        raise ValueError(f"That file is not valid KML: {exc}") from exc
    features = []
    for pm in root.iter():
        if _tag(pm) != "Placemark":
            continue
        props, geom = {}, None
        for child in pm:
            t = _tag(child)
            if t in ("name", "description"):
                props[t] = (child.text or "").strip()
            elif geom is None and t in ("Point", "LineString", "Polygon", "MultiGeometry"):
                geom = _kml_geometry(child)
        if geom:
            features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


# ---- CSV (points) -----------------------------------------------------------
def _number(v: str):
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in v and "e" not in v.lower() else f
    except (TypeError, ValueError):
        return v


def _read_csv(p: Path) -> dict:
    with p.open(newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = csv.DictReader(fh, dialect=dialect)
        cols = {(c or "").strip().lower(): c for c in (rows.fieldnames or [])}
        xc = next((cols[n] for n in LON_NAMES if n in cols), None)
        yc = next((cols[n] for n in LAT_NAMES if n in cols), None)
        if xc is None or yc is None:
            raise ValueError("A CSV needs longitude and latitude columns (for example 'lon' and 'lat').")
        features = []
        for row in rows:
            try:
                x, y = float(row[xc]), float(row[yc])
            except (TypeError, ValueError):
                continue
            props = {k: _number(v) for k, v in row.items() if k not in (xc, yc) and k is not None}
            features.append({"type": "Feature", "properties": props,
                             "geometry": {"type": "Point", "coordinates": [x, y]}})
    if features and not all(-180 <= f["geometry"]["coordinates"][0] <= 180
                            and -90 <= f["geometry"]["coordinates"][1] <= 90 for f in features):
        raise ValueError("The CSV coordinates are not longitude / latitude in degrees. "
                         "Save the points in EPSG:4326, or use a Shapefile / GeoPackage that carries its CRS.")
    return {"type": "FeatureCollection", "features": features}


# ---- everything GDAL can read (needs fiona) -----------------------------------
def _read_with_fiona(p: Path) -> dict:
    try:
        import fiona
        from fiona.model import to_dict
    except ImportError as exc:  # pragma: no cover
        raise ImportError(f"Reading '{p.suffix}' files needs fiona: pip install fiona") from exc
    from rasterio.warp import transform_geom

    source = f"/vsizip/{p.as_posix()}" if p.suffix.lower() == ".zip" else str(p)
    try:
        src = fiona.open(source)
    except Exception as exc:
        raise ValueError(f"Could not open that file as a vector dataset: {exc}") from exc
    with src:
        crs = src.crs
        is_lonlat = bool(crs) and crs.to_epsg() == 4326
        wkt = crs.to_wkt() if crs else None
        features = []
        for feat in src:
            f = to_dict(feat)
            geom = f.get("geometry")
            if not geom:
                continue
            if not is_lonlat and wkt:
                geom = transform_geom(wkt, "EPSG:4326", geom)
            features.append({"type": "Feature", "properties": f.get("properties") or {},
                             "geometry": geom})
    if not wkt and features and not _looks_like_degrees(features):
        raise ValueError("This file has no coordinate system (.prj missing?) and its coordinates are "
                         "not in degrees, so it cannot be placed on the map.")
    # JSON-safe (dates, bytes, ...) and plain lists instead of tuples
    return json.loads(json.dumps({"type": "FeatureCollection", "features": features}, default=str))


def _looks_like_degrees(features: list[dict]) -> bool:
    def walk(c):
        if c and isinstance(c[0], (int, float)):
            yield c
        else:
            for part in c:
                yield from walk(part)
    for f in features[:50]:
        g = f["geometry"]
        parts = g.get("geometries") or [g]
        for part in parts:
            for pt in walk(part.get("coordinates", [])):
                if not (-180 <= pt[0] <= 180 and -90 <= pt[1] <= 90):
                    return False
    return True
