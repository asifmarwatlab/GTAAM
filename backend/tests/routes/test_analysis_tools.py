import pytest

API = "/api/v1"


def test_quality_and_statistics(client, layer_id):
    base = f"{API}/analysis/quality-statistics"
    s = client.get(f"{base}/layer-statistics/{layer_id}").json()
    assert s["min"] == pytest.approx(1500, abs=1) and s["max"] > 1850 and s["nodata_count"] == 0
    h = client.get(f"{base}/histogram/{layer_id}?bins=20").json()
    assert sum(h["counts"]) == 8000 and len(h["counts"]) == 20
    assert client.get(f"{base}/histogram/{layer_id}?bins=0").status_code == 400
    assert client.get(f"{base}/nodata-check/{layer_id}").json()["status"] == "clean"
    o = client.get(f"{base}/outlier-check/{layer_id}?method=zscore&threshold=2").json()
    assert o["method"] == "zscore"
    assert client.get(f"{base}/outlier-check/{layer_id}?method=bogus").status_code == 422


def test_measure_tools(client, layer_id):
    base = f"{API}/analysis/measure"
    d = client.post(f"{base}/distance", json={"layer_id": layer_id, "points": [[73.0, 33.4], [73.0, 33.5]]}).json()
    assert d["total"] == pytest.approx(11_119, rel=0.01)                 # 0.1 deg of latitude
    a = client.post(f"{base}/area", json={"layer_id": layer_id,
                                          "polygon": [[73, 33.4], [73.01, 33.4], [73.01, 33.41], [73, 33.41]]}).json()
    assert 0.9 < a["area_km2"] < 1.2
    p = client.post(f"{base}/elevation-profile", json={"layer_id": layer_id, "samples": 30,
                                                      "line": [[73.001, 33.489], [73.013, 33.489]]}).json()
    assert len(p["elevation"]) == 30 and p["max"] > p["min"]


@pytest.mark.parametrize("path,body", [
    ("surface-analysis/hillshade", {}), ("surface-analysis/slope", {"units": "percent"}),
    ("surface-analysis/aspect", {}), ("surface-analysis/curvature", {}),
    ("terrain-derivatives/roughness", {}), ("terrain-derivatives/tpi", {}),
    ("terrain-derivatives/ruggedness", {}),
])
def test_every_surface_tool_creates_a_new_layer(client, layer_id, path, body):
    r = client.post(f"{API}/analysis/{path}", json={"layer_id": layer_id, **body})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["layer"]["derived_from"] == layer_id and out["statistics"]["count"] > 0
    assert len(client.get(f"{API}/file/add-data/layers").json()) == 2


def test_contours_become_a_vector_layer(client, layer_id):
    r = client.post(f"{API}/analysis/terrain-derivatives/contours", json={"layer_id": layer_id, "interval": 100})
    assert r.status_code == 200 and r.json()["extra"]["feature_count"] >= 3
    vid = r.json()["layer"]["id"]
    assert client.get(f"{API}/file/add-data/layers/{vid}/geojson").json()["type"] == "FeatureCollection"


def test_tools_data_management(client, layer_id):
    base = f"{API}/tools/data-management"
    clip = client.post(f"{base}/clip", json={"layer_id": layer_id,
                                             "bounds": {"min_x": 73.005, "min_y": 33.485, "max_x": 73.015, "max_y": 33.495}})
    assert clip.status_code == 200 and clip.json()["layer"]["width"] < 100
    assert client.post(f"{base}/clip", json={"layer_id": layer_id,
                                             "bounds": {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1}}).status_code == 400
    assert client.post(f"{base}/clip", json={"layer_id": layer_id,
                                             "bounds": {"min_x": 5, "min_y": 0, "max_x": 1, "max_y": 1}}).status_code == 422
    rs = client.post(f"{base}/resample", json={"layer_id": layer_id, "cell_size": 0.00055556, "method": "nearest"})
    assert rs.json()["layer"]["width"] == 50
    rp = client.post(f"{base}/reproject", json={"layer_id": layer_id, "epsg": 32643})
    assert rp.status_code == 200 and rp.json()["layer"]["crs"] == "EPSG:32643"
    assert client.post(f"{base}/fill-nodata", json={"layer_id": layer_id}).status_code == 200


def test_tools_inspect_and_workspace(client, layer_id):
    base = f"{API}/tools/inspect"
    hit = client.post(f"{base}/identify", json={"layer_id": layer_id, "x": 73.0 + 50.5 * 0.000277778, "y": 33.5 - 40.5 * 0.000277778}).json()
    assert hit["inside"] and hit["value"] > 1890                      # the hilltop (~1900 m)
    assert (hit["row"], hit["col"]) == (40, 50)
    out = client.get(f"{base}/pixel/{layer_id}?x=10&y=10").json()
    assert out["inside"] is False and out["value"] is None
    props = client.get(f"{base}/properties/{layer_id}").json()
    assert props["epsg"] == 4326 and props["dimensions"] == [100, 80] and props["nodata_pixels"] == 0
    assert client.get(f"{base}/metadata/{layer_id}").json()["file"] is None     # in-memory layer
    ws = f"{API}/tools/workspace"
    assert client.put(f"{ws}/options", json={"units": "imperial"}).json()["units"] == "imperial"
    assert client.put(f"{ws}/options", json={"default_ramp": "nope"}).status_code == 400
    assert client.get(f"{ws}/shortcuts").json() and client.get(f"{ws}/about").json()["version"]
