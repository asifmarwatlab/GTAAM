"""Reading vector files of different formats gives GeoJSON in lon/lat."""
import json
import zipfile

import pytest

from core.vector.reader import SUPPORTED, read_vector

POINT = {"type": "Point", "coordinates": [73.0, 33.5]}
LINE = {"type": "LineString", "coordinates": [[73.0, 33.5], [73.1, 33.6], [73.2, 33.55]]}
POLY = {"type": "Polygon", "coordinates": [[[73.0, 33.0], [73.2, 33.0], [73.2, 33.2], [73.0, 33.2], [73.0, 33.0]]]}


def _write(path, driver, geom, schema_geom, crs="EPSG:4326", records=None):
    fiona = pytest.importorskip("fiona")
    schema = {"geometry": schema_geom, "properties": {"name": "str", "height": "int"}}
    with fiona.open(path, "w", driver=driver, schema=schema, crs=crs) as out:
        for i, g in enumerate(records or [geom]):
            out.write({"type": "Feature", "geometry": g, "properties": {"name": f"f{i}", "height": i}})


def test_supported_list_names_the_essentials():
    for ext in (".geojson", ".shp", ".gpkg", ".kml", ".gpx", ".csv", ".zip"):
        assert ext in SUPPORTED


def test_geojson_feature_is_wrapped_in_a_collection(tmp_path):
    p = tmp_path / "a.geojson"
    p.write_text(json.dumps({"type": "Feature", "properties": {}, "geometry": POINT}))
    out = read_vector(p)
    assert out["type"] == "FeatureCollection" and len(out["features"]) == 1


def test_bad_geojson_is_rejected(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"hello": "world"}))
    with pytest.raises(ValueError, match="not valid GeoJSON"):
        read_vector(p)


def test_kml_points_lines_polygons(tmp_path):
    kml = """<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
    <Placemark><name>P</name><Point><coordinates>73.0,33.5,100</coordinates></Point></Placemark>
    <Placemark><name>L</name><LineString><coordinates>73,33 73.1,33.1 73.2,33.2</coordinates></LineString></Placemark>
    <Placemark><name>Poly</name><Polygon><outerBoundaryIs><LinearRing><coordinates>73,33 73.2,33 73.2,33.2 73,33.2 73,33</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
    </Document></kml>"""
    p = tmp_path / "a.kml"
    p.write_text(kml)
    kinds = [f["geometry"]["type"] for f in read_vector(p)["features"]]
    assert kinds == ["Point", "LineString", "Polygon"]
    kmz = tmp_path / "a.kmz"
    with zipfile.ZipFile(kmz, "w") as z:
        z.writestr("doc.kml", kml)
    assert len(read_vector(kmz)["features"]) == 3


def test_csv_points_with_lon_lat_columns(tmp_path):
    p = tmp_path / "pts.csv"
    p.write_text("name,Lon,Lat,height\nA,73.0,33.5,640\nB,73.1,33.6,700\n")
    out = read_vector(p)
    assert out["features"][1]["geometry"]["coordinates"] == [73.1, 33.6]
    assert out["features"][0]["properties"] == {"name": "A", "height": 640}


def test_csv_without_coordinate_columns_is_rejected(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError, match="longitude and latitude"):
        read_vector(p)


def test_csv_in_metres_is_rejected(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("x,y\n450000,3700000\n")
    with pytest.raises(ValueError, match="degrees"):
        read_vector(p)


@pytest.mark.parametrize("ext,driver", [(".shp", "ESRI Shapefile"), (".gpkg", "GPKG"), (".fgb", "FlatGeobuf")])
def test_gdal_formats_in_degrees(tmp_path, ext, driver):
    p = tmp_path / f"a{ext}"
    _write(p, driver, LINE, "LineString")
    out = read_vector(p)
    assert out["features"][0]["geometry"]["type"] == "LineString"
    assert out["features"][0]["properties"]["name"] == "f0"
    assert out["features"][0]["geometry"]["coordinates"][0] == [73.0, 33.5]


def test_shapefile_in_utm_is_reprojected_to_lon_lat(tmp_path):
    p = tmp_path / "utm.shp"
    # 73.0E, 33.5N expressed in UTM 43N (EPSG:32643)
    _write(p, "ESRI Shapefile", {"type": "Point", "coordinates": [314214.39, 3708509.35]}, "Point", crs="EPSG:32643")
    lon, lat = read_vector(p)["features"][0]["geometry"]["coordinates"]
    assert lon == pytest.approx(73.0, abs=0.01) and lat == pytest.approx(33.5, abs=0.01)


def test_zipped_shapefile(tmp_path):
    shp = tmp_path / "z.shp"
    _write(shp, "ESRI Shapefile", POLY, "Polygon")
    zp = tmp_path / "z.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for f in tmp_path.glob("z.*"):
            if f.suffix != ".zip":
                z.write(f, f.name)
    assert read_vector(zp)["features"][0]["geometry"]["type"] == "Polygon"


def test_gpx_waypoints(tmp_path):
    p = tmp_path / "a.gpx"
    p.write_text('<?xml version="1.0"?><gpx version="1.1" creator="t" xmlns="http://www.topografix.com/GPX/1/1">'
                 '<wpt lat="33.5" lon="73.0"><name>W</name></wpt></gpx>')
    f = read_vector(p)["features"][0]
    assert f["geometry"]["coordinates"] == [73.0, 33.5]


def test_unknown_extension_is_rejected(tmp_path):
    p = tmp_path / "a.xyz"
    p.write_text("x")
    with pytest.raises(ValueError, match="Unsupported"):
        read_vector(p)
